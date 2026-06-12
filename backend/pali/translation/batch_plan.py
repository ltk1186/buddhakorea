"""Local-only helpers for planning Gemini Batch translation shards."""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from decimal import Decimal
from typing import Any

from .budget import (
    PriceProfile,
    TokenEstimate,
    estimate_request_cost,
    parse_usage_metadata,
)


@dataclass(frozen=True)
class BatchSegmentPlan:
    stable_segment_key: str
    source_text_hash: str
    source_path: str
    text_layer: str
    chunk_type: str
    prompt_text: str
    estimated_input_tokens: int
    estimated_output_tokens: int
    estimated_thinking_tokens: int = 0
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class BatchShard:
    shard_index: int
    segments: list[BatchSegmentPlan]
    estimated_input_tokens: int
    estimated_output_tokens: int
    estimated_thinking_tokens: int
    estimated_cost_usd: Decimal
    estimated_jsonl_bytes: int


@dataclass(frozen=True)
class ParsedBatchResultLine:
    stable_segment_key: str | None
    status: str
    response: dict[str, Any] | None = None
    error: dict[str, Any] | None = None
    usage_status: str = "missing"
    error_message: str = ""


def split_segments_into_budgeted_shards(
    segments: list[BatchSegmentPlan],
    *,
    price_profile: PriceProfile,
    max_estimated_cost_usd: Decimal,
    max_segments: int,
    max_jsonl_bytes: int | None = None,
) -> list[BatchShard]:
    shards: list[BatchShard] = []
    current: list[BatchSegmentPlan] = []

    for segment in segments:
        candidate = [*current, segment]
        if current and exceeds_shard_limits(
            candidate,
            price_profile=price_profile,
            max_estimated_cost_usd=max_estimated_cost_usd,
            max_segments=max_segments,
            max_jsonl_bytes=max_jsonl_bytes,
        ):
            shards.append(build_shard(len(shards), current, price_profile))
            current = [segment]
        else:
            current = candidate

    if current:
        shards.append(build_shard(len(shards), current, price_profile))
    return shards


def exceeds_shard_limits(
    segments: list[BatchSegmentPlan],
    *,
    price_profile: PriceProfile,
    max_estimated_cost_usd: Decimal,
    max_segments: int,
    max_jsonl_bytes: int | None,
) -> bool:
    if len(segments) > max_segments:
        return True
    shard = build_shard(0, segments, price_profile)
    if shard.estimated_cost_usd > max_estimated_cost_usd:
        return True
    if max_jsonl_bytes is not None and shard.estimated_jsonl_bytes > max_jsonl_bytes:
        return True
    return False


def build_shard(
    shard_index: int,
    segments: list[BatchSegmentPlan],
    price_profile: PriceProfile,
) -> BatchShard:
    estimated_input = sum(segment.estimated_input_tokens for segment in segments)
    estimated_output = sum(segment.estimated_output_tokens for segment in segments)
    estimated_thinking = sum(segment.estimated_thinking_tokens for segment in segments)
    estimated_cost = sum(
        (
            estimate_request_cost(
                TokenEstimate(
                    input_tokens=segment.estimated_input_tokens,
                    output_tokens=segment.estimated_output_tokens,
                    thinking_tokens=segment.estimated_thinking_tokens,
                ),
                price_profile,
            )
            for segment in segments
        ),
        Decimal("0"),
    )
    return BatchShard(
        shard_index=shard_index,
        segments=segments,
        estimated_input_tokens=estimated_input,
        estimated_output_tokens=estimated_output,
        estimated_thinking_tokens=estimated_thinking,
        estimated_cost_usd=estimated_cost,
        estimated_jsonl_bytes=estimate_jsonl_bytes(segments),
    )


def build_provider_jsonl_line(
    segment: BatchSegmentPlan,
    *,
    generation_config: dict[str, Any],
) -> dict[str, Any]:
    return {
        "key": segment.stable_segment_key,
        "request": {
            "contents": [
                {
                    "role": "user",
                    "parts": [{"text": segment.prompt_text}],
                }
            ],
            "generation_config": generation_config,
        },
    }


def build_sidecar_metadata(segment: BatchSegmentPlan, estimated_cost_usd: Decimal) -> dict[str, Any]:
    return {
        "stable_segment_key": segment.stable_segment_key,
        "source_text_hash": segment.source_text_hash,
        "source_path": segment.source_path,
        "text_layer": segment.text_layer,
        "chunk_type": segment.chunk_type,
        "estimated_input_tokens": segment.estimated_input_tokens,
        "estimated_output_tokens": segment.estimated_output_tokens,
        "estimated_thinking_tokens": segment.estimated_thinking_tokens,
        "estimated_cost_usd": str(estimated_cost_usd),
        **segment.metadata,
    }


def render_jsonl(segments: list[BatchSegmentPlan], generation_config: dict[str, Any]) -> str:
    return "\n".join(
        json.dumps(
            build_provider_jsonl_line(segment, generation_config=generation_config),
            ensure_ascii=False,
        )
        for segment in segments
    )


def parse_batch_result_line(line: str | dict[str, Any]) -> ParsedBatchResultLine:
    data = json.loads(line) if isinstance(line, str) else line
    key = data.get("key") or data.get("metadata", {}).get("key")
    if data.get("error") or data.get("status"):
        error = data.get("error") or data.get("status")
        return ParsedBatchResultLine(
            stable_segment_key=key,
            status="failed",
            error=error,
            error_message=str(error),
        )

    response = data.get("response") or data.get("inlineResponse", {}).get("response") or data
    usage_result = parse_usage_metadata(response)
    if usage_result.status != "success":
        return ParsedBatchResultLine(
            stable_segment_key=key,
            status="needs_retry",
            response=response,
            usage_status=usage_result.status,
            error_message=usage_result.error_message,
        )
    return ParsedBatchResultLine(
        stable_segment_key=key,
        status="succeeded",
        response=response,
        usage_status=usage_result.status,
    )


def estimate_jsonl_bytes(segments: list[BatchSegmentPlan]) -> int:
    return len(render_jsonl(segments, generation_config={}).encode("utf-8"))

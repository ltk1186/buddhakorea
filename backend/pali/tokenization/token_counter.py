"""Local token counters for Pali corpus sizing.

These counters never call provider APIs. OpenAI/GPT-family counts use local
tiktoken when available. Gemini-family counts are explicitly approximate.
"""

from __future__ import annotations

import json
import math
from abc import ABC, abstractmethod
from collections import Counter, defaultdict
from dataclasses import dataclass
from pathlib import Path
from statistics import mean
from typing import Any


DEFAULT_PROFILES = [
    {
        "profile_id": "gpt_local_default",
        "provider": "openai",
        "counter": "tiktoken",
        "model": "CONFIGURED_LATER",
        "encoding_fallback": "cl100k_base",
        "token_threshold": 8000,
        "notes": "Local GPT-family token estimate using tiktoken. Fill exact model later.",
    },
    {
        "profile_id": "gemini_local_approx",
        "provider": "gemini",
        "counter": "sentencepiece_or_heuristic",
        "sentencepiece_model_path": None,
        "token_threshold": 8000,
        "notes": "Local approximate Gemini-family estimate. Not official billing count.",
    },
]


@dataclass(frozen=True)
class TokenCountResult:
    profile_id: str
    provider: str
    counter: str
    token_count: int
    source_chars: int
    normalized_chars: int
    model: str | None = None
    encoding: str | None = None
    approximate: bool = False
    fallback_used: bool = False
    warnings: tuple[str, ...] = ()


class TokenCounter(ABC):
    def __init__(self, profile: dict[str, Any]):
        self.profile = profile
        self.profile_id = profile["profile_id"]
        self.provider = profile.get("provider", "unknown")
        self.counter = profile.get("counter", "unknown")

    @abstractmethod
    def count(self, text: str) -> TokenCountResult:
        """Return a local token count for text."""


class CharBasedFallbackCounter(TokenCounter):
    def __init__(self, profile: dict[str, Any], *, chars_per_token: float = 4.0):
        super().__init__(profile)
        self.chars_per_token = chars_per_token

    def count(self, text: str) -> TokenCountResult:
        token_count = max(1, math.ceil(len(text) / self.chars_per_token)) if text else 0
        return TokenCountResult(
            profile_id=self.profile_id,
            provider=self.provider,
            counter="char_based_fallback",
            token_count=token_count,
            source_chars=len(text),
            normalized_chars=len(text),
            approximate=True,
            fallback_used=True,
            warnings=("Used char-based fallback token estimate.",),
        )


class OpenAITiktokenCounter(TokenCounter):
    def __init__(self, profile: dict[str, Any]):
        super().__init__(profile)
        self.model = profile.get("model")
        self.encoding_name = profile.get("encoding_fallback", "cl100k_base")
        self.fallback_used = False
        self.warnings: list[str] = []
        try:
            import tiktoken

            if self.model and self.model != "CONFIGURED_LATER":
                try:
                    self.encoding = tiktoken.encoding_for_model(self.model)
                    self.encoding_name = self.encoding.name
                except KeyError:
                    self.encoding = tiktoken.get_encoding(self.encoding_name)
                    self.fallback_used = True
                    self.warnings.append(
                        f"Model {self.model!r} not known to tiktoken; used {self.encoding_name!r}."
                    )
            else:
                self.encoding = tiktoken.get_encoding(self.encoding_name)
                self.fallback_used = True
                self.warnings.append("No exact model configured; used fallback encoding.")
        except Exception as exc:  # pragma: no cover - depends on optional runtime package.
            self.encoding = None
            self.fallback_used = True
            self.warnings.append(f"tiktoken unavailable; used char fallback: {exc}")
            self.char_counter = CharBasedFallbackCounter(profile)

    def count(self, text: str) -> TokenCountResult:
        if self.encoding is None:
            result = self.char_counter.count(text)
            return TokenCountResult(
                profile_id=self.profile_id,
                provider=self.provider,
                counter=result.counter,
                token_count=result.token_count,
                source_chars=len(text),
                normalized_chars=len(text),
                model=self.model,
                approximate=True,
                fallback_used=True,
                warnings=tuple(self.warnings + list(result.warnings)),
            )

        return TokenCountResult(
            profile_id=self.profile_id,
            provider=self.provider,
            counter="tiktoken",
            token_count=len(self.encoding.encode(text)),
            source_chars=len(text),
            normalized_chars=len(text),
            model=self.model,
            encoding=self.encoding_name,
            approximate=False,
            fallback_used=self.fallback_used,
            warnings=tuple(self.warnings),
        )


class GeminiSentencePieceApproxCounter(TokenCounter):
    """Approximate Gemini-family counter using SentencePiece or a heuristic fallback."""

    def __init__(self, profile: dict[str, Any]):
        super().__init__(profile)
        self.model_path = profile.get("sentencepiece_model_path")
        self.processor = None
        self.fallback_used = False
        self.warnings: list[str] = []

        if self.model_path:
            try:
                import sentencepiece as spm

                self.processor = spm.SentencePieceProcessor(model_file=str(self.model_path))
            except Exception as exc:  # pragma: no cover - depends on optional runtime package/model.
                self.fallback_used = True
                self.warnings.append(f"SentencePiece model unavailable; used heuristic fallback: {exc}")
        else:
            self.fallback_used = True
            self.warnings.append("No SentencePiece model configured; used heuristic fallback.")

    def count(self, text: str) -> TokenCountResult:
        if self.processor is not None:
            token_count = len(self.processor.encode(text, out_type=int))
            counter = "sentencepiece_approx"
        else:
            token_count = heuristic_gemini_token_count(text)
            counter = "heuristic_gemini_approx"

        return TokenCountResult(
            profile_id=self.profile_id,
            provider=self.provider,
            counter=counter,
            token_count=token_count,
            source_chars=len(text),
            normalized_chars=len(text),
            approximate=True,
            fallback_used=self.fallback_used,
            warnings=tuple(self.warnings),
        )


def heuristic_gemini_token_count(text: str) -> int:
    if not text:
        return 0
    whitespace_units = len(text.split())
    char_units = math.ceil(len(text) / 4)
    return max(1, max(whitespace_units, char_units))


def load_token_profiles(path: str | Path | None = None) -> list[dict[str, Any]]:
    if path is None:
        return [dict(profile) for profile in DEFAULT_PROFILES]
    payload = json.loads(Path(path).read_text(encoding="utf-8"))
    return payload.get("profiles", [])


def build_counter(profile: dict[str, Any]) -> TokenCounter:
    provider = profile.get("provider")
    counter = profile.get("counter")
    if provider == "openai" and counter == "tiktoken":
        return OpenAITiktokenCounter(profile)
    if provider == "gemini":
        return GeminiSentencePieceApproxCounter(profile)
    return CharBasedFallbackCounter(profile)


def build_token_report(
    artifact: dict[str, Any],
    *,
    profiles: list[dict[str, Any]] | None = None,
) -> dict[str, Any]:
    literature = artifact["literature"]
    segments = artifact["segments"]
    profiles = profiles or load_token_profiles(None)
    counters = [build_counter(profile) for profile in profiles]

    texts = [segment["normalized_text"] for segment in segments]
    full_text = "\n".join(texts)
    tokenizers_used: dict[str, Any] = {}
    tokenizer_warnings: list[str] = []
    estimated_source_tokens_by_profile: dict[str, int] = {}
    average_tokens_per_segment_by_profile: dict[str, float] = {}
    percentile_by_profile: dict[str, dict[str, int]] = {}
    top_20_largest_segments_by_profile: dict[str, list[dict[str, Any]]] = {}
    segments_over_token_threshold_by_profile: dict[str, list[dict[str, Any]]] = {}
    chunk_type_token_breakdown: dict[str, dict[str, int]] = {}
    heading_token_breakdown: dict[str, dict[str, int]] = {}
    text_layer_token_breakdown: dict[str, dict[str, int]] = {}

    for counter in counters:
        profile_id = counter.profile_id
        total_result = counter.count(full_text)
        tokenizers_used[profile_id] = {
            "provider": total_result.provider,
            "counter": total_result.counter,
            "model": total_result.model,
            "encoding": total_result.encoding,
            "approximate": total_result.approximate,
            "fallback_used": total_result.fallback_used,
        }
        tokenizer_warnings.extend(
            f"{profile_id}: {warning}" for warning in total_result.warnings
        )
        estimated_source_tokens_by_profile[profile_id] = total_result.token_count

        per_segment: list[tuple[dict[str, Any], int]] = [
            (segment, counter.count(segment["normalized_text"]).token_count)
            for segment in segments
        ]
        token_values = [token_count for _, token_count in per_segment]
        average_tokens_per_segment_by_profile[profile_id] = (
            round(mean(token_values), 2) if token_values else 0.0
        )
        percentile_by_profile[profile_id] = {
            "p50": percentile(token_values, 50),
            "p90": percentile(token_values, 90),
            "p95": percentile(token_values, 95),
        }
        top_20_largest_segments_by_profile[profile_id] = [
            {
                "stable_segment_key": segment["stable_segment_key"],
                "sort_order": segment["sort_order"],
                "canonical_ref": segment["canonical_ref"],
                "chunk_type": segment["chunk_type"],
                "token_count": token_count,
                "char_count": len(segment["normalized_text"]),
            }
            for segment, token_count in sorted(
                per_segment, key=lambda item: item[1], reverse=True
            )[:20]
        ]
        threshold = int(counter.profile.get("token_threshold", 8000))
        segments_over_token_threshold_by_profile[profile_id] = [
            {
                "stable_segment_key": segment["stable_segment_key"],
                "sort_order": segment["sort_order"],
                "canonical_ref": segment["canonical_ref"],
                "token_count": token_count,
                "threshold": threshold,
            }
            for segment, token_count in per_segment
            if token_count > threshold
        ]
        chunk_type_token_breakdown[profile_id] = breakdown_by_field(
            per_segment, lambda segment: segment.get("chunk_type") or "unknown"
        )
        heading_token_breakdown[profile_id] = breakdown_by_field(
            per_segment, primary_heading_key
        )
        text_layer_token_breakdown[profile_id] = breakdown_by_field(
            per_segment, lambda segment: segment.get("text_layer") or "unknown"
        )

    return {
        "source_path": literature.get("source_path"),
        "source_commit": literature.get("source_commit"),
        "literature_id": literature.get("literature_id"),
        "text_layer": literature.get("text_layer"),
        "total_segments": len(segments),
        "total_source_chars": sum(len(segment["original_text"]) for segment in segments),
        "total_normalized_chars": sum(len(segment["normalized_text"]) for segment in segments),
        "tokenizers_used": tokenizers_used,
        "tokenizer_warnings": sorted(set(tokenizer_warnings)),
        "estimated_source_tokens_by_profile": estimated_source_tokens_by_profile,
        "average_tokens_per_segment_by_profile": average_tokens_per_segment_by_profile,
        "p50_p90_p95_segment_tokens_by_profile": percentile_by_profile,
        "top_20_largest_segments_by_profile": top_20_largest_segments_by_profile,
        "segments_over_token_threshold_by_profile": segments_over_token_threshold_by_profile,
        "chunk_type_token_breakdown": chunk_type_token_breakdown,
        "heading_token_breakdown": heading_token_breakdown,
        "text_layer_token_breakdown": text_layer_token_breakdown,
    }


def breakdown_by_field(
    per_segment: list[tuple[dict[str, Any], int]],
    key_func: Any,
) -> dict[str, int]:
    totals: defaultdict[str, int] = defaultdict(int)
    for segment, token_count in per_segment:
        totals[str(key_func(segment))] += token_count
    return dict(sorted(totals.items()))


def primary_heading_key(segment: dict[str, Any]) -> str:
    heading_path = segment.get("heading_path") or []
    if not heading_path:
        return "headingless"
    heading = heading_path[-1]
    return f"{heading.get('type', 'heading')}:{heading.get('text', '')}"


def percentile(values: list[int], pct: int) -> int:
    if not values:
        return 0
    ordered = sorted(values)
    index = math.ceil((pct / 100) * len(ordered)) - 1
    return ordered[max(0, min(index, len(ordered) - 1))]


def merge_tokenizer_warnings(reports: list[dict[str, Any]]) -> list[str]:
    warnings: set[str] = set()
    for report in reports:
        warnings.update(report.get("tokenizer_warnings", []))
    return sorted(warnings)


def add_counter_dict(target: dict[str, int], source: dict[str, int]) -> None:
    for key, value in source.items():
        target[key] = target.get(key, 0) + value

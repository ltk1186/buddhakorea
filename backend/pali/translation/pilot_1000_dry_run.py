"""Step 6 local-only dry-run for the fixed Pali pilot 1,000 selection.

This module builds request previews, cost estimates, corpus extrapolation, and
QA/retry plans. It does not call provider APIs and intentionally has no live
submit path.
"""

from __future__ import annotations

import json
import re
from collections import Counter, defaultdict
from dataclasses import dataclass
from decimal import Decimal, ROUND_HALF_UP
from pathlib import Path
from statistics import mean
from typing import Any

from backend.pali.scripts.submit_gemini_smoke_batch import DEFAULT_MODEL
from backend.pali.translation.budget import PriceProfile, TokenEstimate, estimate_request_cost
from backend.pali.translation.natural_ko_readability import (
    NATURAL_KO_V2_2_MARKER,
    render_natural_ko_v2_2_prompt,
)
from backend.pali.translation.prompts import render_korean_advanced_prompt_v1
from backend.pali.translation.response_schema_smoke import (
    build_response_schema_experiment,
    validate_response_schema_dialect,
)


PINNED_INVENTORY_COMMIT = "49bc86914748589a2501b548cc6b3e97a8abe018"
DEFAULT_MANIFEST = Path("data/pilot_sets/pali/pilot_1000_v1_manifest.json")
DEFAULT_INVENTORY_CACHE = Path("data/pilot_sets/pali/pilot_300_v1_inventory_cache_49bc869.json")
DEFAULT_OUT = Path("data/reports/pali/pilot_1000_batch")
DEFAULT_HARD_CAP_USD = Decimal("50")
PLANNED_REQUESTS = 1000
GENERATION_TEMPERATURE = Decimal("0.2")
RESPONSE_FIELDS = [
    "literal_ko",
    "natural_ko",
    "terms",
    "grammar_notes",
    "doctrinal_notes",
    "uncertainties",
    "quality_flags",
]
STIFF_LITERAL_ANCHORS = (
    "빠알리 문장 구조와 어순을 가능한 한 보존하십시오",
    "한국어가 다소 어색해도 괜찮습니다",
)
PRICE_PROFILE = PriceProfile(
    input_usd_per_million_tokens=Decimal("1"),
    output_usd_per_million_tokens=Decimal("6"),
    thinking_usd_per_million_tokens=Decimal("6"),
)
CORPUS_SEGMENT_COUNT = 203_594
CORPUS_LAYER_PROPORTIONS = {"mula": Decimal("0.522"), "atthakatha": Decimal("0.377"), "tika": Decimal("0.100")}
CORPUS_LENGTH_PROPORTIONS = {"short": Decimal("0.331"), "medium": Decimal("0.329"), "long": Decimal("0.340")}
CORPUS_CHUNK_PROPORTIONS = {"prose": Decimal("0.757"), "verse": Decimal("0.243")}


class Pilot1000DryRunBlocked(RuntimeError):
    def __init__(self, status: str, message: str, details: dict[str, Any] | None = None):
        super().__init__(message)
        self.status = status
        self.message = message
        self.details = details or {}


@dataclass(frozen=True)
class Step6Paths:
    out_dir: Path
    request_preview: Path
    request_preview_sample_md: Path
    cost_estimate_json: Path
    cost_estimate_md: Path
    corpus_extrapolation_json: Path
    corpus_extrapolation_md: Path
    submit_plan_md: Path
    qa_retry_plan_md: Path
    validation_report_json: Path
    validation_report_md: Path
    dry_run_manifest_json: Path
    no_api_md: Path


def step6_paths(out_dir: Path) -> Step6Paths:
    return Step6Paths(
        out_dir=out_dir,
        request_preview=out_dir / "pilot_1000_request_preview.jsonl",
        request_preview_sample_md=out_dir / "pilot_1000_request_preview_sample.md",
        cost_estimate_json=out_dir / "pilot_1000_cost_estimate.json",
        cost_estimate_md=out_dir / "pilot_1000_cost_estimate.md",
        corpus_extrapolation_json=out_dir / "pilot_1000_corpus_extrapolation.json",
        corpus_extrapolation_md=out_dir / "pilot_1000_corpus_extrapolation.md",
        submit_plan_md=out_dir / "pilot_1000_submit_plan.md",
        qa_retry_plan_md=out_dir / "pilot_1000_qa_retry_plan.md",
        validation_report_json=out_dir / "pilot_1000_validation_report.json",
        validation_report_md=out_dir / "pilot_1000_validation_report.md",
        dry_run_manifest_json=out_dir / "pilot_1000_dry_run_manifest.json",
        no_api_md=out_dir / "pilot_1000_no_api_executed.md",
    )


def read_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def read_jsonl(path: Path) -> list[dict[str, Any]]:
    if not path.exists():
        return []
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


def write_json(path: Path, payload: Any, *, pretty: bool = False) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2 if pretty else None, sort_keys=pretty) + "\n",
        encoding="utf-8",
    )


def write_jsonl(path: Path, rows: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(json.dumps(row, ensure_ascii=False) for row in rows) + "\n", encoding="utf-8")


def quantize_usd(value: Decimal) -> str:
    return str(value.quantize(Decimal("0.000001"), rounding=ROUND_HALF_UP))


def decimal_rate(numerator: int, denominator: int) -> str:
    if denominator <= 0:
        return "0.000000"
    return f"{numerator / denominator:.6f}"


def word_tokens(text: str) -> list[str]:
    return re.findall(r"[\wāīūṅñṭḍṇḷṃĀĪŪṄÑṬḌṆḶṂ]+", text)


def source_unit_from_text(text: str) -> Decimal:
    return Decimal(str(max(len(word_tokens(text)), len(text) / 5, 1)))


def bucket_key(item: dict[str, Any]) -> tuple[str, str, str]:
    return (
        str(item.get("text_layer") or "unknown"),
        str(item.get("length_bucket") or "unknown"),
        str(item.get("chunk_type") or "unknown"),
    )


def bucket_key_string(key: tuple[str, ...]) -> str:
    return "×".join(key)


def backoff_keys(item_or_key: dict[str, Any] | tuple[str, str, str]) -> list[tuple[str, ...]]:
    if isinstance(item_or_key, tuple):
        layer, length, chunk = item_or_key
    else:
        layer, length, chunk = bucket_key(item_or_key)
    return [
        ("primary", layer, length, chunk),
        ("layer_length", layer, length),
        ("layer", layer),
        ("global",),
    ]


def percentile_nearest_rank(values: list[Decimal], percentile: Decimal) -> Decimal:
    if not values:
        return Decimal("0")
    ordered = sorted(values)
    index = int((Decimal(len(ordered)) * percentile).to_integral_value(rounding=ROUND_HALF_UP)) - 1
    index = max(0, min(index, len(ordered) - 1))
    return ordered[index]


def metric_stats(values: list[Decimal]) -> dict[str, Any]:
    if not values:
        return {"n": 0, "mean": "0", "p90": "0"}
    return {
        "n": len(values),
        "mean": str(sum(values, Decimal("0")) / Decimal(len(values))),
        "p90": str(percentile_nearest_rank(values, Decimal("0.90"))),
    }


def load_selection_manifest(path: Path) -> dict[str, Any]:
    if not path.exists():
        raise Pilot1000DryRunBlocked("BLOCKED_MISSING_MANIFEST", f"manifest missing: {path}")
    manifest = read_json(path)
    items = manifest.get("items") or []
    if len(items) != PLANNED_REQUESTS:
        raise Pilot1000DryRunBlocked("BLOCKED_MANIFEST_COUNT", f"expected 1000 manifest items, got {len(items)}")
    source_commit = manifest.get("inventory_source_commit")
    if source_commit != PINNED_INVENTORY_COMMIT:
        raise Pilot1000DryRunBlocked(
            "BLOCKED_INVENTORY_SOURCE_COMMIT",
            f"expected {PINNED_INVENTORY_COMMIT}, got {source_commit}",
        )
    return manifest


def load_inventory_cache(path: Path) -> dict[str, Any]:
    if not path.exists():
        raise Pilot1000DryRunBlocked("BLOCKED_MISSING_INVENTORY_CACHE", f"inventory cache missing: {path}")
    payload = read_json(path)
    if payload.get("source_commit") != PINNED_INVENTORY_COMMIT:
        raise Pilot1000DryRunBlocked(
            "BLOCKED_INVENTORY_CACHE_COMMIT",
            f"expected {PINNED_INVENTORY_COMMIT}, got {payload.get('source_commit')}",
        )
    return payload


def enrich_manifest_items(manifest: dict[str, Any], inventory_payload: dict[str, Any]) -> list[dict[str, Any]]:
    inventory = {
        (item.get("stable_segment_key"), item.get("source_text_hash")): item
        for item in inventory_payload.get("items") or []
    }
    by_key = {item.get("stable_segment_key"): item for item in inventory_payload.get("items") or []}
    enriched: list[dict[str, Any]] = []
    for item in manifest.get("items") or []:
        inv = inventory.get((item.get("stable_segment_key"), item.get("source_text_hash"))) or by_key.get(
            item.get("stable_segment_key")
        )
        if not inv:
            raise Pilot1000DryRunBlocked(
                "BLOCKED_INVENTORY_ITEM_MISSING",
                f"inventory item missing for {item.get('stable_segment_key')}",
            )
        if inv.get("source_text_hash") != item.get("source_text_hash"):
            raise Pilot1000DryRunBlocked(
                "BLOCKED_SOURCE_TEXT_HASH_MISMATCH",
                f"source_text_hash mismatch for {item.get('stable_segment_key')}",
            )
        merged = {**inv, **item}
        merged["original_text"] = inv.get("original_text") or inv.get("normalized_text") or item.get("original_text")
        merged["normalized_text"] = inv.get("normalized_text") or merged["original_text"]
        enriched.append(merged)
    return enriched


def sanitize_reader_ko_references(prompt: str) -> str:
    """Remove negative reader_ko reminders from Step 6 previews.

    Step 6 requires the literal string reader_ko to be absent from prompt text,
    schema, metadata, and output fields. The schema already prevents new fields,
    so the preview can omit the old negative reminder without changing output
    structure.
    """
    return "\n".join(line for line in prompt.splitlines() if "reader_ko" not in line)


def segment_for_prompt(item: dict[str, Any]) -> dict[str, Any]:
    return {
        "stable_segment_key": item.get("stable_segment_key"),
        "source_path": item.get("source_path"),
        "source_text_hash": item.get("source_text_hash"),
        "text_layer": item.get("text_layer"),
        "chunk_type": item.get("chunk_type"),
        "length_bucket": item.get("length_bucket"),
        "original_text": item.get("original_text"),
        "normalized_text": item.get("normalized_text") or item.get("original_text"),
        "canonical_ref": item.get("canonical_ref") or "",
        "heading_path": item.get("heading_path") or [],
    }


def build_request_preview(items: list[dict[str, Any]]) -> list[dict[str, Any]]:
    schema = build_response_schema_experiment()["response_schema"]
    dialect = validate_response_schema_dialect(schema)
    if not dialect["valid"]:
        raise Pilot1000DryRunBlocked("BLOCKED_RESPONSE_SCHEMA_DIALECT", "response schema dialect invalid", dialect)
    generation_config = {
        "temperature": float(GENERATION_TEMPERATURE),
        "response_mime_type": "application/json",
        "response_schema": schema,
    }
    rows: list[dict[str, Any]] = []
    for item in items:
        prompt_v1 = render_korean_advanced_prompt_v1(segment_for_prompt(item))
        prompt = sanitize_reader_ko_references(render_natural_ko_v2_2_prompt(prompt_v1, item))
        metadata = {
            "stable_segment_key": item.get("stable_segment_key"),
            "source_path": item.get("source_path"),
            "source_text_hash": item.get("source_text_hash"),
            "text_layer": item.get("text_layer"),
            "chunk_type": item.get("chunk_type"),
            "length_bucket": item.get("length_bucket"),
            "selection_group": item.get("selection_group"),
            "selection_bucket": item.get("selection_bucket"),
            "source_commit": item.get("source_commit") or PINNED_INVENTORY_COMMIT,
            "original_text": item.get("original_text"),
        }
        rows.append(
            {
                "key": item["stable_segment_key"],
                "arm": "pilot_1000_natural_ko_v2_2_response_schema",
                "metadata": metadata,
                "request": {
                    "model": DEFAULT_MODEL,
                    "contents": [{"role": "user", "parts": [{"text": prompt}]}],
                    "generation_config": dict(generation_config),
                },
            }
        )
    return rows


def prompt_for_row(row: dict[str, Any]) -> str:
    return str(row.get("request", {}).get("contents", [{}])[0].get("parts", [{}])[0].get("text") or "")


def schema_for_row(row: dict[str, Any]) -> dict[str, Any]:
    return row.get("request", {}).get("generation_config", {}).get("response_schema") or {}


def stable_keys(items: list[dict[str, Any]]) -> list[str]:
    return [str(item.get("stable_segment_key") or item.get("key") or "") for item in items]


def validate_preview(manifest: dict[str, Any], items: list[dict[str, Any]], rows: list[dict[str, Any]]) -> dict[str, Any]:
    errors: list[str] = []
    warnings: list[str] = []
    manifest_items = manifest.get("items") or []
    manifest_keys = [item.get("stable_segment_key") for item in manifest_items]
    row_keys = [row.get("key") for row in rows]
    if len(rows) != PLANNED_REQUESTS:
        errors.append(f"BLOCKED_REQUEST_COUNT:{len(rows)}")
    if len(set(row_keys)) != len(row_keys):
        errors.append("BLOCKED_DUPLICATE_STABLE_SEGMENT_KEY")
    if row_keys != manifest_keys:
        errors.append("BLOCKED_PREVIEW_ORDER_OR_KEYS_DIFFER_FROM_MANIFEST")
    for item in items:
        key = item.get("stable_segment_key")
        for field in ("source_text_hash", "source_path", "original_text"):
            if not item.get(field):
                errors.append(f"BLOCKED_MISSING_{field.upper()}:{key}")
    configs = [json.dumps(row.get("request", {}).get("generation_config"), sort_keys=True, ensure_ascii=False) for row in rows]
    if len(set(configs)) != 1:
        errors.append("BLOCKED_GENERATION_CONFIG_DIFFERS")
    for row in rows:
        key = row.get("key")
        prompt = prompt_for_row(row)
        schema = schema_for_row(row)
        config = row.get("request", {}).get("generation_config") or {}
        metadata_text = json.dumps(row.get("metadata") or {}, ensure_ascii=False)
        if NATURAL_KO_V2_2_MARKER not in prompt:
            errors.append(f"BLOCKED_D_V2_2_MARKER_MISSING:{key}")
        for anchor in STIFF_LITERAL_ANCHORS:
            if anchor in prompt:
                errors.append(f"BLOCKED_OLD_STIFF_LITERAL_ANCHOR:{key}:{anchor}")
        if "reader_ko" in prompt or "reader_ko" in metadata_text:
            errors.append(f"BLOCKED_READER_KO_PRESENT:{key}")
        properties = schema.get("properties") or {}
        if "reader_ko" in properties:
            errors.append(f"BLOCKED_READER_KO_IN_SCHEMA:{key}")
        if set(properties) != set(RESPONSE_FIELDS):
            errors.append(f"BLOCKED_RESPONSE_SCHEMA_FIELDS:{key}")
        if "additionalProperties" in json.dumps(schema, ensure_ascii=False):
            errors.append(f"BLOCKED_ADDITIONAL_PROPERTIES:{key}")
        if "propertyOrdering" not in schema:
            errors.append(f"BLOCKED_SCHEMA_PROPERTY_ORDERING_MISSING:{key}")
        if config.get("temperature") != float(GENERATION_TEMPERATURE):
            errors.append(f"BLOCKED_TEMPERATURE:{key}")
        if config.get("response_mime_type") != "application/json":
            errors.append(f"BLOCKED_RESPONSE_MIME_TYPE:{key}")
    return {
        "errors": sorted(set(errors)),
        "warnings": sorted(set(warnings)),
        "request_count": len(rows),
        "duplicate_count": len(row_keys) - len(set(row_keys)),
        "manifest_key_set_equals_preview_key_set": set(row_keys) == set(manifest_keys),
        "manifest_order_equals_preview_order": row_keys == manifest_keys,
        "generation_config_identical": len(set(configs)) == 1 if configs else False,
    }


def calibration_rows_from_artifacts() -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    rows.extend(
        calibration_rows_from_pair(
            request_path=Path("data/reports/pali/natural_ko_calibration_v2_2/d_arm_30_request_preview.jsonl"),
            parsed_path=Path("data/reports/pali/natural_ko_calibration_v2_2/d_arm_30_parsed.json"),
            source_label="d_arm_30_v2_2_response_schema_actual",
        )
    )
    rows.extend(
        calibration_rows_from_pair(
            request_path=Path("data/reports/pali/step4_response_schema_smoke/arm_b_batch_input.jsonl"),
            parsed_path=Path("data/reports/pali/step4_response_schema_smoke/arm_b_parsed.json"),
            source_label="step4_arm_b_response_schema_actual",
        )
    )
    rows.extend(
        calibration_rows_from_parsed_only(
            parsed_path=Path("data/reports/pali/pilot_300_batch/pilot_300_batch_parsed_salvaged.json"),
            source_label="pilot_300_actual_freeform_backoff",
        )
    )
    return rows


def calibration_rows_from_pair(*, request_path: Path, parsed_path: Path, source_label: str) -> list[dict[str, Any]]:
    if not request_path.exists() or not parsed_path.exists():
        return []
    request_by_key = {row.get("key"): row for row in read_jsonl(request_path)}
    parsed = read_json(parsed_path)
    rows: list[dict[str, Any]] = []
    for item in parsed.get("items") or []:
        key = item.get("stable_segment_key")
        request = request_by_key.get(key)
        prompt = prompt_for_row(request) if request else ""
        row = calibration_row_from_parsed_item(item, source_label=source_label, prompt_chars=len(prompt) or None)
        if row:
            rows.append(row)
    return rows


def calibration_rows_from_parsed_only(*, parsed_path: Path, source_label: str) -> list[dict[str, Any]]:
    if not parsed_path.exists():
        return []
    parsed = read_json(parsed_path)
    rows: list[dict[str, Any]] = []
    for item in parsed.get("items") or []:
        row = calibration_row_from_parsed_item(item, source_label=source_label, prompt_chars=None)
        if row:
            rows.append(row)
    return rows


def calibration_row_from_parsed_item(
    item: dict[str, Any],
    *,
    source_label: str,
    prompt_chars: int | None,
) -> dict[str, Any] | None:
    input_tokens = int(item.get("prompt_token_count") or 0)
    output_tokens = int(item.get("candidates_token_count") or 0)
    thinking_tokens = int(item.get("thoughts_token_count") or 0)
    if input_tokens <= 0 or output_tokens <= 0:
        return None
    original_text = str(item.get("original_text") or "")
    source_unit = source_unit_from_text(original_text)
    row = {
        "stable_segment_key": item.get("stable_segment_key"),
        "text_layer": item.get("text_layer") or "unknown",
        "length_bucket": item.get("length_bucket") or "unknown",
        "chunk_type": item.get("chunk_type") or "unknown",
        "source_label": source_label,
        "source_unit": source_unit,
        "input_tokens": Decimal(input_tokens),
        "output_tokens": Decimal(output_tokens),
        "thinking_tokens": Decimal(thinking_tokens),
        "output_per_source_unit": Decimal(output_tokens) / source_unit,
        "thinking_per_source_unit": Decimal(thinking_tokens) / source_unit,
    }
    if prompt_chars and prompt_chars > 0:
        row["prompt_chars"] = Decimal(prompt_chars)
        row["input_per_prompt_char"] = Decimal(input_tokens) / Decimal(prompt_chars)
    return row


def build_metric_index(rows: list[dict[str, Any]], field: str) -> dict[tuple[str, ...], dict[str, Any]]:
    buckets: dict[tuple[str, ...], list[Decimal]] = defaultdict(list)
    for row in rows:
        if field not in row:
            continue
        for key in backoff_keys(row):
            buckets[key].append(Decimal(row[field]))
    return {key: metric_stats(values) for key, values in buckets.items()}


def choose_metric(
    item_or_key: dict[str, Any] | tuple[str, str, str],
    index: dict[tuple[str, ...], dict[str, Any]],
    mode: str,
    *,
    min_n: int = 5,
) -> tuple[Decimal, tuple[str, ...], int, bool]:
    for key in backoff_keys(item_or_key):
        stat = index.get(key)
        if stat and int(stat["n"]) >= min_n:
            return Decimal(str(stat[mode])), key, int(stat["n"]), key != backoff_keys(item_or_key)[0]
    stat = index.get(("global",))
    if stat:
        return Decimal(str(stat[mode])), ("global",), int(stat["n"]), True
    return Decimal("1"), ("constant_fallback",), 0, True


def estimate_costs(rows: list[dict[str, Any]], hard_cap_usd: Decimal) -> dict[str, Any]:
    calibration = calibration_rows_from_artifacts()
    input_index = build_metric_index(calibration, "input_per_prompt_char")
    output_index = build_metric_index(calibration, "output_per_source_unit")
    thinking_index = build_metric_index(calibration, "thinking_per_source_unit")
    item_estimates = []
    for row in rows:
        metadata = row["metadata"]
        item = {
            "text_layer": metadata.get("text_layer"),
            "length_bucket": metadata.get("length_bucket"),
            "chunk_type": metadata.get("chunk_type"),
        }
        prompt_chars = Decimal(len(prompt_for_row(row)))
        source_unit = source_unit_from_text(str(metadata.get("original_text") or ""))
        input_mean_ratio, input_mean_bucket, input_mean_n, input_mean_backoff = choose_metric(item, input_index, "mean")
        input_p90_ratio, input_p90_bucket, input_p90_n, input_p90_backoff = choose_metric(item, input_index, "p90")
        output_mean_ratio, output_mean_bucket, output_mean_n, output_mean_backoff = choose_metric(item, output_index, "mean")
        output_p90_ratio, output_p90_bucket, output_p90_n, output_p90_backoff = choose_metric(item, output_index, "p90")
        thinking_mean_ratio, thinking_mean_bucket, thinking_mean_n, thinking_mean_backoff = choose_metric(item, thinking_index, "mean")
        thinking_p90_ratio, thinking_p90_bucket, thinking_p90_n, thinking_p90_backoff = choose_metric(item, thinking_index, "p90")
        mean_tokens = TokenEstimate(
            input_tokens=max(1, int((prompt_chars * input_mean_ratio).to_integral_value(rounding=ROUND_HALF_UP))),
            output_tokens=max(1, int((source_unit * output_mean_ratio).to_integral_value(rounding=ROUND_HALF_UP))),
            thinking_tokens=max(0, int((source_unit * thinking_mean_ratio).to_integral_value(rounding=ROUND_HALF_UP))),
        )
        p90_tokens = TokenEstimate(
            input_tokens=max(1, int((prompt_chars * input_p90_ratio).to_integral_value(rounding=ROUND_HALF_UP))),
            output_tokens=max(1, int((source_unit * output_p90_ratio).to_integral_value(rounding=ROUND_HALF_UP))),
            thinking_tokens=max(0, int((source_unit * thinking_p90_ratio).to_integral_value(rounding=ROUND_HALF_UP))),
        )
        item_estimates.append(
            {
                "stable_segment_key": row["key"],
                "bucket_key": bucket_key_string(bucket_key(metadata)),
                "text_layer": metadata.get("text_layer"),
                "length_bucket": metadata.get("length_bucket"),
                "chunk_type": metadata.get("chunk_type"),
                "source_unit": str(source_unit),
                "prompt_chars": int(prompt_chars),
                "expected_mean": {
                    "input_tokens": mean_tokens.input_tokens,
                    "output_tokens": mean_tokens.output_tokens,
                    "thinking_tokens": mean_tokens.thinking_tokens,
                    "official_cost_usd": quantize_usd(estimate_request_cost(mean_tokens, PRICE_PROFILE)),
                },
                "planning_p90": {
                    "input_tokens": p90_tokens.input_tokens,
                    "output_tokens": p90_tokens.output_tokens,
                    "thinking_tokens": p90_tokens.thinking_tokens,
                    "official_cost_usd": quantize_usd(estimate_request_cost(p90_tokens, PRICE_PROFILE)),
                },
                "calibration": {
                    "input_mean_bucket": bucket_key_string(input_mean_bucket),
                    "input_mean_n": input_mean_n,
                    "input_p90_bucket": bucket_key_string(input_p90_bucket),
                    "input_p90_n": input_p90_n,
                    "output_mean_bucket": bucket_key_string(output_mean_bucket),
                    "output_mean_n": output_mean_n,
                    "output_p90_bucket": bucket_key_string(output_p90_bucket),
                    "output_p90_n": output_p90_n,
                    "thinking_mean_bucket": bucket_key_string(thinking_mean_bucket),
                    "thinking_mean_n": thinking_mean_n,
                    "thinking_p90_bucket": bucket_key_string(thinking_p90_bucket),
                    "thinking_p90_n": thinking_p90_n,
                    "backoff_used": any(
                        [
                            input_mean_backoff,
                            input_p90_backoff,
                            output_mean_backoff,
                            output_p90_backoff,
                            thinking_mean_backoff,
                            thinking_p90_backoff,
                        ]
                    ),
                },
            }
        )
    totals_mean = sum_estimate_items(item_estimates, "expected_mean")
    totals_p90 = sum_estimate_items(item_estimates, "planning_p90")
    bucket_summaries = summarize_estimate_buckets(item_estimates)
    p90_cost = Decimal(str(totals_p90["official_cost_usd"]))
    return {
        "schema_version": "pali_pilot_1000_cost_estimate_v1",
        "pricing": {
            "input_usd_per_1m_tokens": "1",
            "output_usd_per_1m_tokens": "6",
            "thinking_usd_per_1m_tokens": "6",
            "batch_discount_multiplier": "1",
        },
        "calibration_sources": sorted(set(row["source_label"] for row in calibration)),
        "calibration_row_count": len(calibration),
        "bucket_key": "text_layer×length_bucket×chunk_type",
        "thin_bucket_backoff_min_n": 5,
        "bucket_estimates": bucket_summaries,
        "estimate_totals": {
            "expected_mean": totals_mean,
            "planning_p90": totals_p90,
        },
        "pilot_1000_total_cost_mean": totals_mean["official_cost_usd"],
        "pilot_1000_total_cost_p90": totals_p90["official_cost_usd"],
        "hard_cap_usd": quantize_usd(hard_cap_usd),
        "cap_passed": p90_cost <= hard_cap_usd,
        "submit_ready": p90_cost <= hard_cap_usd,
        "top_cost_buckets": top_cost_buckets(bucket_summaries),
        "items": item_estimates,
        "limitations": [
            "Input token estimates use observed prompt_token_count/prompt_char ratios from response_schema runs.",
            "Output and thinking estimates use observed tokens/source-unit ratios, with pilot_300 as backoff only.",
            "Thin buckets deterministically back off from text_layer×length_bucket×chunk_type to layer×length, layer, then global calibration.",
        ],
    }


def sum_estimate_items(items: list[dict[str, Any]], field: str) -> dict[str, Any]:
    input_tokens = sum(int(item[field]["input_tokens"]) for item in items)
    output_tokens = sum(int(item[field]["output_tokens"]) for item in items)
    thinking_tokens = sum(int(item[field]["thinking_tokens"]) for item in items)
    cost = sum((Decimal(str(item[field]["official_cost_usd"])) for item in items), Decimal("0"))
    return {
        "input_tokens": input_tokens,
        "output_tokens": output_tokens,
        "thinking_tokens": thinking_tokens,
        "official_cost_usd": quantize_usd(cost),
    }


def summarize_estimate_buckets(items: list[dict[str, Any]]) -> list[dict[str, Any]]:
    grouped: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for item in items:
        grouped[item["bucket_key"]].append(item)
    summaries = []
    for key, rows in sorted(grouped.items()):
        mean_totals = sum_estimate_items(rows, "expected_mean")
        p90_totals = sum_estimate_items(rows, "planning_p90")
        backoff_count = sum(1 for row in rows if row["calibration"]["backoff_used"])
        summaries.append(
            {
                "bucket_key": key,
                "manifest_item_count": len(rows),
                "estimated_input_tokens_mean": round(mean(row["expected_mean"]["input_tokens"] for row in rows), 2),
                "estimated_input_tokens_p90": round(mean(row["planning_p90"]["input_tokens"] for row in rows), 2),
                "estimated_output_tokens_mean": round(mean(row["expected_mean"]["output_tokens"] for row in rows), 2),
                "estimated_output_tokens_p90": round(mean(row["planning_p90"]["output_tokens"] for row in rows), 2),
                "estimated_thinking_tokens_mean": round(mean(row["expected_mean"]["thinking_tokens"] for row in rows), 2),
                "estimated_thinking_tokens_p90": round(mean(row["planning_p90"]["thinking_tokens"] for row in rows), 2),
                "estimated_cost_mean": mean_totals["official_cost_usd"],
                "estimated_cost_p90": p90_totals["official_cost_usd"],
                "calibration_source_used": "response_schema_actual_with_pilot300_backoff",
                "thin_bucket_backoff_count": backoff_count,
                "thin_bucket_backoff_status": "used" if backoff_count else "not_used",
            }
        )
    return summaries


def top_cost_buckets(bucket_summaries: list[dict[str, Any]], limit: int = 8) -> list[dict[str, Any]]:
    return sorted(
        (
            {
                "bucket_key": row["bucket_key"],
                "manifest_item_count": row["manifest_item_count"],
                "estimated_cost_p90": row["estimated_cost_p90"],
            }
            for row in bucket_summaries
        ),
        key=lambda row: Decimal(str(row["estimated_cost_p90"])),
        reverse=True,
    )[:limit]


def build_joint_corpus_counts(inventory_payload: dict[str, Any]) -> dict[str, int]:
    counts: Counter[str] = Counter()
    for item in inventory_payload.get("items") or []:
        counts[bucket_key_string(bucket_key(item))] += 1
    return dict(sorted(counts.items()))


def cost_stats_from_pilot_estimates(cost_estimate: dict[str, Any]) -> dict[tuple[str, ...], dict[str, Any]]:
    rows = cost_estimate.get("items") or []
    buckets: dict[tuple[str, ...], list[dict[str, Decimal]]] = defaultdict(list)
    for row in rows:
        layer, length, chunk = str(row["text_layer"]), str(row["length_bucket"]), str(row["chunk_type"])
        value = {
            "mean": Decimal(str(row["expected_mean"]["official_cost_usd"])),
            "p90": Decimal(str(row["planning_p90"]["official_cost_usd"])),
        }
        for key in backoff_keys((layer, length, chunk)):
            buckets[key].append(value)
    stats: dict[tuple[str, ...], dict[str, Any]] = {}
    for key, values in buckets.items():
        stats[key] = {
            "n": len(values),
            "mean": sum(v["mean"] for v in values) / Decimal(len(values)),
            "p90": sum(v["p90"] for v in values) / Decimal(len(values)),
        }
    return stats


def choose_cost_stat(bucket: tuple[str, str, str], stats: dict[tuple[str, ...], dict[str, Any]]) -> tuple[dict[str, Any], tuple[str, ...]]:
    for key in backoff_keys(bucket):
        if key in stats:
            return stats[key], key
    return {"n": 0, "mean": Decimal("0"), "p90": Decimal("0")}, ("missing",)


def corpus_extrapolation(cost_estimate: dict[str, Any], inventory_payload: dict[str, Any]) -> dict[str, Any]:
    joint_counts = build_joint_corpus_counts(inventory_payload)
    if not joint_counts:
        return marginal_corpus_extrapolation(cost_estimate)
    stats = cost_stats_from_pilot_estimates(cost_estimate)
    bucket_weights = []
    total_mean = Decimal("0")
    total_p90 = Decimal("0")
    for key_string, count in joint_counts.items():
        layer, length, chunk = key_string.split("×")
        stat, stat_key = choose_cost_stat((layer, length, chunk), stats)
        mean_cost = Decimal(str(stat["mean"])) * Decimal(count)
        p90_cost = Decimal(str(stat["p90"])) * Decimal(count)
        total_mean += mean_cost
        total_p90 += p90_cost
        bucket_weights.append(
            {
                "bucket_key": key_string,
                "corpus_count": count,
                "corpus_weight": decimal_rate(count, CORPUS_SEGMENT_COUNT),
                "pilot_cost_stat_bucket_used": bucket_key_string(stat_key),
                "pilot_cost_stat_n": stat["n"],
                "projected_cost_mean": quantize_usd(mean_cost),
                "projected_cost_p90": quantize_usd(p90_cost),
            }
        )
    return {
        "schema_version": "pali_pilot_1000_corpus_extrapolation_v1",
        "inventory_source_commit": PINNED_INVENTORY_COMMIT,
        "full_corpus_segment_count": sum(joint_counts.values()),
        "expected_full_corpus_segment_count": CORPUS_SEGMENT_COUNT,
        "corpus_weighting_method": "joint_inventory_counts",
        "bucket_weights_used": bucket_weights,
        "mean_projected_full_corpus_cost": quantize_usd(total_mean),
        "p90_projected_full_corpus_cost": quantize_usd(total_p90),
        "note": "pilot distribution != corpus distribution; this projection uses corpus weights",
        "warning": "Do not multiply pilot average cost by 203,594. The pilot distribution is intentionally harder than the corpus distribution.",
    }


def marginal_corpus_extrapolation(cost_estimate: dict[str, Any]) -> dict[str, Any]:
    stats = cost_stats_from_pilot_estimates(cost_estimate)
    bucket_weights = []
    total_mean = Decimal("0")
    total_p90 = Decimal("0")
    for layer, layer_weight in CORPUS_LAYER_PROPORTIONS.items():
        for length, length_weight in CORPUS_LENGTH_PROPORTIONS.items():
            for chunk, chunk_weight in CORPUS_CHUNK_PROPORTIONS.items():
                raw_count = Decimal(CORPUS_SEGMENT_COUNT) * layer_weight * length_weight * chunk_weight
                count = int(raw_count.to_integral_value(rounding=ROUND_HALF_UP))
                stat, stat_key = choose_cost_stat((layer, length, chunk), stats)
                mean_cost = Decimal(str(stat["mean"])) * Decimal(count)
                p90_cost = Decimal(str(stat["p90"])) * Decimal(count)
                total_mean += mean_cost
                total_p90 += p90_cost
                bucket_key_value = bucket_key_string((layer, length, chunk))
                bucket_weights.append(
                    {
                        "bucket_key": bucket_key_value,
                        "corpus_count": count,
                        "corpus_weight": decimal_rate(count, CORPUS_SEGMENT_COUNT),
                        "pilot_cost_stat_bucket_used": bucket_key_string(stat_key),
                        "pilot_cost_stat_n": stat["n"],
                        "projected_cost_mean": quantize_usd(mean_cost),
                        "projected_cost_p90": quantize_usd(p90_cost),
                    }
                )
    return {
        "schema_version": "pali_pilot_1000_corpus_extrapolation_v1",
        "inventory_source_commit": PINNED_INVENTORY_COMMIT,
        "full_corpus_segment_count": CORPUS_SEGMENT_COUNT,
        "expected_full_corpus_segment_count": CORPUS_SEGMENT_COUNT,
        "corpus_weighting_method": "marginal_independence_approximation",
        "bucket_weights_used": bucket_weights,
        "mean_projected_full_corpus_cost": quantize_usd(total_mean),
        "p90_projected_full_corpus_cost": quantize_usd(total_p90),
        "note": "pilot distribution != corpus distribution; this projection uses corpus weights",
        "warning": "Do not multiply pilot average cost by 203,594. The pilot distribution is intentionally harder than the corpus distribution.",
    }


def render_request_preview_sample(rows: list[dict[str, Any]]) -> str:
    sample = rows[:3]
    lines = [
        "# Pilot 1,000 Request Preview Sample",
        "",
        f"- sample_count: `{len(sample)}`",
        f"- total_preview_requests: `{len(rows)}`",
        "- response_schema: `enabled`",
        "- reader_ko: `absent`",
        "",
    ]
    for row in sample:
        prompt = prompt_for_row(row)
        lines.extend(
            [
                f"## `{row['key']}`",
                "",
                f"- source_path: `{row['metadata'].get('source_path')}`",
                f"- bucket: `{bucket_key_string(bucket_key(row['metadata']))}`",
                f"- prompt_chars: `{len(prompt)}`",
                f"- prompt_has_v2_2_marker: `{NATURAL_KO_V2_2_MARKER in prompt}`",
                "",
            ]
        )
    return "\n".join(lines) + "\n"


def render_cost_estimate_md(cost: dict[str, Any]) -> str:
    lines = [
        "# Pilot 1,000 Cost Estimate",
        "",
        f"- mean cost: `${cost['pilot_1000_total_cost_mean']}`",
        f"- p90 cost: `${cost['pilot_1000_total_cost_p90']}`",
        f"- hard cap: `${cost['hard_cap_usd']}`",
        f"- cap_passed: `{cost['cap_passed']}`",
        f"- submit_ready: `{cost['submit_ready']}`",
        f"- calibration rows: `{cost['calibration_row_count']}`",
        "",
        "## Top Cost Buckets",
        "",
    ]
    for row in cost["top_cost_buckets"]:
        lines.append(f"- `{row['bucket_key']}`: count {row['manifest_item_count']}, p90 ${row['estimated_cost_p90']}")
    lines.extend(["", "## Thin Bucket Backoff", ""])
    for row in cost["bucket_estimates"]:
        if row["thin_bucket_backoff_count"]:
            lines.append(f"- `{row['bucket_key']}`: {row['thin_bucket_backoff_count']} requests used backoff")
    return "\n".join(lines) + "\n"


def render_corpus_extrapolation_md(extrapolation: dict[str, Any]) -> str:
    return "\n".join(
        [
            "# Pilot 1,000 Corpus Extrapolation",
            "",
            f"- full_corpus_segment_count: `{extrapolation['full_corpus_segment_count']}`",
            f"- corpus_weighting_method: `{extrapolation['corpus_weighting_method']}`",
            f"- mean projected full-corpus cost: `${extrapolation['mean_projected_full_corpus_cost']}`",
            f"- p90 projected full-corpus cost: `${extrapolation['p90_projected_full_corpus_cost']}`",
            "",
            "Do not multiply pilot average cost by 203,594. The pilot distribution is intentionally harder than the corpus distribution.",
            "",
            "This projection uses true joint inventory bucket counts from the pinned 49bc869 inventory cache.",
        ]
    ) + "\n"


def render_submit_plan(cost: dict[str, Any], manifest_path: Path, out_dir: Path) -> str:
    return "\n".join(
        [
            "# Pilot 1,000 Submit Plan",
            "",
            "This is documentation only. Step 6 does not implement or execute live submit.",
            "",
            f"- planned_provider_requests: `1000`",
            "- prompt_variant: `natural_ko_v2_2`",
            "- response_schema: `enabled`",
            "- salvage_cascade_fallback: `enabled`",
            "- reader_ko: `false`",
            f"- manifest path: `{manifest_path}`",
            f"- output path: `{out_dir}`",
            f"- estimated_cost_usd_mean: `${cost['pilot_1000_total_cost_mean']}`",
            f"- estimated_cost_usd_p90: `${cost['pilot_1000_total_cost_p90']}`",
            f"- hard_cap_usd: `${cost['hard_cap_usd']}`",
            f"- cap_passed: `{cost['cap_passed']}`",
            f"- submit_ready: `{cost['submit_ready']}`",
            "",
            "Required precondition: `cap_passed == true` and explicit operator approval before any later live submit.",
            "",
            "Silver canary is off by default. A later task may append up to 20 advisory-only canary items tagged `advisory_only_not_gold_accuracy`, excluded from gold scoring.",
            "",
            "Proposed later live command, do not execute in Step 6:",
            "",
            "```bash",
            "./venv/bin/python -m backend.pali.scripts.submit_pilot_1000_batch \\",
            "  --request-preview data/reports/pali/pilot_1000_batch/pilot_1000_request_preview.jsonl \\",
            "  --hard-cap-usd 50",
            "```",
        ]
    ) + "\n"


def render_qa_retry_plan() -> str:
    return """# Pilot 1,000 QA / Retry Plan

Use the 3-state gate model after the later live run:

- `PASS`
- `FAIL_RETRY_ONLY`
- `FAIL_BLOCKING`

## Blocking

Route to human/prompt review:

- provider_error
- schema_invalid
- empty_translation
- unsupported_insertion
- known_content_omission
- negation_scope_risk
- hard_glossary_violation

Hard glossary violations must use co-occurrence gating: a term's disallowed Korean rendering fires only when the relevant Pali term appears in source/terms.

## Retry Only

Route to automatic retry queue:

- bracket_violation
- isolated salvageable parse defect, if implemented later

## Non-Gating Warnings

Track but do not block:

- advisory_glossary_warning
- general_content_omission_pending_scholar_review

## Manual Review Sampling

1. Uncertainty-priority sample: non-empty uncertainties, quality_flags, objective gate warnings.
2. Scholar fidelity sample: stratified by text_layer, with Abhidhamma, Vinaya, long commentary, long subcommentary, and formulaic/matrix passages.
3. Readability sample: long natural_ko, high literal/natural similarity, many Pali parentheses, lemma-gloss-heavy cases, and operator-readable Korean samples.

## Roadmap Only

- context-window injection
- second-LLM cross-check
- reader-flag loop
- silver canary live advisory sample
"""


def render_validation_report_md(validation: dict[str, Any]) -> str:
    lines = [
        "# Pilot 1,000 Validation Report",
        "",
        f"- dry_run_status: `{validation['dry_run_status']}`",
        f"- submit_ready: `{validation['submit_ready']}`",
        f"- errors: `{len(validation['errors'])}`",
        f"- warnings: `{len(validation['warnings'])}`",
    ]
    if validation["errors"]:
        lines.extend(["", "## Errors", ""])
        lines.extend(f"- {error}" for error in validation["errors"][:50])
    if validation["warnings"]:
        lines.extend(["", "## Warnings", ""])
        lines.extend(f"- {warning}" for warning in validation["warnings"][:50])
    return "\n".join(lines) + "\n"


def render_no_api_executed() -> str:
    return """# No API Executed

Step 6 dry-run made no Gemini/API/Batch/provider/network calls.

- api_llm_calls: 0
- network_calls: 0
- batch_submissions: 0
- live_submit_started: false
"""


def build_validation_report(preview_validation: dict[str, Any], cost: dict[str, Any]) -> dict[str, Any]:
    errors = list(preview_validation["errors"])
    warnings = list(preview_validation["warnings"])
    if not cost["cap_passed"]:
        errors.append("BLOCKED_ESTIMATED_P90_COST_OVER_CAP")
    return {
        "schema_version": "pali_pilot_1000_validation_report_v1",
        "selected_count": PLANNED_REQUESTS,
        "planned_requests": preview_validation["request_count"],
        "duplicate_count": preview_validation["duplicate_count"],
        "manifest_key_set_equals_preview_key_set": preview_validation["manifest_key_set_equals_preview_key_set"],
        "manifest_order_equals_preview_order": preview_validation["manifest_order_equals_preview_order"],
        "generation_config_identical": preview_validation["generation_config_identical"],
        "response_schema_default": True,
        "salvage_cascade_fallback": True,
        "estimated_cost_usd_p90": cost["pilot_1000_total_cost_p90"],
        "hard_cap_usd": cost["hard_cap_usd"],
        "cap_passed": cost["cap_passed"],
        "submit_ready": not errors,
        "dry_run_status": "PASS" if not errors else "BLOCKED",
        "errors": sorted(set(errors)),
        "warnings": sorted(set(warnings)),
    }


def build_dry_run_manifest(
    *,
    manifest_path: Path,
    cost: dict[str, Any],
    extrapolation: dict[str, Any],
    validation: dict[str, Any],
) -> dict[str, Any]:
    return {
        "step": "6-pilot-1000-dry-run",
        "api_llm_calls": 0,
        "network_calls": 0,
        "batch_submissions": 0,
        "live_submit_started": False,
        "selection_source": str(manifest_path),
        "selection_reused_not_reselected": True,
        "inventory_source_commit": PINNED_INVENTORY_COMMIT,
        "prompt_variant": "natural_ko_v2_2",
        "response_schema": True,
        "response_schema_dialect": "gemini",
        "salvage_cascade_fallback": True,
        "reader_ko_added": False,
        "step5_selection_modified": False,
        "prompt_mutation": False,
        "glossary_mutation": False,
        "gold_set_mutation": False,
        "source_xml_mutation": False,
        "planned_requests": PLANNED_REQUESTS,
        "estimated_cost_usd_mean": cost["pilot_1000_total_cost_mean"],
        "estimated_cost_usd_p90": cost["pilot_1000_total_cost_p90"],
        "hard_cap_usd": cost["hard_cap_usd"],
        "cap_passed": cost["cap_passed"],
        "submit_ready": validation["submit_ready"],
        "top_cost_buckets": cost["top_cost_buckets"],
        "corpus_extrapolation_usd_mean": extrapolation["mean_projected_full_corpus_cost"],
        "corpus_extrapolation_usd_p90": extrapolation["p90_projected_full_corpus_cost"],
        "corpus_weighting_method": extrapolation["corpus_weighting_method"],
        "gate_status_model": "3-state",
        "objective_gate_status_values": ["PASS", "FAIL_RETRY_ONLY", "FAIL_BLOCKING"],
    }


def run_pilot_1000_dry_run(
    *,
    manifest_path: Path = DEFAULT_MANIFEST,
    out_dir: Path = DEFAULT_OUT,
    prompt_variant: str = "natural_ko_v2_2",
    response_schema: bool = True,
    dry_run: bool = True,
    hard_cap_usd: Decimal = DEFAULT_HARD_CAP_USD,
    inventory_cache_path: Path = DEFAULT_INVENTORY_CACHE,
    pretty: bool = False,
) -> dict[str, Any]:
    if prompt_variant != "natural_ko_v2_2":
        raise Pilot1000DryRunBlocked("BLOCKED_UNSUPPORTED_PROMPT_VARIANT", f"unsupported prompt variant: {prompt_variant}")
    if not response_schema:
        raise Pilot1000DryRunBlocked("BLOCKED_RESPONSE_SCHEMA_REQUIRED", "response_schema must be enabled")
    if not dry_run:
        raise Pilot1000DryRunBlocked("BLOCKED_DRY_RUN_REQUIRED", "Step 6 supports dry-run only")

    paths = step6_paths(out_dir)
    paths.out_dir.mkdir(parents=True, exist_ok=True)
    manifest = load_selection_manifest(manifest_path)
    inventory = load_inventory_cache(inventory_cache_path)
    enriched_items = enrich_manifest_items(manifest, inventory)
    rows = build_request_preview(enriched_items)
    preview_validation = validate_preview(manifest, enriched_items, rows)
    cost = estimate_costs(rows, hard_cap_usd)
    extrapolation = corpus_extrapolation(cost, inventory)
    validation = build_validation_report(preview_validation, cost)
    dry_run_manifest = build_dry_run_manifest(
        manifest_path=manifest_path,
        cost=cost,
        extrapolation=extrapolation,
        validation=validation,
    )

    write_jsonl(paths.request_preview, rows)
    paths.request_preview_sample_md.write_text(render_request_preview_sample(rows), encoding="utf-8")
    write_json(paths.cost_estimate_json, cost, pretty=pretty)
    paths.cost_estimate_md.write_text(render_cost_estimate_md(cost), encoding="utf-8")
    write_json(paths.corpus_extrapolation_json, extrapolation, pretty=pretty)
    paths.corpus_extrapolation_md.write_text(render_corpus_extrapolation_md(extrapolation), encoding="utf-8")
    paths.submit_plan_md.write_text(render_submit_plan(cost, manifest_path, out_dir), encoding="utf-8")
    paths.qa_retry_plan_md.write_text(render_qa_retry_plan(), encoding="utf-8")
    write_json(paths.validation_report_json, validation, pretty=pretty)
    paths.validation_report_md.write_text(render_validation_report_md(validation), encoding="utf-8")
    write_json(paths.dry_run_manifest_json, dry_run_manifest, pretty=pretty)
    paths.no_api_md.write_text(render_no_api_executed(), encoding="utf-8")
    return {
        "status": validation["dry_run_status"],
        "planned_requests": len(rows),
        "estimated_cost_usd_mean": cost["pilot_1000_total_cost_mean"],
        "estimated_cost_usd_p90": cost["pilot_1000_total_cost_p90"],
        "hard_cap_usd": cost["hard_cap_usd"],
        "cap_passed": cost["cap_passed"],
        "submit_ready": validation["submit_ready"],
        "corpus_extrapolation_usd_mean": extrapolation["mean_projected_full_corpus_cost"],
        "corpus_extrapolation_usd_p90": extrapolation["p90_projected_full_corpus_cost"],
        "corpus_weighting_method": extrapolation["corpus_weighting_method"],
        "errors": validation["errors"],
        "warnings": validation["warnings"],
    }

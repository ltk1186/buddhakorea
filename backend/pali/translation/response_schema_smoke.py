"""Local helpers for Step 4 response_schema A/B smoke planning.

This module prepares and analyzes a narrow response_schema experiment. It does
not mutate production prompts, schema files, translations, glossary, or gold
data. Real provider calls are only made by the CLI submit/poll/fetch modes.
"""

from __future__ import annotations

import copy
import hashlib
import json
import re
import time
from collections import Counter, defaultdict
from dataclasses import dataclass
from decimal import Decimal, ROUND_HALF_UP
from pathlib import Path
from typing import Any

from backend.pali.scripts.submit_gemini_smoke_batch import (
    DEFAULT_MODEL,
    build_inline_request_from_provider_line,
    extract_generate_content_response,
    extract_model_output_text,
    extract_result_key,
    parse_batch_results,
)
from backend.pali.scripts.salvage_pilot_300_batch_parse import (
    apply_successful_parse,
    extract_finish_reason,
    parse_output_cascade,
)
from backend.pali.translation.budget import PriceProfile, TokenEstimate, estimate_request_cost


RUN_ID = "step4_response_schema_smoke"
SCHEMA_VERSION = "pali_step4_response_schema_smoke_v1"
DEFAULT_SEED = "step4_response_schema_smoke_v1"
DEFAULT_HARD_CAP_USD = Decimal("4")
TARGET_SAMPLE_COUNT = 50
KNOWN_FAILURE_TARGET = 34
VULNERABLE_TARGET = TARGET_SAMPLE_COUNT - KNOWN_FAILURE_TARGET
MAX_REQUESTS_WITHOUT_OVERRIDE = 100

SILVER_CANARY_STATUS = "advisory_only_not_gold_accuracy"
SILVER_CANARY_NEEDS_PALI_EXPERT_POLICY = "needs_review_not_fail"
ALLOWED_RESPONSE_SCHEMA_KEYWORDS = {
    "type",
    "format",
    "description",
    "nullable",
    "enum",
    "items",
    "properties",
    "required",
    "minItems",
    "maxItems",
    "propertyOrdering",
}
UNSUPPORTED_RESPONSE_SCHEMA_KEYWORDS = {
    "additionalProperties",
    "$schema",
    "definitions",
    "$defs",
    "patternProperties",
    "dependencies",
    "dependentRequired",
    "allOf",
    "anyOf",
    "oneOf",
    "not",
    "if",
    "then",
    "else",
    "const",
    "pattern",
    "minimum",
    "maximum",
    "exclusiveMinimum",
    "exclusiveMaximum",
    "minLength",
    "maxLength",
}

CITATION_MARKER_RE = re.compile(
    r"\b(?:dī\. ni\.|ma\. ni\.|saṃ\. ni\.|aṅ\. ni\.|a\. ni\.|khu\. pā\.|"
    r"dha\. pa\.|udā\.|itivu\.|jā\.|mahāva\.|cūḷava\.|visuddhi\.|"
    r"aṭṭha\.|ṭī\.|abhidhamma)\b",
    re.IGNORECASE,
)


@dataclass(frozen=True)
class Step4Paths:
    out_dir: Path
    selection_manifest: Path
    response_schema: Path
    arm_a_jsonl: Path
    arm_b_jsonl: Path
    cost_estimate: Path
    submit_plan: Path
    provider_status_arm_a: Path
    provider_status_arm_b: Path
    arm_a_raw_results: Path
    arm_b_raw_results: Path
    arm_a_parsed: Path
    arm_b_parsed: Path
    arm_a_salvage_report: Path
    arm_b_salvage_report: Path
    comparison_report: Path
    comparison_report_md: Path
    recommendation: Path
    run_manifest: Path


def step4_paths(out_dir: Path) -> Step4Paths:
    return Step4Paths(
        out_dir=out_dir,
        selection_manifest=out_dir / "selection_manifest.json",
        response_schema=out_dir / "response_schema_experiment.json",
        arm_a_jsonl=out_dir / "arm_a_batch_input.jsonl",
        arm_b_jsonl=out_dir / "arm_b_batch_input.jsonl",
        cost_estimate=out_dir / "cost_estimate.json",
        submit_plan=out_dir / "submit_plan.md",
        provider_status_arm_a=out_dir / "provider_status_arm_a.json",
        provider_status_arm_b=out_dir / "provider_status_arm_b.json",
        arm_a_raw_results=out_dir / "arm_a_raw_results.jsonl",
        arm_b_raw_results=out_dir / "arm_b_raw_results.jsonl",
        arm_a_parsed=out_dir / "arm_a_parsed.json",
        arm_b_parsed=out_dir / "arm_b_parsed.json",
        arm_a_salvage_report=out_dir / "arm_a_salvage_report.json",
        arm_b_salvage_report=out_dir / "arm_b_salvage_report.json",
        comparison_report=out_dir / "comparison_report.json",
        comparison_report_md=out_dir / "comparison_report.md",
        recommendation=out_dir / "recommendation.md",
        run_manifest=out_dir / "run_manifest.json",
    )


def read_json(path: Path) -> dict[str, Any]:
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
    text = "\n".join(json.dumps(row, ensure_ascii=False) for row in rows)
    path.write_text((text + "\n") if text else "", encoding="utf-8")


def stable_json_dumps(payload: Any) -> str:
    return json.dumps(payload, ensure_ascii=False, sort_keys=True, separators=(",", ":"))


def sha256_text(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def file_sha256(path: Path) -> str | None:
    if not path.exists():
        return None
    return hashlib.sha256(path.read_bytes()).hexdigest()


def stable_sort_key(seed: str, stable_segment_key: str, salt: str = "") -> str:
    return hashlib.sha256(f"{seed}|{stable_segment_key}|{salt}".encode("utf-8")).hexdigest()


def quantize_usd(value: Decimal) -> str:
    return str(value.quantize(Decimal("0.000001"), rounding=ROUND_HALF_UP))


def build_response_schema_experiment() -> dict[str, Any]:
    """Return an experiment-local schema copy matching current output fields."""
    return {
        "schema_version": "pali_step4_response_schema_experiment_v1",
        "source": "experiment_copy_of_current_korean_advanced_translation_output_fields",
        "production_schema_file_mutation": False,
        "response_schema": {
            "type": "object",
            "propertyOrdering": [
                "literal_ko",
                "natural_ko",
                "terms",
                "grammar_notes",
                "doctrinal_notes",
                "uncertainties",
                "quality_flags",
            ],
            "required": [
                "literal_ko",
                "natural_ko",
                "terms",
                "grammar_notes",
                "doctrinal_notes",
                "uncertainties",
                "quality_flags",
            ],
            "properties": {
                "literal_ko": {"type": "string"},
                "natural_ko": {"type": "string"},
                "terms": {
                    "type": "array",
                    "items": {
                        "type": "object",
                        "propertyOrdering": ["pali", "ko", "gloss", "note"],
                        "required": ["pali", "ko", "gloss", "note"],
                        "properties": {
                            "pali": {"type": "string"},
                            "ko": {"type": "string"},
                            "gloss": {"type": "string"},
                            "note": {"type": "string"},
                        },
                    },
                },
                "grammar_notes": {"type": "array", "items": {"type": "string"}},
                "doctrinal_notes": {"type": "array", "items": {"type": "string"}},
                "uncertainties": {"type": "array", "items": {"type": "string"}},
                "quality_flags": {"type": "array", "items": {"type": "string"}},
            },
        },
    }


def validate_response_schema_dialect(schema: dict[str, Any]) -> dict[str, Any]:
    """Validate the Gemini Batch response_schema dialect used by this experiment."""
    unsupported: list[dict[str, str]] = []
    disallowed: list[dict[str, str]] = []
    inspect_schema_keywords(schema, "$.response_schema", unsupported=unsupported, disallowed=disallowed)
    return {
        "valid": not unsupported and not disallowed,
        "unsupported_keywords": unsupported,
        "disallowed_keywords": disallowed,
        "allowed_keywords": sorted(ALLOWED_RESPONSE_SCHEMA_KEYWORDS),
    }


def inspect_schema_keywords(
    value: Any,
    path: str,
    *,
    unsupported: list[dict[str, str]],
    disallowed: list[dict[str, str]],
) -> None:
    if isinstance(value, dict):
        for key, nested in value.items():
            key_path = f"{path}.{key}"
            if key in UNSUPPORTED_RESPONSE_SCHEMA_KEYWORDS:
                unsupported.append({"keyword": key, "path": key_path})
            if looks_like_schema_keyword_context(path) and key not in ALLOWED_RESPONSE_SCHEMA_KEYWORDS and key not in property_name_exceptions(path):
                disallowed.append({"keyword": key, "path": key_path})
            inspect_schema_keywords(nested, key_path, unsupported=unsupported, disallowed=disallowed)
    elif isinstance(value, list):
        for index, nested in enumerate(value):
            inspect_schema_keywords(nested, f"{path}[{index}]", unsupported=unsupported, disallowed=disallowed)


def looks_like_schema_keyword_context(path: str) -> bool:
    return (
        path == "$.response_schema"
        or path.endswith(".items")
        or path.endswith(".value")
        or ".items." in path
        or ".properties." not in path
    )


def property_name_exceptions(path: str) -> set[str]:
    if path.endswith(".properties"):
        return {
            "literal_ko",
            "natural_ko",
            "terms",
            "grammar_notes",
            "doctrinal_notes",
            "uncertainties",
            "quality_flags",
            "pali",
            "ko",
            "gloss",
            "note",
        }
    return set()


def select_step4_items(
    *,
    parsed_salvaged: dict[str, Any],
    cost_estimate: dict[str, Any],
    jsonl_manifest: dict[str, Any],
    seed: str = DEFAULT_SEED,
    target_count: int = TARGET_SAMPLE_COUNT,
) -> dict[str, Any]:
    parsed_items = parsed_salvaged.get("items") or []
    cost_by_key = {item.get("stable_segment_key"): item for item in cost_estimate.get("items") or []}
    manifest_by_key = {item.get("stable_segment_key"): item for item in jsonl_manifest.get("items") or []}

    known_failures = [
        item for item in parsed_items if item.get("parse_method") in {"raw_decode", "stack_reclose"}
    ]
    known_failure_keys = {item.get("stable_segment_key") for item in known_failures}
    missing_known_failure_keys: list[str] = []
    readiness_errors: list[str] = []
    if len(known_failures) != KNOWN_FAILURE_TARGET:
        readiness_errors.append(
            f"expected {KNOWN_FAILURE_TARGET} known strict parse failures, found {len(known_failures)}"
        )

    failure_lengths = [len(str(item.get("original_text") or "")) for item in known_failures]
    median_failure_length = sorted(failure_lengths)[len(failure_lengths) // 2] if failure_lengths else 0

    selected: list[dict[str, Any]] = []
    for item in sorted(known_failures, key=lambda row: stable_sort_key(seed, row.get("stable_segment_key", ""), "known")):
        selected.append(selection_record(
            item=item,
            cost_item=cost_by_key.get(item.get("stable_segment_key"), {}),
            manifest_item=manifest_by_key.get(item.get("stable_segment_key"), {}),
            reason=f"known_strict_parse_failure_{item.get('parse_method')}",
            seed=seed,
        ))

    strict_passed = [
        item
        for item in parsed_items
        if item.get("stable_segment_key") not in known_failure_keys
        and item.get("parse_method") == "strict_json"
        and item.get("schema_valid") is True
    ]
    scored = [
        vulnerable_score_record(
            item=item,
            cost_item=cost_by_key.get(item.get("stable_segment_key"), {}),
            manifest_item=manifest_by_key.get(item.get("stable_segment_key"), {}),
            median_failure_length=median_failure_length,
            seed=seed,
        )
        for item in strict_passed
    ]
    scored.sort(key=lambda row: (-row["vulnerability_score"], row["sort_key"]))
    vulnerable_count = max(0, target_count - len(selected))
    selected.extend(
        selection_record(
            item=row["item"],
            cost_item=row["cost_item"],
            manifest_item=row["manifest_item"],
            reason="vulnerable_strict_passed_bucket",
            seed=seed,
            vulnerability_score=row["vulnerability_score"],
            vulnerability_tags=row["vulnerability_tags"],
        )
        for row in scored[:vulnerable_count]
    )
    if len(selected) != target_count:
        readiness_errors.append(f"expected {target_count} selected items, found {len(selected)}")

    reason_counts = Counter(item["selection_reason"] for item in selected)
    distribution = {
        "by_selection_reason": dict(sorted(reason_counts.items())),
        "by_text_layer": count_selected_field(selected, "text_layer"),
        "by_chunk_type": count_selected_field(selected, "chunk_type"),
        "by_length_bucket": count_selected_field(selected, "length_bucket"),
    }
    return {
        "schema_version": "pali_step4_response_schema_selection_manifest_v1",
        "run_id": RUN_ID,
        "hash_seed": seed,
        "selection_policy": "include_all_34_known_strict_parse_failures_plus_16_deterministic_vulnerable_strict_passed",
        "target_count": target_count,
        "selected_count": len(selected),
        "known_strict_parse_failure_count": len(known_failures),
        "known_strict_parse_failure_target": KNOWN_FAILURE_TARGET,
        "vulnerable_strict_passed_count": sum(
            1 for item in selected if item["selection_reason"] == "vulnerable_strict_passed_bucket"
        ),
        "missing_known_failure_keys": missing_known_failure_keys,
        "selection_readiness": "PASS" if not readiness_errors else "BLOCKED_SELECTION_INCOMPLETE",
        "readiness_errors": readiness_errors,
        "distribution": distribution,
        "items": selected,
    }


def selection_record(
    *,
    item: dict[str, Any],
    cost_item: dict[str, Any],
    manifest_item: dict[str, Any],
    reason: str,
    seed: str,
    vulnerability_score: int | None = None,
    vulnerability_tags: list[str] | None = None,
) -> dict[str, Any]:
    key = str(item.get("stable_segment_key") or "")
    return {
        "stable_segment_key": key,
        "selection_reason": reason,
        "source_path": item.get("source_path") or cost_item.get("source_path") or manifest_item.get("source_path"),
        "source_text_hash": item.get("source_text_hash") or cost_item.get("source_text_hash") or manifest_item.get("source_text_hash"),
        "text_layer": item.get("text_layer") or cost_item.get("text_layer") or manifest_item.get("text_layer"),
        "chunk_type": item.get("chunk_type") or cost_item.get("chunk_type") or manifest_item.get("chunk_type"),
        "length_bucket": item.get("length_bucket") or cost_item.get("length_bucket") or manifest_item.get("length_bucket"),
        "previous_parse_status": item.get("status"),
        "previous_salvage_tier": item.get("parse_method") or "unknown",
        "previous_schema_valid": bool(item.get("schema_valid")),
        "previous_error_message": item.get("error_message", ""),
        "selection_bucket": cost_item.get("selection_bucket") or manifest_item.get("selection_bucket"),
        "selection_group": cost_item.get("selection_group") or manifest_item.get("selection_group"),
        "source_char_count": len(str(item.get("original_text") or "")),
        "terms_count": len(item.get("terms") or []),
        "notes_count": sum(len(item.get(field) or []) for field in ("grammar_notes", "doctrinal_notes", "uncertainties", "quality_flags")),
        "vulnerability_score": vulnerability_score,
        "vulnerability_tags": vulnerability_tags or [],
        "hash_seed": seed,
        "stable_sort_key": stable_sort_key(seed, key, reason),
        "estimated_p90": cost_item.get("planning_p90") or {},
        "estimated_mean": cost_item.get("expected_mean") or {},
    }


def vulnerable_score_record(
    *,
    item: dict[str, Any],
    cost_item: dict[str, Any],
    manifest_item: dict[str, Any],
    median_failure_length: int,
    seed: str,
) -> dict[str, Any]:
    tags: list[str] = []
    score = 0
    text_layer = str(item.get("text_layer") or cost_item.get("text_layer") or "")
    length_bucket = str(item.get("length_bucket") or cost_item.get("length_bucket") or "")
    chunk_type = str(item.get("chunk_type") or cost_item.get("chunk_type") or "")
    selection_bucket = str(cost_item.get("selection_bucket") or manifest_item.get("selection_bucket") or "")
    source_text = str(item.get("original_text") or "")
    if selection_bucket in {"tika_long", "atthakatha_long"}:
        score += 45
        tags.append(selection_bucket)
    if text_layer in {"tika", "atthakatha"} and length_bucket == "long":
        score += 35
        tags.append(f"{text_layer}_long")
    if "verse" in chunk_type:
        score += 25
        tags.append("verse")
    if CITATION_MARKER_RE.search(source_text):
        score += 20
        tags.append("citation_heavy")
    note_count = sum(len(item.get(field) or []) for field in ("grammar_notes", "doctrinal_notes", "uncertainties", "quality_flags"))
    term_count = len(item.get("terms") or [])
    if term_count + note_count >= 4:
        score += 20
        tags.append("high_terms_notes_likelihood")
    length_delta = abs(len(source_text) - median_failure_length)
    if median_failure_length:
        length_score = max(0, 25 - min(25, length_delta // 80))
        if length_score:
            score += int(length_score)
            tags.append("similar_length_to_known_failures")
    if length_bucket == "long":
        score += 10
        tags.append("long")
    return {
        "item": item,
        "cost_item": cost_item,
        "manifest_item": manifest_item,
        "vulnerability_score": score,
        "vulnerability_tags": sorted(set(tags)),
        "sort_key": stable_sort_key(seed, str(item.get("stable_segment_key") or ""), "vulnerable"),
    }


def count_selected_field(items: list[dict[str, Any]], field: str) -> dict[str, int]:
    return dict(sorted(Counter(str(item.get(field) or "unknown") for item in items).items()))


def build_arm_jsonl(
    *,
    selection_manifest: dict[str, Any],
    provider_lines: list[dict[str, Any]],
    response_schema_payload: dict[str, Any],
) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    dialect = validate_response_schema_dialect(response_schema_payload["response_schema"])
    if not dialect["valid"]:
        raise RuntimeError(f"BLOCKED_UNSUPPORTED_RESPONSE_SCHEMA_KEYWORD: {dialect}")
    provider_by_key = {line.get("key"): line for line in provider_lines}
    arm_a: list[dict[str, Any]] = []
    arm_b: list[dict[str, Any]] = []
    schema = response_schema_payload["response_schema"]
    for item in selection_manifest.get("items") or []:
        key = item["stable_segment_key"]
        if key not in provider_by_key:
            raise RuntimeError(f"selected key missing from unsubmitted JSONL: {key}")
        line_a = copy.deepcopy(provider_by_key[key])
        line_b = copy.deepcopy(provider_by_key[key])
        generation_config = line_b.setdefault("request", {}).setdefault("generation_config", {})
        generation_config["response_schema"] = schema
        arm_a.append(line_a)
        arm_b.append(line_b)
    return arm_a, arm_b


def estimate_step4_cost(
    *,
    selection_manifest: dict[str, Any],
    hard_cap_usd: Decimal = DEFAULT_HARD_CAP_USD,
) -> dict[str, Any]:
    arm_totals = {"expected_mean": Counter(), "planning_p90": Counter()}
    for item in selection_manifest.get("items") or []:
        for bucket in ("expected_mean", "planning_p90"):
            estimate = item.get("estimated_p90" if bucket == "planning_p90" else "estimated_mean") or {}
            arm_totals[bucket]["input_tokens"] += int(estimate.get("input_tokens") or 0)
            arm_totals[bucket]["output_tokens"] += int(estimate.get("output_tokens") or 0)
            arm_totals[bucket]["thinking_tokens"] += int(estimate.get("thinking_tokens") or 0)
            arm_totals[bucket]["official_cost_usd_micros"] += int(
                (Decimal(str(estimate.get("official_cost_usd") or "0")) * Decimal("1000000")).to_integral_value()
            )
    expected_arm = totals_from_counter(arm_totals["expected_mean"])
    p90_arm = totals_from_counter(arm_totals["planning_p90"])
    expected_both = double_totals(expected_arm)
    p90_both = double_totals(p90_arm)
    cost = Decimal(p90_both["official_cost_usd"])
    return {
        "schema_version": "pali_step4_response_schema_cost_estimate_v1",
        "run_id": RUN_ID,
        "method": "sum selected segment Step 2 planning_p90 estimates for Arm A and Arm B; no arbitrary multiplier",
        "hard_cap_usd": str(hard_cap_usd),
        "request_count_per_arm": selection_manifest.get("selected_count", 0),
        "total_request_count": int(selection_manifest.get("selected_count", 0)) * 2,
        "arm_a": {"expected_mean": expected_arm, "planning_p90": p90_arm},
        "arm_b": {"expected_mean": expected_arm, "planning_p90": p90_arm, "response_schema_overhead_multiplier": "none_applied"},
        "combined": {"expected_mean": expected_both, "planning_p90": p90_both},
        "cost_estimate_usd": p90_both["official_cost_usd"],
        "cap_passed_before_submit": cost <= hard_cap_usd,
        "blocking_reasons": [] if cost <= hard_cap_usd else ["BLOCKED_OVER_HARD_CAP"],
    }


def totals_from_counter(counter: Counter[str]) -> dict[str, Any]:
    return {
        "input_tokens": int(counter["input_tokens"]),
        "output_tokens": int(counter["output_tokens"]),
        "thinking_tokens": int(counter["thinking_tokens"]),
        "official_cost_usd": quantize_usd(Decimal(counter["official_cost_usd_micros"]) / Decimal("1000000")),
    }


def double_totals(totals: dict[str, Any]) -> dict[str, Any]:
    return {
        "input_tokens": int(totals["input_tokens"]) * 2,
        "output_tokens": int(totals["output_tokens"]) * 2,
        "thinking_tokens": int(totals["thinking_tokens"]) * 2,
        "official_cost_usd": quantize_usd(Decimal(str(totals["official_cost_usd"])) * 2),
    }


def parse_arm_raw_results(
    *,
    raw_lines: list[dict[str, Any]],
    provider_lines: list[dict[str, Any]],
    selection_manifest: dict[str, Any],
    price_profile: PriceProfile,
    arm: str,
) -> dict[str, Any]:
    manifest = {
        "items": [
            {
                "stable_segment_key": item["stable_segment_key"],
                "source_text_hash": item.get("source_text_hash"),
                "text_layer": item.get("text_layer"),
                "chunk_type": item.get("chunk_type"),
                "length_bucket": item.get("length_bucket"),
                "source_path": item.get("source_path"),
                "estimated_cost_usd": item.get("estimated_p90", {}).get("official_cost_usd"),
            }
            for item in selection_manifest.get("items") or []
        ]
    }
    parsed = parse_batch_results(
        raw_lines=raw_lines,
        provider_lines=provider_lines,
        manifest=manifest,
        price_profile=price_profile,
    )
    raw_by_key = {extract_result_key(line): line for line in raw_lines if extract_result_key(line)}
    for item in parsed.get("items") or []:
        raw_line = raw_by_key.get(item.get("stable_segment_key")) or {}
        response = extract_generate_content_response(raw_line)
        output_text = extract_model_output_text(response)
        finish_reason = extract_finish_reason(response)
        attempt = parse_output_cascade(output_text or "", finish_reason=finish_reason)
        item["arm"] = arm
        item["parse_method"] = attempt.method
        item["recovered_via"] = "none" if attempt.method in {"strict_json", "failed"} else attempt.method
        item["parser_flags"] = attempt.flags
        item["salvage_applied"] = attempt.method in {"raw_decode", "stack_reclose"}
        item["completeness_gate_passed"] = attempt.completeness_gate_passed
        if attempt.ok and attempt.obj is not None:
            apply_successful_parse(item, attempt.obj)
        if not output_text and item.get("status") == "missing_result":
            item["parse_method"] = "failed"
    return {
        "schema_version": "pali_step4_response_schema_arm_parsed_v1",
        "arm": arm,
        "items": parsed.get("items") or [],
    }


def build_arm_salvage_report(parsed: dict[str, Any]) -> dict[str, Any]:
    items = parsed.get("items") or []
    method_counts = Counter(str(item.get("parse_method") or "unknown") for item in items)
    return {
        "schema_version": "pali_step4_response_schema_arm_salvage_report_v1",
        "arm": parsed.get("arm"),
        "total": len(items),
        "strict_json": method_counts.get("strict_json", 0),
        "raw_decode": method_counts.get("raw_decode", 0),
        "stack_reclose": method_counts.get("stack_reclose", 0),
        "failed": method_counts.get("failed", 0),
        "salvage_needed": method_counts.get("raw_decode", 0) + method_counts.get("stack_reclose", 0),
        "salvage_tier_counts": dict(sorted(method_counts.items())),
    }


def arm_metrics(parsed: dict[str, Any]) -> dict[str, Any]:
    items = parsed.get("items") or []
    total = len(items)
    method_counts = Counter(str(item.get("parse_method") or "unknown") for item in items)
    schema_valid = sum(1 for item in items if item.get("schema_valid") is True)
    required_present = sum(1 for item in items if required_fields_present(item))
    type_valid = sum(1 for item in items if required_types_valid(item))
    empty_translation_count = sum(1 for item in items if has_empty_translation(item))
    provider_error = sum(1 for item in items if item.get("status") == "failed")
    envelope_error = sum(1 for item in items if item.get("parse_method") in {"raw_decode", "stack_reclose", "failed"})
    truncation = sum(
        1
        for item in items
        if "finish_reason_max_tokens" in (item.get("parser_flags") or [])
        or "MAX_TOKENS" in str(item.get("error_message") or "")
    )
    usage = {
        "input_tokens": sum(int(item.get("prompt_token_count") or 0) for item in items),
        "output_tokens": sum(int(item.get("candidates_token_count") or 0) for item in items),
        "thinking_tokens": sum(int(item.get("thoughts_token_count") or 0) for item in items),
    }
    usage["total_tokens"] = usage["input_tokens"] + usage["output_tokens"] + usage["thinking_tokens"]
    actual_cost = sum((Decimal(str(item.get("actual_cost_usd") or "0")) for item in items), Decimal("0"))
    return {
        "total": total,
        "strict_parse_rate": rate(method_counts.get("strict_json", 0), total),
        "salvage_needed_rate": rate(method_counts.get("raw_decode", 0) + method_counts.get("stack_reclose", 0), total),
        "salvage_tier_counts": dict(sorted(method_counts.items())),
        "schema_valid_rate": rate(schema_valid, total),
        "required_field_presence_rate": rate(required_present, total),
        "type_valid_rate": rate(type_valid, total),
        "empty_translation_rate": rate(empty_translation_count, total),
        "truncation_rate": rate(truncation, total),
        "provider_error_rate": rate(provider_error, total),
        "batch_envelope_error_rate": rate(envelope_error, total),
        "cost_actual_usd": quantize_usd(actual_cost),
        **usage,
        "latency_seconds_or_batch_duration": None,
    }


def compare_arms(arm_a: dict[str, Any], arm_b: dict[str, Any]) -> dict[str, Any]:
    a_items = {item.get("stable_segment_key"): item for item in arm_a.get("items") or []}
    b_items = {item.get("stable_segment_key"): item for item in arm_b.get("items") or []}
    pair_checks: list[dict[str, Any]] = []
    suppression_flags: Counter[str] = Counter()
    for key in sorted(set(a_items) & set(b_items)):
        a = a_items[key]
        b = b_items[key]
        if not (a.get("schema_valid") and b.get("schema_valid")):
            continue
        check = content_impact_check(a, b)
        pair_checks.append({"stable_segment_key": key, **check})
        suppression_flags.update(check.get("flags") or [])
    metrics_a = arm_metrics(arm_a)
    metrics_b = arm_metrics(arm_b)
    recommendation = recommendation_from_metrics(metrics_a, metrics_b, suppression_flags)
    return {
        "schema_version": "pali_step4_response_schema_comparison_v1",
        "arm_a_metrics": metrics_a,
        "arm_b_metrics": metrics_b,
        "bucket_metrics": {
            "arm_a": bucket_metrics(arm_a),
            "arm_b": bucket_metrics(arm_b),
        },
        "paired_success_count": len(pair_checks),
        "content_impact_checks": pair_checks,
        "content_suppression_flag_counts": dict(sorted(suppression_flags.items())),
        "recommendation": recommendation,
    }


def content_impact_check(a: dict[str, Any], b: dict[str, Any]) -> dict[str, Any]:
    flags: list[str] = []
    literal_ratio = length_ratio(b.get("literal_ko"), a.get("literal_ko"))
    natural_ratio = length_ratio(b.get("natural_ko"), a.get("natural_ko"))
    if literal_ratio < Decimal("0.60"):
        flags.append("arm_b_literal_much_shorter")
    if natural_ratio < Decimal("0.60"):
        flags.append("arm_b_natural_much_shorter")
    diffs = {
        "terms_count_difference": len(b.get("terms") or []) - len(a.get("terms") or []),
        "grammar_notes_count_difference": len(b.get("grammar_notes") or []) - len(a.get("grammar_notes") or []),
        "doctrinal_notes_count_difference": len(b.get("doctrinal_notes") or []) - len(a.get("doctrinal_notes") or []),
        "uncertainties_count_difference": len(b.get("uncertainties") or []) - len(a.get("uncertainties") or []),
        "quality_flags_count_difference": len(b.get("quality_flags") or []) - len(a.get("quality_flags") or []),
    }
    if diffs["terms_count_difference"] <= -2:
        flags.append("arm_b_terms_dropped")
    optional_fields = ("grammar_notes", "doctrinal_notes", "uncertainties", "quality_flags")
    if any((a.get(field) or []) and not (b.get(field) or []) for field in optional_fields):
        flags.append("arm_b_optional_arrays_emptied")
    if any(not (a.get(field) or []) and (b.get(field) or []) for field in optional_fields):
        flags.append("arm_b_forced_optional_array_filling")
    if not str(b.get("literal_ko") or "").strip() or not str(b.get("natural_ko") or "").strip():
        flags.append("arm_b_empty_translation_field")
    return {
        "literal_ko_length_ratio_b_to_a": str(literal_ratio.quantize(Decimal("0.001"))),
        "natural_ko_length_ratio_b_to_a": str(natural_ratio.quantize(Decimal("0.001"))),
        **diffs,
        "flags": sorted(set(flags)),
    }


def recommendation_from_metrics(
    metrics_a: dict[str, Any],
    metrics_b: dict[str, Any],
    suppression_flags: Counter[str],
    *,
    arm_b_status: str = "parsed",
) -> dict[str, Any]:
    if arm_b_status == "provider_rejected_response_schema":
        return {
            "decision": "keep_current_free_form_json_plus_salvage_cascade",
            "reason": "Arm B response_schema was rejected by the provider batch path.",
        }
    b_better = Decimal(str(metrics_b.get("strict_parse_rate") or "0")) > Decimal(str(metrics_a.get("strict_parse_rate") or "0"))
    b_near_perfect = Decimal(str(metrics_b.get("strict_parse_rate") or "0")) >= Decimal("0.98")
    schema_ok = Decimal(str(metrics_b.get("schema_valid_rate") or "0")) >= Decimal(str(metrics_a.get("schema_valid_rate") or "0"))
    suppression_ok = not suppression_flags
    if b_better and b_near_perfect and schema_ok and suppression_ok:
        return {
            "decision": "consider_response_schema_for_1000_pilot_after_operator_review",
            "reason": "Arm B improved strict parse behavior without detected mechanical content suppression.",
        }
    return {
        "decision": "keep_current_free_form_json_plus_salvage_cascade",
        "reason": "Response schema did not meet all adoption criteria or results are not yet available.",
    }


def bucket_metrics(parsed: dict[str, Any]) -> dict[str, Any]:
    items = parsed.get("items") or []
    output: dict[str, Any] = {}
    for field in ("text_layer", "chunk_type", "length_bucket", "selection_reason"):
        grouped: dict[str, list[dict[str, Any]]] = defaultdict(list)
        for item in items:
            grouped[str(item.get(field) or "unknown")].append(item)
        output[f"by_{field}"] = {
            bucket: arm_metrics({"items": bucket_items})
            for bucket, bucket_items in sorted(grouped.items())
        }
    return output


def required_fields_present(item: dict[str, Any]) -> bool:
    return all(field in item for field in ("literal_ko", "natural_ko", "terms", "grammar_notes", "doctrinal_notes", "uncertainties", "quality_flags"))


def required_types_valid(item: dict[str, Any]) -> bool:
    return (
        isinstance(item.get("literal_ko"), str)
        and isinstance(item.get("natural_ko"), str)
        and all(isinstance(item.get(field), list) for field in ("terms", "grammar_notes", "doctrinal_notes", "uncertainties", "quality_flags"))
        and all(isinstance(term, dict) for term in (item.get("terms") or []))
    )


def has_empty_translation(item: dict[str, Any]) -> bool:
    return not str(item.get("literal_ko") or "").strip() or not str(item.get("natural_ko") or "").strip()


def rate(count: int, total: int) -> str:
    if total <= 0:
        return "0.000000"
    return str((Decimal(count) / Decimal(total)).quantize(Decimal("0.000001"), rounding=ROUND_HALF_UP))


def length_ratio(numerator: Any, denominator: Any) -> Decimal:
    den = max(1, len(str(denominator or "")))
    return Decimal(len(str(numerator or ""))) / Decimal(den)


def build_run_manifest(
    *,
    batch_requests_planned: int,
    cost_estimate: dict[str, Any] | None,
    submitted: bool = False,
    batch_requests_submitted: int = 0,
    api_llm_calls: int = 0,
    arm_a_status: str = "not_submitted",
    arm_b_status: str = "not_submitted",
    arm_a_provider_batch_id: str | None = None,
    arm_b_provider_batch_id: str | None = None,
    arm_a_requests_submitted: int = 0,
    arm_b_requests_submitted: int = 0,
    remaining_cap_usd: str | None = None,
    output_paths: dict[str, str] | None = None,
    warnings: list[str] | None = None,
) -> dict[str, Any]:
    return {
        "step": "4-response-schema-smoke",
        "schema_version": "pali_step4_response_schema_run_manifest_v1",
        "run_id": RUN_ID,
        "api_llm_calls": api_llm_calls,
        "batch_requests_planned": batch_requests_planned,
        "batch_requests_submitted": batch_requests_submitted,
        "cost_estimate_usd": None if cost_estimate is None else cost_estimate.get("cost_estimate_usd"),
        "cost_actual_usd": None,
        "hard_cap_usd": 4,
        "cap_passed_before_submit": bool(cost_estimate and cost_estimate.get("cap_passed_before_submit")),
        "submitted": submitted,
        "arm_a_status": arm_a_status,
        "arm_b_status": arm_b_status,
        "arm_a_provider_batch_id": arm_a_provider_batch_id,
        "arm_b_provider_batch_id": arm_b_provider_batch_id,
        "arm_a_requests_submitted": arm_a_requests_submitted,
        "arm_b_requests_submitted": arm_b_requests_submitted,
        "prompt_mutation": False,
        "glossary_mutation": False,
        "gold_set_mutation": False,
        "schema_file_mutation": False,
        "translation_corpus_mutation": False,
        "production_prompt_changed": False,
        "holdout_gold_frozen": False,
        "silver_canary_status": SILVER_CANARY_STATUS,
        "silver_canary_needs_pali_expert_policy": SILVER_CANARY_NEEDS_PALI_EXPERT_POLICY,
        "future_total_batch_requests": 1020,
        "response_schema_dialect_fixed": True,
        "unsupported_schema_keyword_guard_enabled": True,
        "remaining_cap_usd": remaining_cap_usd,
        "output_paths": output_paths or {},
        "warnings": warnings or [],
    }


def render_submit_plan(
    *,
    out_dir: Path,
    selection_manifest: dict[str, Any],
    cost_estimate: dict[str, Any],
    arm_a_jsonl: Path,
    arm_b_jsonl: Path,
) -> str:
    cap_status = "PASS" if cost_estimate.get("cap_passed_before_submit") else "BLOCKED"
    return "\n".join(
        [
            "# Step 4 Response Schema Stress Micro-Smoke Submit Plan",
            "",
            "This plan is dry-run output. No Gemini Batch job has been submitted.",
            "",
            "## Scope",
            "",
            f"- selected segments: {selection_manifest.get('selected_count')}",
            f"- known strict parse failures included: {selection_manifest.get('known_strict_parse_failure_count')}",
            f"- vulnerable strict-passed included: {selection_manifest.get('vulnerable_strict_passed_count')}",
            "- planned requests: 100 (50 Arm A + 50 Arm B)",
            f"- estimated p90 cost: ${cost_estimate.get('cost_estimate_usd')}",
            f"- hard cap: ${cost_estimate.get('hard_cap_usd')}",
            f"- cap status: {cap_status}",
            "",
            "## Arm Inputs",
            "",
            f"- Arm A JSONL: `{arm_a_jsonl}`",
            f"- Arm B JSONL: `{arm_b_jsonl}`",
            "",
            "## Submit Later",
            "",
            "If neither arm has been submitted, `--submit` may be used after reviewing this package and confirming the $4 cap.",
            "If Arm A already has a provider batch id, do not use plain `--submit`; retry Arm B only:",
            "",
            "```bash",
            "./venv/bin/python -m backend.pali.scripts.run_response_schema_smoke \\",
            f"  --out {out_dir} \\",
            "  --submit-arm B \\",
            "  --pretty",
            "```",
            "",
            "If Arm B is rejected because response_schema is unsupported in the Gemini Batch path, record that result and keep the current free-form JSON plus salvage cascade.",
        ]
    ) + "\n"


def render_recommendation_placeholder() -> str:
    return "\n".join(
        [
            "# Step 4 Recommendation",
            "",
            "Status: dry-run only, not submitted.",
            "",
            "No production recommendation is made until the A/B batch path is executed and parsed.",
            "Until then, keep the current free-form JSON plus salvage cascade.",
            "",
            "Silver canary remains advisory only and is not gold accuracy.",
        ]
    ) + "\n"


def render_comparison_markdown(comparison: dict[str, Any]) -> str:
    rec = comparison.get("recommendation") or {}
    return "\n".join(
        [
            "# Step 4 Response Schema Comparison",
            "",
            f"- recommendation: `{rec.get('decision', 'not_available')}`",
            f"- reason: {rec.get('reason', 'not available')}",
            "",
            "## Arm A Metrics",
            "",
            "```json",
            json.dumps(comparison.get("arm_a_metrics", {}), ensure_ascii=False, indent=2),
            "```",
            "",
            "## Arm B Metrics",
            "",
            "```json",
            json.dumps(comparison.get("arm_b_metrics", {}), ensure_ascii=False, indent=2),
            "```",
        ]
    ) + "\n"


def placeholder_json_outputs(paths: Step4Paths, *, pretty: bool = False, preserve_provider_status: bool = True) -> None:
    status = {"status": "not_submitted", "submitted": False, "provider_batch_id": None}
    if not preserve_provider_status or not paths.provider_status_arm_a.exists():
        write_json(paths.provider_status_arm_a, {"arm": "A", **status}, pretty=pretty)
    if not preserve_provider_status or not paths.provider_status_arm_b.exists():
        write_json(paths.provider_status_arm_b, {"arm": "B", **status}, pretty=pretty)
    if not preserve_provider_status or not paths.arm_a_raw_results.exists():
        paths.arm_a_raw_results.write_text("", encoding="utf-8")
    if not preserve_provider_status or not paths.arm_b_raw_results.exists():
        paths.arm_b_raw_results.write_text("", encoding="utf-8")
    if not preserve_provider_status or not paths.arm_a_parsed.exists():
        write_json(paths.arm_a_parsed, {"schema_version": "pali_step4_response_schema_arm_parsed_v1", "arm": "A", "status": "not_submitted", "items": []}, pretty=pretty)
    if not preserve_provider_status or not paths.arm_b_parsed.exists():
        write_json(paths.arm_b_parsed, {"schema_version": "pali_step4_response_schema_arm_parsed_v1", "arm": "B", "status": "not_submitted", "items": []}, pretty=pretty)
    if not preserve_provider_status or not paths.arm_a_salvage_report.exists():
        write_json(paths.arm_a_salvage_report, {"arm": "A", "status": "not_submitted"}, pretty=pretty)
    if not preserve_provider_status or not paths.arm_b_salvage_report.exists():
        write_json(paths.arm_b_salvage_report, {"arm": "B", "status": "not_submitted"}, pretty=pretty)
    comparison = {
        "schema_version": "pali_step4_response_schema_comparison_v1",
        "status": "not_submitted",
        "recommendation": {
            "decision": "keep_current_free_form_json_plus_salvage_cascade",
            "reason": "Dry-run only; no A/B batch result is available yet.",
        },
    }
    write_json(paths.comparison_report, comparison, pretty=pretty)
    paths.comparison_report_md.write_text(render_comparison_markdown(comparison), encoding="utf-8")
    paths.recommendation.write_text(render_recommendation_placeholder(), encoding="utf-8")


def summarize_selection_for_stdout(selection: dict[str, Any], cost: dict[str, Any], paths: Step4Paths) -> dict[str, Any]:
    return {
        "status": "DRY_RUN_READY" if selection.get("selection_readiness") == "PASS" and cost.get("cap_passed_before_submit") else "DRY_RUN_BLOCKED",
        "selected_count": selection.get("selected_count"),
        "known_fail_count_included": selection.get("known_strict_parse_failure_count"),
        "vulnerable_strict_passed_count": selection.get("vulnerable_strict_passed_count"),
        "planned_requests": cost.get("total_request_count"),
        "cost_estimate_usd": cost.get("cost_estimate_usd"),
        "cap_passed_before_submit": cost.get("cap_passed_before_submit"),
        "api_llm_calls": 0,
        "selection_manifest": str(paths.selection_manifest),
        "arm_a_batch_input": str(paths.arm_a_jsonl),
        "arm_b_batch_input": str(paths.arm_b_jsonl),
        "submit_plan": str(paths.submit_plan),
    }

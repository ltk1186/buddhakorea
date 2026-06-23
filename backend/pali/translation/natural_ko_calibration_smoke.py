"""Controlled natural_ko_v2 calibration smoke harness.

Default/preflight execution is local-only. Provider calls are only made by the
CLI submit/poll/fetch modes. This module does not mutate production prompts,
Step 5 selection, glossary, gold, source XML, or the translation corpus.
"""

from __future__ import annotations

import json
import re
from collections import Counter, defaultdict
from dataclasses import dataclass
from decimal import Decimal, ROUND_HALF_UP
from pathlib import Path
from typing import Any

from backend.pali.scripts.submit_gemini_smoke_batch import (
    DEFAULT_MODEL,
    DEFAULT_PRICE_PROFILE_ID,
    DEFAULT_PRICE_PROFILE_PATH,
    GeminiBatchRestClient,
    build_inline_request_from_provider_line,
    extract_batch_name,
    extract_generate_content_response,
    extract_inline_result_lines,
    extract_model_output_text,
    extract_result_key,
    load_price_profile,
    parse_batch_results,
    status_snapshot,
)
from backend.pali.scripts.salvage_pilot_300_batch_parse import (
    apply_successful_parse,
    extract_finish_reason,
    parse_output_cascade,
)
from backend.pali.translation.budget import PriceProfile, TokenEstimate, estimate_request_cost
from backend.pali.translation.natural_ko_readability import (
    DEFAULT_OUT,
    NATURAL_KO_V2_1_MARKER,
    NATURAL_KO_V2_2_MARKER,
    NATURAL_KO_V2_MARKER,
    build_request_preview_v2_1,
    build_request_preview_v2_2,
    build_request_previews,
    readability_metrics,
    render_glossary_lock_v2_2_md,
    render_dry_run_plan,
    render_prompt_variant,
    render_prompt_variant_v2_1,
    render_prompt_variant_v2_2,
    run_calibration_prep,
    write_json,
    write_jsonl,
)
from backend.pali.translation.natural_ko_v2_2_quality import (
    evaluate_d_arm_item,
    glossary_lock_payload_v2_2,
    summarize_d_arm_gates,
)


HARD_CAP_USD = Decimal("4")
PLANNED_ITEMS = 30
PLANNED_ARMS = 2
PLANNED_REQUESTS = 60
ARM_A = "A_prime"
ARM_B = "B_natural_ko_v2"
ARM_C = "C_natural_ko_v2_1"
ARM_D = "D_natural_ko_v2_2"
DEFAULT_V2_2_OUT = Path("data/reports/pali/natural_ko_calibration_v2_2")


class NaturalKoSmokeBlocked(RuntimeError):
    def __init__(self, status: str, message: str, details: dict[str, Any] | None = None):
        super().__init__(message)
        self.status = status
        self.message = message
        self.details = details or {}


@dataclass(frozen=True)
class NaturalKoSmokePaths:
    out_dir: Path
    selection: Path
    prompt_variant: Path
    prompt_variant_v2_1: Path
    arm_a_jsonl: Path
    arm_b_jsonl: Path
    arm_c_jsonl: Path
    preflight_json: Path
    preflight_md: Path
    preflight_v2_1_json: Path
    preflight_v2_1_md: Path
    run_manifest: Path
    provider_status_arm_a: Path
    provider_status_arm_b: Path
    provider_status_arm_c: Path
    arm_a_raw: Path
    arm_b_raw: Path
    arm_c_raw: Path
    arm_a_parsed: Path
    arm_b_parsed: Path
    arm_c_parsed: Path
    parse_summary: Path
    comparison_json: Path
    comparison_md: Path
    comparison_v2_1_json: Path
    comparison_v2_1_md: Path
    human_review_sheet: Path
    final_recommendation_json: Path
    final_recommendation_md: Path
    step6_handoff_v2_1: Path
    prompt_variant_v2_2: Path
    glossary_lock_v2_2_md: Path
    glossary_lock_v2_2_json: Path
    arm_d_jsonl: Path
    arm_d_submit_plan: Path
    arm_d_run_manifest: Path
    provider_status_arm_d: Path
    arm_d_raw: Path
    arm_d_parsed: Path
    arm_d_summary_json: Path
    arm_d_summary_md: Path
    comparison_v2_2_json: Path
    comparison_v2_2_md: Path
    d_manual_review_sheet: Path
    d_final_recommendation_md: Path
    d_no_api_executed_md: Path


def smoke_paths(out_dir: Path = DEFAULT_OUT) -> NaturalKoSmokePaths:
    return NaturalKoSmokePaths(
        out_dir=out_dir,
        selection=out_dir / "calibration_30_selection.json",
        prompt_variant=out_dir / "prompt_variant_natural_ko_v2.md",
        prompt_variant_v2_1=out_dir / "prompt_variant_natural_ko_v2_1.md",
        arm_a_jsonl=out_dir / "natural_ko_v1_request_preview.jsonl",
        arm_b_jsonl=out_dir / "natural_ko_v2_request_preview.jsonl",
        arm_c_jsonl=out_dir / "natural_ko_v2_1_request_preview.jsonl",
        preflight_json=out_dir / "smoke_preflight.json",
        preflight_md=out_dir / "smoke_preflight.md",
        preflight_v2_1_json=out_dir / "smoke_preflight_v2_1.json",
        preflight_v2_1_md=out_dir / "smoke_preflight_v2_1.md",
        run_manifest=out_dir / "smoke_run_manifest.json",
        provider_status_arm_a=out_dir / "provider_status_arm_a_prime.json",
        provider_status_arm_b=out_dir / "provider_status_arm_b_v2.json",
        provider_status_arm_c=out_dir / "provider_status_arm_c_v2_1.json",
        arm_a_raw=out_dir / "arm_a_prime_raw_results.jsonl",
        arm_b_raw=out_dir / "arm_b_v2_raw_results.jsonl",
        arm_c_raw=out_dir / "arm_c_v2_1_raw_results.jsonl",
        arm_a_parsed=out_dir / "arm_a_prime_parsed.json",
        arm_b_parsed=out_dir / "arm_b_v2_parsed.json",
        arm_c_parsed=out_dir / "arm_c_v2_1_parsed.json",
        parse_summary=out_dir / "parse_summary.json",
        comparison_json=out_dir / "natural_ko_v2_comparison.json",
        comparison_md=out_dir / "natural_ko_v2_comparison.md",
        comparison_v2_1_json=out_dir / "natural_ko_v2_1_comparison.json",
        comparison_v2_1_md=out_dir / "natural_ko_v2_1_comparison.md",
        human_review_sheet=out_dir / "human_review_sheet.md",
        final_recommendation_json=out_dir / "final_recommendation.json",
        final_recommendation_md=out_dir / "final_recommendation.md",
        step6_handoff_v2_1=out_dir / "step6_handoff_natural_ko_v2_1.md",
        prompt_variant_v2_2=out_dir / "prompt_variant_natural_ko_v2_2.md",
        glossary_lock_v2_2_md=out_dir / "glossary_lock_v2_2.md",
        glossary_lock_v2_2_json=out_dir / "glossary_lock_v2_2.json",
        arm_d_jsonl=out_dir / "d_arm_30_request_preview.jsonl",
        arm_d_submit_plan=out_dir / "d_arm_30_submit_plan.md",
        arm_d_run_manifest=out_dir / "d_arm_30_run_manifest.json",
        provider_status_arm_d=out_dir / "d_arm_30_provider_status.json",
        arm_d_raw=out_dir / "d_arm_30_raw_results.jsonl",
        arm_d_parsed=out_dir / "d_arm_30_parsed.json",
        arm_d_summary_json=out_dir / "d_arm_30_summary.json",
        arm_d_summary_md=out_dir / "d_arm_30_summary.md",
        comparison_v2_2_json=out_dir / "d_arm_30_comparison.json",
        comparison_v2_2_md=out_dir / "d_arm_30_comparison.md",
        d_manual_review_sheet=out_dir / "d_arm_30_manual_review_sheet.md",
        d_final_recommendation_md=out_dir / "d_arm_30_final_recommendation.md",
        d_no_api_executed_md=out_dir / "d_arm_30_no_api_executed.md",
    )


def read_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def read_jsonl(path: Path) -> list[dict[str, Any]]:
    if not path.exists():
        return []
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


def decimal_rate(count: int, total: int) -> str:
    if total <= 0:
        return "0.000000"
    return str((Decimal(count) / Decimal(total)).quantize(Decimal("0.000001"), rounding=ROUND_HALF_UP))


def quantize(value: Decimal) -> str:
    return str(value.quantize(Decimal("0.000001"), rounding=ROUND_HALF_UP))


def default_run_manifest() -> dict[str, Any]:
    return {
        "step": "5.5-C-D-natural-ko-v2-controlled-live-smoke",
        "reader_ko_added": False,
        "production_prompt_changed": False,
        "step5_selection_modified": False,
        "step6_started": False,
        "response_schema": True,
        "salvage_cascade_fallback": True,
        "planned_items": PLANNED_ITEMS,
        "planned_arms": PLANNED_ARMS,
        "planned_provider_requests": PLANNED_REQUESTS,
        "prompt_variant_v2_1_created": False,
        "c_arm_planned_requests": 30,
        "a_prime_reused": False,
        "b_kept_reference": False,
        "hard_cost_cap_usd": "4",
        "estimated_cost_usd": None,
        "cap_passed_before_submit": False,
        "api_llm_calls_submitted": 0,
        "batch_submissions": 0,
        "gold_accuracy_available": False,
        "silver_canary_status": "advisory_only_not_gold_accuracy",
        "arm_a_prime_provider_batch_id": None,
        "arm_b_v2_provider_batch_id": None,
        "arm_c_v2_1_provider_batch_id": None,
        "prompt_mutation": False,
        "glossary_mutation": False,
        "gold_set_mutation": False,
        "source_xml_mutation": False,
        "translation_corpus_mutation": False,
    }


def estimate_preview_cost(
    arm_a: list[dict[str, Any]],
    arm_b: list[dict[str, Any]],
    price_profile: PriceProfile,
) -> dict[str, Any]:
    rows = [("A_prime", row) for row in arm_a] + [("B_natural_ko_v2", row) for row in arm_b]
    per_request: list[dict[str, Any]] = []
    totals = Counter()
    bucket_totals: dict[str, Counter[str]] = defaultdict(Counter)
    for arm, row in rows:
        prompt = row["request"]["contents"][0]["parts"][0]["text"]
        # Conservative local estimate. This is a cap gate, not a billing claim.
        input_tokens = max(1, len(prompt) // 3)
        output_tokens = 1200
        thinking_tokens = 3500
        cost = estimate_request_cost(
            TokenEstimate(
                input_tokens=input_tokens,
                output_tokens=output_tokens,
                thinking_tokens=thinking_tokens,
            ),
            price_profile,
        )
        metadata = row.get("metadata") or {}
        bucket = f"{arm}:{metadata.get('text_layer', 'unknown')}:{metadata.get('calibration_role', 'unknown')}"
        totals["input_tokens"] += input_tokens
        totals["output_tokens"] += output_tokens
        totals["thinking_tokens"] += thinking_tokens
        totals["cost_micros"] += int(cost * Decimal("1000000"))
        bucket_totals[bucket]["requests"] += 1
        bucket_totals[bucket]["cost_micros"] += int(cost * Decimal("1000000"))
        per_request.append(
            {
                "arm": arm,
                "stable_segment_key": row.get("key"),
                "estimated_input_tokens": input_tokens,
                "estimated_output_tokens": output_tokens,
                "estimated_thinking_tokens": thinking_tokens,
                "estimated_cost_usd": quantize(cost),
                "bucket": bucket,
            }
        )
    estimated_cost = Decimal(totals["cost_micros"]) / Decimal("1000000")
    bucket_driver = max(
        (
            {
                "bucket": bucket,
                "requests": int(counter["requests"]),
                "estimated_cost_usd": quantize(Decimal(counter["cost_micros"]) / Decimal("1000000")),
            }
            for bucket, counter in bucket_totals.items()
        ),
        key=lambda item: Decimal(item["estimated_cost_usd"]),
        default=None,
    )
    return {
        "schema_version": "natural_ko_v2_smoke_cost_estimate_v1",
        "method": "local conservative char-count token estimate using project batch price profile",
        "request_count": len(rows),
        "estimated_input_tokens": int(totals["input_tokens"]),
        "estimated_output_tokens": int(totals["output_tokens"]),
        "estimated_thinking_tokens": int(totals["thinking_tokens"]),
        "estimated_cost_usd": quantize(estimated_cost),
        "hard_cap_usd": "4",
        "cap_passed_before_submit": estimated_cost <= HARD_CAP_USD,
        "largest_cost_bucket": bucket_driver,
        "per_request": per_request,
    }


def estimate_rows_cost(
    rows: list[tuple[str, dict[str, Any]]],
    price_profile: PriceProfile,
    *,
    schema_version: str,
) -> dict[str, Any]:
    per_request: list[dict[str, Any]] = []
    totals = Counter()
    bucket_totals: dict[str, Counter[str]] = defaultdict(Counter)
    for arm, row in rows:
        prompt = row["request"]["contents"][0]["parts"][0]["text"]
        input_tokens = max(1, len(prompt) // 3)
        output_tokens = 1200
        thinking_tokens = 3500
        cost = estimate_request_cost(
            TokenEstimate(input_tokens=input_tokens, output_tokens=output_tokens, thinking_tokens=thinking_tokens),
            price_profile,
        )
        metadata = row.get("metadata") or {}
        bucket = f"{arm}:{metadata.get('text_layer', 'unknown')}:{metadata.get('calibration_role', 'unknown')}"
        totals["input_tokens"] += input_tokens
        totals["output_tokens"] += output_tokens
        totals["thinking_tokens"] += thinking_tokens
        totals["cost_micros"] += int(cost * Decimal("1000000"))
        bucket_totals[bucket]["requests"] += 1
        bucket_totals[bucket]["cost_micros"] += int(cost * Decimal("1000000"))
        per_request.append(
            {
                "arm": arm,
                "stable_segment_key": row.get("key"),
                "estimated_input_tokens": input_tokens,
                "estimated_output_tokens": output_tokens,
                "estimated_thinking_tokens": thinking_tokens,
                "estimated_cost_usd": quantize(cost),
                "bucket": bucket,
            }
        )
    estimated_cost = Decimal(totals["cost_micros"]) / Decimal("1000000")
    bucket_driver = max(
        (
            {
                "bucket": bucket,
                "requests": int(counter["requests"]),
                "estimated_cost_usd": quantize(Decimal(counter["cost_micros"]) / Decimal("1000000")),
            }
            for bucket, counter in bucket_totals.items()
        ),
        key=lambda item: Decimal(item["estimated_cost_usd"]),
        default=None,
    )
    return {
        "schema_version": schema_version,
        "method": "local conservative char-count token estimate using project batch price profile",
        "request_count": len(rows),
        "estimated_input_tokens": int(totals["input_tokens"]),
        "estimated_output_tokens": int(totals["output_tokens"]),
        "estimated_thinking_tokens": int(totals["thinking_tokens"]),
        "estimated_cost_usd": quantize(estimated_cost),
        "hard_cap_usd": "4",
        "cap_passed_before_submit": estimated_cost <= HARD_CAP_USD,
        "largest_cost_bucket": bucket_driver,
        "per_request": per_request,
    }


def run_preflight(
    *,
    out_dir: Path = DEFAULT_OUT,
    price_profile_path: Path = DEFAULT_PRICE_PROFILE_PATH,
    price_profile_id: str = DEFAULT_PRICE_PROFILE_ID,
    pretty: bool = False,
) -> dict[str, Any]:
    paths = smoke_paths(out_dir)
    if not paths.selection.exists():
        run_calibration_prep(out_dir=out_dir, pretty=pretty)
    selection = read_json(paths.selection)
    arm_a, arm_b = build_request_previews(selection)
    write_jsonl(paths.arm_a_jsonl, arm_a)
    write_jsonl(paths.arm_b_jsonl, arm_b)
    paths.prompt_variant.write_text(render_prompt_variant(), encoding="utf-8")
    arm_a = read_jsonl(paths.arm_a_jsonl)
    arm_b = read_jsonl(paths.arm_b_jsonl)
    price_profile, price_profile_raw = load_price_profile(price_profile_path, price_profile_id)
    cost_estimate = estimate_preview_cost(arm_a, arm_b, price_profile)
    errors, warnings = validate_preflight(selection, arm_a, arm_b)
    if paths.prompt_variant.exists() and prompt_requests_reader_ko(paths.prompt_variant.read_text(encoding="utf-8")):
        errors.append("BLOCKED_READER_KO_IN_PROMPT_VARIANT")
    preflight = {
        "schema_version": "natural_ko_v2_smoke_preflight_v1",
        "status": "PASS" if not errors and cost_estimate["cap_passed_before_submit"] else "FAIL",
        "errors": errors + ([] if cost_estimate["cap_passed_before_submit"] else ["BLOCKED_ESTIMATED_COST_OVER_CAP"]),
        "warnings": warnings,
        "planned_items": len(selection.get("items") or []),
        "planned_arms": 2,
        "planned_provider_requests": len(arm_a) + len(arm_b),
        "estimated_cost_usd": cost_estimate["estimated_cost_usd"],
        "hard_cost_cap_usd": "4",
        "cap_passed_before_submit": cost_estimate["cap_passed_before_submit"],
        "cost_estimate": cost_estimate,
        "price_profile_id": price_profile_id,
        "price_profile": price_profile_raw,
        "reader_ko_added": False,
        "api_llm_calls": 0,
        "network_calls": 0,
        "batch_submissions": 0,
    }
    write_json(paths.preflight_json, preflight, pretty=pretty)
    paths.preflight_md.write_text(render_preflight_markdown(preflight), encoding="utf-8")
    manifest = current_run_manifest(paths)
    manifest.update(
        {
            "estimated_cost_usd": cost_estimate["estimated_cost_usd"],
            "cap_passed_before_submit": cost_estimate["cap_passed_before_submit"],
            "preflight_status": preflight["status"],
        }
    )
    write_json(paths.run_manifest, manifest, pretty=pretty)
    return preflight


def run_preflight_v2_1(
    *,
    out_dir: Path = DEFAULT_OUT,
    price_profile_path: Path = DEFAULT_PRICE_PROFILE_PATH,
    price_profile_id: str = DEFAULT_PRICE_PROFILE_ID,
    pretty: bool = False,
) -> dict[str, Any]:
    paths = smoke_paths(out_dir)
    if not paths.selection.exists():
        run_calibration_prep(out_dir=out_dir, pretty=pretty)
    selection = read_json(paths.selection)
    arm_a, arm_b = build_request_previews(selection)
    arm_c = build_request_preview_v2_1(selection)
    if not paths.arm_a_jsonl.exists():
        write_jsonl(paths.arm_a_jsonl, arm_a)
    if not paths.arm_b_jsonl.exists():
        write_jsonl(paths.arm_b_jsonl, arm_b)
    write_jsonl(paths.arm_c_jsonl, arm_c)
    if not paths.prompt_variant.exists():
        paths.prompt_variant.write_text(render_prompt_variant(), encoding="utf-8")
    paths.prompt_variant_v2_1.write_text(render_prompt_variant_v2_1(), encoding="utf-8")
    arm_a = read_jsonl(paths.arm_a_jsonl)
    arm_b = read_jsonl(paths.arm_b_jsonl)
    arm_c = read_jsonl(paths.arm_c_jsonl)
    price_profile, price_profile_raw = load_price_profile(price_profile_path, price_profile_id)
    cost_estimate = estimate_rows_cost(
        [(ARM_C, row) for row in arm_c],
        price_profile,
        schema_version="natural_ko_v2_1_c_arm_cost_estimate_v1",
    )
    errors, warnings = validate_preflight_v2_1(selection, arm_a, arm_b, arm_c)
    if paths.prompt_variant_v2_1.exists() and prompt_requests_reader_ko(paths.prompt_variant_v2_1.read_text(encoding="utf-8")):
        errors.append("BLOCKED_READER_KO_IN_PROMPT_VARIANT_V2_1")
    preflight = {
        "schema_version": "natural_ko_v2_1_smoke_preflight_v1",
        "status": "PASS" if not errors and cost_estimate["cap_passed_before_submit"] else "FAIL",
        "errors": errors + ([] if cost_estimate["cap_passed_before_submit"] else ["BLOCKED_ESTIMATED_COST_OVER_CAP"]),
        "warnings": warnings,
        "planned_items": len(selection.get("items") or []),
        "planned_arms": 1,
        "planned_provider_requests": len(arm_c),
        "a_prime_reused": True,
        "b_kept_reference": True,
        "estimated_cost_usd": cost_estimate["estimated_cost_usd"],
        "hard_cost_cap_usd": "4",
        "cap_passed_before_submit": cost_estimate["cap_passed_before_submit"],
        "cost_estimate": cost_estimate,
        "price_profile_id": price_profile_id,
        "price_profile": price_profile_raw,
        "reader_ko_added": False,
        "api_llm_calls": 0,
        "network_calls": 0,
        "batch_submissions": 0,
    }
    write_json(paths.preflight_v2_1_json, preflight, pretty=pretty)
    paths.preflight_v2_1_md.write_text(render_preflight_v2_1_markdown(preflight), encoding="utf-8")
    paths.step6_handoff_v2_1.write_text(render_step6_handoff_v2_1({"paired_count": 0}), encoding="utf-8")
    manifest = current_run_manifest(paths)
    manifest.update(
        {
            "previous_ab_api_llm_calls_submitted": manifest.get("api_llm_calls_submitted"),
            "previous_ab_batch_submissions": manifest.get("batch_submissions"),
            "prompt_variant_v2_1_created": True,
            "c_arm_planned_requests": len(arm_c),
            "c_arm_api_llm_calls_submitted": 0,
            "c_arm_batch_submissions": 0,
            "a_prime_reused": True,
            "b_kept_reference": True,
            "api_llm_calls_submitted": 0,
            "batch_submissions": 0,
            "estimated_cost_usd_c_arm": cost_estimate["estimated_cost_usd"],
            "cap_passed_before_submit_c_arm": cost_estimate["cap_passed_before_submit"],
            "preflight_v2_1_status": preflight["status"],
            "reader_ko_added": False,
            "production_prompt_changed": False,
            "step6_started": False,
            "gold_accuracy_available": False,
            "silver_canary_status": "advisory_only_not_gold_accuracy",
        }
    )
    write_json(paths.run_manifest, manifest, pretty=pretty)
    return preflight


def run_preflight_v2_2(
    *,
    out_dir: Path = DEFAULT_V2_2_OUT,
    calibration_source_dir: Path = DEFAULT_OUT,
    price_profile_path: Path = DEFAULT_PRICE_PROFILE_PATH,
    price_profile_id: str = DEFAULT_PRICE_PROFILE_ID,
    pretty: bool = False,
) -> dict[str, Any]:
    paths = smoke_paths(out_dir)
    source_paths = smoke_paths(calibration_source_dir)
    if not source_paths.selection.exists():
        run_calibration_prep(out_dir=calibration_source_dir, pretty=pretty)
    selection = read_json(source_paths.selection)
    arm_a, arm_b = build_request_previews(selection)
    arm_c = build_request_preview_v2_1(selection)
    arm_d = build_request_preview_v2_2(selection)
    paths.out_dir.mkdir(parents=True, exist_ok=True)
    paths.prompt_variant_v2_2.write_text(render_prompt_variant_v2_2(), encoding="utf-8")
    write_json(paths.glossary_lock_v2_2_json, glossary_lock_payload_v2_2(), pretty=pretty)
    paths.glossary_lock_v2_2_md.write_text(render_glossary_lock_v2_2_md(), encoding="utf-8")
    write_jsonl(paths.arm_d_jsonl, arm_d)
    price_profile, price_profile_raw = load_price_profile(price_profile_path, price_profile_id)
    cost_estimate = estimate_rows_cost(
        [(ARM_D, row) for row in arm_d],
        price_profile,
        schema_version="natural_ko_v2_2_d_arm_cost_estimate_v1",
    )
    errors, warnings = validate_preflight_v2_2(selection, arm_a, arm_b, arm_c, arm_d)
    if prompt_requests_reader_ko(paths.prompt_variant_v2_2.read_text(encoding="utf-8")):
        errors.append("BLOCKED_READER_KO_IN_PROMPT_VARIANT_V2_2")
    preflight = {
        "schema_version": "natural_ko_v2_2_d_arm_preflight_v1",
        "status": "PASS" if not errors and cost_estimate["cap_passed_before_submit"] else "FAIL",
        "errors": errors + ([] if cost_estimate["cap_passed_before_submit"] else ["BLOCKED_ESTIMATED_COST_OVER_CAP"]),
        "warnings": warnings,
        "planned_items": len(selection.get("items") or []),
        "planned_arms": 1,
        "planned_provider_requests": len(arm_d),
        "same_calibration_items_as_previous": True,
        "estimated_cost_usd": cost_estimate["estimated_cost_usd"],
        "hard_cost_cap_usd": "4",
        "cap_passed_before_submit": cost_estimate["cap_passed_before_submit"],
        "cost_estimate": cost_estimate,
        "price_profile_id": price_profile_id,
        "price_profile": price_profile_raw,
        "response_schema": True,
        "salvage_cascade_fallback": True,
        "reader_ko_added": False,
        "api_llm_calls": 0,
        "network_calls": 0,
        "batch_submissions": 0,
    }
    paths.arm_d_submit_plan.write_text(render_d_arm_submit_plan(preflight), encoding="utf-8")
    manifest = {
        "step": "5.5-H-I-natural-ko-v2-2-d-arm-prep",
        "api_llm_calls": 0,
        "network_calls": 0,
        "batch_submissions": 0,
        "translation_generation": False,
        "provider_call_made": False,
        "planned_provider_requests": len(arm_d),
        "hard_cost_cap_usd": "4",
        "estimated_cost_usd": preflight["estimated_cost_usd"],
        "cap_passed_before_submit": preflight["cap_passed_before_submit"],
        "response_schema": True,
        "salvage_cascade_fallback": True,
        "reader_ko_added": False,
        "production_prompt_changed": False,
        "step5_selection_modified": False,
        "step6_started": False,
        "glossary_mutation": False,
        "gold_set_mutation": False,
        "source_xml_mutation": False,
        "translation_corpus_mutation": False,
        "calibration_source_dir": str(calibration_source_dir),
        "output_dir": str(out_dir),
        "preflight_status": preflight["status"],
        "warnings": warnings,
    }
    write_json(paths.arm_d_run_manifest, manifest, pretty=pretty)
    paths.d_no_api_executed_md.write_text(render_no_api_executed_v2_2(preflight), encoding="utf-8")
    return preflight


def validate_preflight(
    selection: dict[str, Any],
    arm_a: list[dict[str, Any]],
    arm_b: list[dict[str, Any]],
) -> tuple[list[str], list[str]]:
    errors: list[str] = []
    warnings: list[str] = []
    items = selection.get("items") or []
    if len(items) != PLANNED_ITEMS:
        errors.append(f"BLOCKED_SELECTION_COUNT_{len(items)}")
    if len(arm_a) != PLANNED_ITEMS:
        errors.append(f"BLOCKED_ARM_A_REQUEST_COUNT_{len(arm_a)}")
    if len(arm_b) != PLANNED_ITEMS:
        errors.append(f"BLOCKED_ARM_B_REQUEST_COUNT_{len(arm_b)}")
    if len(arm_a) + len(arm_b) != PLANNED_REQUESTS:
        errors.append(f"BLOCKED_TOTAL_REQUEST_COUNT_{len(arm_a) + len(arm_b)}")
    for row in arm_a + arm_b:
        schema = response_schema_for_row(row)
        if not schema:
            errors.append(f"BLOCKED_MISSING_RESPONSE_SCHEMA:{row.get('key')}")
        elif "reader_ko" in (schema.get("properties") or {}):
            errors.append(f"BLOCKED_READER_KO_IN_RESPONSE_SCHEMA:{row.get('key')}")
        metadata = row.get("metadata") or {}
        if "source_text_hash" not in metadata:
            errors.append(f"BLOCKED_MISSING_SOURCE_TEXT_HASH_METADATA:{row.get('key')}")
        elif not metadata.get("source_text_hash"):
            warnings.append(f"source_text_hash_unavailable:{row.get('key')}")
    selection_missing_hash = [item.get("stable_segment_key") for item in items if "source_text_hash" not in item]
    if selection_missing_hash:
        errors.append(f"BLOCKED_SELECTION_DROPPED_SOURCE_TEXT_HASH:{len(selection_missing_hash)}")

    if arm_a and arm_b:
        a_prompt = prompt_for_row(arm_a[0])
        b_prompt = prompt_for_row(arm_b[0])
        if NATURAL_KO_V2_MARKER in a_prompt:
            errors.append("BLOCKED_ARM_A_CONTAINS_V2_MARKER")
        if NATURAL_KO_V2_MARKER not in b_prompt:
            errors.append("BLOCKED_ARM_B_MISSING_V2_MARKER")
        if "natural_ko 작성 원칙:\n- 독자용 자연역입니다." not in a_prompt:
            errors.append("BLOCKED_ARM_A_MISSING_ORIGINAL_NATURAL_KO_GUIDANCE")
        if "natural_ko 작성 원칙:\n- 독자용 자연역입니다." in b_prompt:
            errors.append("BLOCKED_ARM_B_RETAINS_CONFLICTING_V1_NATURAL_KO_GUIDANCE")
        if prompt_requests_reader_ko(a_prompt) or prompt_requests_reader_ko(b_prompt):
            errors.append("BLOCKED_READER_KO_IN_PROMPT")
    for left, right in zip(arm_a, arm_b, strict=False):
        if left.get("key") != right.get("key"):
            errors.append("BLOCKED_ARM_KEY_ORDER_MISMATCH")
            break
        if left.get("request", {}).get("generation_config") != right.get("request", {}).get("generation_config"):
            errors.append(f"BLOCKED_GENERATION_CONFIG_MISMATCH:{left.get('key')}")
            break
        if left.get("request", {}).get("model") != right.get("request", {}).get("model"):
            errors.append(f"BLOCKED_MODEL_MISMATCH:{left.get('key')}")
            break
    return sorted(set(errors)), sorted(set(warnings))


def validate_preflight_v2_2(
    selection: dict[str, Any],
    arm_a: list[dict[str, Any]],
    arm_b: list[dict[str, Any]],
    arm_c: list[dict[str, Any]],
    arm_d: list[dict[str, Any]],
) -> tuple[list[str], list[str]]:
    errors: list[str] = []
    warnings: list[str] = []
    items = selection.get("items") or []
    if len(items) != PLANNED_ITEMS:
        errors.append(f"BLOCKED_SELECTION_COUNT_{len(items)}")
    if len(arm_d) != PLANNED_ITEMS:
        errors.append(f"BLOCKED_ARM_D_REQUEST_COUNT_{len(arm_d)}")
    for row in arm_d:
        schema = response_schema_for_row(row)
        if not schema:
            errors.append(f"BLOCKED_MISSING_RESPONSE_SCHEMA:{row.get('key')}")
        elif "reader_ko" in (schema.get("properties") or {}):
            errors.append(f"BLOCKED_READER_KO_IN_RESPONSE_SCHEMA:{row.get('key')}")
        metadata = row.get("metadata") or {}
        if "source_text_hash" not in metadata:
            errors.append(f"BLOCKED_MISSING_SOURCE_TEXT_HASH_METADATA:{row.get('key')}")
        elif not metadata.get("source_text_hash"):
            warnings.append(f"source_text_hash_unavailable:{row.get('key')}")
        prompt = prompt_for_row(row)
        if NATURAL_KO_V2_2_MARKER not in prompt:
            errors.append(f"BLOCKED_ARM_D_MISSING_V2_2_MARKER:{row.get('key')}")
        if "natural_ko 작성 원칙:\n- 독자용 자연역입니다." in prompt:
            errors.append(f"BLOCKED_ARM_D_RETAINS_CONFLICTING_V1_NATURAL_KO_GUIDANCE:{row.get('key')}")
        if prompt_requests_reader_ko(prompt):
            errors.append(f"BLOCKED_READER_KO_IN_PROMPT:{row.get('key')}")
    selection_missing_hash = [item.get("stable_segment_key") for item in items if "source_text_hash" not in item]
    if selection_missing_hash:
        errors.append(f"BLOCKED_SELECTION_DROPPED_SOURCE_TEXT_HASH:{len(selection_missing_hash)}")
    for left, right in zip(arm_a, arm_d, strict=False):
        if left.get("key") != right.get("key"):
            errors.append("BLOCKED_ARM_KEY_ORDER_MISMATCH")
            break
        if left.get("request", {}).get("generation_config") != right.get("request", {}).get("generation_config"):
            errors.append(f"BLOCKED_GENERATION_CONFIG_MISMATCH:{left.get('key')}")
            break
        if left.get("request", {}).get("model") != right.get("request", {}).get("model"):
            errors.append(f"BLOCKED_MODEL_MISMATCH:{left.get('key')}")
            break
    for label, rows in (("B", arm_b), ("C", arm_c)):
        if rows and [row.get("key") for row in rows] != [row.get("key") for row in arm_d]:
            warnings.append(f"{label}_reference_key_order_differs_from_d")
    return sorted(set(errors)), sorted(set(warnings))


def validate_preflight_v2_1(
    selection: dict[str, Any],
    arm_a: list[dict[str, Any]],
    arm_b: list[dict[str, Any]],
    arm_c: list[dict[str, Any]],
) -> tuple[list[str], list[str]]:
    errors: list[str] = []
    warnings: list[str] = []
    items = selection.get("items") or []
    if len(items) != PLANNED_ITEMS:
        errors.append(f"BLOCKED_SELECTION_COUNT_{len(items)}")
    if len(arm_c) != PLANNED_ITEMS:
        errors.append(f"BLOCKED_ARM_C_REQUEST_COUNT_{len(arm_c)}")
    for row in arm_c:
        schema = response_schema_for_row(row)
        if not schema:
            errors.append(f"BLOCKED_MISSING_RESPONSE_SCHEMA:{row.get('key')}")
        elif "reader_ko" in (schema.get("properties") or {}):
            errors.append(f"BLOCKED_READER_KO_IN_RESPONSE_SCHEMA:{row.get('key')}")
        metadata = row.get("metadata") or {}
        if "source_text_hash" not in metadata:
            errors.append(f"BLOCKED_MISSING_SOURCE_TEXT_HASH_METADATA:{row.get('key')}")
        elif not metadata.get("source_text_hash"):
            warnings.append(f"source_text_hash_unavailable:{row.get('key')}")
    selection_missing_hash = [item.get("stable_segment_key") for item in items if "source_text_hash" not in item]
    if selection_missing_hash:
        errors.append(f"BLOCKED_SELECTION_DROPPED_SOURCE_TEXT_HASH:{len(selection_missing_hash)}")

    if arm_a and arm_c:
        a_prompt = prompt_for_row(arm_a[0])
        c_prompt = prompt_for_row(arm_c[0])
        if NATURAL_KO_V2_MARKER in a_prompt or NATURAL_KO_V2_1_MARKER in a_prompt:
            errors.append("BLOCKED_ARM_A_CONTAINS_CALIBRATION_MARKER")
        if NATURAL_KO_V2_1_MARKER not in c_prompt:
            errors.append("BLOCKED_ARM_C_MISSING_V2_1_MARKER")
        if "natural_ko 작성 원칙:\n- 독자용 자연역입니다." not in a_prompt:
            errors.append("BLOCKED_ARM_A_MISSING_ORIGINAL_NATURAL_KO_GUIDANCE")
        if "natural_ko 작성 원칙:\n- 독자용 자연역입니다." in c_prompt:
            errors.append("BLOCKED_ARM_C_RETAINS_CONFLICTING_V1_NATURAL_KO_GUIDANCE")
        if prompt_requests_reader_ko(a_prompt) or prompt_requests_reader_ko(c_prompt):
            errors.append("BLOCKED_READER_KO_IN_PROMPT")
    for left, right in zip(arm_a, arm_c, strict=False):
        if left.get("key") != right.get("key"):
            errors.append("BLOCKED_ARM_KEY_ORDER_MISMATCH")
            break
        if left.get("request", {}).get("generation_config") != right.get("request", {}).get("generation_config"):
            errors.append(f"BLOCKED_GENERATION_CONFIG_MISMATCH:{left.get('key')}")
            break
        if left.get("request", {}).get("model") != right.get("request", {}).get("model"):
            errors.append(f"BLOCKED_MODEL_MISMATCH:{left.get('key')}")
            break
    if arm_b:
        c_keys = [row.get("key") for row in arm_c]
        b_keys = [row.get("key") for row in arm_b]
        if b_keys and b_keys != c_keys:
            warnings.append("b_reference_key_order_differs_from_c")
    return sorted(set(errors)), sorted(set(warnings))


def response_schema_for_row(row: dict[str, Any]) -> dict[str, Any] | None:
    return row.get("request", {}).get("generation_config", {}).get("response_schema")


def prompt_for_row(row: dict[str, Any]) -> str:
    return row.get("request", {}).get("contents", [{}])[0].get("parts", [{}])[0].get("text", "")


def prompt_requests_reader_ko(prompt: str) -> bool:
    """Return True only for positive/additive reader_ko prompt instructions."""
    normalized = re.sub(r"[`*]", "", (prompt or "").lower())
    if "reader_ko" not in normalized:
        return False
    negative_patterns = (
        "do not add reader_ko",
        "dont add reader_ko",
        "do not create reader_ko",
        "do not include reader_ko",
        "do not output reader_ko",
        "reader_ko is not being added",
        "reader_ko_added = false",
        "reader_ko: not added",
        "no reader_ko",
    )
    positive_patterns = (
        r"\badd\s+(?:a\s+|the\s+)?reader_ko\b",
        r"\bcreate\s+(?:a\s+|the\s+)?reader_ko\b",
        r"\binclude\s+(?:a\s+|the\s+)?reader_ko\b",
        r"\boutput\s+(?:a\s+|the\s+)?reader_ko\b",
        r"\bfield\s+reader_ko\b",
        r"\breader_ko\s+field\b",
    )
    chunks = re.split(r"[\n.!?。！？]+", normalized)
    for chunk in chunks:
        if "reader_ko" not in chunk:
            continue
        if any(pattern in chunk for pattern in negative_patterns):
            continue
        if any(re.search(pattern, chunk) for pattern in positive_patterns):
            return True
    return False


def render_preflight_markdown(preflight: dict[str, Any]) -> str:
    return "\n".join(
        [
            "# natural_ko_v2 Smoke Preflight",
            "",
            f"- status: `{preflight['status']}`",
            f"- planned_items: `{preflight['planned_items']}`",
            f"- planned_provider_requests: `{preflight['planned_provider_requests']}`",
            f"- estimated_cost_usd: `{preflight['estimated_cost_usd']}`",
            f"- hard_cost_cap_usd: `{preflight['hard_cost_cap_usd']}`",
            f"- cap_passed_before_submit: `{preflight['cap_passed_before_submit']}`",
            f"- API calls made: `{preflight['api_llm_calls']}`",
            "",
            "Both arms use response_schema. A′ uses the production prompt v1 unchanged; B replaces the natural_ko guidance with the natural_ko_v2 calibration block.",
            "",
            f"Errors: `{preflight['errors']}`",
            f"Warnings: `{preflight['warnings']}`",
        ]
    ) + "\n"


def render_preflight_v2_1_markdown(preflight: dict[str, Any]) -> str:
    return "\n".join(
        [
            "# natural_ko_v2.1 C-arm Smoke Preflight",
            "",
            f"- status: `{preflight['status']}`",
            f"- planned_items: `{preflight['planned_items']}`",
            f"- planned_provider_requests: `{preflight['planned_provider_requests']}`",
            f"- estimated_cost_usd: `{preflight['estimated_cost_usd']}`",
            f"- hard_cost_cap_usd: `{preflight['hard_cost_cap_usd']}`",
            f"- cap_passed_before_submit: `{preflight['cap_passed_before_submit']}`",
            f"- A′ reused: `{preflight['a_prime_reused']}`",
            f"- B kept as reference: `{preflight['b_kept_reference']}`",
            f"- API calls made: `{preflight['api_llm_calls']}`",
            "",
            "C uses response_schema and the natural_ko_v2.1 guarded prompt. A′ is not resubmitted; existing A′ parsed output is reused for comparison.",
            "",
            f"Errors: `{preflight['errors']}`",
            f"Warnings: `{preflight['warnings']}`",
        ]
    ) + "\n"


def render_d_arm_submit_plan(preflight: dict[str, Any]) -> str:
    return "\n".join(
        [
            "# natural_ko_v2.2 D-arm Submit Plan",
            "",
            "Status: dry-run/preflight artifact. No provider call was made.",
            "",
            f"- preflight_status: `{preflight['status']}`",
            f"- planned_requests: `{preflight['planned_provider_requests']}`",
            f"- estimated_cost_usd: `{preflight['estimated_cost_usd']}`",
            f"- hard_cost_cap_usd: `{preflight['hard_cost_cap_usd']}`",
            f"- cap_passed_before_submit: `{preflight['cap_passed_before_submit']}`",
            "- response_schema: `true`",
            "- salvage_cascade_fallback: `true`",
            "- reader_ko_added: `false`",
            "",
            "Submit later only with:",
            "",
            "```bash",
            "./venv/bin/python -m backend.pali.scripts.run_natural_ko_calibration_smoke \\",
            "  --out data/reports/pali/natural_ko_calibration_v2_2 \\",
            "  --calibration-source-dir data/reports/pali/natural_ko_calibration_v1 \\",
            "  --submit-arm D \\",
            "  --pretty",
            "```",
        ]
    ) + "\n"


def render_no_api_executed_v2_2(preflight: dict[str, Any]) -> str:
    return "\n".join(
        [
            "# D-arm No API Executed",
            "",
            "No Gemini/API/Batch/provider/network call was made in this dry-run task.",
            "",
            f"- preflight_status: `{preflight['status']}`",
            f"- planned_requests: `{preflight['planned_provider_requests']}`",
            f"- estimated_cost_usd: `{preflight['estimated_cost_usd']}`",
            f"- cap_passed_before_submit: `{preflight['cap_passed_before_submit']}`",
            "- Step 6 started: `false`",
        ]
    ) + "\n"


def current_run_manifest(paths: NaturalKoSmokePaths) -> dict[str, Any]:
    manifest = default_run_manifest()
    if paths.run_manifest.exists():
        try:
            manifest.update(read_json(paths.run_manifest))
        except Exception:
            pass
    if paths.provider_status_arm_a.exists():
        status = read_json(paths.provider_status_arm_a)
        manifest["arm_a_prime_provider_batch_id"] = status.get("provider_batch_id")
    if paths.provider_status_arm_b.exists():
        status = read_json(paths.provider_status_arm_b)
        manifest["arm_b_v2_provider_batch_id"] = status.get("provider_batch_id")
    if paths.provider_status_arm_c.exists():
        status = read_json(paths.provider_status_arm_c)
        manifest["arm_c_v2_1_provider_batch_id"] = status.get("provider_batch_id")
    manifest["api_llm_calls_submitted"] = (
        (30 if manifest.get("arm_a_prime_provider_batch_id") else 0)
        + (30 if manifest.get("arm_b_v2_provider_batch_id") else 0)
        + (30 if manifest.get("arm_c_v2_1_provider_batch_id") else 0)
    )
    manifest["batch_submissions"] = (
        (1 if manifest.get("arm_a_prime_provider_batch_id") else 0)
        + (1 if manifest.get("arm_b_v2_provider_batch_id") else 0)
        + (1 if manifest.get("arm_c_v2_1_provider_batch_id") else 0)
    )
    return manifest


def submit_smoke(
    *,
    out_dir: Path,
    client: GeminiBatchRestClient,
    pretty: bool = False,
) -> dict[str, Any]:
    paths = smoke_paths(out_dir)
    preflight = run_preflight(out_dir=out_dir, pretty=pretty)
    if preflight["status"] != "PASS":
        raise NaturalKoSmokeBlocked("BLOCKED_PREFLIGHT_NOT_PASS", "Preflight must pass before submit.", preflight)
    if paths.provider_status_arm_a.exists() or paths.provider_status_arm_b.exists():
        raise NaturalKoSmokeBlocked("BLOCKED_ALREADY_SUBMITTED", "Provider status file already exists; refusing duplicate submit.")
    if Decimal(str(preflight["estimated_cost_usd"])) > HARD_CAP_USD:
        raise NaturalKoSmokeBlocked("BLOCKED_ESTIMATED_COST_OVER_CAP", "Estimated cost exceeds hard cap.", preflight)
    arm_a_status = submit_arm(paths.arm_a_jsonl, client=client, display_name="pali-natural-ko-calibration-a-prime", arm=ARM_A)
    write_json(paths.provider_status_arm_a, arm_a_status, pretty=pretty)
    arm_b_status = submit_arm(paths.arm_b_jsonl, client=client, display_name="pali-natural-ko-calibration-v2", arm=ARM_B)
    write_json(paths.provider_status_arm_b, arm_b_status, pretty=pretty)
    manifest = current_run_manifest(paths)
    manifest.update(
        {
            "submitted": True,
            "estimated_cost_usd": preflight["estimated_cost_usd"],
            "cap_passed_before_submit": True,
            "api_llm_calls_submitted": 60,
            "batch_submissions": 2,
        }
    )
    write_json(paths.run_manifest, manifest, pretty=pretty)
    return {"status": "SUBMITTED", "arm_a_prime": arm_a_status, "arm_b_v2": arm_b_status}


def submit_c_arm(
    *,
    out_dir: Path,
    client: GeminiBatchRestClient,
    pretty: bool = False,
) -> dict[str, Any]:
    paths = smoke_paths(out_dir)
    preflight = run_preflight_v2_1(out_dir=out_dir, pretty=pretty)
    if preflight["status"] != "PASS":
        raise NaturalKoSmokeBlocked("BLOCKED_PREFLIGHT_NOT_PASS", "C-arm preflight must pass before submit.", preflight)
    if paths.provider_status_arm_c.exists():
        raise NaturalKoSmokeBlocked("BLOCKED_ARM_C_ALREADY_SUBMITTED", "C-arm provider status already exists; refusing duplicate submit.")
    if Decimal(str(preflight["estimated_cost_usd"])) > HARD_CAP_USD:
        raise NaturalKoSmokeBlocked("BLOCKED_ESTIMATED_COST_OVER_CAP", "Estimated C-arm cost exceeds hard cap.", preflight)
    arm_c_status = submit_arm(paths.arm_c_jsonl, client=client, display_name="pali-natural-ko-calibration-v2-1", arm=ARM_C)
    write_json(paths.provider_status_arm_c, arm_c_status, pretty=pretty)
    manifest = current_run_manifest(paths)
    manifest.update(
        {
            "submitted_c_arm": True,
            "prompt_variant_v2_1_created": True,
            "c_arm_planned_requests": 30,
            "c_arm_api_llm_calls_submitted": 30,
            "c_arm_batch_submissions": 1,
            "a_prime_reused": True,
            "b_kept_reference": True,
            "estimated_cost_usd_c_arm": preflight["estimated_cost_usd"],
            "cap_passed_before_submit_c_arm": True,
            "api_llm_calls_submitted": 30,
            "batch_submissions": 1,
        }
    )
    write_json(paths.run_manifest, manifest, pretty=pretty)
    return {"status": "SUBMITTED_C_ARM", "arm_c_v2_1": arm_c_status}


def submit_d_arm(
    *,
    out_dir: Path,
    calibration_source_dir: Path = DEFAULT_OUT,
    client: GeminiBatchRestClient,
    pretty: bool = False,
) -> dict[str, Any]:
    paths = smoke_paths(out_dir)
    preflight = run_preflight_v2_2(out_dir=out_dir, calibration_source_dir=calibration_source_dir, pretty=pretty)
    if preflight["status"] != "PASS":
        raise NaturalKoSmokeBlocked("BLOCKED_PREFLIGHT_NOT_PASS", "D-arm preflight must pass before submit.", preflight)
    if paths.provider_status_arm_d.exists():
        raise NaturalKoSmokeBlocked("BLOCKED_ARM_D_ALREADY_SUBMITTED", "D-arm provider status already exists; refusing duplicate submit.")
    if Decimal(str(preflight["estimated_cost_usd"])) > HARD_CAP_USD:
        raise NaturalKoSmokeBlocked("BLOCKED_ESTIMATED_COST_OVER_CAP", "Estimated D-arm cost exceeds hard cap.", preflight)
    arm_d_status = submit_arm(paths.arm_d_jsonl, client=client, display_name="pali-natural-ko-calibration-v2-2", arm=ARM_D)
    write_json(paths.provider_status_arm_d, arm_d_status, pretty=pretty)
    manifest = read_json(paths.arm_d_run_manifest) if paths.arm_d_run_manifest.exists() else {}
    manifest.update(
        {
            "provider_call_made": True,
            "api_llm_calls": 30,
            "network_calls": 1,
            "batch_submissions": 1,
            "d_arm_provider_batch_id": arm_d_status.get("provider_batch_id"),
            "request_count": arm_d_status.get("request_count"),
            "response_schema": True,
            "salvage_cascade_fallback": True,
            "reader_ko_added": False,
            "production_prompt_changed": False,
            "step5_selection_modified": False,
            "step6_started": False,
        }
    )
    write_json(paths.arm_d_run_manifest, manifest, pretty=pretty)
    return {"status": "SUBMITTED_D_ARM", "arm_d_v2_2": arm_d_status}


def submit_arm(path: Path, *, client: GeminiBatchRestClient, display_name: str, arm: str) -> dict[str, Any]:
    provider_lines = read_jsonl(path)
    requests = [build_inline_request_from_provider_line(line) for line in provider_lines]
    response = client.create_inline_batch(model=DEFAULT_MODEL, requests=requests, display_name=display_name)
    return {
        "arm": arm,
        "status": "submitted",
        "provider_batch_id": extract_batch_name(response),
        "request_count": len(provider_lines),
        "provider_status": status_snapshot(response),
    }


def poll_or_fetch(
    *,
    out_dir: Path,
    client: GeminiBatchRestClient,
    fetch: bool,
    pretty: bool = False,
) -> dict[str, Any]:
    paths = smoke_paths(out_dir)
    outputs: dict[str, Any] = {"status": "FETCHED" if fetch else "POLLED"}
    for arm_name, status_path, raw_path in (
        (ARM_A, paths.provider_status_arm_a, paths.arm_a_raw),
        (ARM_B, paths.provider_status_arm_b, paths.arm_b_raw),
        (ARM_C, paths.provider_status_arm_c, paths.arm_c_raw),
        (ARM_D, paths.provider_status_arm_d, paths.arm_d_raw),
    ):
        if not status_path.exists():
            outputs[arm_name] = {"status": "missing_provider_status"}
            continue
        existing = read_json(status_path)
        provider_id = existing.get("provider_batch_id")
        if not provider_id:
            outputs[arm_name] = {"status": "missing_provider_batch_id"}
            continue
        status = client.get_batch(provider_id)
        payload = {
            "arm": arm_name,
            "status": "polled",
            "provider_batch_id": provider_id,
            "provider_status": status_snapshot(status),
            "raw_provider_status": status,
        }
        write_json(status_path, payload, pretty=pretty)
        if fetch:
            rows = extract_inline_result_lines(status)
            write_jsonl(raw_path, rows)
            outputs[arm_name] = {"provider_batch_id": provider_id, "raw_result_count": len(rows)}
        else:
            outputs[arm_name] = {"provider_batch_id": provider_id, "provider_status": payload["provider_status"]}
    return outputs


def parse_smoke(
    *,
    out_dir: Path,
    calibration_source_dir: Path = DEFAULT_OUT,
    price_profile_path: Path = DEFAULT_PRICE_PROFILE_PATH,
    price_profile_id: str = DEFAULT_PRICE_PROFILE_ID,
    pretty: bool = False,
) -> dict[str, Any]:
    paths = smoke_paths(out_dir)
    source_paths = smoke_paths(calibration_source_dir)
    selection_path = paths.selection if paths.selection.exists() else source_paths.selection
    selection = read_json(selection_path)
    price_profile, _ = load_price_profile(price_profile_path, price_profile_id)
    if paths.arm_d_raw.exists() and paths.arm_d_jsonl.exists() and not paths.arm_a_raw.exists():
        arm_d = parse_arm(
            raw_lines=read_jsonl(paths.arm_d_raw),
            provider_lines=read_jsonl(paths.arm_d_jsonl),
            selection=selection,
            price_profile=price_profile,
            arm=ARM_D,
        )
        write_json(paths.arm_d_parsed, arm_d, pretty=pretty)
        summary = {"schema_version": "natural_ko_v2_2_d_arm_parse_summary_v1", "arm_d_v2_2": arm_metrics(arm_d)}
        write_json(paths.arm_d_summary_json, summary, pretty=pretty)
        paths.arm_d_summary_md.write_text(render_d_arm_summary_markdown(summary), encoding="utf-8")
        return {"status": "PARSED_D_ARM", "arm_d_v2_2_items": len(arm_d["items"])}
    arm_a = parse_arm(
        raw_lines=read_jsonl(paths.arm_a_raw),
        provider_lines=read_jsonl(paths.arm_a_jsonl),
        selection=selection,
        price_profile=price_profile,
        arm=ARM_A,
    )
    arm_b = parse_arm(
        raw_lines=read_jsonl(paths.arm_b_raw),
        provider_lines=read_jsonl(paths.arm_b_jsonl),
        selection=selection,
        price_profile=price_profile,
        arm=ARM_B,
    )
    arm_c = None
    if paths.arm_c_raw.exists() and paths.arm_c_jsonl.exists():
        arm_c = parse_arm(
            raw_lines=read_jsonl(paths.arm_c_raw),
            provider_lines=read_jsonl(paths.arm_c_jsonl),
            selection=selection,
            price_profile=price_profile,
            arm=ARM_C,
        )
    write_json(paths.arm_a_parsed, arm_a, pretty=pretty)
    write_json(paths.arm_b_parsed, arm_b, pretty=pretty)
    if arm_c is not None:
        write_json(paths.arm_c_parsed, arm_c, pretty=pretty)
    summary = {
        "schema_version": "natural_ko_v2_parse_summary_v1",
        "arm_a_prime": arm_metrics(arm_a),
        "arm_b_v2": arm_metrics(arm_b),
    }
    if arm_c is not None:
        summary["arm_c_v2_1"] = arm_metrics(arm_c)
    write_json(paths.parse_summary, summary, pretty=pretty)
    return {
        "status": "PARSED",
        "arm_a_prime_items": len(arm_a["items"]),
        "arm_b_v2_items": len(arm_b["items"]),
        "arm_c_v2_1_items": len(arm_c["items"]) if arm_c is not None else None,
    }


def parse_arm(
    *,
    raw_lines: list[dict[str, Any]],
    provider_lines: list[dict[str, Any]],
    selection: dict[str, Any],
    price_profile: PriceProfile,
    arm: str,
) -> dict[str, Any]:
    manifest_items = [
        {
            "stable_segment_key": item["stable_segment_key"],
            "source_text_hash": item.get("source_text_hash"),
            "source_path": item.get("source_path"),
            "text_layer": item.get("text_layer"),
            "chunk_type": item.get("chunk_type"),
            "length_bucket": item.get("length_bucket"),
            "calibration_role": item.get("calibration_role"),
            "selection_reason": item.get("selection_reason"),
        }
        for item in selection.get("items") or []
    ]
    parsed = parse_batch_results(
        raw_lines=raw_lines,
        provider_lines=provider_lines,
        manifest={"items": manifest_items},
        price_profile=price_profile,
    )
    raw_by_key = {extract_result_key(line): line for line in raw_lines if extract_result_key(line)}
    selection_by_key = {item["stable_segment_key"]: item for item in manifest_items}
    for item in parsed.get("items") or []:
        key = item.get("stable_segment_key")
        raw_line = raw_by_key.get(key) or {}
        response = extract_generate_content_response(raw_line)
        output_text = extract_model_output_text(response)
        finish_reason = extract_finish_reason(response)
        attempt = parse_output_cascade(output_text or "", finish_reason=finish_reason)
        item["arm"] = arm
        item["calibration_role"] = selection_by_key.get(key, {}).get("calibration_role")
        item["selection_reason"] = selection_by_key.get(key, {}).get("selection_reason")
        item["parse_method"] = attempt.method
        item["recovered_via"] = "none" if attempt.method in {"strict_json", "failed"} else attempt.method
        item["parser_flags"] = attempt.flags
        item["salvage_applied"] = attempt.method in {"raw_decode", "stack_reclose"}
        item["completeness_gate_passed"] = attempt.completeness_gate_passed
        item["provider_error"] = item.get("error_message") if item.get("status") == "failed" else None
        if attempt.ok and attempt.obj is not None:
            apply_successful_parse(item, attempt.obj)
        if not output_text and item.get("status") == "missing_result":
            item["parse_method"] = "failed"
    return {"schema_version": "natural_ko_v2_arm_parsed_v1", "arm": arm, "items": parsed.get("items") or []}


def arm_metrics(parsed: dict[str, Any]) -> dict[str, Any]:
    items = parsed.get("items") or []
    total = len(items)
    method_counts = Counter(str(item.get("parse_method") or "unknown") for item in items)
    schema_valid = sum(1 for item in items if item.get("schema_valid") is True)
    empty_translation = sum(1 for item in items if not str(item.get("literal_ko") or "").strip() or not str(item.get("natural_ko") or "").strip())
    truncation = sum(1 for item in items if "finish_reason_max_tokens" in (item.get("parser_flags") or []))
    provider_errors = sum(1 for item in items if item.get("provider_error") or item.get("status") == "failed")
    usage = {
        "input_tokens": sum(int(item.get("prompt_token_count") or 0) for item in items),
        "output_tokens": sum(int(item.get("candidates_token_count") or 0) for item in items),
        "thinking_tokens": sum(int(item.get("thoughts_token_count") or 0) for item in items),
    }
    usage["total_tokens"] = usage["input_tokens"] + usage["output_tokens"] + usage["thinking_tokens"]
    cost = sum((Decimal(str(item.get("actual_cost_usd") or "0")) for item in items), Decimal("0"))
    return {
        "total": total,
        "strict_parse_rate": decimal_rate(method_counts.get("strict_json", 0), total),
        "salvage_needed_rate": decimal_rate(method_counts.get("raw_decode", 0) + method_counts.get("stack_reclose", 0), total),
        "schema_valid_rate": decimal_rate(schema_valid, total),
        "empty_translation_rate": decimal_rate(empty_translation, total),
        "truncation_rate": decimal_rate(truncation, total),
        "provider_error_rate": decimal_rate(provider_errors, total),
        "salvage_tier_counts": dict(sorted(method_counts.items())),
        "cost_actual_usd": quantize(cost),
        **usage,
    }


def compare_smoke(*, out_dir: Path, pretty: bool = False) -> dict[str, Any]:
    paths = smoke_paths(out_dir)
    arm_a = read_json(paths.arm_a_parsed)
    arm_b = read_json(paths.arm_b_parsed)
    comparison = compare_parsed_arms(arm_a, arm_b)
    write_json(paths.comparison_json, comparison, pretty=pretty)
    paths.comparison_md.write_text(render_comparison_markdown(comparison), encoding="utf-8")
    paths.human_review_sheet.write_text(render_human_review_sheet(comparison), encoding="utf-8")
    return {"status": "COMPARED", "paired_count": comparison["paired_count"], "warnings": comparison["warnings"]}


def compare_v2_1_smoke(*, out_dir: Path, pretty: bool = False) -> dict[str, Any]:
    paths = smoke_paths(out_dir)
    arm_a = read_json(paths.arm_a_parsed)
    arm_c = read_json(paths.arm_c_parsed)
    arm_b = read_json(paths.arm_b_parsed) if paths.arm_b_parsed.exists() else None
    comparison = compare_v2_1_arms(arm_a, arm_c, arm_b)
    write_json(paths.comparison_v2_1_json, comparison, pretty=pretty)
    paths.comparison_v2_1_md.write_text(render_v2_1_comparison_markdown(comparison), encoding="utf-8")
    paths.human_review_sheet.write_text(render_human_review_sheet_v2_1(comparison), encoding="utf-8")
    paths.step6_handoff_v2_1.write_text(render_step6_handoff_v2_1(comparison), encoding="utf-8")
    return {"status": "COMPARED_V2_1", "paired_count": comparison["paired_count"], "warnings": comparison["warnings"]}


def compare_v2_2_smoke(*, out_dir: Path, calibration_source_dir: Path = DEFAULT_OUT, pretty: bool = False) -> dict[str, Any]:
    paths = smoke_paths(out_dir)
    source_paths = smoke_paths(calibration_source_dir)
    arm_d = read_json(paths.arm_d_parsed)
    arm_a = read_json(source_paths.arm_a_parsed) if source_paths.arm_a_parsed.exists() else None
    arm_b = read_json(source_paths.arm_b_parsed) if source_paths.arm_b_parsed.exists() else None
    arm_c = read_json(source_paths.arm_c_parsed) if source_paths.arm_c_parsed.exists() else None
    comparison = compare_v2_2_d_arm(arm_d, arm_a, arm_b, arm_c)
    write_json(paths.comparison_v2_2_json, comparison, pretty=pretty)
    paths.comparison_v2_2_md.write_text(render_d_arm_comparison_markdown(comparison), encoding="utf-8")
    paths.d_manual_review_sheet.write_text(render_d_arm_manual_review_sheet(comparison), encoding="utf-8")
    paths.d_final_recommendation_md.write_text(render_d_arm_final_recommendation(comparison), encoding="utf-8")
    return {
        "status": "COMPARED_D_ARM",
        "d_items": comparison["d_item_count"],
        "objective_gate_status": comparison["objective_gate_status"],
    }


def compare_parsed_arms(arm_a: dict[str, Any], arm_b: dict[str, Any]) -> dict[str, Any]:
    a_by_key = {item.get("stable_segment_key"): item for item in arm_a.get("items") or []}
    b_by_key = {item.get("stable_segment_key"): item for item in arm_b.get("items") or []}
    paired_keys = sorted(set(a_by_key) & set(b_by_key))
    missing_in_a = sorted(set(b_by_key) - set(a_by_key))
    missing_in_b = sorted(set(a_by_key) - set(b_by_key))
    pair_checks = []
    role_checks: dict[str, list[dict[str, Any]]] = defaultdict(list)
    warnings: list[str] = []
    for key in paired_keys:
        check = pair_comparison(a_by_key[key], b_by_key[key])
        pair_checks.append(check)
        role_checks[str(check.get("calibration_role") or "unknown")].append(check)
        warnings.extend(check.get("warnings") or [])
    if len(paired_keys) < PLANNED_ITEMS:
        warnings.append("paired_count_less_than_30")
    comparison = {
        "schema_version": "natural_ko_v2_controlled_comparison_v1",
        "paired_count": len(paired_keys),
        "missing_in_a_prime": missing_in_a,
        "missing_in_b_v2": missing_in_b,
        "arm_a_prime_metrics": arm_metrics(arm_a),
        "arm_b_v2_metrics": arm_metrics(arm_b),
        "readability": {
            "arm_a_prime": readability_summary(list(a_by_key.values())),
            "arm_b_v2": readability_summary(list(b_by_key.values())),
            "by_layer": {
                "arm_a_prime": readability_by_field(list(a_by_key.values()), "text_layer"),
                "arm_b_v2": readability_by_field(list(b_by_key.values()), "text_layer"),
            },
        },
        "delta_metrics": delta_metrics(pair_checks),
        "role_delta_metrics": {role: delta_metrics(checks) for role, checks in sorted(role_checks.items())},
        "pair_checks": pair_checks,
        "warnings": sorted(set(warnings)),
        "recommendation_status": "pending_operator_readability_review",
        "gold_accuracy_available": False,
    }
    return comparison


def compare_v2_2_d_arm(
    arm_d: dict[str, Any],
    arm_a: dict[str, Any] | None,
    arm_b: dict[str, Any] | None,
    arm_c: dict[str, Any] | None,
) -> dict[str, Any]:
    d_items = arm_d.get("items") or []
    d_by_key = {item.get("stable_segment_key"): item for item in d_items}
    refs = {
        "A_prime": {item.get("stable_segment_key"): item for item in (arm_a or {}).get("items") or []},
        "B_v2": {item.get("stable_segment_key"): item for item in (arm_b or {}).get("items") or []},
        "C_v2_1": {item.get("stable_segment_key"): item for item in (arm_c or {}).get("items") or []},
    }
    gate_summary = summarize_d_arm_gates(d_items)
    rows = []
    for key, item in sorted(d_by_key.items()):
        gates = evaluate_d_arm_item(item)
        rows.append(
            {
                "stable_segment_key": key,
                "metadata": {
                    "text_layer": item.get("text_layer"),
                    "chunk_type": item.get("chunk_type"),
                    "length_bucket": item.get("length_bucket"),
                },
                "previous_best": "pending_operator_review",
                "d_literal_verdict": "pending_scholar_review",
                "d_natural_verdict": "pending_operator_review",
                "readability_verdict": "pending_operator_review",
                "fidelity_verdict": "pending_scholar_review",
                "insertion_risk": "unsupported_insertion" if gates["unsupported_insertion"] else "none_detected_by_objective_gate",
                "omission_risk": "known_content_omission" if gates["known_content_omission"] else "general_omission_pending_scholar_review",
                "negation_risk": "negation_scope_risk" if gates["negation_scope_risk"] else "pending_scholar_review",
                "glossary_compliance": "glossary_violation" if gates["glossary_violation"] else "ok_for_locked_terms",
                "bracket_violation": gates["bracket_violation"],
                "final_item_verdict": "pending_operator_and_scholar_review",
                "objective_gates": gates,
                "d_item": item,
                "references_present": {label: key in mapping for label, mapping in refs.items()},
            }
        )
    objective_pass = (
        len(d_items) == 30
        and arm_metrics(arm_d)["schema_valid_rate"] == "1.000000"
        and gate_summary["bracket_violations"] == 0
        and gate_summary["unsupported_insertions"] == 0
        and gate_summary["known_content_omissions"] == 0
        and gate_summary["glossary_violations"] == 0
    )
    return {
        "schema_version": "natural_ko_v2_2_d_arm_comparison_v1",
        "d_item_count": len(d_items),
        "arm_d_metrics": arm_metrics(arm_d),
        "objective_gate_status": "PASS" if objective_pass else "FAIL",
        "objective_gate_summary": gate_summary,
        "manual_gates": {
            "readability_gate": "pending_operator_review",
            "fidelity_gate": "pending_scholar_review",
            "general_content_omission_gate": "pending_scholar_review",
            "negation_scope_correctness_gate": "pending_scholar_review",
        },
        "comparison_rows": rows,
        "recommendation": "pending_operator_and_scholar_review",
        "step6_started": False,
        "gold_accuracy_available": False,
        "reader_ko_added": False,
    }


def compare_v2_1_arms(
    arm_a: dict[str, Any],
    arm_c: dict[str, Any],
    arm_b: dict[str, Any] | None = None,
) -> dict[str, Any]:
    a_by_key = {item.get("stable_segment_key"): item for item in arm_a.get("items") or []}
    c_by_key = {item.get("stable_segment_key"): item for item in arm_c.get("items") or []}
    b_by_key = {item.get("stable_segment_key"): item for item in (arm_b or {}).get("items") or []}
    paired_keys = sorted(set(a_by_key) & set(c_by_key))
    missing_in_a = sorted(set(c_by_key) - set(a_by_key))
    missing_in_c = sorted(set(a_by_key) - set(c_by_key))
    pair_checks = []
    warnings: list[str] = []
    role_checks: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for key in paired_keys:
        check = pair_comparison_v2_1(a_by_key[key], c_by_key[key], b_by_key.get(key))
        pair_checks.append(check)
        role_checks[str(check.get("calibration_role") or "unknown")].append(check)
        warnings.extend(check.get("warnings") or [])
    if len(paired_keys) < PLANNED_ITEMS:
        warnings.append("paired_count_less_than_30")
    b_pair_checks = [check for check in pair_checks if check.get("b_reference") is not None]
    comparison = {
        "schema_version": "natural_ko_v2_1_c_arm_comparison_v1",
        "paired_count": len(paired_keys),
        "missing_in_a_prime": missing_in_a,
        "missing_in_c_v2_1": missing_in_c,
        "b_reference_paired_count": len(b_pair_checks),
        "arm_a_prime_metrics": arm_metrics(arm_a),
        "arm_c_v2_1_metrics": arm_metrics(arm_c),
        "arm_b_v2_reference_metrics": arm_metrics(arm_b) if arm_b else None,
        "readability": {
            "arm_a_prime": readability_summary(list(a_by_key.values())),
            "arm_c_v2_1": readability_summary(list(c_by_key.values())),
            "arm_b_v2_reference": readability_summary(list(b_by_key.values())) if arm_b else None,
        },
        "delta_metrics_c_minus_a": delta_metrics_for_label(pair_checks, "c_minus_a_readability_deltas"),
        "delta_metrics_c_minus_b": delta_metrics_for_label(b_pair_checks, "c_minus_b_readability_deltas"),
        "role_delta_metrics_c_minus_a": {
            role: delta_metrics_for_label(checks, "c_minus_a_readability_deltas")
            for role, checks in sorted(role_checks.items())
        },
        "overreach_summary": overreach_summary(pair_checks),
        "pair_checks": pair_checks,
        "must_inspect": must_inspect_items(pair_checks),
        "warnings": sorted(set(warnings)),
        "recommendation_status": "pending_operator_and_scholar_review",
        "gold_accuracy_available": False,
        "reader_ko_added": False,
    }
    return comparison


def pair_comparison_v2_1(a: dict[str, Any], c: dict[str, Any], b: dict[str, Any] | None = None) -> dict[str, Any]:
    a_metrics = readability_metrics(a)
    c_metrics = readability_metrics(c)
    b_metrics = readability_metrics(b) if b else None
    warnings: list[str] = []
    fidelity = fidelity_support(a, c)
    structural = structural_literal_and_overreach_flags(a, c)
    warnings.extend(fidelity["warnings"])
    warnings.extend(flag for flag, value in structural.items() if isinstance(value, bool) and value)
    if a.get("calibration_role") == "convergence_control":
        similarity_drop = Decimal(str(a_metrics["literal_natural_similarity"])) - Decimal(str(c_metrics["literal_natural_similarity"]))
        if similarity_drop > Decimal("0.15") or fidelity["warnings"]:
            warnings.append("control_forced_divergence_warning")
    c_minus_b = None
    if b_metrics:
        c_minus_b = readability_delta(c_metrics, b_metrics)
    return {
        "stable_segment_key": a.get("stable_segment_key"),
        "source_path": a.get("source_path"),
        "source_text_hash_aligned": a.get("source_text_hash") == c.get("source_text_hash"),
        "source_key_aligned": a.get("stable_segment_key") == c.get("stable_segment_key"),
        "text_layer": a.get("text_layer"),
        "chunk_type": a.get("chunk_type"),
        "length_bucket": a.get("length_bucket"),
        "calibration_role": a.get("calibration_role"),
        "a_prime_readability": a_metrics,
        "b_reference_readability": b_metrics,
        "c_v2_1_readability": c_metrics,
        "c_minus_a_readability_deltas": readability_delta(c_metrics, a_metrics),
        "c_minus_b_readability_deltas": c_minus_b,
        "fidelity_support": fidelity,
        "literal_structural_checks": structural,
        "warnings": sorted(set(warnings)),
        "a_prime": a,
        "b_reference": b,
        "c_v2_1": c,
    }


def readability_delta(newer: dict[str, Any], older: dict[str, Any]) -> dict[str, Any]:
    return {
        "literal_natural_similarity": round(newer["literal_natural_similarity"] - older["literal_natural_similarity"], 6),
        "natural_pali_parentheses_count": newer["natural_pali_parentheses_count"] - older["natural_pali_parentheses_count"],
        "natural_pali_token_count": newer["natural_pali_token_count"] - older["natural_pali_token_count"],
        "natural_lemma_quote_count": newer["natural_lemma_quote_count"] - older["natural_lemma_quote_count"],
        "natural_formulaic_gloss_count": newer["natural_formulaic_gloss_count"] - older["natural_formulaic_gloss_count"],
        "natural_raneun_geot_count": newer["natural_raneun_geot_count"] - older["natural_raneun_geot_count"],
        "natural_avg_sentence_length_chars": round(
            newer["natural_avg_sentence_length_chars"] - older["natural_avg_sentence_length_chars"], 6
        ),
        "natural_sentence_count": newer["natural_sentence_count"] - older["natural_sentence_count"],
    }


def structural_literal_and_overreach_flags(a: dict[str, Any], c: dict[str, Any]) -> dict[str, Any]:
    a_literal = str(a.get("literal_ko") or "")
    c_literal = str(c.get("literal_ko") or "")
    a_nat = str(a.get("natural_ko") or "")
    c_nat = str(c.get("natural_ko") or "")
    literal_markers = ("라는 것은", "라는 말은", "라는 뜻", "뜻한다", "가리킨다")
    causal_markers = ("때문에", "이처럼", "선업", "청정하기 때문에", "인과", "업이 청정")
    embellishment_markers = ("기꺼이", "흔쾌히", "말을 쉬게", "쉬게 한 뒤", "잠시 쉬고", "즐겁게")
    ambiguous_overcommit_markers = ("확실히", "분명히", "단정할 수", "틀림없이")
    return {
        "literal_lemma_gloss_marker_retained": any(marker in c_literal for marker in literal_markers)
        or not any(marker in a_literal for marker in literal_markers),
        "literal_pali_parenthetical_count_delta": c_literal.count("(") - a_literal.count("("),
        "literal_narrative_embellishment_flag": any(marker in c_literal and marker not in a_literal for marker in embellishment_markers),
        "added_causal_or_doctrinal_phrase_flag": any(marker in c_nat and marker not in a_nat for marker in causal_markers),
        "ambiguous_verb_overcommit_flag": any(marker in c_nat and marker not in a_nat for marker in ambiguous_overcommit_markers),
    }


def delta_metrics_for_label(pair_checks: list[dict[str, Any]], label: str) -> dict[str, Any]:
    usable = [item for item in pair_checks if item.get(label)]
    if not usable:
        return delta_metrics([])
    deltas = [item[label] for item in usable]
    return {
        "avg_similarity_delta_b_minus_a": avg([d["literal_natural_similarity"] for d in deltas]),
        "near_literal_095_delta_b_minus_a": 0,
        "same_as_literal_delta_b_minus_a": 0,
        "pali_parentheses_delta_b_minus_a": sum(d["natural_pali_parentheses_count"] for d in deltas),
        "lemma_quote_delta_b_minus_a": sum(d["natural_lemma_quote_count"] for d in deltas),
        "formulaic_gloss_delta_b_minus_a": sum(d["natural_formulaic_gloss_count"] for d in deltas),
        "raneun_geot_delta_b_minus_a": sum(d["natural_raneun_geot_count"] for d in deltas),
        "avg_sentence_length_delta_b_minus_a": avg([d["natural_avg_sentence_length_chars"] for d in deltas]),
        "sentence_count_delta_b_minus_a": sum(d["natural_sentence_count"] for d in deltas),
    }


def overreach_summary(pair_checks: list[dict[str, Any]]) -> dict[str, int]:
    return {
        "literal_narrative_embellishment_flag": sum(
            bool(item["literal_structural_checks"].get("literal_narrative_embellishment_flag")) for item in pair_checks
        ),
        "added_causal_or_doctrinal_phrase_flag": sum(
            bool(item["literal_structural_checks"].get("added_causal_or_doctrinal_phrase_flag")) for item in pair_checks
        ),
        "ambiguous_verb_overcommit_flag": sum(
            bool(item["literal_structural_checks"].get("ambiguous_verb_overcommit_flag")) for item in pair_checks
        ),
        "possible_added_claim_warning": sum(
            bool(item["fidelity_support"].get("possible_added_claim_warning")) for item in pair_checks
        ),
        "control_forced_divergence_warning": sum(
            "control_forced_divergence_warning" in (item.get("warnings") or []) for item in pair_checks
        ),
    }


def must_inspect_items(pair_checks: list[dict[str, Any]]) -> list[dict[str, Any]]:
    fragments = (
        "s0514m.mul:88650af1ca41",
        "s0513a3.att:8cd09caf90eb",
        "s0508a1.att",
        "s0515m.mul",
        "vin01t2.tik",
        "e0104n.att",
    )
    output = []
    for item in pair_checks:
        key = str(item.get("stable_segment_key") or "")
        if any(fragment in key for fragment in fragments):
            output.append(
                {
                    "stable_segment_key": key,
                    "warnings": item.get("warnings") or [],
                    "literal_structural_checks": item.get("literal_structural_checks"),
                    "c_minus_a_readability_deltas": item.get("c_minus_a_readability_deltas"),
                    "c_minus_b_readability_deltas": item.get("c_minus_b_readability_deltas"),
                }
            )
    return output


def pair_comparison(a: dict[str, Any], b: dict[str, Any]) -> dict[str, Any]:
    a_metrics = readability_metrics(a)
    b_metrics = readability_metrics(b)
    literal_similarity = similarity(a.get("literal_ko") or "", b.get("literal_ko") or "")
    literal_ratio = length_ratio(b.get("literal_ko"), a.get("literal_ko"))
    warnings: list[str] = []
    if literal_similarity < 0.92:
        warnings.append("literal_similarity_drift_warning")
    if literal_ratio < Decimal("0.80") or literal_ratio > Decimal("1.25"):
        warnings.append("literal_length_ratio_drift_warning")
    fidelity = fidelity_support(a, b)
    warnings.extend(fidelity["warnings"])
    if a.get("calibration_role") == "convergence_control":
        similarity_drop = Decimal(str(a_metrics["literal_natural_similarity"])) - Decimal(str(b_metrics["literal_natural_similarity"]))
        if similarity_drop > Decimal("0.15") or fidelity["warnings"]:
            warnings.append("control_forced_divergence_warning")
    return {
        "stable_segment_key": a.get("stable_segment_key"),
        "source_path": a.get("source_path"),
        "source_text_hash_aligned": a.get("source_text_hash") == b.get("source_text_hash"),
        "source_key_aligned": a.get("stable_segment_key") == b.get("stable_segment_key"),
        "text_layer": a.get("text_layer"),
        "chunk_type": a.get("chunk_type"),
        "length_bucket": a.get("length_bucket"),
        "calibration_role": a.get("calibration_role"),
        "a_prime_readability": a_metrics,
        "b_v2_readability": b_metrics,
        "literal_similarity_a_prime_to_b": f"{literal_similarity:.6f}",
        "literal_length_ratio_b_to_a": str(literal_ratio.quantize(Decimal("0.001"))),
        "literal_terms_drift_warning": term_set(a) != term_set(b),
        "readability_deltas_b_minus_a": {
            "literal_natural_similarity": round(b_metrics["literal_natural_similarity"] - a_metrics["literal_natural_similarity"], 6),
            "natural_pali_parentheses_count": b_metrics["natural_pali_parentheses_count"] - a_metrics["natural_pali_parentheses_count"],
            "natural_pali_token_count": b_metrics["natural_pali_token_count"] - a_metrics["natural_pali_token_count"],
            "natural_lemma_quote_count": b_metrics["natural_lemma_quote_count"] - a_metrics["natural_lemma_quote_count"],
            "natural_formulaic_gloss_count": b_metrics["natural_formulaic_gloss_count"] - a_metrics["natural_formulaic_gloss_count"],
            "natural_raneun_geot_count": b_metrics["natural_raneun_geot_count"] - a_metrics["natural_raneun_geot_count"],
            "natural_avg_sentence_length_chars": round(
                b_metrics["natural_avg_sentence_length_chars"] - a_metrics["natural_avg_sentence_length_chars"], 6
            ),
            "natural_sentence_count": b_metrics["natural_sentence_count"] - a_metrics["natural_sentence_count"],
        },
        "fidelity_support": fidelity,
        "warnings": sorted(set(warnings)),
        "a_prime": a,
        "b_v2": b,
    }


def similarity(a: str, b: str) -> float:
    from backend.pali.translation.natural_ko_readability import string_similarity

    return string_similarity(a, b)


def length_ratio(numerator: Any, denominator: Any) -> Decimal:
    den = max(1, len(str(denominator or "")))
    return Decimal(len(str(numerator or ""))) / Decimal(den)


def term_set(item: dict[str, Any]) -> set[str]:
    return {str(term.get("pali") or "").strip() for term in item.get("terms") or [] if str(term.get("pali") or "").strip()}


def fidelity_support(a: dict[str, Any], b: dict[str, Any]) -> dict[str, Any]:
    warnings: list[str] = []
    a_nat = str(a.get("natural_ko") or "")
    b_nat = str(b.get("natural_ko") or "")
    natural_empty = not b_nat.strip()
    ratio = length_ratio(b_nat, a_nat)
    if natural_empty:
        warnings.append("natural_empty")
    if ratio < Decimal("0.60"):
        warnings.append("possible_dropped_content_warning")
    if ratio > Decimal("1.80"):
        warnings.append("possible_added_claim_warning")
    terms_delta = len(b.get("terms") or []) - len(a.get("terms") or [])
    if terms_delta <= -3:
        warnings.append("possible_dropped_content_warning")
    preserved = sorted(term_set(a) & term_set(b))
    return {
        "natural_empty": natural_empty,
        "natural_too_short": ratio < Decimal("0.60"),
        "natural_too_long": ratio > Decimal("1.80"),
        "terms_count_delta": terms_delta,
        "grammar_notes_count_delta": len(b.get("grammar_notes") or []) - len(a.get("grammar_notes") or []),
        "doctrinal_notes_count_delta": len(b.get("doctrinal_notes") or []) - len(a.get("doctrinal_notes") or []),
        "uncertainties_count_delta": len(b.get("uncertainties") or []) - len(a.get("uncertainties") or []),
        "quality_flags_count_delta": len(b.get("quality_flags") or []) - len(a.get("quality_flags") or []),
        "pali_terms_in_terms_preserved": preserved,
        "possible_added_claim_warning": "possible_added_claim_warning" in warnings,
        "possible_dropped_content_warning": "possible_dropped_content_warning" in warnings,
        "warnings": sorted(set(warnings)),
    }


def readability_summary(items: list[dict[str, Any]]) -> dict[str, Any]:
    if not items:
        return {"total": 0}
    metrics = [readability_metrics(item) for item in items]
    return {
        "total": len(items),
        "avg_literal_natural_similarity": avg([m["literal_natural_similarity"] for m in metrics]),
        "natural_pali_parentheses_count": sum(m["natural_pali_parentheses_count"] for m in metrics),
        "natural_pali_token_count": sum(m["natural_pali_token_count"] for m in metrics),
        "natural_lemma_quote_count": sum(m["natural_lemma_quote_count"] for m in metrics),
        "natural_formulaic_gloss_count": sum(m["natural_formulaic_gloss_count"] for m in metrics),
        "natural_raneun_geot_count": sum(m["natural_raneun_geot_count"] for m in metrics),
        "natural_avg_sentence_length_chars": avg([m["natural_avg_sentence_length_chars"] for m in metrics]),
        "natural_sentence_count": sum(m["natural_sentence_count"] for m in metrics),
        "natural_same_as_literal_count": sum(m["natural_same_as_literal"] for m in metrics),
        "natural_near_literal_095_count": sum(m["literal_natural_similarity"] >= 0.95 for m in metrics),
        "natural_too_close_090_count": sum(m["literal_natural_similarity"] >= 0.90 for m in metrics),
        "natural_likely_literal_polish_count": sum(
            "natural_likely_literal_polish" in m["readability_warning_flags"] for m in metrics
        ),
    }


def readability_by_field(items: list[dict[str, Any]], field: str) -> dict[str, Any]:
    grouped: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for item in items:
        grouped[str(item.get(field) or "unknown")].append(item)
    return {key: readability_summary(value) for key, value in sorted(grouped.items())}


def avg(values: list[float | int]) -> str:
    if not values:
        return "0.000000"
    return str((Decimal(str(sum(values))) / Decimal(len(values))).quantize(Decimal("0.000001"), rounding=ROUND_HALF_UP))


def delta_metrics(pair_checks: list[dict[str, Any]]) -> dict[str, Any]:
    if not pair_checks:
        return {
            "avg_similarity_delta_b_minus_a": "0.000000",
            "near_literal_095_delta_b_minus_a": 0,
            "same_as_literal_delta_b_minus_a": 0,
            "pali_parentheses_delta_b_minus_a": 0,
            "lemma_quote_delta_b_minus_a": 0,
            "formulaic_gloss_delta_b_minus_a": 0,
            "raneun_geot_delta_b_minus_a": 0,
            "avg_sentence_length_delta_b_minus_a": "0.000000",
            "sentence_count_delta_b_minus_a": 0,
        }
    deltas = [item["readability_deltas_b_minus_a"] for item in pair_checks]
    a_metrics = [item["a_prime_readability"] for item in pair_checks]
    b_metrics = [item["b_v2_readability"] for item in pair_checks]
    return {
        "avg_similarity_delta_b_minus_a": avg([d["literal_natural_similarity"] for d in deltas]),
        "near_literal_095_delta_b_minus_a": sum(m["literal_natural_similarity"] >= 0.95 for m in b_metrics)
        - sum(m["literal_natural_similarity"] >= 0.95 for m in a_metrics),
        "same_as_literal_delta_b_minus_a": sum(m["natural_same_as_literal"] for m in b_metrics)
        - sum(m["natural_same_as_literal"] for m in a_metrics),
        "pali_parentheses_delta_b_minus_a": sum(d["natural_pali_parentheses_count"] for d in deltas),
        "lemma_quote_delta_b_minus_a": sum(d["natural_lemma_quote_count"] for d in deltas),
        "formulaic_gloss_delta_b_minus_a": sum(d["natural_formulaic_gloss_count"] for d in deltas),
        "raneun_geot_delta_b_minus_a": sum(d["natural_raneun_geot_count"] for d in deltas),
        "avg_sentence_length_delta_b_minus_a": avg([d["natural_avg_sentence_length_chars"] for d in deltas]),
        "sentence_count_delta_b_minus_a": sum(d["natural_sentence_count"] for d in deltas),
    }


def render_comparison_markdown(comparison: dict[str, Any]) -> str:
    return "\n".join(
        [
            "# natural_ko_v2 Controlled Comparison",
            "",
            f"- paired_count: `{comparison['paired_count']}`",
            f"- missing_in_a_prime: `{comparison['missing_in_a_prime']}`",
            f"- missing_in_b_v2: `{comparison['missing_in_b_v2']}`",
            f"- recommendation_status: `{comparison['recommendation_status']}`",
            f"- warnings: `{comparison['warnings']}`",
            "",
            "Automatic metrics are readability and support signals only. Fidelity requires human/scholar review.",
            "",
            "## Delta Metrics",
            "",
            "```json",
            json.dumps(comparison["delta_metrics"], ensure_ascii=False, indent=2),
            "```",
        ]
    ) + "\n"


def render_v2_1_comparison_markdown(comparison: dict[str, Any]) -> str:
    return "\n".join(
        [
            "# natural_ko_v2.1 C-arm Verification",
            "",
            f"- paired_count: `{comparison['paired_count']}`",
            f"- B reference paired_count: `{comparison['b_reference_paired_count']}`",
            f"- recommendation_status: `{comparison['recommendation_status']}`",
            f"- warnings: `{comparison['warnings']}`",
            "",
            "C uses the v2.1 guarded prompt. A′ is reused and not resubmitted. B is kept as a reference for readability-gain retention.",
            "",
            "## Overreach Summary",
            "",
            "```json",
            json.dumps(comparison["overreach_summary"], ensure_ascii=False, indent=2),
            "```",
            "",
            "## C Minus A′ Delta Metrics",
            "",
            "```json",
            json.dumps(comparison["delta_metrics_c_minus_a"], ensure_ascii=False, indent=2),
            "```",
            "",
            "## C Minus B Reference Delta Metrics",
            "",
            "```json",
            json.dumps(comparison["delta_metrics_c_minus_b"], ensure_ascii=False, indent=2),
            "```",
            "",
            "Automatic metrics are support signals only. Conditional adoption still requires operator readability review and Pāli-capable scholar fidelity review.",
        ]
    ) + "\n"


def render_d_arm_summary_markdown(summary: dict[str, Any]) -> str:
    return "\n".join(
        [
            "# natural_ko_v2.2 D-arm Parse Summary",
            "",
            "```json",
            json.dumps(summary, ensure_ascii=False, indent=2),
            "```",
        ]
    ) + "\n"


def render_d_arm_comparison_markdown(comparison: dict[str, Any]) -> str:
    rows = []
    for row in comparison.get("comparison_rows") or []:
        metadata = row.get("metadata") or {}
        gates = row.get("objective_gates") or {}
        rows.append(
            "| "
            + " | ".join(
                [
                    f"`{row.get('stable_segment_key')}`",
                    f"{metadata.get('text_layer')}/{metadata.get('chunk_type')}/{metadata.get('length_bucket')}",
                    row.get("previous_best", ""),
                    row.get("d_literal_verdict", ""),
                    row.get("d_natural_verdict", ""),
                    row.get("readability_verdict", ""),
                    row.get("fidelity_verdict", ""),
                    row.get("insertion_risk", ""),
                    row.get("omission_risk", ""),
                    row.get("negation_risk", ""),
                    row.get("glossary_compliance", ""),
                    "yes" if gates.get("bracket_violation") else "no",
                    row.get("final_item_verdict", ""),
                ]
            )
            + " |"
        )
    return "\n".join(
        [
            "# natural_ko_v2.2 D-arm Comparison",
            "",
            f"- D items: `{comparison['d_item_count']}`",
            f"- objective_gate_status: `{comparison['objective_gate_status']}`",
            f"- recommendation: `{comparison['recommendation']}`",
            "- subjective readability/fidelity gates: pending human review",
            "",
            "## Objective Gate Summary",
            "",
            "```json",
            json.dumps(comparison["objective_gate_summary"], ensure_ascii=False, indent=2),
            "```",
            "",
            "## Item Table",
            "",
            "| segment_id | metadata | previous best | D literal verdict | D natural verdict | readability verdict | fidelity verdict | insertion risk | omission risk | negation risk | glossary compliance | bracket violation | final item verdict |",
            "|---|---|---|---|---|---|---|---|---|---|---|---|---|",
            *rows,
            "",
            "Automatic gates are objective string/metadata checks only. Readability is operator-reviewed; fidelity, negation scope, and general omission are Pāli-scholar reviewed.",
        ]
    ) + "\n"


def render_d_arm_manual_review_sheet(comparison: dict[str, Any]) -> str:
    blocks = ["# natural_ko_v2.2 D-arm Manual Review Sheet", ""]
    for row in comparison.get("comparison_rows") or []:
        item = row["d_item"]
        blocks.extend(
            [
                f"## `{row['stable_segment_key']}`",
                "",
                f"- metadata: {item.get('text_layer')} / {item.get('chunk_type')} / {item.get('length_bucket')}",
                f"- objective gates: `{row['objective_gates']}`",
                "",
                "### Original",
                "",
                str(item.get("original_text") or ""),
                "",
                "### D literal_ko",
                "",
                str(item.get("literal_ko") or ""),
                "",
                "### D natural_ko",
                "",
                str(item.get("natural_ko") or ""),
                "",
                "### READABILITY (operator)",
                "",
                "- [ ] D natural_ko is better than all previous arms / similar to best / worse",
                "- [ ] D avoids literal regression? yes / no / unclear",
                "- [ ] D reads like serious modern Korean Buddhist prose? yes / no",
                "",
                "### FIDELITY / NEGATION / OMISSION (Pāli-capable scholar)",
                "",
                "- [ ] D preserves source meaning and referents? ok / minor / fidelity_risk / fail",
                "- [ ] D preserves negation scope? ok / risk / needs_pali_expert",
                "- [ ] D omits source content? no / minor / risk",
                "- [ ] D adds unsupported content? no / minor / risk",
                "",
            ]
        )
    return "\n".join(blocks)


def render_d_arm_final_recommendation(comparison: dict[str, Any]) -> str:
    return "\n".join(
        [
            "# natural_ko_v2.2 Final Recommendation",
            "",
            "Recommendation: `pending_operator_and_scholar_review`",
            "",
            f"- objective_gate_status: `{comparison['objective_gate_status']}`",
            f"- D item count: `{comparison['d_item_count']}`",
            "- readability gate: `pending_operator_review`",
            "- fidelity/negation/general omission gates: `pending_scholar_review`",
            "- Step 6 started: `false`",
            "",
            "The tool does not auto-adopt or auto-reject v2.2 from subjective criteria. If objective gates pass and human review confirms readability and fidelity, recommend `adopt_natural_ko_v2_2_for_step6`. Otherwise identify one targeted failure category and revise once.",
        ]
    ) + "\n"


def render_human_review_sheet(comparison: dict[str, Any]) -> str:
    blocks = ["# natural_ko_v2 Human Review Sheet", ""]
    for item in comparison.get("pair_checks") or []:
        a = item["a_prime"]
        b = item["b_v2"]
        blocks.extend(
            [
                f"## `{item['stable_segment_key']}`",
                "",
                f"- metadata: {item['text_layer']} / {item['chunk_type']} / {item['length_bucket']}",
                f"- calibration_role: `{item['calibration_role']}`",
                f"- warnings: `{item['warnings']}`",
                "",
                "### Original",
                "",
                str(a.get("original_text") or ""),
                "",
                "### A′ literal_ko",
                "",
                str(a.get("literal_ko") or ""),
                "",
                "### A′ natural_ko",
                "",
                str(a.get("natural_ko") or ""),
                "",
                "### B natural_ko_v2 literal_ko",
                "",
                str(b.get("literal_ko") or ""),
                "",
                "### B natural_ko_v2 natural_ko",
                "",
                str(b.get("natural_ko") or ""),
                "",
                "### Terms/Notes Differences",
                "",
                f"- terms_count_delta: `{item['fidelity_support']['terms_count_delta']}`",
                f"- grammar_notes_count_delta: `{item['fidelity_support']['grammar_notes_count_delta']}`",
                f"- doctrinal_notes_count_delta: `{item['fidelity_support']['doctrinal_notes_count_delta']}`",
                f"- uncertainties_count_delta: `{item['fidelity_support']['uncertainties_count_delta']}`",
                "",
                "### Auto Readability Deltas",
                "",
                "```json",
                json.dumps(item["readability_deltas_b_minus_a"], ensure_ascii=False, indent=2),
                "```",
                "",
                "### READABILITY (operator-judgeable, Korean reader)",
                "",
                "- [ ] B natural_ko more readable than A′? yes / no / unclear",
                "- [ ] B reads like a publishable modern Korean Buddhist book? yes / no",
                "- [ ] B over-paraphrased / too loose? yes / no",
                "",
                "### FIDELITY (Pāli-capable scholar review)",
                "",
                "- [ ] B preserves doctrinal meaning / referents / logical relations? yes / no / uncertain",
                "- [ ] B drops source content? yes / no",
                "- [ ] B adds content not in source? yes / no",
                "- [ ] fidelity verdict: ok / minor / fidelity_risk",
                "",
            ]
        )
    return "\n".join(blocks)


def render_human_review_sheet_v2_1(comparison: dict[str, Any]) -> str:
    blocks = ["# natural_ko_v2.1 Human Review Sheet", ""]
    for item in comparison.get("pair_checks") or []:
        a = item["a_prime"]
        b = item.get("b_reference") or {}
        c = item["c_v2_1"]
        blocks.extend(
            [
                f"## `{item['stable_segment_key']}`",
                "",
                f"- metadata: {item['text_layer']} / {item['chunk_type']} / {item['length_bucket']}",
                f"- calibration_role: `{item['calibration_role']}`",
                f"- warnings: `{item['warnings']}`",
                "",
                "### Original",
                "",
                str(a.get("original_text") or ""),
                "",
                "### A′ literal_ko",
                "",
                str(a.get("literal_ko") or ""),
                "",
                "### A′ natural_ko",
                "",
                str(a.get("natural_ko") or ""),
                "",
                "### B natural_ko_v2 natural_ko (reference)",
                "",
                str(b.get("natural_ko") or "_B reference unavailable_"),
                "",
                "### C natural_ko_v2.1 literal_ko",
                "",
                str(c.get("literal_ko") or ""),
                "",
                "### C natural_ko_v2.1 natural_ko",
                "",
                str(c.get("natural_ko") or ""),
                "",
                "### Auto Support Signals",
                "",
                "```json",
                json.dumps(
                    {
                        "c_minus_a": item["c_minus_a_readability_deltas"],
                        "c_minus_b": item.get("c_minus_b_readability_deltas"),
                        "literal_structural_checks": item["literal_structural_checks"],
                        "fidelity_support": item["fidelity_support"],
                    },
                    ensure_ascii=False,
                    indent=2,
                ),
                "```",
                "",
                "### READABILITY (operator-judgeable, Korean reader)",
                "",
                "- [ ] C natural_ko more readable than A′? yes / no / unclear",
                "- [ ] C keeps most of B's readability gain? yes / no / unclear",
                "- [ ] C reads like a publishable modern Korean Buddhist book? yes / no",
                "- [ ] C over-paraphrased / too loose? yes / no",
                "",
                "### FIDELITY (Pāli-capable scholar review)",
                "",
                "- [ ] C preserves doctrinal meaning / referents / logical relations? yes / no / uncertain",
                "- [ ] C drops source content? yes / no",
                "- [ ] C adds content not in source? yes / no",
                "- [ ] C avoids unsupported causal/doctrinal insertion? yes / no",
                "- [ ] fidelity verdict: ok / minor / fidelity_risk",
                "",
            ]
        )
    return "\n".join(blocks)


def finalize_recommendation(*, out_dir: Path, pretty: bool = False) -> dict[str, Any]:
    paths = smoke_paths(out_dir)
    comparison = read_json(paths.comparison_json) if paths.comparison_json.exists() else {}
    if not comparison:
        recommendation = {
            "decision": "insufficient_data",
            "reason": "Comparison has not been generated.",
            "gold_accuracy_available": False,
        }
    elif comparison.get("paired_count", 0) < 30:
        recommendation = {
            "decision": "insufficient_data",
            "reason": "Fewer than 30 paired A′/B items were available.",
            "paired_count": comparison.get("paired_count", 0),
            "gold_accuracy_available": False,
        }
    else:
        recommendation = {
            "decision": "pending_operator_readability_review",
            "reason": "Automatic readability metrics are available, but final adoption requires operator readability review and Pāli-capable fidelity review.",
            "paired_count": comparison.get("paired_count", 0),
            "gold_accuracy_available": False,
            "adoption_requires": [
                "positive_operator_readability_verdict",
                "no_unresolved_scholar_fidelity_risk",
            ],
        }
    write_json(paths.final_recommendation_json, recommendation, pretty=pretty)
    paths.final_recommendation_md.write_text(render_final_recommendation_markdown(recommendation), encoding="utf-8")
    return {"status": "FINALIZED", "recommendation": recommendation}


def finalize_v2_1_recommendation(*, out_dir: Path, pretty: bool = False) -> dict[str, Any]:
    paths = smoke_paths(out_dir)
    comparison = read_json(paths.comparison_v2_1_json) if paths.comparison_v2_1_json.exists() else {}
    if not comparison:
        recommendation = {
            "decision": "pending_operator_and_scholar_review",
            "reason": "C-arm comparison has not been generated. Step 6 remains blocked.",
            "step6_prompt_variant": "natural_ko_v2_1",
            "reader_ko_added": False,
            "response_schema_default": True,
            "salvage_cascade_fallback": True,
            "gold_accuracy_available": False,
        }
    elif comparison.get("paired_count", 0) < 30:
        recommendation = {
            "decision": "insufficient_data",
            "reason": "Fewer than 30 paired A′/C items were available.",
            "paired_count": comparison.get("paired_count", 0),
            "step6_prompt_variant": "natural_ko_v2_1",
            "reader_ko_added": False,
            "response_schema_default": True,
            "salvage_cascade_fallback": True,
            "gold_accuracy_available": False,
        }
    else:
        recommendation = {
            "decision": "pending_operator_and_scholar_review",
            "reason": "C-arm metrics are available, but conditional adoption requires operator readability review and Pāli-capable scholar fidelity review.",
            "paired_count": comparison.get("paired_count", 0),
            "step6_prompt_variant": "natural_ko_v2_1",
            "reader_ko_added": False,
            "response_schema_default": True,
            "salvage_cascade_fallback": True,
            "gold_accuracy_available": False,
            "conditional_decisions": {
                "if_c_passes_targeted_failure_cases": "adopt_natural_ko_v2_1_for_step6",
                "if_c_fails_causal_insertion_or_overcommit": "revise_natural_ko_v2_2_and_retest",
                "if_c_dampens_readability": "revise_natural_ko_v2_2_and_retest",
            },
        }
    write_json(paths.final_recommendation_json, recommendation, pretty=pretty)
    paths.final_recommendation_md.write_text(render_final_recommendation_markdown(recommendation), encoding="utf-8")
    return {"status": "FINALIZED_V2_1", "recommendation": recommendation}


def render_final_recommendation_markdown(recommendation: dict[str, Any]) -> str:
    return "\n".join(
        [
            "# natural_ko_v2 Final Recommendation",
            "",
            f"- decision: `{recommendation['decision']}`",
            f"- reason: {recommendation['reason']}",
            f"- gold_accuracy_available: `{recommendation.get('gold_accuracy_available', False)}`",
            "",
            "Automatic metrics do not certify fidelity. Final adoption requires both a positive readability verdict and no unresolved Pāli-scholar fidelity risk.",
        ]
    ) + "\n"


def render_step6_handoff_v2_1(comparison: dict[str, Any]) -> str:
    return f"""# Step 6 Handoff: natural_ko_v2.1

Step 6 may proceed with `natural_ko_v2_1` only after C verification passes operator readability review and Pāli-capable scholar fidelity review.

- response_schema default: true
- salvage fallback: true
- reader_ko added: false
- gold accuracy available: false
- silver canary status: advisory_only_not_gold_accuracy
- paired C verification items: {comparison.get('paired_count', 0)}

v2.1 is a narrow fidelity guard over the already-tested v2 readability prompt. It is additionally verified on the same 30 diagnostic items through a C-only smoke that reuses A′ and keeps B as reference.

Step 6/7 smoke must continue tracking:

- possible_added_claim_warning
- added causal/doctrinal phrase flags
- ambiguous verb over-commit
- over-paraphrase
- convergence-control forced divergence

If causal insertion or fidelity-risk rises, block the 1,000 submit and revise to v2.2.
"""

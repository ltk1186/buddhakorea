"""Run local-only preflight for the Pali 300 pilot.

This script does not call Gemini, GPT, Claude, countTokens, or any network API.
It does not submit Batch jobs, poll provider status, write to a database, run
RAG/embedding, or modify prompts, glossary, gold_set, or the Step 1 selection.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import statistics
import subprocess
import sys
from collections import Counter, defaultdict
from dataclasses import dataclass
from datetime import datetime, timezone
from decimal import Decimal, InvalidOperation, ROUND_HALF_UP
from pathlib import Path
from typing import Any

REPO_ROOT = Path(__file__).resolve().parents[3]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from backend.pali.scripts.build_pilot_300_manifest import (
    selection_content_sha256,
    source_prefix,
    source_text,
    stable_json_sha256,
    word_tokens,
)
from backend.pali.translation.batch_plan import BatchSegmentPlan, build_provider_jsonl_line
from backend.pali.translation.budget import (
    BudgetState,
    PriceProfile,
    TokenEstimate,
    can_submit_batch_under_budget,
    estimate_request_cost,
)
from backend.pali.translation.prompts import (
    KOREAN_ADVANCED_PROMPT_ID,
    KOREAN_ADVANCED_PROMPT_MODEL,
    KOREAN_ADVANCED_PROMPT_VERSION,
    render_korean_advanced_prompt_v1,
)


SCRIPT_VERSION = "pilot_300_preflight_v1"
RUN_ID = "pilot_300_v1"
MODEL = KOREAN_ADVANCED_PROMPT_MODEL
PROMPT_PROFILE = KOREAN_ADVANCED_PROMPT_VERSION
DEFAULT_PRICE = {
    "input_usd_per_1m": Decimal("1.0"),
    "output_usd_per_1m": Decimal("6.0"),
    "thinking_billed_as_output": True,
}
PILOT75_TOTALS = {
    "item_count": 75,
    "input_tokens": 242651,
    "output_tokens": 56043,
    "thinking_tokens": 142478,
    "actual_cost_usd": Decimal("1.433777"),
}
PROMPT_CALIBRATION_DEFAULT = Path("data/reports/pali/gemini_prompt_v1_schemafix_token_calibration_49bc869.json")
GOLD_DEFAULT = Path("data/gold_set.json")


class PreflightBlocked(RuntimeError):
    def __init__(self, status: str, message: str):
        super().__init__(message)
        self.status = status
        self.message = message


@dataclass(frozen=True)
class RatioStats:
    n: int
    mean: Decimal
    median: Decimal
    p90: Decimal


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    try:
        result = run_preflight(args)
    except PreflightBlocked as exc:
        print(json.dumps({"status": exc.status, "message": exc.message}, ensure_ascii=False, sort_keys=True), file=sys.stderr)
        return 2
    print(json.dumps(result, ensure_ascii=False, sort_keys=True))
    return 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Run local-only cost estimate and dry-run preflight for Pali 300 pilot."
    )
    parser.add_argument("--manifest", required=True)
    parser.add_argument("--validation", required=True)
    parser.add_argument("--inventory", required=True)
    parser.add_argument("--pilot75-parsed", required=True)
    parser.add_argument("--glossary", required=True)
    parser.add_argument("--out", required=True)
    parser.add_argument("--qa-dryrun-out", required=True)
    parser.add_argument("--expected-selection-sha")
    parser.add_argument("--budget-usd", default="20")
    parser.add_argument("--prompt-calibration", default=str(PROMPT_CALIBRATION_DEFAULT))
    parser.add_argument("--gold", default=str(GOLD_DEFAULT))
    parser.add_argument(
        "--docs-out",
        default="docs/translation/PALI_300_PILOT_COST_AND_LOCAL_DRY_RUN_PLAN.md",
        help="Path for the generated Step 2 docs. Tests should pass a temp path.",
    )
    parser.add_argument("--pretty", action="store_true")
    return parser


def run_preflight(args: argparse.Namespace) -> dict[str, Any]:
    out_dir = Path(args.out)
    out_dir.mkdir(parents=True, exist_ok=True)
    manifest_path = Path(args.manifest)
    validation_path = Path(args.validation)
    inventory_path = Path(args.inventory)
    pilot75_path = Path(args.pilot75_parsed)
    budget_usd = parse_decimal_money(args.budget_usd, field_name="budget_usd")

    manifest = read_json(manifest_path)
    validation = read_json(validation_path)
    identity = verify_manifest_identity(
        manifest,
        validation,
        expected_selection_sha=args.expected_selection_sha,
    )
    identity["manifest_path"] = str(manifest_path)
    identity["glossary_sha256"] = file_sha256(Path(args.glossary))
    if not inventory_path.exists():
        raise PreflightBlocked("BLOCKED_MISSING_INVENTORY", f"missing inventory: {inventory_path}")
    inventory_payload = read_json(inventory_path)
    inventory_items = inventory_payload.get("items", inventory_payload if isinstance(inventory_payload, list) else [])
    if not isinstance(inventory_items, list):
        raise PreflightBlocked("BLOCKED_MISSING_INVENTORY", "inventory must be a list or contain items")
    if file_sha256(inventory_path) != identity["inventory_sha256"]:
        raise PreflightBlocked("BLOCKED_HASH_MISMATCH", "inventory sha256 differs from Step 1 validation")

    pilot75 = read_json(pilot75_path)
    price_profile = PriceProfile(
        input_usd_per_million_tokens=DEFAULT_PRICE["input_usd_per_1m"],
        output_usd_per_million_tokens=DEFAULT_PRICE["output_usd_per_1m"],
        thinking_usd_per_million_tokens=DEFAULT_PRICE["output_usd_per_1m"],
    )
    pricing_check = pricing_self_check(price_profile)
    if not pricing_check["pass"]:
        raise PreflightBlocked("BLOCKED_PRICING_DRIFT", "75 pilot pricing self-check failed")

    cost_report = estimate_pilot_300_cost(
        manifest=manifest,
        inventory_items=inventory_items,
        pilot75=pilot75,
        price_profile=price_profile,
        prompt_calibration_path=Path(args.prompt_calibration),
        budget_usd=budget_usd,
        identity=identity,
    )
    cost_path = out_dir / "pilot_300_v1_cost_estimate.json"
    cost_md_path = out_dir / "pilot_300_v1_cost_estimate.md"
    write_json(cost_path, cost_report, pretty=args.pretty)
    cost_md_path.write_text(render_cost_markdown(cost_report), encoding="utf-8")

    jsonl_path = out_dir / "pilot_300_v1_batch_unsubmitted.jsonl"
    jsonl_manifest_path = out_dir / "pilot_300_v1_batch_unsubmitted_manifest.json"
    jsonl_result = build_unsubmitted_jsonl(
        manifest=manifest,
        inventory_items=inventory_items,
        estimate=cost_report,
        jsonl_path=jsonl_path,
        jsonl_manifest_path=jsonl_manifest_path,
        pretty=args.pretty,
    )
    if not jsonl_result["validation"]["valid"]:
        raise PreflightBlocked("BLOCKED_JSONL_INVALID", "unsubmitted JSONL validation failed")

    source_integrity = source_integrity_precheck(
        manifest=manifest,
        inventory_items=inventory_items,
        jsonl_manifest=jsonl_result["manifest"],
    )
    source_integrity_path = out_dir / "pilot_300_v1_source_integrity_precheck.json"
    write_json(source_integrity_path, source_integrity, pretty=args.pretty)
    if not source_integrity["valid"]:
        raise PreflightBlocked("BLOCKED_SOURCE_INTEGRITY", "source integrity precheck failed")

    mock_result = build_mock_parsed_and_run_qa(
        manifest=manifest,
        inventory_items=inventory_items,
        out_dir=out_dir,
        qa_out_dir=Path(args.qa_dryrun_out),
        gold_path=Path(args.gold),
        pretty=args.pretty,
    )
    if not mock_result["valid"]:
        raise PreflightBlocked("BLOCKED_QA_DRYRUN_FAILED", "mock QA dry-run failed")

    guardrail = run_budget_guardrail_test(
        budget_usd=budget_usd,
        conservative_gate_cost_usd=parse_decimal_money(
            cost_report["estimate_totals"]["conservative_gate"]["cost_usd"],
            field_name="estimate_totals.conservative_gate.cost_usd",
        ),
    )
    guardrail_path = out_dir / "pilot_300_v1_budget_guardrail_test.json"
    write_json(guardrail_path, guardrail, pretty=args.pretty)
    if not guardrail["valid"]:
        raise PreflightBlocked("BLOCKED_OVER_BUDGET", "budget guardrail failed")

    readiness = build_readiness(
        manifest=manifest,
        identity=identity,
        cost_report=cost_report,
        jsonl_result=jsonl_result,
        source_integrity=source_integrity,
        mock_result=mock_result,
        guardrail=guardrail,
        budget_usd=budget_usd,
    )
    readiness_path = out_dir / "pilot_300_v1_batch_readiness.json"
    write_json(readiness_path, readiness, pretty=args.pretty)

    docs_path = Path(args.docs_out)
    docs_path.parent.mkdir(parents=True, exist_ok=True)
    docs_path.write_text(
        render_plan_doc_from_outputs(
            cost_report=cost_report,
            readiness=readiness,
            jsonl_result=jsonl_result,
            source_integrity=source_integrity,
            mock_result=mock_result,
            guardrail=guardrail,
        ),
        encoding="utf-8",
    )
    preflight_manifest_path = out_dir / "pilot_300_v1_preflight_run_manifest.json"
    preflight_manifest = build_preflight_run_manifest(
        args=args,
        identity=identity,
        outputs={
            "cost_estimate": str(cost_path),
            "cost_estimate_md": str(cost_md_path),
            "jsonl": str(jsonl_path),
            "jsonl_manifest": str(jsonl_manifest_path),
            "source_integrity": str(source_integrity_path),
            "budget_guardrail": str(guardrail_path),
            "readiness": str(readiness_path),
            "qa_dryrun_out": str(args.qa_dryrun_out),
            "docs": str(docs_path),
        },
    )
    write_json(preflight_manifest_path, preflight_manifest, pretty=args.pretty)
    return {
        "cost_estimate": str(cost_path),
        "cost_estimate_md": str(cost_md_path),
        "jsonl": str(jsonl_path),
        "jsonl_manifest": str(jsonl_manifest_path),
        "source_integrity": str(source_integrity_path),
        "budget_guardrail": str(guardrail_path),
        "readiness": str(readiness_path),
        "preflight_run_manifest": str(preflight_manifest_path),
        "qa_dryrun_out": str(args.qa_dryrun_out),
        "readiness_status": readiness["readiness_status"],
        "estimated_cost_usd_conservative_gate": readiness["estimated_cost_usd_conservative_gate"],
    }


def verify_manifest_identity(
    manifest: dict[str, Any],
    validation: dict[str, Any],
    *,
    expected_selection_sha: str | None,
) -> dict[str, Any]:
    if manifest.get("schema_version") != "pali_pilot_300_manifest_v1":
        raise PreflightBlocked("BLOCKED_INVALID_MANIFEST", "unexpected manifest schema_version")
    if validation.get("valid") is not True:
        raise PreflightBlocked("BLOCKED_INVALID_MANIFEST", "Step 1 validation is not valid")
    summary = manifest.get("summary") or {}
    required_counts = {
        "selected_count": 300,
        "hard_count": 100,
        "representative_count": 200,
    }
    for key, expected in required_counts.items():
        if int(summary.get(key) or 0) != expected:
            raise PreflightBlocked("BLOCKED_INVALID_MANIFEST", f"{key} != {expected}")
    stored_sha = (
        validation.get("checks", {})
        .get("selection_content_hash", {})
        .get("sha256")
    )
    recomputed = selection_content_sha256(manifest)
    if stored_sha != recomputed:
        raise PreflightBlocked("BLOCKED_HASH_MISMATCH", "manifest and validation selection hash differ")
    if expected_selection_sha and expected_selection_sha != recomputed:
        raise PreflightBlocked("BLOCKED_HASH_MISMATCH", "expected selection hash mismatch")
    inventory_sha = (
        validation.get("checks", {})
        .get("inventory_hash_present", {})
        .get("sha256")
        or manifest.get("source_provenance", {}).get("inventory_sha256", "")
    )
    return {
        "manifest_sha256": stable_json_sha256(manifest),
        "selection_content_sha256": recomputed,
        "stored_selection_content_sha256": stored_sha,
        "expected_selection_content_sha256": expected_selection_sha,
        "inventory_sha256": inventory_sha,
        "source_commit": manifest.get("source_provenance", {}).get("source_commit", ""),
        "source_path_root": manifest.get("source_provenance", {}).get("source_path_root", ""),
    }


def build_preflight_run_manifest(
    *,
    args: argparse.Namespace,
    identity: dict[str, Any],
    outputs: dict[str, str],
) -> dict[str, Any]:
    input_paths = {
        "manifest": args.manifest,
        "validation": args.validation,
        "inventory": args.inventory,
        "pilot75_parsed": args.pilot75_parsed,
        "glossary": args.glossary,
        "prompt_calibration": args.prompt_calibration,
        "gold": args.gold,
    }
    input_files = {}
    for name, path_value in input_paths.items():
        path = Path(path_value)
        input_files[name] = {
            "path": str(path),
            "exists": path.exists(),
            "sha256": file_sha256(path) if path.exists() else None,
        }
    return {
        "schema_version": "pali_pilot_300_preflight_run_manifest_v1",
        "run_id": RUN_ID,
        "script_version": SCRIPT_VERSION,
        "generated_at": now_iso(),
        "input_files": input_files,
        "output_paths": outputs,
        "identity": identity,
        "prompt_id": KOREAN_ADVANCED_PROMPT_ID,
        "prompt_version": PROMPT_PROFILE,
        "model": MODEL,
        "glossary_version": "data/controlled_glossary.json",
        "network_allowed": False,
        "gemini_calls_allowed": False,
        "batch_submission_allowed": False,
        "live_smoke_allowed": False,
        "command_line_args": vars(args),
    }


def estimate_pilot_300_cost(
    *,
    manifest: dict[str, Any],
    inventory_items: list[dict[str, Any]],
    pilot75: dict[str, Any],
    price_profile: PriceProfile,
    prompt_calibration_path: Path,
    budget_usd: Decimal,
    identity: dict[str, Any],
) -> dict[str, Any]:
    inventory_by_pair = index_inventory_by_pair(inventory_items)
    pilot75_rows = calibration_rows_from_pilot75(pilot75)
    segments_with_usage = len(pilot75_rows)
    if not pilot75_rows:
        raise PreflightBlocked("BLOCKED_PRICING_DRIFT", "pilot75 usage rows are empty")
    source_ratio_stats = source_ratio_stats_from_prompt_calibration(prompt_calibration_path)
    output_stats = build_ratio_index(pilot75_rows, "output_ratio")
    thinking_stats = build_ratio_index(pilot75_rows, "thinking_ratio")
    overhead_stats = build_ratio_index(pilot75_rows, "input_overhead")

    items = []
    for item in manifest["items"]:
        inv = inventory_by_pair.get((item["stable_segment_key"], item["source_text_hash"]))
        if not inv:
            raise PreflightBlocked("BLOCKED_SOURCE_INTEGRITY", f"inventory missing selected item {item['stable_segment_key']}")
        source_unit_value = source_unit(inv)
        source_ratio, source_bucket, source_n = choose_source_ratio(item, source_ratio_stats)
        mean_output, output_bucket, output_n = choose_ratio(item, output_stats, "mean")
        p90_output, output_p90_bucket, output_p90_n = choose_ratio(item, output_stats, "p90")
        mean_thinking, thinking_bucket, thinking_n = choose_ratio(item, thinking_stats, "mean")
        p90_thinking, thinking_p90_bucket, thinking_p90_n = choose_ratio(item, thinking_stats, "p90")
        mean_overhead, overhead_bucket, overhead_n = choose_ratio(item, overhead_stats, "mean")
        p90_overhead, overhead_p90_bucket, overhead_p90_n = choose_ratio(item, overhead_stats, "p90")
        mean_source = round_decimal(source_unit_value * source_ratio)
        p90_source = mean_source
        mean_input = max(1, mean_source + round_decimal(mean_overhead))
        p90_input = max(1, p90_source + round_decimal(p90_overhead))
        mean_output_tokens = max(1, round_decimal(source_unit_value * mean_output))
        p90_output_tokens = max(1, round_decimal(source_unit_value * p90_output))
        mean_thinking_tokens = max(0, round_decimal(source_unit_value * mean_thinking))
        p90_thinking_tokens = max(0, round_decimal(source_unit_value * p90_thinking))
        mean_cost = estimate_request_cost(
            TokenEstimate(mean_input, mean_output_tokens, mean_thinking_tokens),
            price_profile,
        )
        p90_cost = estimate_request_cost(
            TokenEstimate(p90_input, p90_output_tokens, p90_thinking_tokens),
            price_profile,
        )
        items.append(
            {
                "stable_segment_key": item["stable_segment_key"],
                "source_path": item["source_path"],
                "source_text_hash": item["source_text_hash"],
                "text_layer": item["text_layer"],
                "length_bucket": item["length_bucket"],
                "chunk_type": item["chunk_type"],
                "selection_group": item["selection_group"],
                "selection_bucket": item["selection_bucket"],
                "gold_candidate": bool(item.get("gold_candidate")),
                "pool_candidate": item.get("pool_candidate"),
                "source_path_prefix": source_prefix(item["source_path"]),
                "source_unit": float(source_unit_value),
                "expected_mean": {
                    "input_tokens": mean_input,
                    "output_tokens": mean_output_tokens,
                    "thinking_tokens": mean_thinking_tokens,
                    "official_cost_usd": str(mean_cost),
                },
                "planning_p90": {
                    "input_tokens": p90_input,
                    "output_tokens": p90_output_tokens,
                    "thinking_tokens": p90_thinking_tokens,
                    "official_cost_usd": str(p90_cost),
                },
                "calibration": {
                    "source_bucket_used": source_bucket,
                    "source_bucket_n": source_n,
                    "output_bucket_used": output_bucket,
                    "output_bucket_n": output_n,
                    "thinking_bucket_used": thinking_bucket,
                    "thinking_bucket_n": thinking_n,
                    "overhead_bucket_used": overhead_bucket,
                    "overhead_bucket_n": overhead_n,
                    "backoff_used": any(
                        n < 5 or bucket != primary_bucket_key(item)
                        for bucket, n in (
                            (output_bucket, output_n),
                            (thinking_bucket, thinking_n),
                            (overhead_bucket, overhead_n),
                        )
                    ),
                    "confidence": confidence_from_n(min(output_n, thinking_n, overhead_n)),
                    "p90_buckets": {
                        "output": output_p90_bucket,
                        "thinking": thinking_p90_bucket,
                        "overhead": overhead_p90_bucket,
                        "output_n": output_p90_n,
                        "thinking_n": thinking_p90_n,
                        "overhead_n": overhead_p90_n,
                    },
                },
            }
        )

    mean_totals = sum_estimate_items(items, "expected_mean")
    p90_totals = sum_estimate_items(items, "planning_p90")
    empirical_rate = empirical_blended_rate(PILOT75_TOTALS)
    mean_empirical = empirical_cost(mean_totals, empirical_rate)
    p90_empirical = empirical_cost(p90_totals, empirical_rate)
    p90_official = Decimal(str(p90_totals["official_cost_usd"]))
    conservative = max(p90_official, p90_empirical)
    budget_status = "PASS_READY_FOR_USER_APPROVAL" if conservative <= budget_usd else "BLOCKED_OVER_BUDGET"

    totals75 = totals_from_pilot75(pilot75)
    thinking_output_ratio = Decimal(totals75["thinking_tokens"]) / Decimal(max(totals75["output_tokens"], 1))
    return {
        "schema_version": "pali_pilot_300_cost_estimate_v1",
        "run_id": RUN_ID,
        "generated_at": now_iso(),
        "created_from_manifest": {
            **identity,
        },
        "calibration": {
            "source": "pilot_75_qa_patch_v2",
            "source_type": "artifact",
            "item_count": len(pilot75.get("items") or []),
            "segments_with_usage": segments_with_usage,
            "input_tokens": totals75["input_tokens"],
            "output_tokens": totals75["output_tokens"],
            "thinking_tokens": totals75["thinking_tokens"],
            "actual_cost_usd": str(totals75["actual_cost_usd"]),
            "thinking_output_ratio": str(thinking_output_ratio.quantize(Decimal("0.001"))),
            "pricing_self_check": pricing_self_check(price_profile),
            "input_estimation_method": "fixed prompt/glossary overhead separated from source token proxy; output/thinking ratios from 75 actuals",
        },
        "pricing": {
            "mode": "batch",
            "model": MODEL,
            "input_usd_per_1m": float(DEFAULT_PRICE["input_usd_per_1m"]),
            "output_usd_per_1m": float(DEFAULT_PRICE["output_usd_per_1m"]),
            "thinking_billed_as_output": True,
        },
        "estimate_totals": {
            "expected_mean": {
                **mean_totals,
                "empirical_blended_cost_usd": str(mean_empirical),
            },
            "planning_p90": {
                **p90_totals,
                "empirical_blended_cost_usd": str(p90_empirical),
            },
            "conservative_gate": {
                "cost_usd": str(quantize_usd(conservative)),
                "basis": "max(official_planning_p90, empirical_blended_p90)",
            },
        },
        "budget_gate": {
            "budget_usd": str(budget_usd),
            "conservative_gate_cost_usd": str(quantize_usd(conservative)),
            "under_budget": conservative <= budget_usd,
            "status": budget_status,
        },
        "bucket_stats": serialize_bucket_stats(output_stats, thinking_stats, overhead_stats),
        "special_slices": build_special_slices(items),
        "limitations": [
            "No countTokens API was called in Step 2.",
            "Input tokens are estimated from existing calibration and 75 actual prompt usage.",
            "Output and thinking token p90 use 75 observed bucket ratios, with deterministic backoff where n < 5.",
            "This is a preflight estimate, not a production cost commitment.",
        ],
        "items": items,
    }


def build_unsubmitted_jsonl(
    *,
    manifest: dict[str, Any],
    inventory_items: list[dict[str, Any]],
    estimate: dict[str, Any],
    jsonl_path: Path,
    jsonl_manifest_path: Path,
    pretty: bool,
) -> dict[str, Any]:
    inventory_by_pair = index_inventory_by_pair(inventory_items)
    estimate_by_key = {item["stable_segment_key"]: item for item in estimate["items"]}
    generation_config = {"temperature": 0.2, "response_mime_type": "application/json"}
    plans: list[BatchSegmentPlan] = []
    sidecar_items = []
    for index, item in enumerate(manifest["items"]):
        inv = inventory_by_pair[(item["stable_segment_key"], item["source_text_hash"])]
        segment = {**item, **inv}
        prompt = render_korean_advanced_prompt_v1(segment)
        est = estimate_by_key[item["stable_segment_key"]]
        plan = BatchSegmentPlan(
            stable_segment_key=item["stable_segment_key"],
            source_text_hash=item["source_text_hash"],
            source_path=item["source_path"],
            text_layer=item["text_layer"],
            chunk_type=item["chunk_type"],
            prompt_text=prompt,
            estimated_input_tokens=int(est["planning_p90"]["input_tokens"]),
            estimated_output_tokens=int(est["planning_p90"]["output_tokens"]),
            estimated_thinking_tokens=int(est["planning_p90"]["thinking_tokens"]),
            metadata={
                "selection_group": item["selection_group"],
                "selection_bucket": item["selection_bucket"],
                "source_text_hash_from_jsonl_source": hash_normalized(inv),
            },
        )
        plans.append(plan)
        sidecar_items.append(
            {
                "stable_segment_key": plan.stable_segment_key,
                "source_text_hash": plan.source_text_hash,
                "source_path": plan.source_path,
                "text_layer": plan.text_layer,
                "chunk_type": plan.chunk_type,
                "length_bucket": item["length_bucket"],
                "selection_group": item["selection_group"],
                "selection_bucket": item["selection_bucket"],
                "estimated_input_tokens": plan.estimated_input_tokens,
                "estimated_output_tokens": plan.estimated_output_tokens,
                "estimated_thinking_tokens": plan.estimated_thinking_tokens,
                "jsonl_line_index": index,
                "jsonl_source_text_hash": hash_normalized(inv),
                "prompt_template_id": KOREAN_ADVANCED_PROMPT_ID,
                "prompt_template_version": KOREAN_ADVANCED_PROMPT_VERSION,
            }
        )
    lines = [build_provider_jsonl_line(plan, generation_config=generation_config) for plan in plans]
    write_jsonl(jsonl_path, lines)
    jsonl_sha = file_sha256(jsonl_path)
    sidecar = {
        "schema_version": "pali_pilot_300_unsubmitted_batch_manifest_v1",
        "submitted": False,
        "submission_allowed": False,
        "user_approval_required": True,
        "batch_submission_allowed_now": False,
        "request_count": len(lines),
        "selection_content_sha256": selection_content_sha256(manifest),
        "jsonl_sha256": jsonl_sha,
        "generation_config": generation_config,
        "model": MODEL,
        "prompt_profile": PROMPT_PROFILE,
        "prompt_template_id": KOREAN_ADVANCED_PROMPT_ID,
        "prompt_template_version": KOREAN_ADVANCED_PROMPT_VERSION,
        "provider_jsonl_path": str(jsonl_path),
        "items": sidecar_items,
    }
    validation = validate_unsubmitted_jsonl(lines, sidecar, manifest)
    sidecar["validation"] = validation
    write_json(jsonl_manifest_path, sidecar, pretty=pretty)
    return {"jsonl_path": str(jsonl_path), "manifest_path": str(jsonl_manifest_path), "manifest": sidecar, "validation": validation}


def validate_unsubmitted_jsonl(
    lines: list[dict[str, Any]],
    sidecar: dict[str, Any],
    manifest: dict[str, Any],
) -> dict[str, Any]:
    errors = []
    if len(lines) != 300 or sidecar.get("request_count") != 300:
        errors.append("request_count_must_be_300")
    manifest_keys = [item["stable_segment_key"] for item in manifest["items"]]
    line_keys = [line.get("key") for line in lines]
    if line_keys != manifest_keys:
        errors.append("jsonl_keys_do_not_match_manifest_order")
    if sidecar.get("submitted") is not False or sidecar.get("submission_allowed") is not False:
        errors.append("unsubmitted_manifest_submission_flags_invalid")
    if sidecar.get("prompt_template_version") != KOREAN_ADVANCED_PROMPT_VERSION:
        errors.append("prompt_template_version_mismatch")
    if sidecar.get("generation_config") != {"temperature": 0.2, "response_mime_type": "application/json"}:
        errors.append("generation_config_mismatch")
    for line in lines:
        request = line.get("request") or {}
        text = (((request.get("contents") or [{}])[0].get("parts") or [{}])[0].get("text") or "")
        if "literal_ko" not in text or "natural_ko" not in text or "quality_flags" not in text:
            errors.append(f"missing_schema_instruction:{line.get('key')}")
            break
    return {"valid": not errors, "errors": errors}


def source_integrity_precheck(
    *,
    manifest: dict[str, Any],
    inventory_items: list[dict[str, Any]],
    jsonl_manifest: dict[str, Any],
) -> dict[str, Any]:
    inventory_by_pair = index_inventory_by_pair(inventory_items)
    jsonl_by_key = {item["stable_segment_key"]: item for item in jsonl_manifest.get("items") or []}
    mismatches = []
    missing = []
    for item in manifest["items"]:
        key = item["stable_segment_key"]
        inv = inventory_by_pair.get((key, item["source_text_hash"]))
        if not inv:
            missing.append(key)
            continue
        inventory_hash = hash_normalized(inv)
        jsonl_hash = (jsonl_by_key.get(key) or {}).get("jsonl_source_text_hash")
        if inventory_hash != item["source_text_hash"]:
            mismatches.append({"stable_segment_key": key, "kind": "manifest_to_inventory_hash", "expected": item["source_text_hash"], "actual": inventory_hash})
        if jsonl_hash != item["source_text_hash"]:
            mismatches.append({"stable_segment_key": key, "kind": "manifest_to_jsonl_hash", "expected": item["source_text_hash"], "actual": jsonl_hash})
    return {
        "schema_version": "pali_pilot_300_source_integrity_precheck_v1",
        "valid": not mismatches and not missing,
        "checked_count": len(manifest["items"]) - len(missing),
        "mismatches": mismatches,
        "missing_inventory_keys": missing,
        "manifest_to_inventory_hash_match": not any(item["kind"] == "manifest_to_inventory_hash" for item in mismatches),
        "manifest_to_jsonl_hash_match": not any(item["kind"] == "manifest_to_jsonl_hash" for item in mismatches),
    }


def build_mock_parsed_and_run_qa(
    *,
    manifest: dict[str, Any],
    inventory_items: list[dict[str, Any]],
    out_dir: Path,
    qa_out_dir: Path,
    gold_path: Path,
    pretty: bool,
) -> dict[str, Any]:
    inventory_by_pair = index_inventory_by_pair(inventory_items)
    items = []
    for item in manifest["items"]:
        inv = inventory_by_pair[(item["stable_segment_key"], item["source_text_hash"])]
        items.append(
            {
                "stable_segment_key": item["stable_segment_key"],
                "source_text_hash": item["source_text_hash"],
                "text_layer": item["text_layer"],
                "chunk_type": item["chunk_type"],
                "length_bucket": item["length_bucket"],
                "pitaka": item.get("pitaka", ""),
                "nikaya": item.get("nikaya", ""),
                "source_path": item["source_path"],
                "original_text": inv.get("original_text") or inv.get("normalized_text") or "",
                "parsed_translation_json": {
                    "literal_ko": "[MOCK] 구조 검증용 직역 placeholder",
                    "natural_ko": "[MOCK] 구조 검증용 자연역 placeholder",
                    "terms": [],
                    "grammar_notes": [],
                    "doctrinal_notes": [],
                    "uncertainties": [],
                    "quality_flags": [],
                },
                "schema_valid": True,
                "quality_flags": [],
                "local_validator_flags": [],
                "quality_flag_details": [],
                "prompt_token_count": 0,
                "candidates_token_count": 0,
                "thoughts_token_count": 0,
                "cached_content_token_count": 0,
                "total_token_count": 0,
                "estimated_cost_usd": "0",
                "actual_cost_usd": "0",
                "status": "succeeded",
                "error_message": "",
            }
        )
    parsed_path = out_dir / "pilot_300_v1_mock_parsed.json"
    mock_manifest_path = out_dir / "pilot_300_v1_mock_run_manifest.json"
    glossary_qa_path = out_dir / "pilot_300_v1_mock_glossary_qa.json"
    write_json(parsed_path, {"items": items, "mock_run": True}, pretty=pretty)
    write_json(
        mock_manifest_path,
        {
            "schema_version": "pali_pilot_300_mock_run_manifest_v1",
            "mock": True,
            "quality_signal": False,
            "do_not_use_for_translation_evaluation": True,
            "parsed_path": str(parsed_path),
            "item_count": len(items),
            "note": "mock QA dry-run is not a translation quality signal; gold empty is expected because current gold seeds are disjoint from 300.",
        },
        pretty=pretty,
    )
    write_json(
        glossary_qa_path,
        {
            "schema_version": "pali_mock_glossary_qa_v1",
            "reports": {"mock": {"avoid_ko_conflicts": [], "same_segment_signals": [], "cross_term_collisions": [], "untranslated_pali_reclassifications": []}},
        },
        pretty=pretty,
    )
    qa_out_dir.mkdir(parents=True, exist_ok=True)
    cmd = [
        sys.executable,
        "-m",
        "backend.pali.scripts.generate_qa_report",
        "--parsed",
        str(parsed_path),
        "--gold",
        str(gold_path),
        "--glossary-qa",
        str(glossary_qa_path),
        "--out",
        str(qa_out_dir),
    ]
    completed = subprocess.run(cmd, cwd=REPO_ROOT, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, check=False)
    report_path = qa_out_dir / "review_report.md"
    queue_path = qa_out_dir / "review_queue.json"
    run_manifest_path = qa_out_dir / "run_manifest.json"
    if report_path.exists():
        with report_path.open("a", encoding="utf-8") as handle:
            handle.write(
                "\n## Mock QA Dry-Run Note\n\n"
                "mock QA dry-run is not a translation quality signal. It does not evaluate doctrinal correctness, "
                "terminology quality, hallucination, or translation accuracy. It only validates parser/schema/report wiring.\n\n"
                "gold empty is expected: current seed gold entries are disjoint from the 300 pilot selection.\n"
            )
    return {
        "valid": completed.returncode == 0 and report_path.exists() and queue_path.exists() and run_manifest_path.exists(),
        "command": cmd,
        "returncode": completed.returncode,
        "stdout": completed.stdout,
        "stderr": completed.stderr,
        "mock_parsed_path": str(parsed_path),
        "mock_run_manifest_path": str(mock_manifest_path),
        "mock_glossary_qa_path": str(glossary_qa_path),
        "qa_report_path": str(report_path),
        "review_queue_path": str(queue_path),
        "run_manifest_path": str(run_manifest_path),
        "mock": True,
        "quality_signal": False,
        "do_not_use_for_translation_evaluation": True,
        "gold_empty_expected": True,
    }


def run_budget_guardrail_test(
    *,
    budget_usd: Decimal,
    conservative_gate_cost_usd: Decimal,
) -> dict[str, Any]:
    under = can_submit_batch_under_budget(
        BudgetState(Decimal("0"), Decimal("0"), budget_usd),
        min(conservative_gate_cost_usd, budget_usd / Decimal("2")),
    )
    over = can_submit_batch_under_budget(
        BudgetState(Decimal("0"), Decimal("0"), budget_usd),
        budget_usd + Decimal("0.000001"),
    )
    actual = can_submit_batch_under_budget(
        BudgetState(Decimal("0"), Decimal("0"), budget_usd),
        conservative_gate_cost_usd,
    )
    status = "PASS_READY_FOR_USER_APPROVAL" if actual.can_submit else "BLOCKED_OVER_BUDGET"
    return {
        "schema_version": "pali_pilot_300_budget_guardrail_test_v1",
        "valid": under.can_submit and not over.can_submit,
        "budget_usd": str(budget_usd),
        "conservative_gate_cost_usd": str(conservative_gate_cost_usd),
        "actual_gate": {
            "can_submit_under_budget": actual.can_submit,
            "reason": actual.reason.value,
            "status": status,
            "batch_submission_allowed_now": False,
            "requires_user_approval": True,
            "user_approval_received": False,
        },
        "synthetic_under_budget": {"can_submit": under.can_submit, "reason": under.reason.value},
        "synthetic_over_budget": {"can_submit": over.can_submit, "reason": over.reason.value},
    }


def build_readiness(
    *,
    manifest: dict[str, Any],
    identity: dict[str, Any],
    cost_report: dict[str, Any],
    jsonl_result: dict[str, Any],
    source_integrity: dict[str, Any],
    mock_result: dict[str, Any],
    guardrail: dict[str, Any],
    budget_usd: Decimal,
) -> dict[str, Any]:
    conservative = parse_decimal_money(
        cost_report["estimate_totals"]["conservative_gate"]["cost_usd"],
        field_name="estimate_totals.conservative_gate.cost_usd",
    )
    under_budget = conservative <= budget_usd
    blocking = []
    if not under_budget:
        blocking.append("BLOCKED_OVER_BUDGET")
    if not jsonl_result["validation"]["valid"]:
        blocking.append("BLOCKED_JSONL_INVALID")
    if not source_integrity["valid"]:
        blocking.append("BLOCKED_SOURCE_INTEGRITY")
    if not mock_result["valid"]:
        blocking.append("BLOCKED_QA_DRYRUN_FAILED")
    if not guardrail["valid"]:
        blocking.append("BLOCKED_OVER_BUDGET")
    status = "PASS_READY_FOR_USER_APPROVAL" if not blocking else blocking[0]
    mean = cost_report["estimate_totals"]["expected_mean"]
    p90 = cost_report["estimate_totals"]["planning_p90"]
    readiness = {
        "schema_version": "pali_pilot_300_preflight_readiness_v1",
        "run_id": RUN_ID,
        "manifest_valid": True,
        "manifest_sha256": identity["manifest_sha256"],
        "inventory_sha256": identity["inventory_sha256"],
        "source_commit": identity["source_commit"],
        "glossary_sha256": identity.get("glossary_sha256", ""),
        "selection_content_sha256": identity["selection_content_sha256"],
        "expected_selection_sha_match": True,
        "pricing_self_check_passed": cost_report["calibration"]["pricing_self_check"]["pass"],
        "cost_estimate_available": True,
        "jsonl_unsubmitted_generated": True,
        "jsonl_validation_passed": jsonl_result["validation"]["valid"],
        "source_integrity_passed": source_integrity["valid"],
        "mock_qa_dryrun_passed": mock_result["valid"],
        "budget_guardrail_passed": guardrail["valid"] and under_budget,
        "qa_dry_run_plan_available": True,
        "budget_usd": str(budget_usd),
        "estimated_cost_usd_expected_mean": mean["official_cost_usd"],
        "estimated_cost_usd_planning_p90": p90["official_cost_usd"],
        "estimated_cost_usd_conservative_gate": str(conservative),
        "under_budget": under_budget,
        "readiness_status": status,
        "requires_user_approval": True,
        "user_approval_received": False,
        "batch_submission_allowed_now": False,
        "live_smoke_status": "not_run_step_2_excludes_live_calls",
        "recommended_shards": 1,
        "shard_recommendation": {
            "recommended_shards": 1,
            "reason": "estimated cost under cap, 300 requests manageable",
            "alternative": "2 shards if Step 3 operator wants failure isolation",
        },
        "blocking_reasons": blocking,
        "warnings": [
            cost_report["special_slices"].get("s05", {}).get("note", ""),
            "GO status still requires explicit user approval before Step 3 submission.",
            "Live micro-smoke is intentionally not run in Step 2.",
            "Gold empty is expected for mock 300 dry-run because current gold seeds are disjoint from 300.",
        ],
    }
    readiness["decimal_budget_gate"] = decimal_budget_gate_from_readiness(readiness)
    return readiness


def calibration_rows_from_pilot75(payload: dict[str, Any]) -> list[dict[str, Any]]:
    rows = []
    for item in payload.get("items") or []:
        prompt = int(item.get("prompt_token_count") or 0)
        output = int(item.get("candidates_token_count") or 0)
        thinking = int(item.get("thoughts_token_count") or 0)
        if prompt <= 0 or output <= 0:
            continue
        text = item.get("original_text") or ""
        char_count = len(text)
        word_count = len(word_tokens(text))
        unit = source_unit_from_counts(char_count, word_count)
        rows.append(
            {
                **item,
                "source_char_count": char_count,
                "source_word_count": word_count,
                "source_unit": unit,
                "output_ratio": Decimal(output) / unit,
                "thinking_ratio": Decimal(thinking) / unit,
            }
        )
    source_ratio = Decimal("1")
    for row in rows:
        estimated_source = row["source_unit"] * source_ratio
        row["input_overhead"] = max(Decimal("0"), Decimal(int(row["prompt_token_count"])) - estimated_source)
    return rows


def source_ratio_stats_from_prompt_calibration(path: Path) -> dict[tuple[str, ...], RatioStats]:
    if not path.exists():
        return {}
    payload = read_json(path)
    rows = []
    for item in payload.get("sample_results") or []:
        if item.get("status") != "success":
            continue
        source_chars = int(item.get("source_chars") or 0)
        source_tokens = int(item.get("source_text_only_tokens") or 0)
        if source_chars <= 0 or source_tokens <= 0:
            continue
        unit = Decimal(max(source_chars / 5, 1))
        rows.append({**item, "ratio": Decimal(source_tokens) / unit})
    return build_stats_index(rows, "ratio")


def build_ratio_index(rows: list[dict[str, Any]], field: str) -> dict[tuple[str, ...], RatioStats]:
    return build_stats_index(rows, field)


def build_stats_index(rows: list[dict[str, Any]], field: str) -> dict[tuple[str, ...], RatioStats]:
    buckets: dict[tuple[str, ...], list[Decimal]] = defaultdict(list)
    for row in rows:
        for key in bucket_keys(row):
            buckets[key].append(Decimal(row[field]))
    return {key: stats(values) for key, values in buckets.items()}


def bucket_keys(row: dict[str, Any]) -> list[tuple[str, ...]]:
    layer = str(row.get("text_layer") or "unknown")
    length = str(row.get("length_bucket") or "unknown")
    chunk = str(row.get("chunk_type") or "unknown")
    return [
        ("primary", layer, length, chunk),
        ("layer_length", layer, length),
        ("length_chunk", length, chunk),
        ("length", length),
        ("layer", layer),
        ("overall",),
    ]


def primary_bucket_key(item: dict[str, Any]) -> tuple[str, ...]:
    return ("primary", str(item.get("text_layer")), str(item.get("length_bucket")), str(item.get("chunk_type")))


def choose_ratio(item: dict[str, Any], index: dict[tuple[str, ...], RatioStats], mode: str) -> tuple[Decimal, tuple[str, ...], int]:
    for key in bucket_keys(item):
        stat = index.get(key)
        if stat and stat.n >= 5:
            return getattr(stat, mode), key, stat.n
    stat = index.get(("overall",))
    if stat:
        return getattr(stat, mode), ("overall",), stat.n
    return Decimal("1"), ("fallback_constant",), 0


def choose_source_ratio(item: dict[str, Any], index: dict[tuple[str, ...], RatioStats]) -> tuple[Decimal, tuple[str, ...], int]:
    if index:
        value, key, n = choose_ratio(item, index, "median")
        return value, key, n
    return Decimal("1"), ("char_token_proxy",), 0


def stats(values: list[Decimal]) -> RatioStats:
    ordered = sorted(values)
    return RatioStats(
        n=len(ordered),
        mean=sum(ordered, Decimal("0")) / Decimal(len(ordered)),
        median=Decimal(str(statistics.median(ordered))),
        p90=percentile_nearest_rank(ordered, Decimal("0.90")),
    )


def percentile_nearest_rank(values: list[Decimal], percentile: Decimal) -> Decimal:
    if not values:
        return Decimal("0")
    index = int((Decimal(len(values)) * percentile).to_integral_value(rounding=ROUND_HALF_UP)) - 1
    index = max(0, min(index, len(values) - 1))
    return values[index]


def source_unit(item: dict[str, Any]) -> Decimal:
    text = source_text(item)
    return source_unit_from_counts(len(text), len(word_tokens(text)))


def source_unit_from_counts(char_count: int, word_count: int) -> Decimal:
    return Decimal(str(max(word_count, char_count / 5, 1)))


def sum_estimate_items(items: list[dict[str, Any]], field: str) -> dict[str, Any]:
    input_tokens = sum(int(item[field]["input_tokens"]) for item in items)
    output_tokens = sum(int(item[field]["output_tokens"]) for item in items)
    thinking_tokens = sum(int(item[field]["thinking_tokens"]) for item in items)
    official = sum((Decimal(str(item[field]["official_cost_usd"])) for item in items), Decimal("0"))
    return {
        "input_tokens": input_tokens,
        "output_tokens": output_tokens,
        "thinking_tokens": thinking_tokens,
        "official_cost_usd": str(quantize_usd(official)),
    }


def empirical_blended_rate(totals: dict[str, Any]) -> Decimal:
    total_tokens = Decimal(int(totals["input_tokens"]) + int(totals["output_tokens"]) + int(totals["thinking_tokens"]))
    return Decimal(str(totals["actual_cost_usd"])) / total_tokens


def empirical_cost(totals: dict[str, Any], rate: Decimal) -> Decimal:
    total_tokens = Decimal(int(totals["input_tokens"]) + int(totals["output_tokens"]) + int(totals["thinking_tokens"]))
    return quantize_usd(total_tokens * rate)


def build_special_slices(items: list[dict[str, Any]]) -> dict[str, Any]:
    slices = {
        "s05": [item for item in items if item["source_path_prefix"] == "s05"],
        "tika_long": [item for item in items if item["selection_bucket"] == "tika_long"],
        "atthakatha_long": [item for item in items if item["selection_bucket"] == "atthakatha_long"],
        "verse": [item for item in items if item["chunk_type"] == "verse"],
        "long": [item for item in items if item["length_bucket"] == "long"],
        "hard": [item for item in items if item["selection_group"] == "hard"],
        "representative": [item for item in items if item["selection_group"] == "representative"],
        "heading_title_probe": [item for item in items if item["selection_bucket"] == "heading_title_probe"],
        "holdout_candidates": [item for item in items if item.get("gold_candidate")],
    }
    result = {name: summarize_slice(rows) for name, rows in slices.items()}
    result["s05"]["note"] = (
        f"s05 (Khuddaka) is {len(slices['s05'])}/300. This reflects verse/glossary-risk concentration "
        "in Khuddaka and is intentional. Step 2 cost estimate and Step 3 findings must report s05 separately."
    )
    return result


def summarize_slice(rows: list[dict[str, Any]]) -> dict[str, Any]:
    mean = sum_estimate_items(rows, "expected_mean") if rows else {"input_tokens": 0, "output_tokens": 0, "thinking_tokens": 0, "official_cost_usd": "0.000000"}
    p90 = sum_estimate_items(rows, "planning_p90") if rows else {"input_tokens": 0, "output_tokens": 0, "thinking_tokens": 0, "official_cost_usd": "0.000000"}
    return {
        "count": len(rows),
        "expected_mean": mean,
        "planning_p90": p90,
    }


def serialize_bucket_stats(
    output_stats: dict[tuple[str, ...], RatioStats],
    thinking_stats: dict[tuple[str, ...], RatioStats],
    overhead_stats: dict[tuple[str, ...], RatioStats],
) -> dict[str, Any]:
    keys = sorted(set(output_stats) | set(thinking_stats) | set(overhead_stats))
    return {
        str(key): {
            "output": serialize_stat(output_stats.get(key)),
            "thinking": serialize_stat(thinking_stats.get(key)),
            "input_overhead": serialize_stat(overhead_stats.get(key)),
        }
        for key in keys
    }


def serialize_stat(stat: RatioStats | None) -> dict[str, Any] | None:
    if stat is None:
        return None
    return {"n": stat.n, "mean": str(stat.mean), "median": str(stat.median), "p90": str(stat.p90)}


def pricing_self_check(price_profile: PriceProfile) -> dict[str, Any]:
    recomputed = estimate_request_cost(
        TokenEstimate(
            input_tokens=PILOT75_TOTALS["input_tokens"],
            output_tokens=PILOT75_TOTALS["output_tokens"],
            thinking_tokens=PILOT75_TOTALS["thinking_tokens"],
        ),
        price_profile,
    )
    actual = PILOT75_TOTALS["actual_cost_usd"]
    delta = abs(recomputed - actual)
    return {
        "recomputed_cost_usd": str(recomputed),
        "actual_cost_usd": str(actual),
        "delta_usd": str(delta),
        "pass": delta <= Decimal("0.005"),
    }


def parse_decimal_money(value: object, *, field_name: str) -> Decimal:
    try:
        return Decimal(str(value))
    except (InvalidOperation, ValueError, TypeError) as exc:
        raise ValueError(f"invalid decimal money field {field_name}: {value!r}") from exc


def decimal_budget_gate_from_readiness(readiness: dict[str, Any]) -> dict[str, Any]:
    estimated = parse_decimal_money(
        readiness.get("estimated_cost_usd_conservative_gate"),
        field_name="estimated_cost_usd_conservative_gate",
    )
    budget = parse_decimal_money(readiness.get("budget_usd"), field_name="budget_usd")
    under_budget = estimated <= budget
    return {
        "estimated_cost_usd_conservative_gate": str(estimated),
        "budget_usd": str(budget),
        "under_budget": under_budget,
        "status": "PASS_READY_FOR_USER_APPROVAL" if under_budget else "BLOCKED_OVER_BUDGET",
        "comparison": "Decimal(str(value))",
    }


def totals_from_pilot75(payload: dict[str, Any]) -> dict[str, Any]:
    items = payload.get("items") or []
    return {
        "input_tokens": sum(int(item.get("prompt_token_count") or 0) for item in items),
        "output_tokens": sum(int(item.get("candidates_token_count") or 0) for item in items),
        "thinking_tokens": sum(int(item.get("thoughts_token_count") or 0) for item in items),
        "actual_cost_usd": sum((Decimal(str(item.get("actual_cost_usd") or 0)) for item in items), Decimal("0")),
    }


def confidence_from_n(n: int) -> str:
    if n >= 10:
        return "high"
    if n >= 5:
        return "medium"
    return "low"


def build_parser_readiness_status(cost: Decimal, budget: Decimal) -> str:
    return "PASS_READY_FOR_USER_APPROVAL" if cost <= budget else "BLOCKED_OVER_BUDGET"


def index_inventory_by_pair(items: list[dict[str, Any]]) -> dict[tuple[str, str], dict[str, Any]]:
    return {
        (str(item.get("stable_segment_key")), str(item.get("source_text_hash"))): item
        for item in items
        if item.get("stable_segment_key") and item.get("source_text_hash")
    }


def hash_normalized(item: dict[str, Any]) -> str:
    text = item.get("normalized_text") or item.get("original_text") or ""
    return hashlib.sha256(str(text).encode("utf-8")).hexdigest()


def write_jsonl(path: Path, rows: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(json.dumps(row, ensure_ascii=False, sort_keys=True) for row in rows) + "\n", encoding="utf-8")


def read_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def write_json(path: Path, payload: Any, *, pretty: bool = True) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2 if pretty else None, sort_keys=True) + "\n", encoding="utf-8")


def file_sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def quantize_usd(value: Decimal) -> Decimal:
    return value.quantize(Decimal("0.000001"), rounding=ROUND_HALF_UP)


def round_decimal(value: Decimal) -> int:
    return int(value.to_integral_value(rounding=ROUND_HALF_UP))


def now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def render_cost_markdown(report: dict[str, Any]) -> str:
    totals = report["estimate_totals"]
    s05 = report["special_slices"]["s05"]
    return "\n".join(
        [
            "# Pāli 300 Pilot Cost Estimate",
            "",
            "## Purpose",
            "Step 3 제출 전 local-only cost estimate와 preflight gate를 기록한다. Gemini/API/LLM 호출은 없다.",
            "",
            "## Manifest Identity",
            f"- selection_content_sha256: `{report['created_from_manifest']['selection_content_sha256']}`",
            f"- inventory_sha256: `{report['created_from_manifest']['inventory_sha256']}`",
            f"- source_commit: `{report['created_from_manifest']['source_commit']}`",
            "",
            "## 75 Actuals Calibration",
            f"- input/output/thinking: {report['calibration']['input_tokens']} / {report['calibration']['output_tokens']} / {report['calibration']['thinking_tokens']}",
            f"- actual cost: ${report['calibration']['actual_cost_usd']}",
            "",
            "## Pricing Self-Check",
            f"- result: {report['calibration']['pricing_self_check']}",
            "",
            "## Cost Estimate",
            f"- expected mean official cost: ${totals['expected_mean']['official_cost_usd']}",
            f"- planning p90 official cost: ${totals['planning_p90']['official_cost_usd']}",
            f"- conservative gate: ${totals['conservative_gate']['cost_usd']}",
            "",
            "## Bucket Backoff Method",
            "Primary bucket is text_layer × length_bucket × chunk_type. If n < 5, the estimator backs off through layer/length, length/chunk, length, layer, then overall.",
            "",
            "## Special Slices",
            f"- s05: count {s05['count']}, p90 cost ${s05['planning_p90']['official_cost_usd']}",
            f"- heading_title_probe: count {report['special_slices']['heading_title_probe']['count']}",
            f"- hard: count {report['special_slices']['hard']['count']}",
            f"- holdout_candidates: count {report['special_slices']['holdout_candidates']['count']}",
            "",
            "## Known Limitations",
            *[f"- {item}" for item in report["limitations"]],
            "",
            "## Next Step",
            "GO 상태여도 Step 3 제출은 사용자 green-light 전까지 금지. Step 3에서는 JSONL hash, manifest hash, budget readiness를 재검증한 뒤 제출한다.",
            "",
        ]
    )


def render_plan_doc_from_outputs(
    *,
    cost_report: dict[str, Any],
    readiness: dict[str, Any],
    jsonl_result: dict[str, Any],
    source_integrity: dict[str, Any],
    mock_result: dict[str, Any],
    guardrail: dict[str, Any],
) -> str:
    decimal_gate = readiness.get("decimal_budget_gate") or decimal_budget_gate_from_readiness(readiness)
    return "\n".join(
        [
            "# Pāli 300 Pilot Cost And Local Dry-Run Plan",
            "",
            "## Purpose",
            "이 문서는 300 pilot Step 2 local preflight gate의 운영 기준과 산출물을 기록한다.",
            "",
            "## Manifest Identity",
            f"- selection_content_sha256: `{readiness['selection_content_sha256']}`",
            f"- manifest_sha256: `{readiness['manifest_sha256']}`",
            f"- inventory_sha256: `{readiness['inventory_sha256']}`",
            f"- source_commit: `{readiness['source_commit']}`",
            "",
            "## 75 Actuals Calibration",
            "75 pilot actual usage에서 output/thinking ratio를 계산하고, prompt/input overhead는 source token proxy와 분리한다.",
            "",
            "## Pricing Self-Check",
            f"- pass: {readiness['pricing_self_check_passed']}",
            "",
            "## Cost Estimate",
            f"- expected_mean: ${readiness['estimated_cost_usd_expected_mean']}",
            f"- planning_p90: ${readiness['estimated_cost_usd_planning_p90']}",
            f"- conservative_gate: ${readiness['estimated_cost_usd_conservative_gate']}",
            f"- budget_usd: ${readiness['budget_usd']}",
            f"- Decimal budget gate: {decimal_gate['status']} (`{decimal_gate['comparison']}`)",
            "",
            "## Bucket Backoff Method",
            "text_layer × length_bucket × chunk_type bucket이 n < 5이면 parent bucket으로 deterministic backoff한다.",
            "",
            "## Bucket Cost Table",
            "상세 bucket stats는 `pilot_300_v1_cost_estimate.json`의 `bucket_stats`를 기준으로 본다.",
            "",
            "## Special Slices",
            f"- s05: {cost_report['special_slices']['s05']['count']}",
            f"- heading_title_probe: {cost_report['special_slices']['heading_title_probe']['count']}",
            f"- hard: {cost_report['special_slices']['hard']['count']}",
            f"- holdout_candidates: {cost_report['special_slices']['holdout_candidates']['count']}",
            "",
            "## Unsubmitted JSONL Validation",
            f"- passed: {readiness['jsonl_validation_passed']}",
            f"- request_count: {jsonl_result['manifest']['request_count']}",
            f"- submitted: {jsonl_result['manifest']['submitted']}",
            "",
            "## Source Integrity Precheck",
            f"- passed: {readiness['source_integrity_passed']}",
            f"- checked_count: {source_integrity['checked_count']}",
            f"- mismatches: {len(source_integrity['mismatches'])}",
            "",
            "## Mock QA Dry-Run Result",
            f"- passed: {readiness['mock_qa_dryrun_passed']}",
            f"- report_path: `{mock_result['qa_report_path']}`",
            "- mock QA dry-run is not a translation quality signal.",
            "- gold empty is expected because current gold seeds are disjoint from 300.",
            "",
            "## Budget Guardrail Test",
            f"- passed: {readiness['budget_guardrail_passed']}",
            f"- synthetic under-budget: {guardrail['synthetic_under_budget']['can_submit']}",
            f"- synthetic over-budget blocked: {not guardrail['synthetic_over_budget']['can_submit']}",
            f"- actual gate status: {guardrail['actual_gate']['status']}",
            "",
            "## Decimal Budget Parsing",
            "- Cost/readiness JSON의 USD 값은 Decimal-safe string으로 저장될 수 있다.",
            "- 소비자는 `Decimal(str(value))`로 파싱해야 한다.",
            "- 문자열 비교와 float 직접 비교는 금지한다.",
            "- Step 3 제출 직전에는 readiness JSON을 다시 읽고 Decimal budget gate를 재검증한다.",
            "",
            "## Shard Recommendation",
            "- recommended_shards: 1",
            "- alternative: 2 shards if Step 3 operator wants failure isolation.",
            "",
            "## Step 2.5 Live Smoke Plan",
            "- not implemented in Step 2",
            "- separate user approval required",
            "- 3-5 segments only",
            "- hard cap <= $0.50",
            "- generateContent allowed only in Step 2.5",
            "",
            "## GO / NO-GO",
            f"- readiness_status: `{readiness['readiness_status']}`",
            f"- batch_submission_allowed_now: `{str(readiness['batch_submission_allowed_now']).lower()}`",
            f"- requires_user_approval: `{str(readiness['requires_user_approval']).lower()}`",
            f"- user_approval_received: `{str(readiness['user_approval_received']).lower()}`",
            "- GO 상태여도 Step 3 제출은 사용자 green-light 전까지 금지.",
            "",
            "## Known Limitations",
            "- No live provider call is made.",
            "- Cost estimate depends on 75 pilot actuals and bucket backoff.",
            "- Correctness quality is not evaluated in mock QA dry-run.",
            "",
            "## Next Step",
            "GO 상태여도 Step 3 제출은 사용자 green-light 전까지 금지. Step 3에서는 JSONL hash, manifest hash, budget readiness를 재검증한 뒤 제출한다.",
            "",
        ]
    )


def render_plan_doc(cost_report: dict[str, Any], readiness: dict[str, Any]) -> str:
    """Backward-compatible renderer for tests that only need core values."""
    placeholder_jsonl = {"manifest": {"request_count": 0, "submitted": False}}
    placeholder_source = {"checked_count": 0, "mismatches": []}
    placeholder_mock = {"qa_report_path": ""}
    placeholder_guardrail = {
        "synthetic_under_budget": {"can_submit": False},
        "synthetic_over_budget": {"can_submit": False},
        "actual_gate": {"status": readiness.get("readiness_status", "")},
    }
    return render_plan_doc_from_outputs(
        cost_report=cost_report,
        readiness=readiness,
        jsonl_result=placeholder_jsonl,
        source_integrity=placeholder_source,
        mock_result=placeholder_mock,
        guardrail=placeholder_guardrail,
    )


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))

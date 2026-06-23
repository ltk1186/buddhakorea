"""Run Step 4 response_schema A/B smoke preparation and guarded batch modes.

Default execution is local-only dry-run. Real Gemini Batch calls require
``--submit``, and this script never changes production prompts, schema files,
glossary, gold data, translations, or source XML.
"""

from __future__ import annotations

import argparse
import json
import sys
from decimal import Decimal
from pathlib import Path
from typing import Any

REPO_ROOT = Path(__file__).resolve().parents[3]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from backend.pali.scripts.calibrate_gemini_tokens import resolve_gemini_api_key
from backend.pali.scripts.submit_gemini_smoke_batch import (
    DEFAULT_MODEL,
    GeminiBatchRestClient,
    build_inline_request_from_provider_line,
    extract_batch_name,
    extract_inline_result_lines,
    load_price_profile,
    status_snapshot,
)
from backend.pali.translation.response_schema_smoke import (
    DEFAULT_HARD_CAP_USD,
    MAX_REQUESTS_WITHOUT_OVERRIDE,
    build_arm_jsonl,
    build_arm_salvage_report,
    build_response_schema_experiment,
    build_run_manifest,
    build_final_decision,
    compare_arms,
    estimate_step4_cost,
    file_sha256,
    parse_arm_raw_results,
    placeholder_json_outputs,
    read_json,
    read_jsonl,
    render_comparison_markdown,
    render_final_decision_markdown,
    render_recommendation_placeholder,
    render_step5_handoff,
    render_submit_plan,
    select_step4_items,
    sha256_text,
    stable_json_dumps,
    step4_paths,
    summarize_selection_for_stdout,
    operator_decision_payload,
    validate_response_schema_dialect,
    write_json,
    write_jsonl,
)


DEFAULT_OUT = "data/reports/pali/step4_response_schema_smoke"
DEFAULT_PARSED_SALVAGED = "data/reports/pali/pilot_300_batch/pilot_300_batch_parsed_salvaged.json"
DEFAULT_COST_ESTIMATE = "data/pilot_sets/pali/pilot_300_v1_cost_estimate.json"
DEFAULT_JSONL = "data/pilot_sets/pali/pilot_300_v1_batch_unsubmitted.jsonl"
DEFAULT_JSONL_MANIFEST = "data/pilot_sets/pali/pilot_300_v1_batch_unsubmitted_manifest.json"
DEFAULT_PRICE_PROFILE_PATH = "config/pali_batch_price_profiles.example.json"
DEFAULT_PRICE_PROFILE_ID = "official_gemini_3_1_pro_preview_batch_2026_06_13"


class Step4Blocked(RuntimeError):
    def __init__(self, status: str, message: str):
        super().__init__(message)
        self.status = status
        self.message = message


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Step 4 response_schema A/B smoke dry-run and guarded batch modes.")
    mode = parser.add_mutually_exclusive_group()
    mode.add_argument("--dry-run", action="store_true", help="Build local artifacts only. This is the default.")
    mode.add_argument("--estimate-only", action="store_true", help="Build selection/schema/cost only.")
    mode.add_argument("--submit", action="store_true", help="Submit Arm A and Arm B Gemini Batch jobs after cap checks.")
    mode.add_argument("--submit-arm", choices=["A", "B"], help="Submit only one arm. Use B to retry response_schema after Arm A already exists.")
    mode.add_argument("--poll", action="store_true", help="Poll existing provider batch ids from status files or args.")
    mode.add_argument("--fetch", action="store_true", help="Fetch inline results from existing provider batch ids.")
    mode.add_argument("--parse", action="store_true", help="Parse fetched raw result files.")
    mode.add_argument("--compare", action="store_true", help="Compare parsed Arm A and Arm B outputs.")
    mode.add_argument("--finalize", action="store_true", help="Finalize Step 4 with operator decision and Step 5 handoff.")

    parser.add_argument("--out", default=DEFAULT_OUT)
    parser.add_argument("--parsed-salvaged", default=DEFAULT_PARSED_SALVAGED)
    parser.add_argument("--cost-estimate-input", default=DEFAULT_COST_ESTIMATE)
    parser.add_argument("--jsonl", default=DEFAULT_JSONL)
    parser.add_argument("--jsonl-manifest", default=DEFAULT_JSONL_MANIFEST)
    parser.add_argument("--seed", default="step4_response_schema_smoke_v1")
    parser.add_argument("--hard-cap-usd", default=str(DEFAULT_HARD_CAP_USD))
    parser.add_argument("--allow-over-100", action="store_true")
    parser.add_argument("--provider-batch-id-arm-a")
    parser.add_argument("--provider-batch-id-arm-b")
    parser.add_argument("--price-profile-path", default=DEFAULT_PRICE_PROFILE_PATH)
    parser.add_argument("--price-profile-id", default=DEFAULT_PRICE_PROFILE_ID)
    parser.add_argument("--pretty", action="store_true")
    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    try:
        result = run(args)
    except Step4Blocked as exc:
        payload = {"status": exc.status, "message": exc.message}
        print(json.dumps(payload, ensure_ascii=False, sort_keys=True), file=sys.stderr)
        return 2
    print(json.dumps(result, ensure_ascii=False, sort_keys=True))
    return 0


def run(args: argparse.Namespace) -> dict[str, Any]:
    if args.estimate_only:
        return prepare(args, write_all_placeholders=False)
    if args.submit:
        return submit(args, arm=None)
    if args.submit_arm:
        return submit(args, arm=args.submit_arm)
    if args.poll:
        return poll_or_fetch(args, fetch=False)
    if args.fetch:
        return poll_or_fetch(args, fetch=True)
    if args.parse:
        return parse(args)
    if args.compare:
        return compare(args)
    if args.finalize:
        return finalize(args)
    return prepare(args, write_all_placeholders=True)


def prepare(args: argparse.Namespace, *, write_all_placeholders: bool) -> dict[str, Any]:
    out_dir = Path(args.out)
    paths = step4_paths(out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    parsed_salvaged = read_required_json(Path(args.parsed_salvaged), "parsed_salvaged")
    cost_estimate = read_required_json(Path(args.cost_estimate_input), "cost_estimate")
    jsonl_manifest = read_required_json(Path(args.jsonl_manifest), "jsonl_manifest")
    provider_lines = read_jsonl(Path(args.jsonl))
    if not provider_lines:
        raise Step4Blocked("BLOCKED_MISSING_JSONL", f"missing or empty JSONL: {args.jsonl}")

    selection = select_step4_items(
        parsed_salvaged=parsed_salvaged,
        cost_estimate=cost_estimate,
        jsonl_manifest=jsonl_manifest,
        seed=args.seed,
    )
    response_schema = build_response_schema_experiment()
    arm_a, arm_b = build_arm_jsonl(
        selection_manifest=selection,
        provider_lines=provider_lines,
        response_schema_payload=response_schema,
    )
    hard_cap = Decimal(str(args.hard_cap_usd))
    step4_cost = estimate_step4_cost(selection_manifest=selection, hard_cap_usd=hard_cap)

    if selection["selection_readiness"] != "PASS":
        raise Step4Blocked("BLOCKED_SELECTION_INCOMPLETE", "; ".join(selection["readiness_errors"]))
    planned_requests = int(step4_cost["total_request_count"])
    if planned_requests > MAX_REQUESTS_WITHOUT_OVERRIDE and not args.allow_over_100:
        raise Step4Blocked("BLOCKED_TOO_MANY_REQUESTS", f"planned request count {planned_requests} exceeds 100")

    write_json(paths.selection_manifest, selection, pretty=args.pretty)
    write_json(paths.response_schema, response_schema, pretty=args.pretty)
    write_jsonl(paths.arm_a_jsonl, arm_a)
    write_jsonl(paths.arm_b_jsonl, arm_b)
    write_json(paths.cost_estimate, add_input_hashes(step4_cost, args, arm_a, arm_b, response_schema), pretty=args.pretty)
    paths.submit_plan.write_text(
        render_submit_plan(
            out_dir=out_dir,
            selection_manifest=selection,
            cost_estimate=step4_cost,
            arm_a_jsonl=paths.arm_a_jsonl,
            arm_b_jsonl=paths.arm_b_jsonl,
        ),
        encoding="utf-8",
    )
    if write_all_placeholders:
        placeholder_json_outputs(paths, pretty=args.pretty, preserve_provider_status=True)
    arm_state = current_arm_state(paths)
    manifest = build_run_manifest(
        batch_requests_planned=planned_requests,
        cost_estimate=step4_cost,
        submitted=arm_state["submitted"],
        batch_requests_submitted=arm_state["batch_requests_submitted"],
        api_llm_calls=arm_state["batch_requests_submitted"],
        arm_a_status=arm_state["arm_a_status"],
        arm_b_status=arm_state["arm_b_status"],
        arm_a_provider_batch_id=arm_state["arm_a_provider_batch_id"],
        arm_b_provider_batch_id=arm_state["arm_b_provider_batch_id"],
        arm_a_requests_submitted=arm_state["arm_a_requests_submitted"],
        arm_b_requests_submitted=arm_state["arm_b_requests_submitted"],
        remaining_cap_usd=remaining_cap_usd(step4_cost, paths),
        output_paths=output_paths(paths),
        warnings=["dry_run_only_no_api_calls"],
    )
    write_json(paths.run_manifest, manifest, pretty=args.pretty)
    return summarize_selection_for_stdout(selection, step4_cost, paths)


def submit(args: argparse.Namespace, *, arm: str | None) -> dict[str, Any]:
    prep = prepare(args, write_all_placeholders=True)
    paths = step4_paths(Path(args.out))
    cost_estimate = read_json(paths.cost_estimate)
    if not cost_estimate.get("cap_passed_before_submit"):
        raise Step4Blocked("BLOCKED_OVER_HARD_CAP", "cost estimate exceeds Step 4 hard cap")
    total_requests = int(cost_estimate.get("total_request_count") or 0)
    if total_requests > MAX_REQUESTS_WITHOUT_OVERRIDE and not args.allow_over_100:
        raise Step4Blocked("BLOCKED_TOO_MANY_REQUESTS", "more than 100 requests requires --allow-over-100")
    state = current_arm_state(paths)
    if arm is None and state["arm_a_provider_batch_id"]:
        raise Step4Blocked(
            "BLOCKED_ARM_A_ALREADY_SUBMITTED",
            f"Arm A already has provider_batch_id {state['arm_a_provider_batch_id']}; use --submit-arm B for retry.",
        )
    if arm == "A" and state["arm_a_provider_batch_id"]:
        raise Step4Blocked(
            "BLOCKED_ARM_A_ALREADY_SUBMITTED",
            f"Arm A already has provider_batch_id {state['arm_a_provider_batch_id']}.",
        )
    if arm == "B" and state["arm_b_provider_batch_id"]:
        raise Step4Blocked(
            "BLOCKED_ARM_B_ALREADY_SUBMITTED",
            f"Arm B already has provider_batch_id {state['arm_b_provider_batch_id']}.",
        )

    if arm in {None, "B"}:
        validate_arm_b_schema_or_block(paths)
    if arm == "B":
        check_remaining_cap_for_arm_b(cost_estimate, paths)

    credential = resolve_gemini_api_key()
    if not credential:
        raise Step4Blocked("BLOCKED_MISSING_GEMINI_CREDENTIAL", "Gemini credential must be provided by environment or local configured source")
    client = GeminiBatchRestClient(api_key=credential)
    result: dict[str, Any] = {"status": "SUBMIT_ATTEMPTED", "arm_a": None, "arm_b": None}
    submitted = 0
    if arm in {None, "A"}:
        try:
            arm_a_status = submit_arm(paths.arm_a_jsonl, client=client, display_name="pali-step4-response-schema-arm-a", arm="A")
            submitted += len(read_jsonl(paths.arm_a_jsonl))
            write_json(paths.provider_status_arm_a, arm_a_status, pretty=args.pretty)
            result["arm_a"] = arm_a_status
        except RuntimeError as exc:
            status = {"arm": "A", "status": "provider_error", "provider_batch_id": None, "error": str(exc)}
            write_json(paths.provider_status_arm_a, status, pretty=args.pretty)
            result["arm_a"] = status
    else:
        result["arm_a"] = read_json(paths.provider_status_arm_a) if paths.provider_status_arm_a.exists() else {"status": "not_submitted"}
    if arm in {None, "B"}:
        try:
            arm_b_status = submit_arm(paths.arm_b_jsonl, client=client, display_name="pali-step4-response-schema-arm-b", arm="B")
            submitted += len(read_jsonl(paths.arm_b_jsonl))
            write_json(paths.provider_status_arm_b, arm_b_status, pretty=args.pretty)
            result["arm_b"] = arm_b_status
        except RuntimeError as exc:
            status = {
                "arm": "B",
                "status": "provider_rejected_response_schema" if "schema" in str(exc).lower() else "provider_error",
                "provider_batch_id": None,
                "error": str(exc),
            }
            write_json(paths.provider_status_arm_b, status, pretty=args.pretty)
            result["arm_b"] = status
    state_after = current_arm_state(paths)
    manifest = build_run_manifest(
        batch_requests_planned=total_requests,
        batch_requests_submitted=state_after["batch_requests_submitted"],
        api_llm_calls=state_after["batch_requests_submitted"],
        cost_estimate=cost_estimate,
        submitted=state_after["submitted"],
        arm_a_status=state_after["arm_a_status"],
        arm_b_status=state_after["arm_b_status"],
        arm_a_provider_batch_id=state_after["arm_a_provider_batch_id"],
        arm_b_provider_batch_id=state_after["arm_b_provider_batch_id"],
        arm_a_requests_submitted=state_after["arm_a_requests_submitted"],
        arm_b_requests_submitted=state_after["arm_b_requests_submitted"],
        remaining_cap_usd=remaining_cap_usd(cost_estimate, paths),
        output_paths=output_paths(paths),
    )
    write_json(paths.run_manifest, manifest, pretty=args.pretty)
    result["batch_requests_submitted"] = submitted
    result["dry_run"] = prep
    return result


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


def poll_or_fetch(args: argparse.Namespace, *, fetch: bool) -> dict[str, Any]:
    paths = step4_paths(Path(args.out))
    credential = resolve_gemini_api_key()
    if not credential:
        raise Step4Blocked("BLOCKED_MISSING_GEMINI_CREDENTIAL", "Gemini credential is required")
    client = GeminiBatchRestClient(api_key=credential)
    outputs: dict[str, Any] = {"status": "FETCHED" if fetch else "POLLED"}
    for arm, status_path, raw_path, arg_id in (
        ("A", paths.provider_status_arm_a, paths.arm_a_raw_results, args.provider_batch_id_arm_a),
        ("B", paths.provider_status_arm_b, paths.arm_b_raw_results, args.provider_batch_id_arm_b),
    ):
        provider_id = arg_id or provider_batch_id_from_status(status_path)
        if not provider_id:
            outputs[f"arm_{arm.lower()}"] = {"status": "missing_provider_batch_id"}
            continue
        status = client.get_batch(provider_id)
        write_json(status_path, {"arm": arm, "status": "polled", "provider_batch_id": provider_id, "provider_status": status_snapshot(status), "raw_provider_status": status}, pretty=args.pretty)
        if fetch:
            rows = extract_inline_result_lines(status)
            write_jsonl(raw_path, rows)
            outputs[f"arm_{arm.lower()}"] = {"provider_batch_id": provider_id, "raw_result_count": len(rows)}
        else:
            outputs[f"arm_{arm.lower()}"] = {"provider_batch_id": provider_id, "provider_status": status_snapshot(status)}
    return outputs


def parse(args: argparse.Namespace) -> dict[str, Any]:
    paths = step4_paths(Path(args.out))
    selection = read_json(paths.selection_manifest)
    price_profile, _ = load_price_profile(args.price_profile_path, args.price_profile_id)
    arm_a = parse_arm_raw_results(
        raw_lines=read_jsonl(paths.arm_a_raw_results),
        provider_lines=read_jsonl(paths.arm_a_jsonl),
        selection_manifest=selection,
        price_profile=price_profile,
        arm="A",
    )
    arm_b = parse_arm_raw_results(
        raw_lines=read_jsonl(paths.arm_b_raw_results),
        provider_lines=read_jsonl(paths.arm_b_jsonl),
        selection_manifest=selection,
        price_profile=price_profile,
        arm="B",
    )
    write_json(paths.arm_a_parsed, arm_a, pretty=args.pretty)
    write_json(paths.arm_b_parsed, arm_b, pretty=args.pretty)
    write_json(paths.arm_a_salvage_report, build_arm_salvage_report(arm_a), pretty=args.pretty)
    write_json(paths.arm_b_salvage_report, build_arm_salvage_report(arm_b), pretty=args.pretty)
    return {"status": "PARSED", "arm_a_items": len(arm_a["items"]), "arm_b_items": len(arm_b["items"])}


def compare(args: argparse.Namespace) -> dict[str, Any]:
    paths = step4_paths(Path(args.out))
    arm_a = read_json(paths.arm_a_parsed)
    arm_b = read_json(paths.arm_b_parsed)
    comparison = compare_arms(arm_a, arm_b)
    write_json(paths.comparison_report, comparison, pretty=args.pretty)
    paths.comparison_report_md.write_text(render_comparison_markdown(comparison), encoding="utf-8")
    rec = comparison.get("recommendation", {})
    paths.recommendation.write_text(
        "# Step 4 Recommendation\n\n"
        f"- decision: `{rec.get('decision')}`\n"
        f"- reason: {rec.get('reason')}\n\n"
        "This is a recommendation only and does not change production behavior.\n",
        encoding="utf-8",
    )
    return {"status": "COMPARED", "recommendation": rec}


def finalize(args: argparse.Namespace) -> dict[str, Any]:
    paths = step4_paths(Path(args.out))
    comparison = read_json(paths.comparison_report)
    decision = build_final_decision(comparison)
    comparison["operator_decision"] = operator_decision_payload()
    write_json(paths.comparison_report, comparison, pretty=args.pretty)
    paths.comparison_report_md.write_text(render_comparison_markdown(comparison), encoding="utf-8")
    write_json(paths.final_decision_json, decision, pretty=args.pretty)
    paths.final_decision_md.write_text(render_final_decision_markdown(decision), encoding="utf-8")
    paths.step5_handoff.write_text(render_step5_handoff(), encoding="utf-8")
    paths.recommendation.write_text(render_final_recommendation(comparison, decision), encoding="utf-8")
    run_manifest = read_json(paths.run_manifest) if paths.run_manifest.exists() else {}
    output_paths_payload = dict(run_manifest.get("output_paths") or {})
    output_paths_payload.update(
        {
            "final_decision_json": str(paths.final_decision_json),
            "final_decision_md": str(paths.final_decision_md),
            "step5_handoff": str(paths.step5_handoff),
        }
    )
    run_manifest.update(
        {
            "step4_finalized": True,
            "operator_decision": decision["operator_decision"],
            "response_schema_default_for_1000": True,
            "salvage_cascade_fallback": True,
            "fatal_content_suppression_detected": False,
            "warning_optional_array_changes_detected": True,
            "gold_accuracy_available": False,
            "silver_canary_status": "advisory_only_not_gold_accuracy",
            "silver_canary_needs_pali_expert_policy": "needs_review_not_fail",
            "prompt_mutation": False,
            "glossary_mutation": False,
            "gold_set_mutation": False,
            "schema_file_mutation": False,
            "translation_corpus_mutation": False,
            "production_prompt_changed": False,
            "holdout_gold_frozen": False,
            "output_paths": output_paths_payload,
        }
    )
    write_json(paths.run_manifest, run_manifest, pretty=args.pretty)
    return {
        "status": "STEP4_FINALIZED",
        "operator_decision": decision["operator_decision"],
        "final_decision": str(paths.final_decision_json),
        "step5_handoff": str(paths.step5_handoff),
    }


def render_final_recommendation(comparison: dict[str, Any], decision: dict[str, Any]) -> str:
    automatic = comparison.get("recommendation") or {}
    operator = comparison.get("operator_decision") or {}
    return "\n".join(
        [
            "# Step 4 Recommendation",
            "",
            "## Automatic Recommendation",
            "",
            f"- automatic_recommendation: `{automatic.get('decision')}`",
            f"- reason: {automatic.get('reason')}",
            "",
            "## Operator Reviewed Decision",
            "",
            f"- operator_reviewed_decision: `{operator.get('decision')}`",
            f"- reason: {operator.get('reason')}",
            "",
            "The automatic recommendation treated any optional-array content impact flag as blocking. Manual review found no fatal truncation, no empty translations, no major literal/natural suppression, and no large terms drop. The optional-array changes are retained as QA warnings, not adoption blockers.",
            "",
            "## Final Policy",
            "",
            f"- response_schema_default_for_1000: `{decision['response_schema_default_for_1000']}`",
            f"- salvage_cascade_fallback: `{decision['salvage_cascade_fallback']}`",
            f"- gold_accuracy_available: `{decision['gold_accuracy_available']}`",
            f"- silver_canary_status: `{decision['silver_canary_status']}`",
        ]
    ) + "\n"


def add_input_hashes(
    cost_estimate: dict[str, Any],
    args: argparse.Namespace,
    arm_a: list[dict[str, Any]],
    arm_b: list[dict[str, Any]],
    response_schema: dict[str, Any],
) -> dict[str, Any]:
    enriched = dict(cost_estimate)
    enriched["input_files"] = {
        "parsed_salvaged": {"path": args.parsed_salvaged, "sha256": file_sha256(Path(args.parsed_salvaged))},
        "cost_estimate_input": {"path": args.cost_estimate_input, "sha256": file_sha256(Path(args.cost_estimate_input))},
        "jsonl": {"path": args.jsonl, "sha256": file_sha256(Path(args.jsonl))},
        "jsonl_manifest": {"path": args.jsonl_manifest, "sha256": file_sha256(Path(args.jsonl_manifest))},
    }
    enriched["arm_a_jsonl_sha256"] = sha256_text("\n".join(json.dumps(row, ensure_ascii=False) for row in arm_a) + "\n")
    enriched["arm_b_jsonl_sha256"] = sha256_text("\n".join(json.dumps(row, ensure_ascii=False) for row in arm_b) + "\n")
    enriched["response_schema_sha256"] = sha256_text(stable_json_dumps(response_schema))
    return enriched


def output_paths(paths: Any) -> dict[str, str]:
    return {name: str(value) for name, value in paths.__dict__.items() if name != "out_dir"}


def read_required_json(path: Path, label: str) -> dict[str, Any]:
    if not path.exists():
        raise Step4Blocked(f"BLOCKED_MISSING_{label.upper()}", f"missing input: {path}")
    return read_json(path)


def provider_batch_id_from_status(path: Path) -> str | None:
    if not path.exists():
        return None
    data = read_json(path)
    return data.get("provider_batch_id")


def current_arm_state(paths: Any) -> dict[str, Any]:
    arm_a = read_json(paths.provider_status_arm_a) if paths.provider_status_arm_a.exists() else {}
    arm_b = read_json(paths.provider_status_arm_b) if paths.provider_status_arm_b.exists() else {}
    arm_a_provider_id = arm_a.get("provider_batch_id")
    arm_b_provider_id = arm_b.get("provider_batch_id")
    arm_a_submitted = 50 if arm_a_provider_id else 0
    arm_b_submitted = 50 if arm_b_provider_id else 0
    return {
        "submitted": bool(arm_a_provider_id or arm_b_provider_id),
        "batch_requests_submitted": arm_a_submitted + arm_b_submitted,
        "arm_a_status": arm_a.get("status") or ("submitted" if arm_a_provider_id else "not_submitted"),
        "arm_b_status": arm_b.get("status") or ("submitted" if arm_b_provider_id else "not_submitted"),
        "arm_a_provider_batch_id": arm_a_provider_id,
        "arm_b_provider_batch_id": arm_b_provider_id,
        "arm_a_requests_submitted": arm_a_submitted,
        "arm_b_requests_submitted": arm_b_submitted,
    }


def validate_arm_b_schema_or_block(paths: Any) -> None:
    provider_lines = read_jsonl(paths.arm_b_jsonl)
    schemas = []
    for line in provider_lines:
        schema = (
            line.get("request", {})
            .get("generation_config", {})
            .get("response_schema")
        )
        if schema:
            schemas.append(schema)
    if not schemas:
        raise Step4Blocked("BLOCKED_MISSING_RESPONSE_SCHEMA", "Arm B JSONL does not contain response_schema")
    for schema in schemas:
        guard = validate_response_schema_dialect(schema)
        if not guard["valid"]:
            report = {
                "status": "BLOCKED_UNSUPPORTED_RESPONSE_SCHEMA_KEYWORD",
                **guard,
            }
            write_json(paths.provider_status_arm_b, {"arm": "B", **report}, pretty=True)
            raise Step4Blocked("BLOCKED_UNSUPPORTED_RESPONSE_SCHEMA_KEYWORD", json.dumps(report, ensure_ascii=False))


def check_remaining_cap_for_arm_b(cost_estimate: dict[str, Any], paths: Any) -> None:
    arm_b_estimate = Decimal(str(cost_estimate.get("arm_b", {}).get("planning_p90", {}).get("official_cost_usd") or "0"))
    remaining = Decimal(remaining_cap_usd(cost_estimate, paths))
    if arm_b_estimate > remaining:
        raise Step4Blocked(
            "BLOCKED_REMAINING_CAP_EXCEEDED",
            f"Arm B p90 estimate {arm_b_estimate} exceeds remaining cap {remaining}",
        )


def remaining_cap_usd(cost_estimate: dict[str, Any], paths: Any) -> str:
    hard_cap = Decimal(str(cost_estimate.get("hard_cap_usd") or "4"))
    arm_a_estimate = Decimal(str(cost_estimate.get("arm_a", {}).get("planning_p90", {}).get("official_cost_usd") or "0"))
    arm_a_actual = known_arm_actual_cost(paths.arm_a_parsed)
    reserved = max(arm_a_estimate, arm_a_actual)
    remaining = hard_cap - reserved
    if remaining < 0:
        remaining = Decimal("0")
    return str(remaining.quantize(Decimal("0.000001")))


def known_arm_actual_cost(parsed_path: Path) -> Decimal:
    if not parsed_path.exists():
        return Decimal("0")
    try:
        data = read_json(parsed_path)
    except Exception:
        return Decimal("0")
    return sum((Decimal(str(item.get("actual_cost_usd") or "0")) for item in data.get("items") or []), Decimal("0"))


if __name__ == "__main__":
    raise SystemExit(main())

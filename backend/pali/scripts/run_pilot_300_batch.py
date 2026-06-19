"""Pilot 300 Gemini Batch execution harness.

Codex must not run submit/poll/fetch modes for the real pilot. This script is
provided so the operator can run them from a local terminal. Dry-run is local
only and performs no provider calls.
"""

from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
from dataclasses import dataclass
from datetime import datetime, timezone
from decimal import Decimal, InvalidOperation, ROUND_HALF_UP
from pathlib import Path
from typing import Any

REPO_ROOT = Path(__file__).resolve().parents[3]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from backend.pali.scripts.build_pilot_300_manifest import selection_content_sha256
from backend.pali.scripts.submit_gemini_smoke_batch import (
    GeminiBatchRestClient,
    build_inline_request_from_provider_line,
    extract_batch_name,
    extract_inline_result_lines,
    parse_batch_results,
    status_snapshot,
    write_raw_results,
)
from backend.pali.translation.budget import (
    PriceProfile,
    TokenEstimate,
    actual_cost_from_usage,
    estimate_request_cost,
    parse_usage_metadata,
)


RUN_ID = "pilot_300_v1_batch"
SCRIPT_VERSION = "pilot_300_batch_harness_v1"
DEFAULT_MODEL = "models/gemini-3.1-pro-preview"
DEFAULT_GLOSSARY_QA = "data/reports/pali/translation_qa_v1_1_baseline_49bc869.json"
DEFAULT_GOLD = "data/gold_set.json"
ENV_CANDIDATES = (
    "GEMINI_API_KEY",
    "GOOGLE_API_KEY",
    "GOOGLE_GENAI_API_KEY",
    "PALI_GEMINI_API_KEY",
)
TERMINAL_STATES = {
    "BATCH_STATE_SUCCEEDED",
    "BATCH_STATE_FAILED",
    "BATCH_STATE_CANCELLED",
    "BATCH_STATE_EXPIRED",
    "SUCCEEDED",
    "FAILED",
    "CANCELLED",
    "EXPIRED",
}
PRICE_PROFILE = PriceProfile(
    input_usd_per_million_tokens=Decimal("1.0"),
    output_usd_per_million_tokens=Decimal("6.0"),
    thinking_usd_per_million_tokens=Decimal("6.0"),
)


@dataclass(frozen=True)
class BatchPaths:
    out_dir: Path
    dry_run: Path
    submit_plan: Path
    run_manifest: Path
    sentinel: Path
    in_progress_lock: Path
    provider_status: Path
    raw_results: Path
    parsed: Path
    summary_json: Path
    summary_md: Path


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    try:
        result = run(args)
    except RuntimeError as exc:
        print(json.dumps({"status": "ERROR", "message": str(exc)}, ensure_ascii=False, sort_keys=True), file=sys.stderr)
        return 2
    print(json.dumps(result, ensure_ascii=False, sort_keys=True))
    if str(result.get("status", "")).startswith("BLOCKED") or result.get("status") == "ERROR":
        return 2
    return 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Pali 300 Gemini Batch harness with double-submit protection."
    )
    parser.add_argument("--mode", required=True, choices=["dry-run", "submit", "poll", "fetch", "parse", "qa", "full-after-submit"])
    parser.add_argument("--manifest")
    parser.add_argument("--readiness")
    parser.add_argument("--smoke-results")
    parser.add_argument("--jsonl")
    parser.add_argument("--jsonl-manifest")
    parser.add_argument("--cost-estimate")
    parser.add_argument("--source-integrity")
    parser.add_argument("--batch-run-manifest")
    parser.add_argument("--provider-batch-id")
    parser.add_argument("--raw-results")
    parser.add_argument("--parsed")
    parser.add_argument("--summary")
    parser.add_argument("--out", required=True)
    parser.add_argument("--qa-out")
    parser.add_argument("--gold", default=DEFAULT_GOLD)
    parser.add_argument("--glossary-qa", default=DEFAULT_GLOSSARY_QA)
    parser.add_argument("--expected-selection-sha")
    parser.add_argument("--budget-usd", default="20")
    parser.add_argument("--model", default=DEFAULT_MODEL)
    parser.add_argument("--enable-submit", action="store_true")
    parser.add_argument("--user-green-light", action="store_true")
    parser.add_argument("--timeout-seconds", type=int, default=60)
    parser.add_argument("--pretty", action="store_true")
    return parser


def run(args: argparse.Namespace, *, client: GeminiBatchRestClient | None = None) -> dict[str, Any]:
    paths = batch_paths(Path(args.out))
    paths.out_dir.mkdir(parents=True, exist_ok=True)
    mode = args.mode
    if mode == "dry-run":
        return dry_run(args, paths)
    if mode == "submit":
        return submit(args, paths, client=client)
    if mode == "poll":
        return poll(args, paths, client=client)
    if mode == "fetch":
        return fetch(args, paths, client=client)
    if mode == "parse":
        return parse(args, paths)
    if mode == "qa":
        return qa(args, paths)
    if mode == "full-after-submit":
        submit_result = submit(args, paths, client=client)
        if not submit_result.get("status", "").startswith("SUBMITTED"):
            return submit_result
        return {"status": "SUBMITTED_FULL_AFTER_SUBMIT_REQUIRES_OPERATOR_POLL", "submit": submit_result}
    raise RuntimeError(f"unsupported mode: {mode}")


def dry_run(args: argparse.Namespace, paths: BatchPaths) -> dict[str, Any]:
    artifacts = load_required_artifacts(args)
    gate = pre_submit_gate(args, artifacts, paths, require_submit_flags=False)
    status = "DRY_RUN_PASS" if not gate["blocking_reasons"] else gate["blocking_reasons"][0]
    run_manifest = build_run_manifest(args, artifacts, paths, mode="dry-run", submitted=False, provider_batch_id=None, provider_status=None, credential_present=False, gate=gate)
    atomic_write_json(paths.run_manifest, run_manifest, pretty=args.pretty)
    dry_run_payload = {
        "schema_version": "pali_pilot_300_batch_dry_run_v1",
        "run_id": RUN_ID,
        "status": status,
        "pre_submit_gate": gate,
        "batch_submission_allowed_now": False,
        "double_submit_guard": double_submit_state(paths),
        "artifact_paths": output_paths(paths, args),
    }
    atomic_write_json(paths.dry_run, dry_run_payload, pretty=args.pretty)
    paths.submit_plan.write_text(render_submit_plan(dry_run_payload), encoding="utf-8")
    return {"status": status, "dry_run": str(paths.dry_run), "submit_plan": str(paths.submit_plan), "blocking_reasons": gate["blocking_reasons"]}


def submit(
    args: argparse.Namespace,
    paths: BatchPaths,
    *,
    client: GeminiBatchRestClient | None = None,
) -> dict[str, Any]:
    artifacts = load_required_artifacts(args)
    credential = resolve_env_credential()
    gate = pre_submit_gate(args, artifacts, paths, require_submit_flags=True, credential_present=credential is not None)
    if gate["blocking_reasons"]:
        payload = {"status": gate["blocking_reasons"][0], "blocking_reasons": gate["blocking_reasons"], "instruction": recovery_instruction(paths)}
        atomic_write_json(paths.dry_run, {"schema_version": "pali_pilot_300_batch_submit_blocked_v1", **payload}, pretty=args.pretty)
        return payload
    if credential is None:
        return {"status": "BLOCKED_MISSING_GEMINI_CREDENTIAL", "blocking_reasons": ["BLOCKED_MISSING_GEMINI_CREDENTIAL"]}
    acquire_submit_lock(paths)
    try:
        if client is None:
            client = GeminiBatchRestClient(api_key=credential["value"], timeout_seconds=args.timeout_seconds)
        requests = [build_inline_request_from_provider_line(line) for line in artifacts["jsonl_lines"]]
        create_response = client.create_inline_batch(
            model=args.model,
            requests=requests,
            display_name="pali-pilot-300-v1",
        )
        provider_batch_id = extract_batch_name(create_response)
        if not provider_batch_id:
            raise RuntimeError("Gemini Batch create response did not include provider_batch_id")
        provider_status = status_snapshot(create_response)
        run_manifest = build_run_manifest(
            args,
            artifacts,
            paths,
            mode="submit",
            submitted=True,
            provider_batch_id=provider_batch_id,
            provider_status=provider_status,
            credential_present=True,
            gate=gate,
            submitted_at=now_iso(),
        )
        atomic_write_json(paths.run_manifest, run_manifest, pretty=args.pretty)
        atomic_write_json(
            paths.sentinel,
            {"provider_batch_id": provider_batch_id, "selection_content_sha256": artifacts["selection_sha"], "submitted_at": run_manifest["submitted_at"]},
            pretty=args.pretty,
        )
        atomic_write_json(paths.provider_status, create_response, pretty=args.pretty)
        return {"status": "SUBMITTED_PROVIDER_BATCH_ID_RECORDED", "provider_batch_id": provider_batch_id, "run_manifest": str(paths.run_manifest)}
    finally:
        release_submit_lock(paths)


def poll(args: argparse.Namespace, paths: BatchPaths, *, client: GeminiBatchRestClient | None = None) -> dict[str, Any]:
    provider_batch_id = provider_batch_id_from_args(args, paths)
    credential = resolve_env_credential()
    if credential is None and client is None:
        return {"status": "BLOCKED_MISSING_GEMINI_CREDENTIAL", "blocking_reasons": ["BLOCKED_MISSING_GEMINI_CREDENTIAL"]}
    if client is None:
        client = GeminiBatchRestClient(api_key=credential["value"], timeout_seconds=args.timeout_seconds)
    status = client.get_batch(provider_batch_id)
    atomic_write_json(paths.provider_status, status, pretty=args.pretty)
    update_run_manifest_status(paths, args, provider_batch_id, status, mode="poll")
    return {"status": "POLL_STATUS_WRITTEN", "provider_batch_id": provider_batch_id, "provider_status": status_snapshot(status)}


def fetch(args: argparse.Namespace, paths: BatchPaths, *, client: GeminiBatchRestClient | None = None) -> dict[str, Any]:
    provider_batch_id = provider_batch_id_from_args(args, paths)
    credential = resolve_env_credential()
    if credential is None and client is None:
        return {"status": "BLOCKED_MISSING_GEMINI_CREDENTIAL", "blocking_reasons": ["BLOCKED_MISSING_GEMINI_CREDENTIAL"]}
    if client is None:
        client = GeminiBatchRestClient(api_key=credential["value"], timeout_seconds=args.timeout_seconds)
    status = client.get_batch(provider_batch_id)
    inline_results = extract_inline_result_lines(status)
    write_raw_results(paths.raw_results, inline_results, status)
    atomic_write_json(paths.provider_status, status, pretty=args.pretty)
    update_run_manifest_status(paths, args, provider_batch_id, status, mode="fetch")
    return {"status": "FETCH_RAW_RESULTS_WRITTEN", "provider_batch_id": provider_batch_id, "raw_results": str(paths.raw_results), "result_count": len(inline_results)}


def parse(args: argparse.Namespace, paths: BatchPaths) -> dict[str, Any]:
    run_manifest = load_run_manifest(args, paths)
    jsonl_path = Path(run_manifest["input_files"]["jsonl"]["path"])
    jsonl_manifest_path = Path(run_manifest["input_files"]["jsonl_manifest"]["path"])
    raw_path = Path(args.raw_results) if args.raw_results else paths.raw_results
    provider_lines = read_jsonl(jsonl_path)
    sidecar = read_json(jsonl_manifest_path)
    raw_lines = read_jsonl(raw_path) if raw_path.suffix == ".jsonl" else []
    parsed = parse_batch_results(
        raw_lines=raw_lines,
        provider_lines=provider_lines,
        manifest=sidecar,
        price_profile=PRICE_PROFILE,
    )
    provider_batch_id = run_manifest.get("provider_batch_id") or args.provider_batch_id or ""
    adapted_items = [adapt_parsed_item(item, provider_batch_id=provider_batch_id) for item in parsed.get("items") or []]
    parsed_payload = {"schema_version": "pali_pilot_300_batch_parsed_v1", "provider_batch_id": provider_batch_id, "items": adapted_items}
    atomic_write_json(paths.parsed, parsed_payload, pretty=args.pretty)
    summary = build_batch_summary(parsed_payload, run_manifest)
    atomic_write_json(paths.summary_json, summary, pretty=args.pretty)
    paths.summary_md.write_text(render_summary_md(summary), encoding="utf-8")
    return {"status": "PARSED", "parsed": str(paths.parsed), "summary": str(paths.summary_json), "provider_batch_id": provider_batch_id}


def qa(args: argparse.Namespace, paths: BatchPaths) -> dict[str, Any]:
    parsed_path = Path(args.parsed) if args.parsed else paths.parsed
    qa_out = Path(args.qa_out) if args.qa_out else Path("data/qa_reports/pali/qa_report_300_live")
    qa_out.mkdir(parents=True, exist_ok=True)
    glossary_qa_path = Path(args.glossary_qa)
    if not glossary_qa_path.exists():
        placeholder = paths.out_dir / "pilot_300_batch_placeholder_glossary_qa.json"
        atomic_write_json(
            placeholder,
            {"schema_version": "pali_placeholder_glossary_qa_v1", "reports": {"batch_300": {}}},
            pretty=args.pretty,
        )
        glossary_qa_path = placeholder
    cmd = [
        sys.executable,
        "-m",
        "backend.pali.scripts.generate_qa_report",
        "--parsed",
        str(parsed_path),
        "--gold",
        args.gold,
        "--glossary-qa",
        str(glossary_qa_path),
        "--out",
        str(qa_out),
    ]
    completed = subprocess.run(cmd, cwd=REPO_ROOT, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, check=False)
    return {
        "status": "QA_COMPLETE" if completed.returncode == 0 else "QA_FAILED",
        "qa_out": str(qa_out),
        "returncode": completed.returncode,
        "stdout": completed.stdout,
        "stderr": completed.stderr,
    }


def pre_submit_gate(
    args: argparse.Namespace,
    artifacts: dict[str, Any],
    paths: BatchPaths,
    *,
    require_submit_flags: bool,
    credential_present: bool = False,
) -> dict[str, Any]:
    reasons: list[str] = []
    warnings: list[str] = []
    if require_submit_flags and not args.enable_submit:
        reasons.append("BLOCKED_SUBMIT_NOT_ENABLED")
    if require_submit_flags and not args.user_green_light:
        reasons.append("BLOCKED_USER_GREEN_LIGHT_REQUIRED")
    if require_submit_flags and not credential_present:
        reasons.append("BLOCKED_MISSING_GEMINI_CREDENTIAL")
    already = existing_submission(paths)
    if already:
        reasons.append("BLOCKED_ALREADY_SUBMITTED")
    if artifacts["readiness"].get("readiness_status") != "PASS_READY_FOR_USER_APPROVAL":
        reasons.append("BLOCKED_READINESS_NOT_PASS")
    if artifacts["readiness"].get("batch_submission_allowed_now") is not False:
        reasons.append("BLOCKED_UNSAFE_BATCH_FLAG")
    smoke = artifacts["smoke"]
    if smoke.get("status") != "PASS":
        reasons.append("BLOCKED_SMOKE_NOT_PASS")
    if int(smoke.get("sample_count_succeeded") or 0) < 3 or int(smoke.get("schema_valid_count") or 0) != int(smoke.get("sample_count_attempted") or 0) or int(smoke.get("parse_failed_count") or 0) != 0:
        reasons.append("BLOCKED_SMOKE_SCHEMA_OR_PARSE_FAILURE")
    if artifacts["source_integrity"].get("valid") is not True:
        reasons.append("BLOCKED_SOURCE_INTEGRITY")
    if args.expected_selection_sha and artifacts["selection_sha"] != args.expected_selection_sha:
        reasons.append("BLOCKED_HASH_MISMATCH")
    if artifacts["jsonl_sha256"] != artifacts["jsonl_manifest"].get("jsonl_sha256"):
        reasons.append("BLOCKED_JSONL_HASH_MISMATCH")
    if int(artifacts["jsonl_manifest"].get("request_count") or 0) != 300 or len(artifacts["jsonl_lines"]) != 300:
        reasons.append("BLOCKED_JSONL_COUNT_MISMATCH")
    budget = parse_decimal(args.budget_usd, "budget_usd")
    gate_cost = parse_decimal(artifacts["cost"]["estimate_totals"]["conservative_gate"]["cost_usd"], "conservative_gate_cost_usd")
    if budget > Decimal("20") or gate_cost > budget:
        reasons.append("BLOCKED_OVER_BUDGET")
    observed_versions = [normalize_model_name(str(value)) for value in smoke.get("observed_model_versions") or []]
    requested = normalize_model_name(args.model)
    if observed_versions and requested not in observed_versions:
        warnings.append("model_version_drift_after_normalization")
    elif "model_version_drift" in (smoke.get("warnings") or []):
        warnings.append("model_version_drift_false_positive_prefix_only")
    return {
        "valid": not reasons,
        "blocking_reasons": sorted(set(reasons), key=reasons.index),
        "warnings": warnings,
        "existing_submission": already,
        "selection_content_sha256": artifacts["selection_sha"],
        "jsonl_sha256": artifacts["jsonl_sha256"],
        "jsonl_request_count": len(artifacts["jsonl_lines"]),
        "budget_usd": str(budget),
        "estimated_cost_usd_conservative_gate": str(gate_cost),
        "batch_submission_allowed_now_from_step2": artifacts["readiness"].get("batch_submission_allowed_now"),
        "smoke_status": smoke.get("status"),
    }


def load_required_artifacts(args: argparse.Namespace) -> dict[str, Any]:
    required = {
        "manifest": args.manifest,
        "readiness": args.readiness,
        "smoke": args.smoke_results,
        "jsonl": args.jsonl,
        "jsonl_manifest": args.jsonl_manifest,
        "cost": args.cost_estimate,
        "source_integrity": args.source_integrity,
    }
    missing = [name for name, path in required.items() if not path or not Path(path).exists()]
    if missing:
        raise RuntimeError(f"missing required artifact(s): {', '.join(missing)}")
    manifest = read_json(Path(args.manifest))
    return {
        "manifest": manifest,
        "readiness": read_json(Path(args.readiness)),
        "smoke": read_json(Path(args.smoke_results)),
        "jsonl_lines": read_jsonl(Path(args.jsonl)),
        "jsonl_manifest": read_json(Path(args.jsonl_manifest)),
        "cost": read_json(Path(args.cost_estimate)),
        "source_integrity": read_json(Path(args.source_integrity)),
        "selection_sha": selection_content_sha256(manifest),
        "manifest_sha256": file_sha256(Path(args.manifest)),
        "jsonl_sha256": file_sha256(Path(args.jsonl)),
    }


def build_run_manifest(
    args: argparse.Namespace,
    artifacts: dict[str, Any],
    paths: BatchPaths,
    *,
    mode: str,
    submitted: bool,
    provider_batch_id: str | None,
    provider_status: dict[str, Any] | None,
    credential_present: bool,
    gate: dict[str, Any],
    submitted_at: str | None = None,
) -> dict[str, Any]:
    now = now_iso()
    return {
        "schema_version": "pali_pilot_300_batch_run_manifest_v1",
        "run_id": RUN_ID,
        "mode": mode,
        "submitted": submitted,
        "provider_batch_id": provider_batch_id,
        "provider_status": provider_status,
        "selection_content_sha256": artifacts["selection_sha"],
        "manifest_sha256": artifacts["manifest_sha256"],
        "jsonl_sha256": artifacts["jsonl_sha256"],
        "jsonl_request_count": len(artifacts["jsonl_lines"]),
        "readiness_status": artifacts["readiness"].get("readiness_status"),
        "smoke_status": artifacts["smoke"].get("status"),
        "budget_usd": str(parse_decimal(args.budget_usd, "budget_usd")),
        "estimated_cost_usd_conservative_gate": artifacts["cost"]["estimate_totals"]["conservative_gate"]["cost_usd"],
        "credential_source": "environment_variable",
        "credential_present": credential_present,
        "credential_value_logged": False,
        "batch_submission_allowed_by_cli": bool(args.enable_submit and args.user_green_light),
        "batch_submission_allowed_now_from_step2": artifacts["readiness"].get("batch_submission_allowed_now"),
        "created_at": now,
        "updated_at": now,
        "submitted_at": submitted_at,
        "pre_submit_gate": gate,
        "input_files": {
            "manifest": file_record(Path(args.manifest)),
            "readiness": file_record(Path(args.readiness)),
            "smoke_results": file_record(Path(args.smoke_results)),
            "jsonl": file_record(Path(args.jsonl)),
            "jsonl_manifest": file_record(Path(args.jsonl_manifest)),
            "cost_estimate": file_record(Path(args.cost_estimate)),
            "source_integrity": file_record(Path(args.source_integrity)),
        },
        "output_paths": output_paths(paths, args),
    }


def existing_submission(paths: BatchPaths) -> dict[str, Any] | None:
    if paths.run_manifest.exists():
        try:
            data = read_json(paths.run_manifest)
        except json.JSONDecodeError:
            data = {}
        if data.get("provider_batch_id"):
            return {"source": str(paths.run_manifest), "provider_batch_id": data["provider_batch_id"]}
    if paths.sentinel.exists():
        try:
            data = read_json(paths.sentinel)
        except json.JSONDecodeError:
            data = {}
        if data.get("provider_batch_id"):
            return {"source": str(paths.sentinel), "provider_batch_id": data["provider_batch_id"]}
    return None


def double_submit_state(paths: BatchPaths) -> dict[str, Any]:
    existing = existing_submission(paths)
    return {
        "run_manifest_path": str(paths.run_manifest),
        "sentinel_path": str(paths.sentinel),
        "in_progress_lock_path": str(paths.in_progress_lock),
        "run_manifest_exists": paths.run_manifest.exists(),
        "sentinel_exists": paths.sentinel.exists(),
        "in_progress_lock_exists": paths.in_progress_lock.exists(),
        "existing_submission": existing,
        "double_submit_block_active": existing is not None,
    }


def acquire_submit_lock(paths: BatchPaths) -> None:
    if paths.in_progress_lock.exists():
        raise RuntimeError(f"submit lock exists: {paths.in_progress_lock}")
    atomic_write_json(paths.in_progress_lock, {"created_at": now_iso(), "run_id": RUN_ID}, pretty=True)


def release_submit_lock(paths: BatchPaths) -> None:
    try:
        paths.in_progress_lock.unlink()
    except FileNotFoundError:
        pass


def provider_batch_id_from_args(args: argparse.Namespace, paths: BatchPaths) -> str:
    if args.provider_batch_id:
        return args.provider_batch_id
    manifest_path = Path(args.batch_run_manifest) if args.batch_run_manifest else paths.run_manifest
    if manifest_path.exists():
        data = read_json(manifest_path)
        if data.get("provider_batch_id"):
            return data["provider_batch_id"]
    raise RuntimeError("provider_batch_id is required; pass --provider-batch-id or --batch-run-manifest")


def update_run_manifest_status(paths: BatchPaths, args: argparse.Namespace, provider_batch_id: str, status: dict[str, Any], *, mode: str) -> None:
    manifest_path = Path(args.batch_run_manifest) if args.batch_run_manifest else paths.run_manifest
    data: dict[str, Any] = read_json(manifest_path) if manifest_path.exists() else {
        "schema_version": "pali_pilot_300_batch_run_manifest_v1",
        "run_id": RUN_ID,
        "submitted": True,
        "created_at": now_iso(),
        "output_paths": output_paths(paths, args),
    }
    data.update({
        "mode": mode,
        "provider_batch_id": provider_batch_id,
        "provider_status": status_snapshot(status),
        "updated_at": now_iso(),
        "credential_source": "environment_variable",
        "credential_value_logged": False,
    })
    atomic_write_json(paths.run_manifest, data, pretty=args.pretty)


def load_run_manifest(args: argparse.Namespace, paths: BatchPaths) -> dict[str, Any]:
    path = Path(args.batch_run_manifest) if args.batch_run_manifest else paths.run_manifest
    if not path.exists():
        raise RuntimeError(f"run manifest does not exist: {path}")
    return read_json(path)


def adapt_parsed_item(item: dict[str, Any], *, provider_batch_id: str) -> dict[str, Any]:
    parsed = item.get("parsed_translation_json") or {}
    return {
        **item,
        "parse_failed": "json_parse_failed" in (item.get("local_validator_flags") or []) or item.get("status") == "missing_result",
        "literal_ko": parsed.get("literal_ko", ""),
        "natural_ko": parsed.get("natural_ko", ""),
        "terms": parsed.get("terms", []),
        "grammar_notes": parsed.get("grammar_notes", []),
        "doctrinal_notes": parsed.get("doctrinal_notes", []),
        "uncertainties": parsed.get("uncertainties", []),
        "usage_metadata": {
            "prompt_token_count": item.get("prompt_token_count", 0),
            "candidates_token_count": item.get("candidates_token_count", 0),
            "thoughts_token_count": item.get("thoughts_token_count", 0),
            "cached_content_token_count": item.get("cached_content_token_count", 0),
            "total_token_count": item.get("total_token_count", 0),
        },
        "provider_batch_id": provider_batch_id,
        "provider_response_id": item.get("stable_segment_key"),
    }


def build_batch_summary(parsed_payload: dict[str, Any], run_manifest: dict[str, Any]) -> dict[str, Any]:
    items = parsed_payload.get("items") or []
    actual_cost = sum((parse_decimal(item.get("actual_cost_usd") or "0", "actual_cost_usd") for item in items), Decimal("0"))
    actual_input = sum(int(item.get("prompt_token_count") or 0) for item in items)
    actual_output = sum(int(item.get("candidates_token_count") or 0) for item in items)
    actual_thinking = sum(int(item.get("thoughts_token_count") or 0) for item in items)
    conservative = parse_decimal(run_manifest.get("estimated_cost_usd_conservative_gate") or "0", "estimated_cost_usd_conservative_gate")
    warnings: list[str] = []
    if conservative and actual_cost > conservative * Decimal("1.5"):
        warnings.append("actual_cost_gt_conservative_gate_1_5x")
    if actual_cost > parse_decimal(run_manifest.get("budget_usd") or "20", "budget_usd"):
        warnings.append("BUDGET_EXCEEDED_AFTER_RUN")
    failed = [item for item in items if item.get("status") != "succeeded"]
    if failed:
        warnings.append("partial_failure_no_automatic_resubmit")
    return {
        "schema_version": "pali_pilot_300_batch_summary_v1",
        "provider_batch_id": parsed_payload.get("provider_batch_id"),
        "request_count": len(items),
        "succeeded_count": sum(1 for item in items if item.get("status") == "succeeded"),
        "failed_count": len(failed),
        "schema_valid_count": sum(1 for item in items if item.get("schema_valid")),
        "schema_invalid_count": sum(1 for item in items if item.get("status") == "schema_invalid"),
        "parse_failed_count": sum(1 for item in items if item.get("parse_failed")),
        "actual_input_tokens": actual_input,
        "actual_output_tokens": actual_output,
        "actual_thinking_tokens": actual_thinking,
        "actual_total_tokens": actual_input + actual_output + actual_thinking,
        "actual_cost_usd": str(quantize_usd(actual_cost)),
        "estimated_conservative_gate_usd": str(conservative),
        "actual_to_conservative_ratio": str(decimal_ratio(actual_cost, conservative)),
        "budget_usd": run_manifest.get("budget_usd"),
        "budget_passed": actual_cost <= parse_decimal(run_manifest.get("budget_usd") or "20", "budget_usd"),
        "warnings": warnings,
        "failed_item_causes": failed_item_causes(items),
        "automatic_resubmit_allowed": False,
    }


def failed_item_causes(items: list[dict[str, Any]]) -> list[dict[str, Any]]:
    causes = []
    for item in items:
        if item.get("status") == "succeeded":
            continue
        if item.get("status") == "schema_invalid":
            category = "schema_invalid"
        elif item.get("parse_failed"):
            category = "parse_failed"
        elif item.get("status") == "failed":
            category = "provider_error"
        elif item.get("status") == "needs_retry":
            category = "empty_response"
        else:
            category = str(item.get("status") or "unknown")
        causes.append({"stable_segment_key": item.get("stable_segment_key"), "category": category, "error_message": item.get("error_message", "")})
    return causes


def render_summary_md(summary: dict[str, Any]) -> str:
    return "\n".join([
        "# Pāli 300 Batch Summary",
        "",
        f"- provider_batch_id: `{summary.get('provider_batch_id')}`",
        f"- request_count: {summary['request_count']}",
        f"- succeeded_count: {summary['succeeded_count']}",
        f"- failed_count: {summary['failed_count']}",
        f"- schema_valid_count: {summary['schema_valid_count']}",
        f"- parse_failed_count: {summary['parse_failed_count']}",
        f"- actual_cost_usd: ${summary['actual_cost_usd']}",
        f"- budget_passed: {summary['budget_passed']}",
        f"- warnings: {', '.join(summary['warnings']) if summary['warnings'] else 'none'}",
        "",
        "Partial failures must be classified before any retry. Automatic resubmit is disabled.",
        "",
    ])


def render_submit_plan(payload: dict[str, Any]) -> str:
    gate = payload["pre_submit_gate"]
    return "\n".join([
        "# Pāli 300 Batch Submit Plan",
        "",
        f"- status: `{payload['status']}`",
        f"- selection_content_sha256: `{gate['selection_content_sha256']}`",
        f"- jsonl_sha256: `{gate['jsonl_sha256']}`",
        f"- jsonl_request_count: {gate['jsonl_request_count']}",
        f"- smoke_status: `{gate['smoke_status']}`",
        f"- budget_usd: ${gate['budget_usd']}",
        f"- estimated_cost_usd_conservative_gate: ${gate['estimated_cost_usd_conservative_gate']}",
        f"- blocking_reasons: {', '.join(gate['blocking_reasons']) if gate['blocking_reasons'] else 'none'}",
        "",
        "Actual submit is only allowed from the operator's local terminal with `--enable-submit --user-green-light`.",
        "",
    ])


def normalize_model_name(name: str) -> str:
    return str(name or "").removeprefix("models/")


def resolve_env_credential() -> dict[str, str] | None:
    for name in ENV_CANDIDATES:
        value = os.getenv(name)
        if value:
            return {"name": name, "value": value}
    return None


def recovery_instruction(paths: BatchPaths) -> str:
    existing = existing_submission(paths)
    if existing:
        return f"Already submitted. Use --mode poll or --mode fetch with provider_batch_id {existing['provider_batch_id']}."
    return "No existing provider_batch_id."


def batch_paths(out_dir: Path) -> BatchPaths:
    return BatchPaths(
        out_dir=out_dir,
        dry_run=out_dir / "pilot_300_batch_dry_run.json",
        submit_plan=out_dir / "pilot_300_batch_submit_plan.md",
        run_manifest=out_dir / "pilot_300_batch_run_manifest.json",
        sentinel=out_dir / ".pilot_300_v1_batch_submitted.lock",
        in_progress_lock=out_dir / ".pilot_300_v1_batch_submit.in_progress.lock",
        provider_status=out_dir / "pilot_300_batch_provider_status.json",
        raw_results=out_dir / "pilot_300_batch_raw_results.jsonl",
        parsed=out_dir / "pilot_300_batch_parsed.json",
        summary_json=out_dir / "pilot_300_batch_summary.json",
        summary_md=out_dir / "pilot_300_batch_summary.md",
    )


def output_paths(paths: BatchPaths, args: argparse.Namespace) -> dict[str, str]:
    return {
        "dry_run": str(paths.dry_run),
        "submit_plan": str(paths.submit_plan),
        "run_manifest": str(paths.run_manifest),
        "sentinel": str(paths.sentinel),
        "provider_status": str(paths.provider_status),
        "raw_results": str(paths.raw_results),
        "parsed": str(paths.parsed),
        "summary_json": str(paths.summary_json),
        "summary_md": str(paths.summary_md),
        "qa_out": str(args.qa_out or "data/qa_reports/pali/qa_report_300_live"),
    }


def read_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def read_jsonl(path: Path) -> list[dict[str, Any]]:
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


def atomic_write_json(path: Path, payload: Any, *, pretty: bool) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_name(path.name + ".tmp")
    tmp.write_text(json.dumps(payload, ensure_ascii=False, indent=2 if pretty else None, sort_keys=True) + "\n", encoding="utf-8")
    with tmp.open("r+", encoding="utf-8") as handle:
        handle.flush()
        os.fsync(handle.fileno())
    tmp.replace(path)


def file_record(path: Path) -> dict[str, Any]:
    return {"path": str(path), "exists": path.exists(), "sha256": file_sha256(path) if path.exists() else None}


def file_sha256(path: Path) -> str:
    import hashlib

    return hashlib.sha256(path.read_bytes()).hexdigest()


def parse_decimal(value: object, field_name: str) -> Decimal:
    try:
        return Decimal(str(value))
    except (InvalidOperation, ValueError, TypeError) as exc:
        raise ValueError(f"invalid decimal field {field_name}: {value!r}") from exc


def quantize_usd(value: Decimal) -> Decimal:
    return value.quantize(Decimal("0.000001"), rounding=ROUND_HALF_UP)


def decimal_ratio(numerator: Decimal, denominator: Decimal) -> Decimal:
    if denominator == 0:
        return Decimal("0.000")
    return (numerator / denominator).quantize(Decimal("0.001"), rounding=ROUND_HALF_UP)


def now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))

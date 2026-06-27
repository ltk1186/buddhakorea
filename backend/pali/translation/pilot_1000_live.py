"""Step 7 guarded live pipeline for the Pali Pilot 1,000 batch.

This module implements the live submit/poll/fetch/parse/QA/report plumbing, but
its preflight path is fully local. Provider calls only happen through explicit
operator-run modes in ``backend.pali.scripts.submit_pilot_1000_batch``.
"""

from __future__ import annotations

import hashlib
import json
import subprocess
from collections import Counter
from dataclasses import dataclass
from decimal import Decimal, ROUND_HALF_UP
from pathlib import Path
from typing import Any

from backend.pali.scripts.salvage_pilot_300_batch_parse import (
    apply_successful_parse,
    extract_finish_reason,
    parse_output_cascade,
)
from backend.pali.scripts.submit_gemini_smoke_batch import (
    DEFAULT_MODEL,
    DEFAULT_PRICE_PROFILE_ID,
    DEFAULT_PRICE_PROFILE_PATH,
    GeminiBatchRestClient,
    actual_cost_from_usage,
    build_inline_request_from_provider_line,
    extract_batch_name,
    extract_generate_content_response,
    extract_inline_result_lines,
    extract_model_output_text,
    extract_result_key,
    load_price_profile,
    parse_usage_metadata,
    resolve_gemini_api_key,
    status_snapshot,
)
from backend.pali.translation.natural_ko_calibration_smoke import (
    gate_status_from_failures,
)
from backend.pali.translation.natural_ko_readability import NATURAL_KO_V2_2_MARKER
from backend.pali.translation.natural_ko_v2_2_quality import evaluate_d_arm_item
from backend.pali.translation.pilot_1000_dry_run import (
    PINNED_INVENTORY_COMMIT,
    STIFF_LITERAL_ANCHORS,
    decimal_rate,
)
from backend.pali.translation.response_schema_smoke import validate_response_schema_dialect


DEFAULT_OUT = Path("data/reports/pali/pilot_1000_batch")
DEFAULT_REQUEST_PREVIEW = DEFAULT_OUT / "pilot_1000_request_preview.jsonl"
DEFAULT_MANIFEST = Path("data/pilot_sets/pali/pilot_1000_v1_manifest.json")
DEFAULT_HARD_CAP_USD = Decimal("50")
DEFAULT_RETRY_HARD_CAP_USD = Decimal("5")
PLANNED_REQUESTS = 1000
RESPONSE_FIELDS = {
    "literal_ko",
    "natural_ko",
    "terms",
    "grammar_notes",
    "doctrinal_notes",
    "uncertainties",
    "quality_flags",
}


class Pilot1000LiveBlocked(RuntimeError):
    def __init__(self, status: str, message: str, details: dict[str, Any] | None = None):
        super().__init__(message)
        self.status = status
        self.message = message
        self.details = details or {}


@dataclass(frozen=True)
class Step7Paths:
    out_dir: Path
    step6_manifest: Path
    step6_validation: Path
    submit_preflight_json: Path
    submit_preflight_md: Path
    submit_run_manifest: Path
    provider_status: Path
    raw_results: Path
    parsed: Path
    parse_report: Path
    qa: Path
    summary_json: Path
    summary_md: Path
    translation_outputs_md: Path
    manual_review_sheet_md: Path
    final_recommendation_md: Path
    retry_bracket_plan_json: Path
    retry_bracket_plan_md: Path


def step7_paths(out_dir: Path) -> Step7Paths:
    return Step7Paths(
        out_dir=out_dir,
        step6_manifest=out_dir / "pilot_1000_dry_run_manifest.json",
        step6_validation=out_dir / "pilot_1000_validation_report.json",
        submit_preflight_json=out_dir / "pilot_1000_submit_preflight.json",
        submit_preflight_md=out_dir / "pilot_1000_submit_preflight.md",
        submit_run_manifest=out_dir / "submit_run_manifest.json",
        provider_status=out_dir / "pilot_1000_provider_status.json",
        raw_results=out_dir / "pilot_1000_raw_results.jsonl",
        parsed=out_dir / "pilot_1000_parsed.json",
        parse_report=out_dir / "pilot_1000_parse_report.json",
        qa=out_dir / "pilot_1000_qa.json",
        summary_json=out_dir / "pilot_1000_summary.json",
        summary_md=out_dir / "pilot_1000_summary.md",
        translation_outputs_md=out_dir / "pilot_1000_translation_outputs.md",
        manual_review_sheet_md=out_dir / "pilot_1000_manual_review_sheet.md",
        final_recommendation_md=out_dir / "pilot_1000_final_recommendation.md",
        retry_bracket_plan_json=out_dir / "pilot_1000_retry_bracket_plan.json",
        retry_bracket_plan_md=out_dir / "pilot_1000_retry_bracket_plan.md",
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


def file_sha256(path: Path) -> str | None:
    if not path.exists():
        return None
    return hashlib.sha256(path.read_bytes()).hexdigest()


def stable_json(payload: Any) -> str:
    return json.dumps(payload, ensure_ascii=False, sort_keys=True, separators=(",", ":"))


def quantize_usd(value: Decimal) -> str:
    return str(value.quantize(Decimal("0.000001"), rounding=ROUND_HALF_UP))


def prompt_text(row: dict[str, Any]) -> str:
    try:
        return str(row["request"]["contents"][0]["parts"][0]["text"])
    except (KeyError, IndexError, TypeError):
        return ""


def generation_config(row: dict[str, Any]) -> dict[str, Any]:
    request = row.get("request") or {}
    return request.get("generation_config") or request.get("generationConfig") or {}


def response_schema(row: dict[str, Any]) -> dict[str, Any]:
    return generation_config(row).get("response_schema") or generation_config(row).get("responseSchema") or {}


def contains_key_recursive(value: Any, key_name: str) -> bool:
    if isinstance(value, dict):
        return key_name in value or any(contains_key_recursive(v, key_name) for v in value.values())
    if isinstance(value, list):
        return any(contains_key_recursive(v, key_name) for v in value)
    return False


def contains_text_recursive(value: Any, needle: str) -> bool:
    if isinstance(value, str):
        return needle in value
    if isinstance(value, dict):
        return any(contains_text_recursive(v, needle) for v in value.values())
    if isinstance(value, list):
        return any(contains_text_recursive(v, needle) for v in value)
    return False


def manifest_items(manifest: dict[str, Any]) -> list[dict[str, Any]]:
    return manifest.get("items") or []


def row_key(row: dict[str, Any]) -> str | None:
    return row.get("key") or (row.get("metadata") or {}).get("stable_segment_key")


def load_step6_inputs(paths: Step7Paths, manifest_path: Path) -> tuple[dict[str, Any], dict[str, Any], dict[str, Any]]:
    missing = [
        str(path)
        for path in (paths.step6_manifest, paths.step6_validation, manifest_path)
        if not path.exists()
    ]
    if missing:
        raise Pilot1000LiveBlocked("BLOCKED_MISSING_INPUTS", "Required Step 6/Step 5 input missing.", {"missing": missing})
    return read_json(paths.step6_manifest), read_json(paths.step6_validation), read_json(manifest_path)


def existing_provider_batch_id(paths: Step7Paths) -> str | None:
    for path in (paths.provider_status, paths.submit_run_manifest):
        if not path.exists():
            continue
        try:
            payload = read_json(path)
        except Exception:
            continue
        if payload.get("provider_batch_id"):
            return str(payload["provider_batch_id"])
        if payload.get("name"):
            return str(payload["name"])
    return None


def validate_preflight_inputs(
    *,
    rows: list[dict[str, Any]],
    step6_manifest: dict[str, Any],
    step6_validation: dict[str, Any],
    selection_manifest: dict[str, Any],
    paths: Step7Paths,
    hard_cap_usd: Decimal,
) -> tuple[list[str], list[str], dict[str, Any]]:
    errors: list[str] = []
    warnings: list[str] = []
    details: dict[str, Any] = {}

    if len(rows) != PLANNED_REQUESTS:
        errors.append(f"request preview must contain exactly {PLANNED_REQUESTS} rows; got {len(rows)}")
    keys = [row_key(row) for row in rows]
    manifest_keys = [item.get("stable_segment_key") for item in manifest_items(selection_manifest)]
    if len(keys) != len(set(keys)):
        errors.append("request preview contains duplicate stable_segment_key values")
    if len(manifest_keys) != PLANNED_REQUESTS:
        errors.append(f"Step 5 manifest must contain exactly {PLANNED_REQUESTS} items; got {len(manifest_keys)}")
    if keys != manifest_keys:
        errors.append("request preview key order does not match Step 5 manifest order")
    if set(keys) != set(manifest_keys):
        errors.append("request preview key set does not match Step 5 manifest key set")
    if selection_manifest.get("inventory_source_commit") != PINNED_INVENTORY_COMMIT:
        errors.append("Step 5 manifest inventory source commit mismatch")
    if step6_manifest.get("inventory_source_commit") != PINNED_INVENTORY_COMMIT:
        errors.append("Step 6 dry-run manifest inventory source commit mismatch")
    if step6_validation.get("dry_run_status") != "PASS":
        errors.append("Step 6 validation dry_run_status is not PASS")
    if step6_manifest.get("submit_ready") is not True or step6_validation.get("submit_ready") is not True:
        errors.append("Step 6 submit_ready is not true")
    if step6_manifest.get("cap_passed") is not True or step6_validation.get("cap_passed") is not True:
        errors.append("Step 6 cap_passed is not true")

    estimated_p90 = Decimal(str(step6_manifest.get("estimated_cost_usd_p90") or step6_validation.get("estimated_cost_usd_p90") or "0"))
    estimated_mean = Decimal(str(step6_manifest.get("estimated_cost_usd_mean") or "0"))
    details["estimated_cost_usd_mean"] = quantize_usd(estimated_mean)
    details["estimated_cost_usd_p90"] = quantize_usd(estimated_p90)
    details["hard_cap_usd"] = quantize_usd(hard_cap_usd)
    if estimated_p90 > hard_cap_usd:
        errors.append(f"estimated p90 cost {estimated_p90} exceeds hard cap {hard_cap_usd}")

    config_fingerprints: set[str] = set()
    schema_fingerprints: set[str] = set()
    for index, row in enumerate(rows):
        key = row_key(row) or f"row-{index}"
        metadata = row.get("metadata") or {}
        text = prompt_text(row)
        config = generation_config(row)
        schema = response_schema(row)
        config_fingerprints.add(stable_json(config))
        schema_fingerprints.add(stable_json(schema))
        if not schema:
            errors.append(f"{key}: response_schema missing")
        else:
            dialect = validate_response_schema_dialect(schema)
            if not dialect["valid"]:
                errors.append(f"{key}: response_schema dialect invalid: {dialect}")
            if "propertyOrdering" not in schema:
                errors.append(f"{key}: response_schema missing propertyOrdering")
            if contains_key_recursive(schema, "additionalProperties"):
                errors.append(f"{key}: response_schema contains additionalProperties")
            if set((schema.get("properties") or {}).keys()) != RESPONSE_FIELDS:
                errors.append(f"{key}: response_schema fields do not match expected output fields")
        if config.get("temperature") != 0.2:
            errors.append(f"{key}: generation_config.temperature is not 0.2")
        if config.get("response_mime_type") != "application/json":
            errors.append(f"{key}: response_mime_type is not application/json")
        if "reader_ko" in text or contains_text_recursive(schema, "reader_ko") or contains_text_recursive(metadata, "reader_ko"):
            errors.append(f"{key}: reader_ko present in prompt/schema/metadata")
        if NATURAL_KO_V2_2_MARKER not in text:
            errors.append(f"{key}: natural_ko_v2_2 marker missing")
        for anchor in STIFF_LITERAL_ANCHORS:
            if anchor in text:
                errors.append(f"{key}: old stiff literal anchor present: {anchor}")
        for required_metadata in ("source_path", "source_text_hash", "text_layer", "chunk_type", "length_bucket", "original_text"):
            if not metadata.get(required_metadata):
                errors.append(f"{key}: metadata.{required_metadata} missing")
    if len(config_fingerprints) > 1:
        errors.append("generation_config differs across requests")
    if len(schema_fingerprints) > 1:
        errors.append("response_schema differs across requests")

    provider_id = existing_provider_batch_id(paths)
    details["existing_provider_batch_id"] = provider_id
    if provider_id:
        errors.append("existing provider_batch_id found; refusing duplicate submit")
    if paths.raw_results.exists() and provider_id:
        errors.append("raw results already exist for submitted batch")
    if not data_reports_gitignored(paths.raw_results):
        warnings.append("raw results path is not covered by data/reports gitignore policy")
    return errors, warnings, details


def data_reports_gitignored(path: Path) -> bool:
    try:
        repo_root = Path(__file__).resolve().parents[3]
        rel = path.resolve().relative_to(repo_root.resolve())
    except Exception:
        rel = path
        repo_root = Path.cwd()
    gitignore = repo_root / ".gitignore"
    if gitignore.exists() and "data/reports/" in gitignore.read_text(encoding="utf-8", errors="replace"):
        return str(rel).startswith("data/reports/")
    try:
        result = subprocess.run(["git", "check-ignore", "-q", str(rel)], cwd=repo_root, check=False)
        return result.returncode == 0
    except Exception:
        return False


def preflight_submit(
    *,
    request_preview_path: Path = DEFAULT_REQUEST_PREVIEW,
    manifest_path: Path = DEFAULT_MANIFEST,
    out_dir: Path = DEFAULT_OUT,
    hard_cap_usd: Decimal = DEFAULT_HARD_CAP_USD,
    pretty: bool = False,
) -> dict[str, Any]:
    paths = step7_paths(out_dir)
    errors: list[str] = []
    warnings: list[str] = []
    details: dict[str, Any] = {}
    rows: list[dict[str, Any]] = []
    if not request_preview_path.exists():
        errors.append(f"request preview missing: {request_preview_path}")
    else:
        rows = read_jsonl(request_preview_path)
    try:
        step6_manifest, step6_validation, selection_manifest = load_step6_inputs(paths, manifest_path)
        input_errors, input_warnings, input_details = validate_preflight_inputs(
            rows=rows,
            step6_manifest=step6_manifest,
            step6_validation=step6_validation,
            selection_manifest=selection_manifest,
            paths=paths,
            hard_cap_usd=hard_cap_usd,
        )
        errors.extend(input_errors)
        warnings.extend(input_warnings)
        details.update(input_details)
    except Pilot1000LiveBlocked as exc:
        errors.append(exc.message)
        details.update(exc.details)
        step6_manifest = {}
        step6_validation = {}
        selection_manifest = {}

    status = "PASS" if not errors else "BLOCKED"
    payload = {
        "schema_version": "pali_pilot_1000_submit_preflight_v1",
        "status": status,
        "api_llm_calls": 0,
        "network_calls": 0,
        "batch_submissions": 0,
        "planned_requests": len(rows),
        "expected_planned_requests": PLANNED_REQUESTS,
        "request_preview": str(request_preview_path),
        "manifest": str(manifest_path),
        "request_preview_sha256": file_sha256(request_preview_path),
        "step6_dry_run_manifest_sha256": file_sha256(paths.step6_manifest),
        "step5_manifest_sha256": file_sha256(manifest_path),
        "estimated_cost_usd_mean": details.get("estimated_cost_usd_mean", "0.000000"),
        "estimated_cost_usd_p90": details.get("estimated_cost_usd_p90", "0.000000"),
        "hard_cap_usd": details.get("hard_cap_usd", quantize_usd(hard_cap_usd)),
        "cap_passed": status == "PASS",
        "submit_ready": status == "PASS",
        "existing_provider_batch_id": details.get("existing_provider_batch_id"),
        "live_submit_started": False,
        "reader_ko_added": False,
        "response_schema": True,
        "prompt_variant": "natural_ko_v2_2",
        "salvage_cascade_fallback": True,
        "errors": errors,
        "warnings": warnings,
    }
    write_json(paths.submit_preflight_json, payload, pretty=pretty)
    paths.submit_preflight_md.write_text(render_preflight_markdown(payload), encoding="utf-8")
    return payload


def render_preflight_markdown(payload: dict[str, Any]) -> str:
    lines = [
        "# Pilot 1,000 Submit Preflight",
        "",
        f"- status: `{payload['status']}`",
        f"- planned_requests: `{payload['planned_requests']}`",
        f"- request_preview_sha256: `{payload.get('request_preview_sha256')}`",
        f"- estimated_cost_usd_mean: `{payload['estimated_cost_usd_mean']}`",
        f"- estimated_cost_usd_p90: `{payload['estimated_cost_usd_p90']}`",
        f"- hard_cap_usd: `{payload['hard_cap_usd']}`",
        f"- cap_passed: `{payload['cap_passed']}`",
        f"- submit_ready: `{payload['submit_ready']}`",
        f"- existing_provider_batch_id: `{payload.get('existing_provider_batch_id')}`",
        "- API/network/batch calls made: `0`",
        "",
        "This preflight is local-only. It validates the fixed Step 5 selection, Step 6 dry-run artifacts, response_schema dialect, prompt marker, cost cap, and duplicate-spend guard before the operator runs a live submit.",
        "",
        f"Errors: `{payload.get('errors') or []}`",
        f"Warnings: `{payload.get('warnings') or []}`",
    ]
    return "\n".join(lines) + "\n"


def require_passed_preflight(paths: Step7Paths, request_preview_path: Path, hard_cap_usd: Decimal) -> dict[str, Any]:
    if not paths.submit_preflight_json.exists():
        raise Pilot1000LiveBlocked("BLOCKED_PREFLIGHT_MISSING", "Run --preflight before --submit.")
    preflight = read_json(paths.submit_preflight_json)
    if preflight.get("status") != "PASS":
        raise Pilot1000LiveBlocked("BLOCKED_PREFLIGHT_NOT_PASS", "Preflight status must be PASS before submit.", preflight)
    current_hash = file_sha256(request_preview_path)
    if current_hash != preflight.get("request_preview_sha256"):
        raise Pilot1000LiveBlocked(
            "BLOCKED_REQUEST_PREVIEW_HASH_CHANGED",
            "Current request preview hash differs from preflight hash.",
            {"current": current_hash, "preflight": preflight.get("request_preview_sha256")},
        )
    if Decimal(str(preflight.get("estimated_cost_usd_p90") or "0")) > hard_cap_usd:
        raise Pilot1000LiveBlocked("BLOCKED_CAP_EXCEEDED", "Estimated p90 cost exceeds hard cap.", preflight)
    return preflight


def submit_live_batch(
    *,
    request_preview_path: Path = DEFAULT_REQUEST_PREVIEW,
    manifest_path: Path = DEFAULT_MANIFEST,
    out_dir: Path = DEFAULT_OUT,
    hard_cap_usd: Decimal = DEFAULT_HARD_CAP_USD,
    client: GeminiBatchRestClient | None = None,
    api_key: str | None = None,
    pretty: bool = False,
) -> dict[str, Any]:
    paths = step7_paths(out_dir)
    preflight = require_passed_preflight(paths, request_preview_path, hard_cap_usd)
    if existing_provider_batch_id(paths):
        raise Pilot1000LiveBlocked("BLOCKED_ALREADY_SUBMITTED", "Provider batch id already exists; refusing duplicate spend.")
    rows = read_jsonl(request_preview_path)
    if len(rows) != PLANNED_REQUESTS:
        raise Pilot1000LiveBlocked("BLOCKED_REQUEST_COUNT", "Request preview no longer has 1,000 requests.")
    if client is None:
        resolved_api_key = api_key or resolve_gemini_api_key()
        if not resolved_api_key:
            raise Pilot1000LiveBlocked("BLOCKED_MISSING_API_KEY", "Gemini API key is required for --submit.")
        client = GeminiBatchRestClient(api_key=resolved_api_key)
    inline_requests = [build_inline_request_from_provider_line(row) for row in rows]
    create_response = client.create_inline_batch(
        model=DEFAULT_MODEL,
        requests=inline_requests,
        display_name="pali-pilot-1000-natural-ko-v2-2",
    )
    provider_batch_id = extract_batch_name(create_response)
    if not provider_batch_id:
        raise Pilot1000LiveBlocked("BLOCKED_PROVIDER_BATCH_ID_MISSING", "Batch create response did not include provider id.", create_response)
    provider_status = {
        "provider_batch_id": provider_batch_id,
        "status": status_snapshot(create_response),
        "raw_status": create_response,
    }
    manifest = {
        "step": "7-pilot-1000-live",
        "provider_batch_id": provider_batch_id,
        "model": DEFAULT_MODEL,
        "prompt_variant": "natural_ko_v2_2",
        "response_schema": True,
        "salvage_cascade_fallback": True,
        "inventory_source_commit": PINNED_INVENTORY_COMMIT,
        "planned_requests": PLANNED_REQUESTS,
        "hard_cap_usd": quantize_usd(hard_cap_usd),
        "cap_passed": True,
        "estimated_cost_usd_mean": preflight["estimated_cost_usd_mean"],
        "estimated_cost_usd_p90": preflight["estimated_cost_usd_p90"],
        "actual_cost_usd": None,
        "api_llm_calls": 1,
        "batch_submissions": 1,
        "live_submit_started": True,
        "reader_ko_added": False,
        "prompt_mutation": False,
        "glossary_mutation": False,
        "gold_set_mutation": False,
        "source_xml_mutation": False,
        "corpus_mutation": False,
        "gate_model": "3-state",
        "request_preview_sha256": preflight["request_preview_sha256"],
    }
    write_json(paths.provider_status, provider_status, pretty=pretty)
    write_json(paths.submit_run_manifest, manifest, pretty=pretty)
    return {"status": "SUBMITTED", "provider_batch_id": provider_batch_id, "planned_requests": PLANNED_REQUESTS}


def provider_batch_id_from_files(paths: Step7Paths) -> str:
    provider_id = existing_provider_batch_id(paths)
    if not provider_id:
        raise Pilot1000LiveBlocked("BLOCKED_PROVIDER_BATCH_ID_MISSING", "No provider_batch_id found. Submit first.")
    return provider_id


def poll_live_batch(*, out_dir: Path = DEFAULT_OUT, client: GeminiBatchRestClient | None = None, api_key: str | None = None, pretty: bool = False) -> dict[str, Any]:
    paths = step7_paths(out_dir)
    provider_batch_id = provider_batch_id_from_files(paths)
    if client is None:
        resolved_api_key = api_key or resolve_gemini_api_key()
        if not resolved_api_key:
            raise Pilot1000LiveBlocked("BLOCKED_MISSING_API_KEY", "Gemini API key is required for --poll.")
        client = GeminiBatchRestClient(api_key=resolved_api_key)
    status = client.get_batch(provider_batch_id)
    payload = {
        "provider_batch_id": provider_batch_id,
        "status": status_snapshot(status),
        "raw_status": status,
    }
    write_json(paths.provider_status, payload, pretty=pretty)
    return {"status": "POLLED", "provider_batch_id": provider_batch_id, "batch_state": payload["status"].get("state")}


def fetch_live_results(*, out_dir: Path = DEFAULT_OUT, client: GeminiBatchRestClient | None = None, api_key: str | None = None, pretty: bool = False) -> dict[str, Any]:
    paths = step7_paths(out_dir)
    provider_batch_id = provider_batch_id_from_files(paths)
    if client is None:
        resolved_api_key = api_key or resolve_gemini_api_key()
        if not resolved_api_key:
            raise Pilot1000LiveBlocked("BLOCKED_MISSING_API_KEY", "Gemini API key is required for --fetch.")
        client = GeminiBatchRestClient(api_key=resolved_api_key)
    status = client.get_batch(provider_batch_id)
    inline_results = extract_inline_result_lines(status)
    write_jsonl(paths.raw_results, inline_results)
    write_json(paths.provider_status, {"provider_batch_id": provider_batch_id, "status": status_snapshot(status), "raw_status": status}, pretty=pretty)
    return {"status": "FETCHED", "provider_batch_id": provider_batch_id, "raw_result_count": len(inline_results), "raw_results": str(paths.raw_results)}


def content_strings(value: Any) -> list[str]:
    strings: list[str] = []
    if isinstance(value, str):
        if value:
            strings.append(value)
    elif isinstance(value, dict):
        for nested in value.values():
            strings.extend(content_strings(nested))
    elif isinstance(value, list):
        for nested in value:
            strings.extend(content_strings(nested))
    return strings


def content_preservation_guard(parsed_json: dict[str, Any], raw_output: str) -> bool:
    payload = {field: parsed_json.get(field) for field in RESPONSE_FIELDS}
    for string in content_strings(payload):
        if string and string not in raw_output:
            return False
    return True


def base_item_from_preview(row: dict[str, Any], manifest_item: dict[str, Any] | None) -> dict[str, Any]:
    metadata = row.get("metadata") or {}
    merged = {**(manifest_item or {}), **metadata}
    return {
        "stable_segment_key": row_key(row) or merged.get("stable_segment_key"),
        "source_path": merged.get("source_path"),
        "source_text_hash": merged.get("source_text_hash"),
        "text_layer": merged.get("text_layer"),
        "chunk_type": merged.get("chunk_type"),
        "length_bucket": merged.get("length_bucket"),
        "pitaka": merged.get("pitaka"),
        "nikaya": merged.get("nikaya"),
        "source_commit": merged.get("source_commit") or PINNED_INVENTORY_COMMIT,
        "original_text": merged.get("original_text") or "",
        "literal_ko": "",
        "natural_ko": "",
        "terms": [],
        "grammar_notes": [],
        "doctrinal_notes": [],
        "uncertainties": [],
        "quality_flags": [],
        "parsed_translation_json": None,
        "schema_valid": False,
        "parse_method": "failed",
        "salvage_applied": False,
        "provider_error": None,
        "status": "missing_result",
        "error_message": "",
        "prompt_token_count": 0,
        "candidates_token_count": 0,
        "thoughts_token_count": 0,
        "cached_content_token_count": 0,
        "total_token_count": 0,
        "actual_cost_usd": "0.000000",
    }


def parse_result_item_step7(
    *,
    preview_row: dict[str, Any],
    manifest_item: dict[str, Any] | None,
    result_line: dict[str, Any] | None,
    price_profile: Any,
) -> dict[str, Any]:
    item = base_item_from_preview(preview_row, manifest_item)
    if result_line is None:
        item["error_message"] = "No result line found for stable_segment_key."
        return item
    if result_line.get("error") or result_line.get("status"):
        item["status"] = "failed"
        item["provider_error"] = result_line.get("error") or result_line.get("status")
        item["error_message"] = json.dumps(item["provider_error"], ensure_ascii=False)
        return item
    response = extract_generate_content_response(result_line)
    usage_result = parse_usage_metadata(response)
    if usage_result.usage:
        usage = usage_result.usage
        item.update(
            {
                "prompt_token_count": usage.prompt_token_count,
                "candidates_token_count": usage.candidates_token_count,
                "thoughts_token_count": usage.thoughts_token_count,
                "cached_content_token_count": usage.cached_content_token_count,
                "total_token_count": usage.total_token_count,
                "actual_cost_usd": str(actual_cost_from_usage(usage, price_profile)),
            }
        )
    output_text = extract_model_output_text(response)
    if not output_text:
        item["status"] = "failed"
        item["provider_error"] = "missing_model_output_text"
        item["error_message"] = "GenerateContentResponse did not include output text."
        return item
    attempt = parse_output_cascade(output_text, finish_reason=extract_finish_reason(response))
    item["parse_method"] = attempt.method
    item["salvage_applied"] = attempt.method in {"raw_decode", "stack_reclose"}
    item["parser_flags"] = attempt.flags
    item["completeness_gate_passed"] = attempt.completeness_gate_passed
    if attempt.ok and attempt.obj is not None:
        if item["salvage_applied"] and not content_preservation_guard(attempt.obj, output_text):
            item["status"] = "schema_invalid"
            item["schema_valid"] = False
            item["parse_method"] = "failed"
            item["error_message"] = "Salvage content-preservation guard failed."
            item["parser_flags"] = [*attempt.flags, "content_preservation_guard_failed"]
            return item
        apply_successful_parse(item, attempt.obj)
        item["provider_error"] = None if usage_result.status == "success" else usage_result.error_message
        if usage_result.status != "success":
            item["status"] = "failed"
            item["error_message"] = usage_result.error_message
        return sanitize_parsed_item(item)
    item["status"] = "schema_invalid"
    item["schema_valid"] = False
    item["error_message"] = attempt.error or "JSON parse failed."
    return sanitize_parsed_item(item)


def sanitize_parsed_item(item: dict[str, Any]) -> dict[str, Any]:
    for raw_field in ("model_output_raw", "model_output_salvaged", "raw_response", "thought_signature", "thoughtSignatures"):
        item.pop(raw_field, None)
    return item


def parse_live_results(
    *,
    request_preview_path: Path = DEFAULT_REQUEST_PREVIEW,
    manifest_path: Path = DEFAULT_MANIFEST,
    out_dir: Path = DEFAULT_OUT,
    pretty: bool = False,
) -> dict[str, Any]:
    paths = step7_paths(out_dir)
    if not paths.raw_results.exists():
        raise Pilot1000LiveBlocked("BLOCKED_RAW_RESULTS_MISSING", "Fetch raw results before parse.")
    rows = read_jsonl(request_preview_path)
    raw_rows = read_jsonl(paths.raw_results)
    manifest = read_json(manifest_path)
    manifest_by_key = {item.get("stable_segment_key"): item for item in manifest_items(manifest)}
    raw_by_key = {extract_result_key(row): row for row in raw_rows if extract_result_key(row)}
    price_profile, _price_profile_raw = load_price_profile(DEFAULT_PRICE_PROFILE_PATH, DEFAULT_PRICE_PROFILE_ID)
    parsed_items = [
        parse_result_item_step7(
            preview_row=row,
            manifest_item=manifest_by_key.get(row_key(row)),
            result_line=raw_by_key.get(row_key(row)),
            price_profile=price_profile,
        )
        for row in rows
    ]
    parsed = {
        "schema_version": "pali_pilot_1000_parsed_v1",
        "provider_batch_id": existing_provider_batch_id(paths),
        "items": parsed_items,
    }
    report = parse_report(parsed_items)
    write_json(paths.parsed, parsed, pretty=pretty)
    write_json(paths.parse_report, report, pretty=pretty)
    return {"status": "PARSED", **report}


def parse_report(items: list[dict[str, Any]]) -> dict[str, Any]:
    method_counts = Counter(str(item.get("parse_method") or "failed") for item in items)
    schema_valid_count = sum(1 for item in items if item.get("schema_valid") is True)
    provider_error_count = sum(1 for item in items if item.get("provider_error") or item.get("status") == "failed")
    empty_translation_count = sum(1 for item in items if not str(item.get("literal_ko") or "").strip() or not str(item.get("natural_ko") or "").strip())
    actual_cost = sum((Decimal(str(item.get("actual_cost_usd") or "0")) for item in items), Decimal("0"))
    total = len(items)
    return {
        "schema_version": "pali_pilot_1000_parse_report_v1",
        "total_results": total,
        "strict_json_count": method_counts.get("strict_json", 0),
        "raw_decode_count": method_counts.get("raw_decode", 0),
        "stack_reclose_count": method_counts.get("stack_reclose", 0),
        "failed_count": method_counts.get("failed", 0),
        "schema_valid_count": schema_valid_count,
        "schema_valid_rate": decimal_rate(schema_valid_count, total),
        "empty_translation_count": empty_translation_count,
        "provider_error_count": provider_error_count,
        "actual_cost_usd": quantize_usd(actual_cost),
        "salvage_tier_counts": dict(sorted(method_counts.items())),
    }


def gate_failure_record(item: dict[str, Any], failure_type: str, details: list[Any], *, field: str | None = None) -> dict[str, Any]:
    record: dict[str, Any] = {
        "stable_segment_key": item.get("stable_segment_key"),
        "type": failure_type,
        "details": details,
    }
    if field:
        record["field"] = field
    if "parse_method" in item:
        record["parse_method"] = item.get("parse_method")
    if "schema_valid" in item:
        record["schema_valid"] = item.get("schema_valid")
    if item.get("provider_error"):
        record["provider_error"] = item.get("provider_error")
    return record


def classify_item_gate(item: dict[str, Any]) -> dict[str, Any]:
    gates = evaluate_d_arm_item(item)
    blocking: list[dict[str, Any]] = []
    retry_only: list[dict[str, Any]] = []
    if item.get("provider_error") or item.get("status") == "failed":
        blocking.append(gate_failure_record(item, "provider_error", [str(item.get("provider_error") or item.get("status") or "provider_error")]))
    if item.get("schema_valid") is not True:
        blocking.append(gate_failure_record(item, "schema_invalid", [f"schema_valid={item.get('schema_valid')!r}"]))
    empty_fields = [field for field in ("literal_ko", "natural_ko") if not str(item.get(field) or "").strip()]
    if empty_fields:
        blocking.append(gate_failure_record(item, "empty_translation", empty_fields, field=",".join(empty_fields)))
    if gates["unsupported_insertion"]:
        blocking.append(gate_failure_record(item, "unsupported_insertion", gates["unsupported_insertion_details"]))
    if gates["known_content_omission"]:
        blocking.append(gate_failure_record(item, "known_content_omission", gates["known_content_omission_details"]))
    if gates["negation_scope_risk"]:
        blocking.append(gate_failure_record(item, "negation_scope_risk", gates["negation_scope_risk_details"]))
    if gates["glossary_violation"]:
        blocking.append(gate_failure_record(item, "hard_glossary_violation", gates["glossary_violation_details"]))
    if gates["bracket_violation"]:
        retry_only.append(gate_failure_record(item, "bracket_violation", gates["bracket_violation_details"]))
    return {
        "status": gate_status_from_failures(blocking, retry_only),
        "blocking_failures": blocking,
        "retry_only_failures": retry_only,
        "advisory_warnings": gates.get("advisory_glossary_warning_details") or [],
        "objective_gates": gates,
    }


def run_qa(*, out_dir: Path = DEFAULT_OUT, pretty: bool = False) -> dict[str, Any]:
    paths = step7_paths(out_dir)
    if not paths.parsed.exists():
        raise Pilot1000LiveBlocked("BLOCKED_PARSED_MISSING", "Parse before QA.")
    parsed = read_json(paths.parsed)
    items = parsed.get("items") or []
    counts = Counter()
    blocking_failures: list[dict[str, Any]] = []
    retry_only_failures: list[dict[str, Any]] = []
    advisory_warnings: list[dict[str, Any]] = []
    item_statuses: list[dict[str, Any]] = []
    for item in items:
        classification = classify_item_gate(item)
        counts[classification["status"]] += 1
        blocking_failures.extend(classification["blocking_failures"])
        retry_only_failures.extend(classification["retry_only_failures"])
        for warning in classification["advisory_warnings"]:
            advisory_warnings.append({"stable_segment_key": item.get("stable_segment_key"), "type": "advisory_glossary_warning", "details": [warning]})
        item_statuses.append(
            {
                "stable_segment_key": item.get("stable_segment_key"),
                "objective_gate_status": classification["status"],
                "blocking_failures": classification["blocking_failures"],
                "retry_only_failures": classification["retry_only_failures"],
                "advisory_warnings": classification["advisory_warnings"],
            }
        )
    overall = gate_status_from_failures(blocking_failures, retry_only_failures)
    payload = {
        "schema_version": "pali_pilot_1000_qa_v1",
        "gate_model": "3-state",
        "overall_objective_gate_status": overall,
        "counts": {
            "PASS": counts.get("PASS", 0),
            "FAIL_RETRY_ONLY": counts.get("FAIL_RETRY_ONLY", 0),
            "FAIL_BLOCKING": counts.get("FAIL_BLOCKING", 0),
        },
        "blocking_failures": blocking_failures,
        "retry_only_failures": retry_only_failures,
        "advisory_warnings": advisory_warnings,
        "general_content_omission_status": "pending_scholar_review",
        "items": item_statuses,
    }
    write_json(paths.qa, payload, pretty=pretty)
    return {"status": "QA_COMPLETE", "overall_objective_gate_status": overall, "counts": payload["counts"]}


def report_outputs(*, out_dir: Path = DEFAULT_OUT, pretty: bool = False) -> dict[str, Any]:
    paths = step7_paths(out_dir)
    if not paths.parsed.exists() or not paths.qa.exists() or not paths.parse_report.exists():
        raise Pilot1000LiveBlocked("BLOCKED_REPORT_INPUT_MISSING", "Parse and QA before report.")
    parsed = read_json(paths.parsed)
    qa = read_json(paths.qa)
    parse = read_json(paths.parse_report)
    preflight = read_json(paths.submit_preflight_json) if paths.submit_preflight_json.exists() else {}
    items = parsed.get("items") or []
    summary = build_summary(parsed=parsed, qa=qa, parse=parse, preflight=preflight)
    write_json(paths.summary_json, summary, pretty=pretty)
    paths.summary_md.write_text(render_summary_markdown(summary), encoding="utf-8")
    paths.translation_outputs_md.write_text(render_translation_outputs(items, qa), encoding="utf-8")
    paths.manual_review_sheet_md.write_text(render_manual_review_sheet(items, qa), encoding="utf-8")
    paths.final_recommendation_md.write_text(render_final_recommendation(summary), encoding="utf-8")
    return {"status": "REPORTED", "summary": str(paths.summary_json), "readable": str(paths.translation_outputs_md)}


def build_summary(*, parsed: dict[str, Any], qa: dict[str, Any], parse: dict[str, Any], preflight: dict[str, Any]) -> dict[str, Any]:
    items = parsed.get("items") or []
    uncertainties_count = sum(1 for item in items if item.get("uncertainties"))
    quality_flags_count = sum(1 for item in items if item.get("quality_flags"))
    actual_cost = Decimal(str(parse.get("actual_cost_usd") or "0"))
    estimated_p90 = Decimal(str(preflight.get("estimated_cost_usd_p90") or "0"))
    return {
        "schema_version": "pali_pilot_1000_summary_v1",
        "planned_requests": PLANNED_REQUESTS,
        "returned_results": len(items),
        "schema_valid_count": parse.get("schema_valid_count"),
        "schema_valid_rate": parse.get("schema_valid_rate"),
        "strict_parse_rate": decimal_rate(int(parse.get("strict_json_count") or 0), len(items)),
        "salvage_tier_counts": parse.get("salvage_tier_counts") or {},
        "provider_error_count": parse.get("provider_error_count"),
        "empty_translation_count": parse.get("empty_translation_count"),
        "actual_cost_usd": parse.get("actual_cost_usd"),
        "estimated_cost_usd_mean": preflight.get("estimated_cost_usd_mean"),
        "estimated_cost_usd_p90": preflight.get("estimated_cost_usd_p90"),
        "actual_vs_estimate_p90_ratio": str((actual_cost / estimated_p90).quantize(Decimal("0.000001"), rounding=ROUND_HALF_UP)) if estimated_p90 else None,
        "gate_distribution": qa.get("counts") or {},
        "overall_objective_gate_status": qa.get("overall_objective_gate_status"),
        "blocking_failure_count": len(qa.get("blocking_failures") or []),
        "blocking_failures": qa.get("blocking_failures") or [],
        "retry_only_failure_count": len(qa.get("retry_only_failures") or []),
        "retry_only_failures": qa.get("retry_only_failures") or [],
        "advisory_warning_count": len(qa.get("advisory_warnings") or []),
        "advisory_warnings": qa.get("advisory_warnings") or [],
        "uncertainties_item_count": uncertainties_count,
        "quality_flags_item_count": quality_flags_count,
        "reader_ko_added": False,
        "final_recommendation": "pending_operator_and_scholar_review",
    }


def render_summary_markdown(summary: dict[str, Any]) -> str:
    lines = [
        "# Pilot 1,000 Summary",
        "",
        f"- planned_requests: `{summary['planned_requests']}`",
        f"- returned_results: `{summary['returned_results']}`",
        f"- schema_valid: `{summary['schema_valid_count']}` / `{summary['schema_valid_rate']}`",
        f"- strict_parse_rate: `{summary['strict_parse_rate']}`",
        f"- salvage_tier_counts: `{json.dumps(summary['salvage_tier_counts'], ensure_ascii=False, sort_keys=True)}`",
        f"- provider_error_count: `{summary['provider_error_count']}`",
        f"- empty_translation_count: `{summary['empty_translation_count']}`",
        f"- actual_cost_usd: `{summary['actual_cost_usd']}`",
        f"- estimated_cost_usd_mean: `{summary['estimated_cost_usd_mean']}`",
        f"- estimated_cost_usd_p90: `{summary['estimated_cost_usd_p90']}`",
        f"- gate_distribution: `{json.dumps(summary['gate_distribution'], ensure_ascii=False, sort_keys=True)}`",
        f"- blocking_failure_count: `{summary['blocking_failure_count']}`",
        f"- retry_only_failure_count: `{summary['retry_only_failure_count']}`",
        f"- advisory_warning_count: `{summary['advisory_warning_count']}`",
        f"- uncertainties_item_count: `{summary['uncertainties_item_count']}`",
        f"- quality_flags_item_count: `{summary['quality_flags_item_count']}`",
        f"- reader_ko_added: `{summary['reader_ko_added']}`",
        "",
        "Final recommendation remains `pending_operator_and_scholar_review`.",
    ]
    return "\n".join(lines) + "\n"


def qa_by_key(qa: dict[str, Any]) -> dict[str, dict[str, Any]]:
    return {item.get("stable_segment_key"): item for item in qa.get("items") or []}


def render_terms(value: Any) -> str:
    if not value:
        return "[]"
    return json.dumps(value, ensure_ascii=False, sort_keys=True)


def render_translation_outputs(items: list[dict[str, Any]], qa: dict[str, Any]) -> str:
    statuses = qa_by_key(qa)
    lines = ["# Pilot 1,000 Translation Outputs", ""]
    for index, item in enumerate(items, start=1):
        status = statuses.get(item.get("stable_segment_key"), {})
        lines.extend(
            [
                f"## {index}. {item.get('stable_segment_key')}",
                "",
                f"- source_path: `{item.get('source_path')}`",
                f"- source_text_hash: `{item.get('source_text_hash')}`",
                f"- metadata: `{item.get('text_layer')}` / `{item.get('chunk_type')}` / `{item.get('length_bucket')}`",
                f"- objective_gate_status: `{status.get('objective_gate_status')}`",
                "",
                "### Original",
                "",
                str(item.get("original_text") or ""),
                "",
                "### literal_ko",
                "",
                str(item.get("literal_ko") or ""),
                "",
                "### natural_ko",
                "",
                str(item.get("natural_ko") or ""),
                "",
                f"- terms: `{render_terms(item.get('terms'))}`",
                f"- grammar_notes: `{render_terms(item.get('grammar_notes'))}`",
                f"- doctrinal_notes: `{render_terms(item.get('doctrinal_notes'))}`",
                f"- uncertainties: `{render_terms(item.get('uncertainties'))}`",
                f"- quality_flags: `{render_terms(item.get('quality_flags'))}`",
                "",
            ]
        )
    return "\n".join(lines)


def review_priority_items(items: list[dict[str, Any]], qa: dict[str, Any], limit: int = 120) -> list[dict[str, Any]]:
    statuses = qa_by_key(qa)
    scored: list[tuple[int, str, dict[str, Any]]] = []
    for item in items:
        status = statuses.get(item.get("stable_segment_key"), {})
        score = 0
        if status.get("objective_gate_status") == "FAIL_BLOCKING":
            score += 100
        if status.get("objective_gate_status") == "FAIL_RETRY_ONLY":
            score += 80
        if item.get("uncertainties"):
            score += 40
        if item.get("quality_flags"):
            score += 30
        if str(item.get("length_bucket")) == "long":
            score += 10
        scored.append((score, str(item.get("stable_segment_key")), item))
    return [item for _, _key, item in sorted(scored, reverse=True)[:limit]]


def render_manual_review_sheet(items: list[dict[str, Any]], qa: dict[str, Any]) -> str:
    statuses = qa_by_key(qa)
    lines = ["# Pilot 1,000 Manual Review Sheet", "", "Separate operator readability review from Pali-capable scholar fidelity review.", ""]
    for item in review_priority_items(items, qa):
        status = statuses.get(item.get("stable_segment_key"), {})
        lines.extend(
            [
                f"## {item.get('stable_segment_key')}",
                "",
                f"- layer/chunk/length: `{item.get('text_layer')}` / `{item.get('chunk_type')}` / `{item.get('length_bucket')}`",
                f"- objective_gate_status: `{status.get('objective_gate_status')}`",
                f"- blocking_failures: `{render_terms(status.get('blocking_failures'))}`",
                f"- retry_only_failures: `{render_terms(status.get('retry_only_failures'))}`",
                "",
                "### Original",
                str(item.get("original_text") or ""),
                "",
                "### literal_ko",
                str(item.get("literal_ko") or ""),
                "",
                "### natural_ko",
                str(item.get("natural_ko") or ""),
                "",
                "### READABILITY — Operator",
                "- B/D-style natural_ko reads like publishable modern Korean: yes / no / unclear",
                "- Too literal or stiff: yes / no",
                "- Over-paraphrased or too loose: yes / no",
                "",
                "### FIDELITY / NEGATION / OMISSION / TERM — Scholar",
                "- Preserves doctrinal meaning, referents, and logical relations: ok / minor / fidelity_risk",
                "- Drops source content: yes / no / uncertain",
                "- Adds source-unsupported content: yes / no / uncertain",
                "- Negation and conditions preserved: yes / no / uncertain",
                "- Term rendering acceptable: yes / no / needs_expert_confirm",
                "",
            ]
        )
    return "\n".join(lines) + "\n"


def render_final_recommendation(summary: dict[str, Any]) -> str:
    return "\n".join(
        [
            "# Pilot 1,000 Final Recommendation",
            "",
            "Status: `pending_operator_and_scholar_review`.",
            "",
            "This report does not promote the 1,000 result to production corpus. Operator readability review and Pali-capable scholar fidelity review are required before downstream use.",
            "",
            f"- overall_objective_gate_status: `{summary.get('overall_objective_gate_status')}`",
            f"- blocking_failure_count: `{summary.get('blocking_failure_count')}`",
            f"- retry_only_failure_count: `{summary.get('retry_only_failure_count')}`",
        ]
    ) + "\n"


def build_retry_bracket_plan(*, out_dir: Path = DEFAULT_OUT, retry_hard_cap_usd: Decimal = DEFAULT_RETRY_HARD_CAP_USD, pretty: bool = False) -> dict[str, Any]:
    paths = step7_paths(out_dir)
    if not paths.qa.exists():
        raise Pilot1000LiveBlocked("BLOCKED_QA_MISSING", "Run QA before building retry plan.")
    qa = read_json(paths.qa)
    preflight = read_json(paths.submit_preflight_json) if paths.submit_preflight_json.exists() else {}
    retry_failures = qa.get("retry_only_failures") or []
    blocking = qa.get("blocking_failures") or []
    retry_keys = sorted({failure.get("stable_segment_key") for failure in retry_failures if failure.get("type") == "bracket_violation"})
    non_bracket = [failure for failure in retry_failures if failure.get("type") != "bracket_violation"]
    estimated_p90 = Decimal(str(preflight.get("estimated_cost_usd_p90") or "0"))
    per_item = estimated_p90 / Decimal(PLANNED_REQUESTS) if estimated_p90 else Decimal("0")
    retry_estimate = per_item * Decimal(len(retry_keys))
    status = "READY" if retry_keys and not non_bracket and not blocking and retry_estimate <= retry_hard_cap_usd else "BLOCKED"
    if not retry_keys:
        status = "NO_RETRY_NEEDED"
    payload = {
        "schema_version": "pali_pilot_1000_retry_bracket_plan_v1",
        "status": status,
        "retry_reason": "bracket_violation",
        "retry_item_count": len(retry_keys),
        "retry_stable_segment_keys": retry_keys,
        "blocking_failures_present": bool(blocking),
        "non_bracket_retry_failures": non_bracket,
        "estimated_retry_cost_usd": quantize_usd(retry_estimate),
        "retry_hard_cap_usd": quantize_usd(retry_hard_cap_usd),
        "execute_retry_now": False,
        "note": "This mode writes a retry plan only. Actual retry submission requires a later explicit implementation or operator-approved execution flag.",
    }
    write_json(paths.retry_bracket_plan_json, payload, pretty=pretty)
    paths.retry_bracket_plan_md.write_text(render_retry_bracket_markdown(payload), encoding="utf-8")
    return payload


def render_retry_bracket_markdown(payload: dict[str, Any]) -> str:
    return "\n".join(
        [
            "# Pilot 1,000 Bracket Retry Plan",
            "",
            f"- status: `{payload['status']}`",
            f"- retry_item_count: `{payload['retry_item_count']}`",
            f"- estimated_retry_cost_usd: `{payload['estimated_retry_cost_usd']}`",
            f"- retry_hard_cap_usd: `{payload['retry_hard_cap_usd']}`",
            f"- execute_retry_now: `{payload['execute_retry_now']}`",
            "",
            "Stable segment keys:",
            "",
            *[f"- `{key}`" for key in payload.get("retry_stable_segment_keys") or []],
        ]
    ) + "\n"


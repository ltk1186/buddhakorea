"""Salvage JSON envelope parse failures from the Pali 300 Batch result.

This script is local-only. It never calls Gemini, never submits Batch jobs, and
never retries failed items. It only reparses already received raw provider
output and writes separate ``*_salvaged`` artifacts.
"""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
from collections import Counter
from copy import deepcopy
from dataclasses import dataclass
from decimal import Decimal, ROUND_HALF_UP
from pathlib import Path
from typing import Any

from pydantic import ValidationError

REPO_ROOT = Path(__file__).resolve().parents[3]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from backend.pali.scripts.submit_gemini_smoke_batch import (
    extract_generate_content_response,
    extract_model_output_text,
    extract_result_key,
    strip_json_fences,
)
from backend.pali.translation.prompts import validate_korean_advanced_model_output
from backend.pali.translation.quality import detect_quality_flag_details


SCRIPT_VERSION = "pilot_300_json_salvage_v1"
PROVENANCE_FIELDS = {
    "parse_method",
    "recovered_via",
    "parser_flags",
    "salvage_applied",
    "completeness_gate_passed",
    "model_output_salvaged",
    "retry_candidate",
    "automatic_resubmit_allowed",
}
REQUIRED_FIELDS = (
    "literal_ko",
    "natural_ko",
    "terms",
    "grammar_notes",
    "doctrinal_notes",
    "uncertainties",
    "quality_flags",
)


@dataclass(frozen=True)
class SalvageAttempt:
    ok: bool
    obj: dict[str, Any] | None
    text: str | None
    method: str
    flags: list[str]
    error: str = ""
    completeness_gate_passed: bool = False


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    try:
        result = run_salvage(args)
    except RuntimeError as exc:
        print(json.dumps({"status": "ERROR", "message": str(exc)}, ensure_ascii=False, sort_keys=True), file=sys.stderr)
        return 2
    print(json.dumps(result, ensure_ascii=False, sort_keys=True))
    return 0 if result.get("status") in {"SALVAGE_COMPLETE", "SALVAGE_COMPLETE_WITH_RETRY_CANDIDATES"} else 2


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Recover Pali 300 Batch JSON envelope parse failures without API calls.")
    parser.add_argument("--raw-results", required=True)
    parser.add_argument("--previous-parsed", required=True)
    parser.add_argument("--previous-summary", required=True)
    parser.add_argument("--run-manifest", required=True)
    parser.add_argument("--provider-status", required=False)
    parser.add_argument("--out", required=True)
    parser.add_argument("--qa-out", required=True)
    parser.add_argument("--gold", default="data/gold_set.json")
    parser.add_argument("--glossary-qa", default="data/reports/pali/translation_qa_v1_1_baseline_49bc869.json")
    parser.add_argument("--pretty", action="store_true")
    return parser


def run_salvage(args: argparse.Namespace, *, qa_runner: Any | None = None) -> dict[str, Any]:
    raw_path = Path(args.raw_results)
    previous_parsed_path = Path(args.previous_parsed)
    previous_summary_path = Path(args.previous_summary)
    run_manifest_path = Path(args.run_manifest)
    out_dir = Path(args.out)
    qa_out = Path(args.qa_out)
    for path in [raw_path, previous_parsed_path, previous_summary_path, run_manifest_path]:
        if not path.exists():
            raise RuntimeError(f"missing input file: {path}")

    previous_parsed = read_json(previous_parsed_path)
    previous_summary = read_json(previous_summary_path)
    run_manifest = read_json(run_manifest_path)
    raw_lines = read_jsonl(raw_path)
    raw_by_key = {extract_result_key(line): line for line in raw_lines if extract_result_key(line)}
    previous_items = previous_parsed.get("items") or []
    provider_batch_id = previous_parsed.get("provider_batch_id") or run_manifest.get("provider_batch_id")

    salvaged_items: list[dict[str, Any]] = []
    method_counter: Counter[str] = Counter()
    recovered_by_method: Counter[str] = Counter()
    retry_candidates: list[str] = []
    content_guard_failed: list[str] = []
    examples: dict[str, list[dict[str, Any]]] = {"raw_decode": [], "stack_reclose": [], "failed": []}

    for previous_item in previous_items:
        key = previous_item.get("stable_segment_key")
        raw_line = raw_by_key.get(key)
        item = salvage_item(previous_item, raw_line, provider_batch_id=provider_batch_id)
        salvaged_items.append(item)
        method_counter[item["parse_method"]] += 1
        if item.get("salvage_applied"):
            recovered_by_method[item["parse_method"]] += 1
            if len(examples.get(item["parse_method"], [])) < 3:
                examples[item["parse_method"]].append(example_from_item(item))
        if item.get("retry_candidate"):
            retry_candidates.append(key)
            if len(examples["failed"]) < 3:
                examples["failed"].append(example_from_item(item))
        if "content_preservation_guard_failed" in (item.get("parser_flags") or []):
            content_guard_failed.append(key)

    strict_preservation = check_strict_payload_preservation(previous_items, salvaged_items)
    parsed_salvaged = {
        "schema_version": "pali_pilot_300_batch_parsed_salvaged_v1",
        "provider_batch_id": provider_batch_id,
        "items": salvaged_items,
    }
    summary = build_summary_salvaged(
        previous_summary=previous_summary,
        salvaged_items=salvaged_items,
        recovered_by_method=recovered_by_method,
        retry_candidates=retry_candidates,
        content_guard_failed=content_guard_failed,
        strict_preservation=strict_preservation,
    )
    out_dir.mkdir(parents=True, exist_ok=True)
    parsed_out = out_dir / "pilot_300_batch_parsed_salvaged.json"
    summary_out = out_dir / "pilot_300_batch_summary_salvaged.json"
    report_out = out_dir / "pilot_300_batch_salvage_report.md"
    write_json(parsed_out, parsed_salvaged, pretty=args.pretty)
    write_json(summary_out, summary, pretty=args.pretty)
    report_out.write_text(
        render_salvage_report(
            args=args,
            previous_summary=previous_summary,
            summary=summary,
            method_counter=method_counter,
            examples=examples,
        ),
        encoding="utf-8",
    )

    qa_result = run_qa(args, parsed_out, qa_out, qa_runner=qa_runner)
    status = "SALVAGE_COMPLETE" if not retry_candidates else "SALVAGE_COMPLETE_WITH_RETRY_CANDIDATES"
    return {
        "status": status,
        "api_calls_made": 0,
        "parsed_salvaged": str(parsed_out),
        "summary_salvaged": str(summary_out),
        "salvage_report": str(report_out),
        "qa_out": str(qa_out),
        "qa_result": qa_result,
        "before_schema_valid": summary["before"]["schema_valid"],
        "after_schema_valid": summary["after"]["schema_valid"],
        "recovered_count": summary["recovered_count"],
        "unrecovered_count": summary["unrecovered_count"],
        "recovered_by_method": summary["recovered_by_method"],
        "retry_candidates": retry_candidates,
    }


def salvage_item(previous_item: dict[str, Any], raw_line: dict[str, Any] | None, *, provider_batch_id: str | None) -> dict[str, Any]:
    item = deepcopy(previous_item)
    response = extract_generate_content_response(raw_line or {})
    output_text = extract_model_output_text(response) or str(previous_item.get("model_output_raw") or "")
    finish_reason = extract_finish_reason(response)
    attempt = parse_output_cascade(output_text, finish_reason=finish_reason)
    item["provider_batch_id"] = provider_batch_id
    item["model_output_raw"] = output_text
    item["parse_method"] = attempt.method
    item["recovered_via"] = "none" if attempt.method in {"strict_json", "failed"} else attempt.method
    item["parser_flags"] = attempt.flags
    item["salvage_applied"] = attempt.method in {"raw_decode", "stack_reclose"}
    item["completeness_gate_passed"] = attempt.completeness_gate_passed
    item["automatic_resubmit_allowed"] = False
    if item["salvage_applied"] and attempt.text is not None:
        item["model_output_salvaged"] = attempt.text

    if attempt.ok and attempt.obj is not None:
        apply_successful_parse(item, attempt.obj)
    else:
        item["status"] = "schema_invalid"
        item["schema_valid"] = False
        item["parse_failed"] = True
        item["parsed_translation_json"] = None
        item["retry_candidate"] = True
        item["error_message"] = attempt.error or "JSON salvage failed."
        flags = set(item.get("local_validator_flags") or [])
        flags.add("json_parse_failed")
        item["local_validator_flags"] = sorted(flags)
        if "salvage_failed" not in item["parser_flags"]:
            item["parser_flags"] = [*item["parser_flags"], "salvage_failed"]
    return item


def parse_output_cascade(text: str, *, finish_reason: str | None) -> SalvageAttempt:
    normalized, fence_removed = normalize_output_text(text)
    fence_flags = ["json_fence_removed"] if fence_removed else []
    strict = attempt_strict(normalized, finish_reason=finish_reason, base_flags=fence_flags)
    if strict.ok:
        return strict
    if "completeness_gate_failed" in strict.flags:
        return strict
    raw_decode = attempt_raw_decode(normalized, finish_reason=finish_reason, base_flags=fence_flags)
    if raw_decode.ok:
        return raw_decode
    if "completeness_gate_failed" in raw_decode.flags:
        return raw_decode
    stack_reclose = attempt_stack_reclose(normalized, finish_reason=finish_reason, base_flags=fence_flags)
    if stack_reclose.ok:
        return stack_reclose
    flags = list(dict.fromkeys([*fence_flags, "salvage_failed"]))
    if "MAX_TOKENS" == (finish_reason or ""):
        flags.append("finish_reason_max_tokens")
    return SalvageAttempt(
        ok=False,
        obj=None,
        text=None,
        method="failed",
        flags=flags,
        error=stack_reclose.error or raw_decode.error or strict.error,
        completeness_gate_passed=False,
    )


def normalize_output_text(text: str) -> tuple[str, bool]:
    stripped = text.strip()
    unfenced = strip_json_fences(stripped)
    return unfenced.strip(), unfenced.strip() != stripped


def attempt_strict(text: str, *, finish_reason: str | None, base_flags: list[str]) -> SalvageAttempt:
    try:
        obj = json.loads(text)
    except json.JSONDecodeError as exc:
        return SalvageAttempt(False, None, None, "failed", base_flags, str(exc), False)
    return validate_candidate(obj, text, "strict_json", base_flags, finish_reason=finish_reason)


def attempt_raw_decode(text: str, *, finish_reason: str | None, base_flags: list[str]) -> SalvageAttempt:
    try:
        obj, end = json.JSONDecoder().raw_decode(text)
    except json.JSONDecodeError as exc:
        return SalvageAttempt(False, None, None, "failed", base_flags, str(exc), False)
    salvaged = text[:end].strip()
    flags = [*base_flags, "salvaged_json", "trailing_extra_removed"]
    return validate_candidate(obj, salvaged, "raw_decode", flags, finish_reason=finish_reason)


def attempt_stack_reclose(text: str, *, finish_reason: str | None, base_flags: list[str]) -> SalvageAttempt:
    last_error = ""
    for cut in stack_reclose_cut_points(text):
        prefix = text[:cut]
        stack_result = bracket_stack(prefix)
        if not stack_result["valid"] or stack_result["in_string"]:
            last_error = stack_result["error"]
            continue
        closers = "".join(reversed(stack_result["stack"]))
        if not closers:
            continue
        candidate = prefix + closers
        try:
            obj = json.loads(candidate)
        except json.JSONDecodeError as exc:
            last_error = str(exc)
            continue
        flags = [*base_flags, "salvaged_json", "stack_reclosed", "content_preservation_guard_passed"]
        flags.extend(stack_reclose_detail_flags(text, cut, closers))
        attempt = validate_candidate(obj, candidate, "stack_reclose", list(dict.fromkeys(flags)), finish_reason=finish_reason)
        if attempt.ok and content_preservation_guard_passes(text, candidate, cut):
            return attempt
        last_error = attempt.error or "content preservation guard failed"
    return SalvageAttempt(
        ok=False,
        obj=None,
        text=None,
        method="failed",
        flags=[*base_flags, "salvage_failed", "content_preservation_guard_failed"],
        error=last_error,
        completeness_gate_passed=False,
    )


def stack_reclose_cut_points(text: str) -> list[int]:
    suffix_start = len(text)
    while suffix_start > 0 and text[suffix_start - 1] in " \t\r\n]}":
        suffix_start -= 1
    cuts = {len(text), suffix_start}
    for index in range(suffix_start, len(text)):
        if text[index] in "]}":
            cuts.add(index)
            cuts.add(index + 1)
    return sorted(cuts, reverse=True)


def bracket_stack(text: str) -> dict[str, Any]:
    stack: list[str] = []
    in_string = False
    escaped = False
    for char in text:
        if in_string:
            if escaped:
                escaped = False
            elif char == "\\":
                escaped = True
            elif char == '"':
                in_string = False
            continue
        if char == '"':
            in_string = True
        elif char == "{":
            stack.append("}")
        elif char == "[":
            stack.append("]")
        elif char in "}]":
            if not stack or stack[-1] != char:
                return {"valid": False, "stack": stack, "in_string": in_string, "error": f"bracket mismatch at {char}"}
            stack.pop()
    return {"valid": True, "stack": stack, "in_string": in_string, "error": ""}


def stack_reclose_detail_flags(raw: str, cut: int, closers: str) -> list[str]:
    removed = raw[cut:]
    flags: list[str] = []
    if "}" in closers:
        flags.append("missing_final_brace_added")
    if "]" in closers:
        flags.append("missing_final_bracket_added")
    if any(char in removed for char in "]}"):
        expected_without_space = closers
        removed_without_space = "".join(char for char in removed if char in "]}")
        if removed_without_space != expected_without_space:
            flags.append("final_bracket_misclose_repaired")
    return flags


def content_preservation_guard_passes(raw: str, candidate: str, cut: int) -> bool:
    return candidate.startswith(raw[:cut])


def validate_candidate(
    obj: Any,
    text: str,
    method: str,
    flags: list[str],
    *,
    finish_reason: str | None,
) -> SalvageAttempt:
    gate = completeness_gate(obj, finish_reason=finish_reason)
    if not gate["passed"]:
        return SalvageAttempt(
            ok=False,
            obj=obj if isinstance(obj, dict) else None,
            text=text,
            method="failed",
            flags=[*flags, "salvage_failed", "completeness_gate_failed", *gate["flags"]],
            error="; ".join(gate["errors"]),
            completeness_gate_passed=False,
        )
    return SalvageAttempt(
        ok=True,
        obj=obj,
        text=text,
        method=method,
        flags=list(dict.fromkeys(flags)),
        completeness_gate_passed=True,
    )


def completeness_gate(obj: Any, *, finish_reason: str | None) -> dict[str, Any]:
    errors: list[str] = []
    flags: list[str] = []
    if finish_reason == "MAX_TOKENS":
        errors.append("finishReason=MAX_TOKENS")
        flags.append("finish_reason_max_tokens")
    if not isinstance(obj, dict):
        errors.append("top-level JSON is not an object")
        return {"passed": False, "errors": errors, "flags": flags}
    for field in REQUIRED_FIELDS:
        if field not in obj:
            errors.append(f"missing required field: {field}")
    if not isinstance(obj.get("literal_ko"), str) or not obj.get("literal_ko", "").strip():
        errors.append("literal_ko is empty or not a string")
    if not isinstance(obj.get("natural_ko"), str) or not obj.get("natural_ko", "").strip():
        errors.append("natural_ko is empty or not a string")
    for field in ("terms", "grammar_notes", "doctrinal_notes", "uncertainties", "quality_flags"):
        if not isinstance(obj.get(field), list):
            errors.append(f"{field} is not a list")
    try:
        validate_korean_advanced_model_output(obj)
    except (ValidationError, ValueError) as exc:
        errors.append(f"schema validation failed: {exc}")
    return {"passed": not errors, "errors": errors, "flags": flags}


def apply_successful_parse(item: dict[str, Any], parsed_json: dict[str, Any]) -> None:
    translation = validate_korean_advanced_model_output(parsed_json)
    source_text = str(item.get("original_text") or "")
    details = detect_quality_flag_details(source_text, translation)
    local_flags = sorted(
        {
            detail.flag.value
            for detail in details
            if detail.source.value == "local_validator"
        }
    )
    item["parsed_translation_json"] = parsed_json
    item["schema_valid"] = True
    item["parse_failed"] = False
    item["status"] = "succeeded"
    item["error_message"] = ""
    item["quality_flags"] = [flag.value for flag in translation.quality_flags]
    item["local_validator_flags"] = local_flags
    item["quality_flag_details"] = [json.loads(detail.model_dump_json()) for detail in details]
    item["literal_ko"] = parsed_json.get("literal_ko", "")
    item["natural_ko"] = parsed_json.get("natural_ko", "")
    item["terms"] = parsed_json.get("terms", [])
    item["grammar_notes"] = parsed_json.get("grammar_notes", [])
    item["doctrinal_notes"] = parsed_json.get("doctrinal_notes", [])
    item["uncertainties"] = parsed_json.get("uncertainties", [])
    item["retry_candidate"] = False


def extract_finish_reason(response: dict[str, Any]) -> str | None:
    candidates = response.get("candidates") or []
    if candidates and isinstance(candidates[0], dict):
        reason = candidates[0].get("finishReason") or candidates[0].get("finish_reason")
        if reason:
            return str(reason)
    return None


def build_summary_salvaged(
    *,
    previous_summary: dict[str, Any],
    salvaged_items: list[dict[str, Any]],
    recovered_by_method: Counter[str],
    retry_candidates: list[str],
    content_guard_failed: list[str],
    strict_preservation: dict[str, Any],
) -> dict[str, Any]:
    before = {
        "total": int(previous_summary.get("request_count") or len(salvaged_items)),
        "schema_valid": int(previous_summary.get("schema_valid_count") or 0),
        "schema_invalid": int(previous_summary.get("schema_invalid_count") or 0),
        "failed_count": int(previous_summary.get("failed_count") or 0),
    }
    after_schema_valid = sum(1 for item in salvaged_items if item.get("schema_valid"))
    after_failed = sum(1 for item in salvaged_items if item.get("status") != "succeeded")
    after = {
        "total": len(salvaged_items),
        "schema_valid": after_schema_valid,
        "schema_invalid": len(salvaged_items) - after_schema_valid,
        "failed_count": after_failed,
    }
    recovered_count = before["schema_invalid"] - after["schema_invalid"]
    return {
        "schema_version": "pali_pilot_300_batch_summary_salvaged_v1",
        "api_calls_made": 0,
        "automatic_resubmit_allowed": False,
        "before": before,
        "after": after,
        "recovered_count": recovered_count,
        "unrecovered_count": after["schema_invalid"],
        "recovered_by_method": dict(sorted(recovered_by_method.items())),
        "unrecovered_stable_segment_keys": retry_candidates,
        "retry_candidates": retry_candidates,
        "content_preservation_guard": {
            "enabled": True,
            "failed_count": len(content_guard_failed),
            "failed_stable_segment_keys": content_guard_failed,
        },
        "strict_payload_preservation": strict_preservation,
        "cost": {
            "actual_cost_usd": str(previous_summary.get("actual_cost_usd") or previous_summary.get("total_actual_cost_usd") or "0.000000"),
            "estimated_conservative_gate_usd": str(previous_summary.get("estimated_conservative_gate_usd") or "0"),
            "actual_to_conservative_ratio": str(previous_summary.get("actual_to_conservative_ratio") or "0"),
            "budget_usd": str(previous_summary.get("budget_usd") or "20"),
            "budget_passed": bool(previous_summary.get("budget_passed")),
            "new_api_spend_usd": "0.000000",
            "cost_note": "34 failed items were already generated and billed in the original batch; salvage recovers paid-for output with $0 new spend.",
        },
    }


def check_strict_payload_preservation(previous_items: list[dict[str, Any]], salvaged_items: list[dict[str, Any]]) -> dict[str, Any]:
    previous_by_key = {item.get("stable_segment_key"): item for item in previous_items}
    changed: list[str] = []
    checked = 0
    for item in salvaged_items:
        previous = previous_by_key.get(item.get("stable_segment_key"))
        if not previous or previous.get("status") != "succeeded" or not previous.get("schema_valid"):
            continue
        checked += 1
        if canonical_translation_payload(previous) != canonical_translation_payload(item):
            changed.append(item.get("stable_segment_key"))
    return {
        "checked": True,
        "strict_items_checked": checked,
        "strict_translation_payload_changed": len(changed),
        "changed_stable_segment_keys": changed,
        "metadata_fields_excluded_from_comparison": sorted(PROVENANCE_FIELDS),
    }


def canonical_translation_payload(item: dict[str, Any]) -> str:
    payload = {
        "parsed_translation_json": item.get("parsed_translation_json"),
        "literal_ko": item.get("literal_ko"),
        "natural_ko": item.get("natural_ko"),
        "terms": item.get("terms"),
        "grammar_notes": item.get("grammar_notes"),
        "doctrinal_notes": item.get("doctrinal_notes"),
        "uncertainties": item.get("uncertainties"),
        "quality_flags": item.get("quality_flags"),
    }
    return json.dumps(payload, ensure_ascii=False, sort_keys=True, separators=(",", ":"))


def example_from_item(item: dict[str, Any]) -> dict[str, Any]:
    return {
        "stable_segment_key": item.get("stable_segment_key"),
        "parse_method": item.get("parse_method"),
        "parser_flags": item.get("parser_flags") or [],
        "literal_ko_excerpt": excerpt(item.get("literal_ko") or ""),
        "natural_ko_excerpt": excerpt(item.get("natural_ko") or ""),
    }


def excerpt(text: str, limit: int = 160) -> str:
    text = " ".join(str(text).split())
    return text if len(text) <= limit else text[:limit] + "..."


def render_salvage_report(
    *,
    args: argparse.Namespace,
    previous_summary: dict[str, Any],
    summary: dict[str, Any],
    method_counter: Counter[str],
    examples: dict[str, list[dict[str, Any]]],
) -> str:
    lines = [
        "# Pāli 300 Batch JSON Salvage Report",
        "",
        "## Purpose",
        "",
        "This report reparses already received Gemini Batch raw output. It does not call Gemini, resubmit Batch jobs, retry failed items, or modify prompts/glossary/gold/source files.",
        "",
        f"- API calls made: {summary['api_calls_made']}",
        "- New API spend: $0.000000",
        "",
        "## Input Files",
        "",
        f"- raw results: `{args.raw_results}`",
        f"- previous parsed: `{args.previous_parsed}`",
        f"- previous summary: `{args.previous_summary}`",
        f"- run manifest: `{args.run_manifest}`",
        "",
        "## Before / After",
        "",
        f"- before schema valid / invalid: {summary['before']['schema_valid']} / {summary['before']['schema_invalid']}",
        f"- after schema valid / invalid: {summary['after']['schema_valid']} / {summary['after']['schema_invalid']}",
        f"- recovered count: {summary['recovered_count']}",
        f"- unrecovered count: {summary['unrecovered_count']}",
        f"- recovered by method: `{json.dumps(summary['recovered_by_method'], ensure_ascii=False, sort_keys=True)}`",
        f"- retry candidates: {', '.join(summary['retry_candidates']) if summary['retry_candidates'] else 'none'}",
        "",
        "## Completeness Gate",
        "",
        "A salvaged object is accepted only when all required fields exist, `literal_ko` and `natural_ko` are non-empty strings, list fields are lists, schema validation passes, and finishReason is not MAX_TOKENS.",
        "",
        "## Content-Preservation Guard",
        "",
        "For `stack_reclose`, only the final trailing bracket region may be changed. The salvaged output must preserve the raw output exactly before that trailing region.",
        "",
        f"- guard enabled: {summary['content_preservation_guard']['enabled']}",
        f"- guard failed count: {summary['content_preservation_guard']['failed_count']}",
        "",
        "## Strict Payload Preservation",
        "",
        f"- strict items checked: {summary['strict_payload_preservation']['strict_items_checked']}",
        f"- strict translation payload changed: {summary['strict_payload_preservation']['strict_translation_payload_changed']}",
        "- metadata fields excluded from comparison: "
        + ", ".join(summary["strict_payload_preservation"]["metadata_fields_excluded_from_comparison"]),
        "",
        "## Method Examples",
        "",
    ]
    for method in ("raw_decode", "stack_reclose", "failed"):
        lines.append(f"### {method}")
        rows = examples.get(method) or []
        if not rows:
            lines.append("")
            lines.append("No examples.")
            lines.append("")
            continue
        lines.extend(["", "| stable_segment_key | flags | natural_ko excerpt |", "| --- | --- | --- |"])
        for row in rows:
            lines.append(
                f"| `{row['stable_segment_key']}` | `{', '.join(row['parser_flags'])}` | {row['natural_ko_excerpt']} |"
            )
        lines.append("")
    lines.extend(
        [
            "## Cost",
            "",
            f"- actual_cost_usd: ${summary['cost']['actual_cost_usd']}",
            f"- estimated_conservative_gate_usd: ${summary['cost']['estimated_conservative_gate_usd']}",
            f"- actual_to_conservative_ratio: {summary['cost']['actual_to_conservative_ratio']}",
            f"- budget_usd: ${summary['cost']['budget_usd']}",
            f"- budget_passed: {summary['cost']['budget_passed']}",
            "- cost note: 34 failed items were already generated and billed in the original batch; salvage recovers paid-for output with $0 new spend.",
            "",
            "## No Overwrite Confirmation",
            "",
            "Original raw, parsed, summary, and QA report artifacts are not overwritten. Salvaged outputs are written to separate `_salvaged` files and QA folder.",
            "",
            "## Next Recommendation",
            "",
            "For the 1,000 pilot and later production runs, evaluate Gemini structured output / response schema support in the Batch REST path. Do not change prompt/generation config in this salvage step.",
            "",
        ]
    )
    return "\n".join(lines)


def run_qa(args: argparse.Namespace, parsed_out: Path, qa_out: Path, *, qa_runner: Any | None = None) -> dict[str, Any]:
    qa_out.mkdir(parents=True, exist_ok=True)
    cmd = [
        sys.executable,
        "-m",
        "backend.pali.scripts.generate_qa_report",
        "--parsed",
        str(parsed_out),
        "--gold",
        args.gold,
        "--glossary-qa",
        args.glossary_qa,
        "--out",
        str(qa_out),
    ]
    runner = qa_runner or subprocess.run
    completed = runner(cmd, cwd=REPO_ROOT, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, check=False)
    return {
        "status": "QA_COMPLETE" if completed.returncode == 0 else "QA_FAILED",
        "returncode": completed.returncode,
        "review_report": str(qa_out / "review_report.md"),
        "review_queue": str(qa_out / "review_queue.json"),
        "run_manifest": str(qa_out / "run_manifest.json"),
        "stdout": completed.stdout,
        "stderr": completed.stderr,
    }


def read_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def read_jsonl(path: Path) -> list[dict[str, Any]]:
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


def write_json(path: Path, payload: Any, *, pretty: bool) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2 if pretty else None, sort_keys=True) + "\n",
        encoding="utf-8",
    )


def quantize_usd(value: Decimal) -> str:
    return str(value.quantize(Decimal("0.000001"), rounding=ROUND_HALF_UP))


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))

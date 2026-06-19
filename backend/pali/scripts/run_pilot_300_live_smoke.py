"""Run optional live Gemini generateContent smoke for the Pali 300 pilot.

This script is not a Batch submitter and never calls Gemini Batch APIs. It may
call Gemini generateContent for at most five selected segments only when the
explicit smoke gates are enabled. It reuses the Step 2 unsubmitted JSONL
payload and does not re-render prompts.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
from dataclasses import dataclass
from datetime import datetime, timezone
from decimal import Decimal, InvalidOperation, ROUND_HALF_UP
from pathlib import Path
from typing import Any, Protocol

from pydantic import ValidationError

REPO_ROOT = Path(__file__).resolve().parents[3]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from backend.pali.scripts.build_pilot_300_manifest import selection_content_sha256
from backend.pali.scripts.run_pilot_300_preflight import parse_decimal_money
from backend.pali.translation.budget import (
    PriceProfile,
    TokenEstimate,
    actual_cost_from_usage,
    estimate_request_cost,
    parse_usage_metadata,
)
from backend.pali.translation.prompts import (
    KOREAN_ADVANCED_PROMPT_MODEL,
    KOREAN_ADVANCED_PROMPT_VERSION,
    validate_korean_advanced_model_output,
)


RUN_ID = "pilot_300_v1_smoke"
SCRIPT_VERSION = "pilot_300_live_smoke_v1"
DEFAULT_MODEL = "models/gemini-3.1-pro-preview"
DEFAULT_API_BASE_URL = "https://generativelanguage.googleapis.com/v1beta"
JSONL_BASENAME = "pilot_300_v1_batch_unsubmitted.jsonl"
PRICE_PROFILE = PriceProfile(
    input_usd_per_million_tokens=Decimal("1.0"),
    output_usd_per_million_tokens=Decimal("6.0"),
    thinking_usd_per_million_tokens=Decimal("6.0"),
)
GEMINI_API_KEY_ENV_CANDIDATES = (
    "GEMINI_API_KEY",
    "GOOGLE_API_KEY",
    "GOOGLE_GENAI_API_KEY",
    "PALI_GEMINI_API_KEY",
)
RETRYABLE_STATUS_CODES = {408, 429, 500, 502, 503, 504}


class GenerateContentClient(Protocol):
    def generate_content(self, *, model: str, payload: dict[str, Any]) -> dict[str, Any]:
        """Return a GenerateContentResponse-like dict."""


class ProviderError(RuntimeError):
    def __init__(self, status_code: int | None, message: str):
        super().__init__(message)
        self.status_code = status_code
        self.message = message


@dataclass(frozen=True)
class SmokePaths:
    selection: Path
    results: Path
    summary: Path
    run_manifest: Path
    raw_jsonl: Path


class GeminiGenerateContentRestClient:
    def __init__(
        self,
        *,
        api_key: str,
        base_url: str = DEFAULT_API_BASE_URL,
        timeout_seconds: int = 120,
    ) -> None:
        self._api_key = api_key
        self._base_url = base_url.rstrip("/")
        self._timeout_seconds = timeout_seconds

    def generate_content(self, *, model: str, payload: dict[str, Any]) -> dict[str, Any]:
        model_path = model if model.startswith("models/") else f"models/{model}"
        url = f"{self._base_url}/{model_path}:generateContent"
        separator = "&" if "?" in url else "?"
        url_with_key = f"{url}{separator}{urllib.parse.urlencode({'key': self._api_key})}"
        request = urllib.request.Request(
            url_with_key,
            data=json.dumps(payload).encode("utf-8"),
            method="POST",
            headers={"Content-Type": "application/json"},
        )
        try:
            with urllib.request.urlopen(request, timeout=self._timeout_seconds) as response:
                return json.loads(response.read().decode("utf-8"))
        except urllib.error.HTTPError as exc:
            body = exc.read().decode("utf-8", errors="replace")
            raise ProviderError(exc.code, sanitize_error_message(body, self._api_key)) from exc
        except urllib.error.URLError as exc:
            raise ProviderError(None, sanitize_error_message(str(exc), self._api_key)) from exc


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    report = run_live_smoke(args)
    print(
        json.dumps(
            {
                "status": report["status"],
                "results": str(Path(args.out) / "pilot_300_v1_smoke_results.json"),
                "summary": str(Path(args.out) / "pilot_300_v1_smoke_summary.md"),
                "sample_count_attempted": report["sample_count_attempted"],
                "sample_count_succeeded": report["sample_count_succeeded"],
                "blocking_reasons": report["blocking_reasons"],
            },
            ensure_ascii=False,
            sort_keys=True,
        )
    )
    return 2 if report["status"] in {"BLOCKED", "FAIL"} else 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Run optional <=5 segment Gemini generateContent smoke from Step 2 unsubmitted JSONL."
    )
    parser.add_argument("--manifest", required=True)
    parser.add_argument("--readiness", required=True)
    parser.add_argument("--jsonl", required=True)
    parser.add_argument("--jsonl-manifest", required=True)
    parser.add_argument("--cost-estimate", required=True)
    parser.add_argument("--out", required=True)
    parser.add_argument("--max-segments", type=int, default=5)
    parser.add_argument("--budget-usd", default="0.50")
    parser.add_argument("--expected-selection-sha")
    parser.add_argument("--model", default=DEFAULT_MODEL)
    parser.add_argument("--timeout-seconds", type=int, default=120)
    parser.add_argument("--max-attempts-per-segment", type=int, default=3)
    parser.add_argument("--retry-backoff-seconds", type=float, default=1.0)
    parser.add_argument("--enable-smoke", action="store_true")
    parser.add_argument("--user-green-light", action="store_true")
    parser.add_argument("--pretty", action="store_true")
    return parser


def run_live_smoke(
    args: argparse.Namespace,
    *,
    client: GenerateContentClient | None = None,
    sleep_fn: Any = time.sleep,
) -> dict[str, Any]:
    out_dir = Path(args.out)
    out_dir.mkdir(parents=True, exist_ok=True)
    paths = SmokePaths(
        selection=out_dir / "pilot_300_v1_smoke_selection.json",
        results=out_dir / "pilot_300_v1_smoke_results.json",
        summary=out_dir / "pilot_300_v1_smoke_summary.md",
        run_manifest=out_dir / "pilot_300_v1_smoke_run_manifest.json",
        raw_jsonl=out_dir / "pilot_300_v1_smoke_raw.jsonl",
    )

    manifest = read_json(Path(args.manifest))
    readiness = read_json(Path(args.readiness))
    jsonl_manifest = read_json(Path(args.jsonl_manifest))
    cost_estimate = read_json(Path(args.cost_estimate))
    jsonl_lines = read_jsonl(Path(args.jsonl))
    budget_usd = parse_decimal_money(args.budget_usd, field_name="budget_usd")

    selection_sha = selection_content_sha256(manifest)
    selected_items = select_smoke_samples(manifest, max_segments=args.max_segments)
    selection = build_selection_artifact(
        items=selected_items,
        selection_content_sha256_value=selection_sha,
    )
    write_json(paths.selection, selection, pretty=args.pretty)

    credential = resolve_gemini_env_credential()
    blocking = safety_gate(
        args=args,
        readiness=readiness,
        selection_sha=selection_sha,
        budget_usd=budget_usd,
        credential_present=credential is not None,
    )
    request_context = build_request_context(
        selected_items=selected_items,
        jsonl_lines=jsonl_lines,
        jsonl_manifest=jsonl_manifest,
        cost_estimate=cost_estimate,
        jsonl_path=Path(args.jsonl),
    )

    raw_rows: list[dict[str, Any]] = []
    if blocking:
        results = build_base_results(
            args=args,
            selection_sha=selection_sha,
            selected_items=selected_items,
            request_context=request_context,
            budget_usd=budget_usd,
            enabled=args.enable_smoke,
            user_green_light=args.user_green_light,
            blocking_reasons=blocking,
            credential=credential,
        )
        results["status"] = "BLOCKED"
        write_artifacts(paths, results, raw_rows, args=args, credential=credential, pretty=args.pretty)
        return results

    if client is None:
        assert credential is not None
        client = GeminiGenerateContentRestClient(
            api_key=credential["value"],
            timeout_seconds=args.timeout_seconds,
        )

    results = build_base_results(
        args=args,
        selection_sha=selection_sha,
        selected_items=selected_items,
        request_context=request_context,
        budget_usd=budget_usd,
        enabled=True,
        user_green_light=True,
        blocking_reasons=[],
        credential=credential,
    )
    accumulated_cost = Decimal("0")
    stopped_for_budget = False
    for context in request_context:
        if accumulated_cost > budget_usd:
            stopped_for_budget = True
            break
        item_result, raw_row = execute_smoke_item(
            context=context,
            client=client,
            model=args.model,
            budget_usd=budget_usd,
            accumulated_cost=accumulated_cost,
            max_attempts=max(1, int(args.max_attempts_per_segment)),
            retry_backoff_seconds=max(0.0, float(args.retry_backoff_seconds)),
            sleep_fn=sleep_fn,
        )
        raw_rows.append(raw_row)
        results["items"].append(item_result)
        accumulated_cost += parse_decimal_money(
            item_result["usage"]["actual_cost_usd"],
            field_name="item.usage.actual_cost_usd",
        )
        if accumulated_cost > budget_usd:
            stopped_for_budget = True
            results["warnings"].append("smoke_budget_exceeded_after_request")
            break

    finalize_results(results, stopped_for_budget=stopped_for_budget)
    write_artifacts(paths, results, raw_rows, args=args, credential=credential, pretty=args.pretty)
    return results


def safety_gate(
    *,
    args: argparse.Namespace,
    readiness: dict[str, Any],
    selection_sha: str,
    budget_usd: Decimal,
    credential_present: bool,
) -> list[str]:
    reasons: list[str] = []
    if not args.enable_smoke:
        reasons.append("BLOCKED_SMOKE_NOT_ENABLED")
    if not args.user_green_light:
        reasons.append("BLOCKED_USER_GREEN_LIGHT_REQUIRED")
    if int(args.max_segments) > 5:
        reasons.append("BLOCKED_TOO_MANY_SEGMENTS")
    if budget_usd > Decimal("0.50"):
        reasons.append("BLOCKED_SMOKE_BUDGET_TOO_HIGH")
    if readiness.get("readiness_status") != "PASS_READY_FOR_USER_APPROVAL":
        reasons.append("BLOCKED_READINESS_NOT_PASS")
    if readiness.get("batch_submission_allowed_now") is not False:
        reasons.append("BLOCKED_UNSAFE_READINESS")
    if args.expected_selection_sha and args.expected_selection_sha != selection_sha:
        reasons.append("BLOCKED_HASH_MISMATCH")
    if not credential_present:
        reasons.append("BLOCKED_MISSING_GEMINI_CREDENTIAL")
    return reasons


def select_smoke_samples(manifest: dict[str, Any], *, max_segments: int) -> list[dict[str, Any]]:
    eligible = [item for item in manifest.get("items") or [] if not is_holdout(item)]
    selected: list[dict[str, Any]] = []
    policies = [
        ("tika_long", lambda item: item.get("selection_bucket") == "tika_long" or (item.get("text_layer") == "tika" and item.get("length_bucket") == "long")),
        ("atthakatha_long", lambda item: item.get("selection_bucket") == "atthakatha_long" or (item.get("text_layer") == "atthakatha" and item.get("length_bucket") == "long")),
        ("s05_verse_or_glossary_risk", lambda item: source_family(item) == "s05" and (item.get("chunk_type") == "verse" or "glossary_risk" in (item.get("secondary_tags") or []))),
        ("abhidhamma_definition", lambda item: item.get("selection_bucket") == "abhidhamma_definition"),
        ("representative_or_heading", lambda item: item.get("selection_bucket") in {"representative_stratified", "heading_title_probe"}),
    ]
    selected_keys: set[str] = set()
    for bucket, predicate in policies:
        if len(selected) >= max_segments:
            break
        candidates = stable_sort([item for item in eligible if predicate(item) and item.get("stable_segment_key") not in selected_keys])
        if not candidates:
            continue
        chosen = dict(candidates[0])
        chosen["smoke_selection_reason"] = bucket
        selected.append(chosen)
        selected_keys.add(chosen["stable_segment_key"])
    if len(selected) < max_segments:
        for item in stable_sort(eligible):
            if len(selected) >= max_segments:
                break
            key = item.get("stable_segment_key")
            if key in selected_keys:
                continue
            chosen = dict(item)
            chosen["smoke_selection_reason"] = "deterministic_fill"
            selected.append(chosen)
            selected_keys.add(key)
    return selected[: max(0, max_segments)]


def is_holdout(item: dict[str, Any]) -> bool:
    return (
        item.get("do_not_use_for_tuning_until_reviewed") is True
        or item.get("pool_candidate") == "holdout_gold"
        or item.get("gold_candidate") is True
    )


def stable_sort(items: list[dict[str, Any]]) -> list[dict[str, Any]]:
    return sorted(items, key=lambda item: stable_key(str(item.get("stable_segment_key") or "")))


def stable_key(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


def source_family(item: dict[str, Any]) -> str:
    source_path = str(item.get("source_path") or "")
    stem = Path(source_path).name
    return stem[:3] if len(stem) >= 3 else "unknown"


def build_selection_artifact(
    *,
    items: list[dict[str, Any]],
    selection_content_sha256_value: str,
) -> dict[str, Any]:
    return {
        "schema_version": "pali_pilot_300_smoke_selection_v1",
        "run_id": RUN_ID,
        "selection_content_sha256": selection_content_sha256_value,
        "sample_count": len(items),
        "selection_policy": "deterministic_non_holdout_bucket_coverage",
        "items": [
            {
                "stable_segment_key": item.get("stable_segment_key"),
                "source_text_hash": item.get("source_text_hash"),
                "text_layer": item.get("text_layer"),
                "length_bucket": item.get("length_bucket"),
                "chunk_type": item.get("chunk_type"),
                "selection_group": item.get("selection_group"),
                "selection_bucket": item.get("selection_bucket"),
                "secondary_tags": item.get("secondary_tags") or [],
                "source_path": item.get("source_path"),
                "smoke_selection_reason": item.get("smoke_selection_reason", ""),
                "holdout_excluded": True,
                "quality_signal": False,
            }
            for item in items
        ],
    }


def build_request_context(
    *,
    selected_items: list[dict[str, Any]],
    jsonl_lines: list[dict[str, Any]],
    jsonl_manifest: dict[str, Any],
    cost_estimate: dict[str, Any],
    jsonl_path: Path,
) -> list[dict[str, Any]]:
    lines_by_key = {line.get("key"): (index, line) for index, line in enumerate(jsonl_lines)}
    sidecar_by_key = {item.get("stable_segment_key"): item for item in jsonl_manifest.get("items") or []}
    estimate_by_key = {item.get("stable_segment_key"): item for item in cost_estimate.get("items") or []}
    contexts: list[dict[str, Any]] = []
    for item in selected_items:
        key = item.get("stable_segment_key")
        if key not in lines_by_key:
            raise RuntimeError(f"selected smoke key missing from JSONL: {key}")
        line_index, line = lines_by_key[key]
        sidecar = sidecar_by_key.get(key) or {}
        expected_index = sidecar.get("jsonl_line_index")
        if expected_index is not None and int(expected_index) != line_index:
            raise RuntimeError(f"JSONL line index mismatch for {key}")
        request = line.get("request") or {}
        validate_generation_config(request)
        generate_payload = batch_request_to_generate_content_payload(request)
        contexts.append(
            {
                "manifest_item": item,
                "jsonl_line_index": line_index,
                "jsonl_line": line,
                "jsonl_request": request,
                "generate_content_payload": generate_payload,
                "sidecar_item": sidecar,
                "estimate_item": estimate_by_key.get(key) or {},
                "jsonl_path": jsonl_path,
            }
        )
    return contexts


def validate_generation_config(request: dict[str, Any]) -> None:
    config = request.get("generation_config") or request.get("generationConfig") or {}
    if Decimal(str(config.get("temperature", "999"))) != Decimal("0.2"):
        raise RuntimeError("invalid generation config temperature")
    mime = config.get("response_mime_type") or config.get("responseMimeType")
    if mime != "application/json":
        raise RuntimeError("invalid response MIME type")


def batch_request_to_generate_content_payload(request: dict[str, Any]) -> dict[str, Any]:
    config = request.get("generation_config") or request.get("generationConfig") or {}
    api_config: dict[str, Any] = {}
    if "temperature" in config:
        api_config["temperature"] = config["temperature"]
    mime = config.get("response_mime_type") or config.get("responseMimeType")
    if mime:
        api_config["responseMimeType"] = mime
    payload: dict[str, Any] = {"contents": request.get("contents") or []}
    if api_config:
        payload["generationConfig"] = api_config
    return payload


def execute_smoke_item(
    *,
    context: dict[str, Any],
    client: GenerateContentClient,
    model: str,
    budget_usd: Decimal,
    accumulated_cost: Decimal,
    max_attempts: int,
    retry_backoff_seconds: float,
    sleep_fn: Any,
) -> tuple[dict[str, Any], dict[str, Any]]:
    attempts = 0
    retry_reasons: list[str] = []
    last_error = ""
    response: dict[str, Any] | None = None
    while attempts < max_attempts:
        attempts += 1
        try:
            response = client.generate_content(model=model, payload=context["generate_content_payload"])
            break
        except ProviderError as exc:
            last_error = exc.message
            if not is_retryable(exc) or attempts >= max_attempts:
                return failed_item(context, model, attempts, retry_reasons, f"provider_error: {last_error}"), {
                    "stable_segment_key": context["manifest_item"].get("stable_segment_key"),
                    "error": sanitize_for_artifact({"status_code": exc.status_code, "message": last_error}),
                }
            retry_reasons.append(f"provider_error_{exc.status_code or 'network'}")
            sleep_fn(retry_backoff_seconds * (2 ** (attempts - 1)))
        except Exception as exc:
            last_error = sanitize_error_message(str(exc), "")
            if attempts >= max_attempts:
                return failed_item(context, model, attempts, retry_reasons, f"provider_error: {last_error}"), {
                    "stable_segment_key": context["manifest_item"].get("stable_segment_key"),
                    "error": sanitize_for_artifact({"message": last_error}),
                }
            retry_reasons.append("temporary_network_error")
            sleep_fn(retry_backoff_seconds * (2 ** (attempts - 1)))

    assert response is not None
    item = parse_live_response_item(
        context=context,
        response=response,
        requested_model=model,
        attempts=attempts,
        retry_reasons=retry_reasons,
    )
    actual_cost = parse_decimal_money(item["usage"]["actual_cost_usd"], field_name="item.usage.actual_cost_usd")
    if accumulated_cost + actual_cost > budget_usd:
        item["warnings"].append("budget_cap_exceeded_after_request")
    return item, {
        "stable_segment_key": context["manifest_item"].get("stable_segment_key"),
        "response": sanitize_for_artifact(response),
    }


def parse_live_response_item(
    *,
    context: dict[str, Any],
    response: dict[str, Any],
    requested_model: str,
    attempts: int,
    retry_reasons: list[str],
) -> dict[str, Any]:
    manifest_item = context["manifest_item"]
    estimate = context["estimate_item"]
    observed_model = find_model_version(response)
    usage = usage_from_response_or_estimate(response, estimate)
    output_text = extract_model_output_text(response)
    status = "succeeded"
    schema_valid = False
    parse_error: str | None = None
    parsed_json: dict[str, Any] | None = None
    warnings: list[str] = []
    if observed_model is None:
        warnings.append("model_version_unavailable")
    model_drift = bool(observed_model and observed_model != requested_model)
    if model_drift:
        warnings.append("model_version_drift")

    if not output_text:
        status = "parse_failed"
        parse_error = "GenerateContentResponse did not include output text."
    else:
        try:
            parsed_json = json.loads(strip_json_fences(output_text))
            validate_korean_advanced_model_output(parsed_json)
            schema_valid = True
        except json.JSONDecodeError as exc:
            status = "parse_failed"
            parse_error = f"JSON parse failed: {exc}"
        except (ValidationError, ValueError) as exc:
            status = "schema_invalid"
            parse_error = str(exc)

    estimate_comparison = compare_to_estimate(usage, estimate)
    warnings.extend(estimate_comparison["warnings"])
    return {
        "stable_segment_key": manifest_item.get("stable_segment_key"),
        "source_text_hash": manifest_item.get("source_text_hash"),
        "jsonl_line_index": context["jsonl_line_index"],
        "jsonl_request_sha256": stable_json_sha256(context["jsonl_request"]),
        "generate_content_payload_sha256": stable_json_sha256(context["generate_content_payload"]),
        "payload_source": JSONL_BASENAME,
        "prompt_reassembled": False,
        "selection_bucket": manifest_item.get("selection_bucket"),
        "text_layer": manifest_item.get("text_layer"),
        "length_bucket": manifest_item.get("length_bucket"),
        "chunk_type": manifest_item.get("chunk_type"),
        "status": status,
        "schema_valid": schema_valid,
        "parse_error": parse_error,
        "parsed_translation_json": parsed_json,
        "quality_signal": False,
        "attempts": attempts,
        "retry_reasons": retry_reasons,
        "requested_model": requested_model,
        "observed_model_version": observed_model or "model_version_unavailable",
        "model_version_drift": model_drift,
        "usage": usage,
        "estimate_comparison": {k: v for k, v in estimate_comparison.items() if k != "warnings"},
        "warnings": warnings,
    }


def usage_from_response_or_estimate(response: dict[str, Any], estimate: dict[str, Any]) -> dict[str, Any]:
    parsed = parse_usage_metadata(response)
    if parsed.usage:
        usage = parsed.usage
        cost = actual_cost_from_usage(usage, PRICE_PROFILE)
        return {
            "input_tokens": usage.prompt_token_count,
            "output_tokens": usage.candidates_token_count,
            "thinking_tokens": usage.thoughts_token_count,
            "total_tokens": usage.total_token_count,
            "actual_cost_usd": str(cost),
            "usage_source": "provider_usage_metadata",
        }
    p90 = estimate.get("planning_p90") or {}
    tokens = TokenEstimate(
        input_tokens=int(p90.get("input_tokens") or 0),
        output_tokens=int(p90.get("output_tokens") or 0),
        thinking_tokens=int(p90.get("thinking_tokens") or 0),
    )
    return {
        "input_tokens": tokens.input_tokens,
        "output_tokens": tokens.output_tokens,
        "thinking_tokens": tokens.thinking_tokens,
        "total_tokens": tokens.input_tokens + tokens.output_tokens + tokens.thinking_tokens,
        "actual_cost_usd": str(estimate_request_cost(tokens, PRICE_PROFILE)),
        "usage_source": "local_estimate_missing_provider_usage",
    }


def compare_to_estimate(usage: dict[str, Any], estimate: dict[str, Any]) -> dict[str, Any]:
    p90 = estimate.get("planning_p90") or {}
    estimated_tokens = int(p90.get("input_tokens") or 0) + int(p90.get("output_tokens") or 0) + int(p90.get("thinking_tokens") or 0)
    actual_tokens = int(usage.get("total_tokens") or 0)
    estimated_cost = parse_decimal_money(p90.get("official_cost_usd") or "0", field_name="estimated_p90_cost_usd")
    actual_cost = parse_decimal_money(usage.get("actual_cost_usd") or "0", field_name="actual_cost_usd")
    token_ratio = decimal_ratio(actual_tokens, estimated_tokens)
    cost_ratio = decimal_ratio(actual_cost, estimated_cost)
    warnings: list[str] = []
    if estimated_cost > 0 and actual_cost > estimated_cost * Decimal("1.5"):
        warnings.append("cost_estimate_divergence_gt_1_5x")
    if estimated_tokens > 0 and Decimal(actual_tokens) > Decimal(estimated_tokens) * Decimal("1.5"):
        warnings.append("token_estimate_divergence_gt_1_5x")
    if estimated_cost > 0 and actual_cost > estimated_cost * Decimal("2.0"):
        warnings.append("cost_estimate_divergence_gt_2x")
    return {
        "estimated_p90_total_tokens": estimated_tokens,
        "actual_total_tokens": actual_tokens,
        "token_ratio_actual_to_estimated": str(token_ratio),
        "estimated_p90_cost_usd": str(estimated_cost),
        "actual_cost_usd": str(actual_cost),
        "cost_ratio_actual_to_estimated": str(cost_ratio),
        "warnings": warnings,
    }


def failed_item(
    context: dict[str, Any],
    requested_model: str,
    attempts: int,
    retry_reasons: list[str],
    error: str,
) -> dict[str, Any]:
    manifest_item = context["manifest_item"]
    estimate = context["estimate_item"]
    usage = usage_from_response_or_estimate({}, estimate)
    return {
        "stable_segment_key": manifest_item.get("stable_segment_key"),
        "source_text_hash": manifest_item.get("source_text_hash"),
        "jsonl_line_index": context["jsonl_line_index"],
        "jsonl_request_sha256": stable_json_sha256(context["jsonl_request"]),
        "generate_content_payload_sha256": stable_json_sha256(context["generate_content_payload"]),
        "payload_source": JSONL_BASENAME,
        "prompt_reassembled": False,
        "selection_bucket": manifest_item.get("selection_bucket"),
        "status": "failed",
        "schema_valid": False,
        "parse_error": error,
        "quality_signal": False,
        "attempts": attempts,
        "retry_reasons": retry_reasons,
        "requested_model": requested_model,
        "observed_model_version": "model_version_unavailable",
        "model_version_drift": False,
        "usage": usage,
        "estimate_comparison": compare_to_estimate(usage, estimate) | {"warnings": []},
        "warnings": [],
    }


def build_base_results(
    *,
    args: argparse.Namespace,
    selection_sha: str,
    selected_items: list[dict[str, Any]],
    request_context: list[dict[str, Any]],
    budget_usd: Decimal,
    enabled: bool,
    user_green_light: bool,
    blocking_reasons: list[str],
    credential: dict[str, str] | None,
) -> dict[str, Any]:
    estimated_cost = sum(
        (
            parse_decimal_money((context["estimate_item"].get("planning_p90") or {}).get("official_cost_usd") or "0", field_name="estimated_p90_cost_usd")
            for context in request_context
        ),
        Decimal("0"),
    )
    return {
        "schema_version": "pali_pilot_300_live_smoke_results_v1",
        "run_id": RUN_ID,
        "enabled": enabled,
        "user_green_light": user_green_light,
        "status": "BLOCKED" if blocking_reasons else "PENDING",
        "requested_model": args.model,
        "observed_model_versions": [],
        "model_version_drift": False,
        "prompt_profile": KOREAN_ADVANCED_PROMPT_VERSION,
        "selection_content_sha256": selection_sha,
        "sample_count_requested": len(selected_items),
        "sample_count_attempted": 0,
        "sample_count_succeeded": 0,
        "schema_valid_count": 0,
        "schema_invalid_count": 0,
        "parse_failed_count": 0,
        "estimated_cost_usd": str(quantize_usd(estimated_cost)),
        "actual_usage": {"input_tokens": 0, "output_tokens": 0, "thinking_tokens": 0, "total_tokens": 0},
        "actual_cost_usd": "0.000000",
        "budget_usd": str(budget_usd),
        "under_budget": True,
        "batch_submission_allowed_now": False,
        "quality_signal": False,
        "credential_source": "environment_variable",
        "credential_env_var": credential["name"] if credential else None,
        "credential_present": credential is not None,
        "credential_value_logged": False,
        "items": [],
        "blocking_reasons": blocking_reasons,
        "warnings": [],
        "limitations": [
            "This smoke validates live model / prompt / schema / parser behavior only.",
            "It does not validate Gemini Batch submission mechanics.",
            "Batch submission is a separate path and must still be guarded in Step 3.",
            "Smoke output is not a translation quality signal and must not be used for glossary/gold/prompt tuning.",
        ],
    }


def finalize_results(results: dict[str, Any], *, stopped_for_budget: bool) -> None:
    items = results["items"]
    attempted = len(items)
    succeeded = sum(1 for item in items if item["status"] == "succeeded")
    schema_valid = sum(1 for item in items if item.get("schema_valid") is True)
    schema_invalid = sum(1 for item in items if item["status"] == "schema_invalid")
    parse_failed = sum(1 for item in items if item["status"] == "parse_failed")
    failed = sum(1 for item in items if item["status"] == "failed")
    versions = sorted({item.get("observed_model_version") for item in items if item.get("observed_model_version") and item.get("observed_model_version") != "model_version_unavailable"})
    total_input = sum(int(item["usage"]["input_tokens"]) for item in items)
    total_output = sum(int(item["usage"]["output_tokens"]) for item in items)
    total_thinking = sum(int(item["usage"]["thinking_tokens"]) for item in items)
    total_tokens = sum(int(item["usage"]["total_tokens"]) for item in items)
    actual_cost = sum((parse_decimal_money(item["usage"]["actual_cost_usd"], field_name="usage.actual_cost_usd") for item in items), Decimal("0"))
    all_warnings: list[str] = []
    for item in items:
        all_warnings.extend(item.get("warnings") or [])
        if "cost_estimate_divergence_gt_2x" in (item.get("warnings") or []):
            all_warnings.append("fail_review_required_cost_divergence_gt_2x")
    results.update(
        {
            "observed_model_versions": versions,
            "model_version_drift": any(item.get("model_version_drift") for item in items),
            "sample_count_attempted": attempted,
            "sample_count_succeeded": succeeded,
            "schema_valid_count": schema_valid,
            "schema_invalid_count": schema_invalid,
            "parse_failed_count": parse_failed,
            "actual_usage": {
                "input_tokens": total_input,
                "output_tokens": total_output,
                "thinking_tokens": total_thinking,
                "total_tokens": total_tokens,
            },
            "actual_cost_usd": str(quantize_usd(actual_cost)),
            "under_budget": actual_cost <= parse_decimal_money(results["budget_usd"], field_name="budget_usd"),
            "warnings": sorted(set(results.get("warnings", []) + all_warnings)),
        }
    )
    if stopped_for_budget and succeeded >= 1:
        results["status"] = "PARTIAL"
        return
    if stopped_for_budget:
        results["status"] = "FAIL"
        return
    if "fail_review_required_cost_divergence_gt_2x" in results["warnings"]:
        results["status"] = "PARTIAL"
        return
    if attempted >= 3 and succeeded == attempted and schema_valid == attempted and schema_invalid == 0 and parse_failed == 0 and failed == 0:
        results["status"] = "PASS"
    elif succeeded > 0:
        results["status"] = "PARTIAL"
    else:
        results["status"] = "FAIL"


def write_artifacts(
    paths: SmokePaths,
    results: dict[str, Any],
    raw_rows: list[dict[str, Any]],
    *,
    args: argparse.Namespace,
    credential: dict[str, str] | None,
    pretty: bool,
) -> None:
    write_json(paths.results, results, pretty=pretty)
    paths.raw_jsonl.write_text(
        "".join(json.dumps(row, ensure_ascii=False, sort_keys=True) + "\n" for row in raw_rows),
        encoding="utf-8",
    )
    paths.summary.write_text(render_summary(results), encoding="utf-8")
    write_json(
        paths.run_manifest,
        {
            "schema_version": "pali_pilot_300_smoke_run_manifest_v1",
            "run_id": RUN_ID,
            "script_version": SCRIPT_VERSION,
            "generated_at": now_iso(),
            "input_files": {
                "manifest": file_record(Path(args.manifest)),
                "readiness": file_record(Path(args.readiness)),
                "jsonl": file_record(Path(args.jsonl)),
                "jsonl_manifest": file_record(Path(args.jsonl_manifest)),
                "cost_estimate": file_record(Path(args.cost_estimate)),
            },
            "output_paths": {
                "selection": str(paths.selection),
                "results": str(paths.results),
                "summary": str(paths.summary),
                "run_manifest": str(paths.run_manifest),
                "raw_jsonl": str(paths.raw_jsonl),
            },
            "command_line_args": vars(args),
            "credential_source": "environment_variable",
            "credential_env_var": credential["name"] if credential else None,
            "credential_present": credential is not None,
            "credential_value_logged": False,
            "network_call_type": "Gemini generateContent only" if results["status"] != "BLOCKED" else "none_blocked_before_live_call",
            "batch_submission_allowed_now": False,
            "quality_signal": False,
        },
        pretty=pretty,
    )


def render_summary(results: dict[str, Any]) -> str:
    return "\n".join(
        [
            "# Pāli 300 Pilot Step 2.5 Live Micro-Smoke",
            "",
            "## Purpose",
            "Validate live model / prompt / schema / parser behavior for 3-5 selected segments before any 300 Batch submission.",
            "",
            "## Safety Gate",
            f"- status: `{results['status']}`",
            f"- blocking_reasons: {', '.join(results['blocking_reasons']) if results['blocking_reasons'] else 'none'}",
            f"- batch_submission_allowed_now: `{str(results['batch_submission_allowed_now']).lower()}`",
            "",
            "## Credential Handling",
            "- credential source: environment_variable",
            f"- credential present: {results['credential_present']}",
            "- credential value logged: false",
            "",
            "## Sample Selection",
            f"- sample_count_requested: {results['sample_count_requested']}",
            "- holdout candidates excluded.",
            "",
            "## Payload Source",
            f"- payload_source: `{JSONL_BASENAME}`",
            "- prompt_reassembled: false",
            "",
            "## Model / Observed modelVersion",
            f"- requested_model: `{results['requested_model']}`",
            f"- observed_model_versions: {results['observed_model_versions']}",
            f"- model_version_drift: {results['model_version_drift']}",
            "",
            "## Schema Validation Result",
            f"- schema_valid_count: {results['schema_valid_count']}",
            f"- schema_invalid_count: {results['schema_invalid_count']}",
            "",
            "## Parse Result",
            f"- parse_failed_count: {results['parse_failed_count']}",
            "",
            "## Token / Cost Result",
            f"- actual_usage: {results['actual_usage']}",
            f"- estimated_cost_usd: ${results['estimated_cost_usd']}",
            f"- actual_cost_usd: ${results['actual_cost_usd']}",
            "",
            "## Estimate Divergence",
            f"- warnings: {', '.join(results['warnings']) if results['warnings'] else 'none'}",
            "",
            "## Budget Status",
            f"- budget_usd: ${results['budget_usd']}",
            f"- under_budget: {results['under_budget']}",
            "",
            "## Limitations",
            *[f"- {item}" for item in results["limitations"]],
            "",
            "## Next Step",
            "Smoke PASS여도 300 Batch 제출은 자동 허용되지 않는다. Step 3에서는 manifest hash, JSONL hash, readiness, budget gate, smoke result를 다시 확인한 뒤 사용자 승인 하에 제출한다.",
            "",
        ]
    )


def is_retryable(error: ProviderError) -> bool:
    if error.status_code is None:
        return True
    return error.status_code in RETRYABLE_STATUS_CODES


def resolve_gemini_env_credential() -> dict[str, str] | None:
    for name in GEMINI_API_KEY_ENV_CANDIDATES:
        value = os.getenv(name)
        if value:
            return {"name": name, "value": value}
    return None


def extract_model_output_text(response: dict[str, Any]) -> str:
    for candidate in response.get("candidates") or []:
        content = candidate.get("content") or {}
        for part in content.get("parts") or []:
            if isinstance(part, dict) and part.get("text"):
                return str(part["text"])
    return ""


def strip_json_fences(text: str) -> str:
    stripped = text.strip()
    if stripped.startswith("```"):
        lines = stripped.splitlines()
        if lines and lines[0].startswith("```"):
            lines = lines[1:]
        if lines and lines[-1].startswith("```"):
            lines = lines[:-1]
        return "\n".join(lines).strip()
    return stripped


def find_model_version(value: Any) -> str | None:
    if isinstance(value, dict):
        for key, nested in value.items():
            if key in {"modelVersion", "model_version"} and nested:
                return str(nested)
            found = find_model_version(nested)
            if found:
                return found
    if isinstance(value, list):
        for item in value:
            found = find_model_version(item)
            if found:
                return found
    return None


def decimal_ratio(numerator: int | Decimal, denominator: int | Decimal) -> Decimal:
    denominator_dec = Decimal(str(denominator))
    if denominator_dec == 0:
        return Decimal("0.000")
    return (Decimal(str(numerator)) / denominator_dec).quantize(Decimal("0.001"), rounding=ROUND_HALF_UP)


def quantize_usd(value: Decimal) -> Decimal:
    return value.quantize(Decimal("0.000001"), rounding=ROUND_HALF_UP)


def stable_json_sha256(payload: Any) -> str:
    return hashlib.sha256(json.dumps(payload, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode("utf-8")).hexdigest()


def sanitize_error_message(message: str, secret: str) -> str:
    sanitized = message
    if secret:
        sanitized = sanitized.replace(secret, "[REDACTED]")
    return sanitized.replace("\n", " ")[:1200]


def sanitize_for_artifact(value: Any) -> Any:
    if isinstance(value, dict):
        redacted = {}
        for key, nested in value.items():
            lowered = str(key).lower()
            if any(marker in lowered for marker in ("apikey", "api_key", "authorization", "credential", "secret")):
                redacted[key] = "[REDACTED]"
            else:
                redacted[key] = sanitize_for_artifact(nested)
        return redacted
    if isinstance(value, list):
        return [sanitize_for_artifact(item) for item in value]
    return value


def file_record(path: Path) -> dict[str, Any]:
    return {"path": str(path), "exists": path.exists(), "sha256": file_sha256(path) if path.exists() else None}


def read_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def read_jsonl(path: Path) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for line in path.read_text(encoding="utf-8").splitlines():
        if line.strip():
            rows.append(json.loads(line))
    return rows


def write_json(path: Path, payload: Any, *, pretty: bool) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2 if pretty else None, sort_keys=True) + "\n", encoding="utf-8")


def file_sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))

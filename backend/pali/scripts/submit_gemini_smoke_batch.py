"""Submit a guarded Gemini Batch smoke or pilot job.

This script may submit a real Gemini Batch API job. It must only be used for
small approved batches after explicit operator approval.
"""

from __future__ import annotations

import argparse
import json
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
from collections import Counter
from dataclasses import dataclass
from decimal import Decimal
from pathlib import Path
from typing import Any

from pydantic import ValidationError

REPO_ROOT = Path(__file__).resolve().parents[3]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from backend.pali.scripts.calibrate_gemini_tokens import resolve_gemini_api_key
from backend.pali.scripts.plan_gemini_smoke_batch import contains_secret_marker
from backend.pali.translation.budget import (
    PriceProfile,
    TokenEstimate,
    actual_cost_from_usage,
    estimate_request_cost,
    parse_usage_metadata,
)
from backend.pali.translation.prompts import (
    KOREAN_ADVANCED_PROMPT_VERSION,
    validate_korean_advanced_model_output,
)
from backend.pali.translation.quality import detect_quality_flag_details


DEFAULT_PRICE_PROFILE_PATH = REPO_ROOT / "config" / "pali_batch_price_profiles.example.json"
DEFAULT_PRICE_PROFILE_ID = "official_gemini_3_1_pro_preview_batch_2026_06_13"
DEFAULT_MODEL = "models/gemini-3.1-pro-preview"
DEFAULT_API_BASE_URL = "https://generativelanguage.googleapis.com/v1beta"
TERMINAL_STATES = {
    "BATCH_STATE_SUCCEEDED",
    "BATCH_STATE_FAILED",
    "BATCH_STATE_CANCELLED",
    "BATCH_STATE_EXPIRED",
}


@dataclass(frozen=True)
class PreflightResult:
    valid: bool
    errors: list[str]
    warnings: list[str]
    estimated_cost_usd: Decimal


class GeminiBatchRestClient:
    """Small REST wrapper for Developer API batchGenerateContent."""

    def __init__(
        self,
        *,
        api_key: str,
        base_url: str = DEFAULT_API_BASE_URL,
        timeout_seconds: int = 60,
    ) -> None:
        self.api_key = api_key
        self.base_url = base_url.rstrip("/")
        self.timeout_seconds = timeout_seconds

    def create_inline_batch(
        self,
        *,
        model: str,
        requests: list[dict[str, Any]],
        display_name: str,
    ) -> dict[str, Any]:
        model_path = model if model.startswith("models/") else f"models/{model}"
        path = f"{self.base_url}/{model_path}:batchGenerateContent"
        body = {
            "batch": {
                "displayName": display_name,
                "inputConfig": {
                    "requests": {
                        "requests": requests,
                    }
                },
            }
        }
        return self._request_json("POST", path, body)

    def get_batch(self, name: str) -> dict[str, Any]:
        path = f"{self.base_url}/{name.lstrip('/')}"
        return self._request_json("GET", path, None)

    def _request_json(
        self,
        method: str,
        url: str,
        body: dict[str, Any] | None,
    ) -> dict[str, Any]:
        separator = "&" if "?" in url else "?"
        url_with_key = f"{url}{separator}{urllib.parse.urlencode({'key': self.api_key})}"
        data = None if body is None else json.dumps(body).encode("utf-8")
        request = urllib.request.Request(
            url_with_key,
            data=data,
            method=method,
            headers={"Content-Type": "application/json"},
        )
        try:
            with urllib.request.urlopen(request, timeout=self.timeout_seconds) as response:
                return json.loads(response.read().decode("utf-8"))
        except urllib.error.HTTPError as exc:
            message = exc.read().decode("utf-8", errors="replace")
            raise RuntimeError(f"Gemini Batch API HTTP {exc.code}: {message}") from exc


def submit_gemini_smoke_batch(
    *,
    provider_jsonl_path: str | Path,
    manifest_path: str | Path,
    raw_result_path: str | Path,
    parsed_result_path: str | Path,
    summary_path: str | Path,
    model: str = DEFAULT_MODEL,
    price_profile_path: str | Path = DEFAULT_PRICE_PROFILE_PATH,
    price_profile_id: str = DEFAULT_PRICE_PROFILE_ID,
    hard_cap_usd: Decimal = Decimal("5"),
    expected_request_count: int | None = None,
    max_request_count: int = 5,
    job_label: str = "smoke",
    poll: bool = False,
    poll_interval_seconds: int = 10,
    max_wait_seconds: int = 900,
    timeout_seconds: int = 60,
    api_key: str | None = None,
    client: GeminiBatchRestClient | None = None,
) -> dict[str, Any]:
    provider_lines = read_jsonl(Path(provider_jsonl_path))
    manifest = json.loads(Path(manifest_path).read_text(encoding="utf-8"))
    price_profile, price_profile_raw = load_price_profile(price_profile_path, price_profile_id)
    preflight = preflight_smoke_batch(
        provider_lines=provider_lines,
        manifest=manifest,
        model=model,
        price_profile=price_profile,
        hard_cap_usd=hard_cap_usd,
        expected_request_count=expected_request_count,
        max_request_count=max_request_count,
    )
    if not preflight.valid:
        raise RuntimeError(f"Batch smoke preflight failed: {preflight.errors}")

    if client is None:
        resolved_api_key = api_key or resolve_gemini_api_key()
        if not resolved_api_key:
            raise RuntimeError(
                "A Gemini API key is required for Batch submit. "
                "Checked GEMINI_API_KEY, GOOGLE_API_KEY, GOOGLE_GENAI_API_KEY, "
                "and PALI_GEMINI_API_KEY from the environment and local .env files."
            )
        client = GeminiBatchRestClient(api_key=resolved_api_key, timeout_seconds=timeout_seconds)

    batch_requests = [
        build_inline_request_from_provider_line(line)
        for line in provider_lines
    ]
    display_name = f"pali-{job_label}-{manifest.get('source_commit', 'unknown')[:7]}"
    create_response = client.create_inline_batch(
        model=model,
        requests=batch_requests,
        display_name=display_name,
    )
    provider_batch_id = extract_batch_name(create_response)
    if not provider_batch_id:
        raise RuntimeError(f"Gemini Batch create response did not include a batch name: {create_response}")

    final_status = create_response
    polling_history: list[dict[str, Any]] = [status_snapshot(create_response)]
    if poll:
        final_status, polling_history = poll_batch(
            client=client,
            provider_batch_id=provider_batch_id,
            poll_interval_seconds=poll_interval_seconds,
            max_wait_seconds=max_wait_seconds,
            initial_status=create_response,
        )

    inline_results = extract_inline_result_lines(final_status)
    raw_result_file = Path(raw_result_path)
    raw_result_file.parent.mkdir(parents=True, exist_ok=True)
    write_raw_results(raw_result_file, inline_results, final_status)

    parsed = parse_batch_results(
        raw_lines=inline_results,
        provider_lines=provider_lines,
        manifest=manifest,
        price_profile=price_profile,
    )
    parsed["provider_batch_id"] = provider_batch_id
    parsed["polling_history"] = polling_history
    parsed["final_batch_status"] = status_snapshot(final_status)

    parsed_file = Path(parsed_result_path)
    parsed_file.parent.mkdir(parents=True, exist_ok=True)
    parsed_file.write_text(json.dumps(parsed, ensure_ascii=False, indent=2), encoding="utf-8")

    summary = build_summary(
        parsed=parsed,
        manifest=manifest,
        model=model,
        provider_batch_id=provider_batch_id,
        preflight=preflight,
        price_profile=price_profile,
        price_profile_id=price_profile_id,
        price_profile_raw=price_profile_raw,
        raw_result_path=str(raw_result_path),
        parsed_result_path=str(parsed_result_path),
        final_status=final_status,
    )
    summary_file = Path(summary_path)
    summary_file.parent.mkdir(parents=True, exist_ok=True)
    summary_file.write_text(json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8")
    return summary


def read_jsonl(path: Path) -> list[dict[str, Any]]:
    lines: list[dict[str, Any]] = []
    for raw_line in path.read_text(encoding="utf-8").splitlines():
        if raw_line.strip():
            lines.append(json.loads(raw_line))
    return lines


def load_price_profile(path: str | Path, profile_id: str) -> tuple[PriceProfile, dict[str, Any]]:
    data = json.loads(Path(path).read_text(encoding="utf-8"))
    profile = next(
        (item for item in data.get("profiles", []) if item.get("profile_id") == profile_id),
        None,
    )
    if profile is None:
        raise RuntimeError(f"Price profile not found: {profile_id}")
    return (
        PriceProfile(
            input_usd_per_million_tokens=Decimal(str(profile["input_usd_per_million_tokens"])),
            output_usd_per_million_tokens=Decimal(str(profile["output_usd_per_million_tokens"])),
            thinking_usd_per_million_tokens=Decimal(str(profile.get("thinking_usd_per_million_tokens", "0"))),
            batch_discount_multiplier=Decimal(str(profile.get("batch_discount_multiplier", "1"))),
        ),
        profile,
    )


def preflight_smoke_batch(
    *,
    provider_lines: list[dict[str, Any]],
    manifest: dict[str, Any],
    model: str,
    price_profile: PriceProfile,
    hard_cap_usd: Decimal,
    expected_request_count: int | None = None,
    max_request_count: int = 5,
) -> PreflightResult:
    errors: list[str] = []
    warnings: list[str] = []
    request_count = int(manifest.get("request_count") or 0)
    if expected_request_count is not None and request_count != expected_request_count:
        errors.append(f"request_count must be exactly {expected_request_count}")
    if request_count > max_request_count:
        errors.append(f"request_count exceeds configured limit of {max_request_count}")
    if request_count != len(provider_lines):
        errors.append("provider JSONL line count does not match manifest request_count")
    if len(manifest.get("items") or []) != len(provider_lines):
        errors.append("manifest item count does not match provider JSONL line count")
    if not manifest.get("validation", {}).get("valid"):
        errors.append("manifest validation is not valid")

    keys = [line.get("key") for line in provider_lines]
    if len(keys) != len(set(keys)):
        errors.append("provider JSONL keys are not unique")
    item_keys = [item.get("stable_segment_key") for item in manifest.get("items") or []]
    if keys != item_keys:
        errors.append("provider JSONL keys do not match manifest item order")
    if model != DEFAULT_MODEL or manifest.get("model") != DEFAULT_MODEL:
        errors.append("model mismatch; submit only allows models/gemini-3.1-pro-preview")
    if manifest.get("prompt_template_version") != KOREAN_ADVANCED_PROMPT_VERSION:
        errors.append("prompt_template_version mismatch")

    serialized = json.dumps({"provider_lines": provider_lines, "manifest": manifest}, ensure_ascii=False)
    if contains_secret_marker(serialized):
        errors.append("input artifacts appear to contain credential-like content")

    manifest_estimated_cost = Decimal(str(manifest.get("estimated_cost_usd_total") or "0"))
    profile_estimated_cost = estimate_request_cost(
        TokenEstimate(
            input_tokens=int(manifest.get("estimated_input_tokens_total") or 0),
            output_tokens=int(manifest.get("estimated_output_tokens_total") or 0),
            thinking_tokens=int(manifest.get("estimated_thinking_tokens_total") or 0),
        ),
        price_profile,
    )
    estimated_cost = max(manifest_estimated_cost, profile_estimated_cost)
    if estimated_cost > hard_cap_usd:
        errors.append(f"estimated cost {estimated_cost} exceeds hard cap {hard_cap_usd}")
    if profile_estimated_cost != manifest_estimated_cost:
        warnings.append(
            "Manifest estimated cost differs from injected price profile estimate; using the larger value for preflight."
        )

    return PreflightResult(
        valid=not errors,
        errors=errors,
        warnings=warnings,
        estimated_cost_usd=estimated_cost,
    )


def build_inline_request_from_provider_line(line: dict[str, Any]) -> dict[str, Any]:
    request = line.get("request") or {}
    generation_config = request.get("generation_config") or request.get("generationConfig") or {}
    rest_request = {
        "contents": request.get("contents") or [],
    }
    if generation_config:
        rest_request["generationConfig"] = generation_config
    return {
        "metadata": {
            "key": line.get("key"),
        },
        "request": rest_request,
    }


def extract_batch_name(response: dict[str, Any]) -> str | None:
    if response.get("name"):
        return str(response["name"])
    for key in ("batch", "metadata", "response"):
        value = response.get(key)
        if isinstance(value, dict) and value.get("name"):
            return str(value["name"])
    return None


def poll_batch(
    *,
    client: GeminiBatchRestClient,
    provider_batch_id: str,
    poll_interval_seconds: int,
    max_wait_seconds: int,
    initial_status: dict[str, Any],
) -> tuple[dict[str, Any], list[dict[str, Any]]]:
    started = time.monotonic()
    history = [status_snapshot(initial_status)]
    latest = initial_status
    while True:
        state = extract_batch_state(latest)
        if state in TERMINAL_STATES or bool(latest.get("done")):
            return latest, history
        if time.monotonic() - started >= max_wait_seconds:
            history.append({"state": state or "timeout", "timed_out": True})
            return latest, history
        time.sleep(poll_interval_seconds)
        latest = client.get_batch(provider_batch_id)
        history.append(status_snapshot(latest))


def status_snapshot(status: dict[str, Any]) -> dict[str, Any]:
    return {
        "name": extract_batch_name(status),
        "state": extract_batch_state(status),
        "done": status.get("done"),
        "error": status.get("error"),
        "create_time": status.get("createTime") or status.get("create_time"),
        "update_time": status.get("updateTime") or status.get("update_time"),
    }


def extract_batch_state(status: dict[str, Any]) -> str | None:
    for key in ("state", "batchState"):
        if status.get(key):
            return str(status[key])
    for nested_key in ("metadata", "response", "batch"):
        nested = status.get(nested_key)
        if isinstance(nested, dict):
            nested_state = extract_batch_state(nested)
            if nested_state:
                return nested_state
    return None


def extract_inline_result_lines(final_status: dict[str, Any]) -> list[dict[str, Any]]:
    found: list[dict[str, Any]] = []
    collect_inline_responses(final_status, found)
    deduped: list[dict[str, Any]] = []
    seen: set[str] = set()
    for line in found:
        key = extract_result_key(line)
        fingerprint = key or json.dumps(line, sort_keys=True, ensure_ascii=False)
        if fingerprint in seen:
            continue
        seen.add(fingerprint)
        deduped.append(line)
    return deduped


def collect_inline_responses(value: Any, found: list[dict[str, Any]]) -> None:
    if isinstance(value, dict):
        for key, nested in value.items():
            if key in {"inlinedResponses", "inlineResponses"} and isinstance(nested, list):
                found.extend([item for item in nested if isinstance(item, dict)])
            else:
                collect_inline_responses(nested, found)
    elif isinstance(value, list):
        for item in value:
            collect_inline_responses(item, found)


def write_raw_results(path: Path, inline_results: list[dict[str, Any]], final_status: dict[str, Any]) -> None:
    if inline_results:
        path.write_text(
            "\n".join(json.dumps(line, ensure_ascii=False) for line in inline_results) + "\n",
            encoding="utf-8",
        )
    else:
        path.write_text(json.dumps(final_status, ensure_ascii=False, indent=2), encoding="utf-8")


def parse_batch_results(
    *,
    raw_lines: list[dict[str, Any]],
    provider_lines: list[dict[str, Any]],
    manifest: dict[str, Any],
    price_profile: PriceProfile,
) -> dict[str, Any]:
    result_by_key: dict[str, dict[str, Any]] = {}
    for line in raw_lines:
        key = extract_result_key(line)
        if key:
            result_by_key[key] = line

    provider_by_key = {line.get("key"): line for line in provider_lines}
    parsed_items = [
        parse_result_item(
            manifest_item=item,
            provider_line=provider_by_key.get(item.get("stable_segment_key")),
            result_line=result_by_key.get(item.get("stable_segment_key")),
            price_profile=price_profile,
        )
        for item in manifest.get("items") or []
    ]
    return {"items": parsed_items}


def extract_result_key(line: dict[str, Any]) -> str | None:
    metadata = line.get("metadata")
    if isinstance(metadata, dict):
        for key in ("key", "stable_segment_key", "stableSegmentKey"):
            if metadata.get(key):
                return str(metadata[key])
    for key in ("key", "stable_segment_key", "stableSegmentKey"):
        if line.get(key):
            return str(line[key])
    return None


def parse_result_item(
    *,
    manifest_item: dict[str, Any],
    provider_line: dict[str, Any] | None,
    result_line: dict[str, Any] | None,
    price_profile: PriceProfile,
) -> dict[str, Any]:
    source_text = extract_source_text_from_provider_line(provider_line or {})
    base = {
        "stable_segment_key": manifest_item.get("stable_segment_key"),
        "source_text_hash": manifest_item.get("source_text_hash"),
        "text_layer": manifest_item.get("text_layer"),
        "chunk_type": manifest_item.get("chunk_type"),
        "length_bucket": manifest_item.get("length_bucket"),
        "pitaka": manifest_item.get("pitaka"),
        "nikaya": manifest_item.get("nikaya"),
        "source_path": manifest_item.get("source_path"),
        "original_text": source_text,
        "model_output_raw": None,
        "parsed_translation_json": None,
        "schema_valid": False,
        "quality_flags": [],
        "local_validator_flags": [],
        "quality_flag_details": [],
        "prompt_token_count": 0,
        "candidates_token_count": 0,
        "thoughts_token_count": 0,
        "cached_content_token_count": 0,
        "total_token_count": 0,
        "estimated_cost_usd": manifest_item.get("estimated_cost_usd"),
        "actual_cost_usd": "0.000000",
        "status": "missing_result",
        "error_message": "",
    }
    if result_line is None:
        base["error_message"] = "No result line found for stable_segment_key."
        return base
    if result_line.get("error") or result_line.get("status"):
        base["status"] = "failed"
        base["error_message"] = json.dumps(result_line.get("error") or result_line.get("status"), ensure_ascii=False)
        return base

    response = extract_generate_content_response(result_line)
    usage_result = parse_usage_metadata(response)
    if usage_result.usage:
        usage = usage_result.usage
        base.update(
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
    base["model_output_raw"] = output_text
    if not output_text:
        base["status"] = "needs_retry"
        base["error_message"] = "GenerateContentResponse did not include output text."
        if usage_result.status != "success":
            base["error_message"] += f" Usage metadata: {usage_result.error_message}"
        return base

    try:
        parsed_json = json.loads(strip_json_fences(output_text))
    except json.JSONDecodeError as exc:
        base["status"] = "schema_invalid"
        base["error_message"] = f"JSON parse failed: {exc}"
        base["local_validator_flags"] = ["json_parse_failed"]
        return base

    base["parsed_translation_json"] = parsed_json
    try:
        translation = validate_korean_advanced_model_output(parsed_json)
        details = detect_quality_flag_details(source_text, translation)
        local_flags = sorted(
            {
                detail.flag.value
                for detail in details
                if detail.source.value == "local_validator"
            }
        )
        base.update(
            {
                "schema_valid": True,
                "quality_flags": [flag.value for flag in translation.quality_flags],
                "local_validator_flags": local_flags,
                "quality_flag_details": [
                    json.loads(detail.model_dump_json())
                    for detail in details
                ],
                "status": "succeeded" if usage_result.status == "success" else "needs_retry",
                "error_message": "" if usage_result.status == "success" else usage_result.error_message,
            }
        )
    except (ValidationError, ValueError) as exc:
        base["status"] = "schema_invalid"
        base["error_message"] = f"Schema validation failed: {exc}"
        base["local_validator_flags"] = ["schema_validation_failed"]
    return base


def extract_source_text_from_provider_line(provider_line: dict[str, Any]) -> str:
    text = (
        provider_line.get("request", {})
        .get("contents", [{}])[0]
        .get("parts", [{}])[0]
        .get("text", "")
    )
    marker = "빠알리 원문:"
    if marker not in text or "<<<" not in text or ">>>" not in text:
        return ""
    after_marker = text.split(marker, 1)[1]
    return after_marker.split("<<<", 1)[1].split(">>>", 1)[0].strip()


def extract_generate_content_response(result_line: dict[str, Any]) -> dict[str, Any]:
    response = result_line.get("response")
    if isinstance(response, dict):
        return response
    inline_response = result_line.get("inlineResponse")
    if isinstance(inline_response, dict):
        nested = inline_response.get("response")
        if isinstance(nested, dict):
            return nested
    return result_line


def extract_model_output_text(response: dict[str, Any]) -> str:
    candidates = response.get("candidates") or []
    for candidate in candidates:
        content = candidate.get("content") or {}
        for part in content.get("parts") or []:
            if part.get("text"):
                return str(part["text"]).strip()
    if response.get("text"):
        return str(response["text"]).strip()
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


def build_summary(
    *,
    parsed: dict[str, Any],
    manifest: dict[str, Any],
    model: str,
    provider_batch_id: str,
    preflight: PreflightResult,
    price_profile: PriceProfile,
    price_profile_id: str,
    price_profile_raw: dict[str, Any],
    raw_result_path: str,
    parsed_result_path: str,
    final_status: dict[str, Any],
) -> dict[str, Any]:
    items = parsed.get("items") or []
    succeeded = [item for item in items if item["status"] == "succeeded"]
    failed = [item for item in items if item["status"] != "succeeded"]
    schema_valid = [item for item in items if item["schema_valid"]]
    schema_invalid = [item for item in items if item["status"] == "schema_invalid"]
    parse_failed = [
        item
        for item in items
        if "json_parse_failed" in (item.get("local_validator_flags") or [])
    ]
    total_actual_cost = sum((Decimal(str(item["actual_cost_usd"])) for item in items), Decimal("0"))
    total_manifest_estimated_cost = sum((Decimal(str(item.get("estimated_cost_usd") or "0")) for item in items), Decimal("0"))
    total_profile_estimated_cost = estimate_request_cost(
        TokenEstimate(
            input_tokens=int(manifest.get("estimated_input_tokens_total") or 0),
            output_tokens=int(manifest.get("estimated_output_tokens_total") or 0),
            thinking_tokens=int(manifest.get("estimated_thinking_tokens_total") or 0),
        ),
        price_profile,
    )
    warnings = list(preflight.warnings)
    if price_profile_raw.get("profile_id", "").startswith("mock_"):
        warnings.append("Price profile is mock planning data, not official pricing.")
    if total_actual_cost > preflight.estimated_cost_usd and total_actual_cost > Decimal("5"):
        warnings.append("Actual cost exceeded the submitted batch preflight reservation; inspect pricing and usage.")
    if any(item["status"] != "succeeded" for item in items):
        warnings.append("Some batch items failed or need retry; inspect parsed artifact before any larger batch.")

    total_actual_output = sum(item["candidates_token_count"] for item in items)
    total_thinking = sum(item["thoughts_token_count"] for item in items)

    return {
        "provider_batch_id": provider_batch_id,
        "final_batch_status": status_snapshot(final_status),
        "model": model,
        "request_count": len(items),
        "succeeded_count": len(succeeded),
        "failed_count": len(failed),
        "schema_valid_count": len(schema_valid),
        "schema_invalid_count": len(schema_invalid),
        "parse_failed_count": len(parse_failed),
        "total_estimated_input_tokens": int(manifest.get("estimated_input_tokens_total") or 0),
        "total_actual_input_tokens": sum(item["prompt_token_count"] for item in items),
        "total_estimated_output_tokens": int(manifest.get("estimated_output_tokens_total") or 0),
        "total_actual_output_tokens": total_actual_output,
        "total_thinking_tokens": total_thinking,
        "average_output_tokens_per_segment": round(total_actual_output / len(items), 6) if items else 0,
        "average_thinking_tokens_per_segment": round(total_thinking / len(items), 6) if items else 0,
        "total_estimated_cost_usd": str(total_profile_estimated_cost),
        "total_manifest_estimated_cost_usd": str(total_manifest_estimated_cost),
        "preflight_reserved_cost_usd": str(preflight.estimated_cost_usd),
        "total_actual_cost_usd": str(total_actual_cost),
        "cost_delta_usd": str(total_actual_cost - total_profile_estimated_cost),
        "price_profile_id": price_profile_id,
        "price_profile_source_url": price_profile_raw.get("source_url"),
        "quality_flag_counts": counter_from_items(items, "quality_flags"),
        "local_validator_flag_counts": counter_from_items(items, "local_validator_flags"),
        "result_distribution": result_distribution(items),
        "failed_item_causes": failed_item_causes(items),
        "needs_review_items": needs_review_items(items),
        "warnings": warnings,
        "raw_result_path": raw_result_path,
        "parsed_result_path": parsed_result_path,
        "next_recommendation": next_recommendation(items, total_actual_cost),
    }


def counter_from_items(items: list[dict[str, Any]], field: str) -> dict[str, int]:
    counter: Counter[str] = Counter()
    for item in items:
        counter.update(item.get(field) or [])
    return dict(sorted(counter.items()))


def result_distribution(items: list[dict[str, Any]]) -> dict[str, dict[str, int]]:
    return {
        "text_layer": count_field(items, "text_layer"),
        "chunk_type": count_field(items, "chunk_type"),
        "length_bucket": count_field(items, "length_bucket"),
        "status": count_field(items, "status"),
    }


def count_field(items: list[dict[str, Any]], field: str) -> dict[str, int]:
    return dict(
        sorted(
            Counter(str(item.get(field) or "unknown") for item in items).items()
        )
    )


def failed_item_causes(items: list[dict[str, Any]]) -> list[dict[str, Any]]:
    failures: list[dict[str, Any]] = []
    for item in items:
        if item.get("status") == "succeeded" and item.get("schema_valid"):
            continue
        failures.append(
            {
                "stable_segment_key": item.get("stable_segment_key"),
                "status": item.get("status"),
                "schema_valid": item.get("schema_valid"),
                "error_message": item.get("error_message"),
                "local_validator_flags": item.get("local_validator_flags") or [],
                "quality_flags": item.get("quality_flags") or [],
            }
        )
    return failures


def needs_review_items(items: list[dict[str, Any]]) -> list[dict[str, Any]]:
    review: list[dict[str, Any]] = []
    for item in items:
        local_flags = item.get("local_validator_flags") or []
        quality_flags = item.get("quality_flags") or []
        if item.get("status") == "succeeded" and item.get("schema_valid") and not local_flags and not quality_flags:
            continue
        review.append(
            {
                "stable_segment_key": item.get("stable_segment_key"),
                "status": item.get("status"),
                "schema_valid": item.get("schema_valid"),
                "quality_flags": quality_flags,
                "local_validator_flags": local_flags,
                "error_message": item.get("error_message"),
            }
        )
    return review


def next_recommendation(items: list[dict[str, Any]], total_actual_cost: Decimal) -> str:
    if total_actual_cost > Decimal("5"):
        return "Stop. Actual cost exceeded smoke hard cap; inspect pricing and usage before retrying."
    if any(item["status"] != "succeeded" or not item["schema_valid"] for item in items):
        return "Stop. Review failed/schema-invalid items before any pilot batch."
    return "Review the translations manually. Do not proceed to a larger batch without separate approval."


def main() -> None:
    parser = argparse.ArgumentParser(description="Submit a guarded Gemini Batch smoke job.")
    parser.add_argument("--provider-jsonl", required=True)
    parser.add_argument("--manifest", required=True)
    parser.add_argument("--raw-result", required=True)
    parser.add_argument("--parsed-result", required=True)
    parser.add_argument("--summary", required=True)
    parser.add_argument("--model", default=DEFAULT_MODEL)
    parser.add_argument("--price-profile", default=str(DEFAULT_PRICE_PROFILE_PATH))
    parser.add_argument("--price-profile-id", default=DEFAULT_PRICE_PROFILE_ID)
    parser.add_argument("--hard-cap-usd", default="5")
    parser.add_argument("--expected-request-count", type=int)
    parser.add_argument("--max-request-count", type=int, default=5)
    parser.add_argument("--job-label", default="smoke")
    parser.add_argument("--poll", action="store_true")
    parser.add_argument("--poll-interval-seconds", type=int, default=10)
    parser.add_argument("--max-wait-seconds", type=int, default=900)
    parser.add_argument("--timeout-seconds", type=int, default=60)
    args = parser.parse_args()

    try:
        summary = submit_gemini_smoke_batch(
            provider_jsonl_path=args.provider_jsonl,
            manifest_path=args.manifest,
            raw_result_path=args.raw_result,
            parsed_result_path=args.parsed_result,
            summary_path=args.summary,
            model=args.model,
            price_profile_path=args.price_profile,
            price_profile_id=args.price_profile_id,
            hard_cap_usd=Decimal(str(args.hard_cap_usd)),
            expected_request_count=args.expected_request_count,
            max_request_count=args.max_request_count,
            job_label=args.job_label,
            poll=args.poll,
            poll_interval_seconds=args.poll_interval_seconds,
            max_wait_seconds=args.max_wait_seconds,
            timeout_seconds=args.timeout_seconds,
        )
    except RuntimeError as exc:
        print(str(exc), file=sys.stderr)
        raise SystemExit(2) from exc

    print(
        json.dumps(
            {
                "provider_batch_id": summary["provider_batch_id"],
                "final_batch_status": summary["final_batch_status"],
                "request_count": summary["request_count"],
                "succeeded_count": summary["succeeded_count"],
                "failed_count": summary["failed_count"],
                "schema_valid_count": summary["schema_valid_count"],
                "schema_invalid_count": summary["schema_invalid_count"],
                "parse_failed_count": summary["parse_failed_count"],
                "total_actual_input_tokens": summary["total_actual_input_tokens"],
                "total_actual_output_tokens": summary["total_actual_output_tokens"],
                "total_thinking_tokens": summary["total_thinking_tokens"],
                "total_actual_cost_usd": summary["total_actual_cost_usd"],
                "summary": args.summary,
            },
            ensure_ascii=False,
            indent=2,
        )
    )


if __name__ == "__main__":
    main()

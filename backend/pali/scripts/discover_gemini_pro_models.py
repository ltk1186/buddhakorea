"""Discover Gemini Pro models that support countTokens.

This script never calls text-generation APIs. It only calls models.list and
countTokens smoke tests.
"""

from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

REPO_ROOT = Path(__file__).resolve().parents[3]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from backend.pali.scripts.calibrate_gemini_tokens import resolve_gemini_api_key


EXCLUDED_MODEL_TERMS = (
    "flash",
    "flash-lite",
    "lite",
    "embedding",
    "embed",
    "imagen",
    "image",
    "audio",
    "veo",
    "tts",
    "aqa",
)


def discover_gemini_pro_models(
    *,
    out_path: str | Path,
    api_version: str = "v1beta",
    smoke_text: str = "Evaṃ me sutaṃ.",
    pretty: bool = False,
) -> dict[str, Any]:
    api_key = resolve_gemini_api_key()
    if not api_key:
        raise RuntimeError(
            "A Gemini API key is required for model discovery. "
            "Checked GEMINI_API_KEY, GOOGLE_API_KEY, GOOGLE_GENAI_API_KEY, "
            "and PALI_GEMINI_API_KEY from the environment and local .env files."
        )

    from google import genai
    from google.genai import types

    client = genai.Client(
        api_key=api_key,
        http_options=types.HttpOptions(api_version=api_version),
    )

    all_models = list(client.models.list())
    pro_models = [model_to_record(model) for model in all_models if is_pro_candidate(model)]
    prioritized = sorted(pro_models, key=priority_key)

    smoke_results: list[dict[str, Any]] = []
    selected_model: str | None = None
    selection_reason = "No Pro model passed countTokens smoke test."
    for model in prioritized:
        smoke = count_tokens_smoke(client, model["model_name"], smoke_text)
        model["count_tokens_smoke_result"] = smoke
        smoke_results.append(smoke)
        if selected_model is None and smoke["status"] == "success":
            selected_model = model["model_name"]
            selection_reason = (
                "Selected highest-priority Pro model that passed countTokens smoke test."
            )

    has_gemini_31_pro = any(is_gemini_31_pro(model) for model in pro_models)
    has_gemini_3_pro = any(is_gemini_3_pro(model) for model in pro_models)
    has_gemini_25_pro = any(is_gemini_25_pro(model) for model in pro_models)

    report = {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "auth_mode": "api_key",
        "api_version": api_version,
        "discovered_pro_models": prioritized,
        "selected_model": selected_model,
        "selection_reason": selection_reason,
        "warnings": build_warnings(
            pro_models=pro_models,
            selected_model=selected_model,
            has_gemini_31_pro=has_gemini_31_pro,
            has_gemini_3_pro=has_gemini_3_pro,
            has_gemini_25_pro=has_gemini_25_pro,
        ),
        "summary": {
            "pro_model_count": len(pro_models),
            "gemini_31_pro_present": has_gemini_31_pro,
            "gemini_3_pro_present": has_gemini_3_pro,
            "gemini_25_pro_present": has_gemini_25_pro,
            "count_tokens_success_count": sum(
                1 for result in smoke_results if result["status"] == "success"
            ),
            "count_tokens_failed_count": sum(
                1 for result in smoke_results if result["status"] != "success"
            ),
        },
    }

    output_file = Path(out_path)
    output_file.parent.mkdir(parents=True, exist_ok=True)
    output_file.write_text(
        json.dumps(report, ensure_ascii=False, indent=2 if pretty else None),
        encoding="utf-8",
    )
    return report


def model_to_record(model: Any) -> dict[str, Any]:
    return {
        "model_name": getattr(model, "name", None),
        "display_name": getattr(model, "display_name", None),
        "version": getattr(model, "version", None),
        "description": getattr(model, "description", None),
        "input_token_limit": getattr(model, "input_token_limit", None),
        "output_token_limit": getattr(model, "output_token_limit", None),
        "supported_methods": list(getattr(model, "supported_actions", None) or []),
    }


def is_pro_candidate(model: Any) -> bool:
    name = str(getattr(model, "name", "") or "").lower()
    display_name = str(getattr(model, "display_name", "") or "").lower()
    haystack = f"{name} {display_name}"
    if "gemini" not in haystack:
        return False
    if "pro" not in haystack:
        return False
    return not any(term in haystack for term in EXCLUDED_MODEL_TERMS)


def priority_key(model: dict[str, Any]) -> tuple[int, str]:
    haystack = f"{model.get('model_name') or ''} {model.get('display_name') or ''}".lower()
    if "gemini-3.1" in haystack or "gemini 3.1" in haystack:
        rank = 0
    elif "gemini-3" in haystack or "gemini 3" in haystack:
        rank = 1
    elif "gemini-2.5" in haystack or "gemini 2.5" in haystack:
        rank = 2
    else:
        rank = 3
    latest_bonus = 0 if "latest" in haystack else 1
    return (rank, latest_bonus, str(model.get("model_name") or ""))


def count_tokens_smoke(client: Any, model_name: str, smoke_text: str) -> dict[str, Any]:
    try:
        response = client.models.count_tokens(model=model_name, contents=smoke_text)
        token_count = getattr(response, "total_tokens", None)
        if token_count is None and hasattr(response, "model_dump"):
            token_count = response.model_dump().get("total_tokens")
        return {
            "model_name": model_name,
            "status": "success",
            "token_count": int(token_count or 0),
            "error_type": None,
            "error_message": None,
        }
    except Exception as exc:
        return {
            "model_name": model_name,
            "status": "failed",
            "token_count": None,
            "error_type": classify_error(str(exc)),
            "error_message": safe_error_message(str(exc)),
        }


def classify_error(message: str) -> str:
    lowered = message.lower()
    if "404" in lowered or "not_found" in lowered or "not found" in lowered:
        return "model_not_found_or_counttokens_unsupported"
    if "403" in lowered or "permission" in lowered or "forbidden" in lowered:
        return "permission_or_billing"
    if "api key" in lowered or "unauthenticated" in lowered or "401" in lowered:
        return "authentication"
    if "deadline" in lowered or "timeout" in lowered:
        return "timeout"
    return "provider_error"


def safe_error_message(message: str) -> str:
    # The SDK error normally does not include the key, but keep a defensive trim.
    return message.replace("\n", " ")[:1200]


def is_gemini_31_pro(model: dict[str, Any]) -> bool:
    haystack = f"{model.get('model_name') or ''} {model.get('display_name') or ''}".lower()
    return "gemini-3.1" in haystack or "gemini 3.1" in haystack


def is_gemini_3_pro(model: dict[str, Any]) -> bool:
    haystack = f"{model.get('model_name') or ''} {model.get('display_name') or ''}".lower()
    return "gemini-3" in haystack or "gemini 3" in haystack


def is_gemini_25_pro(model: dict[str, Any]) -> bool:
    haystack = f"{model.get('model_name') or ''} {model.get('display_name') or ''}".lower()
    return "gemini-2.5" in haystack or "gemini 2.5" in haystack


def build_warnings(
    *,
    pro_models: list[dict[str, Any]],
    selected_model: str | None,
    has_gemini_31_pro: bool,
    has_gemini_3_pro: bool,
    has_gemini_25_pro: bool,
) -> list[str]:
    warnings: list[str] = []
    if not pro_models:
        warnings.append("No accessible Pro models were returned by models.list.")
    if not has_gemini_31_pro:
        warnings.append("Gemini 3.1 Pro was not present in accessible API model list.")
    if not has_gemini_3_pro:
        warnings.append("Gemini 3 Pro was not present in accessible API model list.")
    if has_gemini_25_pro:
        warnings.append("Gemini 2.5 Pro is present as a reference Pro candidate.")
    if selected_model is None:
        warnings.append("No latest Pro model passed countTokens smoke test.")
    return warnings


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Discover accessible Gemini Pro models and countTokens support."
    )
    parser.add_argument("--out", required=True)
    parser.add_argument("--api-version", default="v1beta")
    parser.add_argument("--pretty", action="store_true")
    args = parser.parse_args()

    try:
        report = discover_gemini_pro_models(
            out_path=args.out,
            api_version=args.api_version,
            pretty=args.pretty,
        )
    except RuntimeError as exc:
        print(str(exc), file=sys.stderr)
        raise SystemExit(2) from exc

    print(
        json.dumps(
            {
                "out": args.out,
                "api_version": report["api_version"],
                "pro_model_count": report["summary"]["pro_model_count"],
                "selected_model": report["selected_model"],
                "count_tokens_success_count": report["summary"]["count_tokens_success_count"],
                "count_tokens_failed_count": report["summary"]["count_tokens_failed_count"],
                "warnings": report["warnings"],
            },
            ensure_ascii=False,
            indent=2 if args.pretty else None,
        )
    )


if __name__ == "__main__":
    main()

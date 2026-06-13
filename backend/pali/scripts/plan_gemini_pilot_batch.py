"""Create local Gemini Batch JSONL and sidecar manifest for the 75-sample pilot.

This script does not submit a Batch API job and does not call provider APIs.
"""

from __future__ import annotations

import argparse
import json
import sys
from collections import Counter
from datetime import datetime, timezone
from decimal import Decimal
from pathlib import Path
from typing import Any

REPO_ROOT = Path(__file__).resolve().parents[3]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from backend.pali.scripts.plan_gemini_smoke_batch import (
    DEFAULT_PRICE_PROFILE_ID,
    DEFAULT_PRICE_PROFILE_PATH,
    contains_secret_marker,
    load_price_profile,
    validate_smoke_batch,
    write_jsonl,
)
from backend.pali.translation.batch_plan import (
    BatchSegmentPlan,
    build_provider_jsonl_line,
    build_sidecar_metadata,
)
from backend.pali.translation.budget import (
    BudgetState,
    TokenEstimate,
    can_submit_batch_under_budget,
    estimate_request_cost,
)
from backend.pali.translation.prompts import (
    KOREAN_ADVANCED_PROMPT_ID,
    KOREAN_ADVANCED_PROMPT_VERSION,
    render_korean_advanced_prompt_v1,
)


OUTPUT_PROFILE = "korean_advanced"


def plan_gemini_pilot_batch(
    *,
    samples_path: str | Path,
    estimate_path: str | Path,
    out_jsonl_path: str | Path,
    out_manifest_path: str | Path,
    model: str,
    pilot_size: int = 75,
    max_estimated_cost_usd: Decimal = Decimal("50"),
    price_profile_path: str | Path | None = None,
    price_profile_id: str | None = None,
    source_calibration_path: str | Path | None = None,
    prompt_token_calibration_path: str | Path | None = None,
    kill_switch: bool = False,
    pretty_manifest: bool = False,
) -> dict[str, Any]:
    samples_file = Path(samples_path)
    sample_artifact = json.loads(samples_file.read_text(encoding="utf-8"))
    estimate_artifact = json.loads(Path(estimate_path).read_text(encoding="utf-8"))
    source_commit = sample_artifact.get("source_commit")
    selected = list(sample_artifact.get("pilot_samples") or [])[:pilot_size]
    if len(selected) != pilot_size:
        raise RuntimeError(f"Expected exactly {pilot_size} pilot samples, got {len(selected)}")

    estimate_by_key = {
        item.get("stable_segment_key"): item
        for item in estimate_artifact.get("items") or []
    }
    missing_estimates = [
        item.get("stable_segment_key")
        for item in selected
        if item.get("stable_segment_key") not in estimate_by_key
    ]
    if missing_estimates:
        raise RuntimeError(f"Missing pilot estimate items for keys: {missing_estimates[:5]}")

    price_profile = load_price_profile(price_profile_path, price_profile_id)
    plans = [
        sample_to_pilot_plan(sample, estimate_by_key[sample["stable_segment_key"]])
        for sample in selected
    ]
    estimated_costs = [
        estimate_request_cost(
            TokenEstimate(
                input_tokens=plan.estimated_input_tokens,
                output_tokens=plan.estimated_output_tokens,
                thinking_tokens=plan.estimated_thinking_tokens,
            ),
            price_profile,
        )
        for plan in plans
    ]
    estimated_cost_total = sum(estimated_costs, Decimal("0"))
    estimated_input_total = sum(plan.estimated_input_tokens for plan in plans)
    estimated_output_total = sum(plan.estimated_output_tokens for plan in plans)
    estimated_thinking_total = sum(plan.estimated_thinking_tokens for plan in plans)
    budget_decision = can_submit_batch_under_budget(
        BudgetState(
            actual_spent_usd=Decimal("0"),
            reserved_open_batches_usd=Decimal("0"),
            hard_cap_usd=max_estimated_cost_usd,
            kill_switch_enabled=kill_switch,
        ),
        estimated_cost_total,
    )
    if not budget_decision.can_submit:
        raise RuntimeError(f"Budget check failed: {budget_decision.reason.value}")

    generation_config = {
        "temperature": 0.2,
        "response_mime_type": "application/json",
    }
    jsonl_lines = [
        build_provider_jsonl_line(plan, generation_config=generation_config)
        for plan in plans
    ]
    sidecar_items = [
        {
            **build_sidecar_metadata(plan, estimated_cost),
            "pitaka": selected[index].get("pitaka"),
            "nikaya": selected[index].get("nikaya"),
            "length_bucket": selected[index].get("length_bucket"),
            "source_chars": len(selected[index].get("original_text") or ""),
            "model": model,
            "output_profile": OUTPUT_PROFILE,
            "prompt_template_id": KOREAN_ADVANCED_PROMPT_ID,
            "prompt_template_version": KOREAN_ADVANCED_PROMPT_VERSION,
            "jsonl_line_index": index,
        }
        for index, (plan, estimated_cost) in enumerate(zip(plans, estimated_costs, strict=True))
    ]
    manifest = {
        "source_commit": source_commit,
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "model": model,
        "request_count": len(plans),
        "expected_request_count": pilot_size,
        "estimated_input_tokens_total": estimated_input_total,
        "estimated_output_tokens_total": estimated_output_total,
        "estimated_thinking_tokens_total": estimated_thinking_total,
        "estimated_cost_usd_total": str(estimated_cost_total),
        "estimate_artifact_estimated_cost_usd": estimate_artifact.get("estimated_cost_usd"),
        "max_estimated_cost_usd": str(max_estimated_cost_usd),
        "budget_check_result": {
            "can_submit": budget_decision.can_submit,
            "reason": budget_decision.reason.value,
            "projected_total_usd": str(budget_decision.projected_total_usd),
            "remaining_budget_usd": str(budget_decision.remaining_budget_usd),
        },
        "provider_jsonl_path": str(out_jsonl_path),
        "price_profile_id": price_profile_id or DEFAULT_PRICE_PROFILE_ID,
        "output_profile": OUTPUT_PROFILE,
        "prompt_template_id": KOREAN_ADVANCED_PROMPT_ID,
        "prompt_template_version": KOREAN_ADVANCED_PROMPT_VERSION,
        "prompt_is_final": True,
        "source_calibration_path": str(source_calibration_path) if source_calibration_path else None,
        "prompt_token_calibration_path": str(prompt_token_calibration_path) if prompt_token_calibration_path else None,
        "estimate_artifact_path": str(estimate_path),
        "warnings": [
            "This is the approved 75-sample pilot JSONL artifact. Do not reuse it for larger batches.",
            "Output and thinking token estimates are rough until this pilot result is reconciled.",
        ],
        "distribution": sample_distribution(selected),
        "items": sidecar_items,
    }
    validation = validate_pilot_batch(jsonl_lines, manifest, expected_count=pilot_size)
    manifest["validation"] = validation
    if not validation["valid"]:
        raise RuntimeError(f"Pilot batch validation failed: {validation['errors']}")

    write_jsonl(Path(out_jsonl_path), jsonl_lines)
    Path(out_manifest_path).parent.mkdir(parents=True, exist_ok=True)
    Path(out_manifest_path).write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2 if pretty_manifest else None),
        encoding="utf-8",
    )
    return manifest


def sample_to_pilot_plan(sample: dict[str, Any], estimate: dict[str, Any]) -> BatchSegmentPlan:
    return BatchSegmentPlan(
        stable_segment_key=sample["stable_segment_key"],
        source_text_hash=sample["source_text_hash"],
        source_path=sample["source_path"],
        text_layer=sample["text_layer"],
        chunk_type=sample["chunk_type"],
        prompt_text=render_korean_advanced_prompt_v1(sample),
        estimated_input_tokens=int(estimate["estimated_input_tokens"]),
        estimated_output_tokens=int(estimate["estimated_output_tokens"]),
        estimated_thinking_tokens=int(estimate.get("estimated_thinking_tokens") or 0),
        metadata={
            "source_correction_factor": estimate.get("source_correction_factor"),
            "prompt_overhead_tokens_applied": estimate.get("prompt_overhead_tokens"),
            "pilot_estimate_source": "gemini_pilot_75_prompt_v1_schemafix_estimate",
        },
    )


def validate_pilot_batch(
    jsonl_lines: list[dict[str, Any]],
    manifest: dict[str, Any],
    *,
    expected_count: int,
) -> dict[str, Any]:
    validation = validate_smoke_batch(jsonl_lines, manifest)
    errors = list(validation["errors"])
    if manifest.get("request_count") != expected_count:
        errors.append(f"Pilot request_count must be exactly {expected_count}.")
    if len(jsonl_lines) != expected_count:
        errors.append(f"Provider JSONL line count must be exactly {expected_count}.")
    if manifest.get("prompt_template_version") != KOREAN_ADVANCED_PROMPT_VERSION:
        errors.append("Prompt template version mismatch.")
    serialized = json.dumps({"jsonl": jsonl_lines, "manifest": manifest}, ensure_ascii=False)
    if contains_secret_marker(serialized):
        errors.append("Pilot artifacts appear to contain credential-like content.")
    return {"valid": not errors, "errors": errors}


def sample_distribution(samples: list[dict[str, Any]]) -> dict[str, dict[str, int]]:
    return {
        "text_layer": count(samples, "text_layer"),
        "chunk_type": count(samples, "chunk_type"),
        "length_bucket": count(samples, "length_bucket"),
        "pitaka": count(samples, "pitaka"),
        "nikaya": count(samples, "nikaya"),
    }


def count(samples: list[dict[str, Any]], field: str) -> dict[str, int]:
    return dict(sorted(Counter(str(item.get(field) or "unknown") for item in samples).items()))


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Plan a local 75-sample Gemini Batch pilot JSONL artifact without submission."
    )
    parser.add_argument("--samples", required=True)
    parser.add_argument("--estimate", required=True)
    parser.add_argument("--out-jsonl", required=True)
    parser.add_argument("--out-manifest", required=True)
    parser.add_argument("--model", required=True)
    parser.add_argument("--pilot-size", type=int, default=75)
    parser.add_argument("--max-estimated-cost-usd", default="50")
    parser.add_argument("--price-profile", default=str(DEFAULT_PRICE_PROFILE_PATH))
    parser.add_argument("--price-profile-id", default=DEFAULT_PRICE_PROFILE_ID)
    parser.add_argument("--source-calibration")
    parser.add_argument("--prompt-token-calibration")
    parser.add_argument("--kill-switch", action="store_true")
    parser.add_argument("--pretty-manifest", action="store_true")
    args = parser.parse_args()

    try:
        manifest = plan_gemini_pilot_batch(
            samples_path=args.samples,
            estimate_path=args.estimate,
            out_jsonl_path=args.out_jsonl,
            out_manifest_path=args.out_manifest,
            model=args.model,
            pilot_size=args.pilot_size,
            max_estimated_cost_usd=Decimal(str(args.max_estimated_cost_usd)),
            price_profile_path=args.price_profile,
            price_profile_id=args.price_profile_id,
            source_calibration_path=args.source_calibration,
            prompt_token_calibration_path=args.prompt_token_calibration,
            kill_switch=args.kill_switch,
            pretty_manifest=args.pretty_manifest,
        )
    except RuntimeError as exc:
        print(str(exc), file=sys.stderr)
        raise SystemExit(2) from exc

    print(
        json.dumps(
            {
                "provider_jsonl_path": args.out_jsonl,
                "manifest_path": args.out_manifest,
                "request_count": manifest["request_count"],
                "estimated_input_tokens_total": manifest["estimated_input_tokens_total"],
                "estimated_output_tokens_total": manifest["estimated_output_tokens_total"],
                "estimated_thinking_tokens_total": manifest["estimated_thinking_tokens_total"],
                "estimated_cost_usd_total": manifest["estimated_cost_usd_total"],
                "budget_check_result": manifest["budget_check_result"],
                "validation": manifest["validation"],
                "distribution": manifest["distribution"],
            },
            ensure_ascii=False,
            indent=2 if args.pretty_manifest else None,
        )
    )


if __name__ == "__main__":
    main()

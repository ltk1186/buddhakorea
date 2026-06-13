"""Create a local-only 75 sample Gemini pilot estimate artifact.

This script does not submit Batch jobs and does not call provider APIs.
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
    correction_factor_for_sample,
    load_calibration,
    load_price_profile,
    prompt_v1_overhead_for_sample,
)
from backend.pali.translation.budget import TokenEstimate, estimate_request_cost
from backend.pali.translation.prompts import (
    KOREAN_ADVANCED_PROMPT_ID,
    KOREAN_ADVANCED_PROMPT_VERSION,
)


def estimate_gemini_pilot_batch(
    *,
    samples_path: str | Path,
    source_calibration_path: str | Path,
    previous_prompt_calibration_path: str | Path,
    schemafix_prompt_calibration_path: str | Path,
    smoke_summary_path: str | Path,
    corpus_corrected_summary_path: str | Path | None = None,
    out_path: str | Path,
    model: str,
    pilot_size: int = 75,
    budget_cap_usd: Decimal = Decimal("50"),
    price_profile_path: str | Path | None = None,
    price_profile_id: str | None = None,
    pretty: bool = False,
) -> dict[str, Any]:
    samples_file = Path(samples_path)
    samples_artifact = json.loads(samples_file.read_text(encoding="utf-8"))
    pilot_samples = list(samples_artifact.get("pilot_samples") or [])[:pilot_size]
    if len(pilot_samples) != pilot_size:
        raise RuntimeError(f"Expected {pilot_size} pilot samples, got {len(pilot_samples)}")

    source_commit = samples_artifact.get("source_commit")
    source_calibration = load_calibration(samples_file, source_commit, source_calibration_path)
    if source_calibration is None:
        raise RuntimeError("Source token calibration artifact is required.")
    previous_prompt = json.loads(Path(previous_prompt_calibration_path).read_text(encoding="utf-8"))
    schemafix_prompt = json.loads(Path(schemafix_prompt_calibration_path).read_text(encoding="utf-8"))
    smoke_summary = json.loads(Path(smoke_summary_path).read_text(encoding="utf-8"))
    price_profile = load_price_profile(price_profile_path, price_profile_id)

    output_ratio, thinking_ratio = smoke_ratios(smoke_summary)
    item_estimates = [
        estimate_item(
            sample,
            source_calibration=source_calibration,
            prompt_calibration=schemafix_prompt,
            output_ratio=output_ratio,
            thinking_ratio=thinking_ratio,
            price_profile=price_profile,
        )
        for sample in pilot_samples
    ]

    estimated_input = sum(item["estimated_input_tokens"] for item in item_estimates)
    estimated_output = sum(item["estimated_output_tokens"] for item in item_estimates)
    estimated_thinking = sum(item["estimated_thinking_tokens"] for item in item_estimates)
    estimated_cost = sum(
        (Decimal(str(item["estimated_cost_usd"])) for item in item_estimates),
        Decimal("0"),
    )
    budget_ok = estimated_cost <= budget_cap_usd

    comparison = compare_prompt_overheads(
        previous_prompt=previous_prompt,
        schemafix_prompt=schemafix_prompt,
        pilot_samples=pilot_samples,
        source_calibration=source_calibration,
        corpus_corrected_summary=(
            json.loads(Path(corpus_corrected_summary_path).read_text(encoding="utf-8"))
            if corpus_corrected_summary_path
            else None
        ),
    )
    report = {
        "source_commit": source_commit,
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "model": model,
        "prompt_template_id": KOREAN_ADVANCED_PROMPT_ID,
        "prompt_template_version": KOREAN_ADVANCED_PROMPT_VERSION,
        "request_count": len(pilot_samples),
        "estimated_input_tokens": estimated_input,
        "estimated_output_tokens": estimated_output,
        "estimated_thinking_tokens": estimated_thinking,
        "estimated_cost_usd": str(estimated_cost),
        "budget_cap_usd": str(budget_cap_usd),
        "budget_check": {
            "can_submit_under_cap": budget_ok,
            "remaining_budget_usd": str(budget_cap_usd - estimated_cost),
        },
        "price_profile_id": price_profile_id or DEFAULT_PRICE_PROFILE_ID,
        "source_calibration_path": str(source_calibration_path),
        "previous_prompt_calibration_path": str(previous_prompt_calibration_path),
        "schemafix_prompt_calibration_path": str(schemafix_prompt_calibration_path),
        "smoke_summary_path": str(smoke_summary_path),
        "corpus_corrected_summary_path": str(corpus_corrected_summary_path) if corpus_corrected_summary_path else None,
        "smoke_based_ratios": {
            "output_tokens_per_input_token": str(output_ratio),
            "thinking_tokens_per_input_token": str(thinking_ratio),
            "source": "5-segment schemafix smoke; rough estimate only.",
        },
        "sample_distribution": sample_distribution(pilot_samples),
        "prompt_overhead_comparison": comparison,
        "warnings": build_warnings(
            budget_ok=budget_ok,
            estimated_cost=estimated_cost,
            budget_cap_usd=budget_cap_usd,
        ),
        "items": item_estimates,
    }
    output_file = Path(out_path)
    output_file.parent.mkdir(parents=True, exist_ok=True)
    output_file.write_text(
        json.dumps(report, ensure_ascii=False, indent=2 if pretty else None),
        encoding="utf-8",
    )
    return report


def estimate_item(
    sample: dict[str, Any],
    *,
    source_calibration: dict[str, Any],
    prompt_calibration: dict[str, Any],
    output_ratio: Decimal,
    thinking_ratio: Decimal,
    price_profile: Any,
) -> dict[str, Any]:
    local_tokens = int((sample.get("token_estimates_by_profile") or {}).get("gemini_local_approx") or 0)
    source_factor = correction_factor_for_sample(sample, source_calibration)
    prompt_overhead = prompt_v1_overhead_for_sample(sample, prompt_calibration)
    estimated_input = round(local_tokens * source_factor) + prompt_overhead
    estimated_output = max(1, round(Decimal(estimated_input) * output_ratio))
    estimated_thinking = max(0, round(Decimal(estimated_input) * thinking_ratio))
    estimated_cost = estimate_request_cost(
        TokenEstimate(
            input_tokens=estimated_input,
            output_tokens=estimated_output,
            thinking_tokens=estimated_thinking,
        ),
        price_profile,
    )
    return {
        "stable_segment_key": sample.get("stable_segment_key"),
        "source_path": sample.get("source_path"),
        "text_layer": sample.get("text_layer"),
        "chunk_type": sample.get("chunk_type"),
        "length_bucket": sample.get("length_bucket"),
        "local_gemini_estimate_tokens": local_tokens,
        "source_correction_factor": str(source_factor),
        "prompt_overhead_tokens": prompt_overhead,
        "estimated_input_tokens": estimated_input,
        "estimated_output_tokens": estimated_output,
        "estimated_thinking_tokens": estimated_thinking,
        "estimated_cost_usd": str(estimated_cost),
    }


def smoke_ratios(smoke_summary: dict[str, Any]) -> tuple[Decimal, Decimal]:
    input_tokens = Decimal(int(smoke_summary.get("total_actual_input_tokens") or 0))
    if input_tokens <= 0:
        return Decimal("3"), Decimal("0")
    output = Decimal(int(smoke_summary.get("total_actual_output_tokens") or 0)) / input_tokens
    thinking = Decimal(int(smoke_summary.get("total_thinking_tokens") or 0)) / input_tokens
    return output, thinking


def compare_prompt_overheads(
    *,
    previous_prompt: dict[str, Any],
    schemafix_prompt: dict[str, Any],
    pilot_samples: list[dict[str, Any]],
    source_calibration: dict[str, Any],
    corpus_corrected_summary: dict[str, Any] | None = None,
) -> dict[str, Any]:
    previous_overhead = total_prompt_overhead_for_samples(pilot_samples, previous_prompt)
    schemafix_overhead = total_prompt_overhead_for_samples(pilot_samples, schemafix_prompt)
    previous_input = estimated_input_total(pilot_samples, source_calibration, previous_prompt)
    schemafix_input = estimated_input_total(pilot_samples, source_calibration, schemafix_prompt)
    comparison = {
        "previous_prompt_template_version": previous_prompt.get("prompt_template_version"),
        "schemafix_prompt_template_version": schemafix_prompt.get("prompt_template_version"),
        "average_overhead_previous": previous_prompt.get("average_prompt_v1_overhead_tokens"),
        "average_overhead_schemafix": schemafix_prompt.get("average_prompt_v1_overhead_tokens"),
        "median_overhead_previous": previous_prompt.get("median_prompt_v1_overhead_tokens"),
        "median_overhead_schemafix": schemafix_prompt.get("median_prompt_v1_overhead_tokens"),
        "p90_overhead_previous": previous_prompt.get("p90_prompt_v1_overhead_tokens"),
        "p90_overhead_schemafix": schemafix_prompt.get("p90_prompt_v1_overhead_tokens"),
        "total_prompt_overhead_previous": previous_prompt.get("prompt_v1_overhead_total"),
        "total_prompt_overhead_schemafix": schemafix_prompt.get("prompt_v1_overhead_total"),
        "overhead_increase_ratio": safe_decimal_ratio(
            schemafix_prompt.get("prompt_v1_overhead_total"),
            previous_prompt.get("prompt_v1_overhead_total"),
        ),
        "pilot_75_prompt_overhead_previous": previous_overhead,
        "pilot_75_prompt_overhead_schemafix": schemafix_overhead,
        "pilot_75_input_tokens_previous": previous_input,
        "pilot_75_input_tokens_schemafix": schemafix_input,
        "pilot_75_input_token_delta": schemafix_input - previous_input,
        "pilot_75_input_token_increase_ratio": safe_decimal_ratio(schemafix_input, previous_input),
    }
    if corpus_corrected_summary:
        comparison["full_corpus_input_estimate"] = full_corpus_input_estimate(
            corpus_corrected_summary=corpus_corrected_summary,
            previous_prompt=previous_prompt,
            schemafix_prompt=schemafix_prompt,
        )
    else:
        comparison["corpus_input_change_note"] = (
            "Full corpus input-token change should be calculated by applying the same layer-level "
            "prompt overhead deltas to the full segment inventory; this artifact estimates only the 75-sample pilot."
        )
    return comparison


def full_corpus_input_estimate(
    *,
    corpus_corrected_summary: dict[str, Any],
    previous_prompt: dict[str, Any],
    schemafix_prompt: dict[str, Any],
) -> dict[str, Any]:
    source_tokens = int(corpus_corrected_summary.get("totals", {}).get("total_corrected_gemini_source_tokens") or 0)
    previous_prompt_total = 0
    schemafix_prompt_total = 0
    layers: dict[str, Any] = {}
    for layer, data in (corpus_corrected_summary.get("layers") or {}).items():
        segments = int(data.get("segments") or 0)
        previous_avg = float(
            previous_prompt.get("overhead_by_text_layer", {})
            .get(layer, {})
            .get("average_prompt_v1_overhead_tokens")
            or previous_prompt.get("average_prompt_v1_overhead_tokens")
            or 0
        )
        schemafix_avg = float(
            schemafix_prompt.get("overhead_by_text_layer", {})
            .get(layer, {})
            .get("average_prompt_v1_overhead_tokens")
            or schemafix_prompt.get("average_prompt_v1_overhead_tokens")
            or 0
        )
        previous_layer_prompt = round(segments * previous_avg)
        schemafix_layer_prompt = round(segments * schemafix_avg)
        previous_prompt_total += previous_layer_prompt
        schemafix_prompt_total += schemafix_layer_prompt
        layers[layer] = {
            "segments": segments,
            "previous_prompt_overhead_tokens": previous_layer_prompt,
            "schemafix_prompt_overhead_tokens": schemafix_layer_prompt,
            "delta_prompt_overhead_tokens": schemafix_layer_prompt - previous_layer_prompt,
        }
    previous_total = source_tokens + previous_prompt_total
    schemafix_total = source_tokens + schemafix_prompt_total
    return {
        "method": "corrected source tokens plus layer-average prompt overhead per segment",
        "corrected_source_tokens": source_tokens,
        "previous_prompt_overhead_tokens": previous_prompt_total,
        "schemafix_prompt_overhead_tokens": schemafix_prompt_total,
        "previous_total_input_tokens": previous_total,
        "schemafix_total_input_tokens": schemafix_total,
        "delta_input_tokens": schemafix_total - previous_total,
        "total_input_increase_ratio": safe_decimal_ratio(schemafix_total, previous_total),
        "prompt_overhead_increase_ratio": safe_decimal_ratio(schemafix_prompt_total, previous_prompt_total),
        "by_text_layer": layers,
    }


def total_prompt_overhead_for_samples(
    samples: list[dict[str, Any]],
    prompt_calibration: dict[str, Any],
) -> int:
    return sum(prompt_v1_overhead_for_sample(sample, prompt_calibration) for sample in samples)


def estimated_input_total(
    samples: list[dict[str, Any]],
    source_calibration: dict[str, Any],
    prompt_calibration: dict[str, Any],
) -> int:
    total = 0
    for sample in samples:
        local_tokens = int((sample.get("token_estimates_by_profile") or {}).get("gemini_local_approx") or 0)
        total += round(local_tokens * correction_factor_for_sample(sample, source_calibration))
        total += prompt_v1_overhead_for_sample(sample, prompt_calibration)
    return total


def safe_decimal_ratio(numerator: Any, denominator: Any) -> float | None:
    if numerator in (None, 0) or denominator in (None, 0):
        return None
    return round(float(Decimal(str(numerator)) / Decimal(str(denominator))), 6)


def sample_distribution(samples: list[dict[str, Any]]) -> dict[str, dict[str, int]]:
    return {
        "text_layer": dict(sorted(Counter(str(item.get("text_layer") or "unknown") for item in samples).items())),
        "chunk_type": dict(sorted(Counter(str(item.get("chunk_type") or "unknown") for item in samples).items())),
        "length_bucket": dict(sorted(Counter(str(item.get("length_bucket") or "unknown") for item in samples).items())),
        "pitaka": dict(sorted(Counter(str(item.get("pitaka") or "unknown") for item in samples).items())),
        "nikaya": dict(sorted(Counter(str(item.get("nikaya") or "unknown") for item in samples).items())),
    }


def build_warnings(
    *,
    budget_ok: bool,
    estimated_cost: Decimal,
    budget_cap_usd: Decimal,
) -> list[str]:
    warnings = [
        "This is a local estimate artifact only; no Batch job was submitted.",
        "Output and thinking tokens use rough ratios from the 5-segment schemafix smoke result.",
        "Do not submit the 75-segment pilot without separate human approval.",
    ]
    if not budget_ok:
        warnings.append(
            f"Estimated cost {estimated_cost} exceeds pilot budget cap {budget_cap_usd}."
        )
    return warnings


def main() -> None:
    parser = argparse.ArgumentParser(description="Estimate a 75-sample Gemini pilot batch locally.")
    parser.add_argument("--samples", required=True)
    parser.add_argument("--source-calibration", required=True)
    parser.add_argument("--previous-prompt-calibration", required=True)
    parser.add_argument("--schemafix-prompt-calibration", required=True)
    parser.add_argument("--smoke-summary", required=True)
    parser.add_argument("--corpus-corrected-summary")
    parser.add_argument("--out", required=True)
    parser.add_argument("--model", required=True)
    parser.add_argument("--pilot-size", type=int, default=75)
    parser.add_argument("--budget-cap-usd", default="50")
    parser.add_argument("--price-profile", default=str(DEFAULT_PRICE_PROFILE_PATH))
    parser.add_argument("--price-profile-id", default=DEFAULT_PRICE_PROFILE_ID)
    parser.add_argument("--pretty", action="store_true")
    args = parser.parse_args()

    report = estimate_gemini_pilot_batch(
        samples_path=args.samples,
        source_calibration_path=args.source_calibration,
        previous_prompt_calibration_path=args.previous_prompt_calibration,
        schemafix_prompt_calibration_path=args.schemafix_prompt_calibration,
        smoke_summary_path=args.smoke_summary,
        corpus_corrected_summary_path=args.corpus_corrected_summary,
        out_path=args.out,
        model=args.model,
        pilot_size=args.pilot_size,
        budget_cap_usd=Decimal(str(args.budget_cap_usd)),
        price_profile_path=args.price_profile,
        price_profile_id=args.price_profile_id,
        pretty=args.pretty,
    )
    print(
        json.dumps(
            {
                "out": args.out,
                "request_count": report["request_count"],
                "estimated_input_tokens": report["estimated_input_tokens"],
                "estimated_output_tokens": report["estimated_output_tokens"],
                "estimated_thinking_tokens": report["estimated_thinking_tokens"],
                "estimated_cost_usd": report["estimated_cost_usd"],
                "budget_check": report["budget_check"],
            },
            ensure_ascii=False,
            indent=2 if args.pretty else None,
        )
    )


if __name__ == "__main__":
    main()

"""Create local Gemini Batch JSONL and sidecar manifest for a smoke batch.

This script does not submit a Batch API job and does not call generateContent.
"""

from __future__ import annotations

import argparse
import json
import random
import sys
from collections import Counter
from datetime import datetime, timezone
from decimal import Decimal
from pathlib import Path
from typing import Any

REPO_ROOT = Path(__file__).resolve().parents[3]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from backend.pali.translation.batch_plan import (
    BatchSegmentPlan,
    build_provider_jsonl_line,
    build_sidecar_metadata,
)
from backend.pali.translation.budget import (
    BudgetState,
    PriceProfile,
    TokenEstimate,
    can_submit_batch_under_budget,
    estimate_request_cost,
)
from backend.pali.translation.prompts import (
    KOREAN_ADVANCED_PROMPT_ID,
    KOREAN_ADVANCED_PROMPT_VERSION,
    render_korean_advanced_prompt_v1,
)


DEFAULT_PRICE_PROFILE_PATH = REPO_ROOT / "config" / "pali_batch_price_profiles.example.json"
DEFAULT_PRICE_PROFILE_ID = "mock_gemini_3_1_pro_batch_planning"
OUTPUT_PROFILE = "korean_advanced"


def plan_gemini_smoke_batch(
    *,
    samples_path: str | Path,
    out_jsonl_path: str | Path,
    out_manifest_path: str | Path,
    model: str,
    max_segments: int = 5,
    max_estimated_cost_usd: Decimal = Decimal("5"),
    price_profile_path: str | Path | None = None,
    price_profile_id: str | None = None,
    calibration_path: str | Path | None = None,
    prompt_token_calibration_path: str | Path | None = None,
    output_token_multiplier: Decimal = Decimal("3"),
    seed: int = 917,
    kill_switch: bool = False,
    prompt_version: str = KOREAN_ADVANCED_PROMPT_VERSION,
    pretty_manifest: bool = False,
) -> dict[str, Any]:
    if prompt_version != KOREAN_ADVANCED_PROMPT_VERSION:
        raise RuntimeError(f"Unsupported prompt version: {prompt_version}")

    samples_file = Path(samples_path)
    sample_artifact = json.loads(samples_file.read_text(encoding="utf-8"))
    source_commit = sample_artifact.get("source_commit")
    calibration = load_calibration(samples_file, source_commit, calibration_path)
    prompt_token_calibration = load_prompt_token_calibration(
        samples_file,
        source_commit,
        prompt_token_calibration_path,
    )
    price_profile = load_price_profile(price_profile_path, price_profile_id)
    warnings = build_initial_warnings(calibration, prompt_token_calibration)

    selected = select_smoke_samples(
        sample_artifact,
        max_segments=max_segments,
        seed=seed,
    )
    if len(selected) < 3:
        raise RuntimeError("Smoke batch requires at least 3 selected segments.")

    plans = [
        sample_to_segment_plan(
            sample,
            calibration=calibration,
            prompt_token_calibration=prompt_token_calibration,
            output_token_multiplier=output_token_multiplier,
        )
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
    budget_state = BudgetState(
        actual_spent_usd=Decimal("0"),
        reserved_open_batches_usd=Decimal("0"),
        hard_cap_usd=max_estimated_cost_usd,
        kill_switch_enabled=kill_switch,
    )
    budget_decision = can_submit_batch_under_budget(budget_state, estimated_cost_total)
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
        "estimated_input_tokens_total": estimated_input_total,
        "estimated_output_tokens_total": estimated_output_total,
        "estimated_cost_usd_total": str(estimated_cost_total),
        "max_estimated_cost_usd": str(max_estimated_cost_usd),
        "budget_check_result": {
            "can_submit": budget_decision.can_submit,
            "reason": budget_decision.reason.value,
            "projected_total_usd": str(budget_decision.projected_total_usd),
            "remaining_budget_usd": str(budget_decision.remaining_budget_usd),
        },
        "provider_jsonl_path": str(out_jsonl_path),
        "price_profile_id": price_profile_id or DEFAULT_PRICE_PROFILE_ID,
        "price_profile_is_mock": True,
        "output_profile": OUTPUT_PROFILE,
        "prompt_template_id": KOREAN_ADVANCED_PROMPT_ID,
        "prompt_template_version": KOREAN_ADVANCED_PROMPT_VERSION,
        "prompt_is_final": True,
        "prompt_token_calibration_path": str(prompt_token_calibration_path) if prompt_token_calibration_path else (
            str(samples_file.parent / f"gemini_prompt_v1_token_calibration_{source_commit[:7]}.json")
            if source_commit and prompt_token_calibration
            else None
        ),
        "prompt_overhead_estimate_source": (
            "prompt_v1_counttokens"
            if prompt_token_calibration
            else "unmeasured_prompt_v1"
        ),
        "prompt_overhead_average_tokens": (
            prompt_token_calibration.get("average_prompt_v1_overhead_tokens")
            if prompt_token_calibration
            else None
        ),
        "warnings": warnings,
        "distribution": {
            "text_layer": dict(Counter(item["text_layer"] for item in selected)),
            "chunk_type": dict(Counter(item["chunk_type"] for item in selected)),
            "length_bucket": dict(Counter(item["length_bucket"] for item in selected)),
        },
        "items": sidecar_items,
    }

    validation = validate_smoke_batch(jsonl_lines, manifest)
    manifest["validation"] = validation
    if not validation["valid"]:
        raise RuntimeError(f"Smoke batch validation failed: {validation['errors']}")

    write_jsonl(Path(out_jsonl_path), jsonl_lines)
    Path(out_manifest_path).parent.mkdir(parents=True, exist_ok=True)
    Path(out_manifest_path).write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2 if pretty_manifest else None),
        encoding="utf-8",
    )
    return manifest


def select_smoke_samples(
    sample_artifact: dict[str, Any],
    *,
    max_segments: int,
    seed: int,
) -> list[dict[str, Any]]:
    if max_segments < 3 or max_segments > 5:
        raise RuntimeError("--max-segments must be between 3 and 5 for smoke batch planning.")

    rng = random.Random(seed)
    candidates = list(sample_artifact.get("pilot_samples") or sample_artifact.get("calibration_samples") or [])
    rng.shuffle(candidates)
    candidates = sorted(candidates, key=lambda item: (length_rank(item), item.get("char_count") or 0))

    selected: list[dict[str, Any]] = []
    selected_keys: set[str] = set()

    for layer in ("mula", "atthakatha", "tika"):
        add_first_matching(selected, selected_keys, candidates, max_segments, text_layer=layer)
    add_first_matching(selected, selected_keys, candidates, max_segments, chunk_type="prose")
    add_first_matching(selected, selected_keys, candidates, max_segments, chunk_type="verse")
    add_first_matching(selected, selected_keys, candidates, max_segments, length_bucket="medium")

    for item in candidates:
        if len(selected) >= max_segments:
            break
        add_item(selected, selected_keys, item, max_segments)
    return selected


def add_first_matching(
    selected: list[dict[str, Any]],
    selected_keys: set[str],
    candidates: list[dict[str, Any]],
    max_segments: int,
    **criteria: str,
) -> None:
    if len(selected) >= max_segments:
        return
    for item in candidates:
        if all(item.get(key) == value for key, value in criteria.items()):
            add_item(selected, selected_keys, item, max_segments)
            return


def add_item(
    selected: list[dict[str, Any]],
    selected_keys: set[str],
    item: dict[str, Any],
    max_segments: int,
) -> None:
    key = item["stable_segment_key"]
    if len(selected) >= max_segments or key in selected_keys:
        return
    selected.append(item)
    selected_keys.add(key)


def length_rank(item: dict[str, Any]) -> int:
    return {"short": 0, "medium": 1, "long": 2}.get(str(item.get("length_bucket")), 3)


def sample_to_segment_plan(
    sample: dict[str, Any],
    *,
    calibration: dict[str, Any] | None,
    prompt_token_calibration: dict[str, Any] | None = None,
    output_token_multiplier: Decimal,
) -> BatchSegmentPlan:
    local_source_tokens = int(
        (sample.get("token_estimates_by_profile") or {}).get("gemini_local_approx") or 0
    )
    factor = correction_factor_for_sample(sample, calibration)
    prompt_overhead = prompt_v1_overhead_for_sample(sample, prompt_token_calibration)
    estimated_input = round(local_source_tokens * factor) + prompt_overhead
    estimated_output = round(Decimal(estimated_input) * output_token_multiplier)
    return BatchSegmentPlan(
        stable_segment_key=sample["stable_segment_key"],
        source_text_hash=sample["source_text_hash"],
        source_path=sample["source_path"],
        text_layer=sample["text_layer"],
        chunk_type=sample["chunk_type"],
        prompt_text=render_korean_advanced_prompt_v1(sample),
        estimated_input_tokens=estimated_input,
        estimated_output_tokens=estimated_output,
        metadata={
            "calibration_factor_applied": str(factor),
            "prompt_overhead_tokens_applied": prompt_overhead,
            "prompt_overhead_source": (
                "prompt_v1_counttokens"
                if prompt_token_calibration
                else "unmeasured_prompt_v1"
            ),
        },
    )


def correction_factor_for_sample(sample: dict[str, Any], calibration: dict[str, Any] | None) -> Decimal:
    if not calibration:
        return Decimal("1")
    factors = calibration.get("aggregate_totals", {}).get("recommended_source_correction_factor") or {}
    by_layer = factors.get("by_text_layer") or {}
    factor = by_layer.get(sample.get("text_layer")) or factors.get("overall") or 1
    return Decimal(str(factor))


def prompt_v1_overhead_for_sample(
    sample: dict[str, Any],
    prompt_token_calibration: dict[str, Any] | None,
) -> int:
    if not prompt_token_calibration:
        return 0
    layer = sample.get("text_layer")
    by_layer = prompt_token_calibration.get("overhead_by_text_layer") or {}
    layer_summary = by_layer.get(layer) or {}
    value = (
        layer_summary.get("average_prompt_v1_overhead_tokens")
        or prompt_token_calibration.get("average_prompt_v1_overhead_tokens")
        or 0
    )
    return int(round(float(value)))


def load_calibration(
    samples_file: Path,
    source_commit: str | None,
    calibration_path: str | Path | None,
) -> dict[str, Any] | None:
    candidates: list[Path] = []
    if calibration_path:
        candidates.append(Path(calibration_path))
    if source_commit:
        candidates.append(samples_file.parent / f"gemini_token_calibration_{source_commit[:7]}.json")
    for path in candidates:
        if path.exists():
            return json.loads(path.read_text(encoding="utf-8"))
    return None


def load_prompt_token_calibration(
    samples_file: Path,
    source_commit: str | None,
    prompt_token_calibration_path: str | Path | None,
) -> dict[str, Any] | None:
    candidates: list[Path] = []
    if prompt_token_calibration_path:
        candidates.append(Path(prompt_token_calibration_path))
    if source_commit:
        candidates.append(samples_file.parent / f"gemini_prompt_v1_token_calibration_{source_commit[:7]}.json")
    for path in candidates:
        if path.exists():
            return json.loads(path.read_text(encoding="utf-8"))
    return None


def load_price_profile(
    price_profile_path: str | Path | None,
    price_profile_id: str | None,
) -> PriceProfile:
    path = Path(price_profile_path) if price_profile_path else DEFAULT_PRICE_PROFILE_PATH
    data = json.loads(path.read_text(encoding="utf-8"))
    target_id = price_profile_id or DEFAULT_PRICE_PROFILE_ID
    profiles = data.get("profiles") or []
    profile = next((item for item in profiles if item.get("profile_id") == target_id), None)
    if profile is None:
        raise RuntimeError(f"Price profile not found: {target_id}")
    return PriceProfile(
        input_usd_per_million_tokens=Decimal(str(profile["input_usd_per_million_tokens"])),
        output_usd_per_million_tokens=Decimal(str(profile["output_usd_per_million_tokens"])),
        thinking_usd_per_million_tokens=Decimal(str(profile.get("thinking_usd_per_million_tokens", "0"))),
        batch_discount_multiplier=Decimal(str(profile.get("batch_discount_multiplier", "1"))),
    )


def build_initial_warnings(
    calibration: dict[str, Any] | None,
    prompt_token_calibration: dict[str, Any] | None,
) -> list[str]:
    warnings = [
        "This is a local dry-run artifact only. It must not be submitted automatically.",
        "The prompt is Korean Advanced Prompt v1; regenerate JSONL if Prompt v1 changes.",
        "The default price profile is mock planning data; replace it before real submission.",
    ]
    if calibration is None:
        warnings.append("No calibration artifact was found; local Gemini estimates were not corrected.")
    if prompt_token_calibration is None:
        warnings.append("No Prompt v1 countTokens calibration artifact was found; input estimates omit Prompt v1 overhead.")
    else:
        warnings.append("Input estimates use Prompt v1 countTokens overhead; old placeholder overhead 106 is deprecated.")
    return warnings


def validate_smoke_batch(
    jsonl_lines: list[dict[str, Any]],
    manifest: dict[str, Any],
) -> dict[str, Any]:
    errors: list[str] = []
    items = manifest.get("items") or []
    if len(jsonl_lines) != len(items):
        errors.append("JSONL line count does not match manifest item count.")
    keys = [line.get("key") for line in jsonl_lines]
    if len(keys) != len(set(keys)):
        errors.append("Duplicate provider JSONL keys found.")
    item_keys = [item.get("stable_segment_key") for item in items]
    if keys != item_keys:
        errors.append("Provider JSONL keys do not match manifest stable_segment_key order.")
    for index, item in enumerate(items):
        if item.get("jsonl_line_index") != index:
            errors.append(f"Invalid jsonl_line_index for item {index}.")
        if not item.get("source_text_hash"):
            errors.append(f"Missing source_text_hash for item {index}.")
    for index, line in enumerate(jsonl_lines):
        try:
            encoded = json.dumps(line, ensure_ascii=False)
            json.loads(encoded)
        except Exception:
            errors.append(f"Invalid JSONL line at index {index}.")
        text = (
            line.get("request", {})
            .get("contents", [{}])[0]
            .get("parts", [{}])[0]
            .get("text", "")
        )
        if ("빠알리 원문:" not in text and "Pāli source:" not in text) or "<<<" not in text:
            errors.append(f"Request text does not include source block at index {index}.")
    estimated_total = Decimal(str(manifest.get("estimated_cost_usd_total") or "0"))
    max_cost = Decimal(str(manifest.get("max_estimated_cost_usd") or "0"))
    if estimated_total > max_cost:
        errors.append("Estimated cost exceeds max_estimated_cost_usd.")
    serialized_manifest = json.dumps(manifest, ensure_ascii=False)
    if contains_secret_marker(serialized_manifest):
        errors.append("Manifest appears to contain credential-like content.")
    return {"valid": not errors, "errors": errors}


def contains_secret_marker(text: str) -> bool:
    markers = ("GEMINI_API_KEY", "GOOGLE_API_KEY", "GOOGLE_GENAI_API_KEY", "AIza")
    return any(marker in text for marker in markers)


def write_jsonl(path: Path, lines: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        "\n".join(json.dumps(line, ensure_ascii=False) for line in lines) + "\n",
        encoding="utf-8",
    )


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Plan a local Gemini Batch smoke JSONL artifact without submission."
    )
    parser.add_argument("--samples", required=True)
    parser.add_argument("--out-jsonl", required=True)
    parser.add_argument("--out-manifest", required=True)
    parser.add_argument("--model", required=True)
    parser.add_argument("--max-segments", type=int, default=5)
    parser.add_argument("--price-profile")
    parser.add_argument("--price-profile-id")
    parser.add_argument("--calibration")
    parser.add_argument("--prompt-token-calibration")
    parser.add_argument("--max-estimated-cost-usd", default="5")
    parser.add_argument("--output-token-multiplier", default="3")
    parser.add_argument("--seed", type=int, default=917)
    parser.add_argument("--kill-switch", action="store_true")
    parser.add_argument("--prompt-version", default=KOREAN_ADVANCED_PROMPT_VERSION)
    parser.add_argument("--pretty-manifest", action="store_true")
    args = parser.parse_args()

    try:
        manifest = plan_gemini_smoke_batch(
            samples_path=args.samples,
            out_jsonl_path=args.out_jsonl,
            out_manifest_path=args.out_manifest,
            model=args.model,
            max_segments=args.max_segments,
            max_estimated_cost_usd=Decimal(str(args.max_estimated_cost_usd)),
            price_profile_path=args.price_profile,
            price_profile_id=args.price_profile_id,
            calibration_path=args.calibration,
            prompt_token_calibration_path=args.prompt_token_calibration,
            output_token_multiplier=Decimal(str(args.output_token_multiplier)),
            seed=args.seed,
            kill_switch=args.kill_switch,
            prompt_version=args.prompt_version,
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

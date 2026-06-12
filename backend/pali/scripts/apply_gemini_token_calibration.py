"""Apply Gemini countTokens calibration factors to a corpus token summary.

This script only transforms local token summary artifacts. It does not call any
LLM API and does not calculate official price-based costs.
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


GEMINI_LOCAL_PROFILE_ID = "gemini_local_approx"


def apply_gemini_token_calibration(
    *,
    corpus_summary_path: str | Path,
    calibration_path: str | Path,
    out_path: str | Path,
    pretty: bool = False,
) -> dict[str, Any]:
    corpus_summary = json.loads(Path(corpus_summary_path).read_text(encoding="utf-8"))
    calibration = json.loads(Path(calibration_path).read_text(encoding="utf-8"))

    report = build_corrected_report(
        corpus_summary=corpus_summary,
        calibration=calibration,
        corpus_summary_path=str(corpus_summary_path),
        calibration_path=str(calibration_path),
    )

    output_file = Path(out_path)
    output_file.parent.mkdir(parents=True, exist_ok=True)
    output_file.write_text(
        json.dumps(report, ensure_ascii=False, indent=2 if pretty else None),
        encoding="utf-8",
    )
    return report


def build_corrected_report(
    *,
    corpus_summary: dict[str, Any],
    calibration: dict[str, Any],
    corpus_summary_path: str,
    calibration_path: str,
) -> dict[str, Any]:
    correction_factors = calibration["aggregate_totals"]["recommended_source_correction_factor"]
    overall_factor = float(correction_factors["overall"])
    factor_by_layer = {
        layer: float(factor)
        for layer, factor in (correction_factors.get("by_text_layer") or {}).items()
        if factor is not None
    }
    factor_by_chunk = extract_ratio_map(calibration, "ratio_by_chunk_type")
    factor_by_length = extract_ratio_map(calibration, "ratio_by_length_bucket")
    prompt_overhead = {
        "average": calibration["aggregate_totals"].get("average_prompt_overhead_tokens"),
        "median": calibration["aggregate_totals"].get("median_prompt_overhead_tokens"),
        "p90": calibration["aggregate_totals"].get("p90_prompt_overhead_tokens"),
    }

    layer_reports: dict[str, dict[str, Any]] = {}
    total_files = 0
    total_segments = 0
    total_local = 0
    total_corrected = 0
    for layer in sorted(corpus_summary.get("tokens_by_text_layer_and_profile", {})):
        local_tokens = int(
            corpus_summary["tokens_by_text_layer_and_profile"]
            .get(layer, {})
            .get(GEMINI_LOCAL_PROFILE_ID, 0)
        )
        factor = factor_by_layer.get(layer, overall_factor)
        corrected_tokens = round(local_tokens * factor)
        files = int(corpus_summary.get("files_by_text_layer", {}).get(layer, 0))
        segments = int(corpus_summary.get("segments_by_text_layer", {}).get(layer, 0))
        layer_reports[layer] = {
            "files": files,
            "segments": segments,
            "local_gemini_heuristic_source_tokens": local_tokens,
            "applied_correction_factor": factor,
            "correction_factor_source": "text_layer" if layer in factor_by_layer else "overall_fallback",
            "corrected_gemini_source_tokens": corrected_tokens,
        }
        total_files += files
        total_segments += segments
        total_local += local_tokens
        total_corrected += corrected_tokens

    report = {
        "source_commit": corpus_summary.get("source_commit") or calibration.get("source_commit"),
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "input_artifacts": {
            "corpus_summary": corpus_summary_path,
            "calibration": calibration_path,
        },
        "correction_model": "Gemini countTokens sample calibration",
        "correction_model_string": calibration.get("model"),
        "calibration_sample_size": calibration.get("sample_size"),
        "correction_factor_overall": overall_factor,
        "correction_factor_by_text_layer": factor_by_layer,
        "correction_factor_by_chunk_type": factor_by_chunk,
        "correction_factor_by_length_bucket": factor_by_length,
        "prompt_overhead_placeholder_tokens": prompt_overhead,
        "warnings": build_warnings(factor_by_layer, factor_by_chunk, factor_by_length),
        "layers": layer_reports,
        "totals": {
            "total_files": total_files,
            "total_segments": total_segments,
            "total_local_gemini_heuristic_source_tokens": total_local,
            "total_corrected_gemini_source_tokens": total_corrected,
        },
        "diagnostics": {
            "prose_vs_verse_ratio_note": prose_vs_verse_note(factor_by_chunk),
            "short_medium_long_ratio_note": length_ratio_note(factor_by_length),
            "prompt_overhead_note": (
                "Placeholder Korean Advanced prompt wrapper added a constant "
                f"{prompt_overhead['average']} token average overhead in the 150-sample calibration. "
                "Rerun after Korean Advanced Prompt v1 is finalized."
            ),
            "calibration_limitations": [
                "Corrected source tokens include source text only.",
                "Corrected source tokens do not include final prompt overhead.",
                "Corrected source tokens do not include output tokens.",
                "Corrected source tokens do not include context, DPD hints, RAG, retries, or arbitration.",
                "Official price-based total cost calculation is out of scope for this report.",
                "Default correction uses text_layer factors; chunk-type ratios are diagnostics only.",
            ],
        },
    }
    return report


def extract_ratio_map(calibration: dict[str, Any], breakdown_key: str) -> dict[str, float]:
    breakdown = calibration.get("breakdowns", {}).get(breakdown_key) or {}
    return {
        key: float(value["ratio"])
        for key, value in breakdown.items()
        if value.get("ratio") is not None
    }


def build_warnings(
    factor_by_layer: dict[str, float],
    factor_by_chunk: dict[str, float],
    factor_by_length: dict[str, float],
) -> list[str]:
    warnings = [
        "Local Gemini heuristic source token estimates are undercounts versus Gemini official countTokens.",
        "This report is a corrected source input token estimate only, not a cost estimate.",
    ]
    if "verse" in factor_by_chunk and "prose" in factor_by_chunk:
        if factor_by_chunk["verse"] > factor_by_chunk["prose"]:
            warnings.append(
                "Verse sample ratio is higher than prose sample ratio; layer-level correction may understate verse-heavy corpora."
            )
    if set(factor_by_length) >= {"short", "medium", "long"}:
        warnings.append(
            "Length-bucket correction ratios are diagnostic only; text_layer factors remain the default correction."
        )
    if not factor_by_layer:
        warnings.append("No text_layer correction factors were found; overall factor will be used for every layer.")
    return warnings


def prose_vs_verse_note(factor_by_chunk: dict[str, float]) -> str:
    prose = factor_by_chunk.get("prose")
    verse = factor_by_chunk.get("verse")
    if prose is None or verse is None:
        return "Prose/verse diagnostic ratio was unavailable in the calibration artifact."
    return (
        f"Calibration ratio for verse ({verse}) is higher than prose ({prose}). "
        "The default report still applies text_layer factors, but verse-heavy subsets should be reviewed separately."
    )


def length_ratio_note(factor_by_length: dict[str, float]) -> str:
    if not factor_by_length:
        return "Length-bucket diagnostic ratios were unavailable in the calibration artifact."
    parts = ", ".join(f"{key}={value}" for key, value in sorted(factor_by_length.items()))
    return (
        f"Length-bucket diagnostic ratios: {parts}. "
        "These are recorded for review and are not used in the default correction."
    )


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Apply Gemini countTokens calibration to a corpus token summary."
    )
    parser.add_argument("--corpus-summary", required=True)
    parser.add_argument("--calibration", required=True)
    parser.add_argument("--out", required=True)
    parser.add_argument("--pretty", action="store_true")
    args = parser.parse_args()

    report = apply_gemini_token_calibration(
        corpus_summary_path=args.corpus_summary,
        calibration_path=args.calibration,
        out_path=args.out,
        pretty=args.pretty,
    )
    print(
        json.dumps(
            {
                "out": args.out,
                "source_commit": report["source_commit"],
                "correction_model_string": report["correction_model_string"],
                "total_corrected_gemini_source_tokens": report["totals"][
                    "total_corrected_gemini_source_tokens"
                ],
                "correction_factor_overall": report["correction_factor_overall"],
            },
            ensure_ascii=False,
            indent=2 if args.pretty else None,
        )
    )


if __name__ == "__main__":
    main()

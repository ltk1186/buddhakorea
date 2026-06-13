"""Measure Gemini countTokens overhead for Korean Advanced Prompt v1.

This script never calls text-generation APIs. It only calls Gemini countTokens
when --dry-run is not set.
"""

from __future__ import annotations

import argparse
import json
import sys
from collections import Counter, defaultdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

REPO_ROOT = Path(__file__).resolve().parents[3]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from backend.pali.scripts.calibrate_gemini_tokens import (
    CountTokensClient,
    GeminiCountTokensClient,
    count_with_retries,
    local_gemini_estimate,
    mean_or_none,
    median_or_none,
    percentile_or_none,
    resolve_gemini_api_key,
    sample_source_text,
    take_evenly,
)
from backend.pali.translation.prompts import (
    KOREAN_ADVANCED_PROMPT_ID,
    KOREAN_ADVANCED_PROMPT_VERSION,
    render_korean_advanced_prompt_v1,
)


DEFAULT_SAMPLE_SET = "calibration_samples"


def calibrate_prompt_v1_tokens(
    *,
    samples_path: str | Path,
    model: str,
    out_path: str | Path,
    sample_set: str = DEFAULT_SAMPLE_SET,
    max_samples: int | None = None,
    dry_run: bool = False,
    timeout_seconds: int = 60,
    max_retries: int = 2,
    retry_backoff_seconds: float = 2.0,
    api_key: str | None = None,
    client: CountTokensClient | None = None,
    pretty: bool = False,
) -> dict[str, Any]:
    samples_file = Path(samples_path)
    samples_artifact = json.loads(samples_file.read_text(encoding="utf-8"))
    samples = select_samples(samples_artifact, sample_set=sample_set, max_samples=max_samples)

    if not dry_run and client is None:
        resolved_api_key = api_key or resolve_gemini_api_key()
        if not resolved_api_key:
            raise RuntimeError(
                "A Gemini API key is required for Prompt v1 countTokens calibration. "
                "Checked GEMINI_API_KEY, GOOGLE_API_KEY, GOOGLE_GENAI_API_KEY, "
                "and PALI_GEMINI_API_KEY from the environment and local .env files. "
                "Use --dry-run to generate an execution plan without API calls."
            )
        client = GeminiCountTokensClient(
            api_key=resolved_api_key,
            timeout_seconds=timeout_seconds,
        )

    results: list[dict[str, Any]] = []
    failed_samples: list[dict[str, Any]] = []
    for sample in samples:
        result = build_base_prompt_v1_result(sample)
        source_text = sample_source_text(sample)
        prompt_text = render_korean_advanced_prompt_v1(sample)
        result["prompt_chars"] = len(prompt_text)

        if dry_run:
            result.update(
                {
                    "source_text_only_tokens": None,
                    "prompt_v1_with_source_tokens": None,
                    "prompt_v1_overhead_tokens": None,
                    "status": "dry_run",
                    "error_message": None,
                }
            )
            results.append(result)
            continue

        try:
            source_tokens = count_with_retries(
                client=client,
                model=model,
                contents=source_text,
                max_retries=max_retries,
                retry_backoff_seconds=retry_backoff_seconds,
            )
            prompt_tokens = count_with_retries(
                client=client,
                model=model,
                contents=prompt_text,
                max_retries=max_retries,
                retry_backoff_seconds=retry_backoff_seconds,
            )
            result.update(
                {
                    "source_text_only_tokens": source_tokens,
                    "prompt_v1_with_source_tokens": prompt_tokens,
                    "prompt_v1_overhead_tokens": prompt_tokens - source_tokens,
                    "status": "success",
                    "error_message": None,
                }
            )
        except Exception as exc:  # provider failures should not stop the run
            result.update(
                {
                    "source_text_only_tokens": None,
                    "prompt_v1_with_source_tokens": None,
                    "prompt_v1_overhead_tokens": None,
                    "status": "failed",
                    "error_message": str(exc),
                }
            )
            failed_samples.append(
                {
                    "stable_segment_key": result["stable_segment_key"],
                    "source_path": result["source_path"],
                    "error_message": str(exc),
                }
            )
        results.append(result)

    report = build_prompt_v1_report(
        samples_artifact=samples_artifact,
        input_samples_path=str(samples_file),
        model=model,
        sample_set=sample_set,
        dry_run=dry_run,
        timeout_seconds=timeout_seconds,
        max_retries=max_retries,
        retry_backoff_seconds=retry_backoff_seconds,
        results=results,
        failed_samples=failed_samples,
    )

    output_file = Path(out_path)
    output_file.parent.mkdir(parents=True, exist_ok=True)
    output_file.write_text(
        json.dumps(report, ensure_ascii=False, indent=2 if pretty else None),
        encoding="utf-8",
    )
    return report


def select_samples(
    samples_artifact: dict[str, Any],
    *,
    sample_set: str,
    max_samples: int | None,
) -> list[dict[str, Any]]:
    samples = list(samples_artifact.get(sample_set) or [])
    if not samples:
        raise RuntimeError(f"Sample set not found or empty: {sample_set}")
    if max_samples is None or max_samples >= len(samples):
        return samples
    return balanced_sample_subset(samples, max(0, max_samples))


def balanced_sample_subset(samples: list[dict[str, Any]], target_size: int) -> list[dict[str, Any]]:
    if target_size <= 0:
        return []
    grouped: dict[tuple[str, str, str], list[dict[str, Any]]] = defaultdict(list)
    for sample in samples:
        key = (
            str(sample.get("text_layer") or "unknown"),
            str(sample.get("chunk_type") or "unknown"),
            str(sample.get("length_bucket") or "unknown"),
        )
        grouped[key].append(sample)

    groups = sorted(grouped)
    quota = distribute_evenly(target_size, groups)
    selected: list[dict[str, Any]] = []
    selected_keys: set[str] = set()
    for group in groups:
        for sample in take_evenly(grouped[group], quota[group]):
            selected.append(sample)
            selected_keys.add(str(sample.get("stable_segment_key")))

    if len(selected) < target_size:
        for sample in samples:
            if len(selected) >= target_size:
                break
            key = str(sample.get("stable_segment_key"))
            if key not in selected_keys:
                selected.append(sample)
                selected_keys.add(key)
    return selected[:target_size]


def distribute_evenly(target_size: int, groups: list[tuple[str, str, str]]) -> dict[tuple[str, str, str], int]:
    if not groups:
        return {}
    base = target_size // len(groups)
    remainder = target_size % len(groups)
    return {
        group: base + (1 if index < remainder else 0)
        for index, group in enumerate(groups)
    }


def build_base_prompt_v1_result(sample: dict[str, Any]) -> dict[str, Any]:
    source_text = sample_source_text(sample)
    return {
        "stable_segment_key": sample.get("stable_segment_key"),
        "source_path": sample.get("source_path"),
        "text_layer": sample.get("text_layer"),
        "pitaka": sample.get("pitaka"),
        "nikaya": sample.get("nikaya"),
        "chunk_type": sample.get("chunk_type"),
        "length_bucket": sample.get("length_bucket"),
        "source_chars": len(source_text),
        "local_gemini_estimate_tokens": local_gemini_estimate(sample),
    }


def build_prompt_v1_report(
    *,
    samples_artifact: dict[str, Any],
    input_samples_path: str,
    model: str,
    sample_set: str,
    dry_run: bool,
    timeout_seconds: int,
    max_retries: int,
    retry_backoff_seconds: float,
    results: list[dict[str, Any]],
    failed_samples: list[dict[str, Any]],
) -> dict[str, Any]:
    successful = [row for row in results if row["status"] == "success"]
    source_total = sum(row["source_text_only_tokens"] for row in successful)
    prompt_total = sum(row["prompt_v1_with_source_tokens"] for row in successful)
    overhead_total = sum(row["prompt_v1_overhead_tokens"] for row in successful)
    overheads = [row["prompt_v1_overhead_tokens"] for row in successful]

    warnings = build_warnings(dry_run=dry_run, successful=successful, results=results)
    return {
        "source_commit": samples_artifact.get("source_commit"),
        "model": model,
        "prompt_template_id": KOREAN_ADVANCED_PROMPT_ID,
        "prompt_template_version": KOREAN_ADVANCED_PROMPT_VERSION,
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "sample_size": len(results),
        "successful_sample_count": len(successful),
        "failed_sample_count": len(failed_samples),
        "sample_set": sample_set,
        "input_samples_path": input_samples_path,
        "api_used": None if dry_run else "gemini.countTokens",
        "dry_run": dry_run,
        "execution": {
            "timeout_seconds": timeout_seconds,
            "max_retries": max_retries,
            "retry_backoff_seconds": retry_backoff_seconds,
        },
        "source_text_only_total": source_total if successful else None,
        "prompt_with_source_total": prompt_total if successful else None,
        "prompt_v1_with_source_total": prompt_total if successful else None,
        "prompt_overhead_total": overhead_total if successful else None,
        "prompt_v1_overhead_total": overhead_total if successful else None,
        "average_prompt_overhead_tokens": mean_or_none(overheads),
        "average_prompt_v1_overhead_tokens": mean_or_none(overheads),
        "median_prompt_overhead_tokens": median_or_none(overheads),
        "median_prompt_v1_overhead_tokens": median_or_none(overheads),
        "p90_prompt_overhead_tokens": percentile_or_none(overheads, 90),
        "p90_prompt_v1_overhead_tokens": percentile_or_none(overheads, 90),
        "overhead_by_text_layer": overhead_by_group(successful, "text_layer"),
        "overhead_by_chunk_type": overhead_by_group(successful, "chunk_type"),
        "overhead_by_length_bucket": overhead_by_group(successful, "length_bucket"),
        "diagnostics": {
            "sample_distribution": sample_distribution(results),
            "largest_prompt_v1_overhead_samples": largest_prompt_v1_overhead_samples(successful),
            "failed_samples": failed_samples,
            "warnings": warnings,
        },
        "failed_samples": failed_samples,
        "warnings": warnings,
        "sample_results": results,
    }


def build_warnings(
    *,
    dry_run: bool,
    successful: list[dict[str, Any]],
    results: list[dict[str, Any]],
) -> list[str]:
    warnings: list[str] = [
        "Prompt v1 overhead supersedes the old placeholder overhead of 106 tokens.",
        "This report uses Gemini countTokens only; it does not call generateContent or submit Batch jobs.",
        "Output token counts remain unknown until a real translation smoke or pilot batch is run.",
    ]
    if dry_run:
        warnings.append("Dry-run mode: no Gemini API calls were made.")
    if not successful and not dry_run:
        warnings.append("No successful Prompt v1 countTokens results were produced.")
    if any(row["local_gemini_estimate_tokens"] == 0 for row in results):
        warnings.append("Some samples have zero local Gemini estimate; use source_text_only_tokens for Prompt v1 overhead.")
    return warnings


def overhead_by_group(rows: list[dict[str, Any]], field: str) -> dict[str, Any]:
    grouped: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for row in rows:
        grouped[str(row.get(field) or "unknown")].append(row)
    return {
        key: overhead_summary(group_rows)
        for key, group_rows in sorted(grouped.items())
    }


def overhead_summary(rows: list[dict[str, Any]]) -> dict[str, Any]:
    source_total = sum(row["source_text_only_tokens"] for row in rows)
    prompt_total = sum(row["prompt_v1_with_source_tokens"] for row in rows)
    overheads = [row["prompt_v1_overhead_tokens"] for row in rows]
    return {
        "sample_count": len(rows),
        "source_text_only_total": source_total,
        "prompt_v1_with_source_total": prompt_total,
        "prompt_v1_overhead_total": sum(overheads),
        "average_prompt_v1_overhead_tokens": mean_or_none(overheads),
        "median_prompt_v1_overhead_tokens": median_or_none(overheads),
        "p90_prompt_v1_overhead_tokens": percentile_or_none(overheads, 90),
    }


def sample_distribution(rows: list[dict[str, Any]]) -> dict[str, dict[str, int]]:
    return {
        "text_layer": counter_dict(rows, "text_layer"),
        "chunk_type": counter_dict(rows, "chunk_type"),
        "length_bucket": counter_dict(rows, "length_bucket"),
        "pitaka": counter_dict(rows, "pitaka"),
        "nikaya": counter_dict(rows, "nikaya"),
    }


def counter_dict(rows: list[dict[str, Any]], field: str) -> dict[str, int]:
    return dict(sorted(Counter(str(row.get(field) or "unknown") for row in rows).items()))


def largest_prompt_v1_overhead_samples(
    rows: list[dict[str, Any]],
    limit: int = 10,
) -> list[dict[str, Any]]:
    ranked = sorted(
        [row for row in rows if row["prompt_v1_overhead_tokens"] is not None],
        key=lambda row: row["prompt_v1_overhead_tokens"],
        reverse=True,
    )
    return [
        {
            "stable_segment_key": row["stable_segment_key"],
            "source_path": row["source_path"],
            "text_layer": row["text_layer"],
            "chunk_type": row["chunk_type"],
            "length_bucket": row["length_bucket"],
            "source_text_only_tokens": row["source_text_only_tokens"],
            "prompt_v1_with_source_tokens": row["prompt_v1_with_source_tokens"],
            "prompt_v1_overhead_tokens": row["prompt_v1_overhead_tokens"],
        }
        for row in ranked[:limit]
    ]


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Measure Gemini countTokens overhead for Korean Advanced Prompt v1."
    )
    parser.add_argument("--samples", required=True)
    parser.add_argument("--model", required=True)
    parser.add_argument("--out", required=True)
    parser.add_argument("--sample-set", default=DEFAULT_SAMPLE_SET)
    parser.add_argument("--max-samples", type=int)
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--pretty", action="store_true")
    parser.add_argument("--timeout-seconds", type=int, default=60)
    parser.add_argument("--max-retries", type=int, default=2)
    parser.add_argument("--retry-backoff-seconds", type=float, default=2.0)
    args = parser.parse_args()

    try:
        report = calibrate_prompt_v1_tokens(
            samples_path=args.samples,
            model=args.model,
            out_path=args.out,
            sample_set=args.sample_set,
            max_samples=args.max_samples,
            dry_run=args.dry_run,
            timeout_seconds=args.timeout_seconds,
            max_retries=args.max_retries,
            retry_backoff_seconds=args.retry_backoff_seconds,
            pretty=args.pretty,
        )
    except RuntimeError as exc:
        print(str(exc), file=sys.stderr)
        raise SystemExit(2) from exc

    print(
        json.dumps(
            {
                "out": args.out,
                "dry_run": report["dry_run"],
                "sample_size": report["sample_size"],
                "successful_sample_count": report["successful_sample_count"],
                "failed_sample_count": report["failed_sample_count"],
                "source_text_only_total": report["source_text_only_total"],
                "prompt_v1_with_source_total": report["prompt_v1_with_source_total"],
                "average_prompt_v1_overhead_tokens": report[
                    "average_prompt_v1_overhead_tokens"
                ],
                "median_prompt_v1_overhead_tokens": report[
                    "median_prompt_v1_overhead_tokens"
                ],
                "p90_prompt_v1_overhead_tokens": report[
                    "p90_prompt_v1_overhead_tokens"
                ],
            },
            ensure_ascii=False,
            indent=2 if args.pretty else None,
        )
    )


if __name__ == "__main__":
    main()

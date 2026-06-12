"""Run Gemini countTokens calibration for VRI translation samples.

This script never calls text-generation APIs. It only calls Gemini countTokens
when --dry-run is not set.
"""

from __future__ import annotations

import argparse
import json
import os
import statistics
import sys
import time
from collections import Counter, defaultdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Protocol

REPO_ROOT = Path(__file__).resolve().parents[3]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))


CALIBRATION_PROMPT_TEMPLATE = """You are translating Pāli Buddhist canonical and commentarial texts into Korean.

Return a JSON object matching the Korean Advanced schema:
{{
  "literal_ko": "...",
  "natural_ko": "...",
  "terms": [],
  "grammar_notes": [],
  "doctrinal_notes": [],
  "uncertainties": [],
  "quality_flags": []
}}

Do not add fields outside the schema.

Pāli source:
<<<
{source_text}
>>>
"""

GEMINI_API_KEY_ENV_CANDIDATES = (
    "GEMINI_API_KEY",
    "GOOGLE_API_KEY",
    "GOOGLE_GENAI_API_KEY",
    "PALI_GEMINI_API_KEY",
)


class CountTokensClient(Protocol):
    def count_tokens(self, model: str, contents: str) -> int:
        """Return official provider token count for contents."""


class GeminiCountTokensClient:
    """Minimal Gemini client wrapper for countTokens only."""

    def __init__(self, *, api_key: str, timeout_seconds: int) -> None:
        from google import genai
        from google.genai import types

        self._client = genai.Client(
            api_key=api_key,
            http_options=types.HttpOptions(timeout=timeout_seconds * 1000),
        )

    def count_tokens(self, model: str, contents: str) -> int:
        response = self._client.models.count_tokens(model=model, contents=contents)
        token_count = getattr(response, "total_tokens", None)
        if token_count is None and hasattr(response, "model_dump"):
            token_count = response.model_dump().get("total_tokens")
        if token_count is None:
            raise RuntimeError("Gemini countTokens response did not include total_tokens")
        return int(token_count)


def build_calibration_prompt(source_text: str) -> str:
    return CALIBRATION_PROMPT_TEMPLATE.format(source_text=source_text)


def calibrate_gemini_tokens(
    *,
    samples_path: str | Path,
    model: str,
    out_path: str | Path,
    max_samples: int | None,
    dry_run: bool,
    timeout_seconds: int = 60,
    max_retries: int = 2,
    retry_backoff_seconds: float = 2.0,
    api_key: str | None = None,
    client: CountTokensClient | None = None,
    pretty: bool = False,
) -> dict[str, Any]:
    samples_file = Path(samples_path)
    samples_artifact = json.loads(samples_file.read_text(encoding="utf-8"))
    samples = select_calibration_samples(samples_artifact, max_samples=max_samples)

    if not dry_run and client is None:
        resolved_api_key = api_key or resolve_gemini_api_key()
        if not resolved_api_key:
            raise RuntimeError(
                "A Gemini API key is required for Gemini countTokens calibration. "
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
        result = build_base_sample_result(sample)
        if dry_run:
            result.update(
                {
                    "official_source_text_only_tokens": None,
                    "official_prompt_with_source_tokens": None,
                    "source_ratio": None,
                    "prompt_overhead_tokens": None,
                    "status": "dry_run",
                    "error_message": None,
                }
            )
            results.append(result)
            continue

        source_text = sample_source_text(sample)
        prompt_text = build_calibration_prompt(source_text)
        try:
            official_source = count_with_retries(
                client=client,
                model=model,
                contents=source_text,
                max_retries=max_retries,
                retry_backoff_seconds=retry_backoff_seconds,
            )
            official_prompt = count_with_retries(
                client=client,
                model=model,
                contents=prompt_text,
                max_retries=max_retries,
                retry_backoff_seconds=retry_backoff_seconds,
            )
            local_estimate = result["local_gemini_estimate_tokens"]
            result.update(
                {
                    "official_source_text_only_tokens": official_source,
                    "official_prompt_with_source_tokens": official_prompt,
                    "source_ratio": safe_ratio(official_source, local_estimate),
                    "prompt_overhead_tokens": official_prompt - official_source,
                    "status": "success",
                    "error_message": None,
                }
            )
        except Exception as exc:  # provider failures should not stop the batch
            result.update(
                {
                    "official_source_text_only_tokens": None,
                    "official_prompt_with_source_tokens": None,
                    "source_ratio": None,
                    "prompt_overhead_tokens": None,
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

    report = build_report(
        samples_artifact=samples_artifact,
        input_samples_path=str(samples_file),
        model=model,
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


def select_calibration_samples(
    samples_artifact: dict[str, Any],
    *,
    max_samples: int | None,
) -> list[dict[str, Any]]:
    samples = list(samples_artifact.get("calibration_samples") or [])
    if max_samples is None or max_samples >= len(samples):
        return samples
    return balanced_sample_subset(samples, max(0, max_samples))


def balanced_sample_subset(samples: list[dict[str, Any]], target_size: int) -> list[dict[str, Any]]:
    if target_size <= 0:
        return []
    grouped: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for sample in samples:
        grouped[str(sample.get("text_layer") or "unknown")].append(sample)

    groups = sorted(grouped)
    quotas = distribute_quota(target_size, groups)
    selected: list[dict[str, Any]] = []
    selected_keys: set[str] = set()
    for group in groups:
        for sample in take_evenly(grouped[group], quotas[group]):
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


def resolve_gemini_api_key() -> str | None:
    for name in GEMINI_API_KEY_ENV_CANDIDATES:
        value = os.getenv(name)
        if value:
            return value

    for env_file in (REPO_ROOT / ".env", REPO_ROOT / "config" / ".env"):
        value = read_api_key_from_env_file(env_file)
        if value:
            return value
    return None


def read_api_key_from_env_file(env_file: Path) -> str | None:
    if not env_file.exists():
        return None
    for raw_line in env_file.read_text(encoding="utf-8", errors="ignore").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        name, value = line.split("=", 1)
        if name.strip() not in GEMINI_API_KEY_ENV_CANDIDATES:
            continue
        cleaned = value.strip().strip('"').strip("'")
        if cleaned:
            return cleaned
    return None


def distribute_quota(target_size: int, groups: list[str]) -> dict[str, int]:
    if not groups:
        return {}
    base = target_size // len(groups)
    remainder = target_size % len(groups)
    return {
        group: base + (1 if index < remainder else 0)
        for index, group in enumerate(groups)
    }


def take_evenly(items: list[dict[str, Any]], count: int) -> list[dict[str, Any]]:
    if count <= 0:
        return []
    if count >= len(items):
        return list(items)
    if count == 1:
        return [items[0]]
    indexes = {
        round(index * (len(items) - 1) / (count - 1))
        for index in range(count)
    }
    return [items[index] for index in sorted(indexes)]


def sample_source_text(sample: dict[str, Any]) -> str:
    return sample.get("normalized_text") or sample.get("original_text") or ""


def build_base_sample_result(sample: dict[str, Any]) -> dict[str, Any]:
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


def local_gemini_estimate(sample: dict[str, Any]) -> int:
    estimates = sample.get("token_estimates_by_profile") or {}
    if "gemini_local_approx" in estimates:
        return int(estimates["gemini_local_approx"] or 0)
    for key, value in estimates.items():
        if "gemini" in key:
            return int(value or 0)
    return 0


def count_with_retries(
    *,
    client: CountTokensClient | None,
    model: str,
    contents: str,
    max_retries: int,
    retry_backoff_seconds: float,
) -> int:
    if client is None:
        raise RuntimeError("countTokens client was not initialized")

    attempts = max(0, max_retries) + 1
    last_error: Exception | None = None
    for attempt in range(attempts):
        try:
            return client.count_tokens(model, contents)
        except Exception as exc:
            last_error = exc
            if attempt >= attempts - 1:
                break
            time.sleep(retry_backoff_seconds * (2 ** attempt))
    raise RuntimeError(f"Gemini countTokens failed after {attempts} attempts: {last_error}")


def build_report(
    *,
    samples_artifact: dict[str, Any],
    input_samples_path: str,
    model: str,
    dry_run: bool,
    timeout_seconds: int,
    max_retries: int,
    retry_backoff_seconds: float,
    results: list[dict[str, Any]],
    failed_samples: list[dict[str, Any]],
) -> dict[str, Any]:
    successful = [row for row in results if row["status"] == "success"]
    dry_rows = [row for row in results if row["status"] == "dry_run"]
    local_total = sum(row["local_gemini_estimate_tokens"] for row in results)
    local_success_total = sum(row["local_gemini_estimate_tokens"] for row in successful)
    official_source_total = sum(row["official_source_text_only_tokens"] for row in successful)
    official_prompt_total = sum(row["official_prompt_with_source_tokens"] for row in successful)
    prompt_overheads = [
        row["prompt_overhead_tokens"]
        for row in successful
        if row["prompt_overhead_tokens"] is not None
    ]

    warnings = build_warnings(dry_run=dry_run, successful=successful, results=results)
    source_commit = samples_artifact.get("source_commit")
    sample_strategy = {
        "source_artifact_parameters": samples_artifact.get("parameters", {}),
        "selector_candidate_pool_report": samples_artifact.get("candidate_pool_report", {}),
        "calibration_scope": "calibration_samples",
    }

    return {
        "source_commit": source_commit,
        "model": model,
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "sample_size": len(results),
        "successful_sample_count": len(successful),
        "failed_sample_count": len(failed_samples),
        "sample_strategy": sample_strategy,
        "dry_run": dry_run,
        "input_samples_path": input_samples_path,
        "api_used": None if dry_run else "gemini.countTokens",
        "execution": {
            "timeout_seconds": timeout_seconds,
            "max_retries": max_retries,
            "retry_backoff_seconds": retry_backoff_seconds,
        },
        "prompt_wrapper": {
            "name": "korean_advanced_calibration_placeholder",
            "version": "placeholder-2026-06-10",
            "is_final_translation_prompt": False,
            "must_recalibrate_after_korean_advanced_prompt_v1": True,
            "preview": build_calibration_prompt("{source_text}"),
        },
        "aggregate_totals": {
            "local_estimate_total": local_total,
            "local_estimate_success_total": local_success_total if successful else None,
            "official_source_text_only_total": official_source_total if successful else None,
            "official_prompt_with_source_total": official_prompt_total if successful else None,
            "recommended_source_correction_factor": {
                "overall": safe_ratio(official_source_total, local_success_total) if successful else None,
                "by_text_layer": correction_by_group(successful, "text_layer"),
            },
            "average_prompt_overhead_tokens": mean_or_none(prompt_overheads),
            "median_prompt_overhead_tokens": median_or_none(prompt_overheads),
            "p90_prompt_overhead_tokens": percentile_or_none(prompt_overheads, 90),
        },
        "breakdowns": {
            "ratio_by_text_layer": ratio_by_group(successful, "text_layer"),
            "ratio_by_chunk_type": ratio_by_group(successful, "chunk_type"),
            "ratio_by_length_bucket": ratio_by_group(successful, "length_bucket"),
            "ratio_by_pitaka": ratio_by_group(successful, "pitaka"),
            "ratio_by_nikaya": ratio_by_group(successful, "nikaya"),
            "sample_distribution": sample_distribution(results or dry_rows),
        },
        "diagnostics": {
            "largest_ratio_outliers": largest_ratio_outliers(successful),
            "largest_prompt_overhead_samples": largest_prompt_overhead_samples(successful),
            "failed_samples": failed_samples,
            "warnings": warnings,
            "fallback_notes": [
                "local_gemini_estimate_tokens is the local Gemini heuristic fallback estimate.",
                "official_source_text_only_tokens comes from Gemini countTokens only when dry_run=false.",
                "recommended_source_correction_factor is a sample-based calibration factor, not a final cost estimate.",
                "prompt_with_source counts use a placeholder Korean Advanced prompt and must be rerun after Prompt v1 is finalized.",
            ],
        },
        "sample_results": results,
    }


def build_warnings(
    *,
    dry_run: bool,
    successful: list[dict[str, Any]],
    results: list[dict[str, Any]],
) -> list[str]:
    warnings: list[str] = []
    if dry_run:
        warnings.append("Dry-run mode: no Gemini API calls were made.")
    if not successful and not dry_run:
        warnings.append("No successful countTokens results were produced.")
    if any(row["local_gemini_estimate_tokens"] == 0 for row in results):
        warnings.append("Some samples have zero local Gemini estimate; source_ratio is null for those samples.")
    return warnings


def ratio_by_group(rows: list[dict[str, Any]], field: str) -> dict[str, Any]:
    grouped: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for row in rows:
        grouped[str(row.get(field) or "unknown")].append(row)
    return {
        key: ratio_summary(group_rows)
        for key, group_rows in sorted(grouped.items())
    }


def correction_by_group(rows: list[dict[str, Any]], field: str) -> dict[str, float | None]:
    return {
        key: summary["ratio"]
        for key, summary in ratio_by_group(rows, field).items()
    }


def ratio_summary(rows: list[dict[str, Any]]) -> dict[str, Any]:
    local_total = sum(row["local_gemini_estimate_tokens"] for row in rows)
    official_total = sum(row["official_source_text_only_tokens"] or 0 for row in rows)
    ratios = [row["source_ratio"] for row in rows if row["source_ratio"] is not None]
    return {
        "sample_count": len(rows),
        "local_estimate_total": local_total,
        "official_source_text_only_total": official_total,
        "ratio": safe_ratio(official_total, local_total),
        "average_sample_ratio": mean_or_none(ratios),
        "median_sample_ratio": median_or_none(ratios),
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


def largest_ratio_outliers(rows: list[dict[str, Any]], limit: int = 10) -> list[dict[str, Any]]:
    valid = [row for row in rows if row["source_ratio"] is not None]
    if not valid:
        return []
    overall = safe_ratio(
        sum(row["official_source_text_only_tokens"] for row in valid),
        sum(row["local_gemini_estimate_tokens"] for row in valid),
    )
    if overall is None:
        return []
    ranked = sorted(valid, key=lambda row: abs(row["source_ratio"] - overall), reverse=True)
    return [diagnostic_sample(row) for row in ranked[:limit]]


def largest_prompt_overhead_samples(rows: list[dict[str, Any]], limit: int = 10) -> list[dict[str, Any]]:
    ranked = sorted(
        [row for row in rows if row["prompt_overhead_tokens"] is not None],
        key=lambda row: row["prompt_overhead_tokens"],
        reverse=True,
    )
    return [diagnostic_sample(row) for row in ranked[:limit]]


def diagnostic_sample(row: dict[str, Any]) -> dict[str, Any]:
    return {
        "stable_segment_key": row["stable_segment_key"],
        "source_path": row["source_path"],
        "text_layer": row["text_layer"],
        "chunk_type": row["chunk_type"],
        "length_bucket": row["length_bucket"],
        "local_gemini_estimate_tokens": row["local_gemini_estimate_tokens"],
        "official_source_text_only_tokens": row["official_source_text_only_tokens"],
        "source_ratio": row["source_ratio"],
        "prompt_overhead_tokens": row["prompt_overhead_tokens"],
    }


def safe_ratio(numerator: int | float | None, denominator: int | float | None) -> float | None:
    if numerator is None or denominator in (None, 0):
        return None
    return round(float(numerator) / float(denominator), 6)


def mean_or_none(values: list[int | float]) -> float | None:
    if not values:
        return None
    return round(statistics.mean(values), 6)


def median_or_none(values: list[int | float]) -> float | None:
    if not values:
        return None
    return round(statistics.median(values), 6)


def percentile_or_none(values: list[int | float], pct: int) -> float | None:
    if not values:
        return None
    sorted_values = sorted(values)
    index = round((pct / 100) * (len(sorted_values) - 1))
    return float(sorted_values[max(0, min(index, len(sorted_values) - 1))])


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Calibrate local Gemini token estimates with Gemini countTokens."
    )
    parser.add_argument("--samples", required=True)
    parser.add_argument("--model", required=True)
    parser.add_argument("--out", required=True)
    parser.add_argument("--max-samples", type=int)
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--pretty", action="store_true")
    parser.add_argument("--timeout-seconds", type=int, default=60)
    parser.add_argument("--max-retries", type=int, default=2)
    parser.add_argument("--retry-backoff-seconds", type=float, default=2.0)
    args = parser.parse_args()

    try:
        report = calibrate_gemini_tokens(
            samples_path=args.samples,
            model=args.model,
            out_path=args.out,
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

    if args.pretty:
        print(
            json.dumps(
                {
                    "out": args.out,
                    "dry_run": report["dry_run"],
                    "sample_size": report["sample_size"],
                    "successful_sample_count": report["successful_sample_count"],
                    "failed_sample_count": report["failed_sample_count"],
                    "recommended_source_correction_factor": report["aggregate_totals"][
                        "recommended_source_correction_factor"
                    ],
                    "average_prompt_overhead_tokens": report["aggregate_totals"][
                        "average_prompt_overhead_tokens"
                    ],
                },
                ensure_ascii=False,
                indent=2,
            )
        )


if __name__ == "__main__":
    main()

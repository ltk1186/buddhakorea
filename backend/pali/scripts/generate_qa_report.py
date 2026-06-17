"""Generate deterministic local QA reports for Pali translation runs.

This CLI is local-only. It does not modify prompts, call Gemini/GPT/LLM
providers, write to a database, run RAG, or perform live oracle checks.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import random
import sys
from pathlib import Path
from typing import Any

from backend.pali.translation.gold_set import (
    build_gold_regression_report,
    evaluate_against_gold,
    load_gold_set,
)
from backend.pali.translation.reference_registry import (
    load_parallel_registry,
    validate_reference_entry,
)
from backend.pali.translation.review_queue import build_review_queue
from backend.pali.translation.second_model_verifier import classify_oracle_availability
from backend.pali.translation.source_integrity import check_integrity


SCRIPT_VERSION = "qa_report_generator_v1_2"
QA_INFRA_VERSION = "pali_qa_infra_v1_2"
BASELINE_PROMPT_VERSION = "korean_advanced_v1_schemafix_qa_patch_v2"
DEFAULT_BUCKET_SIZE = 5


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    result = generate_report(args)
    print(json.dumps(result, ensure_ascii=False, sort_keys=True))
    return 0


def build_parser() -> argparse.ArgumentParser:
    examples = """Examples:
  75 baseline single-run:
    ./venv/bin/python -m backend.pali.scripts.generate_qa_report \\
      --parsed data/reports/pali/gemini_pilot_75_49bc869_prompt_qa_patch_v2_parsed.json \\
      --gold data/gold_set.json \\
      --glossary-qa data/reports/pali/translation_qa_v1_1_baseline_49bc869.json \\
      --out data/reports/pali/qa_report_v1_2_pilot75

  before/after regression:
    ./venv/bin/python -m backend.pali.scripts.generate_qa_report \\
      --before-parsed data/reports/pali/gemini_pilot_75_49bc869_prompt_v1_schemafix_parsed.json \\
      --parsed data/reports/pali/gemini_pilot_75_49bc869_prompt_qa_patch_v2_parsed.json \\
      --gold data/gold_set.json \\
      --glossary-qa data/reports/pali/translation_qa_v1_1_baseline_49bc869.json \\
      --out data/reports/pali/qa_report_v1_2_regression

  300 pilot template:
    ./venv/bin/python -m backend.pali.scripts.generate_qa_report \\
      --parsed <300_pilot_parsed.json> \\
      --gold data/gold_set.json \\
      --glossary-qa <300_qa_report.json> \\
      --out data/reports/pali/qa_report_300_<run_id>
"""
    parser = argparse.ArgumentParser(
        description="Generate local deterministic QA report artifacts.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=examples,
    )
    parser.add_argument("--parsed", required=True, help="Current/after parsed result JSON path.")
    parser.add_argument("--before-parsed", help="Optional before parsed result JSON path for regression mode.")
    parser.add_argument("--gold", required=True, help="Gold set JSON path.")
    parser.add_argument("--glossary-qa", required=True, help="Glossary QA report JSON path.")
    parser.add_argument("--reference-registry", help="Optional parallel reference registry JSON path.")
    parser.add_argument("--out", required=True, help="Output directory.")
    parser.add_argument("--sample-config", help="Optional sample config JSON path.")
    parser.add_argument("--sample-seed", help="Optional deterministic sample seed string or integer.")
    return parser


def generate_report(args: argparse.Namespace) -> dict[str, Any]:
    parsed_path = Path(args.parsed)
    before_path = Path(args.before_parsed) if args.before_parsed else None
    gold_path = Path(args.gold)
    glossary_qa_path = Path(args.glossary_qa)
    out_dir = Path(args.out)
    out_dir.mkdir(parents=True, exist_ok=True)

    parsed_payload = _read_json(parsed_path)
    before_payload = _read_json(before_path) if before_path else None
    gold_set = load_gold_set(gold_path)
    glossary_qa_payload = _read_json(glossary_qa_path)
    selected_glossary_qa = _select_glossary_qa(glossary_qa_payload, parsed_path)
    reference_registry = _load_optional_registry(args.reference_registry)
    sample_config = _load_optional_json(args.sample_config)
    mode = "regression" if before_payload is not None else "single_run"

    parsed_items = _segments(parsed_payload)
    before_items = _segments(before_payload) if before_payload else []
    sample_keys = _sample_seed_keys(parsed_items, before_items, mode)
    sample_seed = _resolve_sample_seed(args.sample_seed, sample_keys)
    rng = random.Random(sample_seed)

    gold_current = _evaluate_gold_current(parsed_payload, gold_set)
    gold_regression = None
    if before_payload is not None:
        gold_regression = build_gold_regression_report(before_payload, parsed_payload, gold_set)

    queue_input = dict(selected_glossary_qa)
    if gold_regression:
        queue_input["gold_regression"] = gold_regression.get("results", [])
    review_queue = _augment_review_queue(build_review_queue(parsed_payload, queue_input))
    source_integrity = _source_integrity_summary(parsed_items)
    oracle_summary = _oracle_availability_summary(parsed_items, reference_registry)
    representative_samples = _representative_samples(
        parsed_items,
        rng=rng,
        bucket_size=int(sample_config.get("bucket_size", DEFAULT_BUCKET_SIZE)),
    )
    run_summary = _run_summary(parsed_items)

    review_queue_path = out_dir / "review_queue.json"
    review_report_path = out_dir / "review_report.md"
    run_manifest_path = out_dir / "run_manifest.json"

    review_queue_payload = {
        "schema_version": "pali_review_queue_v1_2",
        "mode": mode,
        "summary": {
            "total_raw_candidates": review_queue["total_raw_candidates"],
            "deduped_item_count": review_queue["deduped_item_count"],
            "priority_counts": review_queue["priority_counts"],
            "auto_resolvable_count": review_queue["auto_resolvable_count"],
            "human_needed_count": review_queue["human_needed_count"],
            "estimated_review_minutes_total": sum(
                int(item.get("estimated_review_minutes", 0)) for item in review_queue["human_needed"]
            ),
        },
        "items": review_queue["items"],
        "auto_resolvable": review_queue["auto_resolvable"],
        "human_needed": review_queue["human_needed"],
        "representative_samples": representative_samples,
        "oracle_availability": oracle_summary,
        "gold_current": gold_current,
        "gold_regression": gold_regression,
        "source_integrity": source_integrity,
    }
    _write_json(review_queue_path, review_queue_payload)

    manifest = _manifest(
        args=args,
        mode=mode,
        output_paths={
            "review_queue": str(review_queue_path),
            "review_report": str(review_report_path),
            "run_manifest": str(run_manifest_path),
        },
        sample_seed=sample_seed,
        input_paths=[path for path in [parsed_path, before_path, gold_path, glossary_qa_path] if path],
        optional_reference_registry=args.reference_registry,
        gold_set=gold_set,
    )
    _write_json(run_manifest_path, manifest)

    review_report = _render_markdown_report(
        mode=mode,
        run_summary=run_summary,
        review_queue=review_queue_payload,
        gold_current=gold_current,
        gold_regression=gold_regression,
        source_integrity=source_integrity,
        oracle_summary=oracle_summary,
        representative_samples=representative_samples,
        manifest_path=run_manifest_path,
    )
    review_report_path.write_text(review_report, encoding="utf-8")

    return {
        "mode": mode,
        "out": str(out_dir),
        "review_queue": str(review_queue_path),
        "review_report": str(review_report_path),
        "run_manifest": str(run_manifest_path),
        "sample_seed": sample_seed,
    }


def _read_json(path: Path | None) -> dict[str, Any]:
    if path is None:
        return {}
    return json.loads(path.read_text(encoding="utf-8"))


def _load_optional_json(path: str | None) -> dict[str, Any]:
    if not path:
        return {}
    return _read_json(Path(path))


def _load_optional_registry(path: str | None) -> dict[str, Any] | None:
    if not path:
        return None
    registry = load_parallel_registry(path)
    entries = registry.get("entries", []) if isinstance(registry, dict) else []
    validation = [validate_reference_entry(entry) for entry in entries if isinstance(entry, dict)]
    registry["_validation_summary"] = {
        "entry_count": len(validation),
        "valid_count": sum(1 for item in validation if item["valid"]),
        "invalid_count": sum(1 for item in validation if not item["valid"]),
    }
    return registry


def _select_glossary_qa(payload: dict[str, Any], parsed_path: Path) -> dict[str, Any]:
    reports = payload.get("reports")
    if not isinstance(reports, dict):
        return payload
    name = parsed_path.name
    if "qa_patch_v2" in name and isinstance(reports.get("qa_patch_v2"), dict):
        return reports["qa_patch_v2"]
    if "schemafix" in name and isinstance(reports.get("schemafix"), dict):
        return reports["schemafix"]
    if len(reports) == 1:
        value = next(iter(reports.values()))
        return value if isinstance(value, dict) else {}
    return {}


def _segments(payload: dict[str, Any] | None) -> list[dict[str, Any]]:
    if not payload:
        return []
    return [item for item in payload.get("items", []) if isinstance(item, dict)]


def _sample_seed_keys(after_items: list[dict[str, Any]], before_items: list[dict[str, Any]], mode: str) -> list[str]:
    after_keys = {str(item.get("stable_segment_key")) for item in after_items if item.get("stable_segment_key")}
    if mode == "single_run":
        return sorted(after_keys)
    before_keys = {str(item.get("stable_segment_key")) for item in before_items if item.get("stable_segment_key")}
    return sorted(after_keys & before_keys)


def _resolve_sample_seed(user_seed: str | None, keys: list[str]) -> int:
    if user_seed is not None:
        if str(user_seed).isdigit():
            return int(str(user_seed)) % (2**32)
        digest = hashlib.sha256(str(user_seed).encode("utf-8")).hexdigest()
        return int(digest, 16) % (2**32)
    joined = "\n".join(sorted(keys))
    digest = hashlib.sha256(joined.encode("utf-8")).hexdigest()
    return int(digest, 16) % (2**32)


def _evaluate_gold_current(payload: dict[str, Any], gold_set: dict[str, Any]) -> dict[str, Any]:
    by_key = {str(item.get("stable_segment_key")): item for item in _segments(payload)}
    pools = {pool: {"pass": 0, "fail": 0, "escalate": 0, "items": []} for pool in ("discovery", "regression_gold", "holdout_gold")}
    for entry in gold_set.get("entries", []) or []:
        if not isinstance(entry, dict):
            continue
        pool = str(entry.get("pool", "discovery"))
        pools.setdefault(pool, {"pass": 0, "fail": 0, "escalate": 0, "items": []})
        result = evaluate_against_gold(by_key.get(str(entry.get("stable_segment_key"))), entry)
        if result["pass"] is True:
            bucket = "pass"
        elif result["pass"] is False and result["auto_evaluable"]:
            bucket = "fail"
        else:
            bucket = "escalate"
        pools[pool][bucket] += 1
        pools[pool]["items"].append(
            {
                "gold_set_id": entry.get("gold_set_id", ""),
                "stable_segment_key": entry.get("stable_segment_key", ""),
                "pool": pool,
                "result": bucket,
                "evaluation": result,
            }
        )
    return {
        "holdout_correctness": pools.get("holdout_gold", {"pass": 0, "fail": 0, "escalate": 0, "items": []}),
        "regression_canary": pools.get("regression_gold", {"pass": 0, "fail": 0, "escalate": 0, "items": []}),
        "discovery": pools.get("discovery", {"pass": 0, "fail": 0, "escalate": 0, "items": []}),
        "note": "Holdout correctness and regression canary are intentionally separate and must not be combined.",
    }


def _augment_review_queue(queue: dict[str, Any]) -> dict[str, Any]:
    for group_name in ("items", "auto_resolvable", "human_needed"):
        for item in queue.get(group_name, []) or []:
            signals = list(item.get("signals", []))
            item.setdefault("evidence", _evidence_for_item(item))
            item.setdefault("suggested_action", _suggested_action(signals))
    return queue


def _evidence_for_item(item: dict[str, Any]) -> dict[str, Any]:
    return {
        "signals": item.get("signals", []),
        "example_stable_segment_keys": item.get("example_stable_segment_keys", []),
        "source_path": item.get("source_path", ""),
        "text_layer": item.get("text_layer", ""),
        "chunk_type": item.get("chunk_type", ""),
    }


def _suggested_action(signals: list[str]) -> str:
    signal_set = set(signals)
    if "gold_regression_worsened" in signal_set:
        return "review_gold_regression_before_next_pilot"
    if "possible_true_untranslated_pali" in signal_set:
        return "operator_review_untranslated_pali_candidate"
    if "second_model_disagreement" in signal_set:
        return "triage_only_not_error_proof"
    if {"source_hash_mismatch", "silent_source_normalization", "raw_source_hash_mismatch", "normalized_source_hash_mismatch"} & signal_set:
        return "source_integrity_operator_review"
    if signal_set <= {"allowed_parenthetical_pali", "allowed_bracketed_pali", "allowed_text_title", "allowed_person_name", "allowed_citation_abbreviation", "allowed_technical_term"}:
        return "deterministic_validator_or_whitelist_update_candidate"
    if "reference_only_gold" in signal_set:
        return "manual_reference_or_expert_review_if_high_leverage"
    return "human_review"


def _source_integrity_summary(items: list[dict[str, Any]]) -> dict[str, Any]:
    checks = [check_integrity(item, mode="legacy") for item in items]
    return {
        "item_count": len(items),
        "valid_count": sum(1 for item in checks if item.get("valid")),
        "invalid_count": sum(1 for item in checks if not item.get("valid")),
        "gap_counts": _count_values(checks, "gaps"),
        "flag_counts": _count_values(checks, "flags"),
        "sample_gaps": checks[:5],
    }


def _oracle_availability_summary(items: list[dict[str, Any]], registry: dict[str, Any] | None) -> dict[str, Any]:
    rows = []
    counts: dict[str, int] = {}
    for item in items:
        status = classify_oracle_availability(item, registry)
        counts[status] = counts.get(status, 0) + 1
        rows.append(
            {
                "stable_segment_key": item.get("stable_segment_key", ""),
                "source_path": item.get("source_path", ""),
                "text_layer": item.get("text_layer", ""),
                "oracle_availability": status,
            }
        )
    return {
        "registry_provided": registry is not None,
        "counts": dict(sorted(counts.items())),
        "items": rows,
        "policy": [
            "oracle agreement is not proof of correctness",
            "oracle disagreement is not proof of mistranslation",
            "oracle disagreement escalates to review queue only",
            "live oracle calls are disabled in this stage",
        ],
    }


def _representative_samples(items: list[dict[str, Any]], *, rng: random.Random, bucket_size: int) -> dict[str, list[dict[str, str]]]:
    buckets = {
        "random": items,
        "long": [item for item in items if item.get("length_bucket") == "long"],
        "verse": [item for item in items if item.get("chunk_type") == "verse"],
        "tika": [item for item in items if item.get("text_layer") == "tika"],
        "title": [item for item in items if item.get("chunk_type") in {"heading", "title"}],
        "citation_heavy": [item for item in items if _looks_citation_heavy(str(item.get("original_text", "")))],
    }
    result = {}
    for name, bucket_items in buckets.items():
        sorted_items = sorted(bucket_items, key=lambda item: str(item.get("stable_segment_key", "")))
        if len(sorted_items) > bucket_size:
            chosen = rng.sample(sorted_items, bucket_size)
            chosen.sort(key=lambda item: str(item.get("stable_segment_key", "")))
        else:
            chosen = sorted_items
        result[name] = [_sample_row(item) for item in chosen]
    return result


def _looks_citation_heavy(text: str) -> bool:
    markers = ("dī. ni.", "ma. ni.", "saṃ. ni.", "aṅ. ni.", "jā.", "visuddhi.", "aṭṭha.", "ṭī.")
    return sum(text.count(marker) for marker in markers) >= 1


def _sample_row(item: dict[str, Any]) -> dict[str, str]:
    return {
        "stable_segment_key": str(item.get("stable_segment_key", "")),
        "source_path": str(item.get("source_path", "")),
        "text_layer": str(item.get("text_layer", "")),
        "chunk_type": str(item.get("chunk_type", "")),
        "length_bucket": str(item.get("length_bucket", "")),
    }


def _run_summary(items: list[dict[str, Any]]) -> dict[str, Any]:
    return {
        "total_segments": len(items),
        "schema_valid_count": sum(1 for item in items if item.get("schema_valid") is True),
        "schema_invalid_count": sum(1 for item in items if item.get("schema_valid") is False),
        "parse_failed_count": sum(1 for item in items if item.get("status") == "parse_failed"),
    }


def _render_markdown_report(
    *,
    mode: str,
    run_summary: dict[str, Any],
    review_queue: dict[str, Any],
    gold_current: dict[str, Any],
    gold_regression: dict[str, Any] | None,
    source_integrity: dict[str, Any],
    oracle_summary: dict[str, Any],
    representative_samples: dict[str, list[dict[str, str]]],
    manifest_path: Path,
) -> str:
    queue_summary = review_queue["summary"]
    lines = [
        "# Pāli QA Review Report v1.2",
        "",
        "이 보고서는 local-only deterministic QA 산출물입니다. Prompt/API/DB/RAG/UI 작업을 수행하지 않았습니다.",
        "",
        "## Summary",
        "",
        f"- execution mode: `{mode}`",
        f"- regression mode: {'enabled' if mode == 'regression' else 'disabled'}",
        f"- total segments: {run_summary['total_segments']}",
        f"- schema valid / invalid: {run_summary['schema_valid_count']} / {run_summary['schema_invalid_count']}",
        f"- parse failed: {run_summary['parse_failed_count']}",
        f"- Priority counts: {queue_summary['priority_counts']}",
        f"- auto-resolvable groups: {queue_summary['auto_resolvable_count']}",
        f"- human-needed groups: {queue_summary['human_needed_count']}",
        f"- estimated human review minutes: {queue_summary['estimated_review_minutes_total']}",
        f"- source integrity gaps: {source_integrity['gap_counts']}",
        f"- oracle availability: {oracle_summary['counts']}",
        f"- run manifest: `{manifest_path}`",
        "",
        "Oracle 일치 = 정답 확정이 아니며, oracle 불일치 = 오역 확정이 아닙니다. 불일치는 review queue로 올리는 triage signal일 뿐입니다.",
        "",
        "## Auto-Resolvable Summary",
        "",
    ]
    auto_counts: dict[str, int] = {}
    for item in review_queue.get("auto_resolvable", []):
        for signal in item.get("signals", []):
            auto_counts[signal] = auto_counts.get(signal, 0) + int(item.get("recurrence_count", 1))
    if auto_counts:
        for signal, count in sorted(auto_counts.items()):
            lines.append(f"- {signal}: {count}")
    else:
        lines.append("- none")
    lines.extend(["", "## Human-Needed Queue", ""])
    human_items = review_queue.get("human_needed", [])
    if not human_items:
        lines.append("- none")
    for item in human_items:
        lines.extend(
            [
                f"### {item.get('priority')} · {item.get('dedup_group_key')}",
                "",
                f"- recurrence_count: {item.get('recurrence_count')}",
                f"- example stable_segment_keys: {item.get('example_stable_segment_keys', [])}",
                f"- signals: {item.get('signals', [])}",
                f"- suggested_action: {item.get('suggested_action')}",
                f"- estimated_review_minutes: {item.get('estimated_review_minutes')}",
                f"- review_tier: {item.get('review_tier')}",
                "",
            ]
        )

    lines.extend(["## Representative Sample Package", ""])
    for bucket, rows in representative_samples.items():
        lines.append(f"### {bucket}")
        if not rows:
            lines.append("- none")
        for row in rows:
            lines.append(
                f"- `{row['stable_segment_key']}` · {row['text_layer']} · {row['chunk_type']} · {row['length_bucket']}"
            )
        lines.append("")

    lines.extend(["## Gold Results", "", "### Holdout Correctness", ""])
    holdout = gold_current["holdout_correctness"]
    lines.append(
        f"- pass/fail/escalate: {holdout['pass']} / {holdout['fail']} / {holdout['escalate']}"
    )
    lines.append("- holdout_gold는 regression_gold와 합산하지 않습니다.")
    lines.extend(["", "### Regression Canary", ""])
    if gold_regression:
        lines.append(f"- verdict counts: {gold_regression.get('verdict_counts', {})}")
    else:
        canary = gold_current["regression_canary"]
        lines.append(
            f"- current pass/fail/escalate: {canary['pass']} / {canary['fail']} / {canary['escalate']}"
        )
        lines.append("- regression mode disabled: before/after verdict는 계산하지 않았습니다.")
    lines.append("")

    lines.extend(["## Correctness Triage Candidates", ""])
    for status, count in sorted(oracle_summary["counts"].items()):
        lines.append(f"- {status}: {count}")
    lines.extend(
        [
            "",
            "이번 단계에서는 CC0 parallel comparison, copyright eyes-only reference, second-model verifier live 호출을 실행하지 않습니다.",
            "aṭṭhakathā / ṭīkā는 제외하지 않고 `oracle_unavailable`로 표시합니다.",
            "",
        ]
    )
    return "\n".join(lines)


def _manifest(
    *,
    args: argparse.Namespace,
    mode: str,
    output_paths: dict[str, str],
    sample_seed: int,
    input_paths: list[Path],
    optional_reference_registry: str | None,
    gold_set: dict[str, Any],
) -> dict[str, Any]:
    input_hashes = {str(path): _file_sha256(path) for path in input_paths}
    if optional_reference_registry:
        input_hashes[optional_reference_registry] = _file_sha256(Path(optional_reference_registry))
    fingerprint = hashlib.sha256(json.dumps(input_hashes, sort_keys=True).encode("utf-8")).hexdigest()
    return {
        "schema_version": "pali_qa_run_manifest_v1_2",
        "script_version": SCRIPT_VERSION,
        "qa_infra_version": QA_INFRA_VERSION,
        "timestamp": "1970-01-01T00:00:00Z",
        "deterministic_input_fingerprint": fingerprint,
        "execution_mode": mode,
        "prompt_version": BASELINE_PROMPT_VERSION,
        "gold_set_version": gold_set.get("schema_version", ""),
        "glossary_version": "controlled_glossary_v1_or_report_input",
        "input_file_sha256": input_hashes,
        "output_paths": output_paths,
        "sample_seed": sample_seed,
        "command_line_args": _args_to_command(args),
    }


def _args_to_command(args: argparse.Namespace) -> list[str]:
    command = ["./venv/bin/python", "-m", "backend.pali.scripts.generate_qa_report"]
    for name in (
        "before_parsed",
        "parsed",
        "gold",
        "glossary_qa",
        "reference_registry",
        "out",
        "sample_config",
        "sample_seed",
    ):
        value = getattr(args, name, None)
        if value is None:
            continue
        command.extend([f"--{name.replace('_', '-')}", str(value)])
    return command


def _file_sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _write_json(path: Path, payload: dict[str, Any]) -> None:
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def _count_values(items: list[dict[str, Any]], field: str) -> dict[str, int]:
    counts: dict[str, int] = {}
    for item in items:
        for value in item.get(field, []) or []:
            value = str(value)
            counts[value] = counts.get(value, 0) + 1
    return dict(sorted(counts.items()))


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))

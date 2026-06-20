"""Classify Pali 300 QA findings into deterministic review sub-signals.

This CLI is local-only. It does not call Gemini, GPT, Claude, second-model
judges, or any network service, and it does not modify translations.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

REPO_ROOT = Path(__file__).resolve().parents[3]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from backend.pali.translation.pali_qa_findings_classifier import (
    classify_review_findings,
    pattern_decisions,
    reclassified_review_queue,
    render_findings_markdown,
)


SCRIPT_VERSION = "pali_qa_findings_classifier_cli_v1"


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    try:
        result = run(args)
    except RuntimeError as exc:
        print(json.dumps({"status": "ERROR", "message": str(exc)}, ensure_ascii=False, sort_keys=True), file=sys.stderr)
        return 2
    print(json.dumps(result, ensure_ascii=False, sort_keys=True))
    return 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Classify salvaged Pali 300 QA findings without API calls.")
    parser.add_argument("--review-queue", required=True)
    parser.add_argument("--review-report", required=True)
    parser.add_argument("--parsed", required=True)
    parser.add_argument("--out", required=True)
    parser.add_argument("--pretty", action="store_true")
    return parser


def run(args: argparse.Namespace) -> dict[str, Any]:
    review_queue_path = Path(args.review_queue)
    review_report_path = Path(args.review_report)
    parsed_path = Path(args.parsed)
    for path in [review_queue_path, review_report_path, parsed_path]:
        if not path.exists():
            raise RuntimeError(f"missing input file: {path}")
    out_dir = Path(args.out)
    out_dir.mkdir(parents=True, exist_ok=True)

    review_queue = read_json(review_queue_path)
    parsed_payload = read_json(parsed_path)
    sample_seed = read_sample_seed(review_queue_path.parent / "run_manifest.json")
    findings = classify_review_findings(
        review_queue=review_queue,
        parsed_payload=parsed_payload,
        review_report_path=str(review_report_path),
        review_queue_path=str(review_queue_path),
        parsed_path=str(parsed_path),
        sample_seed=sample_seed,
    )
    reclassified = reclassified_review_queue(review_queue, findings)
    decisions = pattern_decisions()
    manifest = run_manifest(args, out_dir, [review_queue_path, review_report_path, parsed_path])

    findings_path = out_dir / "findings.json"
    findings_md_path = out_dir / "findings.md"
    reclassified_path = out_dir / "review_queue_reclassified.json"
    manifest_path = out_dir / "run_manifest.json"
    decisions_path = out_dir / "pali_qa_pattern_decisions_v1.json"

    write_json(findings_path, findings, pretty=args.pretty)
    findings_md_path.write_text(render_findings_markdown(findings), encoding="utf-8")
    write_json(reclassified_path, reclassified, pretty=args.pretty)
    write_json(manifest_path, manifest, pretty=args.pretty)
    write_json(decisions_path, decisions, pretty=args.pretty)

    summary_after = findings["summary_after"]
    subsignals = findings["subsignal_counts"]
    coverage = findings["run_coverage_summary"]
    return {
        "status": "CLASSIFICATION_COMPLETE",
        "input_human_needed": findings["summary_before"]["human_needed"],
        "effective_human_needed": summary_after["human_needed_effective"],
        "auto_allowed": findings["sampling_recommendation"]["auto_allowed_count"],
        "possible_untranslated_pali_strict": subsignals["possible_untranslated_pali_strict"],
        "grammar_uncertain_auto_accepted": summary_after["grammar_uncertain_auto_accepted"],
        "grammar_uncertain_retained_for_review": subsignals["grammar_uncertain_retained"],
        "total_pali_runs_detected": coverage["total_pali_runs_detected"],
        "covered_pali_runs": coverage["covered_pali_runs"],
        "uncovered_pali_runs": coverage["uncovered_pali_runs"],
        "findings": str(findings_path),
        "findings_md": str(findings_md_path),
        "review_queue_reclassified": str(reclassified_path),
        "pattern_decisions": str(decisions_path),
        "run_manifest": str(manifest_path),
        "api_network_calls": 0,
    }


def read_sample_seed(path: Path) -> int | None:
    if not path.exists():
        return None
    try:
        value = read_json(path).get("sample_seed")
    except json.JSONDecodeError:
        return None
    if value is None:
        return None
    try:
        return int(value)
    except (TypeError, ValueError):
        return None


def run_manifest(args: argparse.Namespace, out_dir: Path, input_paths: list[Path]) -> dict[str, Any]:
    return {
        "schema_version": "pali_qa_findings_classifier_run_manifest_v1",
        "script_version": SCRIPT_VERSION,
        "created_at": datetime.now(timezone.utc).isoformat(),
        "api_network_calls": 0,
        "translation_mutation": False,
        "prompt_glossary_gold_mutation": False,
        "input_files": [file_record(path) for path in input_paths],
        "output_files": {
            "findings": str(out_dir / "findings.json"),
            "findings_md": str(out_dir / "findings.md"),
            "review_queue_reclassified": str(out_dir / "review_queue_reclassified.json"),
            "pattern_decisions": str(out_dir / "pali_qa_pattern_decisions_v1.json"),
            "run_manifest": str(out_dir / "run_manifest.json"),
        },
        "args": {
            "review_queue": args.review_queue,
            "review_report": args.review_report,
            "parsed": args.parsed,
            "out": args.out,
            "pretty": bool(args.pretty),
        },
    }


def read_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def write_json(path: Path, payload: Any, *, pretty: bool) -> None:
    path.write_text(
        json.dumps(payload, ensure_ascii=False, sort_keys=True, indent=2 if pretty else None) + "\n",
        encoding="utf-8",
    )


def file_record(path: Path) -> dict[str, Any]:
    return {
        "path": str(path),
        "sha256": hashlib.sha256(path.read_bytes()).hexdigest(),
        "exists": path.exists(),
    }


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))

"""Run Step 3G-A post-hoc review harvest for the Pali 300 pilot.

This CLI is local-only. It does not call Gemini, Batch, second-model judges,
or the network, and it does not modify translations, source XML, prompts,
glossary files, or gold-set decisions.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any

REPO_ROOT = Path(__file__).resolve().parents[3]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from backend.pali.translation.posthoc_review_harvest import run_posthoc_review_harvest


DEFAULT_REVIEW_QUEUE = "data/qa_reports/pali/qa_report_300_live_salvaged_integrated/review_queue_reclassified.json"
DEFAULT_FINDINGS = "data/qa_reports/pali/qa_report_300_live_salvaged_integrated/findings.json"
DEFAULT_PARSED = "data/reports/pali/pilot_300_batch/pilot_300_batch_parsed_salvaged.json"
DEFAULT_APPARATUS_CROSSCHECK = "data/qa_reports/pali/variant_apparatus_v0/apparatus_qa_crosscheck.json"
DEFAULT_VARIANT_APPARATUS = "data/qa_reports/pali/variant_apparatus_v0/variant_apparatus.json"
DEFAULT_PILOT_300_MANIFEST = "data/pilot_sets/pali/pilot_300_v1_manifest.json"
DEFAULT_GOLD_SET = "data/gold_set.json"
DEFAULT_SEED_DECISIONS = "data/review_seeds/pali/step_3g_remaining_seed_decisions.json"
DEFAULT_OUT = "data/qa_reports/pali/step_3g_posthoc_review_harvest"


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
    parser = argparse.ArgumentParser(description="Run Pali Step 3G-A post-hoc review harvest.")
    parser.add_argument("--review-queue-reclassified", default=DEFAULT_REVIEW_QUEUE)
    parser.add_argument("--findings", default=DEFAULT_FINDINGS)
    parser.add_argument("--parsed", default=DEFAULT_PARSED)
    parser.add_argument("--apparatus-crosscheck", default=DEFAULT_APPARATUS_CROSSCHECK)
    parser.add_argument("--variant-apparatus", default=DEFAULT_VARIANT_APPARATUS)
    parser.add_argument("--pilot-300-manifest", default=DEFAULT_PILOT_300_MANIFEST)
    parser.add_argument("--gold-set", default=DEFAULT_GOLD_SET)
    parser.add_argument("--seed-decisions", default=DEFAULT_SEED_DECISIONS)
    parser.add_argument("--out", default=DEFAULT_OUT)
    parser.add_argument("--pretty", action="store_true")
    return parser


def run(args: argparse.Namespace) -> dict[str, Any]:
    review_queue_path = Path(args.review_queue_reclassified)
    findings_path = Path(args.findings)
    parsed_path = Path(args.parsed)
    apparatus_crosscheck_path = Path(args.apparatus_crosscheck)
    variant_apparatus_path = Path(args.variant_apparatus)
    pilot_manifest_path = Path(args.pilot_300_manifest)
    gold_set_path = Path(args.gold_set)
    seed_decisions_path = Path(args.seed_decisions)
    out_dir = Path(args.out)

    required = {
        "review_queue_reclassified": review_queue_path,
        "findings": findings_path,
        "parsed": parsed_path,
        "pilot_300_manifest": pilot_manifest_path,
    }
    for label, path in required.items():
        if not path.exists():
            raise RuntimeError(f"missing required input {label}: {path}")

    input_paths = {
        "review_queue_reclassified": review_queue_path,
        "findings": findings_path,
        "parsed": parsed_path,
        "apparatus_crosscheck": apparatus_crosscheck_path,
        "variant_apparatus": variant_apparatus_path,
        "pilot_300_manifest": pilot_manifest_path,
        "gold_set": gold_set_path,
        "seed_decisions": seed_decisions_path,
    }

    return run_posthoc_review_harvest(
        review_queue_reclassified=read_json(review_queue_path),
        findings=read_json(findings_path),
        parsed_payload=read_json(parsed_path),
        apparatus_crosscheck=read_json(apparatus_crosscheck_path) if apparatus_crosscheck_path.exists() else None,
        variant_apparatus=read_json(variant_apparatus_path) if variant_apparatus_path.exists() else None,
        pilot_300_manifest=read_json(pilot_manifest_path),
        gold_set=read_json(gold_set_path) if gold_set_path.exists() else None,
        seed_decisions=read_json(seed_decisions_path) if seed_decisions_path.exists() else None,
        seed_decisions_path=seed_decisions_path,
        out_dir=out_dir,
        input_paths=input_paths,
        pretty=bool(args.pretty),
    )


def read_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))

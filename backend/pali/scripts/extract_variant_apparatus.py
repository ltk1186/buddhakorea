"""Extract VRI XML <note> apparatus for Pali 300 QA targets.

This CLI is local-only. It does not call Gemini, Batch, second-model judges,
or the network, and it does not modify source XML or translation artifacts.
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

from backend.pali.translation.variant_apparatus import (
    SCRIPT_VERSION,
    dump_json,
    output_record,
    render_findings_markdown,
    run_variant_apparatus_extraction,
)


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    result = run(args)
    print(json.dumps(result, ensure_ascii=False, sort_keys=True))
    return 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Extract local VRI XML note apparatus for Pali QA targets.")
    parser.add_argument("--review-queue-reclassified", required=True)
    parser.add_argument("--findings", required=True)
    parser.add_argument("--parsed", required=True)
    parser.add_argument("--source-root", required=True)
    parser.add_argument("--targets")
    parser.add_argument("--out", required=True)
    parser.add_argument("--max-targets", type=int, default=20)
    parser.add_argument("--window-chars", type=int, default=160)
    parser.add_argument("--pretty", action="store_true")
    return parser


def run(args: argparse.Namespace) -> dict[str, Any]:
    review_queue_path = Path(args.review_queue_reclassified)
    findings_path = Path(args.findings)
    parsed_path = Path(args.parsed)
    source_root = Path(args.source_root)
    targets_path = Path(args.targets) if args.targets else None
    out_dir = Path(args.out)
    out_dir.mkdir(parents=True, exist_ok=True)

    for path in [review_queue_path, findings_path, parsed_path]:
        if not path.exists():
            raise FileNotFoundError(f"missing input file: {path}")
    if targets_path and not targets_path.exists():
        raise FileNotFoundError(f"missing targets file: {targets_path}")

    review_queue = read_json(review_queue_path)
    findings = read_json(findings_path)
    parsed = read_json(parsed_path)
    targets_payload = read_json(targets_path) if targets_path else None

    extraction = run_variant_apparatus_extraction(
        review_queue_reclassified=review_queue,
        findings=findings,
        parsed_payload=parsed,
        source_root=source_root,
        targets_payload=targets_payload,
        max_targets=args.max_targets,
        window_chars=args.window_chars,
    )

    paths = {
        "premise": out_dir / "apparatus_premise_check.json",
        "apparatus": out_dir / "variant_apparatus.json",
        "crosscheck": out_dir / "apparatus_qa_crosscheck.json",
        "findings_md": out_dir / "apparatus_findings.md",
        "run_manifest": out_dir / "run_manifest.json",
    }
    write_json(paths["premise"], extraction["premise_check"], pretty=args.pretty)
    write_json(paths["apparatus"], extraction["variant_apparatus"], pretty=args.pretty)
    write_json(paths["crosscheck"], extraction["crosscheck"], pretty=args.pretty)
    paths["findings_md"].write_text(
        render_findings_markdown(
            premise=extraction["premise_check"],
            apparatus=extraction["variant_apparatus"],
            crosscheck=extraction["crosscheck"],
        ),
        encoding="utf-8",
    )
    manifest = run_manifest(args, paths, [review_queue_path, findings_path, parsed_path] + ([targets_path] if targets_path else []), extraction)
    write_json(paths["run_manifest"], manifest, pretty=args.pretty)

    cross_summary = extraction["crosscheck"]["summary"]
    apparatus_summary = extraction["variant_apparatus"]["summary"]
    return {
        "status": "VARIANT_APPARATUS_EXTRACTION_COMPLETE",
        "api_llm_calls": 0,
        "network_calls": 0,
        "cross_script_collation": False,
        "source_files_checked": apparatus_summary["source_files_checked"],
        "note_records_extracted": apparatus_summary["note_records_extracted"],
        "variant_note_count": apparatus_summary["variant_note_records_in_300_source_scope"],
        "citation_note_count": apparatus_summary["citation_note_records_in_300_source_scope"],
        "target_count": cross_summary["target_count"],
        "apparatus_attests_variant": cross_summary["apparatus_attests_variant"],
        "apparatus_has_variant_nearby": cross_summary["apparatus_has_variant_nearby"],
        "no_apparatus_variant": cross_summary["no_apparatus_variant"],
        "missing_source": cross_summary["apparatus_extraction_missing_source"],
        "out": str(out_dir),
    }


def run_manifest(
    args: argparse.Namespace,
    paths: dict[str, Path],
    input_paths: list[Path],
    extraction: dict[str, Any],
) -> dict[str, Any]:
    return {
        "schema_version": "pali_variant_apparatus_run_manifest_v0",
        "script_version": SCRIPT_VERSION,
        "created_at": datetime.now(timezone.utc).isoformat(),
        "api_llm_calls": 0,
        "network_calls": 0,
        "cross_script_collation": False,
        "translation_mutation": False,
        "source_mutation": False,
        "parsed_mutation": False,
        "prompt_glossary_gold_mutation": False,
        "input_files": {path.name: output_record(path) for path in input_paths},
        "output_files": {name: output_record(path) for name, path in paths.items() if path.exists()},
        "args": {
            "review_queue_reclassified": args.review_queue_reclassified,
            "findings": args.findings,
            "parsed": args.parsed,
            "source_root": args.source_root,
            "targets": args.targets,
            "out": args.out,
            "max_targets": args.max_targets,
            "window_chars": args.window_chars,
        },
        "summary": {
            **extraction["crosscheck"]["summary"],
            **extraction["variant_apparatus"]["summary"],
        },
    }


def read_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def write_json(path: Path, payload: Any, *, pretty: bool) -> None:
    path.write_text(dump_json(payload, pretty=pretty), encoding="utf-8")


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))

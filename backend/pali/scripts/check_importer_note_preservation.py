"""Verify VRI importer note preservation is additive-only.

This script performs local reparses only. It does not call Gemini, Batch, LLMs,
or the network, and it does not modify source XML or translation artifacts.
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

from backend.pali.importers.vri_xml import parse_vri_xml


DEFAULT_SOURCE_PATHS = [
    "romn/s0519m.mul.xml",
    "romn/abh03m11.mul.xml",
    "romn/s0302t.tik.xml",
    "romn/vin02a2.att.xml",
]
DEFAULT_OUT = "data/reports/pali/importer_note_preservation_check.json"


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    report = run_check(
        source_root=Path(args.source_root),
        source_paths=args.source_path or DEFAULT_SOURCE_PATHS,
        out=Path(args.out),
        pretty=args.pretty,
    )
    print(json.dumps(report, ensure_ascii=False, sort_keys=True))
    return 0 if report["status"] in {"PASS", "INCOMPLETE"} else 1


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Check VRI importer source_apparatus additive-only behavior.")
    parser.add_argument("--source-root", default="data/tipitaka-xml")
    parser.add_argument("--source-path", action="append")
    parser.add_argument("--out", default=DEFAULT_OUT)
    parser.add_argument("--pretty", action="store_true")
    return parser


def run_check(
    *,
    source_root: Path,
    source_paths: list[str],
    out: Path,
    pretty: bool = False,
) -> dict[str, Any]:
    report = {
        "step": "3H",
        "api_llm_calls": 0,
        "network_calls": 0,
        "translation_mutation": False,
        "source_mutation": False,
        "prompt_mutation": False,
        "glossary_mutation": False,
        "gold_set_mutation": False,
        "holdout_gold_frozen": False,
        "check_scope": "local_reimport_compare_preserve_source_apparatus_false_vs_true",
        "checked_files": 0,
        "checked_segments": 0,
        "missing_files": [],
        "original_text_mismatches": 0,
        "stable_segment_key_mismatches": 0,
        "source_text_hash_mismatches": 0,
        "segment_count_mismatches": 0,
        "xml_node_paths_mismatches": 0,
        "translation_prompt_input_mismatches": 0,
        "non_additive_diffs": 0,
        "source_apparatus_records_added": 0,
        "file_results": [],
        "status": "PASS",
    }
    for source_path in source_paths:
        xml_path = resolve_source_xml(source_root, source_path)
        if not xml_path.exists():
            report["missing_files"].append(source_path)
            continue
        before = parse_vri_xml(xml_path, source_path=source_path, preserve_source_apparatus=False)
        after = parse_vri_xml(xml_path, source_path=source_path, preserve_source_apparatus=True)
        file_result = compare_artifacts(source_path, before, after)
        report["file_results"].append(file_result)
        report["checked_files"] += 1
        report["checked_segments"] += file_result["checked_segments"]
        for key in (
            "original_text_mismatches",
            "stable_segment_key_mismatches",
            "source_text_hash_mismatches",
            "segment_count_mismatches",
            "xml_node_paths_mismatches",
            "translation_prompt_input_mismatches",
            "non_additive_diffs",
            "source_apparatus_records_added",
        ):
            report[key] += file_result[key]
    if report["checked_files"] == 0:
        report["status"] = "INCOMPLETE"
    elif any(report[key] for key in (
        "original_text_mismatches",
        "stable_segment_key_mismatches",
        "source_text_hash_mismatches",
        "segment_count_mismatches",
        "xml_node_paths_mismatches",
        "translation_prompt_input_mismatches",
        "non_additive_diffs",
    )):
        report["status"] = "FAIL"
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(report, ensure_ascii=False, sort_keys=True, indent=2 if pretty else None) + "\n", encoding="utf-8")
    return report


def resolve_source_xml(source_root: Path, source_path: str) -> Path:
    for candidate in (source_root / source_path, source_root / "tipitaka.org" / source_path):
        if candidate.exists():
            return candidate
    return source_root / source_path


def compare_artifacts(source_path: str, before: dict[str, Any], after: dict[str, Any]) -> dict[str, Any]:
    before_segments = before.get("segments", [])
    after_segments = after.get("segments", [])
    result = {
        "source_path": source_path,
        "checked_segments": min(len(before_segments), len(after_segments)),
        "before_segments": len(before_segments),
        "after_segments": len(after_segments),
        "original_text_mismatches": 0,
        "stable_segment_key_mismatches": 0,
        "source_text_hash_mismatches": 0,
        "segment_count_mismatches": 0 if len(before_segments) == len(after_segments) else 1,
        "xml_node_paths_mismatches": 0,
        "translation_prompt_input_mismatches": 0,
        "non_additive_diffs": 0,
        "source_apparatus_records_added": 0,
    }
    for before_segment, after_segment in zip(before_segments, after_segments):
        if before_segment.get("original_text") != after_segment.get("original_text"):
            result["original_text_mismatches"] += 1
        if before_segment.get("stable_segment_key") != after_segment.get("stable_segment_key"):
            result["stable_segment_key_mismatches"] += 1
        if before_segment.get("source_text_hash") != after_segment.get("source_text_hash"):
            result["source_text_hash_mismatches"] += 1
        if before_segment.get("xml_node_paths") != after_segment.get("xml_node_paths"):
            result["xml_node_paths_mismatches"] += 1
        if prompt_input(before_segment) != prompt_input(after_segment):
            result["translation_prompt_input_mismatches"] += 1
        result["source_apparatus_records_added"] += len(after_segment.get("source_apparatus", []))
        if strip_source_apparatus(before_segment) != strip_source_apparatus(after_segment):
            result["non_additive_diffs"] += 1
    return result


def prompt_input(segment: dict[str, Any]) -> str:
    return str(segment.get("normalized_text") or segment.get("original_text") or "")


def strip_source_apparatus(segment: dict[str, Any]) -> dict[str, Any]:
    cleaned = dict(segment)
    cleaned.pop("source_apparatus", None)
    return cleaned


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))

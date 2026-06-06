"""Batch token summary for VRI romn XML corpus.

This script parses XML files into local segment artifacts and aggregates token
counts by layer, pitaka, and nikaya. It does not call LLM APIs and does not
write to the database.
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

from backend.pali.importers.vri_xml import parse_source_file, parse_vri_xml
from backend.pali.tokenization.token_counter import (
    build_token_report,
    load_token_profiles,
    merge_tokenizer_warnings,
)


def count_corpus_tokens(
    input_dir: str | Path,
    *,
    include_layers: set[str],
    token_profiles_path: str | Path | None = None,
    source_commit: str | None = None,
) -> dict[str, Any]:
    input_path = Path(input_dir)
    profiles = load_token_profiles(token_profiles_path)
    xml_files = sorted(input_path.glob("*.xml"))

    files_by_text_layer: Counter[str] = Counter()
    segments_by_text_layer: Counter[str] = Counter()
    chars_by_text_layer: Counter[str] = Counter()
    tokens_by_text_layer_and_profile: dict[str, dict[str, int]] = defaultdict(dict)
    tokens_by_pitaka_and_profile: dict[str, dict[str, int]] = defaultdict(dict)
    tokens_by_nikaya_and_profile: dict[str, dict[str, int]] = defaultdict(dict)
    largest_files: list[dict[str, Any]] = []
    largest_segments: list[dict[str, Any]] = []
    files_with_errors: list[dict[str, Any]] = []
    files_with_warnings: list[dict[str, Any]] = []
    unknown_filename_patterns: list[str] = []
    token_reports: list[dict[str, Any]] = []
    excluded_layers: Counter[str] = Counter()

    for xml_file in xml_files:
        source_path = f"{input_path.name}/{xml_file.name}"
        file_info = parse_source_file(xml_file.name)
        text_layer = file_info["text_layer"]
        if file_info["filename_pattern"] == "unknown":
            unknown_filename_patterns.append(xml_file.name)
        if text_layer not in include_layers:
            excluded_layers[text_layer] += 1
            continue

        try:
            artifact = parse_vri_xml(
                xml_file,
                source_path=source_path,
                source_commit=source_commit,
                include_token_report=False,
            )
            token_report = build_token_report(artifact, profiles=profiles)
        except Exception as exc:  # pragma: no cover - defensive batch behavior.
            files_with_errors.append({"source_file": xml_file.name, "error": str(exc)})
            continue

        literature = artifact["literature"]
        import_report = artifact["import_report"]
        token_reports.append(token_report)
        layer = literature.get("text_layer") or "unknown"
        pitaka = literature.get("pitaka") or "unknown"
        nikaya = literature.get("nikaya") or "unknown"

        files_by_text_layer[layer] += 1
        segments_by_text_layer[layer] += len(artifact["segments"])
        chars_by_text_layer[layer] += token_report["total_normalized_chars"]

        for profile_id, token_count in token_report["estimated_source_tokens_by_profile"].items():
            tokens_by_text_layer_and_profile[layer][profile_id] = (
                tokens_by_text_layer_and_profile[layer].get(profile_id, 0) + token_count
            )
            tokens_by_pitaka_and_profile[pitaka][profile_id] = (
                tokens_by_pitaka_and_profile[pitaka].get(profile_id, 0) + token_count
            )
            tokens_by_nikaya_and_profile[nikaya][profile_id] = (
                tokens_by_nikaya_and_profile[nikaya].get(profile_id, 0) + token_count
            )

        largest_files.append(
            {
                "source_path": source_path,
                "literature_id": literature["literature_id"],
                "text_layer": layer,
                "segments": len(artifact["segments"]),
                "tokens_by_profile": token_report["estimated_source_tokens_by_profile"],
            }
        )
        for profile_id, items in token_report["top_20_largest_segments_by_profile"].items():
            for item in items:
                largest_segments.append(
                    {
                        "source_path": source_path,
                        "profile_id": profile_id,
                        **item,
                    }
                )

        if import_report.get("warnings"):
            files_with_warnings.append(
                {"source_path": source_path, "warnings": import_report["warnings"][:20]}
            )
        if import_report.get("errors"):
            files_with_errors.append(
                {"source_path": source_path, "errors": import_report["errors"][:20]}
            )

    largest_files = sorted(
        largest_files,
        key=lambda item: max(item["tokens_by_profile"].values()) if item["tokens_by_profile"] else 0,
        reverse=True,
    )[:20]
    largest_segments = sorted(
        largest_segments,
        key=lambda item: item["token_count"],
        reverse=True,
    )[:50]

    fallbacks: dict[str, int] = {}
    for report in token_reports:
        for profile_id, data in report.get("tokenizers_used", {}).items():
            if data.get("fallback_used"):
                fallbacks[profile_id] = fallbacks.get(profile_id, 0) + 1

    return {
        "input_dir": str(input_path),
        "source_commit": source_commit,
        "included_layers": sorted(include_layers),
        "excluded_layers": dict(sorted(excluded_layers.items())),
        "total_files": sum(files_by_text_layer.values()),
        "files_by_text_layer": dict(sorted(files_by_text_layer.items())),
        "segments_by_text_layer": dict(sorted(segments_by_text_layer.items())),
        "chars_by_text_layer": dict(sorted(chars_by_text_layer.items())),
        "tokens_by_text_layer_and_profile": sort_nested(tokens_by_text_layer_and_profile),
        "tokens_by_pitaka_and_profile": sort_nested(tokens_by_pitaka_and_profile),
        "tokens_by_nikaya_and_profile": sort_nested(tokens_by_nikaya_and_profile),
        "largest_files_by_tokens": largest_files,
        "largest_segments_by_tokens": largest_segments,
        "files_with_errors": files_with_errors,
        "files_with_warnings": files_with_warnings,
        "unknown_filename_patterns": unknown_filename_patterns,
        "tokenizer_fallbacks_used": fallbacks,
        "tokenizer_warnings": merge_tokenizer_warnings(token_reports),
        "generated_at": datetime.now(timezone.utc).isoformat(),
    }


def sort_nested(mapping: dict[str, dict[str, int]]) -> dict[str, dict[str, int]]:
    return {key: dict(sorted(value.items())) for key, value in sorted(mapping.items())}


def parse_layers(raw: str) -> set[str]:
    suffix_to_layer = {"mul": "mula", "att": "atthakatha", "tik": "tika"}
    layers: set[str] = set()
    for item in raw.split(","):
        cleaned = item.strip()
        if cleaned:
            layers.add(suffix_to_layer.get(cleaned, cleaned))
    return layers


def main() -> None:
    parser = argparse.ArgumentParser(description="Count local tokens for a VRI XML corpus.")
    parser.add_argument("--input-dir", required=True)
    parser.add_argument("--include-layers", default="mul,att,tik")
    parser.add_argument("--token-profiles")
    parser.add_argument("--source-commit")
    parser.add_argument("--out", required=True)
    parser.add_argument("--pretty", action="store_true")
    args = parser.parse_args()

    summary = count_corpus_tokens(
        args.input_dir,
        include_layers=parse_layers(args.include_layers),
        token_profiles_path=args.token_profiles,
        source_commit=args.source_commit,
    )
    out = Path(args.out)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(
        json.dumps(summary, ensure_ascii=False, indent=2 if args.pretty else None),
        encoding="utf-8",
    )


if __name__ == "__main__":
    main()

"""CLI for Step 5 Pali pilot 1,000 selection.

Selection-only: no API, network, Batch, prompt, glossary, gold, source XML, or
translation mutation.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[3]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from backend.pali.translation.pilot_1000_selection import (
    PINNED_INVENTORY_CACHE,
    Pilot1000SelectionError,
    run_selection,
)


DEFAULT_OUT = "data/pilot_sets/pali"
DEFAULT_SOURCE_ROOT = "data/tipitaka-xml"
DEFAULT_PILOT_300_MANIFEST = "data/pilot_sets/pali/pilot_300_v1_manifest.json"
DEFAULT_STEP4_SELECTION = "data/reports/pali/step4_response_schema_smoke/selection_manifest.json"
DEFAULT_SILVER_DRAFT = "data/review_seeds/pali/silver_canary_draft.json"
DEFAULT_GOLD_SET = "data/gold_set.json"
DEFAULT_STEP4_FINAL_DECISION = "data/reports/pali/step4_response_schema_smoke/final_decision.json"
DEFAULT_STEP4_HANDOFF = "data/reports/pali/step4_response_schema_smoke/step5_handoff.md"
DEFAULT_IMPORTER_CHECK = "data/reports/pali/importer_note_preservation_check.json"
DEFAULT_PILOT75_PATHS = [
    "data/reports/pali/gemini_pilot_75_49bc869_prompt_qa_patch_v2_parsed.json",
    "data/reports/pali/gemini_pilot_75_49bc869_prompt_v1_schemafix_parsed.json",
]


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Build deterministic Pali pilot_1000_new selection manifest.")
    parser.add_argument("--inventory", default=PINNED_INVENTORY_CACHE)
    parser.add_argument("--out", default=DEFAULT_OUT)
    parser.add_argument("--source-root", default=DEFAULT_SOURCE_ROOT)
    parser.add_argument("--pilot-300-manifest", default=DEFAULT_PILOT_300_MANIFEST)
    parser.add_argument("--pilot-75-path", action="append", dest="pilot75_paths")
    parser.add_argument("--step4-selection", default=DEFAULT_STEP4_SELECTION)
    parser.add_argument("--silver-draft", default=DEFAULT_SILVER_DRAFT)
    parser.add_argument("--gold-set", default=DEFAULT_GOLD_SET)
    parser.add_argument("--step4-final-decision", default=DEFAULT_STEP4_FINAL_DECISION)
    parser.add_argument("--step4-handoff", default=DEFAULT_STEP4_HANDOFF)
    parser.add_argument("--importer-check", default=DEFAULT_IMPORTER_CHECK)
    parser.add_argument("--pretty", action="store_true")
    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    pilot75_paths = [Path(path) for path in (args.pilot75_paths or DEFAULT_PILOT75_PATHS)]
    try:
        result = run_selection(
            inventory_path=Path(args.inventory),
            out_dir=Path(args.out),
            source_root=Path(args.source_root),
            pilot_300_manifest=Path(args.pilot_300_manifest),
            pilot_75_paths=pilot75_paths,
            step4_selection=Path(args.step4_selection),
            silver_draft=Path(args.silver_draft),
            gold_set=Path(args.gold_set),
            step4_final_decision=Path(args.step4_final_decision),
            step4_handoff=Path(args.step4_handoff),
            importer_check=Path(args.importer_check),
            pretty=args.pretty,
        )
    except Pilot1000SelectionError as exc:
        print(json.dumps({"status": "FAIL", "error": str(exc)}, ensure_ascii=False, sort_keys=True), file=sys.stderr)
        return 1
    print(json.dumps({"status": "PASS", **result}, ensure_ascii=False, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())


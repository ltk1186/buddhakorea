"""Prepare Step 5.5 natural_ko readability audit and calibration dry-run artifacts."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from backend.pali.translation.natural_ko_readability import (
    DEFAULT_INPUT,
    DEFAULT_OUT,
    run_calibration_prep,
)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input", type=Path, default=DEFAULT_INPUT)
    parser.add_argument("--out", type=Path, default=DEFAULT_OUT)
    parser.add_argument("--pretty", action="store_true")
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    result = run_calibration_prep(source_file=args.input, out_dir=args.out, pretty=args.pretty)
    print(json.dumps(result, ensure_ascii=False, indent=2 if args.pretty else None, sort_keys=args.pretty))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())


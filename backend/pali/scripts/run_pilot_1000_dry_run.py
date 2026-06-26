"""Run Step 6 Pilot 1,000 dry-run artifacts.

This CLI is local-only. It intentionally does not implement provider submit,
poll, fetch, or parse modes.
"""

from __future__ import annotations

import argparse
import json
import sys
from decimal import Decimal
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[3]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from backend.pali.translation.pilot_1000_dry_run import (
    DEFAULT_HARD_CAP_USD,
    DEFAULT_MANIFEST,
    DEFAULT_OUT,
    Pilot1000DryRunBlocked,
    run_pilot_1000_dry_run,
)


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Step 6 Pilot 1,000 dry-run, no live submit.")
    parser.add_argument("--manifest", type=Path, default=DEFAULT_MANIFEST)
    parser.add_argument("--out", type=Path, default=DEFAULT_OUT)
    parser.add_argument("--prompt-variant", default="natural_ko_v2_2")
    parser.add_argument("--response-schema", action="store_true", default=False)
    parser.add_argument("--dry-run", action="store_true", default=False)
    parser.add_argument("--hard-cap-usd", default=str(DEFAULT_HARD_CAP_USD))
    parser.add_argument("--pretty", action="store_true")
    parser.add_argument("--submit", action="store_true", help=argparse.SUPPRESS)
    parser.add_argument("--poll", action="store_true", help=argparse.SUPPRESS)
    parser.add_argument("--fetch", action="store_true", help=argparse.SUPPRESS)
    parser.add_argument("--parse", action="store_true", help=argparse.SUPPRESS)
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    if args.submit or args.poll or args.fetch or args.parse:
        print(
            json.dumps(
                {
                    "status": "BLOCKED_LIVE_MODE_UNSUPPORTED",
                    "message": "Step 6 dry-run CLI intentionally has no submit/poll/fetch/parse path.",
                },
                ensure_ascii=False,
                indent=2 if args.pretty else None,
            ),
            file=sys.stderr,
        )
        return 2
    try:
        result = run_pilot_1000_dry_run(
            manifest_path=args.manifest,
            out_dir=args.out,
            prompt_variant=args.prompt_variant,
            response_schema=args.response_schema,
            dry_run=args.dry_run,
            hard_cap_usd=Decimal(str(args.hard_cap_usd)),
            pretty=args.pretty,
        )
    except Pilot1000DryRunBlocked as exc:
        print(
            json.dumps(
                {"status": exc.status, "message": exc.message, "details": exc.details},
                ensure_ascii=False,
                indent=2 if args.pretty else None,
            ),
            file=sys.stderr,
        )
        return 1
    print(json.dumps(result, ensure_ascii=False, indent=2 if args.pretty else None))
    return 0 if result.get("status") == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())

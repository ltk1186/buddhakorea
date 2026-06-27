"""Step 7 Pilot 1,000 guarded live pipeline CLI.

Default mode is local-only ``--preflight``. Live provider actions require
explicit operator flags and are not chained.
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

from backend.pali.translation.pilot_1000_live import (
    DEFAULT_HARD_CAP_USD,
    DEFAULT_MANIFEST,
    DEFAULT_OUT,
    DEFAULT_REQUEST_PREVIEW,
    DEFAULT_RETRY_HARD_CAP_USD,
    Pilot1000LiveBlocked,
    build_retry_bracket_plan,
    fetch_live_results,
    parse_live_results,
    poll_live_batch,
    preflight_submit,
    report_outputs,
    run_qa,
    submit_live_batch,
)


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Step 7 Pilot 1,000 live pipeline. Default mode is preflight.")
    modes = parser.add_mutually_exclusive_group()
    modes.add_argument("--preflight", action="store_true")
    modes.add_argument("--submit", action="store_true")
    modes.add_argument("--poll", action="store_true")
    modes.add_argument("--fetch", action="store_true")
    modes.add_argument("--parse", action="store_true")
    modes.add_argument("--qa", action="store_true")
    modes.add_argument("--report", action="store_true")
    modes.add_argument("--retry-bracket", action="store_true")
    parser.add_argument("--request-preview", type=Path, default=DEFAULT_REQUEST_PREVIEW)
    parser.add_argument("--manifest", type=Path, default=DEFAULT_MANIFEST)
    parser.add_argument("--out", type=Path, default=DEFAULT_OUT)
    parser.add_argument("--hard-cap-usd", default=str(DEFAULT_HARD_CAP_USD))
    parser.add_argument("--retry-hard-cap-usd", default=str(DEFAULT_RETRY_HARD_CAP_USD))
    parser.add_argument("--pretty", action="store_true")
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    mode_selected = any(
        [
            args.preflight,
            args.submit,
            args.poll,
            args.fetch,
            args.parse,
            args.qa,
            args.report,
            args.retry_bracket,
        ]
    )
    try:
        if args.submit:
            result = submit_live_batch(
                request_preview_path=args.request_preview,
                manifest_path=args.manifest,
                out_dir=args.out,
                hard_cap_usd=Decimal(str(args.hard_cap_usd)),
                pretty=args.pretty,
            )
        elif args.poll:
            result = poll_live_batch(out_dir=args.out, pretty=args.pretty)
        elif args.fetch:
            result = fetch_live_results(out_dir=args.out, pretty=args.pretty)
        elif args.parse:
            result = parse_live_results(
                request_preview_path=args.request_preview,
                manifest_path=args.manifest,
                out_dir=args.out,
                pretty=args.pretty,
            )
        elif args.qa:
            result = run_qa(out_dir=args.out, pretty=args.pretty)
        elif args.report:
            result = report_outputs(out_dir=args.out, pretty=args.pretty)
        elif args.retry_bracket:
            result = build_retry_bracket_plan(
                out_dir=args.out,
                retry_hard_cap_usd=Decimal(str(args.retry_hard_cap_usd)),
                pretty=args.pretty,
            )
        else:
            # Default is deliberately preflight, even when --preflight is omitted.
            result = preflight_submit(
                request_preview_path=args.request_preview,
                manifest_path=args.manifest,
                out_dir=args.out,
                hard_cap_usd=Decimal(str(args.hard_cap_usd)),
                pretty=args.pretty,
            )
        print(json.dumps(result, ensure_ascii=False, indent=2 if args.pretty else None))
        status = result.get("status")
        if mode_selected and args.preflight:
            return 0 if status == "PASS" else 1
        if not mode_selected:
            return 0 if status == "PASS" else 1
        if isinstance(status, str) and status.startswith("BLOCKED"):
            return 1
        return 0
    except Pilot1000LiveBlocked as exc:
        print(
            json.dumps(
                {"status": exc.status, "message": exc.message, "details": exc.details},
                ensure_ascii=False,
                indent=2 if args.pretty else None,
            ),
            file=sys.stderr,
        )
        return 2


if __name__ == "__main__":
    raise SystemExit(main())


"""Run Step 5.5-C/D natural_ko_v2 controlled smoke harness.

Default execution is preflight only and makes no provider calls. Submit, poll,
fetch, parse, compare, and finalize each require explicit CLI flags.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[3]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from backend.pali.scripts.calibrate_gemini_tokens import resolve_gemini_api_key
from backend.pali.scripts.submit_gemini_smoke_batch import GeminiBatchRestClient
from backend.pali.translation.natural_ko_calibration_smoke import (
    DEFAULT_OUT,
    DEFAULT_V2_2_OUT,
    DEFAULT_PRICE_PROFILE_ID,
    DEFAULT_PRICE_PROFILE_PATH,
    NaturalKoSmokeBlocked,
    compare_v2_2_smoke,
    compare_v2_1_smoke,
    compare_smoke,
    finalize_v2_1_recommendation,
    finalize_recommendation,
    parse_smoke,
    poll_or_fetch,
    run_preflight,
    run_preflight_v2_1,
    run_preflight_v2_2,
    submit_c_arm,
    submit_d_arm,
    submit_smoke,
)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    mode = parser.add_mutually_exclusive_group()
    mode.add_argument("--preflight", action="store_true", help="Run local preflight only. This is the default.")
    mode.add_argument("--preflight-v2-2", action="store_true", help="Run D-arm natural_ko_v2.2 preflight only.")
    mode.add_argument("--submit", action="store_true", help="Submit both A′ and B batches after preflight and cost cap checks.")
    mode.add_argument("--submit-arm", choices=["C", "D"], help="Submit one explicit arm.")
    mode.add_argument("--poll", action="store_true", help="Poll existing provider batch ids.")
    mode.add_argument("--fetch", action="store_true", help="Fetch raw inline results for existing provider batch ids.")
    mode.add_argument("--parse", action="store_true", help="Parse fetched raw results.")
    mode.add_argument("--compare", action="store_true", help="Compare parsed A′ and B outputs.")
    mode.add_argument("--compare-v2-1", action="store_true", help="Compare reused A′, reference B, and C v2.1 outputs.")
    mode.add_argument("--compare-v2-2", action="store_true", help="Compare D v2.2 against existing A′/B/C references.")
    mode.add_argument("--finalize", action="store_true", help="Write conditional final recommendation.")
    mode.add_argument("--finalize-v2-1", action="store_true", help="Write conditional v2.1 final recommendation.")
    parser.add_argument("--out", type=Path, default=DEFAULT_OUT)
    parser.add_argument("--calibration-source-dir", type=Path, default=DEFAULT_OUT)
    parser.add_argument("--price-profile-path", type=Path, default=DEFAULT_PRICE_PROFILE_PATH)
    parser.add_argument("--price-profile-id", default=DEFAULT_PRICE_PROFILE_ID)
    parser.add_argument("--pretty", action="store_true")
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    try:
        result = run(args)
    except NaturalKoSmokeBlocked as exc:
        payload = {"status": exc.status, "message": exc.message, **exc.details}
        print(json.dumps(payload, ensure_ascii=False, sort_keys=True), file=sys.stderr)
        return 2
    print(json.dumps(result, ensure_ascii=False, indent=2 if args.pretty else None, sort_keys=args.pretty))
    return 0


def run(args: argparse.Namespace) -> dict:
    out_dir = effective_out(args)
    if args.submit:
        credential = resolve_gemini_api_key()
        if not credential:
            raise NaturalKoSmokeBlocked("BLOCKED_MISSING_GEMINI_CREDENTIAL", "Gemini credential must be present in environment/local config for submit.")
        client = GeminiBatchRestClient(api_key=credential)
        return submit_smoke(out_dir=out_dir, client=client, pretty=args.pretty)
    if args.submit_arm == "C":
        credential = resolve_gemini_api_key()
        if not credential:
            raise NaturalKoSmokeBlocked("BLOCKED_MISSING_GEMINI_CREDENTIAL", "Gemini credential must be present in environment/local config for submit.")
        client = GeminiBatchRestClient(api_key=credential)
        return submit_c_arm(out_dir=out_dir, client=client, pretty=args.pretty)
    if args.submit_arm == "D":
        credential = resolve_gemini_api_key()
        if not credential:
            raise NaturalKoSmokeBlocked("BLOCKED_MISSING_GEMINI_CREDENTIAL", "Gemini credential must be present in environment/local config for submit.")
        client = GeminiBatchRestClient(api_key=credential)
        return submit_d_arm(out_dir=out_dir, calibration_source_dir=args.calibration_source_dir, client=client, pretty=args.pretty)
    if args.poll:
        client = client_from_env()
        return poll_or_fetch(out_dir=out_dir, client=client, fetch=False, pretty=args.pretty)
    if args.fetch:
        client = client_from_env()
        return poll_or_fetch(out_dir=out_dir, client=client, fetch=True, pretty=args.pretty)
    if args.parse:
        return parse_smoke(
            out_dir=out_dir,
            calibration_source_dir=args.calibration_source_dir,
            price_profile_path=args.price_profile_path,
            price_profile_id=args.price_profile_id,
            pretty=args.pretty,
        )
    if args.compare:
        return compare_smoke(out_dir=out_dir, pretty=args.pretty)
    if args.compare_v2_1:
        return compare_v2_1_smoke(out_dir=out_dir, pretty=args.pretty)
    if args.compare_v2_2:
        return compare_v2_2_smoke(out_dir=out_dir, calibration_source_dir=args.calibration_source_dir, pretty=args.pretty)
    if args.finalize:
        return finalize_recommendation(out_dir=out_dir, pretty=args.pretty)
    if args.finalize_v2_1:
        return finalize_v2_1_recommendation(out_dir=out_dir, pretty=args.pretty)
    if args.preflight_v2_2:
        return run_preflight_v2_2(
            out_dir=out_dir,
            calibration_source_dir=args.calibration_source_dir,
            price_profile_path=args.price_profile_path,
            price_profile_id=args.price_profile_id,
            pretty=args.pretty,
        )
    return run_preflight_v2_1(
        out_dir=out_dir,
        price_profile_path=args.price_profile_path,
        price_profile_id=args.price_profile_id,
        pretty=args.pretty,
    )


def effective_out(args: argparse.Namespace) -> Path:
    if (args.preflight_v2_2 or args.submit_arm == "D" or args.compare_v2_2) and args.out == DEFAULT_OUT:
        return DEFAULT_V2_2_OUT
    return args.out


def client_from_env() -> GeminiBatchRestClient:
    credential = resolve_gemini_api_key()
    if not credential:
        raise NaturalKoSmokeBlocked("BLOCKED_MISSING_GEMINI_CREDENTIAL", "Gemini credential must be present in environment/local config.")
    return GeminiBatchRestClient(api_key=credential)


if __name__ == "__main__":
    raise SystemExit(main())

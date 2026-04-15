#!/usr/bin/env python3
"""Run Buddha Korea RAG golden-query smoke checks against a live API."""

from __future__ import annotations

import argparse
import json
import os
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
from http.cookiejar import CookieJar
from pathlib import Path
from typing import Any

REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT))
DEFAULT_USER_AGENT = "BuddhaKorea-RAG-Regression/1.0 (+https://buddhakorea.com)"

from backend.app.rag_regression import (  # noqa: E402
    DEFAULT_GOLDEN_CASES_PATH,
    load_golden_cases,
    summarize_issues,
    validate_chat_response,
)


def _request_json(
    opener: urllib.request.OpenerDirector,
    method: str,
    url: str,
    payload: dict[str, Any] | None = None,
    timeout: int = 30,
) -> tuple[int, dict[str, Any]]:
    body = None
    headers = {
        "Accept": "application/json",
        "User-Agent": DEFAULT_USER_AGENT,
    }
    if payload is not None:
        body = json.dumps(payload).encode("utf-8")
        headers["Content-Type"] = "application/json"

    request = urllib.request.Request(url, data=body, headers=headers, method=method)
    try:
        with opener.open(request, timeout=timeout) as response:
            raw = response.read().decode("utf-8")
            return response.status, json.loads(raw) if raw else {}
    except urllib.error.HTTPError as error:
        raw = error.read().decode("utf-8", errors="replace")
        try:
            data = json.loads(raw) if raw else {}
        except json.JSONDecodeError:
            data = {"raw": raw}
        return error.code, data


def _login_if_configured(
    opener: urllib.request.OpenerDirector,
    base_url: str,
    timeout: int,
) -> None:
    email = os.environ.get("ADMIN_EMAIL")
    password = os.environ.get("ADMIN_PASSWORD")
    if not email or not password:
        print("Admin login skipped: ADMIN_EMAIL/ADMIN_PASSWORD not set")
        return

    status, data = _request_json(
        opener,
        "POST",
        urllib.parse.urljoin(base_url, "/api/admin/login"),
        {"email": email, "password": password},
        timeout=timeout,
    )
    if status != 200:
        raise RuntimeError(f"admin login failed with HTTP {status}: {data}")
    print(f"Admin login ok: role={data.get('role')} user_id={data.get('user_id')}")


def run_checks(args: argparse.Namespace) -> int:
    base_url = args.base_url.rstrip("/") + "/"
    cookie_jar = CookieJar()
    opener = urllib.request.build_opener(urllib.request.HTTPCookieProcessor(cookie_jar))

    health_status, health = _request_json(
        opener,
        "GET",
        urllib.parse.urljoin(base_url, "/api/health"),
        timeout=args.timeout,
    )
    print(f"health: HTTP {health_status} {health}")
    if health_status != 200:
        return 1
    if args.health_only:
        return 0

    if args.login:
        _login_if_configured(opener, base_url, args.timeout)

    cases = load_golden_cases(args.queries)
    selected_cases = [case for case in cases if not args.case or case["id"] in args.case]
    if args.max_cases:
        selected_cases = selected_cases[: args.max_cases]
    if not selected_cases:
        raise RuntimeError("no golden cases selected")

    failures = []
    passed_count = 0
    skipped_count = 0
    for index, case in enumerate(selected_cases, start=1):
        case_id = case["id"]
        payload = dict(case["request"])
        print(f"[{index}/{len(selected_cases)}] {case_id}: {payload['query']}")
        started_at = time.time()
        status, response = _request_json(
            opener,
            "POST",
            urllib.parse.urljoin(base_url, "/api/chat"),
            payload,
            timeout=args.timeout,
        )
        elapsed_ms = int((time.time() - started_at) * 1000)
        if status != 200:
            detail = str(response.get("detail", ""))
            if (
                args.allow_rag_unavailable
                and status == 503
                and "RAG system not initialized" in detail
            ):
                print(f"  skipped: RAG unavailable in this environment ({detail})")
                skipped_count += 1
                continue
            failures.append(f"- {case_id}: HTTP {status}: {response}")
            continue

        issues = validate_chat_response(case, response)
        if issues:
            failures.append(summarize_issues(issues))

        print(
            "  ok"
            if not issues
            else "  failed",
            f"latency={response.get('latency_ms')}ms",
            f"wall={elapsed_ms}ms",
            f"sources={len(response.get('sources') or [])}",
            f"model={response.get('model')}",
        )
        if not issues:
            passed_count += 1

    if failures:
        print("\nRAG regression failures:")
        print("\n".join(failures))
        return 1

    print(f"\nRAG regression checks completed: passed={passed_count} skipped={skipped_count}")
    return 0


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--base-url",
        default=os.environ.get("RAG_BASE_URL", "http://localhost:8000"),
        help="Base URL for Buddha Korea API. Default: %(default)s",
    )
    parser.add_argument(
        "--queries",
        default=str(DEFAULT_GOLDEN_CASES_PATH),
        help="Path to golden query JSON. Default: %(default)s",
    )
    parser.add_argument(
        "--case",
        action="append",
        help="Run only the named case id. Can be repeated.",
    )
    parser.add_argument(
        "--max-cases",
        type=int,
        default=0,
        help="Run only the first N selected cases. Useful for anonymous quota-safe smoke checks.",
    )
    parser.add_argument(
        "--timeout",
        type=int,
        default=150,
        help="Per-request timeout in seconds. Default: %(default)s",
    )
    parser.add_argument(
        "--login",
        action="store_true",
        help="Login with ADMIN_EMAIL and ADMIN_PASSWORD before running chat cases.",
    )
    parser.add_argument(
        "--health-only",
        action="store_true",
        help="Only verify /api/health. Does not call the LLM.",
    )
    parser.add_argument(
        "--allow-rag-unavailable",
        action="store_true",
        help=(
            "Treat local 503 'RAG system not initialized' responses as skipped cases. "
            "Use only for dev environments without a ready QA chain; do not use for production migration checks."
        ),
    )
    return parser.parse_args()


if __name__ == "__main__":
    raise SystemExit(run_checks(parse_args()))

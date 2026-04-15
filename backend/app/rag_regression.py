"""
Validation helpers for Buddha Korea RAG regression checks.

These helpers intentionally avoid network or LLM calls. The CLI script in
scripts/rag_regression_check.py handles HTTP; this module validates the response
shape and coarse quality signals so future LLM/RAG migrations have a stable
smoke-test contract.
"""

from __future__ import annotations

import json
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Any


DEFAULT_GOLDEN_CASES_PATH = Path(__file__).with_name("rag_golden_queries.json")
_MARKDOWN_HEADER_RE = re.compile(r"^\s{0,3}#{1,6}\s+", re.MULTILINE)


@dataclass(frozen=True)
class ValidationIssue:
    """A single validation failure for a RAG regression case."""

    case_id: str
    message: str


def load_golden_cases(path: str | Path = DEFAULT_GOLDEN_CASES_PATH) -> list[dict[str, Any]]:
    """Load golden query cases from JSON."""

    cases_path = Path(path)
    with cases_path.open("r", encoding="utf-8") as file:
        data = json.load(file)

    cases = data.get("cases")
    if not isinstance(cases, list):
        raise ValueError(f"{cases_path} must contain a top-level 'cases' list")

    for index, case in enumerate(cases):
        if not isinstance(case, dict):
            raise ValueError(f"Case at index {index} must be an object")
        if not case.get("id"):
            raise ValueError(f"Case at index {index} is missing 'id'")
        if not isinstance(case.get("request"), dict):
            raise ValueError(f"Case {case.get('id')} is missing a request object")

    return cases


def validate_chat_response(case: dict[str, Any], response: dict[str, Any]) -> list[ValidationIssue]:
    """Validate one /api/chat response against a golden case contract."""

    case_id = str(case.get("id", "unknown"))
    expect = case.get("expect", {})
    issues: list[ValidationIssue] = []

    answer = response.get("response")
    if not isinstance(answer, str) or not answer.strip():
        issues.append(ValidationIssue(case_id, "response must be a non-empty string"))
        answer = ""

    min_response_chars = int(expect.get("min_response_chars", 0))
    if min_response_chars and len(answer.strip()) < min_response_chars:
        issues.append(
            ValidationIssue(
                case_id,
                f"response length {len(answer.strip())} is below {min_response_chars}",
            )
        )

    if expect.get("forbid_markdown_headers", True) and _MARKDOWN_HEADER_RE.search(answer):
        issues.append(ValidationIssue(case_id, "response contains markdown heading syntax"))

    required_any_terms = expect.get("required_any_terms") or []
    if required_any_terms and not any(term in answer for term in required_any_terms):
        issues.append(
            ValidationIssue(
                case_id,
                "response does not contain any required term: "
                + ", ".join(map(str, required_any_terms)),
            )
        )

    forbidden_terms = expect.get("forbidden_terms") or []
    found_forbidden_terms = [term for term in forbidden_terms if term in answer]
    if found_forbidden_terms:
        issues.append(
            ValidationIssue(
                case_id,
                "response contains forbidden term(s): "
                + ", ".join(map(str, found_forbidden_terms)),
            )
        )

    sources = response.get("sources")
    if not isinstance(sources, list):
        issues.append(ValidationIssue(case_id, "sources must be a list"))
        sources = []

    min_sources = int(expect.get("min_sources", 0))
    if len(sources) < min_sources:
        issues.append(ValidationIssue(case_id, f"source count {len(sources)} is below {min_sources}"))

    for index, source in enumerate(sources):
        if not isinstance(source, dict):
            issues.append(ValidationIssue(case_id, f"source[{index}] must be an object"))
            continue
        for field in ("title", "text_id", "excerpt"):
            if not source.get(field):
                issues.append(ValidationIssue(case_id, f"source[{index}].{field} is required"))

    expected_source_text_ids = set(expect.get("expected_source_text_ids") or [])
    if expected_source_text_ids:
        actual_source_text_ids = {str(source.get("text_id")) for source in sources if isinstance(source, dict)}
        missing = expected_source_text_ids - actual_source_text_ids
        if missing:
            issues.append(
                ValidationIssue(
                    case_id,
                    "expected source text_id(s) not found: " + ", ".join(sorted(missing)),
                )
            )

    max_latency_ms = expect.get("max_latency_ms")
    latency_ms = response.get("latency_ms")
    if not isinstance(latency_ms, int) or latency_ms < 0:
        issues.append(ValidationIssue(case_id, "latency_ms must be a non-negative integer"))
    elif max_latency_ms is not None and latency_ms > int(max_latency_ms):
        issues.append(
            ValidationIssue(case_id, f"latency_ms {latency_ms} exceeds {int(max_latency_ms)}")
        )

    for field in ("model", "session_id"):
        if not response.get(field):
            issues.append(ValidationIssue(case_id, f"{field} is required"))

    if response.get("can_followup") is not True:
        issues.append(ValidationIssue(case_id, "can_followup should be true"))

    conversation_depth = response.get("conversation_depth")
    if not isinstance(conversation_depth, int) or conversation_depth < 1:
        issues.append(ValidationIssue(case_id, "conversation_depth must be an integer >= 1"))

    return issues


def summarize_issues(issues: list[ValidationIssue]) -> str:
    """Format validation failures for CLI/test output."""

    return "\n".join(f"- {issue.case_id}: {issue.message}" for issue in issues)

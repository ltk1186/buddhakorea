from backend.app.rag_regression import (
    load_golden_cases,
    summarize_issues,
    validate_chat_response,
)


def test_default_golden_cases_load():
    cases = load_golden_cases()

    assert len(cases) >= 3
    assert all(case["id"] for case in cases)
    assert all(case["request"]["query"] for case in cases)


def test_validate_chat_response_accepts_valid_payload():
    case = {
        "id": "normal_four_noble_truths_ko",
        "expect": {
            "min_response_chars": 20,
            "min_sources": 1,
            "required_any_terms": ["사성제"],
            "forbid_markdown_headers": True,
            "max_latency_ms": 1000,
        },
    }
    response = {
        "response": "사성제는 고, 집, 멸, 도로 설명되는 핵심 가르침입니다.",
        "sources": [
            {
                "title": "잡아함경",
                "text_id": "T02n0099",
                "excerpt": "고와 그 원인에 대한 문헌 내용",
                "metadata": {"sutra_id": "T02n0099"},
            }
        ],
        "model": "gemini-2.5-pro",
        "latency_ms": 500,
        "session_id": "abc",
        "can_followup": True,
        "conversation_depth": 1,
    }

    assert validate_chat_response(case, response) == []


def test_validate_chat_response_reports_quality_failures():
    case = {
        "id": "broken_case",
        "expect": {
            "min_response_chars": 20,
            "min_sources": 1,
            "required_any_terms": ["무상"],
            "expected_source_text_ids": ["T01n0001"],
            "forbid_markdown_headers": True,
            "max_latency_ms": 1000,
        },
    }
    response = {
        "response": "# Heading\n짧음",
        "sources": [{"title": "", "text_id": "T02n0099", "excerpt": ""}],
        "model": "",
        "latency_ms": 2000,
        "session_id": "",
        "can_followup": False,
        "conversation_depth": 0,
    }

    issues = validate_chat_response(case, response)
    summary = summarize_issues(issues)

    assert len(issues) >= 8
    assert "response contains markdown heading syntax" in summary
    assert "expected source text_id(s) not found" in summary
    assert "latency_ms 2000 exceeds 1000" in summary

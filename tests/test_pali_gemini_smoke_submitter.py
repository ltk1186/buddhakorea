import json
from decimal import Decimal
from pathlib import Path

import pytest

from backend.pali.scripts.submit_gemini_smoke_batch import (
    DEFAULT_MODEL,
    PreflightResult,
    build_inline_request_from_provider_line,
    build_summary,
    parse_batch_results,
    preflight_smoke_batch,
)
from backend.pali.translation.prompts import KOREAN_ADVANCED_PROMPT_VERSION
from backend.pali.translation.budget import PriceProfile


def price_profile() -> PriceProfile:
    return PriceProfile(
        input_usd_per_million_tokens=Decimal("1"),
        output_usd_per_million_tokens=Decimal("6"),
        thinking_usd_per_million_tokens=Decimal("6"),
        batch_discount_multiplier=Decimal("1"),
    )


def provider_line(key: str, text: str = "Evaṃ me sutaṃ.") -> dict:
    return {
        "key": key,
        "request": {
            "contents": [
                {
                    "role": "user",
                    "parts": [
                        {
                            "text": f"빠알리 원문:\n<<<\n{text}\n>>>",
                        }
                    ],
                }
            ],
            "generation_config": {
                "temperature": 0.2,
                "response_mime_type": "application/json",
            },
        },
    }


def manifest(count: int = 1) -> dict:
    return {
        "model": DEFAULT_MODEL,
        "request_count": count,
        "estimated_input_tokens_total": 1000,
        "estimated_output_tokens_total": 3000,
        "estimated_cost_usd_total": "0.019000",
        "prompt_template_version": KOREAN_ADVANCED_PROMPT_VERSION,
        "validation": {"valid": True, "errors": []},
        "items": [
            {
                "stable_segment_key": f"seg-{index}",
                "source_text_hash": f"hash-{index}",
                "text_layer": "mula",
                "chunk_type": "prose",
                "estimated_cost_usd": "0.001000",
            }
            for index in range(count)
        ],
    }


def valid_translation() -> dict:
    return {
        "literal_ko": "이와 같이 나에 의해 들렸다.",
        "natural_ko": "나는 이와 같이 들었다.",
        "terms": [],
        "grammar_notes": [],
        "doctrinal_notes": [],
        "uncertainties": [],
        "quality_flags": [],
    }


def result_line(key: str, text: str | None = None, *, usage: bool = True) -> dict:
    response = {
        "candidates": [
            {
                "content": {
                    "parts": [
                        {
                            "text": text if text is not None else json.dumps(valid_translation(), ensure_ascii=False),
                        }
                    ]
                }
            }
        ]
    }
    if usage:
        response["usageMetadata"] = {
            "promptTokenCount": 100,
            "candidatesTokenCount": 50,
            "thoughtsTokenCount": 10,
            "cachedContentTokenCount": 0,
            "totalTokenCount": 160,
        }
    return {"metadata": {"key": key}, "response": response}


def test_preflight_blocks_request_count_over_five():
    lines = [provider_line(f"seg-{index}") for index in range(6)]
    result = preflight_smoke_batch(
        provider_lines=lines,
        manifest=manifest(6),
        model=DEFAULT_MODEL,
        price_profile=price_profile(),
        hard_cap_usd=Decimal("5"),
    )

    assert result.valid is False
    assert any("request_count" in error for error in result.errors)


def test_preflight_allows_approved_75_pilot_count():
    lines = [provider_line(f"seg-{index}") for index in range(75)]
    doc = manifest(75)
    doc["estimated_input_tokens_total"] = 205501
    doc["estimated_output_tokens_total"] = 25859
    doc["estimated_cost_usd_total"] = "0.760249"
    result = preflight_smoke_batch(
        provider_lines=lines,
        manifest=doc,
        model=DEFAULT_MODEL,
        price_profile=price_profile(),
        hard_cap_usd=Decimal("50"),
        expected_request_count=75,
        max_request_count=75,
    )

    assert result.valid is True


def test_preflight_blocks_pilot_request_count_mismatch():
    lines = [provider_line(f"seg-{index}") for index in range(74)]
    result = preflight_smoke_batch(
        provider_lines=lines,
        manifest=manifest(74),
        model=DEFAULT_MODEL,
        price_profile=price_profile(),
        hard_cap_usd=Decimal("50"),
        expected_request_count=75,
        max_request_count=75,
    )

    assert result.valid is False
    assert any("exactly 75" in error for error in result.errors)


def test_preflight_blocks_budget_cap_exceeded():
    doc = manifest(1)
    doc["estimated_cost_usd_total"] = "6"
    result = preflight_smoke_batch(
        provider_lines=[provider_line("seg-0")],
        manifest=doc,
        model=DEFAULT_MODEL,
        price_profile=price_profile(),
        hard_cap_usd=Decimal("5"),
    )

    assert result.valid is False
    assert any("hard cap" in error for error in result.errors)


def test_preflight_blocks_model_mismatch():
    doc = manifest(1)
    doc["model"] = "models/gemini-2.5-pro"
    result = preflight_smoke_batch(
        provider_lines=[provider_line("seg-0")],
        manifest=doc,
        model="models/gemini-2.5-pro",
        price_profile=price_profile(),
        hard_cap_usd=Decimal("5"),
    )

    assert result.valid is False
    assert any("model mismatch" in error for error in result.errors)


def test_preflight_blocks_prompt_version_mismatch():
    doc = manifest(1)
    doc["prompt_template_version"] = "placeholder"
    result = preflight_smoke_batch(
        provider_lines=[provider_line("seg-0")],
        manifest=doc,
        model=DEFAULT_MODEL,
        price_profile=price_profile(),
        hard_cap_usd=Decimal("5"),
    )

    assert result.valid is False
    assert any("prompt_template_version" in error for error in result.errors)


def test_preflight_blocks_credential_marker():
    line = provider_line("seg-0", "AIza credential marker")
    result = preflight_smoke_batch(
        provider_lines=[line],
        manifest=manifest(1),
        model=DEFAULT_MODEL,
        price_profile=price_profile(),
        hard_cap_usd=Decimal("5"),
    )

    assert result.valid is False
    assert any("credential" in error for error in result.errors)


def test_provider_line_is_converted_to_rest_inline_request():
    converted = build_inline_request_from_provider_line(provider_line("seg-0"))

    assert converted["metadata"]["key"] == "seg-0"
    assert "generationConfig" in converted["request"]
    assert "generation_config" not in converted["request"]


def test_parse_result_maps_by_key_and_validates_schema():
    parsed = parse_batch_results(
        raw_lines=[result_line("seg-0")],
        provider_lines=[provider_line("seg-0")],
        manifest=manifest(1),
        price_profile=price_profile(),
    )

    item = parsed["items"][0]
    assert item["stable_segment_key"] == "seg-0"
    assert item["schema_valid"] is True
    assert item["status"] == "succeeded"
    assert item["prompt_token_count"] == 100
    assert item["candidates_token_count"] == 50
    assert item["thoughts_token_count"] == 10
    assert Decimal(item["actual_cost_usd"]) == Decimal("0.000460")


def test_parse_result_distinguishes_error_object():
    parsed = parse_batch_results(
        raw_lines=[{"metadata": {"key": "seg-0"}, "error": {"code": 429, "message": "rate limit"}}],
        provider_lines=[provider_line("seg-0")],
        manifest=manifest(1),
        price_profile=price_profile(),
    )

    item = parsed["items"][0]
    assert item["status"] == "failed"
    assert item["schema_valid"] is False
    assert "rate limit" in item["error_message"]


def test_invalid_json_output_is_parse_failed():
    parsed = parse_batch_results(
        raw_lines=[result_line("seg-0", text="not json")],
        provider_lines=[provider_line("seg-0")],
        manifest=manifest(1),
        price_profile=price_profile(),
    )

    item = parsed["items"][0]
    assert item["status"] == "schema_invalid"
    assert item["local_validator_flags"] == ["json_parse_failed"]


def test_valid_json_with_extra_field_is_schema_invalid():
    payload = {**valid_translation(), "english_translation": "not allowed"}
    parsed = parse_batch_results(
        raw_lines=[result_line("seg-0", text=json.dumps(payload))],
        provider_lines=[provider_line("seg-0")],
        manifest=manifest(1),
        price_profile=price_profile(),
    )

    item = parsed["items"][0]
    assert item["status"] == "schema_invalid"
    assert item["local_validator_flags"] == ["schema_validation_failed"]


def test_build_summary_includes_pilot_distribution_and_failure_causes():
    parsed = parse_batch_results(
        raw_lines=[
            result_line("seg-0"),
            result_line("seg-1", text="not json"),
        ],
        provider_lines=[
            provider_line("seg-0"),
            provider_line("seg-1"),
        ],
        manifest=manifest(2),
        price_profile=price_profile(),
    )

    summary = build_summary(
        parsed=parsed,
        manifest=manifest(2),
        model=DEFAULT_MODEL,
        provider_batch_id="batches/test",
        preflight=PreflightResult(
            valid=True,
            errors=[],
            warnings=[],
            estimated_cost_usd=Decimal("0.01"),
        ),
        price_profile=price_profile(),
        price_profile_id="test",
        price_profile_raw={"profile_id": "test"},
        raw_result_path="/tmp/raw.jsonl",
        parsed_result_path="/tmp/parsed.json",
        final_status={"name": "batches/test", "done": True},
    )

    assert summary["request_count"] == 2
    assert summary["schema_valid_count"] == 1
    assert summary["parse_failed_count"] == 1
    assert summary["average_output_tokens_per_segment"] == 50
    assert summary["average_thinking_tokens_per_segment"] == 10
    assert summary["result_distribution"]["text_layer"] == {"mula": 2}
    assert summary["failed_item_causes"][0]["stable_segment_key"] == "seg-1"
    assert summary["needs_review_items"][0]["local_validator_flags"] == ["json_parse_failed"]

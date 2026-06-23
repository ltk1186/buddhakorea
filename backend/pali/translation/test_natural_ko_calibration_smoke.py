from __future__ import annotations

import json
from decimal import Decimal
from pathlib import Path

import pytest

from backend.pali.translation.budget import PriceProfile
from backend.pali.translation.natural_ko_calibration_smoke import (
    NaturalKoSmokeBlocked,
    compare_parsed_arms,
    finalize_recommendation,
    parse_arm,
    prompt_requests_reader_ko,
    run_preflight,
    smoke_paths,
    submit_smoke,
    validate_preflight,
    write_json,
    write_jsonl,
)
from backend.pali.translation.natural_ko_readability import (
    audit_items,
    build_request_previews,
    select_calibration_items,
)
from backend.pali.translation.test_natural_ko_readability import item


def fixture_selection() -> dict:
    rows = []
    for layer in ("mula", "atthakatha", "tika"):
        for index in range(10):
            literal = natural = f"{layer} 같은 문장 {index}." if index < 3 else f"{layer} 문장 {index}."
            source_path = f"romn/{layer}{index}.xml"
            if index in {2, 3}:
                source_path = f"romn/abh{layer}{index}.xml"
            rows.append(
                item(
                    f"{layer}-{index}",
                    layer,
                    literal,
                    natural,
                    source_path=source_path,
                    original="1. dhammo; 2. dhammo" if index in {2, 3} else "Evaṃ me sutaṃ.",
                    length="short" if index in {2, 3} else "medium",
                )
            )
    audit = audit_items(rows, Path("fixture.md"))
    return select_calibration_items(audit)


def write_selection(out: Path, selection: dict | None = None) -> dict:
    paths = smoke_paths(out)
    paths.out_dir.mkdir(parents=True, exist_ok=True)
    selection = selection or fixture_selection()
    write_json(paths.selection, selection, pretty=True)
    return selection


def test_preflight_passes_and_preserves_source_text_hash(tmp_path: Path) -> None:
    selection = write_selection(tmp_path)
    preflight = run_preflight(out_dir=tmp_path, pretty=True)
    paths = smoke_paths(tmp_path)
    arm_a = [json.loads(line) for line in paths.arm_a_jsonl.read_text(encoding="utf-8").splitlines()]
    assert preflight["status"] == "PASS"
    assert preflight["planned_provider_requests"] == 60
    assert preflight["cap_passed_before_submit"] is True
    assert arm_a[0]["metadata"]["source_text_hash"] == selection["items"][0]["source_text_hash"]
    assert "Do not add `reader_ko`" in paths.prompt_variant.read_text(encoding="utf-8")


def test_prompt_requests_reader_ko_allows_negative_and_blocks_positive() -> None:
    assert prompt_requests_reader_ko("Do not add `reader_ko`.") is False
    assert prompt_requests_reader_ko("reader_ko is not being added") is False
    assert prompt_requests_reader_ko("reader_ko: not added") is False
    assert prompt_requests_reader_ko("Please add reader_ko to the output.") is True
    assert prompt_requests_reader_ko("Create `reader_ko` as a third field.") is True
    assert prompt_requests_reader_ko("Output reader_ko in the JSON.") is True


def test_preflight_fails_if_arm_counts_or_total_are_wrong() -> None:
    selection = fixture_selection()
    arm_a, arm_b = build_request_previews(selection)
    errors, _ = validate_preflight(selection, arm_a[:-1], arm_b)
    assert any(error.startswith("BLOCKED_ARM_A_REQUEST_COUNT_29") for error in errors)
    assert any(error.startswith("BLOCKED_TOTAL_REQUEST_COUNT_59") for error in errors)


def test_preflight_fails_if_response_schema_missing_or_reader_ko_present() -> None:
    selection = fixture_selection()
    arm_a, arm_b = build_request_previews(selection)
    del arm_a[0]["request"]["generation_config"]["response_schema"]
    errors, _ = validate_preflight(selection, arm_a, arm_b)
    assert any(error.startswith("BLOCKED_MISSING_RESPONSE_SCHEMA") for error in errors)
    arm_a, arm_b = build_request_previews(selection)
    arm_b[0]["request"]["generation_config"]["response_schema"]["properties"]["reader_ko"] = {"type": "string"}
    errors, _ = validate_preflight(selection, arm_a, arm_b)
    assert any(error.startswith("BLOCKED_READER_KO_IN_RESPONSE_SCHEMA") for error in errors)


def test_preflight_fails_if_prompt_positively_requests_reader_ko() -> None:
    selection = fixture_selection()
    arm_a, arm_b = build_request_previews(selection)
    arm_b[0]["request"]["contents"][0]["parts"][0]["text"] += "\nPlease add reader_ko to the output JSON."
    errors, _ = validate_preflight(selection, arm_a, arm_b)
    assert "BLOCKED_READER_KO_IN_PROMPT" in errors


def test_preflight_fails_if_source_text_hash_key_is_dropped() -> None:
    selection = fixture_selection()
    del selection["items"][0]["source_text_hash"]
    arm_a, arm_b = build_request_previews(selection)
    errors, _ = validate_preflight(selection, arm_a, arm_b)
    assert any(error.startswith("BLOCKED_SELECTION_DROPPED_SOURCE_TEXT_HASH") for error in errors)


def test_preflight_checks_prompt_override_and_generation_config_parity() -> None:
    selection = fixture_selection()
    arm_a, arm_b = build_request_previews(selection)
    errors, _ = validate_preflight(selection, arm_a, arm_b)
    assert not errors
    a_prompt = arm_a[0]["request"]["contents"][0]["parts"][0]["text"]
    b_prompt = arm_b[0]["request"]["contents"][0]["parts"][0]["text"]
    assert "NATURAL_KO_V2_CALIBRATION_INSTRUCTION" not in a_prompt
    assert "NATURAL_KO_V2_CALIBRATION_INSTRUCTION" in b_prompt
    assert "natural_ko 작성 원칙:\n- 독자용 자연역입니다." in a_prompt
    assert "natural_ko 작성 원칙:\n- 독자용 자연역입니다." not in b_prompt
    assert "용어 정책:" in b_prompt
    arm_b[0]["request"]["generation_config"]["temperature"] = 0.9
    errors, _ = validate_preflight(selection, arm_a, arm_b)
    assert any(error.startswith("BLOCKED_GENERATION_CONFIG_MISMATCH") for error in errors)


class ExplodingClient:
    def create_inline_batch(self, **kwargs):  # pragma: no cover - should not be called
        raise AssertionError("provider call should be blocked")


def test_duplicate_submission_is_blocked_if_provider_ids_exist(tmp_path: Path) -> None:
    write_selection(tmp_path)
    paths = smoke_paths(tmp_path)
    write_json(paths.provider_status_arm_a, {"provider_batch_id": "batches/existing"}, pretty=True)
    with pytest.raises(NaturalKoSmokeBlocked) as exc:
        submit_smoke(out_dir=tmp_path, client=ExplodingClient())  # type: ignore[arg-type]
    assert exc.value.status == "BLOCKED_ALREADY_SUBMITTED"


def raw_result(key: str, payload: dict) -> dict:
    return {
        "metadata": {"key": key},
        "response": {
            "candidates": [{"content": {"parts": [{"text": json.dumps(payload, ensure_ascii=False)}]}}],
            "usageMetadata": {
                "promptTokenCount": 10,
                "candidatesTokenCount": 20,
                "thoughtsTokenCount": 30,
                "totalTokenCount": 60,
            },
        },
    }


def translation(literal: str, natural: str, terms: list[dict] | None = None) -> dict:
    return {
        "literal_ko": literal,
        "natural_ko": natural,
        "terms": terms or [],
        "grammar_notes": [],
        "doctrinal_notes": [],
        "uncertainties": [],
        "quality_flags": [],
    }


def test_parse_preserves_identity_metadata() -> None:
    selection = fixture_selection()
    arm_a, _ = build_request_previews(selection)
    key = selection["items"][0]["stable_segment_key"]
    parsed = parse_arm(
        raw_lines=[raw_result(key, translation("직역입니다.", "자연역입니다."))],
        provider_lines=arm_a[:1],
        selection={"items": selection["items"][:1]},
        price_profile=PriceProfile(Decimal("1"), Decimal("6"), Decimal("6")),
        arm="A_prime",
    )
    parsed_item = parsed["items"][0]
    assert parsed_item["stable_segment_key"] == key
    assert parsed_item["source_path"] == selection["items"][0]["source_path"]
    assert parsed_item["source_text_hash"] == selection["items"][0]["source_text_hash"]
    assert parsed_item["text_layer"] == selection["items"][0]["text_layer"]
    assert parsed_item["chunk_type"] == selection["items"][0]["chunk_type"]
    assert parsed_item["length_bucket"] == selection["items"][0]["length_bucket"]


def parsed_arm(items: list[dict], arm: str) -> dict:
    return {"arm": arm, "items": items}


def parsed_item(key: str, role: str, literal: str, natural: str, *, layer: str = "mula") -> dict:
    return {
        "stable_segment_key": key,
        "source_path": f"romn/{key}.xml",
        "source_text_hash": f"hash-{key}",
        "text_layer": layer,
        "chunk_type": "prose",
        "length_bucket": "medium",
        "calibration_role": role,
        "original_text": "Evaṃ me sutaṃ.",
        "literal_ko": literal,
        "natural_ko": natural,
        "terms": [{"pali": "sati", "ko": "마음챙김", "gloss": "", "note": ""}],
        "grammar_notes": [],
        "doctrinal_notes": [],
        "uncertainties": [],
        "quality_flags": [],
        "schema_valid": True,
        "parse_method": "strict_json",
        "actual_cost_usd": "0.001000",
    }


def test_compare_computes_deltas_literal_warnings_and_roles() -> None:
    a_items = [
        parsed_item("a", "improvement_target", "직역입니다.", "직역입니다."),
        parsed_item("b", "convergence_control", "첫째 법 둘째 법입니다.", "첫째 법 둘째 법입니다."),
    ]
    b_items = [
        parsed_item("a", "improvement_target", "완전히 다른 직역입니다.", "읽기 쉬운 자연역입니다."),
        parsed_item("b", "convergence_control", "첫째 법 둘째 법입니다.", "매우 다르게 풀어쓴 긴 자연역입니다."),
    ]
    comparison = compare_parsed_arms(parsed_arm(a_items, "A_prime"), parsed_arm(b_items, "B_natural_ko_v2"))
    assert comparison["paired_count"] == 2
    assert "avg_similarity_delta_b_minus_a" in comparison["delta_metrics"]
    assert comparison["role_delta_metrics"]["improvement_target"]
    assert any("literal_similarity_drift_warning" in item["warnings"] for item in comparison["pair_checks"])
    assert any("control_forced_divergence_warning" in item["warnings"] for item in comparison["pair_checks"])


def test_compare_reports_unpaired_keys() -> None:
    a = parsed_arm([parsed_item("a", "improvement_target", "직역", "자연")], "A_prime")
    b = parsed_arm([parsed_item("b", "improvement_target", "직역", "자연")], "B_natural_ko_v2")
    comparison = compare_parsed_arms(a, b)
    assert comparison["paired_count"] == 0
    assert comparison["missing_in_a_prime"] == ["b"]
    assert comparison["missing_in_b_v2"] == ["a"]


def test_finalize_pending_operator_review_without_human_review(tmp_path: Path) -> None:
    paths = smoke_paths(tmp_path)
    paths.out_dir.mkdir(parents=True, exist_ok=True)
    comparison = compare_parsed_arms(
        parsed_arm([parsed_item(str(i), "improvement_target", "직역", "자연") for i in range(30)], "A_prime"),
        parsed_arm([parsed_item(str(i), "improvement_target", "직역", "더 자연스러운 문장") for i in range(30)], "B_natural_ko_v2"),
    )
    write_json(paths.comparison_json, comparison, pretty=True)
    result = finalize_recommendation(out_dir=tmp_path, pretty=True)
    assert result["recommendation"]["decision"] == "pending_operator_readability_review"

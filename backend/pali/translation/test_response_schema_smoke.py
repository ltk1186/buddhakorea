from __future__ import annotations

import json
from decimal import Decimal
from pathlib import Path

import pytest

from backend.pali.scripts.run_response_schema_smoke import Step4Blocked, build_parser, run
from backend.pali.translation.response_schema_smoke import (
    build_arm_jsonl,
    build_response_schema_experiment,
    build_run_manifest,
    compare_arms,
    estimate_step4_cost,
    recommendation_from_metrics,
    select_step4_items,
)


def write_json(path: Path, payload: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")


def write_jsonl(path: Path, rows: list[dict]) -> None:
    path.write_text("\n".join(json.dumps(row, ensure_ascii=False) for row in rows) + "\n", encoding="utf-8")


def fixture_payloads(count: int = 60) -> tuple[dict, dict, dict, list[dict]]:
    parsed_items = []
    cost_items = []
    manifest_items = []
    provider_lines = []
    for index in range(count):
        key = f"vri:romn:test:{index:04d}"
        if index < 18:
            parse_method = "raw_decode"
        elif index < 34:
            parse_method = "stack_reclose"
        else:
            parse_method = "strict_json"
        layer = "tika" if index % 2 == 0 else "atthakatha"
        chunk = "verse" if index % 7 == 0 else "prose"
        length = "long" if index % 3 else "medium"
        source = "Tassāti dussīlassa. ma. ni. 1.55. " * (4 + index % 5)
        parsed_items.append(
            {
                "stable_segment_key": key,
                "source_text_hash": f"hash-{index}",
                "source_path": f"romn/test{index:04d}.xml",
                "text_layer": layer,
                "chunk_type": chunk,
                "length_bucket": length,
                "status": "succeeded",
                "schema_valid": True,
                "parse_method": parse_method,
                "original_text": source,
                "literal_ko": "직역 번역입니다.",
                "natural_ko": "자연스러운 번역입니다.",
                "terms": [{"pali": "sati", "ko": "마음챙김", "gloss": "", "note": ""}] if index % 4 == 0 else [],
                "grammar_notes": ["문법 메모"] if index % 5 == 0 else [],
                "doctrinal_notes": [],
                "uncertainties": ["불확실"] if index % 6 == 0 else [],
                "quality_flags": [],
            }
        )
        cost_items.append(
            {
                "stable_segment_key": key,
                "source_text_hash": f"hash-{index}",
                "source_path": f"romn/test{index:04d}.xml",
                "text_layer": layer,
                "chunk_type": chunk,
                "length_bucket": length,
                "selection_group": "hard" if index % 2 == 0 else "representative",
                "selection_bucket": "tika_long" if layer == "tika" else "atthakatha_long",
                "expected_mean": {
                    "input_tokens": 100,
                    "output_tokens": 50,
                    "thinking_tokens": 100,
                    "official_cost_usd": "0.001000",
                },
                "planning_p90": {
                    "input_tokens": 120,
                    "output_tokens": 60,
                    "thinking_tokens": 120,
                    "official_cost_usd": "0.001200",
                },
            }
        )
        manifest_items.append(
            {
                "stable_segment_key": key,
                "source_text_hash": f"hash-{index}",
                "source_path": f"romn/test{index:04d}.xml",
                "text_layer": layer,
                "chunk_type": chunk,
                "length_bucket": length,
                "selection_group": "hard",
                "selection_bucket": "tika_long",
                "jsonl_line_index": index,
            }
        )
        provider_lines.append(
            {
                "key": key,
                "request": {
                    "contents": [{"role": "user", "parts": [{"text": f"prompt {index}\n빠알리 원문:\n<<<\n{source}\n>>>"}]}],
                    "generation_config": {"response_mime_type": "application/json", "temperature": 0.2},
                },
            }
        )
    return (
        {"items": parsed_items},
        {"items": cost_items},
        {"items": manifest_items, "request_count": count},
        provider_lines,
    )


def write_fixture_files(tmp_path: Path) -> dict[str, Path]:
    parsed, cost, manifest, provider_lines = fixture_payloads()
    paths = {
        "parsed": tmp_path / "parsed_salvaged.json",
        "cost": tmp_path / "cost_estimate.json",
        "manifest": tmp_path / "jsonl_manifest.json",
        "jsonl": tmp_path / "batch.jsonl",
        "out": tmp_path / "out",
    }
    write_json(paths["parsed"], parsed)
    write_json(paths["cost"], cost)
    write_json(paths["manifest"], manifest)
    write_jsonl(paths["jsonl"], provider_lines)
    return paths


def test_deterministic_selection_same_seed() -> None:
    parsed, cost, manifest, _ = fixture_payloads()
    first = select_step4_items(parsed_salvaged=parsed, cost_estimate=cost, jsonl_manifest=manifest, seed="same")
    second = select_step4_items(parsed_salvaged=parsed, cost_estimate=cost, jsonl_manifest=manifest, seed="same")
    assert [item["stable_segment_key"] for item in first["items"]] == [
        item["stable_segment_key"] for item in second["items"]
    ]
    assert first["known_strict_parse_failure_count"] == 34
    assert first["vulnerable_strict_passed_count"] == 16


def test_response_schema_smoke_module_does_not_use_builtin_hash() -> None:
    source = Path("backend/pali/translation/response_schema_smoke.py").read_text(encoding="utf-8")
    assert "hash(" not in source
    assert "hashlib.sha256" in source


def test_selection_blocks_when_34_known_failures_missing() -> None:
    parsed, cost, manifest, _ = fixture_payloads()
    parsed["items"][0]["parse_method"] = "strict_json"
    selection = select_step4_items(parsed_salvaged=parsed, cost_estimate=cost, jsonl_manifest=manifest)
    assert selection["selection_readiness"] == "BLOCKED_SELECTION_INCOMPLETE"


def test_arm_b_schema_added_without_prompt_change() -> None:
    parsed, cost, manifest, provider_lines = fixture_payloads()
    selection = select_step4_items(parsed_salvaged=parsed, cost_estimate=cost, jsonl_manifest=manifest)
    schema = build_response_schema_experiment()
    arm_a, arm_b = build_arm_jsonl(selection_manifest=selection, provider_lines=provider_lines, response_schema_payload=schema)
    assert arm_a[0]["request"]["contents"] == arm_b[0]["request"]["contents"]
    assert "response_schema" not in arm_a[0]["request"]["generation_config"]
    assert arm_b[0]["request"]["generation_config"]["response_schema"]["properties"]["literal_ko"]["type"] == "string"
    assert arm_b[0]["request"]["generation_config"]["response_schema"]["properties"]["terms"]["items"]["type"] == "object"


def test_cost_cap_blocks_submit_before_credentials(tmp_path: Path) -> None:
    paths = write_fixture_files(tmp_path)
    args = build_parser().parse_args(
        [
            "--submit",
            "--parsed-salvaged",
            str(paths["parsed"]),
            "--cost-estimate-input",
            str(paths["cost"]),
            "--jsonl",
            str(paths["jsonl"]),
            "--jsonl-manifest",
            str(paths["manifest"]),
            "--out",
            str(paths["out"]),
            "--hard-cap-usd",
            "0.000001",
        ]
    )
    with pytest.raises(Step4Blocked) as exc:
        run(args)
    assert exc.value.status == "BLOCKED_OVER_HARD_CAP"


def test_default_mode_writes_dry_run_without_submit(tmp_path: Path) -> None:
    paths = write_fixture_files(tmp_path)
    args = build_parser().parse_args(
        [
            "--parsed-salvaged",
            str(paths["parsed"]),
            "--cost-estimate-input",
            str(paths["cost"]),
            "--jsonl",
            str(paths["jsonl"]),
            "--jsonl-manifest",
            str(paths["manifest"]),
            "--out",
            str(paths["out"]),
            "--pretty",
        ]
    )
    result = run(args)
    assert result["api_llm_calls"] == 0
    manifest = json.loads((paths["out"] / "run_manifest.json").read_text(encoding="utf-8"))
    assert manifest["submitted"] is False
    assert manifest["batch_requests_submitted"] == 0
    assert manifest["silver_canary_status"] == "advisory_only_not_gold_accuracy"
    assert (paths["out"] / "arm_a_batch_input.jsonl").exists()
    assert (paths["out"] / "arm_b_batch_input.jsonl").exists()


def test_content_suppression_flags_and_recommendation() -> None:
    arm_a = {
        "items": [
            {
                "stable_segment_key": "k1",
                "schema_valid": True,
                "parse_method": "strict_json",
                "literal_ko": "가" * 100,
                "natural_ko": "나" * 100,
                "terms": [{"pali": "sati"}] * 3,
                "grammar_notes": ["a"],
                "doctrinal_notes": [],
                "uncertainties": [],
                "quality_flags": [],
            }
        ]
    }
    arm_b = {
        "items": [
            {
                "stable_segment_key": "k1",
                "schema_valid": True,
                "parse_method": "strict_json",
                "literal_ko": "짧음",
                "natural_ko": "짧음",
                "terms": [],
                "grammar_notes": [],
                "doctrinal_notes": [],
                "uncertainties": [],
                "quality_flags": [],
            }
        ]
    }
    comparison = compare_arms(arm_a, arm_b)
    flags = comparison["content_suppression_flag_counts"]
    assert flags["arm_b_literal_much_shorter"] == 1
    assert flags["arm_b_terms_dropped"] == 1
    assert comparison["recommendation"]["decision"] == "keep_current_free_form_json_plus_salvage_cascade"


def test_provider_rejection_is_valid_recommendation_state() -> None:
    rec = recommendation_from_metrics({}, {}, {}, arm_b_status="provider_rejected_response_schema")
    assert rec["decision"] == "keep_current_free_form_json_plus_salvage_cascade"
    assert "rejected" in rec["reason"]


def test_run_manifest_invariants() -> None:
    manifest = build_run_manifest(batch_requests_planned=100, cost_estimate=None)
    assert manifest["prompt_mutation"] is False
    assert manifest["glossary_mutation"] is False
    assert manifest["gold_set_mutation"] is False
    assert manifest["schema_file_mutation"] is False
    assert manifest["translation_corpus_mutation"] is False
    assert manifest["production_prompt_changed"] is False
    assert manifest["holdout_gold_frozen"] is False
    assert manifest["silver_canary_status"] == "advisory_only_not_gold_accuracy"
    assert manifest["silver_canary_needs_pali_expert_policy"] == "needs_review_not_fail"


def test_estimate_step4_cost_passes_normal_cap() -> None:
    parsed, cost, manifest, _ = fixture_payloads()
    selection = select_step4_items(parsed_salvaged=parsed, cost_estimate=cost, jsonl_manifest=manifest)
    estimate = estimate_step4_cost(selection_manifest=selection, hard_cap_usd=Decimal("4"))
    assert estimate["total_request_count"] == 100
    assert estimate["cap_passed_before_submit"] is True


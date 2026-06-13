import json
from decimal import Decimal
from pathlib import Path

import pytest

from backend.pali.scripts.plan_gemini_smoke_batch import (
    plan_gemini_smoke_batch,
    validate_smoke_batch,
)
from backend.pali.translation.prompts import (
    KOREAN_ADVANCED_PROMPT_ID,
    KOREAN_ADVANCED_PROMPT_VERSION,
)


def write_json(path: Path, data: dict) -> None:
    path.write_text(json.dumps(data), encoding="utf-8")


def sample(key: str, layer: str, chunk: str, length: str, estimate: int = 40) -> dict:
    return {
        "sample_type": "translation_pilot",
        "stable_segment_key": key,
        "source_text_hash": f"hash-{key}",
        "source_path": "romn/s0505m.mul.xml",
        "text_layer": layer,
        "pitaka": "sutta",
        "nikaya": "Khuddakanikāye",
        "chunk_type": chunk,
        "length_bucket": length,
        "char_count": 120,
        "token_estimates_by_profile": {"gemini_local_approx": estimate},
        "original_text": f"Evaṃ me sutaṃ {key}.",
    }


def samples_artifact() -> dict:
    return {
        "source_commit": "49bc86914748589a2501b548cc6b3e97a8abe018",
        "pilot_samples": [
            sample("seg-mula", "mula", "prose", "short"),
            sample("seg-att", "atthakatha", "verse", "medium"),
            sample("seg-tika", "tika", "prose", "short"),
            sample("seg-extra-1", "mula", "verse", "medium"),
            sample("seg-extra-2", "atthakatha", "prose", "long"),
        ],
    }


def calibration_artifact() -> dict:
    return {
        "aggregate_totals": {
            "recommended_source_correction_factor": {
                "overall": 1.7,
                "by_text_layer": {
                    "mula": 1.6,
                    "atthakatha": 1.8,
                    "tika": 1.7,
                },
            },
            "average_prompt_overhead_tokens": 106,
        }
    }


def prompt_token_calibration_artifact() -> dict:
    return {
        "prompt_template_id": KOREAN_ADVANCED_PROMPT_ID,
        "prompt_template_version": KOREAN_ADVANCED_PROMPT_VERSION,
        "average_prompt_v1_overhead_tokens": 600,
        "overhead_by_text_layer": {
            "mula": {"average_prompt_v1_overhead_tokens": 500},
            "atthakatha": {"average_prompt_v1_overhead_tokens": 700},
            "tika": {"average_prompt_v1_overhead_tokens": 900},
        },
    }


def price_profile() -> dict:
    return {
        "profiles": [
            {
                "profile_id": "test",
                "input_usd_per_million_tokens": "10",
                "output_usd_per_million_tokens": "20",
                "thinking_usd_per_million_tokens": "0",
                "batch_discount_multiplier": "0.5",
            }
        ]
    }


def test_smoke_batch_planner_writes_jsonl_and_manifest(tmp_path: Path):
    samples = tmp_path / "samples.json"
    calibration = tmp_path / "calibration.json"
    prompt_calibration = tmp_path / "prompt_calibration.json"
    profile = tmp_path / "price.json"
    out_jsonl = tmp_path / "smoke.jsonl"
    out_manifest = tmp_path / "manifest.json"
    write_json(samples, samples_artifact())
    write_json(calibration, calibration_artifact())
    write_json(prompt_calibration, prompt_token_calibration_artifact())
    write_json(profile, price_profile())

    manifest = plan_gemini_smoke_batch(
        samples_path=samples,
        out_jsonl_path=out_jsonl,
        out_manifest_path=out_manifest,
        model="models/gemini-3.1-pro-preview",
        max_segments=5,
        max_estimated_cost_usd=Decimal("5"),
        price_profile_path=profile,
        price_profile_id="test",
        calibration_path=calibration,
        prompt_token_calibration_path=prompt_calibration,
        pretty_manifest=True,
    )

    lines = [json.loads(line) for line in out_jsonl.read_text().splitlines()]
    manifest_data = json.loads(out_manifest.read_text())
    assert 3 <= len(lines) <= 5
    assert len(lines) == manifest["request_count"] == len(manifest_data["items"])
    assert [line["key"] for line in lines] == [
        item["stable_segment_key"] for item in manifest_data["items"]
    ]
    assert {item["text_layer"] for item in manifest_data["items"]} >= {
        "mula",
        "atthakatha",
        "tika",
    }
    assert {item["chunk_type"] for item in manifest_data["items"]} >= {"prose", "verse"}
    assert Decimal(manifest["estimated_cost_usd_total"]) > Decimal("0")
    assert manifest["budget_check_result"]["can_submit"] is True
    assert manifest["validation"]["valid"] is True
    assert manifest["prompt_template_id"] == KOREAN_ADVANCED_PROMPT_ID
    assert manifest["prompt_template_version"] == KOREAN_ADVANCED_PROMPT_VERSION
    assert manifest["prompt_overhead_estimate_source"] == "prompt_v1_counttokens"
    assert manifest["prompt_overhead_average_tokens"] == 600
    assert manifest_data["items"][0]["prompt_template_id"] == KOREAN_ADVANCED_PROMPT_ID
    for item in manifest_data["items"]:
        expected_overhead = {
            "mula": 500,
            "atthakatha": 700,
            "tika": 900,
        }[item["text_layer"]]
        assert item["prompt_overhead_source"] == "prompt_v1_counttokens"
        assert item["prompt_overhead_tokens_applied"] == expected_overhead
        assert item["estimated_input_tokens"] >= expected_overhead
    assert "literal_ko 작성 원칙" in lines[0]["request"]["contents"][0]["parts"][0]["text"]
    assert "빠알리 원문:" in lines[0]["request"]["contents"][0]["parts"][0]["text"]
    assert "AIza" not in out_manifest.read_text()


def test_schemafix_artifact_naming_does_not_overwrite_previous_smoke(tmp_path: Path):
    samples = tmp_path / "samples.json"
    calibration = tmp_path / "calibration.json"
    prompt_calibration = tmp_path / "prompt_calibration.json"
    profile = tmp_path / "price.json"
    previous_jsonl = tmp_path / "gemini_smoke_batch_49bc869_prompt_v1.jsonl"
    previous_manifest = tmp_path / "gemini_smoke_batch_49bc869_prompt_v1_manifest.json"
    out_jsonl = tmp_path / "gemini_smoke_batch_49bc869_prompt_v1_schemafix.jsonl"
    out_manifest = tmp_path / "gemini_smoke_batch_49bc869_prompt_v1_schemafix_manifest.json"
    previous_jsonl.write_text("previous-jsonl", encoding="utf-8")
    previous_manifest.write_text("previous-manifest", encoding="utf-8")
    write_json(samples, samples_artifact())
    write_json(calibration, calibration_artifact())
    write_json(prompt_calibration, prompt_token_calibration_artifact())
    write_json(profile, price_profile())

    manifest = plan_gemini_smoke_batch(
        samples_path=samples,
        out_jsonl_path=out_jsonl,
        out_manifest_path=out_manifest,
        model="models/gemini-3.1-pro-preview",
        max_segments=5,
        max_estimated_cost_usd=Decimal("5"),
        price_profile_path=profile,
        price_profile_id="test",
        calibration_path=calibration,
        prompt_token_calibration_path=prompt_calibration,
        prompt_version=KOREAN_ADVANCED_PROMPT_VERSION,
    )

    assert previous_jsonl.read_text() == "previous-jsonl"
    assert previous_manifest.read_text() == "previous-manifest"
    assert out_jsonl.exists()
    assert out_manifest.exists()
    assert "schemafix" in out_jsonl.name
    assert manifest["prompt_template_version"] == KOREAN_ADVANCED_PROMPT_VERSION


def test_budget_cap_exceeded_fails(tmp_path: Path):
    samples = tmp_path / "samples.json"
    profile = tmp_path / "price.json"
    write_json(samples, samples_artifact())
    write_json(profile, price_profile())

    with pytest.raises(RuntimeError, match="Budget check failed"):
        plan_gemini_smoke_batch(
            samples_path=samples,
            out_jsonl_path=tmp_path / "smoke.jsonl",
            out_manifest_path=tmp_path / "manifest.json",
            model="models/gemini-3.1-pro-preview",
            max_segments=5,
            max_estimated_cost_usd=Decimal("0.000001"),
            price_profile_path=profile,
            price_profile_id="test",
        )


def test_duplicate_key_validation_fails():
    line = {
        "key": "dup",
        "request": {"contents": [{"parts": [{"text": "Pāli source:\n<<<x>>>"}]}]},
    }
    manifest = {
        "estimated_cost_usd_total": "0",
        "max_estimated_cost_usd": "5",
        "items": [
            {"stable_segment_key": "dup", "source_text_hash": "a", "jsonl_line_index": 0},
            {"stable_segment_key": "dup", "source_text_hash": "b", "jsonl_line_index": 1},
        ],
    }

    validation = validate_smoke_batch([line, line], manifest)
    assert validation["valid"] is False
    assert any("Duplicate" in error for error in validation["errors"])


def test_kill_switch_blocks_artifact_generation(tmp_path: Path):
    samples = tmp_path / "samples.json"
    profile = tmp_path / "price.json"
    write_json(samples, samples_artifact())
    write_json(profile, price_profile())

    with pytest.raises(RuntimeError, match="kill_switch_enabled"):
        plan_gemini_smoke_batch(
            samples_path=samples,
            out_jsonl_path=tmp_path / "smoke.jsonl",
            out_manifest_path=tmp_path / "manifest.json",
            model="models/gemini-3.1-pro-preview",
            max_segments=5,
            price_profile_path=profile,
            price_profile_id="test",
            kill_switch=True,
        )

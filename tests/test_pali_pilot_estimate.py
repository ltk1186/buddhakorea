import json
from decimal import Decimal
from pathlib import Path

from backend.pali.scripts.estimate_gemini_pilot_batch import estimate_gemini_pilot_batch
from backend.pali.translation.prompts import KOREAN_ADVANCED_PROMPT_VERSION


def write_json(path: Path, data: dict) -> None:
    path.write_text(json.dumps(data), encoding="utf-8")


def sample(index: int, layer: str = "mula") -> dict:
    return {
        "stable_segment_key": f"seg-{index}",
        "source_path": "romn/s0505m.mul.xml",
        "source_text_hash": f"hash-{index}",
        "text_layer": layer,
        "pitaka": "sutta",
        "nikaya": "Khuddakanikāye",
        "chunk_type": "prose" if index % 2 == 0 else "verse",
        "length_bucket": "short",
        "original_text": "Evaṃ me sutaṃ.",
        "token_estimates_by_profile": {"gemini_local_approx": 20},
    }


def samples_artifact(count: int = 75) -> dict:
    layers = ["mula", "atthakatha", "tika"]
    return {
        "source_commit": "49bc86914748589a2501b548cc6b3e97a8abe018",
        "pilot_samples": [sample(index, layers[index % 3]) for index in range(count)],
    }


def source_calibration() -> dict:
    return {
        "aggregate_totals": {
            "recommended_source_correction_factor": {
                "overall": 1.7,
                "by_text_layer": {
                    "mula": 1.6,
                    "atthakatha": 1.8,
                    "tika": 1.7,
                },
            }
        }
    }


def prompt_calibration(version: str, overhead: int) -> dict:
    return {
        "prompt_template_id": "korean_advanced",
        "prompt_template_version": version,
        "prompt_v1_overhead_total": overhead * 150,
        "average_prompt_v1_overhead_tokens": overhead,
        "median_prompt_v1_overhead_tokens": overhead,
        "p90_prompt_v1_overhead_tokens": overhead + 5,
        "overhead_by_text_layer": {
            "mula": {"average_prompt_v1_overhead_tokens": overhead},
            "atthakatha": {"average_prompt_v1_overhead_tokens": overhead + 10},
            "tika": {"average_prompt_v1_overhead_tokens": overhead + 20},
        },
    }


def smoke_summary() -> dict:
    return {
        "total_actual_input_tokens": 1000,
        "total_actual_output_tokens": 200,
        "total_thinking_tokens": 300,
    }


def price_profile() -> dict:
    return {
        "profiles": [
            {
                "profile_id": "test",
                "input_usd_per_million_tokens": "1",
                "output_usd_per_million_tokens": "6",
                "thinking_usd_per_million_tokens": "6",
                "batch_discount_multiplier": "1",
            }
        ]
    }


def test_pilot_estimate_artifact_has_75_requests_and_schemafix_version(tmp_path: Path):
    samples = tmp_path / "samples.json"
    source = tmp_path / "source.json"
    previous = tmp_path / "previous.json"
    schemafix = tmp_path / "schemafix.json"
    smoke = tmp_path / "smoke.json"
    profile = tmp_path / "price.json"
    out = tmp_path / "pilot.json"
    write_json(samples, samples_artifact())
    write_json(source, source_calibration())
    write_json(previous, prompt_calibration("korean_advanced_v1", 100))
    write_json(schemafix, prompt_calibration(KOREAN_ADVANCED_PROMPT_VERSION, 150))
    write_json(smoke, smoke_summary())
    write_json(profile, price_profile())

    report = estimate_gemini_pilot_batch(
        samples_path=samples,
        source_calibration_path=source,
        previous_prompt_calibration_path=previous,
        schemafix_prompt_calibration_path=schemafix,
        smoke_summary_path=smoke,
        out_path=out,
        model="models/gemini-3.1-pro-preview",
        price_profile_path=profile,
        price_profile_id="test",
        budget_cap_usd=Decimal("50"),
        pretty=True,
    )

    assert out.exists()
    assert report["request_count"] == 75
    assert report["prompt_template_version"] == KOREAN_ADVANCED_PROMPT_VERSION
    assert report["estimated_input_tokens"] > 0
    assert report["estimated_output_tokens"] > 0
    assert report["estimated_thinking_tokens"] > 0
    assert report["budget_check"]["can_submit_under_cap"] is True
    assert report["prompt_overhead_comparison"]["overhead_increase_ratio"] == 1.5
    assert report["prompt_overhead_comparison"]["pilot_75_input_tokens_schemafix"] > report[
        "prompt_overhead_comparison"
    ]["pilot_75_input_tokens_previous"]


def test_pilot_estimate_warns_when_budget_cap_exceeded(tmp_path: Path):
    samples = tmp_path / "samples.json"
    source = tmp_path / "source.json"
    previous = tmp_path / "previous.json"
    schemafix = tmp_path / "schemafix.json"
    smoke = tmp_path / "smoke.json"
    profile = tmp_path / "price.json"
    out = tmp_path / "pilot.json"
    write_json(samples, samples_artifact())
    write_json(source, source_calibration())
    write_json(previous, prompt_calibration("korean_advanced_v1", 100))
    write_json(schemafix, prompt_calibration(KOREAN_ADVANCED_PROMPT_VERSION, 150))
    write_json(smoke, smoke_summary())
    write_json(profile, price_profile())

    report = estimate_gemini_pilot_batch(
        samples_path=samples,
        source_calibration_path=source,
        previous_prompt_calibration_path=previous,
        schemafix_prompt_calibration_path=schemafix,
        smoke_summary_path=smoke,
        out_path=out,
        model="models/gemini-3.1-pro-preview",
        price_profile_path=profile,
        price_profile_id="test",
        budget_cap_usd=Decimal("0.000001"),
    )

    assert report["budget_check"]["can_submit_under_cap"] is False
    assert any("exceeds pilot budget cap" in warning for warning in report["warnings"])

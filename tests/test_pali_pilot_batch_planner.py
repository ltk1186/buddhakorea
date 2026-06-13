import json
from decimal import Decimal

import pytest

from backend.pali.scripts.plan_gemini_pilot_batch import plan_gemini_pilot_batch
from backend.pali.translation.prompts import KOREAN_ADVANCED_PROMPT_VERSION


def sample(index: int) -> dict:
    layers = ["mula", "atthakatha", "tika"]
    chunks = ["prose", "verse"]
    lengths = ["short", "medium", "long"]
    return {
        "stable_segment_key": f"vri:sample:{index}",
        "source_text_hash": f"hash-{index}",
        "source_path": f"romn/test{index}.mul.xml",
        "source_file": f"test{index}.mul.xml",
        "text_layer": layers[index % len(layers)],
        "pitaka": "sutta",
        "nikaya": "Dīghanikāya",
        "chunk_type": chunks[index % len(chunks)],
        "length_bucket": lengths[index % len(lengths)],
        "original_text": f"Evaṃ me sutaṃ sample {index}.",
        "heading_path": [],
    }


def write_artifacts(tmp_path, *, count: int = 75, estimated_cost: str = "0.750000"):
    samples = [sample(index) for index in range(count)]
    samples_path = tmp_path / "samples.json"
    samples_path.write_text(
        json.dumps(
            {
                "source_commit": "49bc86914748589a2501b548cc6b3e97a8abe018",
                "pilot_samples": samples,
            },
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )
    estimate_path = tmp_path / "estimate.json"
    estimate_path.write_text(
        json.dumps(
            {
                "items": [
                    {
                        "stable_segment_key": item["stable_segment_key"],
                        "estimated_input_tokens": 100,
                        "estimated_output_tokens": 50,
                        "estimated_thinking_tokens": 20,
                        "estimated_cost_usd": estimated_cost,
                        "source_correction_factor": "1.7",
                        "prompt_overhead_tokens": 2616,
                    }
                    for item in samples
                ]
            },
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )
    return samples_path, estimate_path


def test_plan_gemini_pilot_batch_creates_exactly_75_items(tmp_path):
    samples_path, estimate_path = write_artifacts(tmp_path)
    jsonl_path = tmp_path / "pilot.jsonl"
    manifest_path = tmp_path / "pilot_manifest.json"

    manifest = plan_gemini_pilot_batch(
        samples_path=samples_path,
        estimate_path=estimate_path,
        out_jsonl_path=jsonl_path,
        out_manifest_path=manifest_path,
        model="models/gemini-3.1-pro-preview",
        pilot_size=75,
        max_estimated_cost_usd=Decimal("50"),
        pretty_manifest=True,
    )

    assert manifest["request_count"] == 75
    assert manifest["prompt_template_version"] == KOREAN_ADVANCED_PROMPT_VERSION
    assert manifest["validation"]["valid"] is True
    assert len(jsonl_path.read_text(encoding="utf-8").splitlines()) == 75
    assert manifest["distribution"]["text_layer"] == {
        "atthakatha": 25,
        "mula": 25,
        "tika": 25,
    }


def test_plan_gemini_pilot_batch_requires_exact_sample_count(tmp_path):
    samples_path, estimate_path = write_artifacts(tmp_path, count=74)

    with pytest.raises(RuntimeError, match="Expected exactly 75"):
        plan_gemini_pilot_batch(
            samples_path=samples_path,
            estimate_path=estimate_path,
            out_jsonl_path=tmp_path / "pilot.jsonl",
            out_manifest_path=tmp_path / "pilot_manifest.json",
            model="models/gemini-3.1-pro-preview",
            pilot_size=75,
            max_estimated_cost_usd=Decimal("50"),
        )


def test_plan_gemini_pilot_batch_blocks_budget_cap(tmp_path):
    samples_path, estimate_path = write_artifacts(tmp_path)

    with pytest.raises(RuntimeError, match="Budget check failed"):
        plan_gemini_pilot_batch(
            samples_path=samples_path,
            estimate_path=estimate_path,
            out_jsonl_path=tmp_path / "pilot.jsonl",
            out_manifest_path=tmp_path / "pilot_manifest.json",
            model="models/gemini-3.1-pro-preview",
            pilot_size=75,
            max_estimated_cost_usd=Decimal("0.001"),
        )

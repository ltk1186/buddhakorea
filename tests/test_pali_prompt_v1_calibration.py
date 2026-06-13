import json
from pathlib import Path

from backend.pali.scripts.calibrate_prompt_v1_tokens import calibrate_prompt_v1_tokens
from backend.pali.translation.prompts import (
    KOREAN_ADVANCED_PROMPT_ID,
    KOREAN_ADVANCED_PROMPT_VERSION,
)


class FakePromptV1CountTokensClient:
    def __init__(self, failures: set[str] | None = None):
        self.calls: list[str] = []
        self.failures = failures or set()

    def count_tokens(self, model: str, contents: str) -> int:
        self.calls.append(contents)
        if any(marker in contents for marker in self.failures):
            raise RuntimeError("provider unavailable")
        if "literal_ko 작성 원칙" in contents and "빠알리 원문:" in contents:
            return 500
        return 45


def write_sample_artifact(path: Path) -> None:
    artifact = {
        "source_commit": "49bc86914748589a2501b548cc6b3e97a8abe018",
        "calibration_samples": [
            sample("seg-1", "mula", "prose", "short", "Evaṃ me sutaṃ."),
            sample("seg-2", "atthakatha", "verse", "medium", "Dhammo have rakkhati."),
            sample("seg-3", "tika", "prose", "long", "FAIL sample text"),
        ],
    }
    path.write_text(json.dumps(artifact), encoding="utf-8")


def sample(key: str, layer: str, chunk: str, length: str, text: str) -> dict:
    return {
        "stable_segment_key": key,
        "source_path": f"romn/{key}.xml",
        "source_text_hash": f"hash-{key}",
        "text_layer": layer,
        "pitaka": "sutta",
        "nikaya": "Khuddakanikāye",
        "chunk_type": chunk,
        "length_bucket": length,
        "original_text": text,
        "token_estimates_by_profile": {"gemini_local_approx": 20},
    }


def test_prompt_v1_rendered_prompt_is_counted(tmp_path: Path):
    samples = tmp_path / "samples.json"
    out = tmp_path / "prompt_v1.json"
    write_sample_artifact(samples)
    client = FakePromptV1CountTokensClient()

    report = calibrate_prompt_v1_tokens(
        samples_path=samples,
        model="models/gemini-3.1-pro-preview",
        out_path=out,
        max_samples=1,
        dry_run=False,
        client=client,
        max_retries=0,
        pretty=True,
    )

    assert any("Evaṃ me sutaṃ." in call or "Dhammo have rakkhati." in call for call in client.calls)
    assert any("literal_ko 작성 원칙" in call for call in client.calls)
    assert any("빠알리 원문:" in call for call in client.calls)
    assert report["prompt_template_id"] == KOREAN_ADVANCED_PROMPT_ID
    assert report["prompt_template_version"] == KOREAN_ADVANCED_PROMPT_VERSION
    assert report["source_text_only_total"] == 45
    assert report["prompt_with_source_total"] == 500
    assert report["prompt_v1_with_source_total"] == 500
    assert report["prompt_overhead_total"] == 455
    assert report["prompt_v1_overhead_total"] == 455
    assert report["average_prompt_overhead_tokens"] == 455
    assert report["sample_results"][0]["prompt_v1_overhead_tokens"] == 455


def test_dry_run_records_prompt_template_without_api(tmp_path: Path):
    samples = tmp_path / "samples.json"
    out = tmp_path / "dry.json"
    write_sample_artifact(samples)

    report = calibrate_prompt_v1_tokens(
        samples_path=samples,
        model="models/gemini-3.1-pro-preview",
        out_path=out,
        max_samples=2,
        dry_run=True,
    )

    assert report["dry_run"] is True
    assert report["api_used"] is None
    assert report["sample_size"] == 2
    assert report["sample_results"][0]["status"] == "dry_run"
    assert report["prompt_template_version"] == KOREAN_ADVANCED_PROMPT_VERSION


def test_failed_sample_is_recorded(tmp_path: Path):
    samples = tmp_path / "samples.json"
    out = tmp_path / "prompt_v1.json"
    write_sample_artifact(samples)

    report = calibrate_prompt_v1_tokens(
        samples_path=samples,
        model="models/gemini-3.1-pro-preview",
        out_path=out,
        max_samples=3,
        dry_run=False,
        client=FakePromptV1CountTokensClient(failures={"FAIL"}),
        max_retries=0,
    )

    assert report["successful_sample_count"] == 2
    assert report["failed_sample_count"] == 1
    assert report["failed_samples"][0]["stable_segment_key"] == "seg-3"
    assert report["sample_results"][2]["status"] == "failed"
    assert "provider unavailable" in report["sample_results"][2]["error_message"]


def test_overhead_breakdowns_are_calculated(tmp_path: Path):
    samples = tmp_path / "samples.json"
    out = tmp_path / "prompt_v1.json"
    write_sample_artifact(samples)

    report = calibrate_prompt_v1_tokens(
        samples_path=samples,
        model="models/gemini-3.1-pro-preview",
        out_path=out,
        max_samples=2,
        dry_run=False,
        client=FakePromptV1CountTokensClient(),
        max_retries=0,
    )

    assert report["average_prompt_v1_overhead_tokens"] == 455
    assert report["median_prompt_v1_overhead_tokens"] == 455
    assert report["p90_prompt_v1_overhead_tokens"] == 455.0
    assert report["overhead_by_text_layer"]["mula"]["prompt_v1_overhead_total"] == 455
    assert report["overhead_by_chunk_type"]["verse"]["sample_count"] == 1

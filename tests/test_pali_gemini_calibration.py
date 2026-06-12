import json
from pathlib import Path

import pytest

import backend.pali.scripts.calibrate_gemini_tokens as calibration
from backend.pali.scripts.calibrate_gemini_tokens import calibrate_gemini_tokens


class FakeCountTokensClient:
    def __init__(self, failures: set[str] | None = None):
        self.failures = failures or set()

    def count_tokens(self, model: str, contents: str) -> int:
        if any(marker in contents for marker in self.failures):
            raise RuntimeError("provider unavailable")
        if contents.startswith("You are translating"):
            return 120 + len(contents) // 20
        return max(1, len(contents) // 2)


def write_sample_artifact(path: Path) -> None:
    artifact = {
        "source_commit": "49bc86914748589a2501b548cc6b3e97a8abe018",
        "parameters": {"calibration_size": 3},
        "candidate_pool_report": {"total_segments": 3},
        "calibration_samples": [
            sample("seg-1", "romn/s0505m.mul.xml", "mula", "prose", "short", "sutta", "Khuddakanikāye", "Evaṃ me sutaṃ.", 10),
            sample("seg-2", "romn/s0505a.att.xml", "atthakatha", "verse", "medium", "sutta", "Khuddakanikāye", "Dhammo have rakkhati dhammacāriṃ.", 20),
            sample("seg-3", "romn/s0519t.tik.xml", "tika", "prose", "long", "abhidhamma", "Abhidhammapiṭake", "FAIL sample text", 30),
        ],
    }
    path.write_text(json.dumps(artifact), encoding="utf-8")


def sample(
    key: str,
    source_path: str,
    layer: str,
    chunk_type: str,
    length_bucket: str,
    pitaka: str,
    nikaya: str,
    text: str,
    estimate: int,
) -> dict:
    return {
        "stable_segment_key": key,
        "source_path": source_path,
        "text_layer": layer,
        "pitaka": pitaka,
        "nikaya": nikaya,
        "chunk_type": chunk_type,
        "length_bucket": length_bucket,
        "original_text": text,
        "token_estimates_by_profile": {"gemini_local_approx": estimate},
    }


def test_dry_run_without_api_key(tmp_path: Path):
    samples = tmp_path / "samples.json"
    out = tmp_path / "dry_run.json"
    write_sample_artifact(samples)

    report = calibrate_gemini_tokens(
        samples_path=samples,
        model="gemini-3.1-pro",
        out_path=out,
        max_samples=2,
        dry_run=True,
        pretty=True,
    )

    assert out.exists()
    assert report["dry_run"] is True
    assert report["api_used"] is None
    assert report["sample_size"] == 2
    assert report["sample_results"][0]["status"] == "dry_run"
    assert "preview" in report["prompt_wrapper"]


def test_actual_run_requires_api_key_when_no_client(tmp_path: Path, monkeypatch):
    samples = tmp_path / "samples.json"
    out = tmp_path / "calibration.json"
    write_sample_artifact(samples)
    for name in calibration.GEMINI_API_KEY_ENV_CANDIDATES:
        monkeypatch.delenv(name, raising=False)
    monkeypatch.setattr(calibration, "REPO_ROOT", tmp_path)

    with pytest.raises(RuntimeError, match="A Gemini API key is required"):
        calibrate_gemini_tokens(
            samples_path=samples,
            model="gemini-3.1-pro",
            out_path=out,
            max_samples=1,
            dry_run=False,
        )


def test_api_key_resolver_checks_multiple_env_names(tmp_path: Path, monkeypatch):
    for name in calibration.GEMINI_API_KEY_ENV_CANDIDATES:
        monkeypatch.delenv(name, raising=False)
    monkeypatch.setenv("GOOGLE_GENAI_API_KEY", "test-key")

    assert calibration.resolve_gemini_api_key() == "test-key"


def test_api_key_resolver_reads_local_env_file(tmp_path: Path, monkeypatch):
    for name in calibration.GEMINI_API_KEY_ENV_CANDIDATES:
        monkeypatch.delenv(name, raising=False)
    (tmp_path / ".env").write_text("PALI_GEMINI_API_KEY=test-key\n", encoding="utf-8")
    monkeypatch.setattr(calibration, "REPO_ROOT", tmp_path)

    assert calibration.resolve_gemini_api_key() == "test-key"


def test_ratio_overhead_and_breakdown_are_calculated(tmp_path: Path):
    samples = tmp_path / "samples.json"
    out = tmp_path / "calibration.json"
    write_sample_artifact(samples)

    report = calibrate_gemini_tokens(
        samples_path=samples,
        model="gemini-3.1-pro",
        out_path=out,
        max_samples=2,
        dry_run=False,
        client=FakeCountTokensClient(),
        max_retries=0,
        pretty=True,
    )

    first = report["sample_results"][0]
    assert first["status"] == "success"
    assert first["source_ratio"] == round(
        first["official_source_text_only_tokens"] / first["local_gemini_estimate_tokens"],
        6,
    )
    assert first["prompt_overhead_tokens"] == (
        first["official_prompt_with_source_tokens"] - first["official_source_text_only_tokens"]
    )
    assert report["aggregate_totals"]["recommended_source_correction_factor"]["overall"] is not None
    assert "mula" in report["breakdowns"]["ratio_by_text_layer"]
    assert report["failed_sample_count"] == 0


def test_failed_sample_is_recorded_without_stopping_batch(tmp_path: Path):
    samples = tmp_path / "samples.json"
    out = tmp_path / "calibration.json"
    write_sample_artifact(samples)

    report = calibrate_gemini_tokens(
        samples_path=samples,
        model="gemini-3.1-pro",
        out_path=out,
        max_samples=3,
        dry_run=False,
        client=FakeCountTokensClient(failures={"FAIL"}),
        max_retries=0,
    )

    assert report["sample_size"] == 3
    assert report["successful_sample_count"] == 2
    assert report["failed_sample_count"] == 1
    assert report["diagnostics"]["failed_samples"][0]["stable_segment_key"] == "seg-3"
    assert report["sample_results"][2]["status"] == "failed"

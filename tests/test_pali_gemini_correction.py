import json
from pathlib import Path

from backend.pali.scripts.apply_gemini_token_calibration import apply_gemini_token_calibration


def write_json(path: Path, data: dict) -> None:
    path.write_text(json.dumps(data), encoding="utf-8")


def corpus_summary() -> dict:
    return {
        "source_commit": "test-sha",
        "files_by_text_layer": {"mula": 2, "atthakatha": 1, "tika": 1},
        "segments_by_text_layer": {"mula": 10, "atthakatha": 5, "tika": 2},
        "tokens_by_text_layer_and_profile": {
            "mula": {"gemini_local_approx": 100},
            "atthakatha": {"gemini_local_approx": 200},
            "tika": {"gemini_local_approx": 50},
        },
    }


def calibration() -> dict:
    return {
        "source_commit": "test-sha",
        "model": "models/gemini-3.1-pro-preview",
        "sample_size": 150,
        "aggregate_totals": {
            "recommended_source_correction_factor": {
                "overall": 1.7,
                "by_text_layer": {"mula": 1.5, "atthakatha": 2.0},
            },
            "average_prompt_overhead_tokens": 106,
            "median_prompt_overhead_tokens": 106.0,
            "p90_prompt_overhead_tokens": 106.0,
        },
        "breakdowns": {
            "ratio_by_chunk_type": {
                "prose": {"ratio": 1.6},
                "verse": {"ratio": 1.9},
            },
            "ratio_by_length_bucket": {
                "short": {"ratio": 1.8},
                "medium": {"ratio": 1.7},
                "long": {"ratio": 1.6},
            },
        },
    }


def test_layer_factors_and_overall_fallback_are_applied(tmp_path: Path):
    corpus_path = tmp_path / "corpus.json"
    calibration_path = tmp_path / "calibration.json"
    out = tmp_path / "corrected.json"
    write_json(corpus_path, corpus_summary())
    write_json(calibration_path, calibration())

    report = apply_gemini_token_calibration(
        corpus_summary_path=corpus_path,
        calibration_path=calibration_path,
        out_path=out,
        pretty=True,
    )

    assert report["layers"]["mula"]["applied_correction_factor"] == 1.5
    assert report["layers"]["mula"]["corrected_gemini_source_tokens"] == 150
    assert report["layers"]["atthakatha"]["applied_correction_factor"] == 2.0
    assert report["layers"]["atthakatha"]["corrected_gemini_source_tokens"] == 400
    assert report["layers"]["tika"]["applied_correction_factor"] == 1.7
    assert report["layers"]["tika"]["correction_factor_source"] == "overall_fallback"
    assert report["layers"]["tika"]["corrected_gemini_source_tokens"] == 85
    assert out.exists()


def test_corrected_totals_are_calculated(tmp_path: Path):
    corpus_path = tmp_path / "corpus.json"
    calibration_path = tmp_path / "calibration.json"
    out = tmp_path / "corrected.json"
    write_json(corpus_path, corpus_summary())
    write_json(calibration_path, calibration())

    report = apply_gemini_token_calibration(
        corpus_summary_path=corpus_path,
        calibration_path=calibration_path,
        out_path=out,
    )

    assert report["totals"]["total_files"] == 4
    assert report["totals"]["total_segments"] == 17
    assert report["totals"]["total_local_gemini_heuristic_source_tokens"] == 350
    assert report["totals"]["total_corrected_gemini_source_tokens"] == 635


def test_prompt_overhead_and_ratio_notes_are_included(tmp_path: Path):
    corpus_path = tmp_path / "corpus.json"
    calibration_path = tmp_path / "calibration.json"
    out = tmp_path / "corrected.json"
    write_json(corpus_path, corpus_summary())
    write_json(calibration_path, calibration())

    report = apply_gemini_token_calibration(
        corpus_summary_path=corpus_path,
        calibration_path=calibration_path,
        out_path=out,
    )

    assert report["prompt_overhead_placeholder_tokens"]["average"] == 106
    assert "Rerun after Korean Advanced Prompt v1" in report["diagnostics"]["prompt_overhead_note"]
    assert "verse" in report["diagnostics"]["prose_vs_verse_ratio_note"]
    assert any("Verse sample ratio is higher" in warning for warning in report["warnings"])

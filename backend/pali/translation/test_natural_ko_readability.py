from __future__ import annotations

import json
from pathlib import Path

from backend.pali.translation.natural_ko_readability import (
    DEFAULT_INPUT,
    audit_items,
    build_request_previews,
    parse_readable_markdown,
    readability_metrics,
    render_dry_run_plan,
    render_prompt_variant,
    run_calibration_prep,
    select_calibration_items,
)


def item(
    key: str,
    layer: str,
    literal: str,
    natural: str,
    *,
    source_path: str | None = None,
    original: str = "Evaṃ me sutaṃ.",
    length: str = "medium",
    chunk: str = "prose",
) -> dict:
    return {
        "stable_segment_key": key,
        "source_path": source_path or f"romn/{key}.xml",
        "source_text_hash": f"hash-{key}",
        "text_layer": layer,
        "chunk_type": chunk,
        "length_bucket": length,
        "original_text": original,
        "literal_ko": literal,
        "natural_ko": natural,
        "terms": [],
        "grammar_notes": [],
        "doctrinal_notes": [],
        "uncertainties": [],
        "quality_flags": [],
    }


def synthetic_markdown(path: Path) -> None:
    path.write_text(
        """# Pāli 300 Translation Outputs

## 001. `vri:romn:test:0001`

- source_path: `romn/test.xml`
- source_text_hash: `abc`
- layer/chunk/length: `mula` / `prose` / `short`
- selection: `hard` / `test`
- status: `succeeded`, schema_valid: `True`, parse_failed: `False`

### 원문

Evaṃ me sutaṃ.

### 직역

나는 이와 같이 들었다.

### 의역

나는 이와 같이 들었다.

### 용어

_없음_

### 문법

_없음_

### 해설

_없음_

### 불확실성 / 품질 플래그

_없음_
""",
        encoding="utf-8",
    )


def test_parser_extracts_representative_markdown(tmp_path: Path) -> None:
    path = tmp_path / "readable.md"
    synthetic_markdown(path)
    parsed = parse_readable_markdown(path)
    assert len(parsed) == 1
    assert parsed[0]["stable_segment_key"] == "vri:romn:test:0001"
    assert parsed[0]["text_layer"] == "mula"
    assert parsed[0]["source_text_hash"] == "abc"
    assert parsed[0]["literal_ko"] == "나는 이와 같이 들었다."
    assert parsed[0]["natural_ko"] == "나는 이와 같이 들었다."


def test_parser_extracts_300_items_when_local_fixture_exists() -> None:
    if not DEFAULT_INPUT.exists():
        return
    assert len(parse_readable_markdown(DEFAULT_INPUT)) == 300


def test_readability_metrics_are_deterministic_and_flag_equal_literal() -> None:
    payload = item("same", "mula", "나는 이와 같이 들었다.", "나는 이와 같이 들었다.")
    first = readability_metrics(payload)
    second = readability_metrics(payload)
    assert first == second
    assert first["natural_same_as_literal"] is True
    assert "natural_same_as_literal" in first["readability_warning_flags"]
    assert "natural_near_literal_095" in first["readability_warning_flags"]


def test_near_literal_and_formulaic_are_visible_not_silently_passed() -> None:
    payload = item(
        "formula",
        "mula",
        "첫째 법, 둘째 법, 셋째 법이다.",
        "첫째 법, 둘째 법, 셋째 법이다.",
        source_path="romn/abh01m.mul.xml",
        original="1. dhammo; 2. dhammo; 3. dhammo",
        length="short",
    )
    metrics = readability_metrics(payload)
    assert metrics["literal_natural_similarity"] >= 0.95
    assert metrics["is_formulaic_or_matrix_like"] is True
    assert "formulaic_exception_possible" in metrics["readability_warning_flags"]


def test_calibration_selection_returns_30_with_10_per_layer_and_roles(tmp_path: Path) -> None:
    rows = []
    for layer in ("mula", "atthakatha", "tika"):
        for index in range(15):
            key = f"{layer}-{index}"
            if index < 4:
                literal = natural = f"{layer} 같은 문장 {index}."
            elif index < 7:
                literal = f"'{index}'라는 것은 설명이다."
                natural = f"'{index}'라는 것은 설명이다. 이 표현은 뜻한다."
            elif index < 10:
                literal = natural = f"첫째 {index}, 둘째 {index}, 셋째 {index}."
                rows.append(
                    item(
                        key,
                        layer,
                        literal,
                        natural,
                        source_path=f"romn/abh{index:02d}{layer}.xml",
                        original="1. dhammo; 2. dhammo; 3. dhammo",
                        length="short",
                    )
                )
                continue
            else:
                literal = f"{layer} 직역 문장이 길게 이어진다 {index}."
                natural = f"{layer} 자연역 문장이 조금 다르게 이어진다 {index}."
            rows.append(item(key, layer, literal, natural))
    audit = audit_items(rows, tmp_path / "fixture.md")
    selection = select_calibration_items(audit)
    assert selection["selected_count"] == 30
    assert selection["actual_distribution_by_layer"] == {"atthakatha": 10, "mula": 10, "tika": 10}
    assert selection["calibration_role_counts"]["improvement_target"] >= 22
    assert 6 <= selection["calibration_role_counts"]["convergence_control"] <= 8
    assert any(item["selection_reason"] == "baseline_near_identical_offender" for item in selection["items"])
    assert any(item["text_layer"] == "tika" for item in selection["items"])
    assert any("lemma_gloss" in item["selection_reason"] for item in selection["items"])


def test_prompt_variant_and_previews_do_not_add_reader_ko(tmp_path: Path) -> None:
    rows = [item(f"mula-{index}", "mula", "직역", "자연역") for index in range(10)]
    rows += [item(f"att-{index}", "atthakatha", "직역", "자연역") for index in range(10)]
    rows += [item(f"tika-{index}", "tika", "직역", "자연역") for index in range(10)]
    audit = audit_items(rows, tmp_path / "fixture.md")
    selection = select_calibration_items(audit)
    prompt = render_prompt_variant()
    assert "reader_ko" not in prompt
    assert "Do not add any new output field" in prompt
    arm_v1, arm_v2 = build_request_previews(selection)
    assert len(arm_v1) == 30
    assert len(arm_v2) == 30
    assert "response_schema" in arm_v1[0]["request"]["generation_config"]
    assert "response_schema" in arm_v2[0]["request"]["generation_config"]
    schema_v1 = arm_v1[0]["request"]["generation_config"]["response_schema"]
    schema_v2 = arm_v2[0]["request"]["generation_config"]["response_schema"]
    assert "reader_ko" not in schema_v1["properties"]
    assert "reader_ko" not in schema_v2["properties"]
    assert "reader_ko" not in arm_v2[0]["request"]["contents"][0]["parts"][0]["text"]
    assert arm_v1[0]["metadata"]["source_text_hash"] == selection["items"][0]["source_text_hash"]
    assert arm_v2[0]["metadata"]["source_text_hash"] == selection["items"][0]["source_text_hash"]


def test_dry_run_plan_and_manifest_record_no_calls(tmp_path: Path) -> None:
    source = tmp_path / "readable.md"
    synthetic_markdown(source)
    out = tmp_path / "out"
    result = run_calibration_prep(source_file=source, out_dir=out, pretty=True)
    manifest = json.loads((out / "run_manifest.json").read_text(encoding="utf-8"))
    plan = (out / "natural_ko_v2_dry_run_plan.md").read_text(encoding="utf-8")
    assert result["api_llm_calls"] == 0
    assert manifest["api_llm_calls"] == 0
    assert manifest["network_calls"] == 0
    assert manifest["batch_submissions"] == 0
    assert manifest["step5_selection_modified"] is False
    assert manifest["step6_started"] is False
    assert manifest["reader_ko_added"] is False
    assert manifest["estimated_api_calls_for_later_smoke"] == 60
    assert "API calls made in this task: 0" in plan

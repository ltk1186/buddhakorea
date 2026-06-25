from __future__ import annotations

import json
from pathlib import Path

from backend.pali.translation.natural_ko_readability import (
    DEFAULT_INPUT,
    NATURAL_KO_V2_1_MARKER,
    NATURAL_KO_V2_1_INSTRUCTION,
    NATURAL_KO_V2_2_MARKER,
    NATURAL_KO_V2_2_INSTRUCTION,
    audit_items,
    build_request_preview_v2_1,
    build_request_preview_v2_2,
    build_request_previews,
    parse_readable_markdown,
    readability_metrics,
    render_natural_ko_v2_1_prompt,
    render_dry_run_plan,
    render_glossary_lock_v2_2_md,
    render_prompt_variant,
    render_prompt_variant_v2_1,
    render_prompt_variant_v2_2,
    render_natural_ko_v2_2_prompt,
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
    assert "Do not add `reader_ko`" in prompt
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
    assert "Do not add `reader_ko`" in arm_v2[0]["request"]["contents"][0]["parts"][0]["text"]
    assert arm_v1[0]["metadata"]["source_text_hash"] == selection["items"][0]["source_text_hash"]
    assert arm_v2[0]["metadata"]["source_text_hash"] == selection["items"][0]["source_text_hash"]


def test_natural_ko_v2_1_marker_guard_and_prompt_replacement(tmp_path: Path) -> None:
    rows = [item(f"mula-{index}", "mula", "직역", "자연역") for index in range(10)]
    rows += [item(f"att-{index}", "atthakatha", "직역", "자연역") for index in range(10)]
    rows += [item(f"tika-{index}", "tika", "직역", "자연역") for index in range(10)]
    audit = audit_items(rows, tmp_path / "fixture.md")
    selection = select_calibration_items(audit)
    arm_v1, _ = build_request_previews(selection)
    arm_c = build_request_preview_v2_1(selection)
    a_prompt = arm_v1[0]["request"]["contents"][0]["parts"][0]["text"]
    c_prompt = arm_c[0]["request"]["contents"][0]["parts"][0]["text"]
    variant = render_prompt_variant_v2_1()
    assert NATURAL_KO_V2_1_MARKER == "NATURAL_KO_V2_1_CALIBRATION_INSTRUCTION"
    assert NATURAL_KO_V2_1_MARKER in NATURAL_KO_V2_1_INSTRUCTION
    assert NATURAL_KO_V2_1_MARKER in variant
    assert "선업이 청정하기 때문에" in variant
    assert "therefore" in variant
    assert "Assāsayi" in variant
    assert "Do not add reader_ko" in variant
    assert "reader_ko" not in arm_c[0]["request"]["generation_config"]["response_schema"]["properties"]
    assert NATURAL_KO_V2_1_MARKER not in a_prompt
    assert NATURAL_KO_V2_1_MARKER in c_prompt
    assert "natural_ko 작성 원칙:\n- 독자용 자연역입니다." in a_prompt
    assert "natural_ko 작성 원칙:\n- 독자용 자연역입니다." not in c_prompt
    assert "용어 정책:" in c_prompt
    assert arm_c[0]["metadata"]["source_text_hash"] == selection["items"][0]["source_text_hash"]


def test_render_natural_ko_v2_1_prompt_preserves_non_natural_sections() -> None:
    prompt_v1 = (
        "literal_ko 작성 원칙:\n- 직역입니다.\n\n"
        "natural_ko 작성 원칙:\n- 독자용 자연역입니다.\n\n"
        "용어 정책:\n- 용어는 보존합니다."
    )
    c_prompt = render_natural_ko_v2_1_prompt(prompt_v1)
    assert "literal_ko 작성 원칙" in c_prompt
    assert "용어 정책:" in c_prompt
    assert "natural_ko 작성 원칙:\n- 독자용 자연역입니다." not in c_prompt
    assert NATURAL_KO_V2_1_MARKER in c_prompt


def test_natural_ko_v2_2_prompt_has_marker_glossary_and_guards(tmp_path: Path) -> None:
    rows = [item(f"mula-{index}", "mula", "직역", "자연역") for index in range(10)]
    rows += [item(f"att-{index}", "atthakatha", "직역", "자연역") for index in range(10)]
    rows += [item(f"tika-{index}", "tika", "직역", "자연역", source_path=f"romn/s{index}.tik.xml") for index in range(10)]
    audit = audit_items(rows, tmp_path / "fixture.md")
    selection = select_calibration_items(audit)
    arm_d = build_request_preview_v2_2(selection)
    d_prompt = arm_d[0]["request"]["contents"][0]["parts"][0]["text"]
    variant = render_prompt_variant_v2_2()
    assert NATURAL_KO_V2_2_MARKER in NATURAL_KO_V2_2_INSTRUCTION
    assert NATURAL_KO_V2_2_MARKER in variant
    assert NATURAL_KO_V2_2_MARKER in d_prompt
    assert "선업이 청정하기 때문에" in variant
    assert "통찰지를 위로" in variant
    assert "처음-상태" in variant
    assert "공부지음" in variant
    assert "reader_ko를 추가하지 마십시오" in variant
    assert "reader_ko" not in arm_d[0]["request"]["generation_config"]["response_schema"]["properties"]
    assert "natural_ko 작성 원칙:\n- 독자용 자연역입니다." not in d_prompt
    assert "용어 정책:" not in d_prompt
    assert "단일 용어 잠금 블록" in d_prompt
    assert arm_d[0]["metadata"]["source_text_hash"] == selection["items"][0]["source_text_hash"]
    assert "Glossary Lock" in render_glossary_lock_v2_2_md()


def test_natural_ko_v2_2_known_failure_guards_are_item_specific() -> None:
    def item_guard(prompt: str) -> str:
        return prompt.split("## 세그먼트별 알려진 실패 가드", 1)[1].split("## 단일 용어 잠금 블록", 1)[0]

    prompt_v1 = (
        "literal_ko 작성 원칙:\n- 직역입니다.\n\n"
        "natural_ko 작성 원칙:\n- 독자용 자연역입니다.\n\n"
        "용어 정책:\n- 용어는 보존합니다."
    )
    accenti_prompt = render_natural_ko_v2_2_prompt(
        prompt_v1,
        {"stable_segment_key": "vri:romn:s0508a1.att:8b9574445272", "text_layer": "atthakatha"},
    )
    kharena_prompt = render_natural_ko_v2_2_prompt(
        prompt_v1,
        {"stable_segment_key": "vri:romn:s0507a.att:f303db8f57dc", "text_layer": "atthakatha"},
    )
    unrelated_prompt = render_natural_ko_v2_2_prompt(
        prompt_v1,
        {"stable_segment_key": "vri:romn:other.mul:000", "text_layer": "mula"},
    )
    accenti_guard = item_guard(accenti_prompt)
    kharena_guard = item_guard(kharena_prompt)
    unrelated_guard = item_guard(unrelated_prompt)
    assert "지나간다/지나쳐 버린다" in accenti_guard
    assert "상처에" not in accenti_guard
    assert "세속적인" not in accenti_guard
    assert "상처에" in kharena_guard
    assert "지나간다/지나쳐 버린다" not in kharena_guard
    assert "별도 알려진 실패 가드가 없습니다" in unrelated_guard
    assert "선업이 청정하기 때문에" not in unrelated_guard
    assert "상처에" not in unrelated_guard
    assert "지나간다/지나쳐 버린다" not in unrelated_guard


def test_natural_ko_v2_2_prompt_includes_glossary_tiers() -> None:
    prompt_v1 = (
        "literal_ko 작성 원칙:\n- 직역입니다.\n\n"
        "natural_ko 작성 원칙:\n- 독자용 자연역입니다.\n\n"
        "용어 정책:\n- 용어는 보존합니다."
    )
    d_prompt = render_natural_ko_v2_2_prompt(prompt_v1, {"stable_segment_key": "vri:romn:other.mul:000"})
    glossary_md = render_glossary_lock_v2_2_md()
    assert "[hard/high]" in d_prompt
    assert "[advisory/needs_expert_confirm]" in d_prompt
    assert "| Enforcement | Confidence |" in glossary_md


def test_natural_ko_v2_2_rendered_prompt_architecture() -> None:
    prompt_v1 = (
        "헤더\n\n"
        "literal_ko 작성 원칙:\n"
        "- 빠알리 문장 구조와 어순을 가능한 한 보존하십시오.\n"
        "- 한국어가 다소 어색해도 괜찮습니다.\n\n"
        "natural_ko 작성 원칙:\n- 독자용 자연역입니다.\n\n"
        "용어 정책:\n- sati → 마음챙김\n- paññā → 통찰지\n\n"
        "terms 작성 원칙:\n- terms를 작성합니다."
    )
    d_prompt = render_natural_ko_v2_2_prompt(prompt_v1, {"stable_segment_key": "vri:romn:other.mul:000"})
    assert "빠알리 문장 구조와 어순을 가능한 한 보존하십시오" not in d_prompt
    assert "한국어가 다소 어색해도 괜찮습니다" not in d_prompt
    assert "1차 초벌" not in d_prompt
    assert "완벽한 문장이 아니라" not in d_prompt
    assert "충실하다는 것은 빠알리 어순을 그대로 따라가는 것이 아닙니다" in d_prompt
    assert "literal_ko도 문법적으로 완전한 한국어 문장이어야" in d_prompt
    assert "표제어-주석(lemma-gloss) 구조는 literal_ko에서 보존" in d_prompt
    assert "대괄호 보충([뜻이다], [이다], [그러하다], [이것을], [설해지지] 등)은 사용하지 마십시오" in d_prompt
    assert '"(sīlena)", "(paccuppannā)"' in d_prompt
    assert "natural_ko는 literal_ko를 단순히 다듬은 문장이 아닙니다" in d_prompt
    assert "현대 한국어 불교서 독자가 읽을 수 있는 문장으로 다시 번역" in d_prompt
    assert "'Āsevantassā'ti garukārena āsevantassa pavattentassa" in d_prompt
    assert "'닦아 행하는 자의(āsevantassa)'라는 것은" in d_prompt
    assert "통찰지를 위로 하고" in d_prompt
    assert "처음-상태" in d_prompt
    assert "terms 작성 원칙:" in d_prompt


def test_natural_ko_v2_2_rendered_prompt_has_single_glossary_source() -> None:
    prompt_v1 = (
        "헤더\n\n"
        "literal_ko 작성 원칙:\n- 직역입니다.\n\n"
        "natural_ko 작성 원칙:\n- 독자용 자연역입니다.\n\n"
        "용어 정책:\n- sati → 마음챙김\n- paññā → 통찰지\n\n"
        "terms 작성 원칙:\n- terms를 작성합니다."
    )
    d_prompt = render_natural_ko_v2_2_prompt(prompt_v1, {"stable_segment_key": "vri:romn:other.mul:000"})
    assert "용어 정책:" not in d_prompt
    assert d_prompt.count("## 단일 용어 잠금 블록") == 1
    assert d_prompt.count("sati:") == 1
    assert d_prompt.count("paññā:") == 1


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

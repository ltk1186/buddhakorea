from __future__ import annotations

from backend.pali.translation.natural_ko_v2_2_quality import (
    detect_advisory_glossary_warnings,
    detect_bracket_violations,
    detect_glossary_violations,
    detect_known_omissions,
    detect_known_unsupported_insertions,
    detect_negation_scope_risks,
    evaluate_d_arm_item,
)


def d_item(
    key: str,
    literal: str = "",
    natural: str = "",
    *,
    original_text: str = "",
    terms: list[dict] | None = None,
) -> dict:
    return {
        "stable_segment_key": key,
        "original_text": original_text,
        "literal_ko": literal,
        "natural_ko": natural,
        "terms": terms or [],
    }


def test_bracket_supplementation_is_detected() -> None:
    for bracket in ("[뜻이다]", "[이다]", "[설해지지]", "[이것을]"):
        item = d_item("vri:romn:test", literal=f"이것은 {bracket}.")
        assert detect_bracket_violations(item)


def test_known_unsupported_insertions_are_segment_scoped() -> None:
    assert detect_known_unsupported_insertions(
        d_item("vri:romn:abh02m.mul:a8d464d40a45", natural="세속적인 일을 즐김이다.")
    )
    assert not detect_known_unsupported_insertions(
        d_item("vri:romn:other.mul:000", natural="세속적인 일을 즐김이다.")
    )
    assert detect_known_unsupported_insertions(
        d_item("vri:romn:s0507a.att:f303db8f57dc", natural="상처에 잿물을 뿌렸다.")
    )
    assert detect_known_unsupported_insertions(
        d_item("vri:romn:s0101t.tik:14f01d855b04", natural="삼보를 가까이한다.")
    )
    assert detect_known_unsupported_insertions(
        d_item("vri:romn:s0514m.mul:88650af1ca41", natural="말을 쉬게 하고 기꺼이 말했다.")
    )
    assert detect_known_unsupported_insertions(
        d_item("vri:romn:s0513a3.att:8cd09caf90eb", natural="선업이 청정하기 때문에 그렇다.")
    )


def test_known_accenti_omission_is_detected_for_specific_item() -> None:
    missing = d_item("vri:romn:s0508a1.att:8b9574445272", natural="기회가 사라진다.")
    present = d_item("vri:romn:s0508a1.att:8b9574445272", natural="기회가 지나간다.")
    assert detect_known_omissions(missing) == ["missing_accenti_predicate_in_natural_ko"]
    assert detect_known_omissions(present) == []


def test_accenti_omission_checks_natural_ko_not_literal_ko() -> None:
    literal_only = d_item(
        "vri:romn:s0508a1.att:8b9574445272",
        literal="기회가 지나간다.",
        natural="기회가 사라진다.",
    )
    natural_present = d_item(
        "vri:romn:s0508a1.att:8b9574445272",
        literal="다른 말.",
        natural="기회가 지나쳐 버린다.",
    )
    assert detect_known_omissions(literal_only) == ["missing_accenti_predicate_in_natural_ko"]
    assert detect_known_omissions(natural_present) == []


def test_glossary_lock_flags_disallowed_renderings_but_not_gongbujieum() -> None:
    assert detect_glossary_violations(d_item("x", natural="통찰지를 위로 하는 수행이다.", original_text="paññuttara"))
    assert detect_glossary_violations(d_item("x", natural="처음-상태를 말한다.", original_text="ādibhāvo"))
    assert detect_glossary_violations(d_item("x", natural="세속적인 일을 즐김이다.", original_text="kammārāmatā"))
    assert detect_glossary_violations(d_item("x", natural="상처에 잿물을 뿌렸다.", original_text="khārena paripphositvā"))
    assert detect_glossary_violations(d_item("x", natural="번뇌를 동반하지 않으며 그렇다.", original_text="nanabhāvanāya"))
    assert detect_glossary_violations(d_item("x", natural="공부지음이다.")) == []


def test_advisory_glossary_warnings_do_not_count_as_hard_violations() -> None:
    item = d_item("x", natural="맥락 없는 들어감이라고 옮겼다.", original_text="otaraṇā")
    evaluation = evaluate_d_arm_item(item)
    assert detect_glossary_violations(item) == []
    assert detect_advisory_glossary_warnings(item) == ["otaraṇā:맥락 없는 들어감"]
    assert evaluation["glossary_violation"] is False
    assert evaluation["advisory_glossary_warning"] is True
    assert evaluation["advisory_glossary_warning_details"] == ["otaraṇā:맥락 없는 들어감"]


def test_khandha_false_positive_is_fixed_without_trigger() -> None:
    item = d_item(
        "vri:romn:abh02m.mul:a8d464d40a45",
        original_text="saṅgaṇikārāmatā ... kammārāmatā ...",
        literal="무리와 어울림, 일을 즐김이다.",
        natural="무리와 어울리고 일을 즐기는 것이다.",
        terms=[{"pali": "kammārāmatā", "ko": "일을 즐김"}],
    )
    assert "khandha:무리" not in detect_glossary_violations(item)
    bad_kammarama = dict(item)
    bad_kammarama["natural_ko"] = "세속적인 일을 즐김이다."
    assert "kammārāmatā:세속적인 일을 즐김" in detect_glossary_violations(bad_kammarama)


def test_real_khandha_violation_is_still_caught_when_triggered() -> None:
    item = d_item(
        "x",
        original_text="pañcakkhandhā ...",
        literal="다섯 무리이다.",
        natural="다섯 무리이다.",
        terms=[{"pali": "khandha", "ko": "무리"}],
    )
    assert "khandha:무리" in detect_glossary_violations(item)


def test_term_specific_bad_calque_requires_trigger() -> None:
    untriggered = d_item("x", natural="통찰지를 위로 하는 수행이다.")
    triggered = d_item("x", original_text="paññuttara", natural="통찰지를 위로 하는 수행이다.")
    assert detect_glossary_violations(untriggered) == []
    assert "paññuttara:통찰지를 위로" in detect_glossary_violations(triggered)


def test_advisory_warning_requires_trigger_and_stays_advisory() -> None:
    untriggered = d_item("x", natural="맥락 없는 들어감이라고 옮겼다.")
    triggered = d_item("x", original_text="otaraṇā", natural="맥락 없는 들어감이라고 옮겼다.")
    assert detect_advisory_glossary_warnings(untriggered) == []
    assert detect_glossary_violations(triggered) == []
    assert detect_advisory_glossary_warnings(triggered) == ["otaraṇā:맥락 없는 들어감"]


def test_bracket_remains_hard_objective_violation() -> None:
    assert detect_bracket_violations(d_item("x", literal="[그것은] 설해진다."))


def test_patthana_double_negation_unsupported_bunnoe_is_high_risk() -> None:
    item = d_item("vri:romn:abh03m11.mul:4ab6e93ef3c3", natural="번뇌를 동반하지 않으며 그렇다.")
    assert detect_negation_scope_risks(item)
    evaluation = evaluate_d_arm_item(item)
    assert evaluation["negation_scope_risk"] is True

from __future__ import annotations

from backend.pali.translation.natural_ko_v2_2_quality import (
    detect_bracket_violations,
    detect_glossary_violations,
    detect_known_omissions,
    detect_known_unsupported_insertions,
    detect_negation_scope_risks,
    evaluate_d_arm_item,
)


def d_item(key: str, literal: str = "", natural: str = "") -> dict:
    return {
        "stable_segment_key": key,
        "literal_ko": literal,
        "natural_ko": natural,
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
    assert detect_known_omissions(missing) == ["missing_accenti_jinaganda"]
    assert detect_known_omissions(present) == []


def test_glossary_lock_flags_disallowed_renderings_but_not_gongbujieum() -> None:
    assert detect_glossary_violations(d_item("x", natural="통찰지를 위로 하는 수행이다."))
    assert detect_glossary_violations(d_item("x", natural="처음-상태를 말한다."))
    assert detect_glossary_violations(d_item("x", natural="세속적인 일을 즐김이다."))
    assert detect_glossary_violations(d_item("x", natural="공부지음이다.")) == []


def test_patthana_double_negation_unsupported_bunnoe_is_high_risk() -> None:
    item = d_item("vri:romn:abh03m11.mul:4ab6e93ef3c3", natural="번뇌를 동반하지 않으며 그렇다.")
    assert detect_negation_scope_risks(item)
    evaluation = evaluate_d_arm_item(item)
    assert evaluation["negation_scope_risk"] is True

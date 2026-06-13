import pytest
from pydantic import ValidationError

from backend.pali.translation.prompts import (
    KOREAN_ADVANCED_PROMPT_ID,
    KOREAN_ADVANCED_PROMPT_VERSION,
    MODEL_SELF_REPORT_QUALITY_FLAGS,
    render_korean_advanced_prompt_v1,
    validate_korean_advanced_model_output,
)


def segment() -> dict:
    return {
        "stable_segment_key": "vri:romn:s0505m.mul:test",
        "canonical_ref": "s0505m:seg-000001",
        "text_layer": "mula",
        "chunk_type": "prose",
        "heading_path": [{"text": "Khuddakanikāye"}, {"text": "Suttanipātapāḷi"}],
        "original_text": "Evaṃ me sutaṃ.",
        "source_path": "romn/s0505m.mul.xml",
    }


def valid_output() -> dict:
    return {
        "literal_ko": "이와 같이 나에 의해 들렸다.",
        "natural_ko": "나는 이와 같이 들었다.",
        "terms": [
            {
                "pali": "sutaṃ",
                "ko": "들린 것",
                "gloss": "heard",
                "note": "수동적 표현을 직역에 반영했다.",
            }
        ],
        "grammar_notes": [],
        "doctrinal_notes": [],
        "uncertainties": [],
        "quality_flags": [],
    }


def test_render_korean_advanced_prompt_v1_contains_source_and_schema():
    prompt = render_korean_advanced_prompt_v1(segment())
    assert "Evaṃ me sutaṃ." in prompt
    assert '"literal_ko"' in prompt
    assert '"natural_ko"' in prompt
    assert '"terms"' in prompt
    assert "JSON 외 설명" in prompt
    assert "Markdown code fence" in prompt


def test_prompt_has_literal_and_natural_policy_difference():
    prompt = render_korean_advanced_prompt_v1(segment())
    assert "literal_ko 작성 원칙" in prompt
    assert "natural_ko 작성 원칙" in prompt
    assert "원문 구조" in prompt
    assert "독자용 자연역" in prompt


def test_prompt_allows_limited_natural_terms_but_forbids_reinterpretation():
    prompt = render_korean_advanced_prompt_v1(segment())
    assert "일반 불교 용어" in prompt
    assert "일반 불교 용어 자체를 금지하지 않습니다" in prompt
    assert "대승적 해석틀" in prompt
    assert "현대 심리학" in prompt
    assert "자기계발식" in prompt


def test_prompt_lists_only_model_self_report_quality_flags():
    prompt = render_korean_advanced_prompt_v1(segment())
    for flag in MODEL_SELF_REPORT_QUALITY_FLAGS:
        assert f'"{flag.value}"' in prompt
    assert '"json_parse_failed"' in prompt
    assert "생성 금지 예" in prompt


def test_prompt_does_not_request_english_translation_field_or_source_path():
    prompt = render_korean_advanced_prompt_v1(segment())
    assert "english_translation" not in prompt
    assert "free_translation" not in prompt
    assert "romn/s0505m.mul.xml" not in prompt


def test_prompt_has_schemafix_array_type_instructions():
    prompt = render_korean_advanced_prompt_v1(segment())
    assert "terms만 object array" in prompt
    assert "grammar_notes는 반드시 string array" in prompt
    assert "doctrinal_notes는 반드시 string array" in prompt
    assert "uncertainties는 반드시 string array" in prompt
    assert "quality_flags는 반드시 string array" in prompt
    assert '{"note": "..."}' in prompt
    assert "배열 타입 금지 예" in prompt


def test_prompt_clarifies_grammar_notes_are_not_full_morphology():
    prompt = render_korean_advanced_prompt_v1(segment())
    assert "grammar_notes는 모든 단어를 하나씩 분석하는 필드가 아닙니다" in prompt
    assert "모든 단어의 품사/격/수/성/어근" in prompt
    assert "별도 morphology pipeline" in prompt


def test_prompt_clarifies_terms_are_not_full_glossary():
    prompt = render_korean_advanced_prompt_v1(segment())
    assert "terms는 모든 단어의 단어장이 아닙니다" in prompt
    assert "핵심 빠알리 교리 용어, 문헌명, 인명, 중요한 복합어" in prompt
    assert "너무 쉬운 일반어" in prompt


def test_prompt_includes_literature_and_genre_name_policy():
    prompt = render_korean_advanced_prompt_v1(segment())
    assert "문헌명/장르명 표기 정책" in prompt
    assert "Jātaka" in prompt
    assert "Therīgāthā" in prompt
    assert "Dhammasaṅgaṇī" in prompt
    assert "Aṭṭhakathā" in prompt
    assert "Ṭīkā" in prompt
    assert "Vaṇṇanā" in prompt


def test_prompt_includes_qa_patch_v2_terminology_rules():
    prompt = render_korean_advanced_prompt_v1(segment())
    assert 'khandha → 기본 역어는 "무더기"' in prompt
    assert '일반적으로 "무리"로 번역하지 마십시오' in prompt
    assert 'manasikāra → 기본 역어는 "마음에 잡도리함"' in prompt
    assert 'yoniso manasikāra는 "여리작의"' in prompt
    assert "uppala와 paduma를 같은 한국어로 번역하지 마십시오" in prompt
    assert "dhīra와 paṇḍita는 의미가 가까워도 같은 한국어로 번역하지 마십시오" in prompt
    assert "anulomika khanti 등 진리 수용의 의미가 강한 문맥" in prompt


def test_prompt_includes_qa_patch_v2_uncertainties_policy():
    prompt = render_korean_advanced_prompt_v1(segment())
    assert "더 적절하거나 더 개연성 높은 해석을 발견했다면 literal_ko와 natural_ko 본문을 그 해석으로 갱신" in prompt
    assert "uncertainties에는 최종적으로 채택하지 않은 대안 해석만 기록" in prompt
    assert "더 나은 해석을 uncertainties에만 적고 본문에는 덜 적절한 해석을 유지하지 마십시오" in prompt
    assert "고유명사의 격 해석이나 구문 분석이 둘 이상 가능할 경우" in prompt
    assert "무언의 정규화는 하지 마십시오" in prompt


def test_validate_korean_advanced_model_output_accepts_valid_payload():
    translation = validate_korean_advanced_model_output(
        {
            **valid_output(),
            "quality_flags": ["grammar_uncertain"],
        }
    )
    assert translation.literal_ko
    assert translation.quality_flags[0].value == "grammar_uncertain"


def test_validate_korean_advanced_model_output_rejects_extra_field():
    with pytest.raises(ValidationError):
        validate_korean_advanced_model_output(
            {
                **valid_output(),
                "english_translation": "This must not be accepted.",
            }
        )


def test_validate_korean_advanced_model_output_rejects_local_validator_flag():
    with pytest.raises(ValueError, match="disallowed quality_flags"):
        validate_korean_advanced_model_output(
            {
                **valid_output(),
                "quality_flags": ["json_parse_failed"],
            }
        )


def test_validate_rejects_grammar_notes_object_array():
    with pytest.raises(ValidationError):
        validate_korean_advanced_model_output(
            {
                **valid_output(),
                "grammar_notes": [{"note": "object array must fail"}],
            }
        )


def test_validate_rejects_doctrinal_notes_object_array():
    with pytest.raises(ValidationError):
        validate_korean_advanced_model_output(
            {
                **valid_output(),
                "doctrinal_notes": [{"note": "object array must fail"}],
            }
        )


def test_validate_rejects_uncertainties_object_array():
    with pytest.raises(ValidationError):
        validate_korean_advanced_model_output(
            {
                **valid_output(),
                "uncertainties": [{"note": "object array must fail"}],
            }
        )


def test_validate_accepts_valid_string_arrays():
    translation = validate_korean_advanced_model_output(
        {
            **valid_output(),
            "grammar_notes": ["복수 속격으로 부분속격의 의미를 가진다."],
            "doctrinal_notes": ["이 문맥에서 조건 지어진 현상을 가리킨다."],
            "uncertainties": ["복합어 해석은 문맥에 따라 달라질 수 있다."],
        }
    )
    assert translation.grammar_notes[0].startswith("복수")
    assert translation.doctrinal_notes[0].startswith("이 문맥")
    assert translation.uncertainties[0].startswith("복합어")


def test_prompt_manifest_constants():
    assert KOREAN_ADVANCED_PROMPT_ID == "korean_advanced"
    assert KOREAN_ADVANCED_PROMPT_VERSION == "korean_advanced_v1_schemafix_qa_patch_v2"

from pydantic import ValidationError

from backend.pali.translation.quality import detect_quality_flag_details, detect_quality_flags
from backend.pali.translation.schemas import (
    KoreanAdvancedTranslation,
    QualityFlag,
    QualityFlagDetail,
    QualityFlagSource,
    TranslationJobStatus,
    TranslationVersionStatus,
)
from backend.pali.translation.workflow import is_terminal_status


def test_translation_job_status_enum():
    assert TranslationJobStatus.PENDING.value == "pending"
    assert TranslationJobStatus.NEEDS_REVIEW.value == "needs_review"
    assert is_terminal_status(TranslationJobStatus.SUCCEEDED) is True
    assert is_terminal_status(TranslationJobStatus.RUNNING) is False


def test_translation_version_status_enum():
    assert TranslationVersionStatus.MACHINE_DRAFT.value == "machine_draft"
    assert TranslationVersionStatus.PUBLISHED.value == "published"


def test_quality_flag_detection_too_short():
    translation = KoreanAdvancedTranslation(literal_ko="짧음", natural_ko="짧음")
    flags = detect_quality_flags("A" * 200, translation)
    assert QualityFlag.TOO_SHORT in flags


def test_quality_flag_detection_untranslated_pali():
    translation = KoreanAdvancedTranslation(
        literal_ko="aniccā는 무상이다.",
        natural_ko="aniccā는 무상을 뜻한다.",
    )
    flags = detect_quality_flags("aniccā", translation)
    assert QualityFlag.CONTAINS_UNTRANSLATED_PALI in flags


def test_quality_flag_detail_sources():
    translation = KoreanAdvancedTranslation(
        literal_ko="aniccā는 무상이다.",
        natural_ko="aniccā는 무상을 뜻한다.",
        uncertainties=["case ending is ambiguous"],
    )
    details = detect_quality_flag_details("aniccā", translation)
    by_flag = {detail.flag: detail for detail in details}
    assert by_flag[QualityFlag.CONTAINS_UNTRANSLATED_PALI].source == (
        QualityFlagSource.LOCAL_VALIDATOR
    )
    assert by_flag[QualityFlag.GRAMMAR_UNCERTAIN].source == (
        QualityFlagSource.MODEL_SELF_REPORT
    )


def test_korean_advanced_schema_validation():
    translation = KoreanAdvancedTranslation(
        literal_ko="직역",
        natural_ko="자연스러운 번역",
        terms=[{"pali": "anicca", "ko": "무상", "gloss": "impermanent"}],
        grammar_notes=["형용사로 쓰임"],
        doctrinal_notes=["삼특상 문맥"],
        quality_flag_details=[
            QualityFlagDetail(
                flag=QualityFlag.NEEDS_HUMAN_REVIEW,
                source=QualityFlagSource.HUMAN_ADMIN,
                message="Important passage",
            )
        ],
    )
    assert translation.terms[0].ko == "무상"
    assert translation.quality_flag_details[0].source == QualityFlagSource.HUMAN_ADMIN

    try:
        KoreanAdvancedTranslation(literal_ko="", natural_ko="")
    except ValidationError:
        pass
    else:
        raise AssertionError("empty KoreanAdvancedTranslation should fail validation")

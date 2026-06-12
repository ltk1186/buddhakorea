"""Schema skeletons for future Pali translation workflows.

These models are intentionally persistence-agnostic and do not call LLM APIs.
"""

from __future__ import annotations

from enum import StrEnum

from pydantic import BaseModel, Field


class TranslationJobStatus(StrEnum):
    PENDING = "pending"
    RUNNING = "running"
    SUCCEEDED = "succeeded"
    FAILED = "failed"
    RETRYING = "retrying"
    NEEDS_REVIEW = "needs_review"
    CANCELLED = "cancelled"
    SKIPPED = "skipped"


class TranslationVersionStatus(StrEnum):
    MACHINE_DRAFT = "machine_draft"
    MACHINE_REVIEWED = "machine_reviewed"
    HUMAN_REVIEWED = "human_reviewed"
    PUBLISHED = "published"
    DEPRECATED = "deprecated"
    REJECTED = "rejected"


class QualityFlag(StrEnum):
    JSON_PARSE_FAILED = "json_parse_failed"
    SCHEMA_VALIDATION_FAILED = "schema_validation_failed"
    EMPTY_TRANSLATION = "empty_translation"
    TOO_SHORT = "too_short"
    TOO_LONG = "too_long"
    CONTAINS_UNTRANSLATED_PALI = "contains_untranslated_pali"
    GLOSSARY_CONFLICT = "glossary_conflict"
    DOCTRINAL_RISK = "doctrinal_risk"
    GRAMMAR_UNCERTAIN = "grammar_uncertain"
    LOW_CONFIDENCE = "low_confidence"
    NEEDS_HUMAN_REVIEW = "needs_human_review"
    READER_FEEDBACK = "reader_feedback"
    IMPORTANT_DOCTRINAL_SEGMENT = "important_doctrinal_segment"


class QualityFlagSource(StrEnum):
    LOCAL_VALIDATOR = "local_validator"
    MODEL_SELF_REPORT = "model_self_report"
    HUMAN_ADMIN = "human_admin"
    READER_FEEDBACK = "reader_feedback"


class QualityFlagSeverity(StrEnum):
    INFO = "info"
    WARNING = "warning"
    ERROR = "error"


class QualityFlagDetail(BaseModel):
    flag: QualityFlag
    source: QualityFlagSource
    severity: QualityFlagSeverity = QualityFlagSeverity.WARNING
    message: str = ""
    evidence: dict[str, str | int | float | bool | None] = Field(default_factory=dict)


class KoreanAdvancedTerm(BaseModel):
    pali: str
    ko: str
    gloss: str = ""
    note: str = ""


class KoreanAdvancedTranslation(BaseModel):
    literal_ko: str = Field(min_length=1)
    natural_ko: str = Field(min_length=1)
    terms: list[KoreanAdvancedTerm] = Field(default_factory=list)
    grammar_notes: list[str] = Field(default_factory=list)
    doctrinal_notes: list[str] = Field(default_factory=list)
    uncertainties: list[str] = Field(default_factory=list)
    quality_flags: list[QualityFlag] = Field(default_factory=list)
    quality_flag_details: list[QualityFlagDetail] = Field(default_factory=list)


class TranslationJobCandidate(BaseModel):
    source_commit: str
    scope_type: str
    scope_value: str
    target_language: str = "ko"
    output_profile: str = "korean_advanced"
    default_provider: str = "gemini"
    default_model: str
    arbitration_provider: str = "openai"
    arbitration_model: str
    prompt_id: str
    prompt_version: str

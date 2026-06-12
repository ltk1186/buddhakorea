"""Deterministic quality checks for generated translation drafts."""

from __future__ import annotations

import re

from .schemas import (
    KoreanAdvancedTranslation,
    QualityFlag,
    QualityFlagDetail,
    QualityFlagSeverity,
    QualityFlagSource,
)


PALI_DIACRITIC_RE = re.compile(r"[āīūṅñṭḍṇḷṃĀĪŪṄÑṬḌṆḶṂ]")


def detect_quality_flags(
    source_text: str,
    translation: KoreanAdvancedTranslation,
    *,
    min_ratio: float = 0.08,
    max_ratio: float = 8.0,
) -> list[QualityFlag]:
    return sorted({detail.flag for detail in detect_quality_flag_details(
        source_text,
        translation,
        min_ratio=min_ratio,
        max_ratio=max_ratio,
    )}, key=lambda item: item.value)


def detect_quality_flag_details(
    source_text: str,
    translation: KoreanAdvancedTranslation,
    *,
    min_ratio: float = 0.08,
    max_ratio: float = 8.0,
) -> list[QualityFlagDetail]:
    details: list[QualityFlagDetail] = list(translation.quality_flag_details)
    for flag in translation.quality_flags:
        details.append(
            QualityFlagDetail(
                flag=flag,
                source=QualityFlagSource.MODEL_SELF_REPORT,
                message="Flag supplied by model output.",
            )
        )
    combined = f"{translation.literal_ko} {translation.natural_ko}".strip()

    if not combined:
        details.append(
            QualityFlagDetail(
                flag=QualityFlag.EMPTY_TRANSLATION,
                source=QualityFlagSource.LOCAL_VALIDATOR,
                severity=QualityFlagSeverity.ERROR,
                message="literal_ko and natural_ko are both empty.",
            )
        )
        return dedupe_details(details)

    source_len = max(len(source_text.strip()), 1)
    output_len = len(combined)
    ratio = output_len / source_len

    if ratio < min_ratio:
        details.append(
            QualityFlagDetail(
                flag=QualityFlag.TOO_SHORT,
                source=QualityFlagSource.LOCAL_VALIDATOR,
                message="Translation is shorter than configured source/output ratio.",
                evidence={"ratio": round(ratio, 4), "min_ratio": min_ratio},
            )
        )
    if ratio > max_ratio:
        details.append(
            QualityFlagDetail(
                flag=QualityFlag.TOO_LONG,
                source=QualityFlagSource.LOCAL_VALIDATOR,
                message="Translation is longer than configured source/output ratio.",
                evidence={"ratio": round(ratio, 4), "max_ratio": max_ratio},
            )
        )
    if contains_untranslated_pali(combined):
        details.append(
            QualityFlagDetail(
                flag=QualityFlag.CONTAINS_UNTRANSLATED_PALI,
                source=QualityFlagSource.LOCAL_VALIDATOR,
                message="Korean translation fields contain Pali diacritics.",
            )
        )
    if translation.uncertainties:
        details.append(
            QualityFlagDetail(
                flag=QualityFlag.GRAMMAR_UNCERTAIN,
                source=QualityFlagSource.MODEL_SELF_REPORT,
                message="Model output included uncertainties.",
                evidence={"uncertainty_count": len(translation.uncertainties)},
            )
        )

    return dedupe_details(details)


def contains_untranslated_pali(text: str) -> bool:
    return bool(PALI_DIACRITIC_RE.search(text))


def dedupe_details(details: list[QualityFlagDetail]) -> list[QualityFlagDetail]:
    seen: set[tuple[QualityFlag, QualityFlagSource]] = set()
    deduped: list[QualityFlagDetail] = []
    for detail in details:
        key = (detail.flag, detail.source)
        if key in seen:
            continue
        seen.add(key)
        deduped.append(detail)
    return sorted(deduped, key=lambda item: (item.flag.value, item.source.value))

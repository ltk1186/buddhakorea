"""Source integrity helpers for Pali translation QA."""

from __future__ import annotations

import hashlib
from typing import Any


REQUIRED_IDENTITY_FIELDS = ("stable_segment_key", "source_text_hash")


def compute_source_hashes(raw_source_text: str, normalized_source_text: str | None = None) -> dict[str, str]:
    """Return sha256 hashes for raw and normalized source text."""

    normalized = raw_source_text if normalized_source_text is None else normalized_source_text
    return {
        "raw_source_text_hash": _sha256(raw_source_text),
        "normalized_source_text_hash": _sha256(normalized),
    }


def detect_silent_normalization(
    raw_source_text: str,
    translation_source_text: str,
    normalization_notes: list[str] | str | None,
) -> list[str]:
    """Detect source changes that have no explicit normalization note."""

    notes = _notes_as_list(normalization_notes)
    if raw_source_text != translation_source_text and not notes:
        return ["silent_source_normalization"]
    return []


def validate_source_integrity_record(record: dict[str, Any]) -> dict[str, Any]:
    """Validate identity/hash fields in one source integrity record."""

    errors: list[str] = []
    warnings: list[str] = []
    for field in REQUIRED_IDENTITY_FIELDS:
        if not record.get(field):
            errors.append(f"missing_field:{field}")

    raw = str(record.get("raw_source_text") or record.get("original_text") or "")
    normalized = str(record.get("normalized_source_text") or record.get("normalized_text") or raw)
    if raw:
        hashes = compute_source_hashes(raw, normalized)
        expected_raw = record.get("raw_source_text_hash")
        expected_normalized = record.get("normalized_source_text_hash")
        if expected_raw and expected_raw != hashes["raw_source_text_hash"]:
            errors.append("raw_source_hash_mismatch")
        if expected_normalized and expected_normalized != hashes["normalized_source_text_hash"]:
            errors.append("normalized_source_hash_mismatch")
    else:
        warnings.append("missing_raw_source_text")

    return {"valid": not errors, "errors": errors, "warnings": warnings}


def check_integrity(segment_record: dict[str, Any]) -> dict[str, Any]:
    """Check one parsed segment/source record for production integrity gaps."""

    validation = validate_source_integrity_record(segment_record)
    raw = str(segment_record.get("raw_source_text") or segment_record.get("original_text") or "")
    display = str(segment_record.get("display_source_text") or segment_record.get("original_text") or raw)
    translation_source = str(
        segment_record.get("translation_source_text")
        or segment_record.get("normalized_source_text")
        or segment_record.get("original_text")
        or raw
    )
    notes = segment_record.get("normalization_notes")
    flags = list(validation["errors"])
    flags.extend(detect_silent_normalization(raw, translation_source, notes))
    gaps = []
    for field in ("raw_source_text", "display_source_text", "translation_source_text", "normalization_notes"):
        if field not in segment_record:
            gaps.append(f"missing_field:{field}")

    return {
        "stable_segment_key": segment_record.get("stable_segment_key", ""),
        "valid": not flags,
        "flags": sorted(set(flags)),
        "warnings": validation["warnings"],
        "gaps": gaps,
        "raw_equals_display": raw == display,
        "raw_equals_translation_source": raw == translation_source,
    }


def _sha256(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def _notes_as_list(notes: list[str] | str | None) -> list[str]:
    if notes is None:
        return []
    if isinstance(notes, str):
        return [notes] if notes.strip() else []
    return [str(note) for note in notes if str(note).strip()]

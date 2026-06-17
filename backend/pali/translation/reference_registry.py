"""Parallel reference registry helpers.

This module stores locator and divergence metadata only. It must not store,
fetch, compare, or publish protected external translation bodies.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any


PROTECTED_BODY_FIELDS = {
    "translation_text",
    "parallel_translation_text",
    "external_translation_text",
    "protected_translation_text",
    "quote",
    "quoted_text",
    "excerpt",
    "body",
    "full_text",
}
SOURCE_TYPES = {"cc0_storable", "copyright_eyes_only", "unknown_unverified"}
ALLOWED_REFERENCE_FIELDS = {
    "segment_key",
    "stable_segment_key",
    "edition",
    "ref_locator",
    "has_parallel",
    "divergence_flag",
    "divergence_category",
    "divergence_note",
    "operator_marked",
    "references",
    "source_type",
    "license",
    "provenance",
}


def load_parallel_registry(path: str | Path) -> dict[str, Any]:
    """Load a local reference registry."""

    return json.loads(Path(path).read_text(encoding="utf-8"))


def validate_reference_entry(entry: dict[str, Any]) -> dict[str, Any]:
    """Validate that a reference entry contains locator metadata only."""

    errors = _protected_field_errors(entry)
    source_type = entry.get("source_type", "unknown_unverified")
    if source_type not in SOURCE_TYPES:
        errors.append("invalid_source_type")
    unknown = sorted(str(key) for key in entry if key not in ALLOWED_REFERENCE_FIELDS)
    warnings = [f"unknown_field:{key}" for key in unknown]
    warnings.extend(_long_note_warnings(entry))
    return {"valid": not errors, "errors": errors, "warnings": warnings}


def flag_reference_divergence(segment_key: str, registry: dict[str, Any] | list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Return operator-marked divergence records for a segment.

    This function does not fetch external translations and does not compare
    English/Korean text. It only returns registry metadata already present.
    """

    entries = _entries(registry)
    matches = []
    for entry in entries:
        key = entry.get("stable_segment_key") or entry.get("segment_key")
        if key != segment_key or not entry.get("divergence_flag"):
            continue
        matches.append(
            {
                "stable_segment_key": segment_key,
                "edition": entry.get("edition", ""),
                "ref_locator": entry.get("ref_locator", ""),
                "divergence_flag": bool(entry.get("divergence_flag")),
                "divergence_category": entry.get("divergence_category", ""),
                "divergence_note": entry.get("divergence_note", ""),
                "operator_marked": bool(entry.get("operator_marked", True)),
                "source_type": entry.get("source_type", "unknown_unverified"),
            }
        )
    return matches


def is_automatic_comparison_candidate(entry: dict[str, Any]) -> bool:
    """Return whether a reference is a future automatic comparison candidate.

    Even for `cc0_storable`, live comparison requires separate coverage,
    license, provenance, and user green-light checks outside this skeleton.
    """

    return entry.get("source_type") == "cc0_storable"


def _entries(registry: dict[str, Any] | list[dict[str, Any]]) -> list[dict[str, Any]]:
    if isinstance(registry, dict):
        value = registry.get("entries", [])
    else:
        value = registry
    return [item for item in value if isinstance(item, dict)]


def _protected_field_errors(value: Any, path: str = "") -> list[str]:
    errors: list[str] = []
    if isinstance(value, dict):
        for key, child in value.items():
            key_path = f"{path}.{key}" if path else str(key)
            if str(key) in PROTECTED_BODY_FIELDS:
                errors.append(f"protected_translation_body_field:{key_path}")
            errors.extend(_protected_field_errors(child, key_path))
    elif isinstance(value, list):
        for index, child in enumerate(value):
            errors.extend(_protected_field_errors(child, f"{path}[{index}]"))
    return errors


def _long_note_warnings(value: Any, path: str = "") -> list[str]:
    warnings: list[str] = []
    if isinstance(value, dict):
        for key, child in value.items():
            key_path = f"{path}.{key}" if path else str(key)
            if str(key) in {"note", "divergence_note"}:
                word_count = len(str(child).split())
                if word_count > 30:
                    warnings.append(f"long_reference_note:{key_path}:{word_count}_words")
            warnings.extend(_long_note_warnings(child, key_path))
    elif isinstance(value, list):
        for index, child in enumerate(value):
            warnings.extend(_long_note_warnings(child, f"{path}[{index}]"))
    return warnings

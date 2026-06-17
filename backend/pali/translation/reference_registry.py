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
}


def load_parallel_registry(path: str | Path) -> dict[str, Any]:
    """Load a local reference registry."""

    return json.loads(Path(path).read_text(encoding="utf-8"))


def validate_reference_entry(entry: dict[str, Any]) -> dict[str, Any]:
    """Validate that a reference entry contains locator metadata only."""

    errors = _protected_field_errors(entry)
    unknown = sorted(str(key) for key in entry if key not in ALLOWED_REFERENCE_FIELDS)
    warnings = [f"unknown_field:{key}" for key in unknown]
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
            }
        )
    return matches


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

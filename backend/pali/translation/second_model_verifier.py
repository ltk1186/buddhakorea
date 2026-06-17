"""Second-model correctness triage skeleton.

This module is a triage amplifier, not an answer key. Agreement with a future
secondary model does not prove correctness, and disagreement does not prove a
mistranslation. Disagreement only raises review priority for a flagged subset.

No live provider calls are implemented here.
"""

from __future__ import annotations

from typing import Any


def verify_segment(
    source_pali: str,
    korean_translation: str,
    *,
    provider: str,
    enabled: bool = False,
    flagged_subset: bool = True,
) -> dict[str, Any]:
    """Return a disabled verifier result or raise for live verification.

    The verifier is designed only for flagged subsets. It is not a full-corpus
    correctness oracle and must not be used for exhaustive validation.
    """

    if not flagged_subset:
        raise ValueError("second_model_verifier_is_flagged_subset_only")
    if not enabled:
        return {
            "enabled": False,
            "provider": provider,
            "agree": None,
            "disagreements": [],
            "raw": None,
            "status": "disabled_no_live_call",
            "review_signal": None,
            "note": "Second model verification is disabled; no live call was made.",
        }
    raise NotImplementedError(
        "Second-model live verification requires explicit user green-light and is not implemented in v1.2."
    )


def map_second_model_result_to_review_signal(result: dict[str, Any]) -> str | None:
    """Map a future verifier result to a review signal.

    A disagreement is a Priority B review signal, not proof of error.
    """

    if result.get("agree") is False or result.get("disagreements"):
        return "second_model_disagreement"
    return None


def classify_oracle_availability(segment: dict[str, Any], reference_registry: dict[str, Any] | None = None) -> str:
    """Classify future triage availability without live comparison."""

    layer = str(segment.get("text_layer", ""))
    key = str(segment.get("stable_segment_key", ""))
    if reference_registry:
        for entry in reference_registry.get("entries", []) or []:
            if not isinstance(entry, dict):
                continue
            entry_key = entry.get("stable_segment_key") or entry.get("segment_key")
            if entry_key == key and entry.get("source_type") == "cc0_storable":
                return "cc0_parallel_candidate"
            if entry_key == key and entry.get("source_type") == "copyright_eyes_only":
                return "copyright_eyes_only_reference_candidate"
    if layer in {"atthakatha", "tika"}:
        return "oracle_unavailable"
    return "second_model_verifier_candidate"

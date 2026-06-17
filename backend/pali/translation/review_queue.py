"""Deterministic review queue helpers for Pali translation QA."""

from __future__ import annotations

from typing import Any, Iterable


PRIORITY_A_SIGNALS = {
    "schema_invalid",
    "schema_validation_failed",
    "parse_failed",
    "json_parse_failed",
    "possible_true_untranslated_pali",
    "glossary_conflict",
    "avoid_ko_conflict_candidate",
    "cross_term_collision_review",
    "gold_regression_worsened",
    "source_hash_mismatch",
    "silent_source_normalization",
    "raw_source_hash_mismatch",
    "normalized_source_hash_mismatch",
    "high_divergence_candidate",
}
PRIORITY_B_SIGNALS = {
    "grammar_uncertain",
    "doctrinal_risk",
    "low_confidence",
    "needs_human_review",
    "needs_human_glossary_review",
    "unexpected_variant",
    "reference_only_gold",
    "second_model_disagreement",
    "cc0_parallel_disagreement",
    "oracle_unavailable",
}
PRIORITY_C_SIGNALS = {
    "random_sample",
    "long_segment_sample",
    "verse_sample",
    "tika_sample",
    "title_sample",
    "citation_heavy_sample",
}
AUTO_RESOLVABLE_SIGNALS = {
    "allowed_parenthetical_pali",
    "allowed_bracketed_pali",
    "allowed_text_title",
    "allowed_person_name",
    "allowed_citation_abbreviation",
    "allowed_technical_term",
    "citation_mapping_missing",
    "source_display_mapping_missing",
    "number_only_routing",
    "title_only_routing",
}


def build_review_queue(
    parsed_results: dict[str, Any] | list[dict[str, Any]],
    qa_reports: dict[str, Any] | list[dict[str, Any]] | None = None,
) -> dict[str, Any]:
    """Build a deduplicated risk-based review queue."""

    suppress_raw_untranslated = _allowed_untranslated_keys(qa_reports)
    candidates = _candidate_items_from_parsed(
        parsed_results,
        suppress_raw_untranslated=suppress_raw_untranslated,
    )
    candidates.extend(_candidate_items_from_qa_reports(qa_reports))

    grouped: dict[str, dict[str, Any]] = {}
    for candidate in candidates:
        group_key = dedup_group_key(candidate)
        if group_key not in grouped:
            grouped[group_key] = {**candidate, "dedup_group_key": group_key, "recurrence_count": 0}
        grouped[group_key]["recurrence_count"] += int(candidate.get("recurrence_count", 1) or 1)
        grouped[group_key].setdefault("example_stable_segment_keys", [])
        key = candidate.get("stable_segment_key")
        if key and key not in grouped[group_key]["example_stable_segment_keys"]:
            grouped[group_key]["example_stable_segment_keys"].append(key)

    items = []
    for item in grouped.values():
        signals = set(item.get("signals", []))
        item["priority"] = classify_priority(signals)
        item["auto_resolvable"] = is_auto_resolvable(item)
        item["human_needed"] = not item["auto_resolvable"]
        item["review_tier"] = classify_review_tier(item)
        item["estimated_review_minutes"] = estimate_review_minutes(item)
        items.append(item)

    priority_order = {"A": 0, "B": 1, "C": 2}
    items.sort(key=lambda item: (priority_order[item["priority"]], -item["recurrence_count"], item["dedup_group_key"]))

    return {
        "total_raw_candidates": len(candidates),
        "deduped_item_count": len(items),
        "priority_counts": _count_by(items, "priority"),
        "auto_resolvable_count": sum(1 for item in items if item["auto_resolvable"]),
        "human_needed_count": sum(1 for item in items if item["human_needed"]),
        "items": items,
        "auto_resolvable": [item for item in items if item["auto_resolvable"]],
        "human_needed": [item for item in items if item["human_needed"]],
    }


def dedup_group_key(item: dict[str, Any]) -> str:
    if item.get("dedup_group_key"):
        return str(item["dedup_group_key"])
    if item.get("dedup_group"):
        return str(item["dedup_group"])
    signals = sorted(str(signal) for signal in item.get("signals", []))
    signal = signals[0] if signals else "unknown_signal"
    term = item.get("pali") or item.get("citation") or item.get("reference") or item.get("field")
    if term:
        return f"{signal}:{term}"
    return f"{signal}:{item.get('stable_segment_key', 'unknown_segment')}"


def classify_priority(flags: Iterable[str]) -> str:
    flag_set = set(flags)
    if flag_set & PRIORITY_A_SIGNALS:
        return "A"
    if flag_set & PRIORITY_B_SIGNALS:
        return "B"
    return "C"


def estimate_review_minutes(item: dict[str, Any]) -> int:
    if item.get("auto_resolvable"):
        return 1
    if item.get("priority") == "A":
        return 5
    if item.get("priority") == "B":
        return 3
    return 1


def is_auto_resolvable(item: dict[str, Any]) -> bool:
    signals = set(item.get("signals", []))
    return bool(signals) and signals <= AUTO_RESOLVABLE_SIGNALS


def classify_review_tier(item: dict[str, Any]) -> str:
    signals = set(item.get("signals", []))
    if item.get("auto_resolvable"):
        return "tier_1_operator"
    if {
        "source_hash_mismatch",
        "silent_source_normalization",
        "raw_source_hash_mismatch",
        "normalized_source_hash_mismatch",
    } & signals:
        return "tier_source_integrity_operator"
    if {"gold_regression_worsened"} & signals:
        return "tier_3_pali_expert"
    if {"glossary_conflict", "cross_term_collision_review", "avoid_ko_conflict_candidate"} & signals:
        return "tier_2_buddhist_terms"
    if {"possible_true_untranslated_pali", "schema_invalid", "parse_failed"} & signals:
        return "tier_1_operator"
    return "tier_1_operator"


def _candidate_items_from_parsed(
    payload: dict[str, Any] | list[dict[str, Any]],
    *,
    suppress_raw_untranslated: set[str] | None = None,
) -> list[dict[str, Any]]:
    suppress_raw_untranslated = suppress_raw_untranslated or set()
    items = _segments_from_payload(payload)
    candidates = []
    for item in items:
        signals: list[str] = []
        if item.get("schema_valid") is False:
            signals.append("schema_invalid")
        if item.get("status") not in {None, "", "succeeded"}:
            signals.append(str(item.get("status")))
        for flag in item.get("local_validator_flags") or []:
            flag = str(flag)
            if (
                flag == "contains_untranslated_pali"
                and item.get("stable_segment_key") in suppress_raw_untranslated
            ):
                continue
            signals.append(flag)
        signals.extend(str(flag) for flag in item.get("quality_flags") or [])
        translation = item.get("parsed_translation_json") or {}
        if isinstance(translation, dict):
            signals.extend(str(flag) for flag in translation.get("quality_flags") or [])
        if not signals:
            continue
        candidates.append(
            {
                "stable_segment_key": item.get("stable_segment_key", ""),
                "source_path": item.get("source_path", ""),
                "text_layer": item.get("text_layer", ""),
                "chunk_type": item.get("chunk_type", ""),
                "length_bucket": item.get("length_bucket", ""),
                "signals": sorted(set(signals)),
            }
        )
    return candidates


def _candidate_items_from_qa_reports(qa_reports: dict[str, Any] | list[dict[str, Any]] | None) -> list[dict[str, Any]]:
    if qa_reports is None:
        return []
    if isinstance(qa_reports, list):
        return [item for item in qa_reports if isinstance(item, dict)]
    candidates: list[dict[str, Any]] = []

    for key in ("avoid_ko_conflicts", "same_segment_signals", "cross_term_collisions", "failed_items"):
        value = qa_reports.get(key, [])
        if isinstance(value, list):
            candidates.extend(_normalize_qa_item(item) for item in value if isinstance(item, dict))

    cross_metrics = qa_reports.get("cross_term_metrics", {})
    if isinstance(cross_metrics, dict):
        for item in cross_metrics.get("same_segment_signals", []) or []:
            if isinstance(item, dict):
                candidates.append(_normalize_qa_item(item))

    for item in qa_reports.get("untranslated_pali_reclassifications", []) or []:
        if not isinstance(item, dict):
            continue
        status = item.get("final_status")
        if status == "possible_true_untranslated_pali":
            candidates.append(
                {
                    "stable_segment_key": item.get("stable_segment_key", ""),
                    "signals": ["possible_true_untranslated_pali"],
                    "dedup_group_key": "possible_true_untranslated_pali",
                }
            )
        elif status == "allowed":
            classes = sorted((item.get("classification_counts") or {}).keys())
            for classification in classes:
                candidates.append(
                    {
                        "stable_segment_key": item.get("stable_segment_key", ""),
                        "signals": [classification],
                        "dedup_group_key": classification,
                    }
                )

    for result in qa_reports.get("gold_regression", []) or []:
        if not isinstance(result, dict):
            continue
        verdict = result.get("verdict")
        if verdict == "worsened":
            signal = "gold_regression_worsened"
        elif verdict == "escalate":
            signal = "reference_only_gold"
        else:
            continue
        candidates.append(
            {
                "stable_segment_key": result.get("stable_segment_key", ""),
                "signals": [signal],
                "dedup_group_key": f"{signal}:{result.get('gold_set_id', '')}",
            }
        )
    return candidates


def _allowed_untranslated_keys(qa_reports: dict[str, Any] | list[dict[str, Any]] | None) -> set[str]:
    if not isinstance(qa_reports, dict):
        return set()
    allowed = set()
    for item in qa_reports.get("untranslated_pali_reclassifications", []) or []:
        if not isinstance(item, dict):
            continue
        if item.get("final_status") == "allowed" and item.get("stable_segment_key"):
            allowed.add(str(item["stable_segment_key"]))
    return allowed


def _normalize_qa_item(item: dict[str, Any]) -> dict[str, Any]:
    signal = item.get("signal") or item.get("classification") or item.get("status") or "unknown_signal"
    return {
        "stable_segment_key": item.get("stable_segment_key", ""),
        "source_path": item.get("source_path", ""),
        "text_layer": item.get("text_layer", ""),
        "chunk_type": item.get("chunk_type", ""),
        "length_bucket": item.get("length_bucket", ""),
        "signals": [str(signal)],
        "pali": item.get("pali") or item.get("left_pali") or "",
        "citation": item.get("raw") or item.get("citation") or "",
        "dedup_group_key": item.get("dedup_group_key", ""),
    }


def _segments_from_payload(payload: dict[str, Any] | list[dict[str, Any]]) -> list[dict[str, Any]]:
    if isinstance(payload, dict):
        value = payload.get("items", [])
    else:
        value = payload
    return [item for item in value if isinstance(item, dict)]


def _count_by(items: list[dict[str, Any]], field: str) -> dict[str, int]:
    counts: dict[str, int] = {}
    for item in items:
        value = str(item.get(field, ""))
        counts[value] = counts.get(value, 0) + 1
    return counts

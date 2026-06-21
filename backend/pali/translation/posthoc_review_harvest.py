"""Step 3G-A post-hoc review harvest for the Pali 300 pilot.

This module is local-only and deterministic. It joins existing QA,
classifier, and apparatus evidence into review artifacts. It never modifies
source XML, translations, prompts, glossary data, or frozen gold data.
"""

from __future__ import annotations

import hashlib
import json
from collections import Counter, defaultdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


SCRIPT_VERSION = "pali_step_3g_a_posthoc_review_harvest_v0"
OUTPUT_SCHEMA_VERSION = "pali_step_3g_posthoc_review_harvest_v0"
FUTURE_TOTAL_BATCH_REQUESTS = 1020
FUTURE_BATCH_RULE = {
    "pilot_1000_new": 1000,
    "holdout_gold_regression": 20,
    "total_future_batch_requests": FUTURE_TOTAL_BATCH_REQUESTS,
    "rule": "1,000 new segments, disjoint from pilot_75 and pilot_300, plus 20 frozen holdout regression items intentionally re-included.",
    "step_3g_a_selects_1000_new": False,
    "step_3g_a_submits_batch": False,
}
DEFAULT_SEED_DECISION = {
    "seed_decision": "unadjudicated",
    "decision_source": "needs_manual_review_seed",
    "blocks_1000_pilot": False,
    "llm_retry_required": False,
    "expert_review_required": False,
}
HOLDOUT_ACCEPTANCE_TYPES = ["constraint", "exact", "reference"]
MUTATION_FLAGS = {
    "api_llm_calls": 0,
    "network_calls": 0,
    "translation_mutation": False,
    "source_mutation": False,
    "prompt_mutation": False,
    "glossary_mutation": False,
    "gold_set_mutation": False,
    "holdout_gold_frozen": False,
}


def run_posthoc_review_harvest(
    *,
    review_queue_reclassified: dict[str, Any],
    findings: dict[str, Any],
    parsed_payload: dict[str, Any],
    apparatus_crosscheck: dict[str, Any] | None,
    variant_apparatus: dict[str, Any] | None,
    pilot_300_manifest: dict[str, Any],
    gold_set: dict[str, Any] | None,
    seed_decisions: dict[str, Any] | list[Any] | None,
    seed_decisions_path: Path,
    out_dir: Path,
    input_paths: dict[str, Path],
    pretty: bool = False,
) -> dict[str, Any]:
    """Build Step 3G-A artifacts without making review decisions."""

    warnings: list[str] = []
    out_dir.mkdir(parents=True, exist_ok=True)

    parsed_by_key = index_by_key(parsed_payload.get("items", []))
    manifest_by_key = index_by_key(pilot_300_manifest.get("items", []))
    remaining_items = remaining_review_items(review_queue_reclassified)
    remaining_keys = [item["stable_segment_key"] for item in remaining_items if item.get("stable_segment_key")]

    apparatus_records = (variant_apparatus or {}).get("records", [])
    crosscheck_items = (apparatus_crosscheck or {}).get("items", [])
    apparatus_by_key = group_by_key(apparatus_records)
    crosscheck_by_key = {item.get("stable_segment_key"): item for item in crosscheck_items if item.get("stable_segment_key")}
    if not apparatus_crosscheck:
        warnings.append("apparatus_crosscheck_missing_internal_notes_may_be_incomplete")
    if not variant_apparatus:
        warnings.append("variant_apparatus_missing_internal_notes_empty")
    if gold_set is None:
        warnings.append("gold_set_missing_hash_only_context_unavailable")

    seed_exists = seed_decisions is not None
    seed_records = normalize_seed_decisions(seed_decisions) if seed_exists else []
    seed_by_key = {record.get("stable_segment_key"): record for record in seed_records if record.get("stable_segment_key")}
    if not seed_exists:
        warnings.append("seed_decisions_missing_manual_decisions_not_inferred")
    else:
        missing_seed_keys = [key for key in remaining_keys if key not in seed_by_key]
        if missing_seed_keys:
            warnings.append(f"seed_decisions_missing_for_remaining_items:{len(missing_seed_keys)}")

    seed_template = build_seed_decisions_template(remaining_items)
    internal_notes = build_internal_notes(apparatus_by_key, crosscheck_by_key)
    routed = build_routed_outputs(seed_records, remaining_items)
    candidate_payloads = routed["candidate_payloads"]
    resolved_items = routed["resolved_items"]
    routing_index = routed["routing_index"]
    attach_internal_note_counts(routing_index, internal_notes)
    if not seed_exists:
        for payload in candidate_payloads.values():
            payload["warnings"].append("manual_seed_decisions_missing_candidates_not_inferred")
        resolved_items["warnings"].append("manual_seed_decisions_missing_resolved_items_not_inferred")

    holdout_items, holdout_warnings = build_holdout_items(
        pilot_300_manifest=pilot_300_manifest,
        parsed_by_key=parsed_by_key,
        manifest_by_key=manifest_by_key,
        apparatus_by_key=apparatus_by_key,
    )
    warnings.extend(holdout_warnings)

    outputs = {
        "seed_decisions_ingested": out_dir / "seed_decisions_ingested.json",
        "internal_notes": out_dir / "internal_notes.json",
        "glossary_candidates": out_dir / "glossary_candidates.json",
        "reference_table_candidates": out_dir / "reference_table_candidates.json",
        "targeted_retry_candidates": out_dir / "targeted_retry_candidates.json",
        "expert_review_candidates": out_dir / "expert_review_candidates.json",
        "resolved_items": out_dir / "resolved_items.json",
        "remaining_routing_index": out_dir / "remaining_routing_index.json",
        "holdout_adjudication_template": out_dir / "holdout_adjudication_template.json",
        "holdout_gold_manifest_draft": out_dir / "holdout_gold_manifest_draft.json",
        "step_3g_summary": out_dir / "step_3g_summary.md",
        "run_manifest": out_dir / "run_manifest.json",
    }
    if not seed_exists:
        outputs["seed_decisions_template"] = out_dir / "seed_decisions_template.json"

    seed_ingested_payload = seed_decisions if seed_exists else {
        "schema_version": "pali_step_3g_seed_decisions_ingested_v0",
        "seed_file_exists": False,
        "ingested_decisions": [],
        "template_created": str(outputs["seed_decisions_template"]),
    }
    write_json(outputs["seed_decisions_ingested"], seed_ingested_payload, pretty=pretty)
    if not seed_exists:
        write_json(outputs["seed_decisions_template"], seed_template, pretty=pretty)
    write_json(outputs["internal_notes"], internal_notes, pretty=pretty)
    for name, payload in candidate_payloads.items():
        write_json(outputs[name], payload, pretty=pretty)
    write_json(outputs["resolved_items"], resolved_items, pretty=pretty)
    write_json(outputs["remaining_routing_index"], routing_index, pretty=pretty)

    holdout_template = build_holdout_template(holdout_items, warnings)
    holdout_draft = build_holdout_manifest_draft(holdout_items, warnings)
    write_json(outputs["holdout_adjudication_template"], holdout_template, pretty=pretty)
    write_json(outputs["holdout_gold_manifest_draft"], holdout_draft, pretty=pretty)

    summary_counts = {
        "remaining_review_items": len(remaining_items),
        "seed_decisions_ingested": len(seed_records),
        "internal_note_records": len(internal_notes["items"]),
        "internal_note_segments": len({item["stable_segment_key"] for item in internal_notes["items"]}),
        "glossary_candidates": len(candidate_payloads["glossary_candidates"]["items"]),
        "reference_table_candidates": len(candidate_payloads["reference_table_candidates"]["items"]),
        "targeted_retry_candidates": len(candidate_payloads["targeted_retry_candidates"]["items"]),
        "expert_review_candidates": len(candidate_payloads["expert_review_candidates"]["items"]),
        "resolved_items": len(resolved_items["items"]),
        "apparatus_internal_note_routes": routing_index["summary"]["apparatus_internal_note"],
        "routing_duplicates": routing_index["summary"]["duplicates"],
        "routing_missing": routing_index["summary"]["missing"],
        "seed_decision_null_leaks": routing_index["summary"]["seed_decision_null_leaks"],
        "holdout_template_items": len(holdout_items),
    }

    outputs["step_3g_summary"].write_text(
        render_summary(
            counts=summary_counts,
            warnings=warnings,
            seed_exists=seed_exists,
            holdout_items=holdout_items,
        ),
        encoding="utf-8",
    )

    manifest = build_run_manifest(
        input_paths=input_paths,
        output_paths=outputs,
        counts=summary_counts,
        warnings=warnings,
        seed_exists=seed_exists,
    )
    write_json(outputs["run_manifest"], manifest, pretty=pretty)

    return {
        "status": "STEP_3G_A_COMPLETE",
        **MUTATION_FLAGS,
        "manual_adjudication_required": True,
        "future_total_batch_requests": FUTURE_TOTAL_BATCH_REQUESTS,
        "remaining_review_items": len(remaining_items),
        "seed_decisions_ingested": len(seed_records),
        "internal_note_records": len(internal_notes["items"]),
        "holdout_template_items": len(holdout_items),
        "routing_duplicates": routing_index["summary"]["duplicates"],
        "routing_missing": routing_index["summary"]["missing"],
        "seed_decision_null_leaks": routing_index["summary"]["seed_decision_null_leaks"],
        "warnings": warnings,
        "out": str(out_dir),
    }


def remaining_review_items(review_queue_reclassified: dict[str, Any]) -> list[dict[str, Any]]:
    items = review_queue_reclassified.get("items", [])
    return [item for item in items if item.get("review_required_after_classification") is True]


def index_by_key(items: list[dict[str, Any]]) -> dict[str, dict[str, Any]]:
    return {item.get("stable_segment_key"): item for item in items if item.get("stable_segment_key")}


def group_by_key(items: list[dict[str, Any]]) -> dict[str, list[dict[str, Any]]]:
    grouped: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for item in items:
        key = item.get("stable_segment_key")
        if key:
            grouped[key].append(item)
    return dict(grouped)


def normalize_seed_decisions(seed_payload: dict[str, Any] | list[Any] | None) -> list[dict[str, Any]]:
    if seed_payload is None:
        return []
    if isinstance(seed_payload, list):
        return [item for item in seed_payload if isinstance(item, dict)]
    for key in ("decisions", "items", "seeds", "targets"):
        value = seed_payload.get(key)
        if isinstance(value, list):
            return [item for item in value if isinstance(item, dict)]
    return []


def build_seed_decisions_template(remaining_items: list[dict[str, Any]]) -> dict[str, Any]:
    template_items = []
    for item in remaining_items:
        original = item.get("original_queue_item", {})
        template_items.append(
            {
                "stable_segment_key": item.get("stable_segment_key"),
                "source_path": item.get("source_path"),
                "text_layer": item.get("text_layer"),
                "signals_before": item.get("signals_before", []),
                "signals_after": item.get("signals_after", []),
                "decision_before_seed": item.get("decision"),
                "review_required_after_classification": item.get("review_required_after_classification"),
                "priority_before": item.get("priority_before") or original.get("priority"),
                **DEFAULT_SEED_DECISION,
            }
        )
    return {
        "schema_version": "pali_step_3g_seed_decisions_template_v0",
        "status": "template_only_not_adjudicated",
        "manual_adjudication_required": True,
        "items": template_items,
    }


def build_internal_notes(
    apparatus_by_key: dict[str, list[dict[str, Any]]],
    crosscheck_by_key: dict[str, dict[str, Any]],
) -> dict[str, Any]:
    items = []
    for key in sorted(apparatus_by_key):
        crosscheck = crosscheck_by_key.get(key, {})
        status = crosscheck.get("classification", "source_variant_apparatus_present")
        for record in sorted(apparatus_by_key[key], key=lambda item: item.get("apparatus_id", "")):
            items.append(
                {
                    "stable_segment_key": key,
                    "apparatus_id": record.get("apparatus_id"),
                    "internal_note_type": "source_variant_apparatus",
                    "visibility": "internal",
                    "source_path": record.get("source_path"),
                    "main_reading": record.get("main_reading") or record.get("anchor_text") or "",
                    "variant_reading": record.get("variant_text") or "",
                    "raw_note_text": record.get("raw_note_text") or "",
                    "sigla": record.get("sigla", []),
                    "unknown_sigla": record.get("unknown_sigla", []),
                    "evidence_strength_hint": record.get("evidence_strength_hint", "unknown"),
                    "apparatus_status": status,
                    "review_policy": "internal_note_only",
                    "auto_modify_source": False,
                    "auto_modify_translation": False,
                    "llm_retry_required": False,
                    "reader_facing_public_note": False,
                    "auto_apply": False,
                }
            )
    return {
        "schema_version": "pali_step_3g_internal_notes_v0",
        "visibility": "internal",
        "policy": "apparatus-aware QA/review metadata only",
        "auto_modify_source": False,
        "auto_modify_translation": False,
        "llm_retry_required": False,
        "items": items,
        "summary": {
            "note_records": len(items),
            "segments": len({item["stable_segment_key"] for item in items}),
        },
    }


def build_routed_outputs(
    seed_records: list[dict[str, Any]],
    remaining_items: list[dict[str, Any]],
) -> dict[str, Any]:
    review_by_key = {item.get("stable_segment_key"): item for item in remaining_items if item.get("stable_segment_key")}
    seed_by_key = {record.get("stable_segment_key"): record for record in seed_records if record.get("stable_segment_key")}
    definitions = {
        "glossary_candidates": {
            "candidate_type": "glossary_candidate",
            "decision_values": {"glossary_candidate"},
            "flag_fields": {"glossary_candidate"},
            "policy": "manual seed decisions only; no glossary mutation",
        },
        "reference_table_candidates": {
            "candidate_type": "reference_table_candidate",
            "decision_values": {"reference_table_candidate"},
            "flag_fields": {"reference_table_candidate"},
            "policy": "manual seed decisions only unless a later mechanical reference rule is reviewed",
        },
        "targeted_retry_candidates": {
            "candidate_type": "targeted_retry_candidate",
            "decision_values": {"targeted_retry_candidate"},
            "flag_fields": {"targeted_retry_candidate", "llm_retry_required"},
            "policy": "manual seed decisions only; no automatic retry inference",
        },
        "expert_review_candidates": {
            "candidate_type": "expert_review_candidate",
            "decision_values": {"expert_review_candidate", "needs_expert_review"},
            "flag_fields": {"expert_review_candidate", "expert_review_required"},
            "policy": "manual seed decisions or pre-existing expert-review flags only",
        },
    }
    payloads = {
        name: {
            "schema_version": f"pali_step_3g_{name}_v0",
            "candidate_type": definition["candidate_type"],
            "policy": definition["policy"],
            "items": [],
            "warnings": [],
        }
        for name, definition in definitions.items()
    }
    resolved_items = {
        "schema_version": "pali_step_3g_resolved_items_v0",
        "candidate_type": "resolved_item",
        "policy": "manual seed decisions low_severity/no_action only",
        "items": [],
        "warnings": [],
    }
    route_items = []
    output_membership: dict[str, list[str]] = defaultdict(list)

    for review_item in remaining_items:
        key = review_item.get("stable_segment_key")
        record = seed_by_key.get(key)
        if record is not None:
            route = route_for_seed_decision(record.get("seed_decision"))
            append_seeded_route(
                key=key,
                route=route,
                seed_record=record,
                review_item=review_item,
                payloads=payloads,
                resolved_items=resolved_items,
                output_membership=output_membership,
            )
            route_items.append(route_index_item(key, record.get("seed_decision"), route, review_item))
            continue

        route = fallback_route_for_unseeded_item(review_item)
        if route["route_bucket"] == "expert_review_candidate":
            payloads["expert_review_candidates"]["items"].append(
                fallback_expert_item(review_item)
            )
            output_membership[key].append("expert_review_candidates.json")
        route_items.append(route_index_item(key, "unadjudicated", route, review_item, missing_route=route["missing_route"]))

    apply_routing_integrity(route_items, output_membership, seed_by_key, payloads, resolved_items)
    return {
        "candidate_payloads": payloads,
        "resolved_items": resolved_items,
        "routing_index": {
            "schema_version": "pali_step_3g_remaining_routing_index_v0",
            "policy": "manual seed decisions override stale pre-existing flags; fallback flags only apply to unseeded items",
            "items": route_items,
            "summary": routing_summary(route_items),
        },
    }


def route_for_seed_decision(seed_decision: Any) -> dict[str, Any]:
    decision = str(seed_decision or "")
    mapping = {
        "expert_review_candidate": ("expert_review_candidate", "expert_review_candidates.json", False),
        "glossary_candidate": ("glossary_candidate", "glossary_candidates.json", False),
        "reference_table_candidate": ("reference_table_candidate", "reference_table_candidates.json", False),
        "targeted_retry_candidate": ("targeted_retry_candidate", "targeted_retry_candidates.json", False),
        "low_severity": ("resolved", "resolved_items.json", False),
        "no_action": ("resolved", "resolved_items.json", False),
        "apparatus_internal_note": ("apparatus_internal_note", "internal_notes.json", False),
    }
    route_bucket, output_file, missing = mapping.get(decision, ("unadjudicated", "", True))
    return {"route_bucket": route_bucket, "output_file": output_file, "missing_route": missing}


def append_seeded_route(
    *,
    key: str,
    route: dict[str, Any],
    seed_record: dict[str, Any],
    review_item: dict[str, Any],
    payloads: dict[str, dict[str, Any]],
    resolved_items: dict[str, Any],
    output_membership: dict[str, list[str]],
) -> None:
    bucket = route["route_bucket"]
    output_file = route["output_file"]
    if bucket == "glossary_candidate":
        payloads["glossary_candidates"]["items"].append(candidate_item(seed_record, review_item))
    elif bucket == "reference_table_candidate":
        payloads["reference_table_candidates"]["items"].append(candidate_item(seed_record, review_item))
    elif bucket == "targeted_retry_candidate":
        payloads["targeted_retry_candidates"]["items"].append(candidate_item(seed_record, review_item))
    elif bucket == "expert_review_candidate":
        payloads["expert_review_candidates"]["items"].append(candidate_item(seed_record, review_item))
    elif bucket == "resolved":
        resolved_items["items"].append(resolved_item(seed_record, review_item))
    elif bucket == "apparatus_internal_note":
        pass
    if output_file:
        output_membership[key].append(output_file)


def candidate_item(seed_record: dict[str, Any], review_item: dict[str, Any]) -> dict[str, Any]:
    return {
        "stable_segment_key": seed_record.get("stable_segment_key"),
        "seed_decision": seed_record.get("seed_decision"),
        "decision_source": seed_record.get("decision_source", "manual_review_seed"),
        "expert_review_required": seed_record.get("expert_review_required", False),
        "rationale": seed_record.get("rationale", ""),
        "priority": seed_record.get("priority"),
        "target_hint": seed_record.get("target_hint"),
        "route_note": seed_record.get("route_note") or seed_record.get("note"),
        "seed_record": seed_record,
        "review_context": compact_review_context(review_item),
        "applied_now": False,
        "translation_mutation": False,
        "glossary_mutation": False,
        "gold_set_mutation": False,
    }


def resolved_item(seed_record: dict[str, Any], review_item: dict[str, Any]) -> dict[str, Any]:
    return {
        "stable_segment_key": seed_record.get("stable_segment_key"),
        "seed_decision": seed_record.get("seed_decision"),
        "decision_source": seed_record.get("decision_source", "manual_review_seed"),
        "review_required": False,
        "rationale": seed_record.get("rationale", ""),
        "priority": seed_record.get("priority"),
        "target_hint": seed_record.get("target_hint"),
        "route_note": seed_record.get("route_note") or seed_record.get("note"),
        "seed_record": seed_record,
        "review_context": compact_review_context(review_item),
        "applied_now": False,
        "translation_mutation": False,
        "glossary_mutation": False,
        "gold_set_mutation": False,
    }


def fallback_route_for_unseeded_item(review_item: dict[str, Any]) -> dict[str, Any]:
    if review_item.get("expert_question_candidate") is True:
        return {
            "route_bucket": "expert_review_candidate",
            "output_file": "expert_review_candidates.json",
            "missing_route": False,
        }
    return {
        "route_bucket": "unadjudicated",
        "output_file": "",
        "missing_route": True,
    }


def fallback_expert_item(review_item: dict[str, Any]) -> dict[str, Any]:
    return {
        "stable_segment_key": review_item.get("stable_segment_key"),
        "seed_decision": None,
        "decision_source": "pre_existing_expert_question_candidate_flag",
        "review_context": compact_review_context(review_item),
        "applied_now": False,
        "translation_mutation": False,
        "glossary_mutation": False,
        "gold_set_mutation": False,
    }


def route_index_item(
    key: str,
    seed_decision: Any,
    route: dict[str, Any],
    review_item: dict[str, Any],
    *,
    missing_route: bool | None = None,
) -> dict[str, Any]:
    return {
        "stable_segment_key": key,
        "seed_decision": seed_decision,
        "route_bucket": route["route_bucket"],
        "output_file": route["output_file"],
        "supporting_internal_note_count": 0,
        "duplicate_route": False,
        "missing_route": route["missing_route"] if missing_route is None else missing_route,
        "signals_after": review_item.get("signals_after", []),
        "review_required_after_classification": review_item.get("review_required_after_classification"),
    }


def apply_routing_integrity(
    route_items: list[dict[str, Any]],
    output_membership: dict[str, list[str]],
    seed_by_key: dict[str, dict[str, Any]],
    payloads: dict[str, dict[str, Any]],
    resolved_items: dict[str, Any],
) -> None:
    for item in route_items:
        key = item.get("stable_segment_key")
        membership = output_membership.get(key, [])
        item["duplicate_route"] = len(membership) > 1
        if item["route_bucket"] != "apparatus_internal_note":
            item["missing_route"] = item["missing_route"] or len(membership) == 0
    seeded_keys = set(seed_by_key)
    null_leak_keys = set()
    for payload in list(payloads.values()) + [resolved_items]:
        for payload_item in payload.get("items", []):
            key = payload_item.get("stable_segment_key")
            if key in seeded_keys and payload_item.get("seed_decision") is None:
                null_leak_keys.add(key)
    for item in route_items:
        item["seed_decision_null_leak"] = item.get("stable_segment_key") in null_leak_keys


def routing_summary(route_items: list[dict[str, Any]]) -> dict[str, int]:
    bucket_counts = Counter(item.get("route_bucket") for item in route_items)
    return {
        "total": len(route_items),
        "expert_review_candidate": bucket_counts["expert_review_candidate"],
        "glossary_candidate": bucket_counts["glossary_candidate"],
        "reference_table_candidate": bucket_counts["reference_table_candidate"],
        "targeted_retry_candidate": bucket_counts["targeted_retry_candidate"],
        "resolved": bucket_counts["resolved"],
        "apparatus_internal_note": bucket_counts["apparatus_internal_note"],
        "duplicates": sum(1 for item in route_items if item.get("duplicate_route")),
        "missing": sum(1 for item in route_items if item.get("missing_route")),
        "seed_decision_null_leaks": sum(1 for item in route_items if item.get("seed_decision_null_leak")),
    }


def attach_internal_note_counts(routing_index: dict[str, Any], internal_notes: dict[str, Any]) -> None:
    counts = Counter(item["stable_segment_key"] for item in internal_notes.get("items", []))
    for item in routing_index.get("items", []):
        item["supporting_internal_note_count"] = counts[item["stable_segment_key"]]
    routing_index["summary"] = routing_summary(routing_index.get("items", []))


def compact_review_context(item: dict[str, Any]) -> dict[str, Any]:
    if not item:
        return {}
    return {
        "source_path": item.get("source_path"),
        "text_layer": item.get("text_layer"),
        "signals_before": item.get("signals_before", []),
        "signals_after": item.get("signals_after", []),
        "decision": item.get("decision"),
        "review_required_after_classification": item.get("review_required_after_classification"),
    }


def build_holdout_items(
    *,
    pilot_300_manifest: dict[str, Any],
    parsed_by_key: dict[str, dict[str, Any]],
    manifest_by_key: dict[str, dict[str, Any]],
    apparatus_by_key: dict[str, list[dict[str, Any]]],
) -> tuple[list[dict[str, Any]], list[str]]:
    warnings: list[str] = []
    manifest_items = pilot_300_manifest.get("items", [])
    holdout_manifest_items = [
        item
        for item in manifest_items
        if item.get("gold_candidate") is True
        or item.get("pool_candidate") == "holdout_gold"
        or item.get("do_not_use_for_tuning_until_reviewed") is True
    ]
    if len(holdout_manifest_items) != 20:
        warnings.append(f"holdout_candidate_count_expected_20_actual_{len(holdout_manifest_items)}")
    items = []
    for manifest_item in sorted(holdout_manifest_items, key=lambda item: item.get("stable_segment_key", "")):
        key = manifest_item.get("stable_segment_key")
        parsed = parsed_by_key.get(key, {})
        source_text = parsed.get("original_text") or manifest_item.get("source_text") or ""
        if not parsed:
            warnings.append(f"holdout_candidate_missing_parsed_payload:{key}")
        items.append(
            {
                "stable_segment_key": key,
                "source_text": source_text,
                "existing_translation": {
                    "literal_ko": parsed.get("literal_ko", ""),
                    "natural_ko": parsed.get("natural_ko", ""),
                },
                "source_metadata": {
                    "source_path": manifest_item.get("source_path") or parsed.get("source_path"),
                    "layer": manifest_item.get("text_layer") or parsed.get("text_layer"),
                    "text_group": manifest_item.get("selection_group"),
                    "selection_bucket": manifest_item.get("selection_bucket"),
                    "chunk_type": manifest_item.get("chunk_type") or parsed.get("chunk_type"),
                    "length_bucket": manifest_item.get("length_bucket") or parsed.get("length_bucket"),
                    "pitaka": manifest_item.get("pitaka") or parsed.get("pitaka"),
                    "nikaya": manifest_item.get("nikaya") or parsed.get("nikaya"),
                },
                "apparatus": apparatus_by_key.get(key, []),
                "adjudication_status": "needs_human_adjudication",
                "suggested_acceptance_types": HOLDOUT_ACCEPTANCE_TYPES,
                "do_not_use_for_prompt_tuning": True,
                "do_not_use_for_glossary_tuning": True,
                "not_usable_for_prompt_tuning": True,
                "not_usable_for_glossary_tuning": True,
                "frozen": False,
                "holdout_gold_frozen": False,
            }
        )
    return items, warnings


def build_holdout_template(holdout_items: list[dict[str, Any]], warnings: list[str]) -> dict[str, Any]:
    return {
        "schema_version": "pali_step_3g_holdout_adjudication_template_v0",
        "status": "draft_not_frozen",
        "needs_human_adjudication": True,
        "not_usable_for_prompt_tuning": True,
        "not_usable_for_glossary_tuning": True,
        "holdout_gold_frozen": False,
        "items": holdout_items,
        "warnings": warnings,
    }


def build_holdout_manifest_draft(holdout_items: list[dict[str, Any]], warnings: list[str]) -> dict[str, Any]:
    return {
        "schema_version": "pali_step_3g_holdout_gold_manifest_draft_v0",
        "status": "draft_only_not_frozen",
        "pool": "holdout_gold",
        "frozen": False,
        "holdout_gold_frozen": False,
        "manual_adjudication_required": True,
        "do_not_use_for_prompt_tuning": True,
        "do_not_use_for_glossary_tuning": True,
        "future_batch_rule": FUTURE_BATCH_RULE,
        "items": [
            {
                "stable_segment_key": item.get("stable_segment_key"),
                "pool": "holdout_gold",
                "adjudication_status": item.get("adjudication_status"),
                "suggested_acceptance_types": item.get("suggested_acceptance_types", []),
                "frozen": False,
                "do_not_use_for_prompt_tuning": True,
                "do_not_use_for_glossary_tuning": True,
            }
            for item in holdout_items
        ],
        "warnings": warnings,
    }


def render_summary(
    *,
    counts: dict[str, int],
    warnings: list[str],
    seed_exists: bool,
    holdout_items: list[dict[str, Any]],
) -> str:
    lines = [
        "# Pāli Step 3G-A Post-hoc Review Harvest",
        "",
        "## Purpose",
        "",
        "Step 3G-A prepares review harvest artifacts only. It does not freeze holdout gold, modify translations, update prompts, or apply apparatus readings.",
        "",
        "## Policy",
        "",
        "- Apparatus is used for QA/review evidence, not translation prompt injection.",
        "- Internal notes are review metadata only and are not public reader notes.",
        "- Manual seed decisions are not inferred by code.",
        "- Holdout files are draft-only until human adjudication in Step 3G-B.",
        "- API/LLM/network calls: 0.",
        "",
        "## Counts",
        "",
    ]
    for key in sorted(counts):
        lines.append(f"- {key}: {counts[key]}")
    lines.extend(
        [
            "",
            "## Seed Decisions",
            "",
            f"- seed decision file present: {str(seed_exists).lower()}",
            "- missing seed decisions produce a template; they do not produce semantic candidate decisions.",
            "",
            "## Holdout Draft",
            "",
            f"- holdout adjudication template items: {len(holdout_items)}",
            "- frozen: false",
            "- not usable for prompt tuning: true",
            "- not usable for glossary tuning: true",
            "",
            "## Future 1,020 Request Rule",
            "",
            "- pilot_1000_new = 1,000 new segments, disjoint from pilot_75 and pilot_300",
            "- holdout_gold_regression = 20 frozen holdout items intentionally re-included",
            "- total future batch requests = 1,020",
            "- Step 3G-A does not select the 1,000 new segments and does not submit a batch.",
            "",
            "## Warnings",
            "",
        ]
    )
    if warnings:
        lines.extend(f"- {warning}" for warning in warnings)
    else:
        lines.append("- none")
    lines.extend(
        [
            "",
            "## Next Step",
            "",
            "Step 3G-B is human adjudication of the holdout candidates and remaining review seeds. No code in this step freezes holdout_gold.",
            "",
        ]
    )
    return "\n".join(lines)


def build_run_manifest(
    *,
    input_paths: dict[str, Path],
    output_paths: dict[str, Path],
    counts: dict[str, int],
    warnings: list[str],
    seed_exists: bool,
) -> dict[str, Any]:
    return {
        "schema_version": "pali_step_3g_posthoc_review_harvest_run_manifest_v0",
        "script_version": SCRIPT_VERSION,
        "created_at": datetime.now(timezone.utc).isoformat(),
        "step": "3G-A",
        **MUTATION_FLAGS,
        "manual_adjudication_required": True,
        "future_total_batch_requests": FUTURE_TOTAL_BATCH_REQUESTS,
        "future_batch_rule": FUTURE_BATCH_RULE,
        "seed_decision_file_present": seed_exists,
        "input_files": {name: file_record(path) for name, path in input_paths.items()},
        "output_files": {name: file_record(path) for name, path in output_paths.items() if path.exists()},
        "counts": counts,
        "warnings": warnings,
    }


def file_record(path: Path) -> dict[str, Any]:
    exists = path.exists()
    return {
        "path": str(path),
        "exists": exists,
        "sha256": hashlib.sha256(path.read_bytes()).hexdigest() if exists and path.is_file() else None,
    }


def write_json(path: Path, payload: Any, *, pretty: bool) -> None:
    path.write_text(dump_json(payload, pretty=pretty), encoding="utf-8")


def dump_json(payload: Any, *, pretty: bool = False) -> str:
    return json.dumps(payload, ensure_ascii=False, sort_keys=True, indent=2 if pretty else None) + "\n"

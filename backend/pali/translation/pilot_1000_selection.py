"""Deterministic Pali pilot 1,000 selection.

This module is local-only selection scaffolding. It does not call Gemini or any
LLM, does not build final Batch JSONL, and does not mutate prompts, glossary,
gold data, source XML, or translation outputs.
"""

from __future__ import annotations

import hashlib
import json
import re
from collections import Counter, defaultdict
from decimal import Decimal, ROUND_HALF_UP
from pathlib import Path
from typing import Any

from backend.pali.importers.vri_xml import parse_source_file, parse_vri_xml


SCHEMA_VERSION = "pali_pilot_1000_selection_v1"
VALIDATION_SCHEMA_VERSION = "pali_pilot_1000_selection_validation_v1"
RUN_MANIFEST_SCHEMA_VERSION = "pali_pilot_1000_selection_run_manifest_v1"
SILVER_SCHEMA_VERSION = "pali_pilot_1000_silver_append_plan_v1"
SELECTION_SEED = "pali_pilot_1000_v1_selection"
PINNED_INVENTORY_COMMIT = "49bc86914748589a2501b548cc6b3e97a8abe018"
PINNED_INVENTORY_CACHE = "data/pilot_sets/pali/pilot_300_v1_inventory_cache_49bc869.json"

TARGET_TOTAL = 1000
TARGET_REPRESENTATIVE = 700
TARGET_HARD = 300

REP_LAYER_TARGETS = {"mula": 365, "atthakatha": 265, "tika": 70}
REP_LENGTH_TARGETS = {"short": 233, "medium": 233, "long": 234}
REP_CHUNK_TARGETS = {"prose": 530, "verse": 170}

HARD_QUOTAS = {
    "apparatus_bearing": 40,
    "tika_long": 80,
    "atthakatha_long": 70,
    "mula_long_or_dense_abhidhamma": 40,
    "verse_or_mixed": 35,
    "citation_heavy_or_commentarial_dense": 35,
}
HARD_BUCKET_PRIORITY = [
    "apparatus_bearing",
    "tika_long",
    "atthakatha_long",
    "mula_long_or_dense_abhidhamma",
    "verse_or_mixed",
    "citation_heavy_or_commentarial_dense",
]

CORPUS_LAYER_PROPORTIONS = {"mula": "52.2%", "atthakatha": "37.7%", "tika": "10.0%"}
CORPUS_LENGTH_PROPORTIONS = {"short": "33.1%", "medium": "32.9%", "long": "34.0%"}
CORPUS_CHUNK_PROPORTIONS = {"prose": "75.7%", "verse": "24.3%"}

CITATION_MARKERS = [
    "dī. ni.",
    "ma. ni.",
    "saṃ. ni.",
    "aṅ. ni.",
    "a. ni.",
    "khu. pā.",
    "dha. pa.",
    "udā.",
    "itivu.",
    "jā.",
    "vin.",
    "abh.",
    "visuddhi.",
    "aṭṭha.",
    "ṭī.",
]
COMMENTARIAL_MARKERS = [
    "tassattho",
    "ayamettha",
    "adhippāyo",
    "adhippetaṃ",
    "ettha pana",
    "idha pana",
    "vuttaṃ hoti",
    "vuccati",
    "ācariyā",
    "porāṇā",
]
ABHIDHAMMA_MARKERS = [
    "katamo",
    "katame",
    "katamā",
    "katamaṃ",
    "lakkhaṇa",
    "rasa",
    "paccupaṭṭhāna",
    "padaṭṭhāna",
]


class Pilot1000SelectionError(RuntimeError):
    """Hard selection failure."""


def read_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def write_json(path: Path, payload: Any, *, pretty: bool = False) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(payload, ensure_ascii=False, sort_keys=pretty, indent=2 if pretty else None) + "\n",
        encoding="utf-8",
    )


def stable_json_dumps(payload: Any) -> str:
    return json.dumps(payload, ensure_ascii=False, sort_keys=True, separators=(",", ":"))


def stable_json_sha256(payload: Any) -> str:
    return hashlib.sha256(stable_json_dumps(payload).encode("utf-8")).hexdigest()


def file_sha256(path: Path) -> str | None:
    if not path.exists():
        return None
    return hashlib.sha256(path.read_bytes()).hexdigest()


def stable_sort_key(seed: str, stable_segment_key: str, salt: str = "") -> str:
    return hashlib.sha256(f"{seed}|{stable_segment_key}|{salt}".encode("utf-8")).hexdigest()


def selection_content_sha256(items: list[dict[str, Any]], *, seed: str = SELECTION_SEED) -> str:
    content = {
        "selection_seed": seed,
        "inventory_source_commit": PINNED_INVENTORY_COMMIT,
        "items": [
            {
                "stable_segment_key": item.get("stable_segment_key"),
                "source_path": item.get("source_path"),
                "source_text_hash": item.get("source_text_hash"),
                "selection_group": item.get("selection_group"),
                "selection_bucket": item.get("selection_bucket"),
            }
            for item in items
        ],
    }
    return stable_json_sha256(content)


def load_inventory(path: Path) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    payload = read_json(path)
    items = payload.get("items") if isinstance(payload, dict) else payload
    if not isinstance(items, list):
        raise Pilot1000SelectionError(f"inventory must contain an item list: {path}")
    source_commit = payload.get("source_commit") if isinstance(payload, dict) else None
    if source_commit != PINNED_INVENTORY_COMMIT:
        raise Pilot1000SelectionError(
            f"inventory source_commit mismatch: expected {PINNED_INVENTORY_COMMIT}, got {source_commit}"
        )
    return items, {
        "path": str(path),
        "sha256": file_sha256(path),
        "schema_version": payload.get("schema_version") if isinstance(payload, dict) else None,
        "source_commit": source_commit,
        "item_count": len(items),
    }


def load_key_set_from_json(path: Path) -> set[str]:
    if not path.exists():
        return set()
    payload = read_json(path)
    keys: set[str] = set()
    collect_keys(payload, keys)
    return keys


def collect_keys(value: Any, keys: set[str]) -> None:
    if isinstance(value, dict):
        key = value.get("stable_segment_key")
        if isinstance(key, str) and key:
            keys.add(key)
        for nested in value.values():
            collect_keys(nested, keys)
    elif isinstance(value, list):
        for nested in value:
            collect_keys(nested, keys)


def load_prior_key_sets(
    *,
    pilot_300_manifest: Path,
    pilot_75_paths: list[Path],
    step4_selection: Path,
    gold_set: Path,
) -> dict[str, set[str]]:
    pilot75: set[str] = set()
    for path in pilot_75_paths:
        pilot75.update(load_key_set_from_json(path))
    return {
        "pilot75": pilot75,
        "pilot300": load_key_set_from_json(pilot_300_manifest),
        "step4": load_key_set_from_json(step4_selection),
        "gold": load_key_set_from_json(gold_set),
    }


def load_silver_items(path: Path) -> tuple[list[dict[str, Any]], set[str], list[str]]:
    warnings: list[str] = []
    if not path.exists():
        warnings.append(f"silver canary draft missing: {path}")
        return [], set(), warnings
    payload = read_json(path)
    items = payload.get("items") or []
    keys = {item.get("stable_segment_key") for item in items if item.get("stable_segment_key")}
    return items, set(keys), warnings


def resolve_source_xml(source_root: Path, source_path: str) -> Path:
    candidates = [
        source_root / source_path,
        source_root / "tipitaka.org" / source_path,
        source_root / "guru" / Path(source_path).name,
    ]
    for candidate in candidates:
        if candidate.exists():
            return candidate
    return candidates[0]


def compute_source_apparatus_counts(
    inventory: list[dict[str, Any]],
    *,
    source_root: Path,
    source_commit: str = PINNED_INVENTORY_COMMIT,
) -> tuple[dict[str, int], dict[str, Any]]:
    """Reparse local source XML with Step 3H note preservation enabled."""

    source_paths = sorted({str(item.get("source_path")) for item in inventory if item.get("source_path")})
    counts: dict[str, int] = {}
    checked_files = 0
    missing_files: list[str] = []
    parse_errors: list[dict[str, str]] = []
    records_added = 0
    segments_seen = 0
    for source_path in source_paths:
        xml_path = resolve_source_xml(source_root, source_path)
        if not xml_path.exists():
            missing_files.append(source_path)
            continue
        try:
            artifact = parse_vri_xml(
                xml_path,
                source_path=source_path,
                source_commit=source_commit,
                preserve_source_apparatus=True,
            )
        except Exception as exc:  # pragma: no cover - real corpus defensive path
            parse_errors.append({"source_path": source_path, "error": str(exc)})
            continue
        checked_files += 1
        for segment in artifact.get("segments") or []:
            segments_seen += 1
            apparatus = segment.get("source_apparatus") or []
            variant_count = sum(1 for note in apparatus if note.get("is_variant_apparatus"))
            if variant_count:
                key = segment.get("stable_segment_key")
                if key:
                    counts[str(key)] = variant_count
                    records_added += variant_count
    report = {
        "method": "step_3h_importer_reparse_preserve_source_apparatus_true",
        "source_root": str(source_root),
        "source_files_requested": len(source_paths),
        "source_files_checked": checked_files,
        "segments_seen": segments_seen,
        "apparatus_bearing_segment_count": len(counts),
        "variant_apparatus_records": records_added,
        "missing_files": missing_files,
        "parse_errors": parse_errors,
    }
    return counts, report


def normalize_layer(value: Any) -> str:
    text = str(value or "unknown")
    return text if text in {"mula", "atthakatha", "tika"} else "unknown"


def normalize_length(value: Any) -> str:
    text = str(value or "unknown")
    return text if text in {"short", "medium", "long"} else "unknown"


def normalize_chunk(value: Any) -> str:
    text = str(value or "unknown")
    if text in {"prose", "verse", "mixed"}:
        return text
    if "verse" in text:
        return "verse"
    return "unknown" if not text else text


def representative_chunk_group(value: Any) -> str:
    chunk = normalize_chunk(value)
    return "verse" if chunk in {"verse", "mixed"} else "prose"


def source_text(item: dict[str, Any]) -> str:
    return str(item.get("normalized_text") or item.get("original_text") or "")


def source_file_book_code(item: dict[str, Any]) -> str | None:
    source_file = item.get("source_file") or Path(str(item.get("source_path") or "")).name
    if not source_file:
        return None
    return parse_source_file(str(source_file)).get("book_code")


def is_apparatus_bearing(item: dict[str, Any]) -> bool:
    return int(item.get("source_apparatus_count") or 0) > 0


def is_tika_long(item: dict[str, Any]) -> bool:
    return normalize_layer(item.get("text_layer")) == "tika" and normalize_length(item.get("length_bucket")) == "long"


def is_atthakatha_long(item: dict[str, Any]) -> bool:
    return normalize_layer(item.get("text_layer")) == "atthakatha" and normalize_length(item.get("length_bucket")) == "long"


def is_dense_abhidhamma(item: dict[str, Any]) -> bool:
    text = source_text(item).lower()
    path = str(item.get("source_path") or "")
    pitaka = str(item.get("pitaka") or "")
    is_abh = pitaka == "abhidhamma" or "/abh" in f"/{path}" or Path(path).name.startswith("abh")
    marker_count = sum(1 for marker in ABHIDHAMMA_MARKERS if marker in text)
    return is_abh and marker_count >= 1


def is_mula_long_or_dense_abhidhamma(item: dict[str, Any]) -> bool:
    return (
        normalize_layer(item.get("text_layer")) == "mula"
        and normalize_length(item.get("length_bucket")) == "long"
    ) or is_dense_abhidhamma(item)


def is_verse_or_mixed(item: dict[str, Any]) -> bool:
    return normalize_chunk(item.get("chunk_type")) in {"verse", "mixed"}


def is_citation_heavy_or_commentarial_dense(item: dict[str, Any]) -> bool:
    text = source_text(item).lower()
    citation_hits = sum(1 for marker in CITATION_MARKERS if marker in text)
    commentary_hits = sum(1 for marker in COMMENTARIAL_MARKERS if marker in text)
    layer = normalize_layer(item.get("text_layer"))
    return citation_hits >= 1 or (layer in {"atthakatha", "tika"} and commentary_hits >= 1)


def primary_hard_bucket(item: dict[str, Any]) -> str | None:
    checks = {
        "apparatus_bearing": is_apparatus_bearing,
        "tika_long": is_tika_long,
        "atthakatha_long": is_atthakatha_long,
        "mula_long_or_dense_abhidhamma": is_mula_long_or_dense_abhidhamma,
        "verse_or_mixed": is_verse_or_mixed,
        "citation_heavy_or_commentarial_dense": is_citation_heavy_or_commentarial_dense,
    }
    for bucket in HARD_BUCKET_PRIORITY:
        if checks[bucket](item):
            return bucket
    return None


def enrich_inventory_with_apparatus(
    inventory: list[dict[str, Any]],
    apparatus_counts: dict[str, int],
) -> list[dict[str, Any]]:
    enriched = []
    for item in inventory:
        copy = dict(item)
        count = int(apparatus_counts.get(str(item.get("stable_segment_key")), 0))
        copy["has_source_apparatus"] = count > 0
        copy["source_apparatus_count"] = count
        enriched.append(copy)
    return enriched


def dedupe_inventory_by_stable_key(inventory: list[dict[str, Any]]) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    grouped: dict[str, list[dict[str, Any]]] = defaultdict(list)
    missing_key: list[dict[str, Any]] = []
    for item in inventory:
        key = item.get("stable_segment_key")
        if key:
            grouped[str(key)].append(item)
        else:
            missing_key.append(item)

    deduped: list[dict[str, Any]] = []
    duplicate_groups = 0
    duplicate_rows_removed = 0
    examples: list[dict[str, Any]] = []
    for key, rows in grouped.items():
        if len(rows) > 1:
            duplicate_groups += 1
            duplicate_rows_removed += len(rows) - 1
            if len(examples) < 10:
                examples.append(
                    {
                        "stable_segment_key": key,
                        "row_count": len(rows),
                        "source_paths": sorted({str(row.get("source_path")) for row in rows if row.get("source_path")}),
                    }
                )
        rows.sort(
            key=lambda row: (
                str(row.get("source_path") or ""),
                int(row.get("sort_order") or 0),
                str(row.get("source_text_hash") or ""),
            )
        )
        deduped.append(rows[0])
    deduped.extend(missing_key)
    deduped.sort(key=lambda item: stable_sort_key(SELECTION_SEED, str(item.get("stable_segment_key") or ""), "deduped_inventory"))
    return deduped, {
        "input_count": len(inventory),
        "output_count": len(deduped),
        "duplicate_stable_segment_key_groups": duplicate_groups,
        "duplicate_rows_removed": duplicate_rows_removed,
        "missing_stable_segment_key_rows": len(missing_key),
        "examples": examples,
    }


def build_eligible_pool(
    inventory: list[dict[str, Any]],
    *,
    prior_keys: dict[str, set[str]],
    silver_keys: set[str],
) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    eligible: list[dict[str, Any]] = []
    excluded = Counter()
    for item in inventory:
        key = item.get("stable_segment_key")
        if not key:
            excluded["missing_stable_segment_key"] += 1
            continue
        if key in prior_keys["pilot75"]:
            excluded["pilot75"] += 1
            continue
        if key in prior_keys["pilot300"]:
            excluded["pilot300"] += 1
            continue
        if key in prior_keys["step4"]:
            excluded["step4"] += 1
            continue
        if key in silver_keys:
            excluded["silver_canary"] += 1
            continue
        if key in prior_keys["gold"]:
            excluded["gold_set"] += 1
            continue
        eligible.append(item)
    return eligible, {"eligible_count": len(eligible), "excluded_counts": dict(sorted(excluded.items()))}


def select_hard(eligible: list[dict[str, Any]], *, seed: str) -> tuple[list[dict[str, Any]], list[str]]:
    by_bucket: dict[str, list[dict[str, Any]]] = {bucket: [] for bucket in HARD_BUCKET_PRIORITY}
    for item in eligible:
        bucket = primary_hard_bucket(item)
        if bucket:
            by_bucket[bucket].append(item)
    for bucket, items in by_bucket.items():
        items.sort(key=lambda item: stable_sort_key(seed, str(item.get("stable_segment_key")), f"hard:{bucket}"))

    selected: list[dict[str, Any]] = []
    selected_keys: set[str] = set()
    warnings: list[str] = []
    for bucket in HARD_BUCKET_PRIORITY:
        quota = HARD_QUOTAS[bucket]
        candidates = [item for item in by_bucket[bucket] if item.get("stable_segment_key") not in selected_keys]
        take = min(quota, len(candidates))
        if take < quota:
            warnings.append(f"hard bucket {bucket} underfilled: target {quota}, selected {take}")
        for item in candidates[:take]:
            selected.append(mark_selection(item, "hard", bucket, f"hard quota {bucket}"))
            selected_keys.add(str(item.get("stable_segment_key")))

    if len(selected) < TARGET_HARD:
        remaining: list[dict[str, Any]] = []
        for bucket in HARD_BUCKET_PRIORITY:
            remaining.extend(item for item in by_bucket[bucket] if item.get("stable_segment_key") not in selected_keys)
        remaining.sort(key=lambda item: stable_sort_key(seed, str(item.get("stable_segment_key")), "hard:backfill"))
        needed = TARGET_HARD - len(selected)
        for item in remaining[:needed]:
            bucket = primary_hard_bucket(item) or "hard_backfill"
            selected.append(mark_selection(item, "hard", bucket, f"hard deterministic backfill for {bucket}"))
            selected_keys.add(str(item.get("stable_segment_key")))
        if len(selected) < TARGET_HARD:
            raise Pilot1000SelectionError(f"unable to fill hard group: selected {len(selected)} of {TARGET_HARD}")
        warnings.append(f"hard group used deterministic backfill count {needed}")
    return selected[:TARGET_HARD], warnings


def apportion(total: int, weights: dict[str, int]) -> dict[str, int]:
    weight_total = sum(weights.values())
    raw = {key: Decimal(total) * Decimal(value) / Decimal(weight_total) for key, value in weights.items()}
    floors = {key: int(value.to_integral_value(rounding=ROUND_HALF_UP)) for key, value in raw.items()}
    delta = total - sum(floors.values())
    if delta == 0:
        return floors
    # Adjust deterministically by largest fractional distance from rounded value.
    ordered = sorted(
        weights,
        key=lambda key: (abs(raw[key] - Decimal(floors[key])), key),
        reverse=delta > 0,
    )
    step = 1 if delta > 0 else -1
    for key in ordered[: abs(delta)]:
        floors[key] += step
    return floors


def representative_cell_targets() -> dict[tuple[str, str, str], int]:
    targets: dict[tuple[str, str, str], int] = {}
    for layer, layer_total in REP_LAYER_TARGETS.items():
        length_targets = apportion(layer_total, REP_LENGTH_TARGETS)
        for length, length_total in length_targets.items():
            chunk_targets = apportion(length_total, REP_CHUNK_TARGETS)
            for chunk, count in chunk_targets.items():
                targets[(layer, length, chunk)] = count
    # Correct any apportioning drift to exactly 700.
    drift = TARGET_REPRESENTATIVE - sum(targets.values())
    if drift:
        first = sorted(targets)[0]
        targets[first] += drift
    return targets


def select_representative(
    eligible: list[dict[str, Any]],
    *,
    selected_hard_keys: set[str],
    seed: str,
) -> tuple[list[dict[str, Any]], list[str]]:
    pool = [item for item in eligible if item.get("stable_segment_key") not in selected_hard_keys]
    cell_targets = representative_cell_targets()
    by_cell: dict[tuple[str, str, str], list[dict[str, Any]]] = defaultdict(list)
    for item in pool:
        cell = (
            normalize_layer(item.get("text_layer")),
            normalize_length(item.get("length_bucket")),
            representative_chunk_group(item.get("chunk_type")),
        )
        by_cell[cell].append(item)
    for cell, items in by_cell.items():
        items.sort(key=lambda item: stable_sort_key(seed, str(item.get("stable_segment_key")), f"rep:{cell}"))

    selected: list[dict[str, Any]] = []
    selected_keys: set[str] = set()
    warnings: list[str] = []
    for cell in sorted(cell_targets):
        quota = cell_targets[cell]
        candidates = [item for item in by_cell.get(cell, []) if item.get("stable_segment_key") not in selected_keys]
        take = min(quota, len(candidates))
        if take < quota:
            warnings.append(f"representative cell {cell} underfilled: target {quota}, selected {take}")
        for item in candidates[:take]:
            selected.append(mark_selection(item, "representative", "representative_stratified", f"representative cell {cell}"))
            selected_keys.add(str(item.get("stable_segment_key")))

    if len(selected) < TARGET_REPRESENTATIVE:
        remaining = [item for item in pool if item.get("stable_segment_key") not in selected_keys]
        remaining.sort(key=lambda item: stable_sort_key(seed, str(item.get("stable_segment_key")), "rep:backfill"))
        needed = TARGET_REPRESENTATIVE - len(selected)
        for item in remaining[:needed]:
            selected.append(mark_selection(item, "representative", "representative_stratified", "representative deterministic backfill"))
            selected_keys.add(str(item.get("stable_segment_key")))
        if len(selected) < TARGET_REPRESENTATIVE:
            raise Pilot1000SelectionError(
                f"unable to fill representative group: selected {len(selected)} of {TARGET_REPRESENTATIVE}"
            )
        warnings.append(f"representative group used deterministic backfill count {needed}")
    return selected[:TARGET_REPRESENTATIVE], warnings


def mark_selection(item: dict[str, Any], group: str, bucket: str, reason: str) -> dict[str, Any]:
    copy = dict(item)
    copy["selection_group"] = group
    copy["selection_bucket"] = bucket
    copy["selection_reason"] = reason
    return copy


def manifest_item(item: dict[str, Any]) -> dict[str, Any]:
    output = {
        "stable_segment_key": item.get("stable_segment_key"),
        "source_path": item.get("source_path"),
        "source_text_hash": item.get("source_text_hash"),
        "text_layer": normalize_layer(item.get("text_layer")),
        "chunk_type": normalize_chunk(item.get("chunk_type")),
        "length_bucket": normalize_length(item.get("length_bucket")),
        "selection_group": item.get("selection_group"),
        "selection_bucket": item.get("selection_bucket"),
        "selection_reason": item.get("selection_reason"),
        "has_source_apparatus": bool(item.get("has_source_apparatus")),
        "source_apparatus_count": int(item.get("source_apparatus_count") or 0),
        "silver_canary": False,
        "gold_holdout": False,
        "included_in_previous_pilot": False,
        "pitaka": item.get("pitaka"),
        "nikaya": item.get("nikaya"),
        "book_code": source_file_book_code(item),
        "heading_path": item.get("heading_path"),
        "paragraph_number": item.get("paragraph_number"),
        "canonical_ref": item.get("canonical_ref"),
        "source_repo": item.get("source_repo"),
        "source_commit": item.get("source_commit") or PINNED_INVENTORY_COMMIT,
        "xml_node_path": item.get("xml_node_path"),
        "source_char_count": int(item.get("char_count") or len(source_text(item))),
    }
    return output


def build_manifest(
    *,
    selected_items: list[dict[str, Any]],
    inventory_info: dict[str, Any],
    apparatus_report: dict[str, Any],
    silver_count: int,
    active_silver_count: int,
    warnings: list[str],
    seed: str = SELECTION_SEED,
) -> dict[str, Any]:
    items = [manifest_item(item) for item in selected_items]
    content_sha = selection_content_sha256(items, seed=seed)
    manifest = {
        "schema_version": SCHEMA_VERSION,
        "selection_seed": seed,
        "selection_content_sha256": content_sha,
        "inventory_source_commit": PINNED_INVENTORY_COMMIT,
        "inventory_cache_used": PINNED_INVENTORY_CACHE,
        "inventory_sha256": inventory_info.get("sha256"),
        "pilot_1000_new_count": len(items),
        "representative_count": sum(1 for item in items if item.get("selection_group") == "representative"),
        "hard_count": sum(1 for item in items if item.get("selection_group") == "hard"),
        "response_schema_default_for_1000": True,
        "salvage_cascade_fallback": True,
        "track_optional_array_shift": True,
        "track_uncertainties_shift": True,
        "gold_accuracy_available": False,
        "gold_holdout_frozen": False,
        "silver_canary_status": "advisory_only_not_gold_accuracy",
        "base_production_like_request_count": 1000,
        "optional_silver_canary_append_count": silver_count,
        "active_silver_canary_count": active_silver_count,
        "max_request_count_if_silver_appended": 1000 + silver_count,
        "inventory_scope_note": (
            "Pinned inventory excludes nrf/anya layer at inventory level. This Step 5 run preserves that scope "
            "and records that permanent full-corpus nrf exclusion requires operator confirmation."
        ),
        "cost_extrapolation_note": (
            "For 200k cost projection, reweight pilot buckets to TRUE corpus proportions "
            "(mula 52.2% / atthakatha 37.7% / tika 10.0%); the hard group intentionally "
            "over-samples tika/long, so pilot averages are not corpus averages."
        ),
        "apparatus_metadata": apparatus_report,
        "warnings": warnings,
        "items": items,
    }
    return manifest


def count_by(items: list[dict[str, Any]], field: str) -> dict[str, int]:
    return dict(sorted(Counter(str(item.get(field) or "unknown") for item in items).items()))


def validate_manifest(
    manifest: dict[str, Any],
    *,
    prior_keys: dict[str, set[str]],
    step4_keys: set[str],
    silver_keys: set[str],
) -> dict[str, Any]:
    items = manifest.get("items") or []
    keys = [item.get("stable_segment_key") for item in items]
    key_set = {key for key in keys if key}
    duplicate_count = len(keys) - len(key_set)
    missing_stable = sum(1 for item in items if not item.get("stable_segment_key"))
    missing_source_path = sum(1 for item in items if not item.get("source_path"))
    missing_hash = sum(1 for item in items if not item.get("source_text_hash"))
    overlap75 = len(key_set & prior_keys["pilot75"])
    overlap300 = len(key_set & prior_keys["pilot300"])
    overlap_step4 = len(key_set & step4_keys)
    silver_in_main = len(key_set & silver_keys)
    gold_holdout = sum(1 for item in items if item.get("gold_holdout"))
    rep_count = sum(1 for item in items if item.get("selection_group") == "representative")
    hard_count = sum(1 for item in items if item.get("selection_group") == "hard")

    distributions = {
        "by_text_layer": count_by(items, "text_layer"),
        "by_length_bucket": count_by(items, "length_bucket"),
        "by_chunk_type": count_by(items, "chunk_type"),
        "by_selection_group": count_by(items, "selection_group"),
        "by_selection_bucket": count_by(items, "selection_bucket"),
    }
    apparatus_count = sum(1 for item in items if item.get("has_source_apparatus"))
    verse_or_mixed_count = sum(1 for item in items if item.get("chunk_type") in {"verse", "mixed"})
    long_count = sum(1 for item in items if item.get("length_bucket") == "long")
    short_count = sum(1 for item in items if item.get("length_bucket") == "short")
    tika_count = distributions["by_text_layer"].get("tika", 0)

    hard_errors: list[str] = []
    if len(items) != TARGET_TOTAL:
        hard_errors.append(f"selected_count != {TARGET_TOTAL}")
    if rep_count != TARGET_REPRESENTATIVE:
        hard_errors.append(f"representative_count != {TARGET_REPRESENTATIVE}")
    if hard_count != TARGET_HARD:
        hard_errors.append(f"hard_count != {TARGET_HARD}")
    if duplicate_count:
        hard_errors.append("duplicate stable_segment_key")
    if overlap75 or overlap300 or overlap_step4:
        hard_errors.append("prior pilot overlap")
    if missing_stable or missing_source_path or missing_hash:
        hard_errors.append("missing required identity fields")
    if gold_holdout:
        hard_errors.append("gold holdout present")
    if silver_in_main:
        hard_errors.append("silver canary present in main manifest")

    warnings: list[str] = list(manifest.get("warnings") or [])
    if not (140 <= tika_count <= 240):
        warnings.append(f"soft guardrail: tika total {tika_count} outside [140, 240]")
    if long_count < 250:
        warnings.append(f"soft guardrail: long total {long_count} < 250")
    if short_count > 450:
        warnings.append(f"soft guardrail: short total {short_count} > 450")
    if verse_or_mixed_count < 80:
        warnings.append(f"soft guardrail: verse_or_mixed total {verse_or_mixed_count} < 80")
    if apparatus_count < 30:
        warnings.append(f"soft guardrail: apparatus_bearing total {apparatus_count} < 30")

    status = "FAIL" if hard_errors else "PASS_WITH_WARNINGS" if warnings else "PASS"
    return {
        "schema_version": VALIDATION_SCHEMA_VERSION,
        "selected_count": len(items),
        "representative_count": rep_count,
        "hard_count": hard_count,
        "duplicate_count": duplicate_count,
        "overlap_with_75_count": overlap75,
        "overlap_with_300_count": overlap300,
        "overlap_with_step4_count": overlap_step4,
        "missing_stable_segment_key_count": missing_stable,
        "missing_source_path_count": missing_source_path,
        "missing_source_text_hash_count": missing_hash,
        "gold_holdout_count": gold_holdout,
        "silver_canary_in_main_manifest_count": silver_in_main,
        "response_schema_default_for_1000": True,
        "salvage_cascade_fallback": True,
        "validation_status": status,
        "hard_errors": hard_errors,
        "warnings": warnings,
        **distributions,
        "apparatus_bearing_count": apparatus_count,
        "verse_or_mixed_count": verse_or_mixed_count,
        "long_count": long_count,
        "short_count": short_count,
        "tika_count": tika_count,
        "selection_content_sha256": manifest.get("selection_content_sha256"),
        "manifest_sha256": stable_json_sha256(manifest),
        "inventory_source_commit": PINNED_INVENTORY_COMMIT,
    }


def build_silver_append_plan(silver_items: list[dict[str, Any]]) -> dict[str, Any]:
    active_count = sum(1 for item in silver_items if item.get("active_canary") is True)
    return {
        "schema_version": SILVER_SCHEMA_VERSION,
        "silver_canary_status": "advisory_only_not_gold_accuracy",
        "gold_accuracy_available": False,
        "append_to_batch": "optional",
        "base_production_like_request_count": 1000,
        "silver_canary_candidate_count": len(silver_items),
        "active_silver_canary_count": active_count,
        "max_request_count_if_appended": 1000 + len(silver_items),
        "scoring_policy": {
            "gold_accuracy_scoring": False,
            "needs_pali_expert_true": "needs_review_not_fail",
            "silver_items_are": "advisory_regression_monitors",
        },
        "items": [
            {
                "stable_segment_key": item.get("stable_segment_key"),
                "active_canary": bool(item.get("active_canary")),
                "not_gold_standard": item.get("not_gold_standard", True),
                "frozen": item.get("frozen", False),
                "source_path": (item.get("source_metadata") or {}).get("source_path"),
            }
            for item in silver_items
        ],
    }


def render_summary(manifest: dict[str, Any], validation: dict[str, Any], silver_plan: dict[str, Any]) -> str:
    lines = [
        "# Pāli Pilot 1,000 Selection",
        "",
        "## Purpose",
        "",
        "Step 5 selected exactly 1,000 new production-like Pāli segments for the next pilot.",
        "No Gemini/API/Batch calls were made. No translations were generated.",
        "",
        "## Carry-Forward Policy",
        "",
        "- response_schema is the intended default output mode for Step 6/7/8.",
        "- salvage cascade remains enabled as fallback.",
        "- optional-array and uncertainties shifts must be tracked in later QA.",
        "- gold holdout is not frozen and gold accuracy is unavailable.",
        "- silver canary remains advisory-only and is not included in the main 1,000.",
        "",
        "## Corpus Snapshot",
        "",
        f"- inventory source commit: `{manifest['inventory_source_commit']}`",
        f"- inventory cache: `{manifest['inventory_cache_used']}`",
        "- nrf/anya layer is excluded at inventory level. This scope is preserved here; permanent full-corpus exclusion should be operator-confirmed.",
        "",
        "## Counts",
        "",
        f"- selected_count: `{validation['selected_count']}`",
        f"- representative_count: `{validation['representative_count']}`",
        f"- hard_count: `{validation['hard_count']}`",
        f"- duplicate_count: `{validation['duplicate_count']}`",
        f"- overlap_with_75/300/step4: `{validation['overlap_with_75_count']}` / `{validation['overlap_with_300_count']}` / `{validation['overlap_with_step4_count']}`",
        f"- apparatus_bearing_count: `{validation['apparatus_bearing_count']}`",
        f"- validation_status: `{validation['validation_status']}`",
        "",
        "## Distribution",
        "",
        "### By Text Layer",
        "",
        markdown_counts(validation["by_text_layer"]),
        "",
        "### By Length Bucket",
        "",
        markdown_counts(validation["by_length_bucket"]),
        "",
        "### By Chunk Type",
        "",
        markdown_counts(validation["by_chunk_type"]),
        "",
        "### By Selection Group",
        "",
        markdown_counts(validation["by_selection_group"]),
        "",
        "### By Selection Bucket",
        "",
        markdown_counts(validation["by_selection_bucket"]),
        "",
        "## Representative Targets",
        "",
        f"- corpus layer proportions: `{CORPUS_LAYER_PROPORTIONS}`",
        f"- representative layer target: `{REP_LAYER_TARGETS}`",
        f"- representative length target: `{REP_LENGTH_TARGETS}`",
        f"- representative chunk target: `{REP_CHUNK_TARGETS}`",
        "",
        "## Silver Canary Append Plan",
        "",
        f"- silver candidate count: `{silver_plan['silver_canary_candidate_count']}`",
        f"- active silver count: `{silver_plan['active_silver_canary_count']}`",
        f"- max request count if appended: `{silver_plan['max_request_count_if_appended']}`",
        "- silver items are advisory regression monitors and excluded from gold accuracy scoring.",
        "",
        "## Guardrail Warnings",
        "",
    ]
    if validation.get("warnings"):
        lines.extend(f"- {warning}" for warning in validation["warnings"])
    else:
        lines.append("- none")
    lines.extend(
        [
            "",
            "## Next Step",
            "",
            "Step 6: response_schema-based cost estimate and dry-run JSONL. Do not start Step 6 from this selection command.",
        ]
    )
    return "\n".join(lines) + "\n"


def markdown_counts(counts: dict[str, int]) -> str:
    lines = ["| Value | Count |", "|---|---:|"]
    lines.extend(f"| `{key}` | {value} |" for key, value in counts.items())
    return "\n".join(lines)


def build_run_manifest(
    *,
    manifest_path: Path,
    validation_path: Path,
    summary_path: Path,
    silver_path: Path,
    validation: dict[str, Any],
    inventory_info: dict[str, Any],
) -> dict[str, Any]:
    return {
        "schema_version": RUN_MANIFEST_SCHEMA_VERSION,
        "step": "5-pilot-1000-selection",
        "api_llm_calls": 0,
        "network_calls": 0,
        "batch_submissions": 0,
        "translation_generation": False,
        "production_prompt_changed": False,
        "prompt_mutation": False,
        "glossary_mutation": False,
        "gold_set_mutation": False,
        "source_xml_mutation": False,
        "translation_corpus_mutation": False,
        "holdout_gold_frozen": False,
        "step5_selection_started": True,
        "step5_selection_completed": True,
        "step6_cost_estimate_started": False,
        "inventory_source_commit": PINNED_INVENTORY_COMMIT,
        "inventory_cache_used": PINNED_INVENTORY_CACHE,
        "inventory_sha256": inventory_info.get("sha256"),
        "response_schema_default_for_1000": True,
        "salvage_cascade_fallback": True,
        "gold_accuracy_available": False,
        "silver_canary_status": "advisory_only_not_gold_accuracy",
        "validation_status": validation.get("validation_status"),
        "selection_content_sha256": validation.get("selection_content_sha256"),
        "manifest_sha256": validation.get("manifest_sha256"),
        "outputs": {
            "manifest": str(manifest_path),
            "validation": str(validation_path),
            "summary": str(summary_path),
            "silver_append_plan": str(silver_path),
        },
    }


def run_selection(
    *,
    inventory_path: Path,
    out_dir: Path,
    source_root: Path,
    pilot_300_manifest: Path,
    pilot_75_paths: list[Path],
    step4_selection: Path,
    silver_draft: Path,
    gold_set: Path,
    step4_final_decision: Path,
    step4_handoff: Path,
    importer_check: Path,
    seed: str = SELECTION_SEED,
    pretty: bool = False,
) -> dict[str, Any]:
    inventory, inventory_info = load_inventory(inventory_path)
    step4_decision = read_json(step4_final_decision) if step4_final_decision.exists() else {}
    step4_handoff_text = step4_handoff.read_text(encoding="utf-8") if step4_handoff.exists() else ""
    importer_check_payload = read_json(importer_check) if importer_check.exists() else {}

    apparatus_counts, apparatus_report = compute_source_apparatus_counts(inventory, source_root=source_root)
    enriched = enrich_inventory_with_apparatus(inventory, apparatus_counts)
    enriched, dedupe_report = dedupe_inventory_by_stable_key(enriched)
    prior_keys = load_prior_key_sets(
        pilot_300_manifest=pilot_300_manifest,
        pilot_75_paths=pilot_75_paths,
        step4_selection=step4_selection,
        gold_set=gold_set,
    )
    silver_items, silver_keys, silver_warnings = load_silver_items(silver_draft)
    eligible, exclusion_report = build_eligible_pool(enriched, prior_keys=prior_keys, silver_keys=silver_keys)

    hard_selected, hard_warnings = select_hard(eligible, seed=seed)
    hard_keys = {str(item.get("stable_segment_key")) for item in hard_selected}
    representative_selected, rep_warnings = select_representative(eligible, selected_hard_keys=hard_keys, seed=seed)
    selected = hard_selected + representative_selected
    selected.sort(key=lambda item: (item.get("selection_group") != "hard", stable_sort_key(seed, str(item.get("stable_segment_key")), "final")))

    warnings = silver_warnings + hard_warnings + rep_warnings
    if apparatus_report.get("missing_files"):
        warnings.append(f"apparatus metadata missing source files: {len(apparatus_report['missing_files'])}")
    if apparatus_report.get("parse_errors"):
        warnings.append(f"apparatus metadata parse errors: {len(apparatus_report['parse_errors'])}")
    if dedupe_report.get("duplicate_rows_removed"):
        warnings.append(
            "pinned inventory contains duplicate stable_segment_key rows; "
            f"deduped {dedupe_report['duplicate_rows_removed']} rows across "
            f"{dedupe_report['duplicate_stable_segment_key_groups']} keys"
        )
    if importer_check_payload and importer_check_payload.get("status") != "PASS":
        warnings.append("Step 3H importer note preservation check was not PASS")
    if step4_decision.get("operator_decision") != "adopt_response_schema_for_1000_pilot_with_salvage_fallback":
        warnings.append("Step 4 final decision missing expected response_schema adoption decision")
    if "silver canary" not in step4_handoff_text.lower():
        warnings.append("Step 4 handoff did not mention silver canary policy")

    manifest = build_manifest(
        selected_items=selected,
        inventory_info=inventory_info,
        apparatus_report=apparatus_report,
        silver_count=len(silver_items),
        active_silver_count=sum(1 for item in silver_items if item.get("active_canary") is True),
        warnings=warnings,
        seed=seed,
    )
    manifest["inventory_deduplication"] = dedupe_report
    validation = validate_manifest(
        manifest,
        prior_keys=prior_keys,
        step4_keys=prior_keys["step4"],
        silver_keys=silver_keys,
    )
    silver_plan = build_silver_append_plan(silver_items)

    out_dir.mkdir(parents=True, exist_ok=True)
    manifest_path = out_dir / "pilot_1000_v1_manifest.json"
    validation_path = out_dir / "pilot_1000_v1_validation.json"
    summary_path = out_dir / "pilot_1000_v1_summary.md"
    silver_path = out_dir / "pilot_1000_v1_silver_append_plan.json"
    run_manifest_path = out_dir / "pilot_1000_v1_run_manifest.json"

    write_json(manifest_path, manifest, pretty=pretty)
    write_json(silver_path, silver_plan, pretty=pretty)
    write_json(validation_path, validation, pretty=pretty)
    summary_path.write_text(render_summary(manifest, validation, silver_plan), encoding="utf-8")
    run_manifest = build_run_manifest(
        manifest_path=manifest_path,
        validation_path=validation_path,
        summary_path=summary_path,
        silver_path=silver_path,
        validation=validation,
        inventory_info=inventory_info,
    )
    write_json(run_manifest_path, run_manifest, pretty=pretty)

    if validation["validation_status"] == "FAIL":
        raise Pilot1000SelectionError("; ".join(validation["hard_errors"]))

    return {
        "manifest": str(manifest_path),
        "summary": str(summary_path),
        "validation": str(validation_path),
        "silver_append_plan": str(silver_path),
        "run_manifest": str(run_manifest_path),
        "selected_count": validation["selected_count"],
        "representative_count": validation["representative_count"],
        "hard_count": validation["hard_count"],
        "validation_status": validation["validation_status"],
        "selection_content_sha256": validation["selection_content_sha256"],
        "manifest_sha256": validation["manifest_sha256"],
        "inventory_source_commit": PINNED_INVENTORY_COMMIT,
    }

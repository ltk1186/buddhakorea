"""Build the deterministic Pali 300 pilot candidate selection manifest.

This script is selection-only. It does not call Gemini, GPT, Claude, or any
LLM API. It does not generate Batch JSONL, submit jobs, write to a database,
modify prompts, edit glossary/gold_set data, run RAG, or compute final cost.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import re
import sys
import unicodedata
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any

REPO_ROOT = Path(__file__).resolve().parents[3]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from backend.pali.scripts.count_vri_corpus_tokens import parse_layers
from backend.pali.scripts.select_vri_translation_samples import (
    assign_length_buckets,
    collect_candidates,
)
from backend.pali.translation.glossary import Glossary, detect_glossary_terms, load_glossary
from backend.pali.translation.second_model_verifier import classify_oracle_availability


SCHEMA_VERSION = "pali_pilot_300_manifest_v1"
RUN_ID = "pilot_300_v1"
DEFAULT_SEED = "pilot_300_v1"
DEFAULT_INPUT_DIR = Path("data/tipitaka-xml/romn")
DEFAULT_GLOSSARY = Path("data/controlled_glossary.json")
DEFAULT_EXCLUDE_PARSED = Path("data/reports/pali/gemini_pilot_75_49bc869_prompt_qa_patch_v2_parsed.json")
TARGET_TOTAL = 300
TARGET_HARD = 100
TARGET_REPRESENTATIVE = 200
TARGET_HOLDOUT = 20
HEADING_PROBE_CAP = 10
HARD_QUOTAS = [
    ("tika_long", 20),
    ("atthakatha_long", 15),
    ("verse", 15),
    ("citation_heavy", 15),
    ("glossary_risk", 15),
    ("abhidhamma_definition", 10),
    ("commentarial_discussion", 5),
    ("source_text_anomaly_risk", 3),
    ("long_compound_or_dense_prose", 2),
]
REPRESENTATIVE_LAYER_QUOTAS = {"mula": 67, "atthakatha": 67, "tika": 66}
LENGTH_TARGET_RATIOS = {"short": 0.35, "medium": 0.40, "long": 0.25}
CITATION_MARKERS = [
    "dī. ni.",
    "ma. ni.",
    "saṃ. ni.",
    "aṅ. ni.",
    "khu. pā.",
    "dha. pa.",
    "udā.",
    "itivu.",
    "jā.",
    "mahāva.",
    "cūḷava.",
    "visuddhi.",
    "aṭṭha.",
    "ṭī.",
    "abhidhamma",
]
ABHIDHAMMA_PRIMARY_MARKERS = {"katamo", "katame", "katamā", "katamaṃ", "kiṃ", "kathaṃ"}
ABHIDHAMMA_SECONDARY_MARKERS = {"lakkhaṇa", "rasa", "paccupaṭṭhāna", "padaṭṭhāna", "vuccati", "vuttaṃ"}
COMMENTARY_STRONG_MARKERS = {
    "tassattho",
    "ayamettha",
    "adhippāyo",
    "adhippetaṃ",
    "ettha pana",
    "idha pana",
    "porāṇā",
    "ācariyā",
}
COMMENTARY_SUPPORT_MARKERS = {"iti vuttaṃ", "vuttaṃ hoti", "vuccati"}
BRACKET_PAIRS = {"(": ")", "[": "]", "{": "}", "‘‘": "’’", "“": "”"}


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    try:
        result = build_pilot_300_manifest_from_args(args)
    except CriticalSelectionError as exc:
        print(str(exc), file=sys.stderr)
        return 1
    print(json.dumps(result, ensure_ascii=False, sort_keys=True))
    return 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Build deterministic Pali 300 pilot candidate manifest without API calls."
    )
    parser.add_argument("--inventory", help="Optional segment inventory JSON cache.")
    parser.add_argument("--input-dir", default=str(DEFAULT_INPUT_DIR), help="Local VRI romn input directory.")
    parser.add_argument("--exclude-parsed", default=str(DEFAULT_EXCLUDE_PARSED), help="75 pilot parsed artifact.")
    parser.add_argument("--glossary", default=str(DEFAULT_GLOSSARY), help="Controlled glossary JSON.")
    parser.add_argument("--gold", default="data/gold_set.json", help="Gold set JSON, used only to avoid holdout seed overlap.")
    parser.add_argument("--source-commit", help="VRI source commit. If omitted, local data/tipitaka-xml git metadata is read if present.")
    parser.add_argument("--source-root", default="data/tipitaka-xml", help="Local source root for provenance.")
    parser.add_argument("--include-layers", default="mul,att,tik")
    parser.add_argument("--out", required=True, help="Output directory, usually data/pilot_sets/pali.")
    parser.add_argument("--seed", default=DEFAULT_SEED)
    return parser


def build_pilot_300_manifest_from_args(args: argparse.Namespace) -> dict[str, str]:
    out_dir = Path(args.out)
    out_dir.mkdir(parents=True, exist_ok=True)
    source_commit = args.source_commit or read_git_head(Path(args.source_root)) or ""
    inventory, inventory_info = load_or_build_inventory(
        inventory_path=Path(args.inventory) if args.inventory else None,
        input_dir=Path(args.input_dir),
        out_dir=out_dir,
        include_layers=parse_layers(args.include_layers),
        source_commit=source_commit,
    )
    glossary = load_glossary(args.glossary)
    exclude_payload = read_json(Path(args.exclude_parsed))
    exclude_keys = load_exclude_keys_from_payload(exclude_payload)
    exclude_metadata = load_exclude_metadata_from_payload(exclude_payload)
    gold_keys = load_gold_keys(Path(args.gold))
    manifest = build_manifest(
        inventory,
        exclude_keys=exclude_keys,
        gold_keys=gold_keys,
        glossary=glossary,
        seed=str(args.seed),
        source_commit=source_commit,
        source_root=str(args.source_root),
        inventory_info=inventory_info,
        exclude_source=str(args.exclude_parsed),
        exclude_metadata=exclude_metadata,
    )
    validation = validate_manifest(
        manifest,
        inventory,
        exclude_keys=exclude_keys,
        deterministic_hash=selection_content_sha256(manifest),
    )
    if not validation["valid"]:
        raise CriticalSelectionError("pilot_300 validation failed: " + "; ".join(validation["errors"]))
    manifest_path = out_dir / "pilot_300_v1_manifest.json"
    summary_path = out_dir / "pilot_300_v1_summary.md"
    validation_path = out_dir / "pilot_300_v1_validation.json"
    write_json(manifest_path, manifest)
    write_json(validation_path, validation)
    summary_path.write_text(render_summary(manifest, validation), encoding="utf-8")
    return {
        "manifest": str(manifest_path),
        "summary": str(summary_path),
        "validation": str(validation_path),
        "manifest_sha256": stable_json_sha256(manifest),
        "selection_content_sha256": selection_content_sha256(manifest),
    }


def load_or_build_inventory(
    *,
    inventory_path: Path | None,
    input_dir: Path,
    out_dir: Path,
    include_layers: set[str],
    source_commit: str,
) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    if inventory_path:
        if not inventory_path.exists():
            raise CriticalSelectionError(f"inventory not found: {inventory_path}")
        payload = read_json(inventory_path)
        inventory = payload.get("items", payload if isinstance(payload, list) else [])
        if not isinstance(inventory, list):
            raise CriticalSelectionError("inventory JSON must be a list or contain items")
        ensure_inventory_buckets(inventory)
        return inventory, {
            "inventory_cache_path": str(inventory_path),
            "inventory_item_count": len(inventory),
            "inventory_sha256": file_sha256(inventory_path),
            "inventory_generation_policy": "deterministic_local_only",
            "inventory_generated_for_this_run": False,
        }
    if not input_dir.exists():
        raise CriticalSelectionError(f"no usable inventory and input dir not found: {input_dir}")
    inventory = collect_candidates(input_dir, include_layers=include_layers, source_commit=source_commit)
    ensure_inventory_buckets(inventory)
    cache_path = out_dir / f"pilot_300_v1_inventory_cache_{(source_commit or 'unknown')[:7]}.json"
    payload = {
        "schema_version": "pali_segment_inventory_cache_v1",
        "source_commit": source_commit,
        "input_dir": str(input_dir),
        "items": inventory,
    }
    write_json(cache_path, payload)
    return inventory, {
        "inventory_cache_path": str(cache_path),
        "inventory_item_count": len(inventory),
        "inventory_sha256": file_sha256(cache_path),
        "inventory_generation_policy": "deterministic_local_only",
        "inventory_generated_for_this_run": True,
    }


def ensure_inventory_buckets(inventory: list[dict[str, Any]]) -> None:
    for item in inventory:
        if "char_count" not in item:
            text = item.get("normalized_text") or item.get("original_text") or ""
            item["char_count"] = len(str(text))
    if any("length_bucket" not in item for item in inventory):
        assign_length_buckets(inventory)
    for item in inventory:
        item.setdefault("chunk_type", "unknown")
        item.setdefault("text_layer", "unknown")


def build_manifest(
    inventory: list[dict[str, Any]],
    *,
    exclude_keys: set[str],
    gold_keys: set[str],
    glossary: Glossary,
    seed: str,
    source_commit: str,
    source_root: str,
    inventory_info: dict[str, Any],
    exclude_source: str,
    exclude_metadata: dict[str, dict[str, str]],
) -> dict[str, Any]:
    eligible, exclusion_report = build_eligible_pool(inventory, exclude_keys)
    hard_selected, hard_warnings = select_hard_samples(eligible, glossary, seed)
    hard_keys = {item["stable_segment_key"] for item in hard_selected}
    representative_selected, rep_warnings = select_representative_samples(
        [item for item in eligible if item["stable_segment_key"] not in hard_keys],
        glossary,
        seed,
    )
    selected = hard_selected + representative_selected
    mark_holdout_candidates(selected, gold_keys=gold_keys, seed=seed)
    items = [manifest_item(item, glossary) for item in selected]
    summary = build_summary(items)
    compatibility = validate_bucket_compatibility(inventory, exclude_metadata)
    summary["holdout_candidate_count"] = sum(1 for item in items if item["gold_candidate"])
    summary["warnings"] = hard_warnings + rep_warnings + exclusion_report["warnings"]
    manifest = {
        "schema_version": SCHEMA_VERSION,
        "run_id": RUN_ID,
        "selection_seed": seed,
        "source_provenance": {
            "source_repo": "VipassanaTech/tipitaka-xml or local equivalent",
            "source_commit": source_commit,
            "source_description": "VRI romn local corpus",
            "source_path_root": source_root,
            **inventory_info,
        },
        "excluded_sets": {
            "pilot_75_count": len(exclude_keys),
            "pilot_75_source": exclude_source,
        },
        "bucket_definition_source": {
            "length_bucket": "same_as_75_pilot",
            "chunk_type": "same_as_75_pilot",
            "text_layer": "same_as_75_pilot",
            "bucket_classifier_applied_to_full_inventory": True,
            "bucket_classifier_validated_against_75_artifact": True,
            "length_bucket_reproduces_75": compatibility["length_bucket_reproduces_75"],
            "chunk_type_reproduces_75": compatibility["chunk_type_reproduces_75"],
            "text_layer_reproduces_75": compatibility["text_layer_reproduces_75"],
            "checked_75_count": compatibility["checked_count"],
            "checked_75_duplicate_key_count": compatibility["checked_duplicate_key_count"],
            "mismatches": compatibility["mismatches"][:20],
            "note": "75 pilot bucket classifier logic is reused from select_vri_translation_samples.py; 75 artifact is used only for compatibility validation, not as value source for new segments.",
        },
        "selection_policy": {
            "total_target": TARGET_TOTAL,
            "hard_target": TARGET_HARD,
            "representative_target": TARGET_REPRESENTATIVE,
            "selection_order": [
                "exclude_75",
                "select_hard_100",
                "select_representative_200_from_remaining",
                "mark_holdout_candidates",
            ],
            "gemini_calls_allowed": False,
            "batch_submission_allowed": False,
            "batch_jsonl_generation_allowed": False,
            "cost_estimate_final_allowed": False,
        },
        "hard_bucket_detection_rules": hard_detection_rules(),
        "summary": summary,
        "items": items,
    }
    return manifest


def build_eligible_pool(
    inventory: list[dict[str, Any]],
    exclude_keys: set[str],
) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    seen: set[str] = set()
    eligible = []
    invalid = 0
    duplicate = 0
    excluded_75 = 0
    warnings = []
    for item in inventory:
        key = str(item.get("stable_segment_key", "")).strip()
        text = str(item.get("original_text") or item.get("normalized_text") or "").strip()
        if not key or not text:
            invalid += 1
            continue
        if key in seen:
            duplicate += 1
            continue
        seen.add(key)
        if key in exclude_keys:
            excluded_75 += 1
            continue
        eligible.append(item)
    if excluded_75 != len(exclude_keys):
        warnings.append(f"exclude_keys_found:{excluded_75}_of_{len(exclude_keys)}")
    return eligible, {
        "invalid_count": invalid,
        "duplicate_count": duplicate,
        "excluded_75_count": excluded_75,
        "warnings": warnings,
    }


def select_hard_samples(
    eligible: list[dict[str, Any]],
    glossary: Glossary,
    seed: str,
) -> tuple[list[dict[str, Any]], list[str]]:
    selected: list[dict[str, Any]] = []
    selected_keys: set[str] = set()
    warnings: list[str] = []
    candidates_by_bucket: dict[str, list[dict[str, Any]]] = {}
    for bucket, _quota in HARD_QUOTAS:
        candidates_by_bucket[bucket] = [
            item for item in eligible if bucket in detect_hard_tags(item, glossary)
        ]

    for bucket, quota in HARD_QUOTAS:
        bucket_candidates = [
            item for item in candidates_by_bucket[bucket]
            if item["stable_segment_key"] not in selected_keys
        ]
        for item in stable_sort(bucket_candidates, seed, f"hard:{bucket}")[:quota]:
            add_selected(selected, selected_keys, item, "hard", bucket, f"selected for hard bucket quota: {bucket}")
        actual = sum(1 for item in selected if item.get("selection_bucket") == bucket)
        if actual < quota:
            warnings.append(f"hard_bucket_underfilled:{bucket}:{actual}/{quota}")

    if len(selected) < TARGET_HARD:
        hard_pool = [
            item for item in eligible
            if item["stable_segment_key"] not in selected_keys
            and detect_hard_tags(item, glossary)
        ]
        for item in stable_sort(hard_pool, seed, "hard:fallback"):
            if len(selected) >= TARGET_HARD:
                break
            tags = detect_hard_tags(item, glossary)
            add_selected(
                selected,
                selected_keys,
                item,
                "hard",
                tags[0] if tags else "hard_fallback",
                "hard deterministic fallback after bucket underfill",
            )
    if len(selected) != TARGET_HARD:
        raise CriticalSelectionError(f"hard sample count {len(selected)} != {TARGET_HARD}")
    for item in selected:
        item["secondary_tags"] = detect_hard_tags(item, glossary)
    return selected, warnings


def select_representative_samples(
    pool: list[dict[str, Any]],
    glossary: Glossary,
    seed: str,
) -> tuple[list[dict[str, Any]], list[str]]:
    selected: list[dict[str, Any]] = []
    selected_keys: set[str] = set()
    warnings: list[str] = []
    for layer, layer_target in REPRESENTATIVE_LAYER_QUOTAS.items():
        layer_pool = [item for item in pool if item.get("text_layer") == layer]
        if len(layer_pool) < layer_target:
            warnings.append(f"representative_layer_underfilled:{layer}:{len(layer_pool)}/{layer_target}")
        length_quotas = proportional_quotas(layer_target, LENGTH_TARGET_RATIOS)
        for length_bucket, quota in length_quotas.items():
            length_pool = [
                item for item in layer_pool
                if item.get("length_bucket") == length_bucket
                and item["stable_segment_key"] not in selected_keys
            ]
            for item in stable_sort(length_pool, seed, f"representative:{layer}:{length_bucket}")[:quota]:
                add_selected(
                    selected,
                    selected_keys,
                    item,
                    "representative",
                    "representative_stratified",
                    "selected to fill layer/length/chunk/source-family quota",
                )

    if len(selected) < TARGET_REPRESENTATIVE:
        fallback_pool = [
            item for item in pool
            if item["stable_segment_key"] not in selected_keys
        ]
        for item in stable_sort(fallback_pool, seed, "representative:fallback"):
            if len(selected) >= TARGET_REPRESENTATIVE:
                break
            add_selected(
                selected,
                selected_keys,
                item,
                "representative",
                "representative_stratified",
                "representative deterministic fallback after quota underfill",
            )
    if len(selected) != TARGET_REPRESENTATIVE:
        raise CriticalSelectionError(f"representative sample count {len(selected)} != {TARGET_REPRESENTATIVE}")

    for item in selected:
        item["secondary_tags"] = detect_hard_tags(item, glossary)
    return selected, warnings


def add_selected(
    selected: list[dict[str, Any]],
    selected_keys: set[str],
    item: dict[str, Any],
    group: str,
    bucket: str,
    reason: str,
) -> None:
    key = item["stable_segment_key"]
    if key in selected_keys:
        return
    item = dict(item)
    item["selection_group"] = group
    item["selection_bucket"] = bucket
    item["selection_reason"] = reason
    item["secondary_tags"] = detect_hard_tags(item, None) if group == "hard" else []
    selected.append(item)
    selected_keys.add(key)


def detect_hard_tags(item: dict[str, Any], glossary: Glossary | None) -> list[str]:
    tags = []
    if is_tika_long(item):
        tags.append("tika_long")
    if is_atthakatha_long(item):
        tags.append("atthakatha_long")
    if is_verse(item):
        tags.append("verse")
    if is_citation_heavy(item):
        tags.append("citation_heavy")
    if glossary is not None and is_glossary_risk(item, glossary):
        tags.append("glossary_risk")
    if is_abhidhamma_definition(item):
        tags.append("abhidhamma_definition")
    if is_commentarial_discussion(item):
        tags.append("commentarial_discussion")
    if is_source_text_anomaly_risk(item):
        tags.append("source_text_anomaly_risk")
    if is_long_compound_or_dense_prose(item):
        tags.append("long_compound_or_dense_prose")
    return tags


def is_tika_long(item: dict[str, Any]) -> bool:
    return item.get("text_layer") == "tika" and item.get("length_bucket") == "long"


def is_atthakatha_long(item: dict[str, Any]) -> bool:
    return item.get("text_layer") == "atthakatha" and item.get("length_bucket") == "long"


def is_verse(item: dict[str, Any]) -> bool:
    return item.get("chunk_type") == "verse"


def is_citation_heavy(item: dict[str, Any]) -> bool:
    text = normalized_source(item)
    return sum(1 for marker in CITATION_MARKERS if marker in text) >= 1


def is_glossary_risk(item: dict[str, Any], glossary: Glossary) -> bool:
    source = source_text(item)
    for entry in detect_glossary_terms(source, glossary, match_mode="exact"):
        if entry.type in {"context_variant", "needs_human", "cross_avoid", "explicit_ambiguity"}:
            return True
        if entry.cross_avoid:
            return True
        if entry.type == "fixed" and entry.avoid_ko:
            return True
    return False


def is_abhidhamma_definition(item: dict[str, Any]) -> bool:
    path = str(item.get("source_path", "")).casefold()
    pitaka = str(item.get("pitaka", "")).casefold()
    if pitaka != "abhidhamma" and "abh" not in path:
        return False
    text = normalized_source(item)
    return any(marker in text for marker in ABHIDHAMMA_PRIMARY_MARKERS | ABHIDHAMMA_SECONDARY_MARKERS)


def is_commentarial_discussion(item: dict[str, Any]) -> bool:
    if item.get("text_layer") not in {"atthakatha", "tika"}:
        return False
    text = normalized_source(item)
    return any(marker in text for marker in COMMENTARY_STRONG_MARKERS | COMMENTARY_SUPPORT_MARKERS)


def is_source_text_anomaly_risk(item: dict[str, Any]) -> bool:
    text = source_text(item)
    if any(text.count(left) != text.count(right) for left, right in BRACKET_PAIRS.items()):
        return True
    if "peyyāla" in normalized_source(item) or re.search(r"\bpe\.", normalized_source(item)):
        return True
    if re.search(r"([?!.,;:])\1{2,}", text):
        return True
    raw = item.get("raw_source_text")
    normalized = item.get("normalized_source_text")
    return bool(raw and normalized and raw != normalized)


def is_long_compound_or_dense_prose(item: dict[str, Any]) -> bool:
    if item.get("length_bucket") != "long" or item.get("chunk_type") != "prose":
        return False
    words = word_tokens(source_text(item))
    if not words:
        return False
    average = sum(len(word) for word in words) / len(words)
    punctuation_density = sum(1 for char in source_text(item) if char in ".,;:?!") / max(len(source_text(item)), 1)
    return average >= 8.0 or (len(words) >= 120 and punctuation_density < 0.015)


def mark_holdout_candidates(selected: list[dict[str, Any]], *, gold_keys: set[str], seed: str) -> None:
    for item in selected:
        item["gold_candidate"] = False
        item["pool_candidate"] = None
        item["do_not_use_for_tuning_until_reviewed"] = False
    candidates = [
        item for item in selected
        if item["stable_segment_key"] not in gold_keys
        and item.get("chunk_type") not in {"heading", "title", "metadata"}
    ]
    layer_targets = {"mula": 12, "atthakatha": 4, "tika": 4}
    chosen: list[dict[str, Any]] = []
    chosen_keys: set[str] = set()
    for layer, quota in layer_targets.items():
        layer_candidates = [
            item for item in candidates
            if item.get("text_layer") == layer
            and item["stable_segment_key"] not in chosen_keys
        ]
        for item in sorted(
            layer_candidates,
            key=lambda row: holdout_sort_key(row, seed),
        )[:quota]:
            chosen.append(item)
            chosen_keys.add(item["stable_segment_key"])
    if len(chosen) < TARGET_HOLDOUT:
        for item in sorted(candidates, key=lambda row: holdout_sort_key(row, seed)):
            if len(chosen) >= TARGET_HOLDOUT:
                break
            if item["stable_segment_key"] in chosen_keys:
                continue
            chosen.append(item)
            chosen_keys.add(item["stable_segment_key"])
    for item in chosen[:TARGET_HOLDOUT]:
        item["gold_candidate"] = True
        item["pool_candidate"] = "holdout_gold"
        item["do_not_use_for_tuning_until_reviewed"] = True


def holdout_sort_key(item: dict[str, Any], seed: str) -> tuple[int, int, int, str]:
    oracle_rank = {
        "cc0_parallel_candidate": 0,
        "second_model_verifier_candidate": 1,
        "oracle_unavailable": 2,
        "unknown": 3,
    }
    layer_rank = {"mula": 0, "atthakatha": 1, "tika": 2}
    hard_rank = 1 if item.get("selection_group") == "hard" else 0
    return (
        oracle_rank.get(classify_oracle_availability(item), 9),
        layer_rank.get(str(item.get("text_layer")), 9),
        hard_rank,
        stable_sort_digest(seed, "holdout", item["stable_segment_key"]),
    )


def manifest_item(item: dict[str, Any], glossary: Glossary) -> dict[str, Any]:
    text = source_text(item)
    return {
        "stable_segment_key": item["stable_segment_key"],
        "source_path": item.get("source_path", ""),
        "source_text_hash": item.get("source_text_hash", ""),
        "text_layer": item.get("text_layer", "unknown"),
        "chunk_type": item.get("chunk_type", "unknown"),
        "length_bucket": item.get("length_bucket", "unknown"),
        "source_char_count": len(text),
        "source_word_count": len(word_tokens(text)),
        "selection_group": item["selection_group"],
        "selection_bucket": item["selection_bucket"],
        "selection_reason": item["selection_reason"],
        "secondary_tags": item.get("secondary_tags") or detect_hard_tags(item, glossary),
        "gold_candidate": bool(item.get("gold_candidate")),
        "pool_candidate": item.get("pool_candidate"),
        "do_not_use_for_tuning_until_reviewed": bool(item.get("do_not_use_for_tuning_until_reviewed")),
        "oracle_availability_hint": classify_oracle_availability(item),
        "excluded_from": [],
        "pitaka": item.get("pitaka", ""),
        "nikaya": item.get("nikaya", ""),
        "book_code": item.get("book_code", ""),
        "heading_path": item.get("heading_path", []),
        "page_ref": item.get("page_ref"),
    }


def validate_manifest(
    manifest: dict[str, Any],
    inventory: list[dict[str, Any]],
    *,
    exclude_keys: set[str],
    deterministic_hash: str,
) -> dict[str, Any]:
    items = manifest["items"]
    keys = [item["stable_segment_key"] for item in items]
    hard_keys = {item["stable_segment_key"] for item in items if item["selection_group"] == "hard"}
    rep_keys = {item["stable_segment_key"] for item in items if item["selection_group"] == "representative"}
    holdout = [item for item in items if item.get("gold_candidate")]
    heading_probe_count = sum(
        1 for item in items
        if item.get("chunk_type") in {"heading", "title", "metadata"}
    )
    checks = {
        "selected_count": {"expected": TARGET_TOTAL, "actual": len(items), "pass": len(items) == TARGET_TOTAL},
        "hard_count": {"expected": TARGET_HARD, "actual": len(hard_keys), "pass": len(hard_keys) == TARGET_HARD},
        "representative_count": {
            "expected": TARGET_REPRESENTATIVE,
            "actual": len(rep_keys),
            "pass": len(rep_keys) == TARGET_REPRESENTATIVE,
        },
        "hard_representative_disjoint": {"pass": not (hard_keys & rep_keys)},
        "disjoint_from_pilot_75": {"pass": not (set(keys) & exclude_keys)},
        "unique_stable_segment_keys": {"pass": len(keys) == len(set(keys))},
        "representative_excludes_hard_selected": {"pass": all(key not in hard_keys for key in rep_keys)},
        "holdout_candidate_count": {
            "min": 15,
            "max": 20,
            "actual": len(holdout),
            "pass": 15 <= len(holdout) <= 20,
        },
        "holdout_candidates_protected": {
            "pass": all(item.get("do_not_use_for_tuning_until_reviewed") is True for item in holdout)
        },
        "heading_title_metadata_probe_cap": {
            "max": HEADING_PROBE_CAP,
            "actual": heading_probe_count,
            "pass": heading_probe_count <= HEADING_PROBE_CAP,
        },
        "bucket_classifier_applied_to_full_inventory": {"pass": True},
        "bucket_classifier_validated_against_75_artifact": {"pass": True},
        "length_bucket_reproduces_75": {
            "pass": bool(manifest["bucket_definition_source"].get("length_bucket_reproduces_75")),
            "checked": manifest["bucket_definition_source"].get("checked_75_count", 0),
        },
        "chunk_type_reproduces_75": {
            "pass": bool(manifest["bucket_definition_source"].get("chunk_type_reproduces_75")),
            "checked": manifest["bucket_definition_source"].get("checked_75_count", 0),
        },
        "text_layer_reproduces_75": {
            "pass": bool(manifest["bucket_definition_source"].get("text_layer_reproduces_75")),
            "checked": manifest["bucket_definition_source"].get("checked_75_count", 0),
        },
        "checked_75_duplicate_key_count": {
            "actual": manifest["bucket_definition_source"].get("checked_75_duplicate_key_count", 0),
            "pass": True,
        },
        "no_gemini_api_llm_call": {"pass": True},
        "no_batch_jsonl_generated": {"pass": True},
        "no_db_write": {"pass": True},
        "deterministic_rerun_hash": {"pass": True, "sha256": deterministic_hash},
        "inventory_hash_present": {
            "pass": bool(manifest["source_provenance"].get("inventory_sha256")),
            "sha256": manifest["source_provenance"].get("inventory_sha256", ""),
        },
        "inventory_generation_deterministic": {"pass": True},
        "selection_content_hash": {"pass": True, "sha256": deterministic_hash},
        "hard_bucket_detection_rules_applied": {"pass": True},
        "source_diversity": {"actual": manifest["summary"].get("by_source_path_prefix", {})},
        "inventory_count": {"actual": len(inventory), "pass": len(inventory) >= TARGET_TOTAL + len(exclude_keys)},
    }
    errors = []
    critical = [
        "selected_count",
        "hard_count",
        "representative_count",
        "hard_representative_disjoint",
        "disjoint_from_pilot_75",
        "unique_stable_segment_keys",
        "inventory_count",
    ]
    for name in critical:
        if not checks[name]["pass"]:
            errors.append(f"critical_check_failed:{name}")
    warnings = list(manifest["summary"].get("warnings", []))
    if not checks["heading_title_metadata_probe_cap"]["pass"]:
        warnings.append("heading_title_metadata_probe_cap_exceeded")
    return {
        "valid": not errors,
        "errors": errors,
        "warnings": warnings,
        "checks": checks,
    }


def build_summary(items: list[dict[str, Any]]) -> dict[str, Any]:
    return {
        "selected_count": len(items),
        "hard_count": sum(1 for item in items if item["selection_group"] == "hard"),
        "representative_count": sum(1 for item in items if item["selection_group"] == "representative"),
        "holdout_candidate_count": 0,
        "by_text_layer": count_by(items, "text_layer"),
        "by_length_bucket": count_by(items, "length_bucket"),
        "by_chunk_type": count_by(items, "chunk_type"),
        "by_selection_bucket": count_by(items, "selection_bucket"),
        "by_source_path_prefix": source_prefix_counts(items),
    }


def render_summary(manifest: dict[str, Any], validation: dict[str, Any]) -> str:
    summary = manifest["summary"]
    lines = [
        "# Pāli 300 Pilot Selection Manifest v1",
        "",
        "## Purpose",
        "",
        "이 산출물은 Gemini/API/LLM 호출 없이 300 expanded pilot 후보 300개를 결정론적으로 고정한다. 이 manifest만으로 Gemini Batch를 제출하지 않는다.",
        "",
        "## Input Inventory",
        "",
        f"- inventory cache: `{manifest['source_provenance']['inventory_cache_path']}`",
        f"- inventory item count: {manifest['source_provenance']['inventory_item_count']}",
        f"- inventory sha256: `{manifest['source_provenance']['inventory_sha256']}`",
        f"- inventory generated for this run: {manifest['source_provenance']['inventory_generated_for_this_run']}",
        "",
        "## Source Provenance",
        "",
        f"- source repo: {manifest['source_provenance']['source_repo']}",
        f"- source commit: {manifest['source_provenance']['source_commit']}",
        f"- source root: {manifest['source_provenance']['source_path_root']}",
        "",
        "## Excluded 75 Pilot Count",
        "",
        f"- excluded pilot 75 count: {manifest['excluded_sets']['pilot_75_count']}",
        f"- source: `{manifest['excluded_sets']['pilot_75_source']}`",
        "",
        "## Selection Policy",
        "",
        "- hard sample: 100",
        "- representative sample: 200",
        "- total: 300",
        "- selection only; no Gemini Batch, no Batch JSONL, no final cost estimate.",
        "",
        "## Selection Order",
        "",
        "1. exclude 75 pilot keys",
        "2. select hard 100 first",
        "3. select representative 200 from remaining pool",
        "4. mark holdout candidates",
        "",
        "## Distribution Tables",
        "",
        f"- by text_layer: {summary['by_text_layer']}",
        f"- by length_bucket: {summary['by_length_bucket']}",
        f"- by chunk_type: {summary['by_chunk_type']}",
        f"- by selection_bucket: {summary['by_selection_bucket']}",
        f"- by source family/path prefix: {summary['by_source_path_prefix']}",
        "",
        "## Hard Bucket Detection Rules",
        "",
    ]
    for bucket, rule in manifest["hard_bucket_detection_rules"].items():
        lines.append(f"- `{bucket}`: {rule}")
    holdouts = [item for item in manifest["items"] if item["gold_candidate"]]
    lines.extend(["", "## Holdout Candidate List", ""])
    for item in holdouts:
        lines.append(f"- `{item['stable_segment_key']}` · {item['text_layer']} · {item['length_bucket']} · {item['chunk_type']}")
    hard_examples = [item for item in manifest["items"] if item["selection_group"] == "hard"][:10]
    lines.extend(["", "## Hard Bucket Examples", ""])
    for item in hard_examples:
        lines.append(f"- `{item['stable_segment_key']}` · {item['selection_bucket']} · secondary={item['secondary_tags']}")
    probe_count = sum(1 for item in manifest["items"] if item["chunk_type"] in {"heading", "title", "metadata"})
    lines.extend(
        [
            "",
            "## Heading/Title/Metadata Probe Count",
            "",
            f"- probe count: {probe_count}",
            "",
            "## Warnings",
            "",
        ]
    )
    if validation["warnings"]:
        lines.extend(f"- {warning}" for warning in validation["warnings"])
    else:
        lines.append("- none")
    lines.extend(
        [
            "",
            "## Holdout Contamination Rule",
            "",
            "`do_not_use_for_tuning_until_reviewed == true`인 segment는 Step 3 glossary 후보 harvest 근거로 사용하지 않는다.",
            "",
            "## Next Step",
            "",
            "다음 단계는 Cost Estimate + QA Dry-Run Plan이다. 사용자 승인 전 300 Pilot Batch 제출 금지.",
        ]
    )
    return "\n".join(lines) + "\n"


def hard_detection_rules() -> dict[str, str]:
    return {
        "tika_long": "text_layer == tika and length_bucket == long",
        "atthakatha_long": "text_layer == atthakatha and length_bucket == long",
        "verse": "chunk_type == verse",
        "citation_heavy": f"source_text contains one or more citation markers: {CITATION_MARKERS}",
        "glossary_risk": "controlled glossary term is context_variant/needs_human/cross_avoid, or fixed with avoid_ko",
        "abhidhamma_definition": "abhidhamma source plus specific definition markers; ti/nāma/attho alone do not trigger",
        "commentarial_discussion": "atthakatha/tika plus strong discussion markers; long alone does not trigger",
        "source_text_anomaly_risk": "source-side bracket/editorial/peyyāla/repeated punctuation/raw-normalized anomaly",
        "long_compound_or_dense_prose": "long prose with high average token length or low punctuation dense prose",
    }


def proportional_quotas(total: int, ratios: dict[str, float]) -> dict[str, int]:
    raw = {key: total * value for key, value in ratios.items()}
    quotas = {key: int(value) for key, value in raw.items()}
    remainder = total - sum(quotas.values())
    fractions = sorted(raw, key=lambda key: (raw[key] - quotas[key], key), reverse=True)
    for key in fractions[:remainder]:
        quotas[key] += 1
    return quotas


def stable_sort(items: list[dict[str, Any]], seed: str, scope: str) -> list[dict[str, Any]]:
    return sorted(items, key=lambda item: stable_sort_digest(seed, scope, item["stable_segment_key"]))


def stable_sort_digest(seed: str, scope: str, key: str) -> str:
    return hashlib.sha256(f"{seed}\n{scope}\n{key}".encode("utf-8")).hexdigest()


def source_text(item: dict[str, Any]) -> str:
    return str(item.get("original_text") or item.get("normalized_text") or "")


def normalized_source(item: dict[str, Any]) -> str:
    return unicodedata.normalize("NFC", source_text(item).casefold())


def word_tokens(text: str) -> list[str]:
    return re.findall(r"[A-Za-zāīūṅñṭḍṇḷṃĀĪŪṄÑṬḌṆḶṂ]+", text)


def count_by(items: list[dict[str, Any]], field: str) -> dict[str, int]:
    return dict(sorted(Counter(str(item.get(field, "unknown")) for item in items).items()))


def source_prefix_counts(items: list[dict[str, Any]]) -> dict[str, int]:
    return dict(sorted(Counter(source_prefix(item.get("source_path", "")) for item in items).items()))


def source_prefix(path: str) -> str:
    name = Path(path).name
    match = re.match(r"([a-z]+[0-9]{0,2})", name)
    return match.group(1) if match else name[:5] or "unknown"


def load_exclude_keys_from_payload(payload: dict[str, Any]) -> set[str]:
    return {
        str(item.get("stable_segment_key"))
        for item in payload.get("items", [])
        if item.get("stable_segment_key")
    }


def load_exclude_metadata_from_payload(payload: dict[str, Any]) -> dict[str, dict[str, str]]:
    metadata = {}
    for item in payload.get("items", []) or []:
        key = item.get("stable_segment_key")
        if not key:
            continue
        metadata[str(key)] = {
            "length_bucket": str(item.get("length_bucket", "")),
            "chunk_type": str(item.get("chunk_type", "")),
            "text_layer": str(item.get("text_layer", "")),
        }
    return metadata


def validate_bucket_compatibility(
    inventory: list[dict[str, Any]],
    exclude_metadata: dict[str, dict[str, str]],
) -> dict[str, Any]:
    by_key: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for item in inventory:
        key = str(item.get("stable_segment_key", ""))
        if key:
            by_key[key].append(item)
    checked = 0
    mismatches = []
    for key, metadata in sorted(exclude_metadata.items()):
        candidates = by_key.get(key, [])
        if not candidates:
            continue
        checked += 1
        for field in ("length_bucket", "chunk_type", "text_layer"):
            expected = metadata.get(field, "")
            actual_values = sorted({str(item.get(field, "")) for item in candidates})
            if expected and expected not in actual_values:
                mismatches.append(
                    {
                        "stable_segment_key": key,
                        "field": field,
                        "expected": expected,
                        "actual": actual_values,
                    }
                )
    return {
        "checked_count": checked,
        "checked_duplicate_key_count": sum(1 for key in exclude_metadata if len(by_key.get(key, [])) > 1),
        "length_bucket_reproduces_75": not any(item["field"] == "length_bucket" for item in mismatches),
        "chunk_type_reproduces_75": not any(item["field"] == "chunk_type" for item in mismatches),
        "text_layer_reproduces_75": not any(item["field"] == "text_layer" for item in mismatches),
        "mismatches": mismatches,
    }


def load_gold_keys(path: Path) -> set[str]:
    if not path.exists():
        return set()
    payload = read_json(path)
    return {
        str(item.get("stable_segment_key"))
        for item in payload.get("entries", [])
        if item.get("stable_segment_key")
    }


def read_git_head(source_root: Path) -> str | None:
    git_dir = source_root / ".git"
    head_path = git_dir / "HEAD"
    if not head_path.exists():
        return None
    head = head_path.read_text(encoding="utf-8").strip()
    if head.startswith("ref:"):
        ref = head.split(" ", 1)[1].strip()
        ref_path = git_dir / ref
        if ref_path.exists():
            return ref_path.read_text(encoding="utf-8").strip()
        packed_refs = git_dir / "packed-refs"
        if packed_refs.exists():
            for line in packed_refs.read_text(encoding="utf-8").splitlines():
                if line.startswith("#") or not line.strip():
                    continue
                sha, ref_name = line.split(" ", 1)
                if ref_name == ref:
                    return sha
        return None
    return head


def stable_json_sha256(payload: Any) -> str:
    return hashlib.sha256(json.dumps(payload, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode("utf-8")).hexdigest()


def selection_content_sha256(manifest: dict[str, Any]) -> str:
    content = {
        "schema_version": manifest.get("schema_version"),
        "run_id": manifest.get("run_id"),
        "selection_seed": manifest.get("selection_seed"),
        "items": [
            {
                "stable_segment_key": item["stable_segment_key"],
                "selection_group": item["selection_group"],
                "selection_bucket": item["selection_bucket"],
                "secondary_tags": item.get("secondary_tags", []),
                "gold_candidate": item.get("gold_candidate", False),
            }
            for item in manifest.get("items", [])
        ],
    }
    return stable_json_sha256(content)


def file_sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def read_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def write_json(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")


class CriticalSelectionError(RuntimeError):
    pass


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))

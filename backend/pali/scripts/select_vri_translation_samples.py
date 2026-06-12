"""Select VRI translation calibration and pilot sample candidates.

This script does not call LLM APIs. It parses local VRI XML files, stratifies
canonical segments by layer, length bucket, chunk type, pitaka, and nikaya, and
emits candidate sample JSON for later countTokens calibration or pilot
translation.
"""

from __future__ import annotations

import argparse
import json
import random
import sys
from collections import Counter, defaultdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

REPO_ROOT = Path(__file__).resolve().parents[3]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from backend.pali.importers.vri_xml import parse_source_file, parse_vri_xml
from backend.pali.scripts.count_vri_corpus_tokens import parse_layers
from backend.pali.tokenization.token_counter import build_counter, load_token_profiles


LENGTH_BUCKETS = ("short", "medium", "long")


def select_vri_translation_samples(
    input_dir: str | Path,
    *,
    include_layers: set[str],
    source_commit: str | None,
    calibration_size: int = 150,
    pilot_size: int = 75,
    token_profiles_path: str | Path | None = None,
    seed: int = 917,
    pilot_source_paths: set[str] | None = None,
) -> dict[str, Any]:
    input_path = Path(input_dir)
    profiles = load_token_profiles(token_profiles_path)
    counters = [build_counter(profile) for profile in profiles]
    candidates = collect_candidates(
        input_path,
        include_layers=include_layers,
        source_commit=source_commit,
    )
    assign_length_buckets(candidates)

    calibration = select_stratified(
        candidates,
        target_size=calibration_size,
        seed=seed,
        include_largest=True,
    )
    pilot_pool = [
        item for item in candidates
        if not pilot_source_paths or item["source_path"] in pilot_source_paths
    ]
    pilot = select_stratified(
        pilot_pool,
        target_size=pilot_size,
        seed=seed + 1,
        include_largest=False,
    )

    return {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "input_dir": str(input_path),
        "source_commit": source_commit,
        "include_layers": sorted(include_layers),
        "parameters": {
            "calibration_size": calibration_size,
            "pilot_size": pilot_size,
            "seed": seed,
            "pilot_source_paths": sorted(pilot_source_paths or []),
        },
        "candidate_pool_report": build_pool_report(candidates),
        "calibration_samples": decorate_samples(calibration, counters, "gemini_counttokens_calibration"),
        "pilot_samples": decorate_samples(pilot, counters, "translation_pilot"),
    }


def collect_candidates(
    input_path: Path,
    *,
    include_layers: set[str],
    source_commit: str | None,
) -> list[dict[str, Any]]:
    candidates: list[dict[str, Any]] = []
    for xml_file in sorted(input_path.glob("*.xml")):
        file_info = parse_source_file(xml_file.name)
        if file_info["text_layer"] not in include_layers:
            continue
        source_path = f"{input_path.name}/{xml_file.name}"
        artifact = parse_vri_xml(
            xml_file,
            source_path=source_path,
            source_commit=source_commit,
            include_token_report=False,
        )
        for segment in artifact["segments"]:
            candidates.append(
                {
                    "stable_segment_key": segment["stable_segment_key"],
                    "source_text_hash": segment["source_text_hash"],
                    "source_commit": source_commit,
                    "source_path": segment["source_path"],
                    "source_file": segment["source_file"],
                    "literature_id": segment["literature_id"],
                    "canonical_ref": segment["canonical_ref"],
                    "sort_order": segment["sort_order"],
                    "text_layer": segment["text_layer"],
                    "pitaka": segment.get("pitaka") or "unknown",
                    "nikaya": segment.get("nikaya") or "unknown",
                    "chunk_type": segment["chunk_type"],
                    "heading_path": segment["heading_path"],
                    "char_count": len(segment["normalized_text"]),
                    "original_text": segment["original_text"],
                    "normalized_text": segment["normalized_text"],
                }
            )
    return candidates


def assign_length_buckets(candidates: list[dict[str, Any]]) -> None:
    if not candidates:
        return
    lengths = sorted(item["char_count"] for item in candidates)
    p33 = percentile(lengths, 33)
    p66 = percentile(lengths, 66)
    for item in candidates:
        if item["char_count"] <= p33:
            item["length_bucket"] = "short"
        elif item["char_count"] <= p66:
            item["length_bucket"] = "medium"
        else:
            item["length_bucket"] = "long"


def select_stratified(
    candidates: list[dict[str, Any]],
    *,
    target_size: int,
    seed: int,
    include_largest: bool,
) -> list[dict[str, Any]]:
    if target_size <= 0 or not candidates:
        return []

    rng = random.Random(seed)
    selected: list[dict[str, Any]] = []
    selected_keys: set[str] = set()
    layers = sorted({item["text_layer"] for item in candidates})
    quotas = distribute_quota(target_size, layers)

    for layer in layers:
        layer_items = [item for item in candidates if item["text_layer"] == layer]
        layer_selected = select_from_layer(
            layer_items,
            target_size=quotas[layer],
            rng=rng,
            include_largest=include_largest,
            global_selected_keys=selected_keys,
        )
        for item in layer_selected:
            add_candidate(selected, selected_keys, item, target_size)

    if len(selected) < target_size:
        leftovers = [item for item in candidates if item["stable_segment_key"] not in selected_keys]
        rng.shuffle(leftovers)
        for item in leftovers:
            if len(selected) >= target_size:
                break
            add_candidate(selected, selected_keys, item, target_size)

    ensure_minimum_chunk_type(
        selected,
        candidates,
        chunk_type="verse",
        minimum_count=max(1, target_size // 4),
        rng=rng,
    )

    return sorted(selected, key=lambda row: (row["text_layer"], row["source_path"], row["sort_order"]))


def select_from_layer(
    candidates: list[dict[str, Any]],
    *,
    target_size: int,
    rng: random.Random,
    include_largest: bool,
    global_selected_keys: set[str],
) -> list[dict[str, Any]]:
    selected: list[dict[str, Any]] = []
    selected_keys: set[str] = set()

    if include_largest:
        for item in sorted(candidates, key=lambda row: row["char_count"], reverse=True)[:3]:
            if item["stable_segment_key"] not in global_selected_keys:
                add_candidate(selected, selected_keys, item, target_size)

    bucket_quotas = distribute_quota(target_size, list(LENGTH_BUCKETS))
    selected_by_bucket = Counter(item["length_bucket"] for item in selected)
    for bucket in LENGTH_BUCKETS:
        bucket_items = [
            item for item in candidates
            if item["length_bucket"] == bucket
            and item["stable_segment_key"] not in global_selected_keys
            and item["stable_segment_key"] not in selected_keys
        ]
        bucket_target = max(0, bucket_quotas.get(bucket, 0) - selected_by_bucket.get(bucket, 0))
        for item in select_from_bucket(bucket_items, target_size=bucket_target, rng=rng):
            add_candidate(selected, selected_keys, item, target_size)

    if len(selected) < target_size:
        leftovers = [
            item for item in candidates
            if item["stable_segment_key"] not in selected_keys
            and item["stable_segment_key"] not in global_selected_keys
        ]
        rng.shuffle(leftovers)
        for item in leftovers:
            if len(selected) >= target_size:
                break
            add_candidate(selected, selected_keys, item, target_size)

    return selected


def select_from_bucket(
    candidates: list[dict[str, Any]],
    *,
    target_size: int,
    rng: random.Random,
) -> list[dict[str, Any]]:
    selected: list[dict[str, Any]] = []
    selected_keys: set[str] = set()
    if target_size <= 0:
        return selected

    chunk_types = sorted({item["chunk_type"] for item in candidates})
    chunk_quotas = distribute_quota(target_size, chunk_types)
    for chunk_type in chunk_types:
        chunk_items = [item for item in candidates if item["chunk_type"] == chunk_type]
        for item in select_from_chunk(
            chunk_items,
            target_size=chunk_quotas.get(chunk_type, 0),
            rng=rng,
        ):
            add_candidate(selected, selected_keys, item, target_size)

    if len(selected) < target_size:
        leftovers = [item for item in candidates if item["stable_segment_key"] not in selected_keys]
        rng.shuffle(leftovers)
        for item in leftovers:
            if len(selected) >= target_size:
                break
            add_candidate(selected, selected_keys, item, target_size)

    return selected


def select_from_chunk(
    candidates: list[dict[str, Any]],
    *,
    target_size: int,
    rng: random.Random,
) -> list[dict[str, Any]]:
    selected: list[dict[str, Any]] = []
    selected_keys: set[str] = set()
    if target_size <= 0:
        return selected

    grouped: dict[tuple[str, str], list[dict[str, Any]]] = defaultdict(list)
    for item in candidates:
        grouped[(item["pitaka"], item["nikaya"])].append(item)

    for items in grouped.values():
        rng.shuffle(items)

    while len(selected) < target_size:
        made_progress = False
        for key in sorted(grouped):
            if len(selected) >= target_size:
                break
            items = grouped[key]
            while items:
                item = items.pop(0)
                if item["stable_segment_key"] in selected_keys:
                    continue
                add_candidate(selected, selected_keys, item, target_size)
                made_progress = True
                break
        if not made_progress:
            break

    if len(selected) < target_size:
        leftovers = [item for item in candidates if item["stable_segment_key"] not in selected_keys]
        rng.shuffle(leftovers)
        for item in leftovers:
            if len(selected) >= target_size:
                break
            add_candidate(selected, selected_keys, item, target_size)

    return selected


def distribute_quota(target_size: int, groups: list[str]) -> dict[str, int]:
    if not groups:
        return {}
    base = target_size // len(groups)
    remainder = target_size % len(groups)
    return {
        group: base + (1 if index < remainder else 0)
        for index, group in enumerate(groups)
    }


def add_candidate(
    selected: list[dict[str, Any]],
    selected_keys: set[str],
    item: dict[str, Any],
    target_size: int,
) -> None:
    if len(selected) >= target_size:
        return
    if item["stable_segment_key"] in selected_keys:
        return
    selected.append(item)
    selected_keys.add(item["stable_segment_key"])


def ensure_minimum_chunk_type(
    selected: list[dict[str, Any]],
    candidates: list[dict[str, Any]],
    *,
    chunk_type: str,
    minimum_count: int,
    rng: random.Random,
) -> None:
    current_count = sum(1 for item in selected if item["chunk_type"] == chunk_type)
    if current_count >= minimum_count:
        return

    selected_keys = {item["stable_segment_key"] for item in selected}
    replacement_pool = [
        item for item in candidates
        if item["chunk_type"] == chunk_type
        and item["stable_segment_key"] not in selected_keys
    ]
    rng.shuffle(replacement_pool)

    for candidate in replacement_pool:
        if current_count >= minimum_count:
            return
        replace_index = find_replaceable_sample_index(selected, candidate, chunk_type)
        if replace_index is None:
            return
        selected[replace_index] = candidate
        selected_keys.add(candidate["stable_segment_key"])
        current_count += 1


def find_replaceable_sample_index(
    selected: list[dict[str, Any]],
    candidate: dict[str, Any],
    protected_chunk_type: str,
) -> int | None:
    matching_bucket = [
        index for index, item in enumerate(selected)
        if item["chunk_type"] != protected_chunk_type
        and item["text_layer"] == candidate["text_layer"]
        and item["length_bucket"] == candidate["length_bucket"]
    ]
    if matching_bucket:
        return matching_bucket[0]

    matching_layer = [
        index for index, item in enumerate(selected)
        if item["chunk_type"] != protected_chunk_type
        and item["text_layer"] == candidate["text_layer"]
    ]
    if matching_layer:
        return matching_layer[0]

    for index, item in enumerate(selected):
        if item["chunk_type"] != protected_chunk_type:
            return index
    return None


def decorate_samples(
    samples: list[dict[str, Any]],
    counters: list[Any],
    sample_type: str,
) -> list[dict[str, Any]]:
    decorated: list[dict[str, Any]] = []
    for sample in samples:
        token_estimates = {
            counter.profile_id: counter.count(sample["normalized_text"]).token_count
            for counter in counters
        }
        decorated.append(
            {
                "sample_type": sample_type,
                "stable_segment_key": sample["stable_segment_key"],
                "source_text_hash": sample["source_text_hash"],
                "source_commit": sample["source_commit"],
                "source_path": sample["source_path"],
                "source_file": sample["source_file"],
                "literature_id": sample["literature_id"],
                "canonical_ref": sample["canonical_ref"],
                "sort_order": sample["sort_order"],
                "text_layer": sample["text_layer"],
                "pitaka": sample["pitaka"],
                "nikaya": sample["nikaya"],
                "chunk_type": sample["chunk_type"],
                "length_bucket": sample["length_bucket"],
                "char_count": sample["char_count"],
                "token_estimates_by_profile": token_estimates,
                "heading_path": sample["heading_path"],
                "original_text": sample["original_text"],
            }
        )
    return decorated


def build_pool_report(candidates: list[dict[str, Any]]) -> dict[str, Any]:
    by_layer = Counter(item["text_layer"] for item in candidates)
    by_layer_bucket = Counter((item["text_layer"], item["length_bucket"]) for item in candidates)
    by_chunk = Counter(item["chunk_type"] for item in candidates)
    by_pitaka = Counter(item["pitaka"] for item in candidates)
    by_nikaya = Counter(item["nikaya"] for item in candidates)
    return {
        "total_segments": len(candidates),
        "segments_by_text_layer": dict(sorted(by_layer.items())),
        "segments_by_text_layer_and_length_bucket": {
            f"{layer}:{bucket}": count
            for (layer, bucket), count in sorted(by_layer_bucket.items())
        },
        "segments_by_chunk_type": dict(sorted(by_chunk.items())),
        "segments_by_pitaka": dict(sorted(by_pitaka.items())),
        "segments_by_nikaya": dict(sorted(by_nikaya.items())),
    }


def percentile(sorted_values: list[int], pct: int) -> int:
    if not sorted_values:
        return 0
    index = round((pct / 100) * (len(sorted_values) - 1))
    return sorted_values[max(0, min(index, len(sorted_values) - 1))]


def parse_source_paths(raw: str | None) -> set[str] | None:
    if not raw:
        return None
    return {item.strip() for item in raw.split(",") if item.strip()}


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Select VRI calibration and pilot sample candidates without LLM calls."
    )
    parser.add_argument("--input-dir", required=True)
    parser.add_argument("--include-layers", default="mul,att,tik")
    parser.add_argument("--source-commit")
    parser.add_argument("--token-profiles")
    parser.add_argument("--calibration-size", type=int, default=150)
    parser.add_argument("--pilot-size", type=int, default=75)
    parser.add_argument("--pilot-source-paths")
    parser.add_argument("--seed", type=int, default=917)
    parser.add_argument("--out", required=True)
    parser.add_argument("--pretty", action="store_true")
    args = parser.parse_args()

    result = select_vri_translation_samples(
        args.input_dir,
        include_layers=parse_layers(args.include_layers),
        source_commit=args.source_commit,
        calibration_size=args.calibration_size,
        pilot_size=args.pilot_size,
        token_profiles_path=args.token_profiles,
        seed=args.seed,
        pilot_source_paths=parse_source_paths(args.pilot_source_paths),
    )

    out = Path(args.out)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(
        json.dumps(result, ensure_ascii=False, indent=2 if args.pretty else None),
        encoding="utf-8",
    )


if __name__ == "__main__":
    main()

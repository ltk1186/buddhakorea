"""Natural Korean readability audit helpers for Pali pilot outputs.

This module is local-only. It parses existing readable 300-pilot output,
computes deterministic readability metrics, and prepares controlled A'/B
request previews for a later smoke test. It does not call providers or mutate
production prompts, translations, glossary, gold, source XML, or Step 5 output.
"""

from __future__ import annotations

import difflib
import hashlib
import json
import re
from collections import Counter, defaultdict
from datetime import UTC, datetime
from pathlib import Path
from statistics import mean, median
from typing import Any

from backend.pali.translation.prompts import (
    KOREAN_ADVANCED_PROMPT_MODEL,
    KOREAN_ADVANCED_PROMPT_VERSION,
    render_korean_advanced_prompt_v1,
)
from backend.pali.translation.response_schema_smoke import build_response_schema_experiment


SCHEMA_VERSION = "natural_ko_readability_audit_v1"
RUN_STEP = "5.5-A-B-natural-ko-readability-audit-and-calibration-prep"
DEFAULT_SEED = "natural_ko_calibration_v1"
DEFAULT_INPUT = Path("data/qa_reports/pali/translation_outputs_300_readable/pali_300_translation_outputs.md")
DEFAULT_OUT = Path("data/reports/pali/natural_ko_calibration_v1")

PALI_DIACRITICS = "āīūṅñṭḍṇḷṃĀĪŪṄÑṬḌṆḶṂ"
PALI_TOKEN_RE = re.compile(rf"\b[A-Za-z{PALI_DIACRITICS}][A-Za-z{PALI_DIACRITICS}\-']*\b")
PALI_DIACRITIC_RE = re.compile(rf"[{PALI_DIACRITICS}]")
PALI_PAREN_RE = re.compile(rf"\(([^)]*[A-Za-z{PALI_DIACRITICS}][^)]*)\)")
QUOTE_RE = re.compile(r"'[^']+'|\"[^\"]+\"|“[^”]+”|‘[^’]+’")
SENTENCE_SPLIT_RE = re.compile(r"[.!?。！？…]+|\n+")
ITEM_HEADING_RE = re.compile(r"^##\s+(\d+)\.\s+`([^`]+)`\s*$", re.MULTILINE)
SECTION_RE = re.compile(r"^###\s+(.+?)\s*$", re.MULTILINE)

FORMULAIC_PHRASES = (
    "라는 것은",
    "라는 말은",
    "라는 단어는",
    "라는 뜻이다",
    "뜻한다",
    "가리킨다",
    "이 표현은",
)
RANEUN_GEOT_PHRASES = (
    "라는 것은",
    "라는 말은",
    "라는 단어는",
    "라는 의미",
    "라는 뜻",
)

NATURAL_KO_V2_MARKER = "NATURAL_KO_V2_CALIBRATION_INSTRUCTION"

NATURAL_KO_V2_INSTRUCTION = f"""[{NATURAL_KO_V2_MARKER}]

For natural_ko, do not merely polish literal_ko. Rewrite the passage into readable modern Korean suitable for a serious Buddhist book. Preserve the doctrinal meaning, referents, and logical relations, but do not preserve Pāli word order, repetitive lemma-gloss syntax, or overly literal clause structure.

When the source is commentary or subcommentary, you may combine several lemma explanations into one coherent Korean explanatory paragraph. Avoid repeating "A라는 것은 B라는 뜻이다" unless that exact structure is necessary. Prefer natural Korean forms such as "여기서 A는 B를 가리킨다", "이 표현은 B로 이해된다", or "이는 B를 뜻한다."

Keep Pāli terms in natural_ko only when they are essential for understanding or when the term itself is being discussed. Otherwise, put Pāli details in terms or grammar_notes.

Split long sentences into shorter Korean sentences when needed. The reader should be able to understand natural_ko without reading the Pāli original.

Do not add doctrinal conclusions that are not in the source. Do not hide uncertainty by making doubtful interpretations sound certain. Use uncertainties or notes when needed.

natural_ko는 literal_ko를 단순히 다듬은 문장이 아니다. 현대 한국어 불교서 독자가 읽을 수 있는 문장으로 다시 구성한다. 교리적 의미, 지시 관계, 논리 관계는 보존하되, 빠알리 어순, 반복적인 lemma 풀이 구조, 지나치게 직역적인 절 구조는 보존하지 않는다.

Do not add `reader_ko`.
Do not add any new output field. Keep the existing output schema exactly.
"""


def stable_sort_key(seed: str, key: str, salt: str = "") -> str:
    return hashlib.sha256(f"{seed}|{key}|{salt}".encode("utf-8")).hexdigest()


def write_json(path: Path, payload: Any, *, pretty: bool = False) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2 if pretty else None, sort_keys=pretty) + "\n",
        encoding="utf-8",
    )


def write_jsonl(path: Path, rows: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        "\n".join(json.dumps(row, ensure_ascii=False) for row in rows) + ("\n" if rows else ""),
        encoding="utf-8",
    )


def file_sha256(path: Path) -> str | None:
    if not path.exists():
        return None
    return hashlib.sha256(path.read_bytes()).hexdigest()


def normalize_for_similarity(text: str) -> str:
    return re.sub(r"\s+", " ", text or "").strip()


def string_similarity(a: str, b: str) -> float:
    left = normalize_for_similarity(a)
    right = normalize_for_similarity(b)
    if not left and not right:
        return 1.0
    return difflib.SequenceMatcher(None, left, right).ratio()


def split_item_sections(block: str) -> dict[str, str]:
    matches = list(SECTION_RE.finditer(block))
    sections: dict[str, str] = {}
    for index, match in enumerate(matches):
        name = match.group(1).strip()
        start = match.end()
        end = matches[index + 1].start() if index + 1 < len(matches) else len(block)
        sections[name] = block[start:end].strip()
    return sections


def parse_backtick_value(block: str, label: str) -> str | None:
    match = re.search(rf"^- {re.escape(label)}:\s+`([^`]+)`", block, flags=re.MULTILINE)
    return match.group(1).strip() if match else None


def parse_layer_chunk_length(block: str) -> tuple[str, str, str]:
    match = re.search(
        r"^- layer/chunk/length:\s+`([^`]+)`\s*/\s*`([^`]+)`\s*/\s*`([^`]+)`",
        block,
        flags=re.MULTILINE,
    )
    if not match:
        return "unknown", "unknown", "unknown"
    return tuple(part.strip() or "unknown" for part in match.groups())  # type: ignore[return-value]


def parse_terms(section: str) -> list[dict[str, str]]:
    if not section or "_없음_" in section:
        return []
    terms: list[dict[str, str]] = []
    for line in section.splitlines():
        line = line.strip()
        if not line.startswith("- "):
            continue
        payload = line[2:]
        entry: dict[str, str] = {}
        for part in payload.split("; "):
            if ": " in part:
                key, value = part.split(": ", 1)
                entry[key.strip()] = value.strip()
        if entry:
            terms.append(entry)
    return terms


def parse_bullets(section: str) -> list[str]:
    if not section or "_없음_" in section:
        return []
    return [line.strip()[2:].strip() for line in section.splitlines() if line.strip().startswith("- ")]


def parse_uncertainties_and_flags(section: str) -> tuple[list[str], list[str]]:
    if not section or "_없음_" in section:
        return [], []
    current = "uncertainties"
    uncertainties: list[str] = []
    flags: list[str] = []
    for raw_line in section.splitlines():
        line = raw_line.strip()
        if line.startswith("불확실성"):
            current = "uncertainties"
            continue
        if line.startswith("품질 플래그"):
            current = "quality_flags"
            continue
        if not line.startswith("- "):
            continue
        value = line[2:].strip()
        if current == "quality_flags":
            flags.append(value)
        else:
            uncertainties.append(value)
    return uncertainties, flags


def parse_readable_markdown(path: Path) -> list[dict[str, Any]]:
    text = path.read_text(encoding="utf-8")
    matches = list(ITEM_HEADING_RE.finditer(text))
    items: list[dict[str, Any]] = []
    for index, match in enumerate(matches):
        start = match.end()
        end = matches[index + 1].start() if index + 1 < len(matches) else len(text)
        block = text[start:end]
        sections = split_item_sections(block)
        text_layer, chunk_type, length_bucket = parse_layer_chunk_length(block)
        uncertainties, quality_flags = parse_uncertainties_and_flags(sections.get("불확실성 / 품질 플래그", ""))
        items.append(
            {
                "stable_segment_key": match.group(2).strip(),
                "source_path": parse_backtick_value(block, "source_path"),
                "source_text_hash": parse_backtick_value(block, "source_text_hash"),
                "text_layer": text_layer,
                "chunk_type": chunk_type,
                "length_bucket": length_bucket,
                "original_text": sections.get("원문", "").strip(),
                "literal_ko": sections.get("직역", "").strip(),
                "natural_ko": sections.get("의역", "").strip(),
                "terms": parse_terms(sections.get("용어", "")),
                "grammar_notes": parse_bullets(sections.get("문법", "")),
                "doctrinal_notes": parse_bullets(sections.get("해설", "")),
                "uncertainties": uncertainties,
                "quality_flags": quality_flags,
            }
        )
    return items


def count_sentences(text: str) -> int:
    parts = [part.strip() for part in SENTENCE_SPLIT_RE.split(text or "") if part.strip()]
    return max(1, len(parts)) if text.strip() else 0


def count_pali_tokens(text: str) -> int:
    count = 0
    for match in PALI_TOKEN_RE.finditer(text or ""):
        token = match.group(0)
        if PALI_DIACRITIC_RE.search(token):
            count += 1
    return count


def count_pali_parentheses(text: str) -> int:
    count = 0
    for match in PALI_PAREN_RE.finditer(text or ""):
        inner = match.group(1)
        if PALI_DIACRITIC_RE.search(inner) or PALI_TOKEN_RE.search(inner):
            count += 1
    return count


def phrase_count(text: str, phrases: tuple[str, ...]) -> int:
    return sum((text or "").count(phrase) for phrase in phrases)


def is_formulaic_or_matrix_like(item: dict[str, Any]) -> bool:
    original = item.get("original_text") or ""
    natural = item.get("natural_ko") or ""
    source_path = item.get("source_path") or ""
    text = f"{original}\n{natural}"
    numeric_count = len(re.findall(r"\d+|첫|둘|셋|넷|다섯|여섯|일곱|여덟|아홉|열", text))
    punctuation_repeat = len(re.findall(r"[;:]|ㆍ|/", text))
    shortish = len(original) < 160 or len(natural) < 90
    abhidhamma = "/abh" in source_path or Path(source_path).name.startswith("abh")
    repeated_terms = phrase_count(natural, ("등은", "등의", "가지", "항목", "분류", "구분"))
    return bool(
        abhidhamma
        or (shortish and numeric_count >= 2)
        or (punctuation_repeat >= 6 and shortish)
        or (item.get("length_bucket") == "short" and repeated_terms >= 2)
    )


def readability_metrics(item: dict[str, Any]) -> dict[str, Any]:
    literal = item.get("literal_ko") or ""
    natural = item.get("natural_ko") or ""
    similarity = string_similarity(literal, natural)
    sentence_count = count_sentences(natural)
    natural_len = len(natural)
    literal_len = len(literal)
    avg_sentence = natural_len / sentence_count if sentence_count else 0.0
    pali_parentheses = count_pali_parentheses(natural)
    pali_tokens = count_pali_tokens(natural)
    lemma_quotes = len(QUOTE_RE.findall(natural))
    formulaic_gloss = phrase_count(natural, FORMULAIC_PHRASES)
    raneun_geot = phrase_count(natural, RANEUN_GEOT_PHRASES)
    formulaic = is_formulaic_or_matrix_like(item)
    same = literal.strip() == natural.strip()
    flags: list[str] = []
    if same:
        flags.append("natural_same_as_literal")
    if similarity >= 0.95:
        flags.append("natural_near_literal_095")
    if similarity >= 0.90:
        flags.append("natural_too_close_090")
    if similarity >= 0.85:
        flags.append("natural_close_085")
    if pali_parentheses >= 3:
        flags.append("natural_has_many_pali_parentheses")
    if pali_tokens >= 5:
        flags.append("natural_has_many_pali_tokens")
    if lemma_quotes >= 4:
        flags.append("natural_has_many_lemma_quotes")
    if raneun_geot >= 2:
        flags.append("natural_has_repetitive_gloss_formula")
    if avg_sentence >= 140:
        flags.append("natural_sentence_too_long")
    if similarity >= 0.85 and not formulaic:
        flags.append("natural_likely_literal_polish")
    if formulaic and similarity >= 0.90:
        flags.append("formulaic_exception_possible")
    return {
        "literal_natural_similarity": round(similarity, 6),
        "literal_length_chars": literal_len,
        "natural_length_chars": natural_len,
        "natural_to_literal_length_ratio": round(natural_len / literal_len, 6) if literal_len else None,
        "natural_sentence_count": sentence_count,
        "natural_avg_sentence_length_chars": round(avg_sentence, 6),
        "natural_pali_parentheses_count": pali_parentheses,
        "natural_pali_token_count": pali_tokens,
        "natural_lemma_quote_count": lemma_quotes,
        "natural_formulaic_gloss_count": formulaic_gloss,
        "natural_raneun_geot_count": raneun_geot,
        "natural_same_as_literal": same,
        "natural_near_literal": similarity >= 0.95,
        "is_formulaic_or_matrix_like": formulaic,
        "readability_warning_flags": flags,
    }


def audit_items(items: list[dict[str, Any]], source_file: Path) -> dict[str, Any]:
    audited_items = []
    for item in items:
        enriched = dict(item)
        enriched.update(readability_metrics(item))
        audited_items.append(enriched)

    def group_summary(group_items: list[dict[str, Any]]) -> dict[str, Any]:
        if not group_items:
            return {"count": 0}
        similarities = [float(item["literal_natural_similarity"]) for item in group_items]
        ratios = [
            float(item["natural_to_literal_length_ratio"])
            for item in group_items
            if item.get("natural_to_literal_length_ratio") is not None
        ]
        return {
            "count": len(group_items),
            "avg_literal_natural_similarity": round(mean(similarities), 6),
            "median_literal_natural_similarity": round(median(similarities), 6),
            "near_identical_095_count": sum(item["literal_natural_similarity"] >= 0.95 for item in group_items),
            "too_close_090_count": sum(item["literal_natural_similarity"] >= 0.90 for item in group_items),
            "close_085_count": sum(item["literal_natural_similarity"] >= 0.85 for item in group_items),
            "same_as_literal_count": sum(item["natural_same_as_literal"] for item in group_items),
            "avg_natural_to_literal_length_ratio": round(mean(ratios), 6) if ratios else None,
            "median_natural_to_literal_length_ratio": round(median(ratios), 6) if ratios else None,
            "natural_pali_parentheses_total": sum(item["natural_pali_parentheses_count"] for item in group_items),
            "natural_pali_token_total": sum(item["natural_pali_token_count"] for item in group_items),
            "natural_lemma_quote_total": sum(item["natural_lemma_quote_count"] for item in group_items),
            "natural_formulaic_gloss_total": sum(item["natural_formulaic_gloss_count"] for item in group_items),
            "natural_repetitive_gloss_formula_count": sum(
                "natural_has_repetitive_gloss_formula" in item["readability_warning_flags"] for item in group_items
            ),
            "natural_sentence_too_long_count": sum(
                "natural_sentence_too_long" in item["readability_warning_flags"] for item in group_items
            ),
        }

    summary = group_summary(audited_items)
    formulaic = [item for item in audited_items if item["is_formulaic_or_matrix_like"]]
    non_formulaic = [item for item in audited_items if not item["is_formulaic_or_matrix_like"]]
    summary.update(
        {
            "avg_similarity_formulaic_or_matrix": round(
                mean([item["literal_natural_similarity"] for item in formulaic]), 6
            )
            if formulaic
            else None,
            "avg_similarity_non_formulaic": round(
                mean([item["literal_natural_similarity"] for item in non_formulaic]), 6
            )
            if non_formulaic
            else None,
            "near_identical_095_formulaic_or_matrix_count": sum(
                item["literal_natural_similarity"] >= 0.95 for item in formulaic
            ),
            "near_identical_095_non_formulaic_count": sum(
                item["literal_natural_similarity"] >= 0.95 for item in non_formulaic
            ),
            "baseline_avg_similarity": summary.get("avg_literal_natural_similarity"),
            "near_identical_095_share": round(
                summary.get("near_identical_095_count", 0) / len(audited_items), 6
            )
            if audited_items
            else 0,
        }
    )

    def grouped(field: str) -> dict[str, Any]:
        groups: dict[str, list[dict[str, Any]]] = defaultdict(list)
        for item in audited_items:
            groups[str(item.get(field) or "unknown")].append(item)
        return {key: group_summary(value) for key, value in sorted(groups.items())}

    worst = sorted(
        audited_items,
        key=lambda item: (
            item["literal_natural_similarity"],
            len(item["readability_warning_flags"]),
            not item["is_formulaic_or_matrix_like"],
        ),
        reverse=True,
    )[:20]
    best = sorted(
        audited_items,
        key=lambda item: (
            item["literal_natural_similarity"],
            len(item["readability_warning_flags"]),
        ),
    )[:12]
    return {
        "schema_version": SCHEMA_VERSION,
        "source_file": str(source_file),
        "source_file_sha256": file_sha256(source_file),
        "total_items": len(audited_items),
        "api_llm_calls": 0,
        "network_calls": 0,
        "summary": summary,
        "by_text_layer": grouped("text_layer"),
        "by_chunk_type": grouped("chunk_type"),
        "by_length_bucket": grouped("length_bucket"),
        "worst_cases": [compact_item_for_report(item) for item in worst],
        "best_cases": [compact_item_for_report(item) for item in best],
        "items": audited_items,
    }


def compact_item_for_report(item: dict[str, Any]) -> dict[str, Any]:
    return {
        "stable_segment_key": item.get("stable_segment_key"),
        "source_path": item.get("source_path"),
        "text_layer": item.get("text_layer"),
        "chunk_type": item.get("chunk_type"),
        "length_bucket": item.get("length_bucket"),
        "literal_natural_similarity": item.get("literal_natural_similarity"),
        "natural_to_literal_length_ratio": item.get("natural_to_literal_length_ratio"),
        "is_formulaic_or_matrix_like": item.get("is_formulaic_or_matrix_like"),
        "readability_warning_flags": item.get("readability_warning_flags", []),
        "literal_ko_excerpt": excerpt(item.get("literal_ko") or "", 220),
        "natural_ko_excerpt": excerpt(item.get("natural_ko") or "", 220),
    }


def excerpt(text: str, limit: int = 180) -> str:
    normalized = re.sub(r"\s+", " ", text or "").strip()
    return normalized if len(normalized) <= limit else normalized[: limit - 1] + "…"


def select_calibration_items(audit: dict[str, Any], *, seed: str = DEFAULT_SEED) -> dict[str, Any]:
    items = list(audit["items"])
    selected: list[dict[str, Any]] = []
    selected_keys: set[str] = set()
    warnings: list[str] = []

    def add(item: dict[str, Any], reason: str, role: str | None = None) -> bool:
        key = item["stable_segment_key"]
        if key in selected_keys:
            return False
        enriched = dict(item)
        enriched["selection_reason"] = reason
        enriched["calibration_role"] = role or calibration_role_for_item(item)
        selected.append(enriched)
        selected_keys.add(key)
        return True

    by_layer: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for item in items:
        by_layer[str(item.get("text_layer") or "unknown")].append(item)

    target_layers = ("mula", "atthakatha", "tika")
    for layer in target_layers:
        layer_items = by_layer.get(layer, [])
        if len(layer_items) < 10:
            warnings.append(f"layer_{layer}_has_fewer_than_10_items")
        offenders = sorted(
            [
                item
                for item in layer_items
                if item["natural_same_as_literal"] or item["literal_natural_similarity"] >= 0.95
            ],
            key=lambda item: (-item["literal_natural_similarity"], stable_sort_key(seed, item["stable_segment_key"], "offender")),
        )
        for item in offenders[:4]:
            add(item, "baseline_near_identical_offender", "improvement_target")

        controls = sorted(
            [item for item in layer_items if item["is_formulaic_or_matrix_like"]],
            key=lambda item: (-item["literal_natural_similarity"], stable_sort_key(seed, item["stable_segment_key"], "control")),
        )
        for item in controls[:2]:
            add(item, "formulaic_or_matrix_convergence_control", "convergence_control")

        lemma_heavy = sorted(
            [
                item
                for item in layer_items
                if item["natural_raneun_geot_count"] >= 1
                or item["natural_formulaic_gloss_count"] >= 2
                or item["natural_lemma_quote_count"] >= 2
            ],
            key=lambda item: (
                -item["natural_raneun_geot_count"],
                -item["natural_formulaic_gloss_count"],
                stable_sort_key(seed, item["stable_segment_key"], "lemma"),
            ),
        )
        for item in lemma_heavy[:3]:
            add(item, "lemma_gloss_heavy_readability_target", "improvement_target")

        pali_heavy = sorted(
            [
                item
                for item in layer_items
                if item["natural_pali_parentheses_count"] >= 2 or item["natural_pali_token_count"] >= 4
            ],
            key=lambda item: (
                -item["natural_pali_parentheses_count"],
                -item["natural_pali_token_count"],
                stable_sort_key(seed, item["stable_segment_key"], "pali"),
            ),
        )
        for item in pali_heavy[:2]:
            add(item, "pali_parentheses_or_token_heavy_target", "improvement_target")

        long_sentence = sorted(
            [item for item in layer_items if item["natural_avg_sentence_length_chars"] >= 120],
            key=lambda item: (-item["natural_avg_sentence_length_chars"], stable_sort_key(seed, item["stable_segment_key"], "long")),
        )
        for item in long_sentence[:2]:
            add(item, "long_sentence_readability_target", "improvement_target")

        layer_selected = [item for item in selected if item.get("text_layer") == layer]
        remaining = sorted(
            [item for item in layer_items if item["stable_segment_key"] not in selected_keys],
            key=lambda item: (
                -len(item["readability_warning_flags"]),
                -item["literal_natural_similarity"],
                stable_sort_key(seed, item["stable_segment_key"], "fill"),
            ),
        )
        for item in remaining:
            if len([entry for entry in selected if entry.get("text_layer") == layer]) >= 10:
                break
            reason = "narrative_or_discursive_readability_target"
            role = calibration_role_for_item(item)
            add(item, reason, role)

        layer_selected = [item for item in selected if item.get("text_layer") == layer]
        if len(layer_selected) > 10:
            keep = set(
                item["stable_segment_key"]
                for item in sorted(
                    layer_selected,
                    key=lambda item: selection_keep_priority(item, seed),
                )[:10]
            )
            selected = [item for item in selected if item.get("text_layer") != layer or item["stable_segment_key"] in keep]
            selected_keys = {item["stable_segment_key"] for item in selected}

    selected = sorted(
        selected,
        key=lambda item: (target_layers.index(item["text_layer"]) if item.get("text_layer") in target_layers else 99,
                          stable_sort_key(seed, item["stable_segment_key"], "final")),
    )
    rebalance_calibration_roles(selected, seed)
    if len(selected) != 30:
        warnings.append(f"selected_count_{len(selected)}_instead_of_30")
    role_counts = Counter(item["calibration_role"] for item in selected)
    layer_counts = Counter(item.get("text_layer") for item in selected)
    if role_counts.get("convergence_control", 0) < 6 or role_counts.get("convergence_control", 0) > 8:
        warnings.append("convergence_control_count_outside_target_6_to_8")
    for layer in target_layers:
        if layer_counts.get(layer, 0) != 10:
            warnings.append(f"layer_{layer}_count_{layer_counts.get(layer, 0)}_instead_of_10")

    return {
        "schema_version": "natural_ko_calibration_30_selection_v1",
        "selection_seed": seed,
        "selected_count": len(selected),
        "target_distribution_by_layer": {"mula": 10, "atthakatha": 10, "tika": 10},
        "actual_distribution_by_layer": dict(sorted(layer_counts.items())),
        "calibration_role_counts": dict(sorted(role_counts.items())),
        "warnings": warnings,
        "items": [calibration_item_payload(item) for item in selected],
    }


def rebalance_calibration_roles(selected: list[dict[str, Any]], seed: str) -> None:
    """Keep convergence controls in the requested 6-8 range when possible."""
    controls = [item for item in selected if item.get("calibration_role") == "convergence_control"]
    if len(controls) < 6:
        candidates = sorted(
            [
                item
                for item in selected
                if item.get("calibration_role") == "improvement_target" and item.get("is_formulaic_or_matrix_like")
            ],
            key=lambda item: (
                item.get("selection_reason") != "baseline_near_identical_offender",
                -float(item.get("literal_natural_similarity", 0)),
                stable_sort_key(seed, item["stable_segment_key"], "role-up"),
            ),
        )
        for item in candidates[: 6 - len(controls)]:
            item["calibration_role"] = "convergence_control"
    elif len(controls) > 8:
        candidates = sorted(
            controls,
            key=lambda item: (
                item.get("selection_reason") == "formulaic_or_matrix_convergence_control",
                float(item.get("literal_natural_similarity", 0)),
                stable_sort_key(seed, item["stable_segment_key"], "role-down"),
            ),
        )
        for item in candidates[: len(controls) - 8]:
            item["calibration_role"] = "improvement_target"


def selection_keep_priority(item: dict[str, Any], seed: str) -> tuple[int, str]:
    reason = item.get("selection_reason")
    reason_rank = {
        "baseline_near_identical_offender": 0,
        "formulaic_or_matrix_convergence_control": 1,
        "lemma_gloss_heavy_readability_target": 2,
        "pali_parentheses_or_token_heavy_target": 3,
        "long_sentence_readability_target": 4,
    }.get(reason, 5)
    return (reason_rank, stable_sort_key(seed, item["stable_segment_key"], "keep"))


def calibration_role_for_item(item: dict[str, Any]) -> str:
    return "convergence_control" if item.get("is_formulaic_or_matrix_like") else "improvement_target"


def calibration_item_payload(item: dict[str, Any]) -> dict[str, Any]:
    return {
        "stable_segment_key": item.get("stable_segment_key"),
        "source_path": item.get("source_path"),
        "source_text_hash": item.get("source_text_hash"),
        "text_layer": item.get("text_layer"),
        "chunk_type": item.get("chunk_type"),
        "length_bucket": item.get("length_bucket"),
        "selection_reason": item.get("selection_reason"),
        "calibration_role": item.get("calibration_role"),
        "readability_problem_flags": item.get("readability_warning_flags", []),
        "literal_natural_similarity": f"{float(item.get('literal_natural_similarity', 0)):.6f}",
        "natural_to_literal_length_ratio": (
            f"{float(item['natural_to_literal_length_ratio']):.6f}"
            if item.get("natural_to_literal_length_ratio") is not None
            else None
        ),
        "original_text": item.get("original_text"),
        "baseline_literal_ko": item.get("literal_ko"),
        "baseline_natural_ko": item.get("natural_ko"),
        "terms": item.get("terms", []),
        "grammar_notes": item.get("grammar_notes", []),
        "doctrinal_notes": item.get("doctrinal_notes", []),
        "uncertainties": item.get("uncertainties", []),
    }


def build_request_previews(selection: dict[str, Any]) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    schema = build_response_schema_experiment()["response_schema"]
    arm_v1: list[dict[str, Any]] = []
    arm_v2: list[dict[str, Any]] = []
    for item in selection["items"]:
        segment = {
            "stable_segment_key": item["stable_segment_key"],
            "source_path": item.get("source_path"),
            "source_text_hash": item.get("source_text_hash"),
            "text_layer": item.get("text_layer"),
            "chunk_type": item.get("chunk_type"),
            "length_bucket": item.get("length_bucket"),
            "original_text": item.get("original_text"),
            "normalized_text": item.get("original_text"),
            "canonical_ref": "",
            "heading_path": [],
        }
        prompt_v1 = render_korean_advanced_prompt_v1(segment)
        prompt_v2 = render_natural_ko_v2_prompt(prompt_v1)
        base_config = {
            "response_mime_type": "application/json",
            "response_schema": schema,
        }
        metadata = {
            "stable_segment_key": item["stable_segment_key"],
            "source_path": item.get("source_path"),
            "source_text_hash": item.get("source_text_hash"),
            "text_layer": item.get("text_layer"),
            "chunk_type": item.get("chunk_type"),
            "length_bucket": item.get("length_bucket"),
            "calibration_role": item.get("calibration_role"),
            "selection_reason": item.get("selection_reason"),
        }
        arm_v1.append(
            {
                "key": item["stable_segment_key"],
                "arm": "A_prime_natural_ko_v1_response_schema",
                "calibration_role": item["calibration_role"],
                "metadata": metadata,
                "request": {
                    "model": KOREAN_ADVANCED_PROMPT_MODEL,
                    "contents": [{"role": "user", "parts": [{"text": prompt_v1}]}],
                    "generation_config": dict(base_config),
                },
            }
        )
        arm_v2.append(
            {
                "key": item["stable_segment_key"],
                "arm": "B_natural_ko_v2_response_schema",
                "calibration_role": item["calibration_role"],
                "metadata": metadata,
                "request": {
                    "model": KOREAN_ADVANCED_PROMPT_MODEL,
                    "contents": [{"role": "user", "parts": [{"text": prompt_v2}]}],
                    "generation_config": dict(base_config),
                },
            }
        )
    return arm_v1, arm_v2


def render_natural_ko_v2_prompt(prompt_v1: str) -> str:
    """Replace the production natural_ko guidance with the v2 calibration block."""
    start = prompt_v1.find("natural_ko 작성 원칙:")
    end = prompt_v1.find("\n\n용어 정책:", start)
    replacement = (
        "natural_ko 작성 원칙 (v2 calibration override):\n"
        "The following block replaces the production v1 natural_ko guidance for this calibration arm.\n\n"
        f"{NATURAL_KO_V2_INSTRUCTION.strip()}"
    )
    if start == -1 or end == -1:
        return f"{prompt_v1}\n\n---\n{replacement}\n"
    return f"{prompt_v1[:start]}{replacement}{prompt_v1[end:]}"


def render_prompt_variant() -> str:
    return f"""# natural_ko_v2 Prompt Variant

Status: experiment-only prompt variant for Step 5.5-C/D. This file is not a production prompt replacement.

Output schema: unchanged. Do not add any new output field.

```text
{NATURAL_KO_V2_INSTRUCTION.strip()}
```
"""


def render_audit_markdown(audit: dict[str, Any]) -> str:
    summary = audit["summary"]
    layer_lines = []
    for layer, payload in audit["by_text_layer"].items():
        if payload.get("count", 0):
            layer_lines.append(
                f"| {layer} | {payload['count']} | {payload['avg_literal_natural_similarity']:.6f} | "
                f"{payload['near_identical_095_count']} | {payload['same_as_literal_count']} |"
            )
    worst_lines = []
    for item in audit["worst_cases"][:10]:
        worst_lines.append(
            f"- `{item['stable_segment_key']}` ({item['text_layer']}, sim={item['literal_natural_similarity']:.6f}): "
            f"{', '.join(item['readability_warning_flags']) or 'no flags'}"
        )
    return f"""# natural_ko Readability Audit for 300 Pilot

## Purpose

This audit checks whether `natural_ko` is functioning as a publishable modern Korean Buddhist-book translation rather than a lightly polished `literal_ko`.

`reader_ko` is not being added. The target is to make `natural_ko` itself fulfill its intended role.

## Headline Metrics

- Total items: {audit['total_items']}
- Average literal/natural similarity: {summary['avg_literal_natural_similarity']:.6f}
- Median literal/natural similarity: {summary['median_literal_natural_similarity']:.6f}
- Near-identical similarity >= 0.95: {summary['near_identical_095_count']} ({summary['near_identical_095_share']:.2%})
- Similarity >= 0.90: {summary['too_close_090_count']}
- Similarity >= 0.85: {summary['close_085_count']}
- Exact same literal/natural: {summary['same_as_literal_count']}
- Average similarity, formulaic or matrix-like: {summary['avg_similarity_formulaic_or_matrix']}
- Average similarity, non-formulaic: {summary['avg_similarity_non_formulaic']}
- Natural Pāli parentheses total: {summary['natural_pali_parentheses_total']}
- Natural Pāli token total: {summary['natural_pali_token_total']}
- Formulaic gloss phrase total: {summary['natural_formulaic_gloss_total']}
- Long-sentence warnings: {summary['natural_sentence_too_long_count']}

## By Text Layer

| Layer | Count | Avg Similarity | Near-identical >=0.95 | Same as literal |
|---|---:|---:|---:|---:|
{chr(10).join(layer_lines)}

## Diagnosis

The central risk is not that `natural_ko` is too short. Proper Korean re-expression may keep the same total length or even increase it. The readability target is shorter, clearer Korean sentences where useful: sentence count may rise and average sentence length should fall, while doctrinal meaning, referents, and logical relations remain intact.

High similarity is expected for some matrix-like, list-like, or very short formulaic passages. Those cases are marked as `formulaic_exception_possible`, not treated as automatic passes.

Recurring style problems include literal clause order, repeated lemma-gloss phrasing such as "A라는 것은 B라는 뜻이다", dense Pāli parenthetical carry-over, and long commentary sentences that remain too close to the source structure.

## Representative Worst Cases

{chr(10).join(worst_lines)}

## Recommendation

Run a controlled 30-item Step 5.5-C/D micro-smoke before Step 6. Both arms should use response_schema:

- A′: current production prompt v1, response_schema on.
- B: natural_ko_v2 prompt variant, response_schema on.

The existing free-form 300 output is a reference view only, not the controlled baseline.
"""


def render_selection_markdown(selection: dict[str, Any]) -> str:
    rows = []
    for item in selection["items"]:
        rows.append(
            f"| `{item['stable_segment_key']}` | {item['text_layer']} | {item['calibration_role']} | "
            f"{item['selection_reason']} | {item['literal_natural_similarity']} |"
        )
    return f"""# natural_ko_v2 Calibration 30 Selection

- Selected count: {selection['selected_count']}
- Target distribution: mula 10 / atthakatha 10 / tika 10
- Actual distribution: {selection['actual_distribution_by_layer']}
- Calibration role split: {selection['calibration_role_counts']}
- Warnings: {selection['warnings'] or []}

The set is intentionally diagnostic. `improvement_target` items should become more readable under v2. `convergence_control` items are formulaic or matrix-like cases where forcing divergence would be a failure.

| stable_segment_key | layer | role | reason | similarity |
|---|---|---|---|---:|
{chr(10).join(rows)}
"""


def render_dry_run_plan(selection: dict[str, Any]) -> str:
    return f"""# natural_ko_v2 Controlled Dry-run Plan

Status: dry-run preparation only. No Gemini/API/Batch/network call was made.

## Controlled A′/B Design

The later smoke must isolate the prompt change from the output-method change. Therefore both arms use response_schema:

- A′: current production prompt v1, read-only and unchanged.
- B: natural_ko_v2 prompt variant.

The existing 300 free-form output is retained as a reference view only, not the controlled comparison baseline.

## Planned Later Smoke

- selected_count: {selection['selected_count']}
- estimated API calls for later live smoke: 60 (30 A′ + 30 B)
- API calls made in this task: 0
- response_schema: on
- salvage fallback: on
- reader_ko: not added
- hard cost cap recommendation for later smoke: $4
- calibration role split: {selection['calibration_role_counts']}

## Future Step 5.5-C/D Checks

1. literal_ko stability: literal_ko similarity A′↔B should be approximately 1.0. Large movement means the natural_ko-only prompt change leaked into literal_ko.
2. Fidelity pass is human/scholar review. The operator is not a Pāli expert, so each B natural_ko must be checked against literal_ko plus original_text for dropped, added, or distorted doctrinal content. Auto-metrics such as preserved terms/notes and no added claims are supporting signals only.
3. The readability target is not shorter total natural_ko length. The target is clearer modern Korean, often via shorter sentences and less lemma-gloss repetition.

## Output Files

- natural_ko_v1_request_preview.jsonl
- natural_ko_v2_request_preview.jsonl

Do not submit either preview in Step 5.5-A/B.
"""


def build_run_manifest(
    *,
    source_file: Path,
    out_dir: Path,
    audit: dict[str, Any],
    selection: dict[str, Any],
) -> dict[str, Any]:
    return {
        "step": RUN_STEP,
        "created_at": datetime.now(UTC).isoformat(),
        "api_llm_calls": 0,
        "api_calls_made_in_this_task": 0,
        "network_calls": 0,
        "batch_submissions": 0,
        "translation_generation": False,
        "live_smoke_started": False,
        "step5_selection_modified": False,
        "step6_started": False,
        "reader_ko_added": False,
        "production_prompt_changed": False,
        "prompt_variant_created": True,
        "production_prompt_mutation": False,
        "glossary_mutation": False,
        "gold_set_mutation": False,
        "source_xml_mutation": False,
        "translation_corpus_mutation": False,
        "holdout_gold_frozen": False,
        "response_schema_default_for_later_smoke": True,
        "salvage_cascade_fallback": True,
        "gold_accuracy_available": False,
        "silver_canary_status": "advisory_only_not_gold_accuracy",
        "controlled_arms": {
            "A_prime": "current_production_prompt_v1_response_schema",
            "B": "natural_ko_v2_prompt_variant_response_schema",
            "existing_300_free_form_output": "reference_only_not_controlled_baseline",
        },
        "estimated_api_calls_for_later_smoke": 60,
        "hard_cost_cap_recommendation_for_later_smoke_usd": "4",
        "input_files": {
            "readable_300_markdown": str(source_file),
        },
        "output_files": {
            "readability_audit_json": str(out_dir / "readability_audit_300.json"),
            "readability_audit_md": str(out_dir / "readability_audit_300.md"),
            "calibration_selection_json": str(out_dir / "calibration_30_selection.json"),
            "calibration_selection_md": str(out_dir / "calibration_30_selection.md"),
            "prompt_variant": str(out_dir / "prompt_variant_natural_ko_v2.md"),
            "dry_run_plan": str(out_dir / "natural_ko_v2_dry_run_plan.md"),
            "natural_ko_v1_request_preview": str(out_dir / "natural_ko_v1_request_preview.jsonl"),
            "natural_ko_v2_request_preview": str(out_dir / "natural_ko_v2_request_preview.jsonl"),
        },
        "counts": {
            "parsed_items": audit["total_items"],
            "calibration_selected": selection["selected_count"],
            "calibration_by_layer": selection["actual_distribution_by_layer"],
            "calibration_roles": selection["calibration_role_counts"],
        },
        "prompt_template_version_read_only": KOREAN_ADVANCED_PROMPT_VERSION,
        "warnings": selection.get("warnings", []),
    }


def run_calibration_prep(
    *,
    source_file: Path = DEFAULT_INPUT,
    out_dir: Path = DEFAULT_OUT,
    pretty: bool = False,
) -> dict[str, Any]:
    items = parse_readable_markdown(source_file)
    audit = audit_items(items, source_file)
    selection = select_calibration_items(audit)
    arm_v1, arm_v2 = build_request_previews(selection)

    out_dir.mkdir(parents=True, exist_ok=True)
    write_json(out_dir / "readability_audit_300.json", audit, pretty=pretty)
    (out_dir / "readability_audit_300.md").write_text(render_audit_markdown(audit), encoding="utf-8")
    write_json(out_dir / "calibration_30_selection.json", selection, pretty=pretty)
    (out_dir / "calibration_30_selection.md").write_text(render_selection_markdown(selection), encoding="utf-8")
    (out_dir / "prompt_variant_natural_ko_v2.md").write_text(render_prompt_variant(), encoding="utf-8")
    (out_dir / "natural_ko_v2_dry_run_plan.md").write_text(render_dry_run_plan(selection), encoding="utf-8")
    write_jsonl(out_dir / "natural_ko_v1_request_preview.jsonl", arm_v1)
    write_jsonl(out_dir / "natural_ko_v2_request_preview.jsonl", arm_v2)
    manifest = build_run_manifest(source_file=source_file, out_dir=out_dir, audit=audit, selection=selection)
    write_json(out_dir / "run_manifest.json", manifest, pretty=pretty)
    return {
        "status": "PREP_COMPLETE",
        "source_file": str(source_file),
        "parsed_items": audit["total_items"],
        "selected_count": selection["selected_count"],
        "calibration_by_layer": selection["actual_distribution_by_layer"],
        "calibration_roles": selection["calibration_role_counts"],
        "api_llm_calls": 0,
        "network_calls": 0,
        "out_dir": str(out_dir),
        "warnings": selection.get("warnings", []),
    }

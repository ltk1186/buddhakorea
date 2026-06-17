"""Read-only deterministic QA layer for glossary and citation signals.

This module does not modify validators, prompts, databases, or translations.
It consumes parsed translation artifacts and emits review-oriented signals.
"""

from __future__ import annotations

import re
import unicodedata
from collections import Counter, defaultdict
from typing import Any, Iterable

from .glossary import (
    Glossary,
    detect_glossary_terms,
    extract_translation_head_terms,
)


QA_SIGNAL_CROSS_TERM_COLLISION = "cross_term_collision_review"
QA_SIGNAL_AVOID_KO_CONFLICT = "avoid_ko_conflict_candidate"

PALI_DIACRITIC_RE = re.compile(r"[āīūṅñṭḍṇḷṃĀĪŪṄÑṬḌṆḶṂ]")
ROMAN_TOKEN_RE = re.compile(r"[A-Za-zāīūṅñṭḍṇḷṃĀĪŪṄÑṬḌṆḶṂ]+(?:\.[A-Za-zāīūṅñṭḍṇḷṃĀĪŪṄÑṬḌṆḶṂ]+)*\.?")
PAREN_RE = re.compile(r"\(([^)]*[A-Za-zāīūṅñṭḍṇḷṃĀĪŪṄÑṬḌṆḶṂ][^)]*)\)")
BRACKET_RE = re.compile(r"\[([^\]]*[A-Za-zāīūṅñṭḍṇḷṃĀĪŪṄÑṬḌṆḶṂ][^\]]*)\]")

KNOWN_TEXT_TITLES = {
    "girimānandasutta",
    "visuddhimagga",
    "therīgāthā",
    "theragāthā",
    "jātaka",
    "dhammasaṅgaṇī",
    "mahāniddesa",
    "cūḷaniddesa",
    "paṭisambhidāmagga",
}
KNOWN_PERSON_NAMES = {
    "ānanda",
    "sāriputta",
    "mahāmoggallāna",
    "moggallāna",
    "kassapa",
    "buddha",
}
KNOWN_TECHNICAL_TERMS = {
    "bhavaṅga",
    "jhāna",
    "asubha",
    "kamma",
    "nibbāna",
    "vipassanā",
    "yoniso",
    "ayoniso",
    "manasikāra",
}
TRUE_UNTRANSLATED_PHRASES = {
    "anicca dukkha anattā",
    "aniccaṃ dukkhaṃ anattā",
}

BASE_CITATION_MAP = {
    "saṃ. ni.": "상윳따 니까야",
    "dī. ni.": "디가 니까야",
    "ma. ni.": "맛지마 니까야",
    "aṅ. ni.": "앙굿따라 니까야",
    "jā.": "자따까",
    "visuddhi.": "청정도론",
    "paṭi. ma.": "빠띠삼비다막가",
    "sārattha.": "사라앗타",
    "mahāni.": "마하닛데사",
    "cūḷani.": "쭐라닛데사",
    "kathā.": "까타왓투",
}
LAYER_SUFFIX_MAP = {
    "aṭṭha.": "주석",
    "ṭī.": "복주석",
}
LOCATOR_RE = re.compile(r"^\d+(?:\.\d+)*(?:-\d+(?:\.\d+)*)?$")


def detect_cross_term_collisions(
    parsed_segment: dict[str, Any],
    glossary: Glossary,
) -> list[dict[str, Any]]:
    pairs = _declared_cross_pairs(glossary)
    source_keys = {_norm(entry.pali) for entry in detect_glossary_terms(_source_text(parsed_segment), glossary)}
    observed = _observed_head_terms(parsed_segment, glossary)
    signals: list[dict[str, Any]] = []
    stable_key = str(parsed_segment.get("stable_segment_key") or "")

    for left, right in sorted(pairs):
        if left not in source_keys or right not in source_keys:
            continue
        left_ko = observed.get(left)
        right_ko = observed.get(right)
        if not left_ko or not right_ko:
            continue
        shared = sorted(set(left_ko) & set(right_ko))
        if not shared:
            continue
        signals.append(
            {
                "signal": QA_SIGNAL_CROSS_TERM_COLLISION,
                "severity": "review",
                "stable_segment_key": stable_key,
                "left_pali": glossary.by_pali[left].pali,
                "right_pali": glossary.by_pali[right].pali,
                "shared_ko": shared,
                "scope": "same_segment",
            }
        )
    return signals


def calculate_cross_term_metrics(
    parsed_segments: Iterable[dict[str, Any]] | dict[str, Any],
    glossary: Glossary,
) -> dict[str, Any]:
    segments = _segments_from_payload(parsed_segments)
    same_segment_signals: list[dict[str, Any]] = []
    global_observed: dict[tuple[str, str], dict[str, set[str]]] = {
        pair: defaultdict(set) for pair in _declared_cross_pairs(glossary)
    }

    for segment in segments:
        same_segment_signals.extend(detect_cross_term_collisions(segment, glossary))
        observed = _observed_head_terms(segment, glossary)
        for pair in global_observed:
            for side in pair:
                for ko in observed.get(side, []):
                    global_observed[pair][ko].add(side)

    repeated_global = []
    for pair, ko_map in global_observed.items():
        for ko, sides in sorted(ko_map.items()):
            if len(sides) > 1:
                repeated_global.append(
                    {
                        "left_pali": glossary.by_pali[pair[0]].pali,
                        "right_pali": glossary.by_pali[pair[1]].pali,
                        "shared_ko": ko,
                        "scope": "batch_diagnostic_only",
                    }
                )

    return {
        "same_segment_collision_count": len(same_segment_signals),
        "same_segment_signals": same_segment_signals,
        "batch_global_collision_diagnostics": repeated_global,
        "batch_global_collision_count": len(repeated_global),
        "hard_signal_count": 0,
    }


def detect_avoid_ko_conflicts(
    parsed_segment: dict[str, Any],
    glossary: Glossary,
) -> list[dict[str, Any]]:
    source_matches = detect_glossary_terms(_source_text(parsed_segment), glossary)
    source_keys = {_norm(entry.pali) for entry in source_matches}
    body = _body_translation_text(parsed_segment)
    observed_terms = dict(extract_translation_head_terms(parsed_segment, glossary))
    conflicts: list[dict[str, Any]] = []
    stable_key = str(parsed_segment.get("stable_segment_key") or "")

    for entry in source_matches:
        entry_key = _norm(entry.pali)
        if any(_norm(cross) in source_keys for cross in entry.cross_avoid):
            continue
        for avoided in entry.avoid_ko:
            if not avoided:
                continue
            locations = []
            if avoided in body:
                locations.append("literal_or_natural")
            if avoided in observed_terms.get(entry.pali, ""):
                locations.append("terms.ko")
            if not locations:
                continue
            conflicts.append(
                {
                    "signal": QA_SIGNAL_AVOID_KO_CONFLICT,
                    "severity": "review",
                    "stable_segment_key": stable_key,
                    "pali": entry.pali,
                    "avoid_ko": avoided,
                    "locations": locations,
                }
            )
    return conflicts


def reclassify_untranslated_pali_flags(parsed_segment: dict[str, Any]) -> dict[str, Any]:
    has_existing_flag = "contains_untranslated_pali" in (parsed_segment.get("local_validator_flags") or [])
    text = _body_translation_text(parsed_segment)
    detections: list[dict[str, str]] = []

    parenthetical_spans = _span_ranges(PAREN_RE, text)
    bracketed_spans = _span_ranges(BRACKET_RE, text)
    for match in ROMAN_TOKEN_RE.finditer(text):
        token = match.group(0).strip()
        if not token or not _looks_pali_like(token):
            continue
        category = _classify_roman_token(token, match.span(), text, parenthetical_spans, bracketed_spans)
        detections.append({"text": token, "classification": category})

    lowered = _norm(text)
    for phrase in TRUE_UNTRANSLATED_PHRASES:
        if phrase in lowered and not any(item["text"].casefold() == phrase for item in detections):
            detections.append(
                {
                    "text": phrase,
                    "classification": "possible_true_untranslated_pali",
                }
            )

    counter = Counter(item["classification"] for item in detections)
    if not detections and has_existing_flag:
        counter["unknown"] += 1
    final_status = "no_pali_detected"
    if counter.get("possible_true_untranslated_pali"):
        final_status = "possible_true_untranslated_pali"
    elif detections and all(key.startswith("allowed_") for key in counter):
        final_status = "allowed"
    elif detections:
        final_status = "unknown"

    return {
        "stable_segment_key": parsed_segment.get("stable_segment_key", ""),
        "had_contains_untranslated_pali": has_existing_flag,
        "final_status": final_status,
        "detections": detections,
        "classification_counts": dict(counter),
    }


def parse_composite_citation(raw_citation: str) -> dict[str, Any]:
    raw = _clean_citation(raw_citation)
    lowered = _norm(raw)
    base = ""
    base_display = ""
    for candidate in sorted(BASE_CITATION_MAP, key=len, reverse=True):
        if lowered.startswith(candidate):
            base = candidate
            base_display = BASE_CITATION_MAP[candidate]
            break

    if not base:
        return {
            "raw": raw,
            "mapped": False,
            "display": raw,
            "base_abbrev": "",
            "base_display": "",
            "layer_suffix": "",
            "layer_display": "",
            "locator": "",
        }

    remainder = raw[len(base) :].strip()
    layer_suffix = ""
    layer_display = ""
    lowered_remainder = _norm(remainder)
    for candidate, display in LAYER_SUFFIX_MAP.items():
        if lowered_remainder.startswith(candidate):
            layer_suffix = candidate
            layer_display = display
            remainder = remainder[len(candidate) :].strip()
            break

    locator = _extract_locator(remainder)
    pieces = [base_display]
    if layer_display:
        pieces.append(layer_display)
    if locator:
        pieces.append(locator)
    return {
        "raw": raw,
        "mapped": True,
        "display": " ".join(pieces),
        "base_abbrev": base,
        "base_display": base_display,
        "layer_suffix": layer_suffix,
        "layer_display": layer_display,
        "locator": locator,
    }


def map_citation_display(raw_citation: str) -> dict[str, Any]:
    return parse_composite_citation(raw_citation)


def build_glossary_qa_report(
    parsed_segments: Iterable[dict[str, Any]] | dict[str, Any],
    glossary: Glossary,
) -> dict[str, Any]:
    segments = _segments_from_payload(parsed_segments)
    cross_metrics = calculate_cross_term_metrics(segments, glossary)
    avoid_conflicts: list[dict[str, Any]] = []
    reclassifications: list[dict[str, Any]] = []
    citations: list[dict[str, Any]] = []

    for segment in segments:
        avoid_conflicts.extend(detect_avoid_ko_conflicts(segment, glossary))
        reclassifications.append(reclassify_untranslated_pali_flags(segment))
        for raw in _extract_citation_candidates(segment):
            mapped = map_citation_display(raw)
            mapped["stable_segment_key"] = segment.get("stable_segment_key", "")
            citations.append(mapped)

    reclass_counts = Counter(item["final_status"] for item in reclassifications)
    before_flag_count = sum(1 for item in reclassifications if item["had_contains_untranslated_pali"])
    after_possible_true = sum(
        1 for item in reclassifications if item["final_status"] == "possible_true_untranslated_pali"
    )
    mapped_count = sum(1 for item in citations if item["mapped"])

    return {
        "summary": {
            "total_segments": len(segments),
            "cross_term_collision_review_count": cross_metrics["same_segment_collision_count"],
            "avoid_ko_conflict_count": len(avoid_conflicts),
            "contains_untranslated_pali_before_count": before_flag_count,
            "contains_untranslated_pali_possible_true_after_count": after_possible_true,
            "citation_candidate_count": len(citations),
            "citation_mapped_count": mapped_count,
            "citation_mapping_coverage": round(mapped_count / len(citations), 6) if citations else 1.0,
        },
        "cross_term_metrics": cross_metrics,
        "avoid_ko_conflicts": avoid_conflicts,
        "untranslated_pali_reclassification_counts": dict(reclass_counts),
        "untranslated_pali_reclassifications": reclassifications,
        "citation_mapping": {
            "mapped_count": mapped_count,
            "total": len(citations),
            "coverage": round(mapped_count / len(citations), 6) if citations else 1.0,
            "items": citations,
        },
    }


def _declared_cross_pairs(glossary: Glossary) -> set[tuple[str, str]]:
    pairs: set[tuple[str, str]] = set()
    for entry in glossary.entries:
        left = _norm(entry.pali)
        for right_raw in entry.cross_avoid:
            right = _norm(right_raw)
            if right in glossary.by_pali:
                pairs.add(tuple(sorted((left, right))))
    return pairs


def _observed_head_terms(parsed_segment: dict[str, Any], glossary: Glossary) -> dict[str, set[str]]:
    observed: dict[str, set[str]] = defaultdict(set)
    for pali, ko in extract_translation_head_terms(parsed_segment, glossary):
        if ko:
            observed[_norm(pali)].add(ko)
    return observed


def _classify_roman_token(
    token: str,
    span: tuple[int, int],
    text: str,
    parenthetical_spans: list[tuple[int, int]],
    bracketed_spans: list[tuple[int, int]],
) -> str:
    normalized = _norm(token.strip("."))
    phrase = _expand_local_roman_phrase(text, span)
    phrase_norm = _norm(phrase.strip(" ."))
    if any(_inside(span, item) for item in parenthetical_spans):
        return "allowed_parenthetical_pali"
    if any(_inside(span, item) for item in bracketed_spans):
        return "allowed_bracketed_pali"
    if phrase_norm in TRUE_UNTRANSLATED_PHRASES or normalized in {"anicca", "dukkha", "anattā"}:
        return "possible_true_untranslated_pali"
    if normalized in KNOWN_TEXT_TITLES:
        return "allowed_text_title"
    if normalized in KNOWN_PERSON_NAMES:
        return "allowed_person_name"
    if normalized in KNOWN_TECHNICAL_TERMS:
        return "allowed_technical_term"
    if any(phrase_norm.startswith(key) for key in BASE_CITATION_MAP):
        return "allowed_citation_abbreviation"
    return "possible_true_untranslated_pali"


def _extract_citation_candidates(segment: dict[str, Any]) -> list[str]:
    text = "\n".join([_source_text(segment), _body_translation_text(segment)])
    candidates: list[str] = []
    seen: set[str] = set()
    base_pattern = "|".join(re.escape(key) for key in sorted(BASE_CITATION_MAP, key=len, reverse=True))
    layer_pattern = "|".join(re.escape(key) for key in sorted(LAYER_SUFFIX_MAP, key=len, reverse=True))
    pattern = re.compile(
        rf"(?i)\b(?:{base_pattern})(?:\s+(?:{layer_pattern}))?(?:\s+\d+(?:\.\d+)*)?"
    )
    for match in pattern.finditer(text):
        raw = _clean_citation(match.group(0))
        if raw and raw not in seen:
            seen.add(raw)
            candidates.append(raw)
    return candidates


def _translation_payload(segment: dict[str, Any]) -> dict[str, Any]:
    value = segment.get("parsed_translation_json") or segment.get("translation") or segment
    return value if isinstance(value, dict) else {}


def _source_text(segment: dict[str, Any]) -> str:
    return str(segment.get("original_text") or segment.get("source_text") or "")


def _body_translation_text(segment: dict[str, Any]) -> str:
    translation = _translation_payload(segment)
    return "\n".join(
        str(translation.get(key) or "")
        for key in ("literal_ko", "natural_ko")
        if isinstance(translation.get(key), str)
    )


def _segments_from_payload(payload: Iterable[dict[str, Any]] | dict[str, Any]) -> list[dict[str, Any]]:
    if isinstance(payload, dict):
        for key in ("items", "results", "parsed_results", "segments"):
            value = payload.get(key)
            if isinstance(value, list):
                return [item for item in value if isinstance(item, dict)]
        return [payload]
    return [item for item in payload if isinstance(item, dict)]


def _norm(value: str) -> str:
    return unicodedata.normalize("NFC", value).casefold().strip()


def _looks_pali_like(token: str) -> bool:
    return bool(PALI_DIACRITIC_RE.search(token))


def _span_ranges(pattern: re.Pattern[str], text: str) -> list[tuple[int, int]]:
    return [match.span(1) for match in pattern.finditer(text)]


def _inside(inner: tuple[int, int], outer: tuple[int, int]) -> bool:
    return outer[0] <= inner[0] and inner[1] <= outer[1]


def _expand_local_roman_phrase(text: str, span: tuple[int, int]) -> str:
    start, end = span
    while start > 0 and re.match(r"[A-Za-zāīūṅñṭḍṇḷṃĀĪŪṄÑṬḌṆḶṂ .]", text[start - 1]):
        start -= 1
    while end < len(text) and re.match(r"[A-Za-zāīūṅñṭḍṇḷṃĀĪŪṄÑṬḌṆḶṂ .]", text[end]):
        end += 1
    return text[start:end].strip()


def _clean_citation(value: str) -> str:
    return re.sub(r"\s+", " ", value.strip(" ;,()[]"))


def _extract_locator(remainder: str) -> str:
    for token in remainder.split():
        token = token.strip(" ;,()[]")
        if LOCATOR_RE.match(token):
            return token
    return ""

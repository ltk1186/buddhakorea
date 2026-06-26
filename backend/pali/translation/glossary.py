"""Deterministic glossary infrastructure for Pali translation QA.

This module is local-only: no provider APIs, database calls, embeddings, or
fuzzy matching. It uses conservative exact matching to avoid substring
collisions in Pali compounds.
"""

from __future__ import annotations

import json
import re
import unicodedata
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Iterable


TOKEN_RE = re.compile(r"[A-Za-zāīūṅñṭḍṇḷṃĀĪŪṄÑṬḌṆḶṂ]+")
FINAL_VOWELS = ("a", "ā", "i", "ī", "u", "ū")
INFLECTION_SUFFIXES = frozenset(
    {
        "ṃ",
        "ṁ",
        "o",
        "e",
        "aṃ",
        "ā",
        "ānaṃ",
        "āni",
        "āsu",
        "āya",
        "āyaṃ",
        "āyo",
        "āhi",
        "ābhi",
        "ehi",
        "ebhi",
        "ena",
        "esaṃ",
        "esu",
        "assa",
        "amhi",
        "asmiṃ",
        "ato",
        "enaṃ",
        "ika",
        "ikā",
        "iko",
        "ikaṃ",
        "ikāya",
        "ikāni",
        "ikānaṃ",
        "ti",
        "āti",
        "īti",
        "oti",
        "nti",
        "to",
        "su",
        "hi",
        "bhi",
        "naṃ",
        "mhi",
        "smiṃ",
    }
)


@dataclass(frozen=True)
class GlossaryVariant:
    context_key: str
    allowed_ko: tuple[str, ...]
    note: str = ""


@dataclass(frozen=True)
class GlossaryEntry:
    pali: str
    type: str
    status: str
    canonical_ko: str = ""
    natural_ko_allowed: tuple[str, ...] = ()
    avoid_ko: tuple[str, ...] = ()
    variants: tuple[GlossaryVariant, ...] = ()
    candidate_ko: tuple[str, ...] = ()
    note: str = ""
    priority: int = 0
    cross_avoid: tuple[str, ...] = ()

    @property
    def allowed_variant_ko(self) -> set[str]:
        allowed: set[str] = set()
        for variant in self.variants:
            allowed.update(variant.allowed_ko)
        return allowed


@dataclass(frozen=True)
class Glossary:
    schema_version: str
    entries: tuple[GlossaryEntry, ...]
    by_pali: dict[str, GlossaryEntry] = field(default_factory=dict)


def load_glossary(path: str | Path) -> Glossary:
    data = json.loads(Path(path).read_text(encoding="utf-8"))
    entries = tuple(_entry_from_dict(item) for item in data.get("entries", []))
    by_pali = {_norm(entry.pali): entry for entry in entries}
    return Glossary(
        schema_version=str(data.get("schema_version", "")),
        entries=entries,
        by_pali=by_pali,
    )


def detect_glossary_terms(
    source_text: str,
    glossary: Glossary,
    match_mode: str = "exact",
) -> list[GlossaryEntry]:
    if match_mode not in {"exact", "substring"}:
        raise ValueError("match_mode must be exact or substring")
    normalized_source = _norm(source_text)
    tokens = [_norm(token) for token in TOKEN_RE.findall(source_text)]
    matches: list[GlossaryEntry] = []

    for entry in glossary.entries:
        term = _norm(entry.pali)
        if match_mode == "substring":
            if term in normalized_source:
                matches.append(entry)
            continue
        if any(_token_matches_term(token, term) for token in tokens):
            matches.append(entry)
    return matches


def select_glossary_entries_for_segment(
    source_text: str,
    glossary: Glossary,
    max_n: int = 8,
) -> list[GlossaryEntry]:
    seen: set[str] = set()
    selected: list[GlossaryEntry] = []
    for entry in detect_glossary_terms(source_text, glossary, match_mode="exact"):
        key = _norm(entry.pali)
        if key in seen:
            continue
        seen.add(key)
        selected.append(entry)
    return sorted(selected, key=_entry_sort_key)[:max_n]


def extract_translation_head_terms(
    parsed_segment: dict[str, Any],
    glossary: Glossary,
) -> list[tuple[str, str]]:
    translation = _translation_payload(parsed_segment)
    extracted: list[tuple[str, str]] = []
    for term in translation.get("terms") or []:
        if not isinstance(term, dict):
            continue
        pali = str(term.get("pali", "")).strip()
        ko = str(term.get("ko", "")).strip()
        entry = glossary.by_pali.get(_norm(pali))
        if entry is None:
            continue
        extracted.append((entry.pali, ko))
    return extracted


def source_or_terms_text(parsed_segment: dict[str, Any]) -> str:
    """Return normalized Pali-bearing text used to scope glossary QA checks.

    This deliberately uses source text and declared Pali term heads, not Korean
    body text, so avoid/disallowed Korean renderings are only evaluated when the
    relevant Pali term is actually present in the segment context.
    """
    parts = [
        str(parsed_segment.get("original_text") or parsed_segment.get("source_text") or ""),
    ]
    translation = _translation_payload(parsed_segment)
    for term in translation.get("terms") or []:
        if isinstance(term, dict):
            parts.append(str(term.get("pali") or ""))
    for field in ("grammar_notes", "doctrinal_notes", "uncertainties"):
        value = translation.get(field) or []
        if isinstance(value, list):
            parts.extend(str(item) for item in value)
        elif isinstance(value, str):
            parts.append(value)
    return _norm("\n".join(parts))


def glossary_entry_is_triggered(entry: GlossaryEntry, parsed_segment: dict[str, Any]) -> bool:
    """Return True when a glossary entry is present in source or terms metadata."""
    trigger_text = source_or_terms_text(parsed_segment)
    if not trigger_text:
        return False
    term = _norm(entry.pali)
    tokens = [_norm(token) for token in TOKEN_RE.findall(trigger_text)]
    if any(_token_matches_term(token, term) for token in tokens):
        return True
    for pali, _ko in extract_translation_head_terms(parsed_segment, Glossary("", (entry,), {_norm(entry.pali): entry})):
        if _norm(pali) == term:
            return True
    return False


def calculate_term_consistency(
    parsed_segments: Iterable[dict[str, Any]] | dict[str, Any],
    glossary: Glossary,
) -> dict[str, Any]:
    segments = _segments_from_payload(parsed_segments)
    term_reports: dict[str, dict[str, Any]] = {
        entry.pali: _empty_term_report(entry) for entry in glossary.entries
    }

    for segment in segments:
        source_text = str(segment.get("original_text") or segment.get("source_text") or "")
        stable_key = str(segment.get("stable_segment_key") or "")
        source_matches = detect_glossary_terms(source_text, glossary, match_mode="exact")
        source_match_keys = {_norm(entry.pali) for entry in source_matches}
        for entry in source_matches:
            report = term_reports[entry.pali]
            report["source_match_count"] += 1
            if stable_key:
                report["source_match_examples"].append(stable_key)

        for pali, ko in extract_translation_head_terms(segment, glossary):
            report = term_reports[pali]
            report["exact_terms_count"] += 1
            if ko:
                report["observed_ko"][ko] = report["observed_ko"].get(ko, 0) + 1
                report["observed_examples"].setdefault(ko, []).append(stable_key)
            entry = glossary.by_pali[_norm(pali)]
            for avoided in entry.avoid_ko:
                if avoided and avoided in ko:
                    report["avoid_hits"].append(
                        {
                            "stable_segment_key": stable_key,
                            "avoid_ko": avoided,
                            "location": "terms.ko",
                        }
                    )

        body_text = _body_translation_text(segment)
        for entry in glossary.entries:
            key = _norm(entry.pali)
            if key not in source_match_keys and not glossary_entry_is_triggered(entry, segment):
                continue
            if any(_norm(cross) in source_match_keys for cross in entry.cross_avoid):
                continue
            for avoided in entry.avoid_ko:
                if avoided and avoided in body_text:
                    term_reports[entry.pali]["avoid_hits"].append(
                        {
                            "stable_segment_key": stable_key,
                            "avoid_ko": avoided,
                            "location": "literal_or_natural",
                        }
                    )

    summary = {
        "total_segments": len(segments),
        "fixed_terms": 0,
        "fixed_consistent": 0,
        "fixed_violations": 0,
        "context_variant_terms": 0,
        "context_unexpected_variants": 0,
        "needs_human_terms": 0,
    }

    for entry in glossary.entries:
        report = term_reports[entry.pali]
        observed = set(report["observed_ko"])
        if entry.type == "fixed":
            summary["fixed_terms"] += 1
            violations = []
            if len(observed) > 1:
                violations.append("multiple_observed_ko")
            if report["avoid_hits"]:
                violations.append("avoid_ko_observed")
            report["violations"] = violations
            report["consistent"] = not violations
            if violations:
                summary["fixed_violations"] += 1
            else:
                summary["fixed_consistent"] += 1
        elif entry.type == "context_variant":
            summary["context_variant_terms"] += 1
            allowed = entry.allowed_variant_ko
            unexpected = sorted(ko for ko in observed if ko not in allowed)
            report["allowed_variant_ko"] = sorted(allowed)
            report["unexpected_variants"] = unexpected
            if unexpected:
                summary["context_unexpected_variants"] += len(unexpected)
        elif entry.type == "needs_human":
            summary["needs_human_terms"] += 1
            report["consistency_excluded"] = True
            report["candidate_ko"] = list(entry.candidate_ko)

        report["source_match_examples"] = report["source_match_examples"][:5]
        report["observed_examples"] = {
            ko: examples[:5] for ko, examples in report["observed_examples"].items()
        }

    return {
        "summary": summary,
        "terms": term_reports,
    }


def render_injection_block(entries: list[GlossaryEntry]) -> str:
    if not entries:
        return ""
    lines = ["Controlled glossary hints for this segment:"]
    for entry in entries:
        if entry.type == "fixed":
            allowed = ", ".join(entry.natural_ko_allowed) or entry.canonical_ko
            avoided = ", ".join(entry.avoid_ko) or "none"
            lines.append(
                f"- {entry.pali}: use {entry.canonical_ko}; allowed natural forms: {allowed}; avoid: {avoided}."
            )
        elif entry.type == "context_variant":
            variants = "; ".join(
                f"{variant.context_key}: {', '.join(variant.allowed_ko)}"
                for variant in entry.variants
            )
            lines.append(
                f"- {entry.pali}: context variant, do not force one rendering. Allowed variants: {variants}."
            )
        elif entry.type == "needs_human":
            candidates = ", ".join(entry.candidate_ko)
            lines.append(
                f"- {entry.pali}: human review marker only; candidates: {candidates}. Do not treat as authoritative."
            )
    return "\n".join(lines)


def _entry_from_dict(item: dict[str, Any]) -> GlossaryEntry:
    variants = tuple(
        GlossaryVariant(
            context_key=str(variant.get("context_key", "")),
            allowed_ko=tuple(str(value) for value in variant.get("allowed_ko", [])),
            note=str(variant.get("note", "")),
        )
        for variant in item.get("variants", [])
    )
    return GlossaryEntry(
        pali=str(item["pali"]),
        type=str(item["type"]),
        status=str(item.get("status", "pending")),
        canonical_ko=str(item.get("canonical_ko", "")),
        natural_ko_allowed=tuple(str(value) for value in item.get("natural_ko_allowed", [])),
        avoid_ko=tuple(str(value) for value in item.get("avoid_ko", [])),
        variants=variants,
        candidate_ko=tuple(str(value) for value in item.get("candidate_ko", [])),
        note=str(item.get("note", "")),
        priority=int(item.get("priority", 0)),
        cross_avoid=tuple(str(value) for value in item.get("cross_avoid", [])),
    )


def _norm(value: str) -> str:
    return unicodedata.normalize("NFC", value).casefold().strip()


def _stem(term: str) -> str:
    return term[:-1] if term.endswith(FINAL_VOWELS) else term


def _token_matches_term(token: str, term: str) -> bool:
    if token == term:
        return True
    if token.startswith(term) and token[len(term) :] in INFLECTION_SUFFIXES:
        return True
    stem = _stem(term)
    if stem and token.startswith(stem) and token[len(stem) :] in INFLECTION_SUFFIXES:
        return True
    return False


def _entry_sort_key(entry: GlossaryEntry) -> tuple[int, int, str]:
    type_rank = {
        "needs_human": 0,
        "fixed": 1,
        "context_variant": 2,
    }.get(entry.type, 3)
    return (type_rank, -entry.priority, entry.pali)


def _segments_from_payload(payload: Iterable[dict[str, Any]] | dict[str, Any]) -> list[dict[str, Any]]:
    if isinstance(payload, dict):
        for key in ("items", "results", "parsed_results", "segments"):
            value = payload.get(key)
            if isinstance(value, list):
                return [item for item in value if isinstance(item, dict)]
        return [payload]
    return [item for item in payload if isinstance(item, dict)]


def _translation_payload(segment: dict[str, Any]) -> dict[str, Any]:
    translation = segment.get("parsed_translation_json") or segment.get("translation") or segment
    return translation if isinstance(translation, dict) else {}


def _body_translation_text(segment: dict[str, Any]) -> str:
    translation = _translation_payload(segment)
    parts: list[str] = []
    for key in ("literal_ko", "natural_ko"):
        value = translation.get(key)
        if isinstance(value, str):
            parts.append(value)
    return "\n".join(parts)


def _combined_translation_text(segment: dict[str, Any]) -> str:
    translation = _translation_payload(segment)
    parts: list[str] = [_body_translation_text(segment)]
    for term in translation.get("terms") or []:
        if isinstance(term, dict):
            for key in ("pali", "ko", "gloss", "note"):
                value = term.get(key)
                if isinstance(value, str):
                    parts.append(value)
    return "\n".join(parts)


def _empty_term_report(entry: GlossaryEntry) -> dict[str, Any]:
    return {
        "type": entry.type,
        "status": entry.status,
        "source_match_count": 0,
        "source_match_examples": [],
        "exact_terms_count": 0,
        "observed_ko": {},
        "observed_examples": {},
        "avoid_hits": [],
        "violations": [],
        "consistent": None,
    }

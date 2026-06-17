"""Gold set and regression helpers for Pali translation QA.

This module is deterministic and local-only. It does not call LLM providers,
databases, RAG systems, or external reference services.
"""

from __future__ import annotations

import json
import re
import unicodedata
from pathlib import Path
from typing import Any


POOLS = {"discovery", "holdout_gold", "regression_gold"}
ACCEPTANCE_TYPES = {"exact", "constraint", "reference"}
EVAL_MODES = {"terms_strict", "body_allowed"}
VERDICTS = {"improved", "worsened", "neutral", "escalate"}
PROTECTED_REFERENCE_KEYS = {
    "external_translation_text",
    "protected_translation_text",
    "parallel_translation_text",
    "source_translation_text",
    "quoted_translation",
    "full_translation",
    "translation_body",
    "translation_excerpt",
}
REQUIRED_ENTRY_FIELDS = {
    "gold_set_id",
    "pool",
    "stable_segment_key",
    "source_text",
    "acceptance_type",
    "rationale",
    "difficulty",
    "leverage",
    "reviewer_type",
    "expert_question_status",
    "adjudication_status",
    "gold_version",
    "created_from_pilot",
}
ROMAN_TOKEN_RE = re.compile(r"[A-Za-zāīūṅñṭḍṇḷṃĀĪŪṄÑṬḌṆḶṂ]+")
FINAL_VOWELS = ("a", "ā", "i", "ī", "u", "ū")
INFLECTION_SUFFIXES = frozenset(
    {
        "",
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


def load_gold_set(path: str | Path) -> dict[str, Any]:
    """Load a gold set JSON artifact."""

    return json.loads(Path(path).read_text(encoding="utf-8"))


def validate_gold_entry(entry: dict[str, Any]) -> dict[str, Any]:
    """Validate a single gold entry shape and reference hygiene."""

    errors: list[str] = []
    warnings: list[str] = []
    missing = sorted(field for field in REQUIRED_ENTRY_FIELDS if field not in entry)
    errors.extend(f"missing_field:{field}" for field in missing)

    if entry.get("pool") not in POOLS:
        errors.append("invalid_pool")
    if entry.get("acceptance_type") not in ACCEPTANCE_TYPES:
        errors.append("invalid_acceptance_type")
    if entry.get("eval_mode", "terms_strict") not in EVAL_MODES:
        errors.append("invalid_eval_mode")
    if not str(entry.get("stable_segment_key", "")).strip():
        errors.append("empty_stable_segment_key")
    if not str(entry.get("source_text", "")).strip():
        errors.append("empty_source_text")
    errors.extend(_protected_reference_errors(entry))
    warnings.extend(_long_note_warnings(entry))

    return {"valid": not errors, "errors": errors, "warnings": warnings}


def evaluate_against_gold(
    parsed_segment: dict[str, Any] | None,
    gold_entry: dict[str, Any],
) -> dict[str, Any]:
    """Evaluate one parsed segment against one gold entry.

    `reference` entries intentionally do not auto pass/fail.
    """

    validation = validate_gold_entry(gold_entry)
    if not validation["valid"]:
        return _evaluation(
            pass_value=None,
            auto_evaluable=False,
            acceptance_type=str(gold_entry.get("acceptance_type", "")),
            errors=validation["errors"],
        )
    if parsed_segment is None:
        return _evaluation(
            pass_value=False,
            auto_evaluable=True,
            acceptance_type=str(gold_entry.get("acceptance_type", "")),
            errors=["missing_parsed_segment"],
        )

    acceptance_type = str(gold_entry.get("acceptance_type"))
    if acceptance_type == "reference":
        return _evaluation(
            pass_value=None,
            auto_evaluable=False,
            acceptance_type=acceptance_type,
            errors=["reference_only_no_auto_pass_fail"],
        )
    if acceptance_type == "exact":
        return _evaluate_exact(parsed_segment, gold_entry)
    if acceptance_type == "constraint":
        return _evaluate_constraint(parsed_segment, gold_entry)
    return _evaluation(
        pass_value=None,
        auto_evaluable=False,
        acceptance_type=acceptance_type,
        errors=["unsupported_acceptance_type"],
    )


def gold_anchored_verdict(
    before_segment: dict[str, Any] | None,
    after_segment: dict[str, Any] | None,
    gold_entry: dict[str, Any] | None,
) -> dict[str, Any]:
    """Compare before/after results with a gold entry."""

    if gold_entry is None:
        return {
            "verdict": "escalate",
            "reason": "missing_gold_entry",
            "before_eval": None,
            "after_eval": None,
        }

    before_eval = evaluate_against_gold(before_segment, gold_entry)
    after_eval = evaluate_against_gold(after_segment, gold_entry)
    if not before_eval["auto_evaluable"] or not after_eval["auto_evaluable"]:
        verdict = "escalate"
        reason = "not_auto_evaluable"
    elif before_eval["pass"] is False and after_eval["pass"] is True:
        verdict = "improved"
        reason = "failed_to_passed"
    elif before_eval["pass"] is True and after_eval["pass"] is False:
        verdict = "worsened"
        reason = "passed_to_failed"
    else:
        verdict = "neutral"
        reason = "same_pass_state"

    return {
        "verdict": verdict,
        "reason": reason,
        "before_eval": before_eval,
        "after_eval": after_eval,
        "stable_segment_key": gold_entry.get("stable_segment_key", ""),
        "gold_set_id": gold_entry.get("gold_set_id", ""),
    }


def build_gold_regression_report(
    before_payload: dict[str, Any] | list[dict[str, Any]],
    after_payload: dict[str, Any] | list[dict[str, Any]],
    gold_set: dict[str, Any],
) -> dict[str, Any]:
    """Build a read-only before/after regression report."""

    before_by_key = _items_by_key(before_payload)
    after_by_key = _items_by_key(after_payload)
    results = []
    counts = {verdict: 0 for verdict in sorted(VERDICTS)}

    for entry in gold_set.get("entries", []):
        key = str(entry.get("stable_segment_key", ""))
        result = gold_anchored_verdict(before_by_key.get(key), after_by_key.get(key), entry)
        counts[result["verdict"]] += 1
        results.append(result)

    return {
        "gold_set_schema_version": gold_set.get("schema_version", ""),
        "gold_entry_count": len(gold_set.get("entries", [])),
        "verdict_counts": counts,
        "results": results,
    }


def _evaluate_exact(parsed_segment: dict[str, Any], gold_entry: dict[str, Any]) -> dict[str, Any]:
    translation = _translation_payload(parsed_segment)
    expected_literal = gold_entry.get("accepted_literal_ko")
    expected_natural = gold_entry.get("accepted_natural_ko")
    errors = []
    if expected_literal is None and expected_natural is None:
        return _evaluation(
            pass_value=None,
            auto_evaluable=False,
            acceptance_type="exact",
            errors=["exact_entry_without_expected_translation"],
        )
    if expected_literal is not None and translation.get("literal_ko") != expected_literal:
        errors.append("literal_ko_mismatch")
    if expected_natural is not None and translation.get("natural_ko") != expected_natural:
        errors.append("natural_ko_mismatch")
    return _evaluation(
        pass_value=not errors,
        auto_evaluable=True,
        acceptance_type="exact",
        errors=errors,
    )


def _evaluate_constraint(parsed_segment: dict[str, Any], gold_entry: dict[str, Any]) -> dict[str, Any]:
    required = list(gold_entry.get("required_terms") or [])
    forbidden = list(gold_entry.get("forbidden_terms") or [])
    variants = list(gold_entry.get("acceptable_variants") or [])
    terms = _term_pairs(parsed_segment)
    body = _body_text(parsed_segment)
    source_text = str(gold_entry.get("source_text") or parsed_segment.get("original_text") or "")
    eval_mode = str(gold_entry.get("eval_mode", "terms_strict"))

    matched_required: list[dict[str, str]] = []
    missing_required: list[dict[str, str]] = []
    hit_forbidden: list[dict[str, str]] = []
    matched_variants: list[dict[str, str]] = []

    for pair in required:
        if _pair_matches(pair, terms, body, source_text=source_text, eval_mode=eval_mode):
            matched_required.append(_pair_dict(pair))
        else:
            missing_required.append(_pair_dict(pair))
    for pair in forbidden:
        if _pair_matches(pair, terms, body, source_text=source_text, eval_mode=eval_mode):
            hit_forbidden.append(_pair_dict(pair))
    for pair in variants:
        if _pair_matches(pair, terms, body, source_text=source_text, eval_mode=eval_mode):
            matched_variants.append(_pair_dict(pair))

    passed = not missing_required and not hit_forbidden
    return {
        **_evaluation(
            pass_value=passed,
            auto_evaluable=True,
            acceptance_type="constraint",
            errors=[],
        ),
        "eval_mode": eval_mode,
        "matched_required": matched_required,
        "missing_required": missing_required,
        "hit_forbidden": hit_forbidden,
        "matched_variants": matched_variants,
    }


def _evaluation(
    *,
    pass_value: bool | None,
    auto_evaluable: bool,
    acceptance_type: str,
    errors: list[str],
) -> dict[str, Any]:
    return {
        "pass": pass_value,
        "auto_evaluable": auto_evaluable,
        "acceptance_type": acceptance_type,
        "errors": errors,
        "matched_required": [],
        "missing_required": [],
        "hit_forbidden": [],
        "matched_variants": [],
    }


def _translation_payload(segment: dict[str, Any]) -> dict[str, Any]:
    payload = segment.get("parsed_translation_json", segment)
    return payload if isinstance(payload, dict) else {}


def _term_pairs(segment: dict[str, Any]) -> set[tuple[str, str]]:
    translation = _translation_payload(segment)
    pairs: set[tuple[str, str]] = set()
    for item in translation.get("terms") or []:
        if not isinstance(item, dict):
            continue
        pali = str(item.get("pali", "")).strip()
        ko = str(item.get("ko", "")).strip()
        if pali and ko:
            pairs.add((pali, ko))
    return pairs


def _body_text(segment: dict[str, Any]) -> str:
    translation = _translation_payload(segment)
    return " ".join(
        str(translation.get(field, ""))
        for field in ("literal_ko", "natural_ko")
        if translation.get(field)
    )


def _pair_matches(
    pair: dict[str, Any],
    terms: set[tuple[str, str]],
    body: str,
    *,
    source_text: str,
    eval_mode: str,
) -> bool:
    pali = str(pair.get("pali", "")).strip()
    ko = str(pair.get("ko", "")).strip()
    if not ko:
        return False
    if pali:
        if (pali, ko) in terms:
            return True
        return eval_mode == "body_allowed" and ko in body and _pali_term_in_source(pali, source_text)
    if not pali and ko in body:
        return True
    return False


def _pair_dict(pair: dict[str, Any]) -> dict[str, str]:
    return {"pali": str(pair.get("pali", "")), "ko": str(pair.get("ko", ""))}


def _items_by_key(payload: dict[str, Any] | list[dict[str, Any]]) -> dict[str, dict[str, Any]]:
    if isinstance(payload, dict):
        items = payload.get("items", [])
    else:
        items = payload
    return {
        str(item.get("stable_segment_key", "")): item
        for item in items
        if isinstance(item, dict) and item.get("stable_segment_key")
    }


def _protected_reference_errors(value: Any, path: str = "") -> list[str]:
    errors: list[str] = []
    if isinstance(value, dict):
        for key, child in value.items():
            key_path = f"{path}.{key}" if path else str(key)
            if str(key) in PROTECTED_REFERENCE_KEYS:
                errors.append(f"protected_reference_body_field:{key_path}")
            errors.extend(_protected_reference_errors(child, key_path))
    elif isinstance(value, list):
        for index, child in enumerate(value):
            errors.extend(_protected_reference_errors(child, f"{path}[{index}]"))
    return errors


def _long_note_warnings(value: Any, path: str = "") -> list[str]:
    warnings: list[str] = []
    if isinstance(value, dict):
        for key, child in value.items():
            key_path = f"{path}.{key}" if path else str(key)
            if str(key) in {"note", "divergence_note", "rationale"}:
                word_count = len(str(child).split())
                if word_count > 30:
                    warnings.append(f"long_reference_note:{key_path}:{word_count}_words")
            warnings.extend(_long_note_warnings(child, key_path))
    elif isinstance(value, list):
        for index, child in enumerate(value):
            warnings.extend(_long_note_warnings(child, f"{path}[{index}]"))
    return warnings


def _pali_term_in_source(pali: str, source_text: str) -> bool:
    term = _norm(pali)
    tokens = [_norm(token) for token in ROMAN_TOKEN_RE.findall(source_text)]
    return any(_token_matches_term(token, term) for token in tokens)


def _token_matches_term(token: str, term: str) -> bool:
    if token == term:
        return True
    stem = _stem(term)
    return bool(stem and token.startswith(stem) and token[len(stem) :] in INFLECTION_SUFFIXES)


def _stem(term: str) -> str:
    if term.endswith(FINAL_VOWELS):
        return term[:-1]
    return term


def _norm(text: str) -> str:
    return unicodedata.normalize("NFC", text.strip().casefold())

"""Deterministic QA finding classifier for Pali translation outputs.

This module reduces noisy ``contains_untranslated_pali`` review signals by
classifying Pali/roman runs into allowed scholarly display patterns. It does
not certify translation correctness and never calls external services.
"""

from __future__ import annotations

import hashlib
import json
import math
import re
from collections import Counter
from dataclasses import dataclass
from typing import Any


PALI_DIACRITICS = "āīūṅñṭḍṇḷṃĀĪŪṄÑṬḌṆḶṂ"
ROMAN_CHARS = f"A-Za-z{PALI_DIACRITICS}"
ROMAN_TOKEN_RE = re.compile(rf"[{ROMAN_CHARS}][{ROMAN_CHARS}'’.-]*")
DIACRITIC_RE = re.compile(f"[{PALI_DIACRITICS}]")
HANGUL_RE = re.compile(r"[가-힣]")
PAREN_RE = re.compile(rf"[\(\[]\s*([{ROMAN_CHARS}][{ROMAN_CHARS}0-9 .,'’:/-]{{0,120}}?)\s*[\)\]]")
QUOTE_RE = re.compile(rf"['\"“”‘’]\s*([{ROMAN_CHARS}][{ROMAN_CHARS}0-9 .,'’:/-]{{0,120}}?)\s*['\"“”‘’]")
GRAMMAR_MARKER_RE = re.compile(
    r"(라는 것은|이라는 것은|라는 구절에서|이라는 구절에서|라는 단어는|이라는 단어는|라는 말은|"
    r"이라는 말은|의 뜻이다|라는 의미이다|이라는 의미이다|뜻한다|가리킨다|라고 한 것은)"
)
PROPER_SUFFIXES = (
    "magga",
    "vaṃsa",
    "nikāya",
    "piṭaka",
    "sutta",
    "jātaka",
    "gāthā",
    "vibha",
)
HUMAN_REVIEW_SIGNALS = {
    "grammar_uncertain",
    "needs_human_review",
    "retry_candidate",
    "doctrinal_risk",
    "low_confidence",
    "schema_invalid",
    "parse_failed",
    "json_parse_failed",
    "source_hash_mismatch",
    "silent_source_normalization",
    "raw_source_hash_mismatch",
    "normalized_source_hash_mismatch",
}


@dataclass(frozen=True)
class PaliRun:
    run_text: str
    location: str
    span: tuple[int, int]
    context_excerpt: str
    source: str
    in_parenthetical: bool = False
    in_quote: bool = False


def classify_review_findings(
    *,
    review_queue: dict[str, Any],
    parsed_payload: dict[str, Any],
    review_report_path: str = "",
    review_queue_path: str = "",
    parsed_path: str = "",
    sample_seed: int | None = None,
) -> dict[str, Any]:
    parsed_by_key = {
        item.get("stable_segment_key"): item
        for item in parsed_payload.get("items", [])
        if isinstance(item, dict)
    }
    input_items = review_queue.get("items") or []
    classified_items = [
        classify_review_item(item, parsed_by_key.get(item.get("stable_segment_key"), {}))
        for item in input_items
    ]
    summary_before = review_queue.get("summary") or {}
    seed = sample_seed if sample_seed is not None else stable_sample_seed(
        [str(item.get("stable_segment_key") or "") for item in classified_items]
    )
    return {
        "schema_version": "pali_qa_findings_classifier_v1",
        "input": {
            "review_queue": review_queue_path,
            "parsed_salvaged": parsed_path,
            "review_report": review_report_path,
        },
        "summary_before": {
            "human_needed": int(summary_before.get("human_needed_count") or len(input_items)),
            "priority_counts": summary_before.get("priority_counts") or {},
        },
        "summary_after": summary_after(classified_items),
        "subsignal_counts": subsignal_counts(classified_items),
        "run_coverage_summary": run_coverage_summary(classified_items),
        "items": classified_items,
        "sampling_recommendation": sampling_recommendation(classified_items, seed),
    }


def classify_review_item(queue_item: dict[str, Any], parsed_item: dict[str, Any]) -> dict[str, Any]:
    signals_before = sorted(set(str(signal) for signal in queue_item.get("signals") or []))
    runs = detect_pali_runs(parsed_item)
    terms = parsed_item.get("terms") or []
    classified_runs = [classify_run(run, parsed_item, terms) for run in runs]
    uncovered_runs = [run for run in classified_runs if not run["covered"]]
    signals_after = [signal for signal in signals_before if signal != "contains_untranslated_pali"]
    matched_patterns = sorted({run["coverage_rule"] for run in classified_runs if run["covered"]})
    if "contains_untranslated_pali" in signals_before:
        if uncovered_runs:
            signals_after.append("possible_untranslated_pali_strict")
        signals_after.extend(matched_patterns)
    grammar_hint = grammar_uncertain_hint(parsed_item, signals_before)
    if "grammar_uncertain" in signals_before and "grammar_uncertain_retained" not in signals_after:
        signals_after.append("grammar_uncertain_retained")

    review_required = review_required_after(signals_before, signals_after, uncovered_runs)
    decision = decide(signals_before, signals_after, classified_runs, uncovered_runs, review_required)
    priority_after = "auto_allowed" if not review_required else queue_item.get("priority", "C")
    second_model_candidate = decision == "needs_second_model_review"
    expert_candidate = grammar_hint["expert_question_candidate"] or decision == "needs_expert_review"
    return {
        "stable_segment_key": queue_item.get("stable_segment_key", ""),
        "priority_before": queue_item.get("priority", ""),
        "signals_before": signals_before,
        "signals_after": sorted(set(signals_after)),
        "priority_after": priority_after,
        "decision": decision,
        "decision_reason": decision_reason(decision, signals_after, uncovered_runs),
        "source_path": queue_item.get("source_path") or parsed_item.get("source_path", ""),
        "text_layer": queue_item.get("text_layer") or parsed_item.get("text_layer", ""),
        "chunk_type": queue_item.get("chunk_type") or parsed_item.get("chunk_type", ""),
        "length_bucket": queue_item.get("length_bucket") or parsed_item.get("length_bucket", ""),
        "matched_patterns": matched_patterns,
        "pali_runs": classified_runs,
        "uncovered_pali_runs": uncovered_runs,
        "run_worst_case_passed": not uncovered_runs,
        "signal_worst_case_passed": not review_required,
        "review_required_after_classification": review_required,
        "sample_review_candidate": not review_required and "contains_untranslated_pali" in signals_before,
        "expert_question_candidate": expert_candidate,
        "second_model_candidate": second_model_candidate,
        "grammar_uncertain_hint": grammar_hint["hint"],
        "grammar_uncertain_hint_reasons": grammar_hint["reasons"],
        "original_queue_item": queue_item,
    }


def detect_pali_runs(parsed_item: dict[str, Any]) -> list[dict[str, Any]]:
    fields = {
        "literal_ko": str(parsed_item.get("literal_ko") or ""),
        "natural_ko": str(parsed_item.get("natural_ko") or ""),
    }
    terms = parsed_item.get("terms") or []
    runs: list[PaliRun] = []
    for location, text in fields.items():
        runs.extend(parenthetical_runs(text, location))
        runs.extend(quoted_runs(text, location))
        runs.extend(diacritic_runs(text, location))
        runs.extend(known_term_or_title_runs(text, location, terms))
    return [run_to_dict(run) for run in dedupe_runs(runs)]


def parenthetical_runs(text: str, location: str) -> list[PaliRun]:
    runs = []
    for match in PAREN_RE.finditer(text):
        value = match.group(1).strip()
        if not roman_like(value):
            continue
        start = match.start(1)
        end = match.end(1)
        runs.append(
            PaliRun(
                run_text=value,
                location=location,
                span=(start, end),
                context_excerpt=context_excerpt(text, start, end),
                source="parenthetical",
                in_parenthetical=True,
            )
        )
    return runs


def quoted_runs(text: str, location: str) -> list[PaliRun]:
    runs = []
    for match in QUOTE_RE.finditer(text):
        value = match.group(1).strip()
        if not roman_like(value):
            continue
        # Mixed Korean quotes such as '그의(tassa)' are handled by the
        # parenthetical detector; the whole quote is not a Pali run.
        if HANGUL_RE.search(value):
            continue
        start = match.start(1)
        end = match.end(1)
        runs.append(
            PaliRun(
                run_text=value,
                location=location,
                span=(start, end),
                context_excerpt=context_excerpt(text, start, end),
                source="quote",
                in_quote=True,
            )
        )
    return runs


def diacritic_runs(text: str, location: str) -> list[PaliRun]:
    runs = []
    for match in ROMAN_TOKEN_RE.finditer(text):
        value = match.group(0)
        if not DIACRITIC_RE.search(value):
            continue
        runs.append(
            PaliRun(
                run_text=value,
                location=location,
                span=(match.start(), match.end()),
                context_excerpt=context_excerpt(text, match.start(), match.end()),
                source="diacritic",
            )
        )
    return runs


def known_term_or_title_runs(text: str, location: str, terms: list[dict[str, Any]]) -> list[PaliRun]:
    term_set = {normalize_pali(str(term.get("pali") or "")) for term in terms if term.get("pali")}
    runs = []
    for match in ROMAN_TOKEN_RE.finditer(text):
        value = match.group(0)
        normalized = normalize_pali(value)
        if not normalized:
            continue
        if normalized not in term_set and not proper_name_or_title_allowed(value):
            continue
        runs.append(
            PaliRun(
                run_text=value,
                location=location,
                span=(match.start(), match.end()),
                context_excerpt=context_excerpt(text, match.start(), match.end()),
                source="known_term_or_title",
            )
        )
    return runs


def dedupe_runs(runs: list[PaliRun]) -> list[PaliRun]:
    # Prefer wider context-specific runs, then suppress overlapping generic
    # diacritic token runs.
    source_priority = {"parenthetical": 0, "quote": 1, "known_term_or_title": 2, "diacritic": 3}
    runs = sorted(
        runs,
        key=lambda run: (
            run.location,
            run.span[0],
            source_priority.get(run.source, 9),
            -(run.span[1] - run.span[0]),
        ),
    )
    accepted: list[PaliRun] = []
    for run in runs:
        if any(run.location == other.location and spans_overlap(run.span, other.span) for other in accepted):
            continue
        accepted.append(run)
    return accepted


def classify_run(run: dict[str, Any], parsed_item: dict[str, Any], terms: list[dict[str, Any]]) -> dict[str, Any]:
    text = run["run_text"]
    coverage_rule = None
    if parenthetical_allowed(run):
        coverage_rule = "pali_parenthetical_allowed"
    elif terms_explained_allowed(text, terms):
        coverage_rule = "terms_explained_pali_allowed"
    elif grammar_quote_allowed(run):
        coverage_rule = "pali_grammar_quote_allowed"
    elif lemma_discussion_allowed(run):
        coverage_rule = "pali_lemma_discussion_allowed"
    elif proper_name_or_title_allowed(text):
        coverage_rule = "pali_proper_name_or_title_allowed"
    covered = coverage_rule is not None
    return {
        **run,
        "covered": covered,
        "coverage_rule": coverage_rule,
    }


def parenthetical_allowed(run: dict[str, Any]) -> bool:
    if not run.get("in_parenthetical"):
        return False
    excerpt = run.get("context_excerpt", "")
    before = excerpt.split(run["run_text"], 1)[0]
    return bool(HANGUL_RE.search(before))


def grammar_quote_allowed(run: dict[str, Any]) -> bool:
    excerpt = run.get("context_excerpt", "")
    if GRAMMAR_MARKER_RE.search(excerpt) and (run.get("in_quote") or run.get("in_parenthetical")):
        return True
    if re.search(rf"{re.escape(run['run_text'])}\s*[\(\[]\s*[가-힣][^\)\]]*[\)\]][\"'”’]?\s*(라는 것은|이라는 것은|라는 게송|는|은)", excerpt):
        return True
    return False


def lemma_discussion_allowed(run: dict[str, Any]) -> bool:
    excerpt = run.get("context_excerpt", "")
    if run.get("in_quote") and re.search(r"(는|은|란|라는 것은|이라는 것은|뜻이다|의미이다|뜻한다|가리킨다)", excerpt):
        return True
    return bool(
        re.search(
            rf"{re.escape(run['run_text'])}\s*(?:는|은|이|가|란|라는 것은|이라는 것은)[^.\n]{{0,80}}(뜻|의미|말하|가리킨|풀이)",
            excerpt,
        )
    )


def terms_explained_allowed(run_text: str, terms: list[dict[str, Any]]) -> bool:
    normalized = normalize_pali(run_text)
    for term in terms:
        pali = normalize_pali(str(term.get("pali") or ""))
        ko = str(term.get("ko") or "").strip()
        gloss = str(term.get("gloss") or term.get("note") or "").strip()
        if pali and normalized == pali and (ko or gloss):
            return True
    return False


def proper_name_or_title_allowed(run_text: str) -> bool:
    stripped = run_text.strip(" .'’")
    lower = stripped.lower()
    if "." in run_text and len(stripped) <= 20:
        return True
    if stripped[:1].isupper():
        return True
    return any(lower.endswith(suffix) for suffix in PROPER_SUFFIXES)


def review_required_after(signals_before: list[str], signals_after: list[str], uncovered_runs: list[dict[str, Any]]) -> bool:
    if uncovered_runs:
        return True
    signal_set = set(signals_before) | set(signals_after)
    if signal_set & HUMAN_REVIEW_SIGNALS:
        return True
    return False


def decide(
    signals_before: list[str],
    signals_after: list[str],
    runs: list[dict[str, Any]],
    uncovered_runs: list[dict[str, Any]],
    review_required: bool,
) -> str:
    signal_set = set(signals_before) | set(signals_after)
    if {"retry_candidate", "schema_invalid", "parse_failed", "json_parse_failed"} & signal_set:
        return "retry_candidate"
    if uncovered_runs:
        return "needs_human_review"
    if "grammar_uncertain" in signal_set or "grammar_uncertain_retained" in signal_set:
        return "needs_human_review"
    if "needs_human_review" in signal_set:
        return "needs_human_review"
    if "doctrinal_risk" in signal_set:
        return "needs_expert_review"
    if any(run.get("coverage_rule") == "pali_proper_name_or_title_allowed" for run in runs) and not review_required:
        return "glossary_or_allowlist_candidate"
    if "contains_untranslated_pali" in signals_before and runs and not review_required:
        return "auto_accept_with_display_policy"
    if not review_required:
        return "auto_accept"
    return "needs_human_review"


def decision_reason(decision: str, signals_after: list[str], uncovered_runs: list[dict[str, Any]]) -> str:
    if uncovered_runs:
        return "At least one Pali/roman run is not covered by allowed display, lemma, proper-name, or terms rules."
    if decision == "auto_accept_with_display_policy":
        return "All detected Pali runs are covered by allowed parenthetical, grammar quote, lemma discussion, proper-name/title, or terms rules."
    if decision == "needs_human_review" and "grammar_uncertain_retained" in signals_after:
        return "grammar_uncertain is retained for human review; deterministic classifier only provides ordering hints."
    if decision == "glossary_or_allowlist_candidate":
        return "Detected proper-name/title-like Pali run should be harvested as an allowlist candidate rather than treated as untranslated text."
    return decision.replace("_", " ")


def grammar_uncertain_hint(parsed_item: dict[str, Any], signals: list[str]) -> dict[str, Any]:
    if "grammar_uncertain" not in signals:
        return {"hint": "unknown", "reasons": [], "expert_question_candidate": False}
    text = " ".join(
        [
            " ".join(str(value) for value in parsed_item.get("uncertainties") or []),
            " ".join(str(value) for value in parsed_item.get("grammar_notes") or []),
            " ".join(str(value) for value in parsed_item.get("doctrinal_notes") or []),
        ]
    ).lower()
    reasons = []
    keywords = {
        "compound_interpretation_keyword": ["복합어", "compound", "samāsa", "해석 가능"],
        "negation_scope_keyword": ["부정", "not", " na ", "범위"],
        "doctrinal_term_keyword": ["교리", "doctrinal", "오온", "연기", "열반"],
        "quotation_or_particle_keyword": ["kho", "ti", "vā", "불변화사", "인용"],
    }
    for reason, words in keywords.items():
        if any(word in text for word in words):
            reasons.append(reason)
    flags = set(parsed_item.get("quality_flags") or [])
    if {"doctrinal_risk", "needs_human_review"} & flags:
        reasons.append("model_quality_flag_keyword")
    return {
        "hint": "possible_high" if reasons else "ordinary",
        "reasons": sorted(set(reasons)),
        "expert_question_candidate": bool(reasons),
    }


def summary_after(items: list[dict[str, Any]]) -> dict[str, Any]:
    decisions = Counter(item["decision"] for item in items)
    human_needed = sum(1 for item in items if item["review_required_after_classification"])
    grammar_auto = sum(
        1
        for item in items
        if "grammar_uncertain" in item["signals_before"] and not item["review_required_after_classification"]
    )
    return {
        "human_needed_effective": human_needed,
        "auto_accept": decisions.get("auto_accept", 0),
        "auto_accept_with_display_policy": decisions.get("auto_accept_with_display_policy", 0),
        "qa_false_positive": decisions.get("qa_false_positive", 0),
        "glossary_or_allowlist_candidate": decisions.get("glossary_or_allowlist_candidate", 0),
        "needs_human_review": decisions.get("needs_human_review", 0),
        "needs_second_model_review": decisions.get("needs_second_model_review", 0),
        "needs_expert_review": decisions.get("needs_expert_review", 0),
        "retry_candidate": decisions.get("retry_candidate", 0),
        "grammar_uncertain_auto_accepted": grammar_auto,
    }


def subsignal_counts(items: list[dict[str, Any]]) -> dict[str, int]:
    counter: Counter[str] = Counter()
    for item in items:
        for signal in item["signals_after"]:
            if signal.startswith("pali_") or signal in {
                "terms_explained_pali_allowed",
                "possible_untranslated_pali_strict",
                "grammar_uncertain_retained",
            }:
                counter[signal] += 1
    keys = [
        "pali_parenthetical_allowed",
        "pali_grammar_quote_allowed",
        "pali_lemma_discussion_allowed",
        "pali_proper_name_or_title_allowed",
        "terms_explained_pali_allowed",
        "possible_untranslated_pali_strict",
        "grammar_uncertain_retained",
    ]
    return {key: counter.get(key, 0) for key in keys}


def run_coverage_summary(items: list[dict[str, Any]]) -> dict[str, int]:
    total = sum(len(item["pali_runs"]) for item in items)
    covered = sum(sum(1 for run in item["pali_runs"] if run.get("covered")) for item in items)
    uncovered = sum(len(item["uncovered_pali_runs"]) for item in items)
    return {
        "total_pali_runs_detected": total,
        "covered_pali_runs": covered,
        "uncovered_pali_runs": uncovered,
        "run_worst_case_failures": sum(1 for item in items if not item["run_worst_case_passed"]),
        "signal_worst_case_failures": sum(1 for item in items if not item["signal_worst_case_passed"]),
    }


def sampling_recommendation(items: list[dict[str, Any]], sample_seed: int) -> dict[str, Any]:
    auto_allowed = sum(1 for item in items if not item["review_required_after_classification"])
    if auto_allowed <= 0:
        size = 0
    elif auto_allowed <= 100:
        size = min(10, auto_allowed)
    else:
        size = min(50, max(10, math.ceil(auto_allowed * 0.05)))
    return {
        "auto_allowed_count": auto_allowed,
        "recommended_sample_size": size,
        "sample_seed": sample_seed,
        "stratification": ["decision", "subsignal", "text_layer"],
    }


def pattern_decisions() -> dict[str, Any]:
    return {
        "schema_version": "pali_qa_pattern_decisions_v1",
        "source": "pilot_300_batch",
        "decisions": [
            {
                "rule_id": "allow_parenthetical_pali_after_korean_translation",
                "decision": "auto_accept_with_display_policy",
                "description": "Korean translation followed by parenthetical Pali lemma is allowed only when all Pali runs in the segment are covered and no independent human-review signal exists.",
                "requires_sampling_in_next_batch": True,
            },
            {
                "rule_id": "allow_commentarial_grammar_lemma_quote",
                "decision": "auto_accept_with_display_policy",
                "description": "Pali lemma quoted as object of explanation in atthakatha/tika is allowed only when all Pali runs are covered and no independent human-review signal exists.",
                "requires_sampling_in_next_batch": True,
            },
            {
                "rule_id": "strict_untranslated_pali_by_exclusion",
                "decision": "human_review",
                "description": "Only Pali runs not covered by allowed parenthetical, grammar quote, lemma discussion, proper-name, or terms rules remain human-needed.",
                "requires_sampling_in_next_batch": True,
            },
            {
                "rule_id": "grammar_uncertain_retained_for_human_review",
                "decision": "human_review",
                "description": "grammar_uncertain is never auto-accepted by deterministic classifier; hints may be used only for ordering.",
                "requires_sampling_in_next_batch": False,
            },
        ],
    }


def reclassified_review_queue(original: dict[str, Any], findings: dict[str, Any]) -> dict[str, Any]:
    items = findings["items"]
    human_needed = [item for item in items if item["review_required_after_classification"]]
    auto_allowed = [item for item in items if not item["review_required_after_classification"]]
    priority_counts = Counter(item["priority_after"] for item in human_needed)
    return {
        "schema_version": "pali_review_queue_reclassified_v1",
        "source_schema_version": original.get("schema_version"),
        "summary": {
            "input_item_count": len(original.get("items") or []),
            "human_needed_before": findings["summary_before"]["human_needed"],
            "human_needed_after": len(human_needed),
            "auto_allowed_after": len(auto_allowed),
            "priority_counts_after": dict(sorted(priority_counts.items())),
        },
        "items": items,
        "human_needed": human_needed,
        "auto_allowed": auto_allowed,
    }


def render_findings_markdown(findings: dict[str, Any]) -> str:
    strict_items = [
        item for item in findings["items"]
        if "possible_untranslated_pali_strict" in item["signals_after"]
    ]
    grammar_items = [
        item for item in findings["items"]
        if "grammar_uncertain" in item["signals_before"]
    ]
    lines = [
        "# Pāli QA Findings Classifier v1",
        "",
        "## Purpose",
        "",
        "This local deterministic classifier decomposes broad `contains_untranslated_pali` signals into narrower allowed-display and strict-review signals. It does not modify translations and does not certify translation correctness.",
        "",
        "Important caveat: auto-allowed items are flag-level false positives, not certified-correct translations. Translation correctness remains tracked separately through gold/holdout regression, sampling, oracle comparison where available, and later human/expert review.",
        "",
        "## Input Files",
        "",
        f"- review queue: `{findings['input']['review_queue']}`",
        f"- parsed salvaged: `{findings['input']['parsed_salvaged']}`",
        f"- review report: `{findings['input']['review_report']}`",
        "",
        "## Summary",
        "",
        f"- human-needed before: {findings['summary_before']['human_needed']}",
        f"- effective human-needed after: {findings['summary_after']['human_needed_effective']}",
        f"- auto_accept_with_display_policy: {findings['summary_after']['auto_accept_with_display_policy']}",
        f"- possible_untranslated_pali_strict: {findings['subsignal_counts']['possible_untranslated_pali_strict']}",
        f"- grammar_uncertain retained: {findings['subsignal_counts']['grammar_uncertain_retained']}",
        f"- grammar_uncertain auto-accepted: {findings['summary_after']['grammar_uncertain_auto_accepted']}",
        "",
        "## Run Coverage Summary",
        "",
        f"- total Pāli runs detected: {findings['run_coverage_summary']['total_pali_runs_detected']}",
        f"- covered Pāli runs: {findings['run_coverage_summary']['covered_pali_runs']}",
        f"- uncovered Pāli runs: {findings['run_coverage_summary']['uncovered_pali_runs']}",
        f"- run worst-case failures: {findings['run_coverage_summary']['run_worst_case_failures']}",
        f"- signal worst-case failures: {findings['run_coverage_summary']['signal_worst_case_failures']}",
        "",
        "## contains_untranslated_pali Reclassification",
        "",
        "contains_untranslated_pali was mostly false positive in the 300 pilot. Most cases are parenthetical Pāli or commentarial grammar lemma citations. Strict untranslated Pāli candidates should be the only untranslated-Pāli items that remain human-needed.",
        "",
    ]
    lines.extend(render_examples(findings, "pali_parenthetical_allowed", "Allowed Parenthetical Pāli Examples"))
    lines.extend(render_examples(findings, "pali_grammar_quote_allowed", "Allowed Grammar Quote Examples"))
    lines.extend(render_examples(findings, "pali_lemma_discussion_allowed", "Allowed Lemma Discussion Examples"))
    lines.extend(
        [
            "## possible_untranslated_pali_strict Candidates",
            "",
        ]
    )
    if strict_items:
        lines.extend(["| stable_segment_key | uncovered runs |", "| --- | --- |"])
        for item in strict_items:
            runs = ", ".join(run["run_text"] for run in item["uncovered_pali_runs"])
            lines.append(f"| `{item['stable_segment_key']}` | `{runs}` |")
        lines.append("")
    else:
        lines.extend(["None.", ""])
    lines.extend(
        [
            "## grammar_uncertain Retained",
            "",
        ]
    )
    if grammar_items:
        lines.extend(["| stable_segment_key | hint | reasons |", "| --- | --- | --- |"])
        for item in grammar_items:
            lines.append(
                f"| `{item['stable_segment_key']}` | `{item['grammar_uncertain_hint']}` | `{', '.join(item['grammar_uncertain_hint_reasons'])}` |"
            )
        lines.append("")
    else:
        lines.extend(["None.", ""])
    expert = [item for item in findings["items"] if item["expert_question_candidate"]]
    lines.extend(["## needs_expert_review Candidates", ""])
    if expert:
        lines.extend(["| stable_segment_key | reason |", "| --- | --- |"])
        for item in expert:
            lines.append(f"| `{item['stable_segment_key']}` | `{item['grammar_uncertain_hint']}` |")
        lines.append("")
    else:
        lines.extend(["None.", ""])
    lines.extend(
        [
            "## QA Rule Improvement Recommendation",
            "",
            "- Add deterministic allowed-Pāli rules into the main QA pipeline after this classifier is reviewed.",
            "- Keep grammar_uncertain in the human review queue; classifier hints are ordering aids only.",
            "- Add sampling guard for auto-allowed items in the next batch.",
            "",
            "## Sampling Guard",
            "",
            f"- auto-allowed count: {findings['sampling_recommendation']['auto_allowed_count']}",
            f"- recommended sample size: {findings['sampling_recommendation']['recommended_sample_size']}",
            f"- sample seed: {findings['sampling_recommendation']['sample_seed']}",
            "- stratification: decision, subsignal, text_layer",
            "",
            "## Next Step",
            "",
            "1. Review this classifier output before integrating allowed-Pāli rules into the main QA pipeline.",
            "2. Re-run 300 QA after integration and measure human-needed reduction.",
            "3. Add response_schema micro-smoke before the 1,000 pilot.",
            "4. Add second-model verifier only for unresolved/high-risk subset after deterministic false positives are reduced.",
            "",
        ]
    )
    return "\n".join(lines)


def render_examples(findings: dict[str, Any], rule: str, title: str) -> list[str]:
    rows = []
    for item in findings["items"]:
        matched = [run for run in item["pali_runs"] if run.get("coverage_rule") == rule]
        if not matched:
            continue
        rows.append((item, matched[0]))
        if len(rows) >= 5:
            break
    lines = [f"## {title}", ""]
    if not rows:
        lines.extend(["None.", ""])
        return lines
    lines.extend(["| stable_segment_key | run | context |", "| --- | --- | --- |"])
    for item, run in rows:
        lines.append(f"| `{item['stable_segment_key']}` | `{run['run_text']}` | {run['context_excerpt']} |")
    lines.append("")
    return lines


def run_to_dict(run: PaliRun) -> dict[str, Any]:
    return {
        "run_text": run.run_text,
        "location": run.location,
        "span": [run.span[0], run.span[1]],
        "context_excerpt": run.context_excerpt,
        "source": run.source,
        "in_parenthetical": run.in_parenthetical,
        "in_quote": run.in_quote,
    }


def roman_like(text: str) -> bool:
    return bool(re.search(rf"[{ROMAN_CHARS}]", text)) and not HANGUL_RE.search(text)


def context_excerpt(text: str, start: int, end: int, width: int = 60) -> str:
    return text[max(0, start - width): min(len(text), end + width)].replace("\n", " ")


def normalize_pali(text: str) -> str:
    return re.sub(r"[^A-Za-zāīūṅñṭḍṇḷṃĀĪŪṄÑṬḌṆḶṂ]+", "", text).lower()


def spans_overlap(a: tuple[int, int], b: tuple[int, int]) -> bool:
    return max(a[0], b[0]) < min(a[1], b[1])


def stable_sample_seed(keys: list[str]) -> int:
    joined = "\n".join(sorted(key for key in keys if key))
    return int(hashlib.sha256(joined.encode("utf-8")).hexdigest(), 16) % (2**32)


def dump_json(payload: Any) -> str:
    return json.dumps(payload, ensure_ascii=False, sort_keys=True, indent=2)

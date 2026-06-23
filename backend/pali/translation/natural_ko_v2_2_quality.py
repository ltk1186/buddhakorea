"""Objective v2.2 quality gates for the natural_ko D-arm smoke.

These checks are deterministic support signals only. They do not replace
operator readability review or Pali-capable scholar fidelity review.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Literal


BRACKET_SUPPLEMENT_PATTERNS = (
    "[뜻이다]",
    "[이다]",
    "[설해지지]",
    "[이것을]",
    "[마찬가지이다]",
    "[그러하다]",
)

KNOWN_INSERTION_CHECKS: dict[str, tuple[str, ...]] = {
    "abh02m.mul:a8d464d40a45": ("세속적인 일", "세속적"),
    "s0507a.att:f303db8f57dc": ("상처에 잿물", "상처에"),
    "s0101t.tik:14f01d855b04": ("삼보",),
    "s0513a3.att:8cd09caf90eb": ("선업이 청정", "청정하기 때문에"),
    "s0514m.mul:88650af1ca41": ("말을 쉬게", "기꺼이", "흔쾌히"),
}

KNOWN_OMISSION_CHECKS: dict[str, tuple[str, ...]] = {
    "s0508a1.att:8b9574445272": ("지나간", "지나가", "지나쳐", "지나쳐 버린"),
}

DOUBLE_NEGATION_RISK_CHECKS: dict[str, tuple[str, ...]] = {
    "abh03m11.mul:4ab6e93ef3c3": ("번뇌를 동반", "번뇌 동반", "번뇌를 수반", "번뇌 수반"),
}


@dataclass(frozen=True)
class GlossaryEntry:
    pali: str
    preferred_ko: list[str]
    allowed_alternatives: list[str]
    disallowed_renderings: list[str]
    notes: str
    lock_status: str = "locked"
    enforcement_level: Literal["hard", "advisory"] = "hard"
    confidence: Literal["high", "needs_expert_confirm"] = "high"


def glossary_lock_entries_v2_2() -> list[GlossaryEntry]:
    return [
        GlossaryEntry("sikkhā", ["공부지음"], ["학습", "훈련"], ["공부의 만들어짐"], "Project convention allows 공부지음; do not treat it as broken Korean."),
        GlossaryEntry("adhisīlasikkhā", ["증상계의 공부지음", "증상계학"], [], [], "Context determines analytic vs compact rendering."),
        GlossaryEntry("adhicittasikkhā", ["증상심의 공부지음", "증상심학"], [], [], "Context determines analytic vs compact rendering."),
        GlossaryEntry("paññuttara", ["통찰지를 으뜸으로 삼는", "통찰지를 최상으로 삼는"], [], ["통찰지를 위로"], "Avoid awkward morphological calque."),
        GlossaryEntry("ādibhāva", ["처음이 됨", "시작이 됨", "시작으로서의 성격"], [], ["처음-상태"], "Avoid hyphenated calque."),
        GlossaryEntry("cāritta", ["작지", "해야 할 것을 실천하는 계행"], [], [], "Vinaya/commentarial technical term."),
        GlossaryEntry("vāritta", ["지지", "하지 말아야 할 것을 금하는 계행"], [], [], "Vinaya/commentarial technical term."),
        GlossaryEntry("yama", ["금계"], [], ["맥락 없는 금계"], "Needs project/expert confirmation before full glossary promotion.", lock_status="needs_expert_confirm", enforcement_level="advisory", confidence="needs_expert_confirm"),
        GlossaryEntry("niyama", ["권계"], [], ["맥락 없는 권계"], "Needs project/expert confirmation before full glossary promotion.", lock_status="needs_expert_confirm", enforcement_level="advisory", confidence="needs_expert_confirm"),
        GlossaryEntry("āsevati / āsevantassa", ["실천하는", "거듭 익히는", "닦아 익히는"], ["의지하는"], ["맥락 없는 의지하는"], "Use 의지하다 only when reliance is genuinely meant."),
        GlossaryEntry("kammārāmatā", ["일을 즐김"], [], ["세속적인 일을 즐김"], "Do not add 세속적인 unless source/context explicitly supports it."),
        GlossaryEntry("khārena paripphositvā", ["잿물을 뿌리고서"], [], ["상처에 잿물", "상처에 잿물을 뿌리고서"], "Do not add 상처 unless source/context says wound."),
        GlossaryEntry("accenti", ["지나간다", "지나쳐 버린다"], [], [], "Predicate must not be omitted."),
        GlossaryEntry("pahātabbahetuka", ["버려져야 할 원인을 가진", "버려져야 할 원인을 가지지 않은"], [], [], "Preserve negation scope."),
        GlossaryEntry("nanabhāvanāya / nasaraṇaṃ-type double negatives", ["원인/닦음/귀의 관련 부정 범위를 보존"], [], ["번뇌를 동반", "번뇌를 동반하지 않으며"], "Paṭṭhāna/double-negation risk; mark uncertainty if unsure."),
        GlossaryEntry("appavatti", ["맥락에 따라 비전전/일어나지 않음/작용하지 않음"], [], ["맥락 없는 비전전"], "Context-sensitive; do not force obscure calque.", lock_status="needs_expert_confirm", enforcement_level="advisory", confidence="needs_expert_confirm"),
        GlossaryEntry("otaraṇā", ["끌어들여 해석함", "적용하여 해석함"], ["들어감"], ["맥락 없는 들어감"], "Context-sensitive commentarial function.", lock_status="needs_expert_confirm", enforcement_level="advisory", confidence="needs_expert_confirm"),
        GlossaryEntry("musā", ["거짓"], [], [], "Stable basic term."),
        GlossaryEntry("musāvāda", ["거짓말"], [], [], "Stable basic term."),
        GlossaryEntry("cetanā", ["의도"], [], [], "Stable Abhidhamma/Vinaya term."),
        GlossaryEntry("viññatti", ["암시", "표의", "의사표시"], [], ["맥락 없는 표의"], "Needs context and project convention confirmation.", lock_status="needs_expert_confirm", enforcement_level="advisory", confidence="needs_expert_confirm"),
        GlossaryEntry("virati", ["절제", "삼감"], [], [], "Stable ethical term."),
        GlossaryEntry("appanā", ["본삼매"], [], [], "Project convention term."),
        GlossaryEntry("kalyāṇamitta", ["훌륭한 친구", "선지식"], [], ["맥락 없는 선지식"], "Project convention/context dependent.", lock_status="needs_expert_confirm", enforcement_level="advisory", confidence="needs_expert_confirm"),
        GlossaryEntry("ājīvika", ["생활수단", "생계", "아지비카"], [], ["맥락 없는 아지비카"], "Sect vs livelihood is an expert crux.", lock_status="needs_expert_confirm", enforcement_level="advisory", confidence="needs_expert_confirm"),
        GlossaryEntry("āpatti", ["범죄", "죄를 범함"], [], [], "Vinaya context."),
        GlossaryEntry("anāpatti", ["범죄가 성립하지 않음", "무범"], [], [], "Vinaya context."),
    ]


def glossary_lock_payload_v2_2() -> dict[str, Any]:
    return {
        "schema_version": "natural_ko_v2_2_glossary_lock_v1",
        "status": "d_arm_test_lock_not_project_glossary",
        "entries": [
            {
                "pali": entry.pali,
                "preferred_ko": entry.preferred_ko,
                "allowed_alternatives": entry.allowed_alternatives,
                "disallowed_renderings": entry.disallowed_renderings,
                "notes": entry.notes,
                "lock_status": entry.lock_status,
                "enforcement_level": entry.enforcement_level,
                "confidence": entry.confidence,
            }
            for entry in glossary_lock_entries_v2_2()
        ],
    }


def output_text(item: dict[str, Any]) -> str:
    return "\n".join(
        str(item.get(field) or "")
        for field in ("literal_ko", "natural_ko")
    )


def has_key_fragment(stable_segment_key: str, fragment: str) -> bool:
    return fragment in stable_segment_key


def detect_bracket_violations(item: dict[str, Any]) -> list[str]:
    text = output_text(item)
    violations = [pattern for pattern in BRACKET_SUPPLEMENT_PATTERNS if pattern in text]
    if "[" in text or "]" in text:
        violations.append("square_bracket_present")
    return sorted(set(violations))


def detect_known_unsupported_insertions(item: dict[str, Any]) -> list[str]:
    key = str(item.get("stable_segment_key") or "")
    text = output_text(item)
    violations: list[str] = []
    for fragment, phrases in KNOWN_INSERTION_CHECKS.items():
        if has_key_fragment(key, fragment):
            violations.extend(phrase for phrase in phrases if phrase in text)
    return sorted(set(violations))


def detect_known_omissions(item: dict[str, Any]) -> list[str]:
    key = str(item.get("stable_segment_key") or "")
    text = str(item.get("natural_ko") or "")
    omissions: list[str] = []
    for fragment, required_phrases in KNOWN_OMISSION_CHECKS.items():
        if has_key_fragment(key, fragment) and not any(phrase in text for phrase in required_phrases):
            omissions.append("missing_accenti_predicate_in_natural_ko")
    return omissions


def detect_negation_scope_risks(item: dict[str, Any]) -> list[str]:
    key = str(item.get("stable_segment_key") or "")
    text = output_text(item)
    risks: list[str] = []
    for fragment, phrases in DOUBLE_NEGATION_RISK_CHECKS.items():
        if has_key_fragment(key, fragment):
            risks.extend(phrase for phrase in phrases if phrase in text)
    return sorted(set(risks))


def detect_glossary_violations(item: dict[str, Any]) -> list[str]:
    text = output_text(item)
    violations: list[str] = []
    for entry in glossary_lock_entries_v2_2():
        if entry.enforcement_level != "hard":
            continue
        for phrase in entry.disallowed_renderings:
            if phrase and phrase in text:
                violations.append(f"{entry.pali}:{phrase}")
    return sorted(set(violations))


def detect_advisory_glossary_warnings(item: dict[str, Any]) -> list[str]:
    text = output_text(item)
    warnings: list[str] = []
    for entry in glossary_lock_entries_v2_2():
        if entry.enforcement_level != "advisory":
            continue
        for phrase in entry.disallowed_renderings:
            if phrase and phrase in text:
                warnings.append(f"{entry.pali}:{phrase}")
    return sorted(set(warnings))


def evaluate_d_arm_item(item: dict[str, Any]) -> dict[str, Any]:
    bracket = detect_bracket_violations(item)
    insertions = detect_known_unsupported_insertions(item)
    omissions = detect_known_omissions(item)
    negation = detect_negation_scope_risks(item)
    glossary = detect_glossary_violations(item)
    advisory_glossary = detect_advisory_glossary_warnings(item)
    return {
        "stable_segment_key": item.get("stable_segment_key"),
        "bracket_violation": bool(bracket),
        "bracket_violation_details": bracket,
        "unsupported_insertion": bool(insertions),
        "unsupported_insertion_details": insertions,
        "known_content_omission": bool(omissions),
        "known_content_omission_details": omissions,
        "negation_scope_risk": bool(negation),
        "negation_scope_risk_details": negation,
        "glossary_violation": bool(glossary),
        "glossary_violation_details": glossary,
        "advisory_glossary_warning": bool(advisory_glossary),
        "advisory_glossary_warning_details": advisory_glossary,
        "general_content_omission_status": "pending_scholar_review",
    }


def summarize_d_arm_gates(items: list[dict[str, Any]]) -> dict[str, Any]:
    checks = [evaluate_d_arm_item(item) for item in items]
    return {
        "schema_version": "natural_ko_v2_2_objective_gate_summary_v1",
        "items_checked": len(items),
        "bracket_violations": sum(check["bracket_violation"] for check in checks),
        "unsupported_insertions": sum(check["unsupported_insertion"] for check in checks),
        "known_content_omissions": sum(check["known_content_omission"] for check in checks),
        "negation_scope_risks": sum(check["negation_scope_risk"] for check in checks),
        "glossary_violations": sum(check["glossary_violation"] for check in checks),
        "advisory_glossary_warnings": sum(check["advisory_glossary_warning"] for check in checks),
        "general_content_omission_status": "pending_scholar_review",
        "items": checks,
    }

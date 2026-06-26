"""Objective v2.2 quality gates for the natural_ko D-arm smoke.

These checks are deterministic support signals only. They do not replace
operator readability review or Pali-capable scholar fidelity review.
"""

from __future__ import annotations

import re
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
    trigger_patterns: tuple[str, ...] = ()
    match_policy: Literal["term_scoped", "global_phrase"] = "term_scoped"


def glossary_lock_entries_v2_2() -> list[GlossaryEntry]:
    return [
        GlossaryEntry("sikkhā", ["공부지음"], ["학습", "훈련"], ["공부의 만들어짐"], "Project convention allows 공부지음; do not treat it as broken Korean.", trigger_patterns=("sikkh", "sikkhā")),
        GlossaryEntry("adhisīlasikkhā", ["증상계의 공부지음", "증상계학"], [], [], "Context determines analytic vs compact rendering.", trigger_patterns=("adhisīlasikkh", "adhisīlasikkhā")),
        GlossaryEntry("adhicittasikkhā", ["증상심의 공부지음", "증상심학"], [], [], "Context determines analytic vs compact rendering.", trigger_patterns=("adhicittasikkh", "adhicittasikkhā")),
        GlossaryEntry("sati", ["마음챙김"], ["기억", "수념"], [], "Use project convention; in anussati/saraṇa contexts, inspect context rather than forcing 마음챙김 mechanically.", trigger_patterns=("sati",)),
        GlossaryEntry("viññāṇa", ["알음알이"], ["의식"], [], "Prefer 알음알이 in literal_ko and terms; avoid Yogācāra-style expansion.", trigger_patterns=("viññā", "viññāṇa")),
        GlossaryEntry("paññā", ["통찰지"], ["지혜"], [], "Prefer 통찰지 in literal_ko and terms; do not expand into later 반야/공사상 meanings.", trigger_patterns=("paññ", "paññā")),
        GlossaryEntry("āyatana / saḷāyatana", ["감각장소", "여섯 감각장소"], [], [], "Use the established sense-base convention.", trigger_patterns=("āyatana", "āyatan", "saḷāyatana", "saḷāyatan")),
        GlossaryEntry("phassa", ["감각접촉"], [], [], "Stable dependent-origination term.", trigger_patterns=("phassa", "phass")),
        GlossaryEntry("nibbidā", ["염오"], [], [], "Stable project rendering.", trigger_patterns=("nibbid", "nibbidā")),
        GlossaryEntry("virāga", ["탐욕의 빛바램"], [], [], "Stable project rendering.", trigger_patterns=("virāga", "virāg")),
        GlossaryEntry("saṅkhāra", ["형성된 것들", "심리현상들", "의도적 행위들"], [], [], "Choose by context: aggregates, dependent origination, or conditioned phenomena generally.", trigger_patterns=("saṅkhār", "saṅkhāra")),
        GlossaryEntry("nibbāna", ["열반"], [], ["불성", "진여", "본래면목"], "Do not layer later doctrinal meanings onto nibbāna.", trigger_patterns=("nibbān", "nibbāna")),
        GlossaryEntry("khandha", ["무더기"], ["오온"], ["무리"], "Default is 무더기; natural_ko may support first occurrence with 오온 where helpful.", trigger_patterns=("khandha", "khandh")),
        GlossaryEntry("manasikāra", ["마음에 잡도리함"], ["여리작의", "비여리작의"], [], "yoniso/ayoniso manasikāra use the project terms 여리작의/비여리작의.", trigger_patterns=("manasikār", "manasikāra")),
        GlossaryEntry("uppala / paduma", ["수련", "연꽃"], [], [], "Do not collapse uppala and paduma into the same Korean term when the distinction matters.", trigger_patterns=("uppala", "uppal", "paduma", "padum")),
        GlossaryEntry("dhīra / paṇḍita", ["슬기로운 이", "현자"], [], [], "Do not collapse the two terms into one repeated rendering when the distinction matters.", trigger_patterns=("dhīra", "dhīr", "paṇḍita", "paṇḍit")),
        GlossaryEntry("khanti", ["감내", "참음", "인욕"], ["수순", "받아들임"], [], "In anulomika khanti or truth-acceptance contexts, consider 수순/받아들임 and mark uncertainty if unclear.", trigger_patterns=("khanti", "khant")),
        GlossaryEntry("paññuttara", ["통찰지를 으뜸으로 삼는", "통찰지를 최상으로 삼는"], [], ["통찰지를 위로"], "Avoid awkward morphological calque.", trigger_patterns=("paññuttara", "paññuttar")),
        GlossaryEntry("ādibhāva", ["처음이 됨", "시작이 됨", "시작으로서의 성격"], [], ["처음-상태"], "Avoid hyphenated calque.", trigger_patterns=("ādibhāva", "ādibhāv")),
        GlossaryEntry("cāritta", ["작지", "해야 할 것을 실천하는 계행"], [], [], "Vinaya/commentarial technical term.", trigger_patterns=("cāritta", "cāritt")),
        GlossaryEntry("vāritta", ["지지", "하지 말아야 할 것을 금하는 계행"], [], [], "Vinaya/commentarial technical term.", trigger_patterns=("vāritta", "vāritt")),
        GlossaryEntry("yama", ["금계"], [], ["맥락 없는 금계"], "Needs project/expert confirmation before full glossary promotion.", lock_status="needs_expert_confirm", enforcement_level="advisory", confidence="needs_expert_confirm", trigger_patterns=("yama", "yam")),
        GlossaryEntry("niyama", ["권계"], [], ["맥락 없는 권계"], "Needs project/expert confirmation before full glossary promotion.", lock_status="needs_expert_confirm", enforcement_level="advisory", confidence="needs_expert_confirm", trigger_patterns=("niyama", "niyam")),
        GlossaryEntry("āsevati / āsevantassa", ["실천하는", "거듭 익히는", "닦아 익히는"], ["의지하는"], ["맥락 없는 의지하는"], "Use 의지하다 only when reliance is genuinely meant.", trigger_patterns=("āsev", "āsevati", "āsevant")),
        GlossaryEntry("kammārāmatā", ["일을 즐김"], [], ["세속적인 일을 즐김"], "Do not add 세속적인 unless source/context explicitly supports it.", trigger_patterns=("kammārāmat", "kammārāmatā")),
        GlossaryEntry("khārena paripphositvā", ["잿물을 뿌리고서"], [], ["상처에 잿물", "상처에 잿물을 뿌리고서"], "Do not add 상처 unless source/context says wound.", trigger_patterns=("khārena", "khāra", "paripphositvā", "paripphosit")),
        GlossaryEntry("accenti", ["지나간다", "지나쳐 버린다"], [], [], "Predicate must not be omitted.", trigger_patterns=("accenti",)),
        GlossaryEntry("pahātabbahetuka", ["버려져야 할 원인을 가진", "버려져야 할 원인을 가지지 않은"], [], [], "Preserve negation scope.", trigger_patterns=("pahātabbahetuka", "pahātabbahetuk")),
        GlossaryEntry("nanabhāvanāya / nasaraṇaṃ-type double negatives", ["원인/닦음/귀의 관련 부정 범위를 보존"], [], ["번뇌를 동반", "번뇌를 동반하지 않으며"], "Paṭṭhāna/double-negation risk; mark uncertainty if unsure.", trigger_patterns=("nanabhāvanāya", "nanabhāvan", "nasaraṇa", "nasaraṇaṃ", "pahātabbahetuk")),
        GlossaryEntry("appavatti", ["맥락에 따라 비전전/일어나지 않음/작용하지 않음"], [], ["맥락 없는 비전전"], "Context-sensitive; do not force obscure calque.", lock_status="needs_expert_confirm", enforcement_level="advisory", confidence="needs_expert_confirm", trigger_patterns=("appavatti", "appavatt")),
        GlossaryEntry("otaraṇā", ["끌어들여 해석함", "적용하여 해석함"], ["들어감"], ["맥락 없는 들어감"], "Context-sensitive commentarial function.", lock_status="needs_expert_confirm", enforcement_level="advisory", confidence="needs_expert_confirm", trigger_patterns=("otaraṇ", "otaraṇā")),
        GlossaryEntry("musā", ["거짓"], [], [], "Stable basic term.", trigger_patterns=("musā", "musa")),
        GlossaryEntry("musāvāda", ["거짓말"], [], [], "Stable basic term.", trigger_patterns=("musāvād", "musāvāda")),
        GlossaryEntry("cetanā", ["의도"], [], [], "Stable Abhidhamma/Vinaya term.", trigger_patterns=("cetanā", "cetan")),
        GlossaryEntry("viññatti", ["암시", "표의", "의사표시"], [], ["맥락 없는 표의"], "Needs context and project convention confirmation.", lock_status="needs_expert_confirm", enforcement_level="advisory", confidence="needs_expert_confirm", trigger_patterns=("viññatti", "viññatt")),
        GlossaryEntry("virati", ["절제", "삼감"], [], [], "Stable ethical term.", trigger_patterns=("virati", "virat")),
        GlossaryEntry("appanā", ["본삼매"], [], [], "Project convention term.", trigger_patterns=("appanā", "appan")),
        GlossaryEntry("kalyāṇamitta", ["훌륭한 친구", "선지식"], [], ["맥락 없는 선지식"], "Project convention/context dependent.", lock_status="needs_expert_confirm", enforcement_level="advisory", confidence="needs_expert_confirm", trigger_patterns=("kalyāṇamitta", "kalyāṇamitt")),
        GlossaryEntry("ājīvika", ["생활수단", "생계", "아지비카"], [], ["맥락 없는 아지비카"], "Sect vs livelihood is an expert crux.", lock_status="needs_expert_confirm", enforcement_level="advisory", confidence="needs_expert_confirm", trigger_patterns=("ājīvika", "ājīvik", "ājīvaka", "ājīvak")),
        GlossaryEntry("āpatti", ["범죄", "죄를 범함"], [], [], "Vinaya context.", trigger_patterns=("āpatti", "āpatt")),
        GlossaryEntry("anāpatti", ["범죄가 성립하지 않음", "무범"], [], [], "Vinaya context.", trigger_patterns=("anāpatti", "anāpatt")),
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
                "trigger_patterns": list(entry.trigger_patterns),
                "match_policy": entry.match_policy,
            }
            for entry in glossary_lock_entries_v2_2()
        ],
    }


def output_text(item: dict[str, Any]) -> str:
    return "\n".join(
        str(item.get(field) or "")
        for field in ("literal_ko", "natural_ko")
    )


def source_or_terms_text(item: dict[str, Any]) -> str:
    parts = [
        str(item.get("original_text") or ""),
        str(item.get("source_text") or ""),
    ]
    for term in item.get("terms") or []:
        if isinstance(term, dict):
            parts.append(str(term.get("pali") or ""))
    for field in ("grammar_notes", "doctrinal_notes", "uncertainties"):
        value = item.get(field) or []
        if isinstance(value, list):
            parts.extend(str(part) for part in value)
        elif isinstance(value, str):
            parts.append(value)
    return "\n".join(parts).casefold()


def glossary_entry_is_triggered(entry: GlossaryEntry, item: dict[str, Any]) -> bool:
    if entry.match_policy == "global_phrase":
        return True
    source_text = source_or_terms_text(item)
    patterns = entry.trigger_patterns or (entry.pali.casefold(),)
    return any(pattern.casefold() in source_text for pattern in patterns if pattern)


def has_key_fragment(stable_segment_key: str, fragment: str) -> bool:
    return fragment in stable_segment_key


def detect_bracket_violations(item: dict[str, Any]) -> list[str]:
    text = output_text(item)
    violations = [pattern for pattern in BRACKET_SUPPLEMENT_PATTERNS if pattern in text]
    violations.extend(re.findall(r"\[[^\[\]]+\]", text))
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
        if not glossary_entry_is_triggered(entry, item):
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
        if not glossary_entry_is_triggered(entry, item):
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

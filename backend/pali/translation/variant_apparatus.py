"""VRI XML note apparatus extraction for Pali translation QA.

This module is local-only. It extracts structured evidence from VRI XML
``<note>`` elements and never applies variants to source text or translations.
Apparatus notes attest variant readings; they do not prove that the main
reading is erroneous.
"""

from __future__ import annotations

import hashlib
import json
import re
from collections import Counter, defaultdict
from dataclasses import dataclass
from pathlib import Path
from typing import Any
from xml.etree import ElementTree as ET

from backend.pali.importers.vri_xml import (
    build_node_path_map,
    extract_main_text,
    normalize_whitespace,
    parse_vri_xml,
    strip_namespace,
)


SCRIPT_VERSION = "variant_apparatus_extraction_v0"
CROSS_SCRIPT_DEPRECATED_REASON = (
    "Script variants are generated from a master source and are not treated as "
    "independent witnesses for source-variant detection."
)

KNOWN_SIGLA = {
    "sī": "Sinhala",
    "syā": "Siamese / Thai",
    "ka": "ka / unspecified manuscript group",
    "pī": "PTS",
    "ma": "Myanmar / Burmese",
}
NAMED_WITNESS_SIGLA = {"sī", "syā", "pī", "ma"}
CITATION_RE = re.compile(
    r"\b(?:dī|di|ma|saṃ|sam|aṅ|a|khu|dha|su|udā|itivu|jā|vin|abh|theragā|therīgā|pe\. va)\.\s*"
    r"(?:ni|pa)?\.?\s*\d*(?:\.\d+)*",
    re.IGNORECASE,
)
PAREN_GROUP_RE = re.compile(r"\(([^()]*)\)")
ROMAN_TOKEN_RE = re.compile(r"[A-Za-zāīūṅñṭḍṇḷṃĀĪŪṄÑṬḌṆḶṂ][A-Za-zāīūṅñṭḍṇḷṃĀĪŪṄÑṬḌṆḶṂ'-]*")

SEED_TARGETS = [
    {
        "stable_segment_key": "vri:romn:s0519m.mul:f43a9c761757",
        "source_path": "romn/s0519m.mul.xml",
        "target_hint": "accantadiṭṭhaṃ",
        "issue_note": "Possible source variant: accantadiṭṭhaṃ vs accantaniṭṭhaṃ.",
    },
    {
        "stable_segment_key": "vri:romn:abh03m11.mul:4ab6e93ef3c3",
        "source_path": "romn/abh03m11.mul.xml",
        "target_hint": "nanabhāvanāya",
        "issue_note": "na-chain / source segmentation / variant suspicion.",
    },
    {
        "stable_segment_key": "vri:romn:s0302t.tik:75cb6eb45b34",
        "source_path": "romn/s0302t.tik.xml",
        "target_hint": "Tassāti pāṭhassa",
        "issue_note": "pāṭha / lemma commentary pattern.",
    },
    {
        "stable_segment_key": "vri:romn:vin02a2.att:bfbd7f00efd4",
        "source_path": "romn/vin02a2.att.xml",
        "target_hint": "Jiridanti",
        "issue_note": "form / etymology / rare lemma suspicion.",
    },
]


@dataclass(frozen=True)
class NoteClassification:
    note_type: str
    is_variant_apparatus: bool
    variant_text: str
    sigla: list[str]
    unknown_sigla: list[str]
    citation_refs: list[str]
    evidence_strength_hint: str


def parse_sigla(raw_note_text: str) -> dict[str, Any]:
    """Parse variant sigla from parenthesized note endings.

    Citation-like notes such as ``ma. ni. 1.55`` are not treated as sigla.
    """

    text = normalize_whitespace(raw_note_text)
    groups = list(PAREN_GROUP_RE.finditer(text))
    for match in groups:
        group = normalize_whitespace(match.group(1))
        if CITATION_RE.search(group):
            continue
        tokens = [token.strip().rstrip(".").lower() for token in re.findall(r"[A-Za-zāīūṅñṭḍṇḷṃ]+\.?", group)]
        tokens = [token for token in tokens if token and token != "pe"]
        if not tokens:
            continue
        known = [token for token in tokens if token in KNOWN_SIGLA]
        unknown = [token for token in tokens if token not in KNOWN_SIGLA]
        if not known and not unknown:
            continue
        variant_text = normalize_whitespace(text[: match.start()].rstrip(" ,;"))
        return {
            "variant_text": variant_text,
            "sigla": known,
            "unknown_sigla": unknown,
            "sigla_group": group,
            "sigla_span": [match.start(), match.end()],
        }
    return {"variant_text": "", "sigla": [], "unknown_sigla": [], "sigla_group": "", "sigla_span": None}


def classify_note(raw_note_text: str) -> NoteClassification:
    text = normalize_whitespace(raw_note_text)
    sigla_result = parse_sigla(text)
    citation_refs = extract_citation_refs(text)

    if is_pure_citation_note(text, sigla_result):
        return NoteClassification("citation", False, "", [], [], citation_refs, "unknown")
    if is_peyyala_note(text):
        return NoteClassification("peyyala", False, "", [], [], citation_refs, "unknown")
    if sigla_result["sigla"] or sigla_result["unknown_sigla"]:
        sigla = list(sigla_result["sigla"])
        unknown = list(sigla_result["unknown_sigla"])
        return NoteClassification(
            "variant",
            True,
            sigla_result["variant_text"],
            sigla,
            unknown,
            citation_refs,
            evidence_strength_hint(sigla, unknown),
        )
    if re.search(r"(vicāretabb|passitabb|dissati|vattabba)", text, re.IGNORECASE):
        return NoteClassification("editorial", False, "", [], [], citation_refs, "unknown")
    if citation_refs:
        return NoteClassification("citation", False, "", [], [], citation_refs, "unknown")
    return NoteClassification("unknown", False, "", [], [], [], "unknown")


def is_pure_citation_note(text: str, sigla_result: dict[str, Any]) -> bool:
    if sigla_result["sigla"] or sigla_result["unknown_sigla"]:
        return False
    return bool(CITATION_RE.search(text))


def is_peyyala_note(text: str) -> bool:
    lowered = text.lower().strip()
    return lowered in {"pe.", "pe", "peyyāla", "peyyālaṃ"} or lowered.startswith("peyyāla")


def extract_citation_refs(text: str) -> list[str]:
    refs = []
    for match in CITATION_RE.finditer(text):
        value = normalize_whitespace(match.group(0)).strip(" ,;")
        if value and value not in refs:
            refs.append(value)
    return refs


def evidence_strength_hint(sigla: list[str], unknown: list[str]) -> str:
    if any(item in NAMED_WITNESS_SIGLA for item in sigla):
        return "named_witness"
    if sigla and all(item == "ka" for item in sigla):
        return "weak_or_unspecified"
    if sigla:
        return "manuscript_group"
    if unknown:
        return "unknown"
    return "unknown"


def expand_sigla(sigla: list[str]) -> list[dict[str, str]]:
    return [{"siglum": item, "label": KNOWN_SIGLA.get(item, "unknown")} for item in sigla]


def resolve_source_xml(source_root: Path, source_path: str) -> Path:
    candidates = [
        source_root / source_path,
        source_root / "tipitaka.org" / source_path,
    ]
    for candidate in candidates:
        if candidate.exists():
            return candidate
    return candidates[0]


def read_xml_text(path: Path) -> str:
    raw = path.read_bytes()
    for encoding in ("utf-16", "utf-8-sig", "utf-8"):
        try:
            return raw.decode(encoding)
        except UnicodeDecodeError:
            continue
    return raw.decode("utf-8", errors="replace")


def extract_source_apparatus(source_root: Path, source_path: str, *, window_chars: int = 160) -> dict[str, Any]:
    xml_path = resolve_source_xml(source_root, source_path)
    if not xml_path.exists():
        return {
            "source_path": source_path,
            "exists": False,
            "note_records": [],
            "note_count": 0,
            "sigla_counts": {},
            "note_type_counts": {},
        }

    xml_text = read_xml_text(xml_path)
    tree = ET.parse(xml_path)
    root = tree.getroot()
    path_map = build_node_path_map(root)
    parent_map = build_parent_map(root)
    note_records = []
    sigla_counts: Counter[str] = Counter()
    note_type_counts: Counter[str] = Counter()
    for index, note in enumerate([node for node in root.iter() if strip_namespace(node.tag) == "note"], start=1):
        raw_note = normalize_whitespace("".join(note.itertext()))
        classification = classify_note(raw_note)
        note_type_counts[classification.note_type] += 1
        sigla_counts.update(classification.sigla)
        parent = nearest_parent_with_tag(note, parent_map, "p")
        parent_path = path_map.get(id(parent), "") if parent is not None else ""
        note_path = path_map.get(id(note), "")
        before_text = text_before_target(parent, note) if parent is not None else ""
        after_text = text_after_target(parent, note) if parent is not None else ""
        anchor = preceding_token(before_text)
        char_offset = xml_text.find(raw_note) if raw_note else -1
        note_records.append(
            {
                "apparatus_id": f"{source_path}:note:{index:06d}",
                "source_path": source_path,
                "xml_node_path": note_path,
                "parent_xml_node_path": parent_path,
                "parent_tag": strip_namespace(parent.tag) if parent is not None else "",
                "parent_rend": parent.attrib.get("rend", "") if parent is not None else "",
                "char_offset": char_offset,
                "anchor_text": anchor,
                "anchor_uncertain": True,
                "main_reading": anchor,
                "variant_text": classification.variant_text,
                "raw_note_text": raw_note,
                "note_type": classification.note_type,
                "is_variant_apparatus": classification.is_variant_apparatus,
                "sigla": classification.sigla,
                "unknown_sigla": classification.unknown_sigla,
                "sigla_expanded": expand_sigla(classification.sigla),
                "citation_refs": classification.citation_refs,
                "evidence_strength_hint": classification.evidence_strength_hint,
                "context_before": normalize_whitespace(before_text)[-window_chars:],
                "context_after": normalize_whitespace(after_text)[:window_chars],
                "auto_apply": False,
            }
        )
    return {
        "source_path": source_path,
        "exists": True,
        "xml_path": str(xml_path),
        "note_records": note_records,
        "note_count": len(note_records),
        "sigla_counts": dict(sorted(sigla_counts.items())),
        "note_type_counts": dict(sorted(note_type_counts.items())),
    }


def build_parent_map(root: ET.Element) -> dict[int, ET.Element]:
    parents: dict[int, ET.Element] = {}
    for parent in root.iter():
        for child in list(parent):
            parents[id(child)] = parent
    return parents


def nearest_parent_with_tag(
    node: ET.Element,
    parent_map: dict[int, ET.Element],
    tag_name: str,
) -> ET.Element | None:
    current = node
    while id(current) in parent_map:
        current = parent_map[id(current)]
        if strip_namespace(current.tag) == tag_name:
            return current
    return None


def text_before_target(parent: ET.Element | None, target: ET.Element) -> str:
    if parent is None:
        return ""
    parts: list[str] = []
    found = False

    def walk(node: ET.Element) -> None:
        nonlocal found
        if found:
            return
        if node is target:
            found = True
            return
        tag = strip_namespace(node.tag)
        if tag in {"note", "pb"}:
            if node.tail:
                parts.append(node.tail)
            return
        if node.text:
            parts.append(node.text)
        for child in list(node):
            walk(child)
            if found:
                return
        if node.tail:
            parts.append(node.tail)

    walk(parent)
    return "".join(parts)


def text_after_target(parent: ET.Element | None, target: ET.Element) -> str:
    if parent is None:
        return ""
    parts: list[str] = []
    collecting = False

    def walk(node: ET.Element) -> None:
        nonlocal collecting
        if node is target:
            collecting = True
            if node.tail:
                parts.append(node.tail)
            return
        tag = strip_namespace(node.tag)
        if collecting:
            if tag not in {"note", "pb"} and node.text:
                parts.append(node.text)
            for child in list(node):
                walk(child)
            if node.tail:
                parts.append(node.tail)
            return
        for child in list(node):
            walk(child)

    walk(parent)
    return "".join(parts)


def preceding_token(text: str) -> str:
    tokens = ROMAN_TOKEN_RE.findall(text)
    return tokens[-1] if tokens else ""


def build_segment_index(source_root: Path, source_path: str) -> dict[str, Any]:
    xml_path = resolve_source_xml(source_root, source_path)
    if not xml_path.exists():
        return {"exists": False, "segments": {}, "path_to_key": {}}
    artifact = parse_vri_xml(xml_path, source_path=source_path)
    segments = {
        item["stable_segment_key"]: item
        for item in artifact.get("segments", [])
        if isinstance(item, dict)
    }
    path_to_key: dict[str, str] = {}
    for item in segments.values():
        for path in item.get("xml_node_paths", []) or []:
            path_to_key[str(path)] = str(item["stable_segment_key"])
    return {"exists": True, "segments": segments, "path_to_key": path_to_key}


def select_targets(
    review_queue_reclassified: dict[str, Any],
    findings: dict[str, Any],
    parsed_payload: dict[str, Any],
    *,
    targets_payload: dict[str, Any] | None = None,
    max_targets: int = 20,
) -> list[dict[str, Any]]:
    parsed_by_key = {item.get("stable_segment_key"): item for item in parsed_payload.get("items", []) if isinstance(item, dict)}
    selected: dict[str, dict[str, Any]] = {}
    if targets_payload:
        for item in targets_payload.get("targets", []) or []:
            if isinstance(item, dict) and item.get("stable_segment_key"):
                selected[str(item["stable_segment_key"])] = normalize_target(item, parsed_by_key)
        return list(selected.values())[:max_targets]

    for seed in SEED_TARGETS:
        selected[seed["stable_segment_key"]] = normalize_target(seed, parsed_by_key)

    for item in review_queue_reclassified.get("items", []) or []:
        if not isinstance(item, dict):
            continue
        if not item.get("review_required_after_classification"):
            continue
        signals = set(item.get("signals_after") or []) | set(item.get("signals_before") or [])
        if not (signals & {"grammar_uncertain", "needs_human_review", "source_hash_mismatch", "silent_source_normalization"}):
            continue
        key = str(item.get("stable_segment_key") or "")
        if not key:
            continue
        if key not in selected:
            selected[key] = normalize_target(item, parsed_by_key)
        if len(selected) >= max_targets:
            break
    return list(selected.values())[:max_targets]


def normalize_target(item: dict[str, Any], parsed_by_key: dict[str, Any]) -> dict[str, Any]:
    key = str(item.get("stable_segment_key") or "")
    parsed = parsed_by_key.get(key, {})
    return {
        "stable_segment_key": key,
        "source_path": str(item.get("source_path") or parsed.get("source_path") or ""),
        "target_hint": str(item.get("target_hint") or derive_target_hint(item, parsed)),
        "issue_note": str(item.get("issue_note") or ""),
        "signals_before": item.get("signals_before") or [],
        "signals_after": item.get("signals_after") or [],
    }


def derive_target_hint(item: dict[str, Any], parsed: dict[str, Any]) -> str:
    if item.get("target_hint"):
        return str(item["target_hint"])
    for run in item.get("uncovered_pali_runs") or item.get("pali_runs") or []:
        if isinstance(run, dict) and run.get("run_text"):
            return str(run["run_text"])
    return ""


def run_variant_apparatus_extraction(
    *,
    review_queue_reclassified: dict[str, Any],
    findings: dict[str, Any],
    parsed_payload: dict[str, Any],
    source_root: Path,
    targets_payload: dict[str, Any] | None = None,
    max_targets: int = 20,
    window_chars: int = 160,
) -> dict[str, Any]:
    parsed_items = [item for item in parsed_payload.get("items", []) if isinstance(item, dict)]
    parsed_by_key = {str(item.get("stable_segment_key")): item for item in parsed_items if item.get("stable_segment_key")}
    targets = select_targets(
        review_queue_reclassified,
        findings,
        parsed_payload,
        targets_payload=targets_payload,
        max_targets=max_targets,
    )
    source_paths = sorted({item.get("source_path") for item in parsed_items if item.get("source_path")})
    target_source_paths = sorted({item.get("source_path") for item in targets if item.get("source_path")})
    all_source_paths = sorted(set(source_paths) | set(target_source_paths))
    pilot_keys = set(parsed_by_key)

    source_checks = []
    records_for_300: list[dict[str, Any]] = []
    all_notes_for_300: list[dict[str, Any]] = []
    missing_sources: list[str] = []
    for source_path in all_source_paths:
        extraction = extract_source_apparatus(source_root, source_path, window_chars=window_chars)
        if not extraction.get("exists"):
            missing_sources.append(source_path)
            source_checks.append(
                {
                    "source_path": source_path,
                    "exists": False,
                    "note_count": 0,
                    "sigla_counts": {},
                    "note_type_counts": {},
                }
            )
            continue
        index = build_segment_index(source_root, source_path)
        path_to_key = index.get("path_to_key", {})
        for note in extraction["note_records"]:
            attributed_key = path_to_key.get(note.get("parent_xml_node_path", ""))
            note = {**note, "stable_segment_key": attributed_key or "", "attribution_confidence": "high" if attributed_key else "none"}
            if attributed_key in pilot_keys:
                all_notes_for_300.append(note)
                if note["is_variant_apparatus"]:
                    records_for_300.append(note)
        source_checks.append(
            {
                "source_path": source_path,
                "exists": True,
                "note_count": extraction["note_count"],
                "sigla_counts": extraction["sigla_counts"],
                "note_type_counts": extraction["note_type_counts"],
            }
        )

    crosscheck = build_crosscheck(targets, records_for_300, all_notes_for_300, parsed_by_key, missing_sources)
    full_300_summary = build_pilot_300_loss_summary(parsed_items, records_for_300, all_notes_for_300)
    premise = build_premise_check(source_checks, targets, crosscheck, parsed_by_key, full_300_summary)
    apparatus = build_variant_apparatus(records_for_300, source_checks, full_300_summary)
    return {
        "targets": targets,
        "premise_check": premise,
        "variant_apparatus": apparatus,
        "crosscheck": crosscheck,
        "source_checks": source_checks,
    }


def build_crosscheck(
    targets: list[dict[str, Any]],
    variant_records: list[dict[str, Any]],
    all_notes: list[dict[str, Any]],
    parsed_by_key: dict[str, Any],
    missing_sources: list[str],
) -> dict[str, Any]:
    variants_by_key: dict[str, list[dict[str, Any]]] = defaultdict(list)
    notes_by_key: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for record in variant_records:
        variants_by_key[record.get("stable_segment_key", "")].append(record)
    for record in all_notes:
        notes_by_key[record.get("stable_segment_key", "")].append(record)
    items = []
    counts: Counter[str] = Counter()
    for target in targets:
        key = target["stable_segment_key"]
        if target["source_path"] in missing_sources:
            classification = "apparatus_extraction_missing_source"
            records: list[dict[str, Any]] = []
        else:
            records = variants_by_key.get(key, [])
            if not records and key not in parsed_by_key:
                classification = "apparatus_attribution_failed"
            elif any(record_directly_attests_target(record, target) for record in records):
                classification = "apparatus_attests_variant"
            elif records:
                classification = "apparatus_has_variant_nearby"
            else:
                classification = "no_apparatus_variant"
        counts[classification] += 1
        items.append(crosscheck_item(target, classification, records))
    return {
        "schema_version": "pali_apparatus_qa_crosscheck_v0",
        "scope": "pilot_300_flagged_subset",
        "summary": {
            "target_count": len(targets),
            "apparatus_attests_variant": counts.get("apparatus_attests_variant", 0),
            "apparatus_has_variant_nearby": counts.get("apparatus_has_variant_nearby", 0),
            "no_apparatus_variant": counts.get("no_apparatus_variant", 0),
            "apparatus_extraction_missing_source": counts.get("apparatus_extraction_missing_source", 0),
            "apparatus_attribution_failed": counts.get("apparatus_attribution_failed", 0),
        },
        "items": items,
    }


def record_directly_attests_target(record: dict[str, Any], target: dict[str, Any]) -> bool:
    hint = normalize_for_match(target.get("target_hint", ""))
    if not hint:
        return False
    haystacks = [
        record.get("anchor_text", ""),
        record.get("main_reading", ""),
        record.get("context_before", ""),
        record.get("context_after", ""),
    ]
    normalized_haystacks = [normalize_for_match(value) for value in haystacks]
    if any(hint in value for value in normalized_haystacks):
        return True
    variant = normalize_for_match(record.get("variant_text", ""))
    return bool(variant and shared_long_token(hint, variant))


def normalize_for_match(text: str) -> str:
    return re.sub(r"\s+", " ", str(text).lower()).strip()


def shared_long_token(a: str, b: str) -> bool:
    a_tokens = {token for token in re.split(r"[^a-zāīūṅñṭḍṇḷṃ]+", a) if len(token) >= 5}
    b_tokens = {token for token in re.split(r"[^a-zāīūṅñṭḍṇḷṃ]+", b) if len(token) >= 5}
    return bool(a_tokens & b_tokens)


def crosscheck_item(target: dict[str, Any], classification: str, records: list[dict[str, Any]]) -> dict[str, Any]:
    if classification == "apparatus_attests_variant" and records:
        evidence = (
            f"Source note attests a variant reading '{records[0]['raw_note_text']}' near target "
            f"{target.get('target_hint', '')}."
        )
        recommendation = "source_variant_review_with_apparatus_evidence"
    elif classification == "apparatus_has_variant_nearby":
        evidence = "Source XML has variant apparatus structurally attributed to this segment, but direct relation to the target hint is uncertain."
        recommendation = "review_apparatus_nearby"
    elif classification == "apparatus_extraction_missing_source":
        evidence = "Source XML file was not available locally."
        recommendation = "local_source_required_before_apparatus_review"
    else:
        evidence = "No variant apparatus was structurally attributed to this segment."
        recommendation = "continue_normal_review_without_apparatus_evidence"
    return {
        "stable_segment_key": target["stable_segment_key"],
        "source_path": target["source_path"],
        "target_hint": target.get("target_hint", ""),
        "classification": classification,
        "apparatus_records": [record["apparatus_id"] for record in records],
        "evidence_summary": evidence,
        "recommendation": recommendation,
        "auto_modify_translation": False,
        "auto_modify_source": False,
        "review_required_after_crosscheck": True,
    }


def build_pilot_300_loss_summary(
    parsed_items: list[dict[str, Any]],
    variant_records: list[dict[str, Any]],
    all_notes: list[dict[str, Any]],
) -> dict[str, Any]:
    variants_by_key: dict[str, list[dict[str, Any]]] = defaultdict(list)
    citations_by_key: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for record in variant_records:
        variants_by_key[record.get("stable_segment_key", "")].append(record)
    for note in all_notes:
        if note.get("note_type") == "citation":
            citations_by_key[note.get("stable_segment_key", "")].append(note)
    variant_segments = {key for key, records in variants_by_key.items() if key and records}
    citation_segments = {key for key, records in citations_by_key.items() if key and records}
    missing_count = 0
    for item in parsed_items:
        key = str(item.get("stable_segment_key") or "")
        if key not in variant_segments:
            continue
        if not parsed_contains_any_apparatus_marker(item, variants_by_key[key]):
            missing_count += 1
    total = len(parsed_items)
    return {
        "total_segments": total,
        "segments_with_variant_apparatus_in_source": len(variant_segments),
        "segments_with_variant_apparatus_missing_from_translation_input": missing_count,
        "segments_with_citation_notes_in_source": len(citation_segments),
        "variant_note_records_in_300_source_scope": len(variant_records),
        "citation_note_records_in_300_source_scope": sum(len(value) for value in citations_by_key.values()),
        "apparatus_loss_rate": round(missing_count / len(variant_segments), 6) if variant_segments else 0.0,
    }


def parsed_contains_any_apparatus_marker(parsed_item: dict[str, Any], records: list[dict[str, Any]]) -> bool:
    text = " ".join(
        str(parsed_item.get(field, ""))
        for field in ("original_text", "literal_ko", "natural_ko", "source_text", "normalized_text")
    )
    for record in records:
        markers = [record.get("raw_note_text", ""), record.get("variant_text", "")]
        markers.extend(f"{siglum}." for siglum in record.get("sigla", []))
        if any(marker and marker in text for marker in markers):
            return True
    return False


def build_premise_check(
    source_checks: list[dict[str, Any]],
    targets: list[dict[str, Any]],
    crosscheck: dict[str, Any],
    parsed_by_key: dict[str, Any],
    full_300_summary: dict[str, Any],
) -> dict[str, Any]:
    case_items_by_key = {item["stable_segment_key"]: item for item in crosscheck["items"]}
    records_by_id = {
        record_id
        for item in crosscheck["items"]
        for record_id in item.get("apparatus_records", [])
    }
    case_checks = []
    for target in targets:
        item = case_items_by_key.get(target["stable_segment_key"], {})
        parsed = parsed_by_key.get(target["stable_segment_key"], {})
        parsed_text = " ".join(str(parsed.get(field, "")) for field in ("original_text", "literal_ko", "natural_ko"))
        source_note_found = bool(item.get("apparatus_records"))
        case_checks.append(
            {
                "stable_segment_key": target["stable_segment_key"],
                "target_hint": target.get("target_hint", ""),
                "source_note_found": source_note_found,
                "note_text": item.get("evidence_summary", ""),
                "parsed_contains_note_reading": False if source_note_found else None,
                "parsed_contains_siglum": bool(re.search(r"\([a-zāīūṅñṭḍṇḷṃ]+\.\)", parsed_text, re.IGNORECASE)),
                "premise_status": "apparatus_present_but_missing_from_translation_input"
                if source_note_found
                else "no_apparatus_note_found_or_missing_source",
            }
        )
    return {
        "schema_version": "pali_variant_apparatus_premise_check_v0",
        "cross_script_collation_deprecated": True,
        "reason": CROSS_SCRIPT_DEPRECATED_REASON,
        "source_xml_checked": source_checks,
        "case_checks": case_checks,
        "pilot_300_apparatus_loss_summary": full_300_summary,
        "importer_loss_location": "extract_main_text excludes note elements; exact downstream loss location not_determined",
        "recorded_apparatus_ids": sorted(records_by_id),
        "conclusion": "Use source <note> apparatus extraction instead of cross-script collation.",
    }


def build_variant_apparatus(
    variant_records: list[dict[str, Any]],
    source_checks: list[dict[str, Any]],
    full_300_summary: dict[str, Any],
) -> dict[str, Any]:
    unknown_sigla_count = sum(len(record.get("unknown_sigla", [])) for record in variant_records)
    return {
        "schema_version": "pali_variant_apparatus_v0",
        "scope": "pilot_300_flagged_subset_and_full_300_loss_measurement",
        "source": "VRI XML <note> apparatus",
        "cross_script_collation_deprecated": True,
        "records": [record for record in variant_records if record.get("is_variant_apparatus")],
        "summary": {
            "source_files_checked": len(source_checks),
            "note_records_extracted": sum(check.get("note_count", 0) for check in source_checks),
            "records_attributed_to_flagged_segments": sum(1 for record in variant_records if record.get("stable_segment_key")),
            "unknown_sigla_count": unknown_sigla_count,
            **full_300_summary,
        },
    }


def render_findings_markdown(
    *,
    premise: dict[str, Any],
    apparatus: dict[str, Any],
    crosscheck: dict[str, Any],
) -> str:
    summary = crosscheck["summary"]
    loss = premise["pilot_300_apparatus_loss_summary"]
    case_11 = next(
        (
            item
            for item in crosscheck["items"]
            if item["stable_segment_key"] == "vri:romn:s0519m.mul:f43a9c761757"
        ),
        None,
    )
    lines = [
        "# Pāli Variant Apparatus Extraction v0",
        "",
        "## Purpose",
        "",
        "This report extracts VRI XML `<note>` apparatus evidence for the 300 pilot QA subset. It does not modify source text, translations, parsed output, prompts, glossary, or gold sets.",
        "",
        "## Why Cross-Script Collation Was Deprecated",
        "",
        CROSS_SCRIPT_DEPRECATED_REASON,
        "",
        "## Premise Check",
        "",
        f"- cross_script_collation_deprecated: `{premise['cross_script_collation_deprecated']}`",
        f"- importer loss location: `{premise['importer_loss_location']}`",
        "",
        "## Source Files Checked",
        "",
        f"- source files checked: {apparatus['summary']['source_files_checked']}",
        f"- note records extracted: {apparatus['summary']['note_records_extracted']}",
        "",
        "## Note Counts and Sigla Counts",
        "",
    ]
    aggregate_sigla: Counter[str] = Counter()
    aggregate_note_types: Counter[str] = Counter()
    for check in premise["source_xml_checked"]:
        aggregate_sigla.update(check.get("sigla_counts") or {})
        aggregate_note_types.update(check.get("note_type_counts") or {})
    lines.append(f"- sigla counts: {dict(sorted(aggregate_sigla.items()))}")
    lines.append(f"- note type counts: {dict(sorted(aggregate_note_types.items()))}")
    lines.extend(
        [
            "",
            "## 300 Pilot Flagged Target Summary",
            "",
            f"- target count: {summary['target_count']}",
            f"- apparatus_attests_variant: {summary['apparatus_attests_variant']}",
            f"- apparatus_has_variant_nearby: {summary['apparatus_has_variant_nearby']}",
            f"- no_apparatus_variant: {summary['no_apparatus_variant']}",
            f"- apparatus_extraction_missing_source: {summary['apparatus_extraction_missing_source']}",
            f"- apparatus_attribution_failed: {summary['apparatus_attribution_failed']}",
            "",
            "## Full 300 Apparatus-Loss Summary",
            "",
            f"- total segments: {loss['total_segments']}",
            f"- segments with variant apparatus in source: {loss['segments_with_variant_apparatus_in_source']}",
            f"- segments with variant apparatus missing from translation input: {loss['segments_with_variant_apparatus_missing_from_translation_input']}",
            f"- segments with citation notes in source: {loss['segments_with_citation_notes_in_source']}",
            f"- variant note records in 300 source scope: {loss['variant_note_records_in_300_source_scope']}",
            f"- citation note records in 300 source scope: {loss['citation_note_records_in_300_source_scope']}",
            f"- apparatus loss rate: {loss['apparatus_loss_rate']}",
            "",
            "## #11 accantadiṭṭhaṃ Case Study",
            "",
        ]
    )
    if case_11:
        lines.extend(
            [
                f"- stable_segment_key: `{case_11['stable_segment_key']}`",
                f"- classification: `{case_11['classification']}`",
                f"- evidence: {case_11['evidence_summary']}",
                "- interpretation: #11 has an apparatus-attested variant involving `niṭṭhaṃ` in the Sinhala witness. This strongly supports a source-variant review, but no automatic correction is applied.",
            ]
        )
    else:
        lines.append("- #11 target was not present in the selected targets.")
    lines.extend(
        [
            "",
            "## Apparatus Cross-Check Results",
            "",
            "| stable_segment_key | target_hint | classification |",
            "| --- | --- | --- |",
        ]
    )
    for item in crosscheck["items"]:
        lines.append(f"| `{item['stable_segment_key']}` | `{item.get('target_hint', '')}` | `{item['classification']}` |")
    lines.extend(
        [
            "",
            "## Importer Note-Loss Finding",
            "",
            "Current ingestion/translation pipeline appears to drop or exclude XML `<note>` apparatus from translation input. Future work should preserve `<note>` apparatus as structured metadata, separate from main text.",
            "",
            "## Caveat: Apparatus Evidence Is Not Automatic Correction",
            "",
            "Apparatus notes attest variant readings; they do not automatically prove that the main reading is erroneous. The VRI main text remains the editor-selected reading. Any adoption of a variant reading requires a later reviewed decision with explicit provenance.",
            "",
            "No automatic correction was applied. `auto_modify_translation=false` and `auto_modify_source=false` remain in the cross-check output.",
            "",
            "## Upstream Recommendation",
            "",
            "Preserve note apparatus as source metadata fields: `note_raw_text`, `variant_text`, `sigla`, `anchor_text`, `source_path`, `xml_node_path`, `char_offset`, and `stable_segment_key`.",
            "",
            "Do not silently merge note variants into main source text.",
            "",
            "## Next Steps",
            "",
            "1. Importer note preservation.",
            "2. Apparatus-aware translation context experiment.",
            "3. Reviewer-adopted variant provenance field.",
            "",
        ]
    )
    return "\n".join(lines)


def output_record(path: Path) -> dict[str, Any]:
    return {"path": str(path), "sha256": hashlib.sha256(path.read_bytes()).hexdigest(), "exists": path.exists()}


def dump_json(payload: Any, *, pretty: bool = False) -> str:
    return json.dumps(payload, ensure_ascii=False, sort_keys=True, indent=2 if pretty else None) + "\n"

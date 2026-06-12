"""VRI tipitaka-xml importer for Buddha Korea canonical segment artifacts.

This importer deliberately avoids database writes, translation APIs, DPD hints,
embeddings, and RAG. It reads one XML file and emits a local JSON artifact:

    {"literature": {...}, "segments": [...], "import_report": {...}, "token_report": {...}}

The token report is optional and uses local counters only.
"""

from __future__ import annotations

import argparse
import copy
import hashlib
import json
import re
import sys
from collections import Counter, defaultdict
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
from xml.etree import ElementTree as ET

REPO_ROOT = Path(__file__).resolve().parents[3]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

try:
    from backend.pali.tokenization.token_counter import build_token_report, load_token_profiles
except ImportError:  # pragma: no cover - supports direct execution from unusual cwd values.
    build_token_report = None
    load_token_profiles = None


SOURCE_REPO = "https://github.com/VipassanaTech/tipitaka-xml"

HEADING_RENDS = {"nikaya", "book", "title", "chapter", "subhead", "subsubhead"}
PROSE_RENDS = {"bodytext", "indent", "unindented"}
VERSE_RENDS = {"hangnum", "gatha1", "gatha2", "gatha3", "gathalast"}
SKIP_RENDS = {"centre"}
KNOWN_RENDS = HEADING_RENDS | PROSE_RENDS | VERSE_RENDS | SKIP_RENDS
KNOWN_TAGS = {"TEI.2", "teiHeader", "text", "front", "body", "div", "head", "p", "pb", "note", "hi", "trailer"}

PITAKA_BY_PREFIX = {
    "vin": "vinaya",
    "s": "sutta",
    "abh": "abhidhamma",
    "e": "extra",
}

NIKAYA_BY_SUTTA_PREFIX = {
    "01": "Dīghanikāya",
    "02": "Majjhimanikāya",
    "03": "Saṃyuttanikāya",
    "04": "Aṅguttaranikāya",
    "05": "Khuddakanikāya",
}

TEXT_LAYER_BY_SUFFIX = {
    "mul": "mula",
    "att": "atthakatha",
    "tik": "tika",
    "nrf": "nrf",
}


@dataclass(frozen=True)
class VriXmlImportConfig:
    xml_path: Path
    source_path: str | None = None
    source_commit: str | None = None
    source_repo: str = SOURCE_REPO
    limit: int | None = None
    include_token_report: bool = False
    token_profiles_path: Path | None = None


@dataclass(frozen=True)
class LiteratureArtifact:
    data: dict[str, Any]


@dataclass(frozen=True)
class SegmentArtifact:
    data: dict[str, Any]


@dataclass(frozen=True)
class ImportReport:
    data: dict[str, Any]


@dataclass(frozen=True)
class VriXmlImportResult:
    literature: LiteratureArtifact
    segments: list[SegmentArtifact]
    import_report: ImportReport
    token_report: dict[str, Any] | None = None

    def to_dict(self) -> dict[str, Any]:
        result: dict[str, Any] = {
            "literature": self.literature.data,
            "segments": [segment.data for segment in self.segments],
            "import_report": self.import_report.data,
        }
        if self.token_report is not None:
            result["token_report"] = self.token_report
        return result


class VriXmlParser:
    """Parse one VRI XML file into Buddha Korea Segment JSON v1."""

    def __init__(self, config: VriXmlImportConfig):
        self.config = config
        self.unknown_rend_values: Counter[str] = Counter()
        self.unknown_node_count = 0
        self.skipped_node_count = 0
        self.metadata_only_node_count = 0
        self.pb_only_node_count = 0
        self.note_only_node_count = 0
        self.skipped_empty_node_count = 0
        self.note_count = 0
        self.page_ref_count = 0
        self.empty_text_segment_count = 0
        self.empty_text_error_count = 0
        self.empty_node_classification: Counter[str] = Counter()
        self.verse_group_count = 0
        self.verse_line_count = 0
        self.warnings: list[str] = []
        self.errors: list[str] = []

    def parse(self) -> VriXmlImportResult:
        source_path = self.config.source_path or self.config.xml_path.name
        source_file = Path(source_path).name
        script = infer_script(source_path)
        file_info = parse_source_file(source_file)

        tree = ET.parse(self.config.xml_path)
        root = tree.getroot()
        self._collect_document_stats(root)
        path_map = build_node_path_map(root)

        literature_title = find_literature_title(root) or file_info["book_code"]
        nikaya = find_first_rend_text(root, "nikaya") or infer_nikaya(file_info)
        pitaka = PITAKA_BY_PREFIX.get(file_info["prefix"])

        literature = {
            "literature_id": build_literature_id(script, source_file),
            "literature_name": literature_title,
            "pali_name": literature_title,
            "source_repo": self.config.source_repo,
            "source_commit": self.config.source_commit,
            "source_path": source_path,
            "source_file": source_file,
            "script": script,
            "text_group": pitaka,
            "pitaka": pitaka,
            "nikaya": nikaya,
            "book_code": file_info["book_code"],
            "text_layer": file_info["text_layer"],
            "filename_pattern": file_info["filename_pattern"],
        }

        state: dict[str, Any] = {
            "heading_path": [],
            "vagga_id": None,
            "vagga_name": None,
            "sutta_id": None,
            "sutta_name": None,
            "paragraph_counter": 0,
        }
        segments: list[dict[str, Any]] = []

        body = find_first_tag(root, "body")
        if body is None:
            self.warnings.append("No body element found; parsed from document root.")
            body = root

        self._walk_children(body, state, path_map, literature, segments)
        literature["total_segments"] = len(segments)

        import_report = self._build_import_report(segments, source_path, literature)
        token_report = None
        if self.config.include_token_report:
            if build_token_report is None or load_token_profiles is None:
                self.warnings.append("Token report requested, but token_counter module could not be imported.")
            else:
                profiles = load_token_profiles(self.config.token_profiles_path)
                token_report = build_token_report(
                    {"literature": literature, "segments": segments},
                    profiles=profiles,
                )

        return VriXmlImportResult(
            literature=LiteratureArtifact(literature),
            segments=[SegmentArtifact(segment) for segment in segments],
            import_report=ImportReport(import_report),
            token_report=token_report,
        )

    def _collect_document_stats(self, root: ET.Element) -> None:
        for element in root.iter():
            tag = strip_namespace(element.tag)
            if tag not in KNOWN_TAGS:
                self.unknown_node_count += 1
            if tag == "p":
                rend = element.attrib.get("rend")
                if rend and rend not in KNOWN_RENDS:
                    self.unknown_rend_values[rend] += 1
            elif tag == "note":
                self.note_count += 1
            elif tag == "pb":
                self.page_ref_count += 1

    def _walk_children(
        self,
        parent: ET.Element,
        state: dict[str, Any],
        path_map: dict[int, str],
        literature: dict[str, Any],
        segments: list[dict[str, Any]],
    ) -> None:
        verse_buffer: list[ET.Element] = []
        local_state = copy.deepcopy(state)

        def flush_verse() -> None:
            nonlocal verse_buffer
            if not verse_buffer:
                return
            self.verse_group_count += 1
            self.verse_line_count += len(verse_buffer)
            if self.config.limit is None or len(segments) < self.config.limit:
                segment = self._build_segment(
                    verse_buffer,
                    "verse",
                    local_state,
                    path_map,
                    literature,
                    len(segments) + 1,
                )
                if segment:
                    segments.append(segment)
            verse_buffer = []

        for child in list(parent):
            if self.config.limit is not None and len(segments) >= self.config.limit:
                return

            tag = strip_namespace(child.tag)

            if tag == "div":
                flush_verse()
                div_state = copy.deepcopy(local_state)
                apply_div_heading(child, div_state)
                self._walk_children(child, div_state, path_map, literature, segments)
                continue

            if tag == "trailer":
                flush_verse()
                self.skipped_node_count += 1
                continue

            if tag != "p":
                continue

            rend = child.attrib.get("rend", "")

            if rend in VERSE_RENDS:
                if not normalize_whitespace(extract_main_text(child)):
                    self._record_empty_candidate([child])
                    if rend == "gathalast":
                        flush_verse()
                    continue
                verse_buffer.append(child)
                if rend == "gathalast":
                    flush_verse()
                continue

            flush_verse()

            if rend in HEADING_RENDS:
                apply_p_heading(child, rend, local_state)
                self.metadata_only_node_count += 1
                self.skipped_node_count += 1
                continue

            if rend in PROSE_RENDS:
                if not normalize_whitespace(extract_main_text(child)):
                    self._record_empty_candidate([child])
                    continue
                segment = self._build_segment(
                    [child],
                    "prose",
                    local_state,
                    path_map,
                    literature,
                    len(segments) + 1,
                )
                if segment:
                    segments.append(segment)
                continue

            if rend in SKIP_RENDS:
                self.skipped_node_count += 1
                continue

            if rend:
                self.unknown_rend_values[rend] += 1
                self.warnings.append(f"Skipped p with unknown rend={rend!r} at {path_map.get(id(child))}.")
            else:
                self.warnings.append(f"Skipped p without rend at {path_map.get(id(child))}.")
            self.skipped_node_count += 1

        flush_verse()

    def _build_segment(
        self,
        nodes: list[ET.Element],
        chunk_type: str,
        state: dict[str, Any],
        path_map: dict[int, str],
        literature: dict[str, Any],
        sort_order: int,
    ) -> dict[str, Any] | None:
        state["paragraph_counter"] = int(state.get("paragraph_counter") or 0) + 1

        parts = [normalize_whitespace(extract_main_text(node)) for node in nodes]
        original_text = normalize_whitespace(" ".join(part for part in parts if part))
        normalized_text = normalize_whitespace(original_text)

        paths = [path_map[id(node)] for node in nodes if id(node) in path_map]
        xml_node_path = paths[0] if len(paths) == 1 else " + ".join(paths)

        if not original_text:
            classification = self._record_empty_candidate(nodes)
            if classification == "empty_text_error":
                self.errors.append(f"Empty original_text for segment candidate at {xml_node_path}.")
            return None

        canonical_ref = build_canonical_ref(literature, state, nodes, sort_order)
        key_material = f"{literature['source_path']}|{xml_node_path}"
        stable_segment_key = (
            f"vri:{literature['script']}:{literature['source_file'].removesuffix('.xml')}:"
            f"{short_hash(key_material)}"
        )
        edition_refs = collect_edition_refs(nodes)

        first_paragraph_number = next(
            (node.attrib.get("n") for node in nodes if node.attrib.get("n")),
            None,
        )
        paragraph_number = first_paragraph_number or state["paragraph_counter"]

        return {
            "stable_segment_key": stable_segment_key,
            "literature_id": literature["literature_id"],
            "literature_name": literature["literature_name"],
            "pali_name": literature["pali_name"],
            "source_repo": literature["source_repo"],
            "source_commit": literature["source_commit"],
            "source_path": literature["source_path"],
            "source_file": literature["source_file"],
            "script": literature["script"],
            "text_group": literature["text_group"],
            "pitaka": literature["pitaka"],
            "nikaya": literature["nikaya"],
            "book_code": literature["book_code"],
            "text_layer": literature["text_layer"],
            "canonical_ref": canonical_ref,
            "sort_order": sort_order,
            "xml_node_path": xml_node_path,
            "xml_node_paths": paths,
            "heading_path": copy.deepcopy(state["heading_path"]),
            "parent_key": build_parent_key(literature, state),
            "chunk_type": chunk_type,
            "paragraph_number": paragraph_number,
            "page_ref": format_page_ref(edition_refs[0]) if edition_refs else None,
            "edition_ref": edition_refs,
            "notes": collect_notes(nodes),
            "original_text": original_text,
            "normalized_text": normalized_text,
            "source_text_hash": hashlib.sha256(normalized_text.encode("utf-8")).hexdigest(),
            "legacy_location": None,
            "vagga_id": state.get("vagga_id"),
            "vagga_name": state.get("vagga_name"),
            "sutta_id": state.get("sutta_id"),
            "sutta_name": state.get("sutta_name"),
            "paragraph_id": state["paragraph_counter"],
        }

    def _record_empty_candidate(self, nodes: list[ET.Element]) -> str:
        classifications = [classify_empty_node(node) for node in nodes]
        if "empty_text_error" in classifications:
            classification = "empty_text_error"
        elif "pb_note_only" in classifications:
            classification = "pb_note_only"
        elif "pb_only" in classifications:
            classification = "pb_only"
        elif "note_only" in classifications:
            classification = "note_only"
        elif "metadata_only" in classifications:
            classification = "metadata_only"
        else:
            classification = "blank_only"

        self.empty_node_classification[classification] += 1
        self.empty_text_segment_count += 1
        self.skipped_empty_node_count += 1
        self.skipped_node_count += len(nodes)

        if classification == "pb_only":
            self.pb_only_node_count += 1
        elif classification == "note_only":
            self.note_only_node_count += 1
        elif classification == "pb_note_only":
            self.pb_only_node_count += 1
            self.note_only_node_count += 1
            self.metadata_only_node_count += 1
        elif classification == "metadata_only":
            self.metadata_only_node_count += 1
        elif classification == "empty_text_error":
            self.empty_text_error_count += 1

        return classification

    def _build_import_report(
        self,
        segments: list[dict[str, Any]],
        source_path: str,
        literature: dict[str, Any],
    ) -> dict[str, Any]:
        sort_orders = [segment["sort_order"] for segment in segments]
        source_hash_counts = Counter(segment["source_text_hash"] for segment in segments)
        duplicate_hash_count = sum(1 for count in source_hash_counts.values() if count > 1)
        headingless_count = sum(1 for segment in segments if not segment["heading_path"])
        chunk_type_counts = Counter(segment["chunk_type"] for segment in segments)
        largest = sorted(segments, key=lambda item: len(item["normalized_text"]), reverse=True)[:20]

        if sort_orders != list(range(1, len(sort_orders) + 1)):
            self.errors.append("sort_order is not a contiguous 1-based sequence.")

        return {
            "source_path": source_path,
            "source_commit": literature.get("source_commit"),
            "generated_at": datetime.now(timezone.utc).isoformat(),
            "total_segments": len(segments),
            "segment_count_by_chunk_type": dict(sorted(chunk_type_counts.items())),
            "unknown_node_count": self.unknown_node_count,
            "unknown_rend_values": dict(sorted(self.unknown_rend_values.items())),
            "skipped_node_count": self.skipped_node_count,
            "metadata_only_node_count": self.metadata_only_node_count,
            "pb_only_node_count": self.pb_only_node_count,
            "note_only_node_count": self.note_only_node_count,
            "skipped_empty_node_count": self.skipped_empty_node_count,
            "note_count": self.note_count,
            "page_ref_count": self.page_ref_count,
            "empty_text_segment_count": self.empty_text_segment_count,
            "empty_text_error_count": self.empty_text_error_count,
            "empty_node_classification": dict(sorted(self.empty_node_classification.items())),
            "duplicate_source_text_hash_count": duplicate_hash_count,
            "headingless_segment_count": headingless_count,
            "largest_segments_by_chars": [
                {
                    "stable_segment_key": segment["stable_segment_key"],
                    "sort_order": segment["sort_order"],
                    "chunk_type": segment["chunk_type"],
                    "char_count": len(segment["normalized_text"]),
                    "canonical_ref": segment["canonical_ref"],
                }
                for segment in largest
            ],
            "verse_group_count": self.verse_group_count,
            "verse_line_count": self.verse_line_count,
            "sort_order_unique": len(sort_orders) == len(set(sort_orders)),
            "sort_order_contiguous": sort_orders == list(range(1, len(sort_orders) + 1)),
            "notes_excluded_from_original_text": True,
            "page_refs_excluded_from_original_text": True,
            "warnings": self.warnings,
            "errors": self.errors,
        }


def parse_vri_xml(
    xml_path: str | Path,
    *,
    source_path: str | None = None,
    source_commit: str | None = None,
    source_repo: str = SOURCE_REPO,
    limit: int | None = None,
    include_token_report: bool = False,
    token_profiles_path: str | Path | None = None,
) -> dict[str, Any]:
    """Compatibility helper returning a plain dict artifact."""

    config = VriXmlImportConfig(
        xml_path=Path(xml_path),
        source_path=source_path,
        source_commit=source_commit,
        source_repo=source_repo,
        limit=limit,
        include_token_report=include_token_report,
        token_profiles_path=Path(token_profiles_path) if token_profiles_path else None,
    )
    return VriXmlParser(config).parse().to_dict()


def parse_source_file(source_file: str) -> dict[str, str]:
    stem = source_file.removesuffix(".xml")
    match = re.match(
        r"^(?P<prefix>[a-z]+)(?P<number>\d+)(?P<layer_letter>[matn])(?P<part>\d*)\.(?P<suffix>[a-z]+)$",
        stem,
    )
    if not match:
        return {
            "prefix": "",
            "number": "",
            "part": "",
            "book_code": stem.split(".", 1)[0],
            "text_layer": "unknown",
            "filename_pattern": "unknown",
        }

    data = match.groupdict()
    return {
        "prefix": data["prefix"],
        "number": data["number"],
        "part": data["part"],
        "book_code": f"{data['prefix']}{data['number']}{data['layer_letter']}{data['part']}",
        "text_layer": TEXT_LAYER_BY_SUFFIX.get(data["suffix"], data["suffix"]),
        "filename_pattern": "{prefix}{number}{layer_letter}{part}.{suffix}.xml",
    }


def infer_script(source_path: str) -> str:
    parts = Path(source_path).parts
    if "romn" in parts:
        return "romn"
    return parts[0] if len(parts) > 1 else "unknown"


def infer_nikaya(file_info: dict[str, str]) -> str | None:
    if file_info["prefix"] != "s" or len(file_info["number"]) < 2:
        return None
    return NIKAYA_BY_SUTTA_PREFIX.get(file_info["number"][:2])


def build_literature_id(script: str, source_file: str) -> str:
    slug = source_file.removesuffix(".xml").replace(".", "-").replace("_", "-")
    return f"vri-{script}-{slug}"


def apply_div_heading(div: ET.Element, state: dict[str, Any]) -> None:
    div_type = div.attrib.get("type")
    div_id = div.attrib.get("n") or div.attrib.get("id")
    head = next((child for child in list(div) if strip_namespace(child.tag) == "head"), None)
    heading_text = normalize_whitespace(extract_main_text(head)) if head is not None else div_id
    if not heading_text:
        return

    level_type = div_type or "div"
    replace_heading(state, level_type, heading_text, div_id)

    number = parse_leading_number(heading_text)
    if div_type in {"vagga", "chapter", "kanda"}:
        state["vagga_id"] = number
        state["vagga_name"] = heading_text
    elif div_type == "sutta":
        state["sutta_id"] = number
        state["sutta_name"] = heading_text
    elif div_type == "book":
        state["book_name"] = heading_text


def apply_p_heading(p: ET.Element, rend: str, state: dict[str, Any]) -> None:
    text = normalize_whitespace(extract_main_text(p))
    if not text:
        return

    replace_heading(state, rend, text, p.attrib.get("n"))
    number = parse_leading_number(text)

    if rend == "chapter":
        state["vagga_id"] = number
        state["vagga_name"] = text
        state["sutta_id"] = None
        state["sutta_name"] = None
        state["paragraph_counter"] = 0
    elif rend in {"subhead", "subsubhead"}:
        if number is not None or state.get("sutta_name") is None:
            state["sutta_id"] = number
            state["sutta_name"] = text
            state["paragraph_counter"] = 0


def replace_heading(
    state: dict[str, Any],
    kind: str,
    text: str,
    identifier: str | None,
) -> None:
    levels = {
        "nikaya": 0,
        "book": 1,
        "title": 2,
        "chapter": 3,
        "vagga": 3,
        "kanda": 3,
        "sutta": 4,
        "subhead": 5,
        "subsubhead": 6,
        "div": 7,
    }
    level = levels.get(kind, 6)
    path = [item for item in state["heading_path"] if item["level"] < level]
    path.append({"level": level, "type": kind, "text": text, "id": identifier})
    state["heading_path"] = path


def build_canonical_ref(
    literature: dict[str, Any],
    state: dict[str, Any],
    nodes: list[ET.Element],
    sort_order: int,
) -> str:
    node_number = next((node.attrib.get("n") for node in nodes if node.attrib.get("n")), None)
    heading_id = next(
        (item.get("id") for item in reversed(state["heading_path"]) if item.get("id")),
        None,
    )
    base = heading_id or literature["book_code"]
    if node_number:
        return f"{base}:{node_number}"
    return f"{base}:seg-{sort_order:06d}"


def build_parent_key(literature: dict[str, Any], state: dict[str, Any]) -> str | None:
    heading_id = next(
        (item.get("id") for item in reversed(state["heading_path"]) if item.get("id")),
        None,
    )
    if not heading_id:
        return None
    material = f"{literature['source_path']}|{heading_id}"
    return f"vri-parent:{short_hash(material)}"


def build_node_path_map(root: ET.Element) -> dict[int, str]:
    path_map: dict[int, str] = {}

    def walk(node: ET.Element, path: str) -> None:
        path_map[id(node)] = path
        counts: defaultdict[str, int] = defaultdict(int)
        for child in list(node):
            tag = strip_namespace(child.tag)
            counts[tag] += 1
            child_path = path_component(path, child, tag, counts[tag])
            walk(child, child_path)

    root_tag = strip_namespace(root.tag)
    walk(root, f"/{root_tag}")
    return path_map


def path_component(parent_path: str, element: ET.Element, tag: str, ordinal: int) -> str:
    stable_id = element.attrib.get("n") or element.attrib.get("id")
    if stable_id:
        return f"{parent_path}/{tag}[@n='{stable_id}']"
    return f"{parent_path}/{tag}[{ordinal}]"


def extract_main_text(element: ET.Element | None) -> str:
    if element is None:
        return ""
    parts: list[str] = []

    def walk(node: ET.Element) -> None:
        tag = strip_namespace(node.tag)
        if tag in {"note", "pb"}:
            if node.tail:
                parts.append(node.tail)
            return
        if node.text:
            parts.append(node.text)
        for child in list(node):
            walk(child)
        if node.tail:
            parts.append(node.tail)

    walk(element)
    return "".join(parts)


def collect_edition_refs(nodes: list[ET.Element]) -> list[dict[str, str | None]]:
    refs: list[dict[str, str | None]] = []
    for node in nodes:
        for pb in node.iter():
            if strip_namespace(pb.tag) == "pb":
                refs.append({"ed": pb.attrib.get("ed"), "n": pb.attrib.get("n")})
    return refs


def collect_notes(nodes: list[ET.Element]) -> list[str]:
    notes: list[str] = []
    for node in nodes:
        for note in node.iter():
            if strip_namespace(note.tag) == "note":
                text = normalize_whitespace("".join(note.itertext()))
                if text:
                    notes.append(text)
    return notes


def classify_empty_node(node: ET.Element) -> str:
    child_tags = [strip_namespace(child.tag) for child in list(node)]
    has_pb = any(strip_namespace(element.tag) == "pb" for element in node.iter())
    has_note = any(strip_namespace(element.tag) == "note" for element in node.iter())
    non_pb_note_children = [
        strip_namespace(element.tag)
        for element in node.iter()
        if element is not node and strip_namespace(element.tag) not in {"pb", "note"}
    ]
    tail_and_text = (node.text or "") + "".join(child.tail or "" for child in list(node))
    text_blank = not normalize_whitespace(tail_and_text)

    if has_pb and not has_note and not non_pb_note_children and text_blank:
        return "pb_only"
    if has_note and not has_pb and not non_pb_note_children and text_blank:
        return "note_only"
    if has_pb and has_note and not non_pb_note_children and text_blank:
        return "pb_note_only"
    if text_blank and not child_tags:
        return "blank_only"
    if text_blank and set(child_tags).issubset({"pb", "note"}):
        return "metadata_only"
    return "empty_text_error"


def format_page_ref(ref: dict[str, str | None]) -> str | None:
    if not ref.get("ed") and not ref.get("n"):
        return None
    if ref.get("ed") and ref.get("n"):
        return f"{ref['ed']}:{ref['n']}"
    return ref.get("n") or ref.get("ed")


def find_literature_title(root: ET.Element) -> str | None:
    for rend in ("book", "title"):
        found = find_first_rend_text(root, rend)
        if found:
            return found
    for element in root.iter():
        if strip_namespace(element.tag) == "head" and element.attrib.get("rend") == "book":
            text = normalize_whitespace(extract_main_text(element))
            if text:
                return text
    return None


def find_first_rend_text(root: ET.Element, rend: str) -> str | None:
    for element in root.iter():
        if strip_namespace(element.tag) == "p" and element.attrib.get("rend") == rend:
            text = normalize_whitespace(extract_main_text(element))
            if text:
                return text
    return None


def find_first_tag(root: ET.Element, tag_name: str) -> ET.Element | None:
    for element in root.iter():
        if strip_namespace(element.tag) == tag_name:
            return element
    return None


def parse_leading_number(text: str) -> int | None:
    match = re.match(r"^\s*(\d+)", text)
    if not match:
        return None
    return int(match.group(1))


def normalize_whitespace(text: str) -> str:
    return re.sub(r"\s+", " ", text).strip()


def short_hash(text: str) -> str:
    return hashlib.sha1(text.encode("utf-8")).hexdigest()[:12]


def strip_namespace(tag: str) -> str:
    return tag.rsplit("}", 1)[-1]


def write_json(path: Path, payload: dict[str, Any], *, pretty: bool) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2 if pretty else None),
        encoding="utf-8",
    )


def main() -> None:
    parser = argparse.ArgumentParser(description="Parse one VRI XML file into Segment JSON v1.")
    parser.add_argument("xml_path")
    parser.add_argument("--source-path")
    parser.add_argument("--source-commit")
    parser.add_argument("--source-repo", default=SOURCE_REPO)
    parser.add_argument("--out")
    parser.add_argument("--token-report")
    parser.add_argument("--token-profiles")
    parser.add_argument("--limit", type=int)
    parser.add_argument("--pretty", action="store_true")
    args = parser.parse_args()

    include_token_report = bool(args.token_report or args.token_profiles)
    result = parse_vri_xml(
        args.xml_path,
        source_path=args.source_path,
        source_commit=args.source_commit,
        source_repo=args.source_repo,
        limit=args.limit,
        include_token_report=include_token_report,
        token_profiles_path=args.token_profiles,
    )

    if args.out:
        write_json(Path(args.out), result, pretty=args.pretty)
    else:
        print(json.dumps(result, ensure_ascii=False, indent=2 if args.pretty else None))

    if args.token_report:
        token_report = result.get("token_report", {})
        write_json(Path(args.token_report), token_report, pretty=args.pretty)


if __name__ == "__main__":
    main()

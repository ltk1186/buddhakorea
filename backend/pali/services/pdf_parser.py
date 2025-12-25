"""
PDF parser for extracting Pali text from commentary PDFs.
Adapted from the existing process_pali.py logic.
"""
from __future__ import annotations

import re
import unicodedata
from collections import Counter
from pathlib import Path
from typing import Any, Dict, List, Optional, Sequence, Tuple
from dataclasses import dataclass

import fitz  # PyMuPDF


# Pali character set for regex patterns
PALI_CHARS = r"A-Za-zāīūṅñṭḍṇḷṃĀĪŪṄÑṬḌṆḶṂ"

# PDF artifacts to remove (line-level, robust to NBSP and broken dots)
PDF_ARTIFACT_LINE_PATTERNS = [
    re.compile(r"vipassana", re.IGNORECASE),
    re.compile(r"research\s+institute", re.IGNORECASE),
    re.compile(r"tipitaka\s*\.?\s*org", re.IGNORECASE),
    re.compile(r"www\s*\.?\s*tipitaka", re.IGNORECASE),
    re.compile(r"page[\s\u00a0]+\d+[\s\u00a0]+sur[\s\u00a0]+\d+", re.IGNORECASE),
]

PDF_PAGE_NUMBER_ONLY = re.compile(r"^\s*\d+\s*$")

HEADER_FOOTER_HINTS = (
    "vipassana",
    "tipitaka",
    "atthakatha",
    "pitaka",
    "nikayo",
    "institute",
    "www",
    "page",
)

HEADING_NUMBER_PATTERN = re.compile(r"^\s*(\d+)\.\s*(.+?)\s*$")

LEVEL_1_SUFFIXES = ("vagga", "vaggo", "nipata", "nipato", "kanda", "pariccheda", "niddeso", "niddesa")
LEVEL_2_SUFFIXES = ("suttavannana",)
GENERIC_HEADING_SUFFIXES = ("vannana", "katha")


@dataclass
class ParsedSegment:
    """Represents a parsed text segment."""
    vagga_id: int
    vagga_name: str
    sutta_id: int
    sutta_name: str
    page_number: int  # 1-based PDF page where the segment starts
    paragraph_id: int
    original_text: str


@dataclass(frozen=True)
class Heading:
    """Detected structural heading."""

    level: int  # 1 or 2
    section_id: int
    title: str
    kind: str  # used for hierarchy_labels inference
    page_number: int  # 1-based


class PdfParser:
    """Parser for extracting structured text from Pali PDFs."""

    def __init__(self, pdf_path: str):
        """Initialize the parser with a PDF file."""
        self.pdf_path = pdf_path
        self.headings: List[Heading] = []
        self.hierarchy_labels: Optional[Dict[str, str]] = None

        # Pre-compiled patterns used by some heading types (Pali with diacritics)
        self._vagga_heading_re = re.compile(
            rf"^\s*(\d+)\.\s+([{PALI_CHARS}]+(vaggo|vagga))\s*$",
            re.IGNORECASE,
        )
        self._sutta_heading_re = re.compile(
            rf"^\s*(\d+)\.\s+([{PALI_CHARS}]+suttavaṇṇanā)\s*$",
            re.IGNORECASE,
        )

    @staticmethod
    def _normalize_spaces(text: str) -> str:
        text = text.replace("\u00a0", " ")
        text = unicodedata.normalize("NFKC", text)
        text = re.sub(r"\s+", " ", text)
        return text.strip()

    @staticmethod
    def _strip_diacritics(text: str) -> str:
        normalized = unicodedata.normalize("NFKD", text)
        return "".join(ch for ch in normalized if unicodedata.category(ch) != "Mn")

    def _normalize_for_keywords(self, text: str) -> str:
        text = self._strip_diacritics(text).lower()
        text = re.sub(r"[^a-z0-9]+", " ", text)
        return " ".join(text.split())

    def _infer_boilerplate_keys(self, pages_lines: Sequence[List[str]]) -> set[str]:
        """
        Infer repeating header/footer lines (normalized) from first/last lines of pages.
        This complements explicit regex-based stripping and improves robustness.
        """
        counter: Counter[str] = Counter()
        pages_count = len(pages_lines)
        if pages_count == 0:
            return set()

        header_scan = 6
        footer_scan = 6

        for lines in pages_lines:
            nonempty = [self._normalize_spaces(l) for l in lines if self._normalize_spaces(l)]
            head = nonempty[:header_scan]
            tail = nonempty[-footer_scan:] if len(nonempty) >= footer_scan else nonempty

            for candidate in head + tail:
                key = self._normalize_for_keywords(re.sub(r"\d+", "#", candidate))
                if not key or len(key) < 6 or len(key) > 160:
                    continue
                if not any(hint in key for hint in HEADER_FOOTER_HINTS):
                    continue
                counter[key] += 1

        min_occurrences = max(5, int(pages_count * 0.2))
        return {k for k, v in counter.items() if v >= min_occurrences}

    def _is_artifact_line(self, line: str, boilerplate_keys: set[str]) -> bool:
        normalized = self._normalize_spaces(line)
        if not normalized:
            return False

        if PDF_PAGE_NUMBER_ONLY.match(normalized):
            return True

        for pattern in PDF_ARTIFACT_LINE_PATTERNS:
            if pattern.search(normalized):
                return True

        key = self._normalize_for_keywords(re.sub(r"\d+", "#", normalized))
        return key in boilerplate_keys

    def _extract_pages_lines(self, max_pages: Optional[int]) -> List[List[str]]:
        """Extract raw text lines per page using PyMuPDF."""
        pages_lines: List[List[str]] = []
        with fitz.open(self.pdf_path) as doc:
            pages_total = doc.page_count
            pages_to_process = pages_total if max_pages is None else min(pages_total, max_pages)
            for i in range(pages_to_process):
                page = doc.load_page(i)
                text = page.get_text("text") or ""
                text = text.replace("\r\n", "\n").replace("\r", "\n")
                pages_lines.append(text.splitlines())
        return pages_lines

    def _clean_pages_lines(
        self,
        pages_lines: Sequence[List[str]],
        boilerplate_keys: set[str],
    ) -> List[List[str]]:
        """Normalize and strip artifacts from raw page lines."""
        cleaned: List[List[str]] = []
        for raw_lines in pages_lines:
            page_clean: List[str] = []
            for raw_line in raw_lines:
                line = self._normalize_spaces(raw_line)
                if line and self._is_artifact_line(line, boilerplate_keys):
                    continue
                page_clean.append(line)
            cleaned.append(page_clean)
        return cleaned

    def _match_heading_candidate(self, line: str) -> Optional[Tuple[Optional[int], str, str]]:
        """
        Try to match a structural heading candidate.

        Returns:
            (number, title, kind) or None

        kind values (used to infer the best two-level hierarchy per PDF):
        - One of `LEVEL_1_SUFFIXES` (vagga/nipata/kanda/...)
        - "sutta" (…suttavaṇṇanā)
        - "vannana" (…vaṇṇanā, excluding suttavaṇṇanā)
        - "katha" (…kathā, excluding aṭṭhakathā)
        """
        raw = self._normalize_spaces(line)
        if not raw:
            return None

        # Headings are typically short and do not end with sentence punctuation.
        if len(raw) > 140 or raw.endswith((".", ":", ";")):
            return None

        number: Optional[int] = None
        title = raw
        match = HEADING_NUMBER_PATTERN.match(raw)
        if match:
            try:
                number = int(match.group(1))
            except ValueError:
                number = None
            title = match.group(2).strip()

        normalized = self._normalize_for_keywords(title)
        if not normalized:
            return None

        # Avoid misclassifying book titles (…aṭṭhakathā) as structure headings.
        if "atthakatha" in normalized:
            return None

        alpha_count = sum(1 for ch in title if ch.isalpha())
        if alpha_count / max(1, len(title)) < 0.5:
            return None

        # Heuristic fallback: only treat short "title-like" lines as headings.
        # This prevents false positives from content lines that mention "vagga/sutta".
        words = title.split()
        if len(words) > 4:
            return None
        if match and len(title) > 80:
            return None
        if not match and len(title) > 60:
            return None

        # Strong, exact match for vagga/vaggo headings (numbered, single-line).
        if match and self._vagga_heading_re.match(raw):
            kind = "vaggo" if normalized.endswith("vaggo") else "vagga"
            return number, title, kind

        # Strong, exact match for suttavaṇṇanā headings.
        if match and self._sutta_heading_re.match(raw):
            return number, title, "sutta"

        # Prefer suffix-based matching (headings usually end with these markers).
        if any(normalized.endswith(s) for s in LEVEL_1_SUFFIXES):
            kind = next((s for s in LEVEL_1_SUFFIXES if normalized.endswith(s)), "vagga")
            return number, title, kind

        if any(normalized.endswith(s) for s in LEVEL_2_SUFFIXES):
            return number, title, "sutta"

        if normalized.endswith("vannana"):
            return number, title, "vannana"

        if normalized.endswith("katha"):
            return number, title, "katha"

        return None

    def _infer_hierarchy_labels_from_headings(self, headings: Sequence[Heading]) -> Dict[str, str]:
        level_1_kinds = [h.kind for h in headings if h.level == 1]
        level_2_kinds = [h.kind for h in headings if h.level == 2]

        def canonical(kind: str) -> str:
            if kind in ("vaggo", "vagga"):
                return "vagga"
            if kind in ("nipata", "nipato"):
                return "nipāta"
            if kind == "kanda":
                return "kaṇḍa"
            if kind in ("niddeso", "niddesa"):
                return "niddesa"
            if kind == "sutta":
                return "sutta"
            if kind == "katha":
                return "kathā"
            if kind == "vannana":
                return "vaṇṇanā"
            return kind

        def pick(kinds: List[str], default: str) -> str:
            if not kinds:
                return default
            counts = Counter(canonical(k) for k in kinds)
            max_count = max(counts.values())
            candidates = [k for k, v in counts.items() if v == max_count]

            # Deterministic tie-breaker: prefer more semantically useful labels.
            priority = [
                "vagga",
                "nipāta",
                "kaṇḍa",
                "pariccheda",
                "sutta",
                "vaṇṇanā",
                "kathā",
                "section",
                "subsection",
            ]
            for p in priority:
                if p in candidates:
                    return p
            return sorted(candidates)[0]

        return {
            "level_1": pick(level_1_kinds, default="section"),
            "level_2": pick(level_2_kinds, default="subsection"),
        }

    def parse(
        self,
        max_pages: Optional[int] = None,
        max_chunk_size: int = 2000,
        pages_lines: Optional[Sequence[List[str]]] = None,
    ) -> List[ParsedSegment]:
        """
        Parse the PDF and extract structured segments.

        Args:
            max_pages: Maximum number of pages to process
            max_chunk_size: Maximum character count per segment

        Returns:
            List of ParsedSegment objects
        """
        pages_lines = self._extract_pages_lines(max_pages=max_pages) if pages_lines is None else list(pages_lines)
        boilerplate_keys = self._infer_boilerplate_keys(pages_lines)
        cleaned_pages = self._clean_pages_lines(pages_lines, boilerplate_keys)

        # First pass: detect what kinds of headings exist, so we can map them to two levels reliably.
        kind_counts: Counter[str] = Counter()
        for page_lines in cleaned_pages:
            for line in page_lines:
                if not line:
                    continue
                candidate = self._match_heading_candidate(line)
                if candidate:
                    _, _, kind = candidate
                    kind_counts[kind] += 1

        level_1_marker_count = sum(kind_counts.get(k, 0) for k in LEVEL_1_SUFFIXES)
        sutta_heading_count = kind_counts.get("sutta", 0)

        # Mode selection:
        # - marker: PDFs that contain internal vaggas/nipātas/kaṇḍas, etc.
        # - sutta_only: PDFs that are a single commentary unit but contain many suttavaṇṇanā headings
        #              (e.g., DN/MN/SN/AN vagga commentaries). We create a synthetic level_1.
        # - generic: fallback (Abhidhamma/Vinaya substructures, nested vaṇṇanā, etc.)
        if level_1_marker_count >= 2:
            mode = "marker"
        elif sutta_heading_count >= 2:
            mode = "sutta_only"
        else:
            mode = "generic"

        # In marker mode, pick the best available level_2 heading kind.
        marker_level_2_kind: Optional[str] = None
        if mode == "marker":
            if sutta_heading_count > 0:
                marker_level_2_kind = "sutta"
            elif kind_counts.get("vannana", 0) > 0:
                marker_level_2_kind = "vannana"
            elif kind_counts.get("katha", 0) > 0:
                marker_level_2_kind = "katha"

        segments: List[ParsedSegment] = []
        self.headings = []

        current_level_1_id = 0
        current_level_1_name = ""
        current_level_2_id = 0
        current_level_2_name = ""

        level_1_seq_id = 0  # Always use sequential IDs (PDF numbering often resets across sub-collections)
        level_2_seq_id = 0  # Reset per level_1

        paragraph_id = 0
        buffer: List[str] = []
        buffer_start_page = 1

        # sutta_only: create a single synthetic level_1 bucket for the whole PDF.
        if mode == "sutta_only":
            level_1_seq_id = 1
            current_level_1_id = level_1_seq_id
            current_level_1_name = Path(self.pdf_path).stem
            self.headings.append(
                Heading(
                    level=1,
                    section_id=current_level_1_id,
                    title=current_level_1_name,
                    kind="work",
                    page_number=1,
                )
            )

        def flush_buffer() -> None:
            nonlocal paragraph_id, buffer, buffer_start_page
            text = " ".join(buffer).strip()
            buffer = []
            if not text or len(text) <= 10:
                buffer_start_page = 1
                return

            chunks = self._split_long_text(text, max_chunk_size) if len(text) > max_chunk_size else [text]
            for chunk in chunks:
                segments.append(
                    ParsedSegment(
                        vagga_id=current_level_1_id,
                        vagga_name=current_level_1_name,
                        sutta_id=current_level_2_id,
                        sutta_name=current_level_2_name,
                        page_number=buffer_start_page,
                        paragraph_id=paragraph_id,
                        original_text=chunk,
                    )
                )
                paragraph_id += 1
            buffer_start_page = 1

        seen_marker_level_1 = False

        for page_index, page_lines in enumerate(cleaned_pages):
            page_number = page_index + 1
            for line in page_lines:
                # Treat empty lines as paragraph boundaries.
                if not line:
                    flush_buffer()
                    continue

                candidate = self._match_heading_candidate(line)
                if candidate:
                    flush_buffer()
                    number, title, kind = candidate

                    normalized_title = self._normalize_for_keywords(title)
                    apply_level: Optional[int] = None

                    if mode == "marker":
                        if kind in LEVEL_1_SUFFIXES:
                            apply_level = 1
                            seen_marker_level_1 = True
                        elif marker_level_2_kind and kind == marker_level_2_kind and seen_marker_level_1:
                            # Some PDFs insert an unnumbered "...niddesavaṇṇanā" line as an intermediate label
                            # before the real numbered subsections (e.g., Cuḷaniddesa-aṭṭhakathā).
                            if (
                                marker_level_2_kind == "vannana"
                                and number is None
                                and normalized_title.endswith("niddesavannana")
                            ):
                                apply_level = None
                            else:
                                apply_level = 2
                        elif (
                            seen_marker_level_1
                            and marker_level_2_kind == "sutta"
                            and kind == "vannana"
                            and number is not None
                            and "sutta" in normalized_title
                        ):
                            # Some sutta headings are formatted as "...-vaṇṇanā" (not "...suttavaṇṇanā")
                            # but still include "sutta" in the title.
                            apply_level = 2
                        elif kind == "katha" and number is None and "nigamana" in normalized_title:
                            # Include conclusion-style headings (e.g., "Nigamanakathā") as a top-level section.
                            apply_level = 1
                        elif not seen_marker_level_1 and kind in ("katha", "vannana"):
                            # Keep preface-style headings before the first real marker section.
                            apply_level = 1
                        else:
                            # Ignore other headings to avoid breaking the primary structure.
                            apply_level = None

                    elif mode == "sutta_only":
                        if kind == "sutta":
                            apply_level = 2
                        else:
                            apply_level = None

                    else:  # generic
                        if kind in LEVEL_1_SUFFIXES or kind == "sutta":
                            apply_level = 1
                        elif kind in ("katha", "vannana"):
                            # Nested numbered headings become level_2 when we already have a level_1.
                            apply_level = 2 if (number is not None and current_level_1_name) else 1

                    if apply_level == 1:
                        display_title = f"{number}. {title}" if number is not None else title
                        # Some PDFs repeat the same level_1 marker at volume boundaries (e.g., "(Dutiyo bhāgo)")
                        # without actually starting a new section. Treat exact repeats as duplicates.
                        if current_level_1_name:
                            current_key = self._normalize_for_keywords(current_level_1_name)
                            candidate_key = self._normalize_for_keywords(display_title)
                            if current_key == candidate_key:
                                continue
                        level_1_seq_id += 1 if mode != "sutta_only" else 0
                        if mode != "sutta_only":
                            current_level_1_id = level_1_seq_id
                        current_level_1_name = display_title

                        current_level_2_id = 0
                        current_level_2_name = ""
                        level_2_seq_id = 0
                        paragraph_id = 0

                        self.headings.append(
                            Heading(
                                level=1,
                                section_id=current_level_1_id,
                                title=display_title,
                                kind=kind,
                                page_number=page_number,
                            )
                        )
                        continue

                    if apply_level == 2:
                        display_title = f"{number}. {title}" if number is not None else title
                        level_2_seq_id += 1
                        current_level_2_id = level_2_seq_id
                        current_level_2_name = display_title
                        paragraph_id = 0

                        self.headings.append(
                            Heading(
                                level=2,
                                section_id=current_level_2_id,
                                title=display_title,
                                kind=kind,
                                page_number=page_number,
                            )
                        )
                        continue

                    # Candidate heading that isn't used in this mode: drop it as text boundary.
                    continue

                # Merge wrapped lines into a single paragraph buffer.
                if buffer and buffer[-1].endswith("-") and line and line[0].islower():
                    buffer[-1] = buffer[-1][:-1] + line
                else:
                    if not buffer:
                        buffer_start_page = page_number
                    buffer.append(line)

        flush_buffer()
        if mode == "sutta_only":
            self.hierarchy_labels = {"level_1": "work", "level_2": "sutta"}
        else:
            self.hierarchy_labels = self._infer_hierarchy_labels_from_headings(self.headings)
        return segments

    def _split_long_text(self, text: str, max_size: int) -> List[str]:
        """Split long text at sentence boundaries."""
        if len(text) <= max_size:
            return [text]

        # Try to split at sentence boundaries (period followed by space and uppercase)
        sentence_pattern = r'(?<=[.!?])\s+(?=[A-ZĀĪŪṄÑṬḌṆḶṂ])'
        sentences = re.split(sentence_pattern, text)

        chunks = []
        current_chunk = ""

        for sentence in sentences:
            if len(current_chunk) + len(sentence) <= max_size:
                current_chunk += (" " if current_chunk else "") + sentence
            else:
                if current_chunk:
                    chunks.append(current_chunk)
                current_chunk = sentence

        if current_chunk:
            chunks.append(current_chunk)

        return chunks

    def to_dict_list(self, segments: List[ParsedSegment]) -> List[dict]:
        """Convert parsed segments to list of dicts for DB insertion."""
        return [
            {
                "vagga_id": s.vagga_id,
                "vagga_name": s.vagga_name,
                "sutta_id": s.sutta_id,
                "sutta_name": s.sutta_name,
                "page_number": s.page_number,
                "paragraph_id": s.paragraph_id,
                "original_text": s.original_text,
            }
            for s in segments
        ]

    def extract_hierarchy(self, max_pages: Optional[int] = None) -> Dict[str, Any]:
        """
        Extract a two-level hierarchy outline for the PDF (vagga/sutta or equivalent).

        Returns:
            {
              "hierarchy_labels": {"level_1": "...", "level_2": "..."},
              "vaggas": [
                 {"vagga_id": 1, "vagga_name": "...", "start_page": 3, "suttas": [...]},
              ],
              "headings_count": 123
            }
        """
        # Trigger heading extraction with a cheap pass (no need to keep segments).
        _ = self.parse(max_pages=max_pages)

        vaggas: List[Dict[str, Any]] = []
        current_vagga: Optional[Dict[str, Any]] = None

        for h in self.headings:
            if h.level == 1:
                current_vagga = {
                    "vagga_id": h.section_id,
                    "vagga_name": h.title,
                    "start_page": h.page_number,
                    "suttas": [],
                }
                vaggas.append(current_vagga)
                continue

            if h.level == 2:
                if current_vagga is None:
                    current_vagga = {
                        "vagga_id": 0,
                        "vagga_name": "General",
                        "start_page": 1,
                        "suttas": [],
                    }
                    vaggas.append(current_vagga)

                current_vagga["suttas"].append(
                    {
                        "sutta_id": h.section_id,
                        "sutta_name": h.title,
                        "start_page": h.page_number,
                    }
                )

        return {
            "hierarchy_labels": self.hierarchy_labels or {"level_1": "section", "level_2": "subsection"},
            "vaggas": vaggas,
            "headings_count": len(self.headings),
        }

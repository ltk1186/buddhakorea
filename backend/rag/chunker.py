"""TEI P5 XML Chunker for Buddhist Texts.

This module parses CBETA TEI P5 XML files and extracts text chunks with metadata
for the Buddhist RAG system.

Following clean architecture principles:
- Type hints for all functions
- Comprehensive docstrings
- Data classes for configuration
- Dependency injection pattern
"""

import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Optional

from lxml import etree


class InvalidXMLError(Exception):
    """Raised when XML file cannot be parsed."""

    pass


@dataclass
class ChunkerConfig:
    """Configuration for TEI XML chunking.

    Attributes:
        chunk_size: Maximum characters per chunk
        chunk_overlap: Number of characters to overlap between chunks
        min_chunk_size: Minimum characters to consider a valid chunk
        include_metadata: Whether to include metadata in chunks
    """

    chunk_size: int = 512
    chunk_overlap: int = 50
    min_chunk_size: int = 50
    include_metadata: bool = True


@dataclass
class Chunk:
    """Text chunk with metadata.

    Attributes:
        text: The actual text content
        metadata: Dictionary containing sutra_id, chapter, paragraph, etc.
    """

    text: str
    metadata: Dict[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        """Add character count to metadata after initialization."""
        self.metadata["char_count"] = len(self.text)


def parse_tei_file(xml_path: Path) -> etree._Element:
    """Parse TEI P5 XML file.

    Args:
        xml_path: Path to XML file

    Returns:
        Root element of parsed XML tree

    Raises:
        FileNotFoundError: If XML file doesn't exist
        InvalidXMLError: If XML cannot be parsed
    """
    if not xml_path.exists():
        raise FileNotFoundError(f"XML file not found: {xml_path}")

    try:
        parser = etree.XMLParser(remove_blank_text=True, encoding="utf-8")
        tree = etree.parse(str(xml_path), parser)
        return tree.getroot()
    except etree.XMLSyntaxError as e:
        raise InvalidXMLError(f"Failed to parse XML file {xml_path}: {e}")
    except Exception as e:
        raise InvalidXMLError(f"Unexpected error parsing XML {xml_path}: {e}")


def extract_sutra_id(root: etree._Element) -> Optional[str]:
    """Extract sutra ID from TEI header.

    Args:
        root: Root element of TEI document

    Returns:
        Sutra ID (e.g., "T0001") or None if not found
    """
    # TEI namespace
    ns = {"tei": "http://www.tei-c.org/ns/1.0"}

    # Try to find bibl element in sourceDesc
    bibl = root.find(".//tei:sourceDesc/tei:bibl", ns)

    if bibl is not None and bibl.text:
        # Clean up whitespace
        sutra_id = bibl.text.strip()
        return sutra_id if sutra_id else None

    return None


def extract_text_chunks(
    root: etree._Element,
    sutra_id: Optional[str] = None,
    config: Optional[ChunkerConfig] = None,
) -> List[Chunk]:
    """Extract text chunks from TEI body.

    Args:
        root: Root element of TEI document
        sutra_id: Sutra identifier
        config: Chunker configuration

    Returns:
        List of Chunk objects with text and metadata
    """
    if config is None:
        config = ChunkerConfig()

    if sutra_id is None:
        sutra_id = "UNKNOWN"

    chunks: List[Chunk] = []
    ns = {"tei": "http://www.tei-c.org/ns/1.0"}

    # Find all chapter divisions
    body = root.find(".//tei:body", ns)
    if body is None:
        return chunks

    # Find all divs (chapters)
    divs = body.findall(".//tei:div", ns)

    if not divs:
        # If no divs, process paragraphs directly
        divs = [body]

    for div_idx, div in enumerate(divs):
        # Get chapter number from div attribute
        chapter_num = div.get("n", str(div_idx + 1))

        # Find all paragraphs in this chapter
        paragraphs = div.findall(".//tei:p", ns)

        for para_idx, para in enumerate(paragraphs):
            # Extract text from paragraph
            text = "".join(para.itertext()).strip()

            # Skip empty paragraphs (whitespace-only)
            if not text:
                continue

            # If text is within chunk size, create single chunk
            if len(text) <= config.chunk_size:
                chunk = Chunk(
                    text=text,
                    metadata={
                        "sutra_id": sutra_id,
                        "chapter": chapter_num,
                        "paragraph": str(para_idx + 1),
                    },
                )
                chunks.append(chunk)
            else:
                # Split long paragraphs into overlapping chunks
                sub_chunks = _split_text_with_overlap(
                    text, config.chunk_size, config.chunk_overlap
                )

                for sub_idx, sub_text in enumerate(sub_chunks):
                    chunk = Chunk(
                        text=sub_text,
                        metadata={
                            "sutra_id": sutra_id,
                            "chapter": chapter_num,
                            "paragraph": f"{para_idx + 1}.{sub_idx + 1}",
                        },
                    )
                    chunks.append(chunk)

    return chunks


def _split_text_with_overlap(text: str, chunk_size: int, overlap: int) -> List[str]:
    """Split text into overlapping chunks.

    Args:
        text: Text to split
        chunk_size: Maximum size per chunk
        overlap: Number of characters to overlap

    Returns:
        List of text chunks
    """
    chunks: List[str] = []
    start = 0

    while start < len(text):
        end = start + chunk_size
        chunk = text[start:end]
        chunks.append(chunk)

        # Move start forward, accounting for overlap
        start = end - overlap
        if start >= len(text):
            break

    return chunks


class TEIChunker:
    """TEI XML chunker with configurable parameters.

    Uses dependency injection pattern for configuration.
    Implements __call__ interface for functional use.

    Example:
        ```python
        config = ChunkerConfig(chunk_size=1024)
        chunker = TEIChunker(config=config)
        chunks = chunker(Path("sutra.xml"))
        ```
    """

    def __init__(self, config: Optional[ChunkerConfig] = None):
        """Initialize chunker with configuration.

        Args:
            config: Chunker configuration (uses defaults if None)
        """
        self.config = config if config is not None else ChunkerConfig()

    def __call__(self, xml_path: Path) -> List[Chunk]:
        """Process TEI XML file and extract chunks.

        Args:
            xml_path: Path to TEI XML file

        Returns:
            List of Chunk objects

        Raises:
            FileNotFoundError: If XML file doesn't exist
            InvalidXMLError: If XML cannot be parsed
        """
        # Parse XML file
        root = parse_tei_file(xml_path)

        # Extract sutra ID from header
        sutra_id = extract_sutra_id(root)

        # Extract text chunks from body
        chunks = extract_text_chunks(root, sutra_id, self.config)

        return chunks

    def process_directory(self, directory: Path) -> List[Chunk]:
        """Process all XML files in a directory.

        Args:
            directory: Directory containing XML files

        Returns:
            List of all chunks from all files
        """
        all_chunks: List[Chunk] = []

        for xml_file in directory.glob("*.xml"):
            try:
                chunks = self(xml_file)
                all_chunks.extend(chunks)
            except (FileNotFoundError, InvalidXMLError) as e:
                print(f"Warning: Failed to process {xml_file}: {e}")
                continue

        return all_chunks

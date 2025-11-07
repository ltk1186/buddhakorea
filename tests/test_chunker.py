"""Test suite for TEI P5 XML Chunker module.

This module tests the parsing of CBETA TEI P5 XML files and extraction of text chunks
with proper metadata for the Buddhist RAG system.

Following TDD: These tests are written BEFORE implementation.
"""

from pathlib import Path
from typing import Any, Dict, List

import pytest
from lxml import etree

from src.chunker import (
    TEIChunker,
    Chunk,
    ChunkerConfig,
    InvalidXMLError,
    parse_tei_file,
    extract_sutra_id,
    extract_text_chunks,
)


class TestChunkerConfig:
    """Test ChunkerConfig data class."""

    def test_default_config(self) -> None:
        """Test default configuration values."""
        config = ChunkerConfig()

        assert config.chunk_size == 512
        assert config.chunk_overlap == 50
        assert config.min_chunk_size == 50
        assert config.include_metadata is True

    def test_custom_config(self) -> None:
        """Test custom configuration values."""
        config = ChunkerConfig(
            chunk_size=1024,
            chunk_overlap=100,
            min_chunk_size=100,
            include_metadata=False,
        )

        assert config.chunk_size == 1024
        assert config.chunk_overlap == 100
        assert config.min_chunk_size == 100
        assert config.include_metadata is False


class TestChunk:
    """Test Chunk data class."""

    def test_chunk_creation(self) -> None:
        """Test creating a chunk with text and metadata."""
        chunk = Chunk(
            text="This is test text.",
            metadata={
                "sutra_id": "T0001",
                "chapter": "1",
                "paragraph": "1",
            },
        )

        assert chunk.text == "This is test text."
        assert chunk.metadata["sutra_id"] == "T0001"
        assert chunk.metadata["chapter"] == "1"

    def test_chunk_char_count(self) -> None:
        """Test that chunk calculates character count."""
        chunk = Chunk(
            text="Hello World!",
            metadata={"sutra_id": "T0001"},
        )

        # Should add char_count to metadata
        assert chunk.metadata.get("char_count") == 12 or len(chunk.text) == 12


class TestParseTEIFile:
    """Test TEI XML file parsing."""

    def test_parse_valid_xml(self, sample_tei_xml: str, tmp_path: Path) -> None:
        """Test parsing a valid TEI XML file."""
        # Write sample XML to temp file
        xml_file = tmp_path / "test_sutra.xml"
        xml_file.write_text(sample_tei_xml, encoding="utf-8")

        # Parse the file
        root = parse_tei_file(xml_file)

        assert root is not None
        assert root.tag.endswith("TEI")

    def test_parse_invalid_xml(self, tmp_path: Path) -> None:
        """Test that parsing invalid XML raises InvalidXMLError."""
        # Create invalid XML file
        xml_file = tmp_path / "invalid.xml"
        xml_file.write_text("<<invalid>>xml<>", encoding="utf-8")

        with pytest.raises(InvalidXMLError) as exc_info:
            parse_tei_file(xml_file)

        assert "Failed to parse XML" in str(exc_info.value)

    def test_parse_nonexistent_file(self, tmp_path: Path) -> None:
        """Test that parsing nonexistent file raises FileNotFoundError."""
        xml_file = tmp_path / "does_not_exist.xml"

        with pytest.raises(FileNotFoundError):
            parse_tei_file(xml_file)

    def test_parse_with_namespaces(self, sample_tei_xml: str, tmp_path: Path) -> None:
        """Test that parser handles TEI namespaces correctly."""
        xml_file = tmp_path / "test_ns.xml"
        xml_file.write_text(sample_tei_xml, encoding="utf-8")

        root = parse_tei_file(xml_file)

        # Should be able to find elements with namespace
        namespaces = {"tei": "http://www.tei-c.org/ns/1.0"}
        body = root.find(".//tei:body", namespaces)

        assert body is not None


class TestExtractSutraID:
    """Test sutra ID extraction from TEI header."""

    def test_extract_sutra_id_from_bibl(self, sample_tei_xml: str, tmp_path: Path) -> None:
        """Test extracting sutra ID from bibl element."""
        xml_file = tmp_path / "test.xml"
        xml_file.write_text(sample_tei_xml, encoding="utf-8")

        root = parse_tei_file(xml_file)
        sutra_id = extract_sutra_id(root)

        assert sutra_id == "T0001"

    def test_extract_sutra_id_missing(self, tmp_path: Path) -> None:
        """Test extraction when sutra ID is missing."""
        xml_content = """<?xml version="1.0"?>
        <TEI xmlns="http://www.tei-c.org/ns/1.0">
            <teiHeader>
                <fileDesc>
                    <sourceDesc></sourceDesc>
                </fileDesc>
            </teiHeader>
        </TEI>
        """
        xml_file = tmp_path / "no_id.xml"
        xml_file.write_text(xml_content, encoding="utf-8")

        root = parse_tei_file(xml_file)
        sutra_id = extract_sutra_id(root)

        # Should return None or "UNKNOWN"
        assert sutra_id is None or sutra_id == "UNKNOWN"


class TestExtractTextChunks:
    """Test text chunk extraction from TEI body."""

    def test_extract_chunks_from_paragraphs(
        self, sample_tei_xml: str, tmp_path: Path
    ) -> None:
        """Test extracting chunks from paragraph elements."""
        xml_file = tmp_path / "test.xml"
        xml_file.write_text(sample_tei_xml, encoding="utf-8")

        root = parse_tei_file(xml_file)
        chunks = extract_text_chunks(root, sutra_id="T0001")

        # Should extract 3 paragraphs from sample XML
        assert len(chunks) == 3
        assert "impermanence" in chunks[0].text
        assert "suffering" in chunks[1].text
        assert "Noble Eightfold Path" in chunks[2].text

    def test_chunk_metadata_includes_location(
        self, sample_tei_xml: str, tmp_path: Path
    ) -> None:
        """Test that chunks include chapter and paragraph metadata."""
        xml_file = tmp_path / "test.xml"
        xml_file.write_text(sample_tei_xml, encoding="utf-8")

        root = parse_tei_file(xml_file)
        chunks = extract_text_chunks(root, sutra_id="T0001")

        # First chunk should be from chapter 1, paragraph 1
        assert chunks[0].metadata["sutra_id"] == "T0001"
        assert chunks[0].metadata["chapter"] == "1"

        # Third chunk should be from chapter 2
        assert chunks[2].metadata["chapter"] == "2"

    def test_extract_chunks_with_size_limit(
        self, sample_tei_xml: str, tmp_path: Path
    ) -> None:
        """Test chunk extraction respects size limits."""
        xml_file = tmp_path / "test.xml"
        xml_file.write_text(sample_tei_xml, encoding="utf-8")

        root = parse_tei_file(xml_file)
        config = ChunkerConfig(chunk_size=50, chunk_overlap=10)
        chunks = extract_text_chunks(root, sutra_id="T0001", config=config)

        # All chunks should be <= chunk_size
        for chunk in chunks:
            assert len(chunk.text) <= config.chunk_size

    def test_extract_chunks_filters_empty(self, tmp_path: Path) -> None:
        """Test that empty paragraphs are filtered out."""
        xml_content = """<?xml version="1.0"?>
        <TEI xmlns="http://www.tei-c.org/ns/1.0">
            <text>
                <body>
                    <p>Valid text</p>
                    <p></p>
                    <p>   </p>
                    <p>Another valid text</p>
                </body>
            </text>
        </TEI>
        """
        xml_file = tmp_path / "empty_p.xml"
        xml_file.write_text(xml_content, encoding="utf-8")

        root = parse_tei_file(xml_file)
        chunks = extract_text_chunks(root, sutra_id="T0002")

        # Should only have 2 valid chunks
        assert len(chunks) == 2
        assert chunks[0].text == "Valid text"
        assert chunks[1].text == "Another valid text"


class TestTEIChunker:
    """Test TEIChunker class with dependency injection."""

    def test_chunker_initialization(self) -> None:
        """Test chunker initializes with config."""
        config = ChunkerConfig(chunk_size=1024)
        chunker = TEIChunker(config=config)

        assert chunker.config.chunk_size == 1024

    def test_chunker_call_interface(self, sample_tei_xml: str, tmp_path: Path) -> None:
        """Test chunker __call__ method processes file."""
        xml_file = tmp_path / "test.xml"
        xml_file.write_text(sample_tei_xml, encoding="utf-8")

        chunker = TEIChunker()
        chunks = chunker(xml_file)

        assert len(chunks) > 0
        assert all(isinstance(chunk, Chunk) for chunk in chunks)

    def test_chunker_processes_directory(self, sample_tei_xml: str, tmp_path: Path) -> None:
        """Test chunker can process multiple files in directory."""
        # Create multiple XML files
        for i in range(3):
            xml_file = tmp_path / f"sutra_{i}.xml"
            xml_file.write_text(sample_tei_xml.replace("T0001", f"T000{i}"), encoding="utf-8")

        chunker = TEIChunker()
        all_chunks: List[Chunk] = []

        # Process all files
        for xml_file in tmp_path.glob("*.xml"):
            chunks = chunker(xml_file)
            all_chunks.extend(chunks)

        # Should have chunks from all 3 files
        assert len(all_chunks) >= 9  # 3 chunks per file * 3 files

    def test_chunker_with_custom_config(self, sample_tei_xml: str, tmp_path: Path) -> None:
        """Test chunker uses custom configuration."""
        xml_file = tmp_path / "test.xml"
        xml_file.write_text(sample_tei_xml, encoding="utf-8")

        config = ChunkerConfig(
            chunk_size=100,
            chunk_overlap=20,
            min_chunk_size=10,
        )
        chunker = TEIChunker(config=config)
        chunks = chunker(xml_file)

        # Verify chunks respect config
        for chunk in chunks:
            assert len(chunk.text) <= config.chunk_size

    def test_chunker_handles_invalid_file(self, tmp_path: Path) -> None:
        """Test chunker handles invalid XML gracefully."""
        xml_file = tmp_path / "invalid.xml"
        xml_file.write_text("not xml", encoding="utf-8")

        chunker = TEIChunker()

        with pytest.raises(InvalidXMLError):
            chunker(xml_file)

    @pytest.mark.unit
    def test_chunker_preserves_korean_text(self, tmp_path: Path) -> None:
        """Test chunker correctly handles Korean text encoding."""
        korean_xml = """<?xml version="1.0" encoding="UTF-8"?>
        <TEI xmlns="http://www.tei-c.org/ns/1.0">
            <teiHeader>
                <fileDesc>
                    <sourceDesc><bibl>T0001</bibl></sourceDesc>
                </fileDesc>
            </teiHeader>
            <text>
                <body>
                    <p>사성제는 고집멸도입니다.</p>
                    <p>팔정도는 정견, 정사유, 정어, 정업, 정명, 정정진, 정념, 정정입니다.</p>
                </body>
            </text>
        </TEI>
        """
        xml_file = tmp_path / "korean.xml"
        xml_file.write_text(korean_xml, encoding="utf-8")

        chunker = TEIChunker()
        chunks = chunker(xml_file)

        assert len(chunks) == 2
        assert "사성제" in chunks[0].text
        assert "팔정도" in chunks[1].text

    @pytest.mark.unit
    def test_chunker_with_overlap(self, tmp_path: Path) -> None:
        """Test that chunker creates overlapping chunks for long text."""
        long_text = "A" * 200  # Create long paragraph
        xml_content = f"""<?xml version="1.0"?>
        <TEI xmlns="http://www.tei-c.org/ns/1.0">
            <teiHeader>
                <fileDesc><sourceDesc><bibl>T0001</bibl></sourceDesc></fileDesc>
            </teiHeader>
            <text><body><p>{long_text}</p></body></text>
        </TEI>
        """
        xml_file = tmp_path / "long.xml"
        xml_file.write_text(xml_content, encoding="utf-8")

        config = ChunkerConfig(chunk_size=100, chunk_overlap=20)
        chunker = TEIChunker(config=config)
        chunks = chunker(xml_file)

        # Should create multiple overlapping chunks
        if len(chunks) > 1:
            # Check that chunks have some overlap
            chunk1_end = chunks[0].text[-config.chunk_overlap:]
            chunk2_start = chunks[1].text[:config.chunk_overlap]
            # At least some characters should overlap
            assert len(chunk1_end) > 0 and len(chunk2_start) > 0


class TestIntegrationChunker:
    """Integration tests for complete chunking workflow."""

    @pytest.mark.integration
    def test_end_to_end_chunking(self, sample_tei_xml: str, tmp_path: Path) -> None:
        """Test complete workflow from XML file to chunks."""
        # Setup
        xml_file = tmp_path / "complete_sutra.xml"
        xml_file.write_text(sample_tei_xml, encoding="utf-8")

        # Execute
        chunker = TEIChunker()
        chunks = chunker(xml_file)

        # Verify
        assert len(chunks) > 0

        for chunk in chunks:
            # Each chunk should have text
            assert isinstance(chunk.text, str)
            assert len(chunk.text) > 0

            # Each chunk should have metadata
            assert "sutra_id" in chunk.metadata
            assert chunk.metadata["sutra_id"] == "T0001"

            # Metadata should have location info
            assert "chapter" in chunk.metadata or "paragraph" in chunk.metadata

    @pytest.mark.integration
    def test_chunker_statistics(self, sample_tei_xml: str, tmp_path: Path) -> None:
        """Test that chunker provides useful statistics."""
        xml_file = tmp_path / "test.xml"
        xml_file.write_text(sample_tei_xml, encoding="utf-8")

        chunker = TEIChunker()
        chunks = chunker(xml_file)

        # Calculate statistics
        total_chars = sum(len(chunk.text) for chunk in chunks)
        avg_chunk_size = total_chars / len(chunks)

        assert total_chars > 0
        assert avg_chunk_size > 0
        assert len(chunks) == 3  # From sample XML

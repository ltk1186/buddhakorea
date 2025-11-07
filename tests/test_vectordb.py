"""Test suite for VectorDB module.

This module tests ChromaDB integration for storing and querying embeddings
with metadata for the Buddhist RAG system.

Following TDD: These tests are written BEFORE implementation.
"""

from pathlib import Path
from typing import Any, Dict, List

import numpy as np
import pytest

from src.vectordb import (
    VectorDB,
    VectorDBConfig,
    ChromaDBAdapter,
    VectorDBError,
    CollectionNotFoundError,
)


class TestVectorDBConfig:
    """Test VectorDBConfig data class."""

    def test_default_config(self) -> None:
        """Test default configuration values."""
        config = VectorDBConfig()

        assert config.collection_name == "taisho_canon"
        assert config.persist_directory is None
        assert config.distance_metric == "cosine"

    def test_custom_config(self, tmp_path: Path) -> None:
        """Test custom configuration."""
        persist_dir = tmp_path / "chroma"
        config = VectorDBConfig(
            collection_name="test_collection",
            persist_directory=str(persist_dir),
            distance_metric="l2",
        )

        assert config.collection_name == "test_collection"
        assert config.persist_directory == str(persist_dir)
        assert config.distance_metric == "l2"


class TestChromaDBAdapter:
    """Test ChromaDB adapter."""

    @pytest.mark.unit
    def test_adapter_initialization(self, tmp_path: Path) -> None:
        """Test ChromaDB adapter initializes correctly."""
        persist_dir = tmp_path / "chroma"
        adapter = ChromaDBAdapter(
            collection_name="test",
            persist_directory=str(persist_dir),
        )

        assert adapter.collection_name == "test"
        assert adapter.persist_directory == str(persist_dir)

    @pytest.mark.unit
    def test_adapter_creates_collection(self, tmp_path: Path) -> None:
        """Test that adapter creates collection on initialization."""
        persist_dir = tmp_path / "chroma"
        adapter = ChromaDBAdapter(
            collection_name="test",
            persist_directory=str(persist_dir),
        )

        # Collection should be created
        assert adapter.collection is not None
        assert adapter.collection.name == "test"

    @pytest.mark.unit
    def test_add_documents_with_embeddings(self, tmp_path: Path) -> None:
        """Test adding documents with embeddings."""
        persist_dir = tmp_path / "chroma"
        adapter = ChromaDBAdapter(
            collection_name="test",
            persist_directory=str(persist_dir),
        )

        # Add documents
        ids = ["id1", "id2", "id3"]
        texts = ["Text 1", "Text 2", "Text 3"]
        embeddings = np.random.rand(3, 384).astype(np.float32)
        metadatas = [
            {"sutra_id": "T0001", "chapter": "1"},
            {"sutra_id": "T0001", "chapter": "2"},
            {"sutra_id": "T0002", "chapter": "1"},
        ]

        adapter.add(
            ids=ids,
            embeddings=embeddings,
            texts=texts,
            metadatas=metadatas,
        )

        # Verify documents were added
        count = adapter.count()
        assert count == 3

    @pytest.mark.unit
    def test_add_documents_auto_generates_ids(self, tmp_path: Path) -> None:
        """Test that adapter auto-generates IDs if not provided."""
        persist_dir = tmp_path / "chroma"
        adapter = ChromaDBAdapter(
            collection_name="test",
            persist_directory=str(persist_dir),
        )

        texts = ["Text 1", "Text 2"]
        embeddings = np.random.rand(2, 384).astype(np.float32)

        result_ids = adapter.add(
            embeddings=embeddings,
            texts=texts,
        )

        # Should return generated IDs
        assert len(result_ids) == 2
        assert all(isinstance(id, str) for id in result_ids)

    @pytest.mark.unit
    def test_query_by_embedding(self, tmp_path: Path) -> None:
        """Test querying by embedding vector."""
        persist_dir = tmp_path / "chroma"
        adapter = ChromaDBAdapter(
            collection_name="test",
            persist_directory=str(persist_dir),
        )

        # Add documents
        embeddings = np.array([
            [1.0] * 384,
            [2.0] * 384,
            [3.0] * 384,
        ], dtype=np.float32)
        texts = ["One", "Two", "Three"]
        adapter.add(embeddings=embeddings, texts=texts)

        # Query with similar vector
        query_embedding = np.array([[1.1] * 384], dtype=np.float32)
        results = adapter.query(
            query_embeddings=query_embedding,
            n_results=2,
        )

        # Should return closest matches
        assert len(results["ids"][0]) == 2
        # Check that "One" is in the results (order may vary)
        all_docs = results["documents"][0]
        assert any("One" in doc or "Two" in doc or "Three" in doc for doc in all_docs)

    @pytest.mark.unit
    def test_query_with_metadata_filter(self, tmp_path: Path) -> None:
        """Test querying with metadata filtering."""
        persist_dir = tmp_path / "chroma"
        adapter = ChromaDBAdapter(
            collection_name="test",
            persist_directory=str(persist_dir),
        )

        # Add documents with different sutras
        embeddings = np.random.rand(3, 384).astype(np.float32)
        texts = ["Text 1", "Text 2", "Text 3"]
        metadatas = [
            {"sutra_id": "T0001"},
            {"sutra_id": "T0002"},
            {"sutra_id": "T0001"},
        ]
        adapter.add(embeddings=embeddings, texts=texts, metadatas=metadatas)

        # Query with filter
        query_embedding = np.random.rand(1, 384).astype(np.float32)
        results = adapter.query(
            query_embeddings=query_embedding,
            n_results=10,
            where={"sutra_id": "T0001"},
        )

        # Should only return T0001 documents
        assert len(results["ids"][0]) == 2
        for metadata in results["metadatas"][0]:
            assert metadata["sutra_id"] == "T0001"

    @pytest.mark.unit
    def test_persistence(self, tmp_path: Path) -> None:
        """Test that data persists across adapter instances."""
        persist_dir = tmp_path / "chroma"

        # Create first adapter and add data
        adapter1 = ChromaDBAdapter(
            collection_name="test",
            persist_directory=str(persist_dir),
        )
        embeddings = np.random.rand(2, 384).astype(np.float32)
        texts = ["Persistent 1", "Persistent 2"]
        adapter1.add(embeddings=embeddings, texts=texts)

        # Create second adapter with same directory
        adapter2 = ChromaDBAdapter(
            collection_name="test",
            persist_directory=str(persist_dir),
        )

        # Data should still be there
        count = adapter2.count()
        assert count == 2

    @pytest.mark.unit
    def test_delete_collection(self, tmp_path: Path) -> None:
        """Test deleting collection."""
        persist_dir = tmp_path / "chroma"
        adapter = ChromaDBAdapter(
            collection_name="test",
            persist_directory=str(persist_dir),
        )

        # Add some data
        embeddings = np.random.rand(2, 384).astype(np.float32)
        adapter.add(embeddings=embeddings, texts=["A", "B"])

        # Delete collection
        adapter.delete_collection()

        # Collection should be gone
        assert adapter.collection is None

    @pytest.mark.unit
    def test_get_by_ids(self, tmp_path: Path) -> None:
        """Test retrieving documents by IDs."""
        persist_dir = tmp_path / "chroma"
        adapter = ChromaDBAdapter(
            collection_name="test",
            persist_directory=str(persist_dir),
        )

        # Add documents with known IDs
        ids = ["doc1", "doc2", "doc3"]
        embeddings = np.random.rand(3, 384).astype(np.float32)
        texts = ["First", "Second", "Third"]
        adapter.add(ids=ids, embeddings=embeddings, texts=texts)

        # Get specific documents
        results = adapter.get(ids=["doc1", "doc3"])

        assert len(results["ids"]) == 2
        assert "doc1" in results["ids"]
        assert "doc3" in results["ids"]

    @pytest.mark.unit
    def test_update_documents(self, tmp_path: Path) -> None:
        """Test updating existing documents."""
        persist_dir = tmp_path / "chroma"
        adapter = ChromaDBAdapter(
            collection_name="test",
            persist_directory=str(persist_dir),
        )

        # Add initial document
        ids = ["doc1"]
        embeddings = np.random.rand(1, 384).astype(np.float32)
        texts = ["Original text"]
        adapter.add(ids=ids, embeddings=embeddings, texts=texts)

        # Update the document
        new_embeddings = np.random.rand(1, 384).astype(np.float32)
        new_texts = ["Updated text"]
        adapter.update(ids=ids, embeddings=new_embeddings, texts=new_texts)

        # Get the document
        results = adapter.get(ids=["doc1"])
        assert results["documents"][0] == "Updated text"


class TestVectorDB:
    """Test VectorDB class with dependency injection."""

    @pytest.mark.unit
    def test_vectordb_initialization(self, tmp_path: Path) -> None:
        """Test VectorDB initializes with config."""
        config = VectorDBConfig(
            collection_name="test",
            persist_directory=str(tmp_path / "chroma"),
        )
        vectordb = VectorDB.from_config(config)

        assert vectordb.config == config

    @pytest.mark.unit
    def test_add_chunks_with_embeddings(
        self, tmp_path: Path, sample_chunks: List[Dict[str, Any]]
    ) -> None:
        """Test adding chunks with embeddings."""
        config = VectorDBConfig(
            collection_name="test",
            persist_directory=str(tmp_path / "chroma"),
        )
        vectordb = VectorDB.from_config(config)

        # Create embeddings for chunks
        embeddings = np.random.rand(len(sample_chunks), 384).astype(np.float32)

        # Add chunks
        ids = vectordb.add_chunks(
            chunks=sample_chunks,
            embeddings=embeddings,
        )

        assert len(ids) == len(sample_chunks)

    @pytest.mark.unit
    def test_search_by_embedding(
        self, tmp_path: Path, sample_chunks: List[Dict[str, Any]]
    ) -> None:
        """Test searching by embedding vector."""
        config = VectorDBConfig(
            collection_name="test",
            persist_directory=str(tmp_path / "chroma"),
        )
        vectordb = VectorDB.from_config(config)

        # Add chunks
        embeddings = np.random.rand(len(sample_chunks), 384).astype(np.float32)
        vectordb.add_chunks(chunks=sample_chunks, embeddings=embeddings)

        # Search
        query_embedding = np.random.rand(384).astype(np.float32)
        results = vectordb.search(query_embedding=query_embedding, top_k=2)

        assert len(results) == 2
        assert all("text" in r for r in results)
        assert all("metadata" in r for r in results)
        assert all("score" in r for r in results)

    @pytest.mark.unit
    def test_search_with_metadata_filter(
        self, tmp_path: Path, sample_chunks: List[Dict[str, Any]]
    ) -> None:
        """Test searching with metadata filtering."""
        config = VectorDBConfig(
            collection_name="test",
            persist_directory=str(tmp_path / "chroma"),
        )
        vectordb = VectorDB.from_config(config)

        # Add chunks
        embeddings = np.random.rand(len(sample_chunks), 384).astype(np.float32)
        vectordb.add_chunks(chunks=sample_chunks, embeddings=embeddings)

        # Search with filter
        query_embedding = np.random.rand(384).astype(np.float32)
        results = vectordb.search(
            query_embedding=query_embedding,
            top_k=10,
            filter_metadata={"sutra_id": "T0001"},
        )

        # All results should be from T0001
        for result in results:
            assert result["metadata"]["sutra_id"] == "T0001"

    @pytest.mark.unit
    def test_get_collection_stats(self, tmp_path: Path) -> None:
        """Test getting collection statistics."""
        config = VectorDBConfig(
            collection_name="test",
            persist_directory=str(tmp_path / "chroma"),
        )
        vectordb = VectorDB.from_config(config)

        # Add some data
        chunks = [{"text": f"Text {i}", "metadata": {}} for i in range(5)]
        embeddings = np.random.rand(5, 384).astype(np.float32)
        vectordb.add_chunks(chunks=chunks, embeddings=embeddings)

        # Get stats
        stats = vectordb.get_stats()

        assert stats["count"] == 5
        assert stats["collection_name"] == "test"

    @pytest.mark.unit
    def test_clear_collection(self, tmp_path: Path) -> None:
        """Test clearing all data from collection."""
        config = VectorDBConfig(
            collection_name="test",
            persist_directory=str(tmp_path / "chroma"),
        )
        vectordb = VectorDB.from_config(config)

        # Add data
        chunks = [{"text": "Test", "metadata": {}}]
        embeddings = np.random.rand(1, 384).astype(np.float32)
        vectordb.add_chunks(chunks=chunks, embeddings=embeddings)

        # Clear
        vectordb.clear()

        # Should be empty
        stats = vectordb.get_stats()
        assert stats["count"] == 0

    @pytest.mark.unit
    def test_vectordb_handles_empty_search(self, tmp_path: Path) -> None:
        """Test searching in empty collection."""
        config = VectorDBConfig(
            collection_name="test",
            persist_directory=str(tmp_path / "chroma"),
        )
        vectordb = VectorDB.from_config(config)

        # Search empty collection
        query_embedding = np.random.rand(384).astype(np.float32)
        results = vectordb.search(query_embedding=query_embedding, top_k=5)

        assert results == []

    @pytest.mark.unit
    def test_vectordb_validates_embedding_dimension(self, tmp_path: Path) -> None:
        """Test that VectorDB validates embedding dimensions."""
        config = VectorDBConfig(
            collection_name="test",
            persist_directory=str(tmp_path / "chroma"),
        )
        vectordb = VectorDB.from_config(config)

        # Try to add with wrong dimension
        chunks = [{"text": "Test", "metadata": {}}]
        wrong_embeddings = np.random.rand(1, 100).astype(np.float32)  # Wrong dim

        # Add first embedding (sets expected dimension)
        correct_embeddings = np.random.rand(1, 384).astype(np.float32)
        vectordb.add_chunks(chunks=chunks, embeddings=correct_embeddings)

        # Now try to add with different dimension
        with pytest.raises(VectorDBError):
            vectordb.add_chunks(chunks=chunks, embeddings=wrong_embeddings)


class TestIntegrationVectorDB:
    """Integration tests for complete VectorDB workflow."""

    @pytest.mark.integration
    def test_end_to_end_workflow(
        self, tmp_path: Path, sample_chunks: List[Dict[str, Any]]
    ) -> None:
        """Test complete workflow: add, search, filter."""
        config = VectorDBConfig(
            collection_name="test",
            persist_directory=str(tmp_path / "chroma"),
        )
        vectordb = VectorDB.from_config(config)

        # Add chunks
        embeddings = np.random.rand(len(sample_chunks), 384).astype(np.float32)
        ids = vectordb.add_chunks(chunks=sample_chunks, embeddings=embeddings)

        assert len(ids) == len(sample_chunks)

        # Search all
        query = np.random.rand(384).astype(np.float32)
        all_results = vectordb.search(query_embedding=query, top_k=10)
        assert len(all_results) == len(sample_chunks)

        # Search with filter
        filtered_results = vectordb.search(
            query_embedding=query,
            top_k=10,
            filter_metadata={"chapter": "1"},
        )
        assert len(filtered_results) <= len(all_results)

    @pytest.mark.integration
    def test_persistence_workflow(self, tmp_path: Path) -> None:
        """Test that data persists across VectorDB instances."""
        persist_dir = tmp_path / "chroma"
        config = VectorDBConfig(
            collection_name="test",
            persist_directory=str(persist_dir),
        )

        # First instance: add data
        vectordb1 = VectorDB.from_config(config)
        chunks = [
            {"text": "Persistent data", "metadata": {"test": "value"}},
        ]
        embeddings = np.random.rand(1, 384).astype(np.float32)
        vectordb1.add_chunks(chunks=chunks, embeddings=embeddings)

        # Second instance: verify data exists
        vectordb2 = VectorDB.from_config(config)
        stats = vectordb2.get_stats()
        assert stats["count"] == 1

    @pytest.mark.integration
    def test_large_batch_insertion(self, tmp_path: Path) -> None:
        """Test inserting large batch of documents."""
        config = VectorDBConfig(
            collection_name="test",
            persist_directory=str(tmp_path / "chroma"),
        )
        vectordb = VectorDB.from_config(config)

        # Create 1000 chunks
        n_chunks = 1000
        chunks = [
            {"text": f"Text {i}", "metadata": {"index": str(i)}}
            for i in range(n_chunks)
        ]
        embeddings = np.random.rand(n_chunks, 384).astype(np.float32)

        # Add all at once
        ids = vectordb.add_chunks(chunks=chunks, embeddings=embeddings)

        assert len(ids) == n_chunks

        # Verify count
        stats = vectordb.get_stats()
        assert stats["count"] == n_chunks

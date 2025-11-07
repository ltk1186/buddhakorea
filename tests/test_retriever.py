"""Test suite for Retriever module.

This module tests semantic search retrieval using embeddings and vector database
for the Buddhist RAG system.

Following TDD: These tests are written BEFORE implementation.
"""

from typing import Any, Dict, List
from unittest.mock import Mock

import numpy as np
import pytest

from src.retriever import (
    Retriever,
    RetrieverConfig,
    RetrievalResult,
    RetrievalError,
)


class TestRetrieverConfig:
    """Test RetrieverConfig data class."""

    def test_default_config(self) -> None:
        """Test default configuration values."""
        config = RetrieverConfig()

        assert config.top_k == 5
        assert config.similarity_threshold == 0.0
        assert config.enable_reranking is False

    def test_custom_config(self) -> None:
        """Test custom configuration."""
        config = RetrieverConfig(
            top_k=10,
            similarity_threshold=0.7,
            enable_reranking=True,
        )

        assert config.top_k == 10
        assert config.similarity_threshold == 0.7
        assert config.enable_reranking is True


class TestRetrievalResult:
    """Test RetrievalResult data class."""

    def test_result_creation(self) -> None:
        """Test creating retrieval result."""
        result = RetrievalResult(
            text="Buddhist teaching text",
            metadata={"sutra_id": "T0001", "chapter": "1"},
            score=0.95,
            rank=1,
        )

        assert result.text == "Buddhist teaching text"
        assert result.metadata["sutra_id"] == "T0001"
        assert result.score == 0.95
        assert result.rank == 1


class TestRetriever:
    """Test Retriever class."""

    @pytest.mark.unit
    def test_retriever_initialization(self, mocker: Mock) -> None:
        """Test retriever initializes with embedder and vectordb."""
        mock_embedder = mocker.Mock()
        mock_vectordb = mocker.Mock()
        config = RetrieverConfig()

        retriever = Retriever(
            embedder=mock_embedder,
            vectordb=mock_vectordb,
            config=config,
        )

        assert retriever.embedder == mock_embedder
        assert retriever.vectordb == mock_vectordb
        assert retriever.config == config

    @pytest.mark.unit
    def test_retrieve_by_text_query(self, mocker: Mock) -> None:
        """Test retrieving by text query."""
        # Mock embedder
        query_embedding = np.array([0.1] * 384, dtype=np.float32)
        mock_embedder = mocker.Mock()
        mock_embedder.return_value = query_embedding.reshape(1, -1)

        # Mock vectordb results
        mock_results = [
            {
                "text": "Result 1",
                "metadata": {"sutra_id": "T0001"},
                "score": 0.95,
            },
            {
                "text": "Result 2",
                "metadata": {"sutra_id": "T0002"},
                "score": 0.85,
            },
        ]
        mock_vectordb = mocker.Mock()
        mock_vectordb.search.return_value = mock_results

        # Retrieve
        config = RetrieverConfig(top_k=2)
        retriever = Retriever(
            embedder=mock_embedder,
            vectordb=mock_vectordb,
            config=config,
        )

        results = retriever.retrieve("What is Four Noble Truths?")

        # Verify
        assert len(results) == 2
        assert all(isinstance(r, RetrievalResult) for r in results)
        assert results[0].text == "Result 1"
        assert results[0].rank == 1
        assert results[1].rank == 2

    @pytest.mark.unit
    def test_retrieve_filters_by_similarity_threshold(self, mocker: Mock) -> None:
        """Test that retriever filters results below similarity threshold."""
        mock_embedder = mocker.Mock()
        mock_embedder.return_value = np.random.rand(1, 384).astype(np.float32)

        # Mock results with varying scores
        mock_results = [
            {"text": "High score", "metadata": {}, "score": 0.95},
            {"text": "Medium score", "metadata": {}, "score": 0.75},
            {"text": "Low score", "metadata": {}, "score": 0.45},
        ]
        mock_vectordb = mocker.Mock()
        mock_vectordb.search.return_value = mock_results

        # Retrieve with threshold
        config = RetrieverConfig(top_k=10, similarity_threshold=0.7)
        retriever = Retriever(
            embedder=mock_embedder,
            vectordb=mock_vectordb,
            config=config,
        )

        results = retriever.retrieve("test query")

        # Only results above 0.7 should be returned
        assert len(results) == 2
        assert all(r.score >= 0.7 for r in results)

    @pytest.mark.unit
    def test_retrieve_with_metadata_filter(self, mocker: Mock) -> None:
        """Test retrieving with metadata filtering."""
        mock_embedder = mocker.Mock()
        mock_embedder.return_value = np.random.rand(1, 384).astype(np.float32)

        mock_vectordb = mocker.Mock()
        mock_vectordb.search.return_value = []

        config = RetrieverConfig()
        retriever = Retriever(
            embedder=mock_embedder,
            vectordb=mock_vectordb,
            config=config,
        )

        # Retrieve with filter
        filter_metadata = {"sutra_id": "T0001"}
        retriever.retrieve("test", filter_metadata=filter_metadata)

        # Verify filter was passed to vectordb
        mock_vectordb.search.assert_called_once()
        call_kwargs = mock_vectordb.search.call_args[1]
        assert call_kwargs["filter_metadata"] == filter_metadata

    @pytest.mark.unit
    def test_retrieve_handles_empty_results(self, mocker: Mock) -> None:
        """Test retriever handles empty results gracefully."""
        mock_embedder = mocker.Mock()
        mock_embedder.return_value = np.random.rand(1, 384).astype(np.float32)

        mock_vectordb = mocker.Mock()
        mock_vectordb.search.return_value = []

        config = RetrieverConfig()
        retriever = Retriever(
            embedder=mock_embedder,
            vectordb=mock_vectordb,
            config=config,
        )

        results = retriever.retrieve("no results query")

        assert results == []

    @pytest.mark.unit
    def test_retrieve_respects_top_k(self, mocker: Mock) -> None:
        """Test that retriever respects top_k limit."""
        mock_embedder = mocker.Mock()
        mock_embedder.return_value = np.random.rand(1, 384).astype(np.float32)

        # Mock vectordb to return only top_k results
        def mock_search(query_embedding, top_k, filter_metadata=None):
            all_results = [
                {"text": f"Result {i}", "metadata": {}, "score": 1.0 - i * 0.05}
                for i in range(10)
            ]
            # Return only top_k results (simulating real vectordb behavior)
            return all_results[:top_k]

        mock_vectordb = mocker.Mock()
        mock_vectordb.search.side_effect = mock_search

        # Request only top 3
        config = RetrieverConfig(top_k=3)
        retriever = Retriever(
            embedder=mock_embedder,
            vectordb=mock_vectordb,
            config=config,
        )

        results = retriever.retrieve("test query")

        # Should respect top_k
        assert len(results) == 3

    @pytest.mark.unit
    def test_retrieve_with_korean_query(self, mocker: Mock) -> None:
        """Test retrieval with Korean language query."""
        mock_embedder = mocker.Mock()
        mock_embedder.return_value = np.random.rand(1, 384).astype(np.float32)

        mock_results = [
            {
                "text": "사성제에 대한 가르침",
                "metadata": {"sutra_id": "T0001"},
                "score": 0.9,
            }
        ]
        mock_vectordb = mocker.Mock()
        mock_vectordb.search.return_value = mock_results

        config = RetrieverConfig()
        retriever = Retriever(
            embedder=mock_embedder,
            vectordb=mock_vectordb,
            config=config,
        )

        # Query in Korean
        results = retriever.retrieve("사성제란 무엇입니까?")

        # Verify embedder was called with Korean text
        mock_embedder.assert_called_once_with(["사성제란 무엇입니까?"])
        assert len(results) == 1
        assert "사성제" in results[0].text

    @pytest.mark.unit
    def test_retrieve_handles_embedder_error(self, mocker: Mock) -> None:
        """Test retriever handles embedder errors."""
        mock_embedder = mocker.Mock()
        mock_embedder.side_effect = Exception("Embedding failed")

        mock_vectordb = mocker.Mock()

        config = RetrieverConfig()
        retriever = Retriever(
            embedder=mock_embedder,
            vectordb=mock_vectordb,
            config=config,
        )

        with pytest.raises(RetrievalError) as exc_info:
            retriever.retrieve("test query")

        assert "Embedding failed" in str(exc_info.value)

    @pytest.mark.unit
    def test_retrieve_handles_vectordb_error(self, mocker: Mock) -> None:
        """Test retriever handles vectordb errors."""
        mock_embedder = mocker.Mock()
        mock_embedder.return_value = np.random.rand(1, 384).astype(np.float32)

        mock_vectordb = mocker.Mock()
        mock_vectordb.search.side_effect = Exception("Search failed")

        config = RetrieverConfig()
        retriever = Retriever(
            embedder=mock_embedder,
            vectordb=mock_vectordb,
            config=config,
        )

        with pytest.raises(RetrievalError):
            retriever.retrieve("test query")

    @pytest.mark.unit
    def test_retrieve_assigns_correct_ranks(self, mocker: Mock) -> None:
        """Test that results are ranked correctly."""
        mock_embedder = mocker.Mock()
        mock_embedder.return_value = np.random.rand(1, 384).astype(np.float32)

        # Results in descending score order
        mock_results = [
            {"text": "Best", "metadata": {}, "score": 0.95},
            {"text": "Second", "metadata": {}, "score": 0.85},
            {"text": "Third", "metadata": {}, "score": 0.75},
        ]
        mock_vectordb = mocker.Mock()
        mock_vectordb.search.return_value = mock_results

        config = RetrieverConfig()
        retriever = Retriever(
            embedder=mock_embedder,
            vectordb=mock_vectordb,
            config=config,
        )

        results = retriever.retrieve("test")

        # Check ranks
        assert results[0].rank == 1
        assert results[1].rank == 2
        assert results[2].rank == 3

    @pytest.mark.unit
    def test_retrieve_by_embedding_directly(self, mocker: Mock) -> None:
        """Test retrieving with pre-computed embedding."""
        mock_embedder = mocker.Mock()

        mock_results = [
            {"text": "Result", "metadata": {}, "score": 0.9}
        ]
        mock_vectordb = mocker.Mock()
        mock_vectordb.search.return_value = mock_results

        config = RetrieverConfig()
        retriever = Retriever(
            embedder=mock_embedder,
            vectordb=mock_vectordb,
            config=config,
        )

        # Provide embedding directly
        query_embedding = np.random.rand(384).astype(np.float32)
        results = retriever.retrieve_by_embedding(query_embedding)

        # Embedder should NOT be called
        mock_embedder.assert_not_called()
        assert len(results) == 1


class TestIntegrationRetriever:
    """Integration tests for complete retrieval workflow."""

    @pytest.mark.integration
    def test_end_to_end_retrieval(
        self, mocker: Mock, sample_chunks: List[Dict[str, Any]]
    ) -> None:
        """Test complete retrieval workflow."""
        # Mock embedder that returns consistent embeddings
        def mock_embed(texts):
            # Return different embeddings for different texts
            if "Four Noble Truths" in texts[0]:
                return np.array([[0.9] * 384], dtype=np.float32)
            else:
                return np.array([[0.1] * 384], dtype=np.float32)

        mock_embedder = mocker.Mock(side_effect=mock_embed)

        # Mock vectordb with sample data
        mock_vectordb = mocker.Mock()
        mock_vectordb.search.return_value = [
            {
                "text": sample_chunks[0]["text"],
                "metadata": sample_chunks[0]["metadata"],
                "score": 0.92,
            }
        ]

        config = RetrieverConfig(top_k=5)
        retriever = Retriever(
            embedder=mock_embedder,
            vectordb=mock_vectordb,
            config=config,
        )

        # Retrieve
        results = retriever.retrieve("What are the Four Noble Truths?")

        assert len(results) > 0
        assert isinstance(results[0], RetrievalResult)
        assert results[0].rank == 1

    @pytest.mark.integration
    def test_retrieval_with_filtering_and_threshold(self, mocker: Mock) -> None:
        """Test retrieval with both filtering and threshold."""
        mock_embedder = mocker.Mock()
        mock_embedder.return_value = np.random.rand(1, 384).astype(np.float32)

        # Mock vectordb to respect metadata filtering
        def mock_search(query_embedding, top_k, filter_metadata=None):
            all_results = [
                {
                    "text": "T0001 high",
                    "metadata": {"sutra_id": "T0001"},
                    "score": 0.9,
                },
                {
                    "text": "T0001 low",
                    "metadata": {"sutra_id": "T0001"},
                    "score": 0.5,
                },
                {
                    "text": "T0002 high",
                    "metadata": {"sutra_id": "T0002"},
                    "score": 0.85,
                },
            ]
            # Apply metadata filter if provided
            if filter_metadata:
                filtered = [
                    r for r in all_results
                    if all(r["metadata"].get(k) == v for k, v in filter_metadata.items())
                ]
                return filtered
            return all_results

        mock_vectordb = mocker.Mock()
        mock_vectordb.search.side_effect = mock_search

        config = RetrieverConfig(similarity_threshold=0.7)
        retriever = Retriever(
            embedder=mock_embedder,
            vectordb=mock_vectordb,
            config=config,
        )

        results = retriever.retrieve(
            query="test",
            filter_metadata={"sutra_id": "T0001"},
        )

        # Should filter by metadata AND threshold
        assert len(results) == 1
        assert results[0].metadata["sutra_id"] == "T0001"
        assert results[0].score >= 0.7

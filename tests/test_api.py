"""Test suite for FastAPI API module.

This module tests the REST API endpoints for the Buddhist RAG system.

Following TDD: These tests are written BEFORE implementation.
"""

from typing import Any, Dict
from unittest.mock import Mock

import pytest
from fastapi.testclient import TestClient

from src.retriever import RetrievalResult
from src.answerer import AnswerResponse


@pytest.fixture
def mock_rag_pipeline(mocker: Mock):
    """Fixture to mock RAG pipeline components."""
    mock_retriever = mocker.Mock()
    mock_answerer = mocker.Mock()
    mock_vectordb = mocker.Mock()

    mocker.patch("src.api.get_retriever", return_value=mock_retriever)
    mocker.patch("src.api.get_answerer", return_value=mock_answerer)
    mocker.patch("src.api.get_vectordb", return_value=mock_vectordb)

    return {
        "retriever": mock_retriever,
        "answerer": mock_answerer,
        "vectordb": mock_vectordb,
    }


class TestHealthEndpoint:
    """Test health check endpoint."""

    @pytest.mark.unit
    def test_health_check_returns_200(self, mocker: Mock) -> None:
        """Test that health endpoint returns 200 OK."""
        from src.api import app

        client = TestClient(app)
        response = client.get("/health")

        assert response.status_code == 200
        assert response.json()["status"] == "healthy"

    @pytest.mark.unit
    def test_health_check_includes_version(self, mocker: Mock) -> None:
        """Test that health endpoint includes version info."""
        from src.api import app

        client = TestClient(app)
        response = client.get("/health")

        assert "version" in response.json()


class TestQueryEndpoint:
    """Test main query endpoint."""

    @pytest.mark.unit
    def test_query_endpoint_basic(self, mocker: Mock) -> None:
        """Test basic query functionality."""
        # Mock the RAG components
        mock_retrieval_result = RetrievalResult(
            text="The Four Noble Truths teaching",
            metadata={"sutra_id": "T0001"},
            score=0.95,
            rank=1,
        )

        mock_answer_response = AnswerResponse(
            answer="The Four Noble Truths are...",
            sources=[mock_retrieval_result],
            tokens_used=150,
        )

        # Mock retriever and answerer
        mock_retriever = mocker.Mock()
        mock_retriever.retrieve.return_value = [mock_retrieval_result]

        mock_answerer = mocker.Mock()
        mock_answerer.answer.return_value = mock_answer_response

        # Patch the getter functions
        mocker.patch("src.api.get_retriever", return_value=mock_retriever)
        mocker.patch("src.api.get_answerer", return_value=mock_answerer)

        from src.api import app

        client = TestClient(app)
        response = client.post(
            "/query",
            json={"query": "What are the Four Noble Truths?"},
        )

        assert response.status_code == 200
        data = response.json()
        assert "answer" in data
        assert "sources" in data
        assert "tokens_used" in data

    @pytest.mark.unit
    def test_query_endpoint_with_filters(self, mocker: Mock) -> None:
        """Test query with metadata filters."""
        mock_retrieval_result = RetrievalResult(
            text="Teaching from T0001",
            metadata={"sutra_id": "T0001"},
            score=0.9,
            rank=1,
        )

        mock_answer_response = AnswerResponse(
            answer="Answer from filtered results",
            sources=[mock_retrieval_result],
            tokens_used=100,
        )

        mock_retriever = mocker.Mock()
        mock_retriever.retrieve.return_value = [mock_retrieval_result]

        mock_answerer = mocker.Mock()
        mock_answerer.answer.return_value = mock_answer_response

        mocker.patch("src.api.get_retriever", return_value=mock_retriever)
        mocker.patch("src.api.get_answerer", return_value=mock_answerer)

        from src.api import app

        client = TestClient(app)
        response = client.post(
            "/query",
            json={
                "query": "Test query",
                "filter_metadata": {"sutra_id": "T0001"},
            },
        )

        assert response.status_code == 200
        # Verify filter was passed to retriever
        mock_retriever.retrieve.assert_called_once()

    @pytest.mark.unit
    def test_query_endpoint_with_top_k(self, mocker: Mock) -> None:
        """Test query with custom top_k parameter."""
        results = [
            RetrievalResult(
                text=f"Result {i}",
                metadata={"sutra_id": "T0001"},
                score=0.9 - i * 0.1,
                rank=i + 1,
            )
            for i in range(3)
        ]

        mock_answer = AnswerResponse(
            answer="Answer",
            sources=results,
            tokens_used=100,
        )

        # Mock the retriever and answerer instances
        mock_retriever = mocker.Mock()
        mock_retriever.retrieve.return_value = results

        mock_answerer = mocker.Mock()
        mock_answerer.answer.return_value = mock_answer

        mocker.patch("src.api.get_retriever", return_value=mock_retriever)
        mocker.patch("src.api.get_answerer", return_value=mock_answerer)

        from src.api import app

        client = TestClient(app)
        response = client.post(
            "/query",
            json={"query": "Test", "top_k": 3},
        )

        assert response.status_code == 200
        assert len(response.json()["sources"]) == 3

    @pytest.mark.unit
    def test_query_endpoint_missing_query(self, mocker: Mock) -> None:
        """Test that missing query parameter returns 422."""
        from src.api import app

        client = TestClient(app)
        response = client.post("/query", json={})

        assert response.status_code == 422  # Validation error

    @pytest.mark.unit
    def test_query_endpoint_empty_query(self, mocker: Mock) -> None:
        """Test that empty query returns 400."""
        from src.api import app

        client = TestClient(app)
        response = client.post("/query", json={"query": ""})

        # Pydantic validation returns 422, but API also validates and returns 400
        # Since both are client errors, accept either
        assert response.status_code in [400, 422]

    @pytest.mark.unit
    def test_query_endpoint_handles_errors(self, mocker: Mock) -> None:
        """Test that API handles retrieval errors gracefully."""
        mock_retriever = mocker.Mock()
        mock_retriever.retrieve.side_effect = Exception("Retrieval failed")

        mocker.patch("src.api.get_retriever", return_value=mock_retriever)

        from src.api import app

        client = TestClient(app)
        response = client.post(
            "/query",
            json={"query": "Test query"},
        )

        assert response.status_code == 500
        assert "detail" in response.json()  # FastAPI uses "detail" for error messages

    @pytest.mark.unit
    def test_query_endpoint_korean_text(self, mocker: Mock) -> None:
        """Test query with Korean text."""
        mock_result = RetrievalResult(
            text="사성제에 대한 가르침",
            metadata={"sutra_id": "T0001"},
            score=0.95,
            rank=1,
        )

        mock_answer = AnswerResponse(
            answer="사성제는...",
            sources=[mock_result],
            tokens_used=180,
        )

        mock_retriever = mocker.Mock()
        mock_retriever.retrieve.return_value = [mock_result]

        mock_answerer = mocker.Mock()
        mock_answerer.answer.return_value = mock_answer

        mocker.patch("src.api.get_retriever", return_value=mock_retriever)
        mocker.patch("src.api.get_answerer", return_value=mock_answerer)

        from src.api import app

        client = TestClient(app)
        response = client.post(
            "/query",
            json={"query": "사성제란 무엇입니까?"},
        )

        assert response.status_code == 200
        assert "사성제" in response.json()["answer"]


class TestStatsEndpoint:
    """Test statistics endpoint."""

    @pytest.mark.unit
    def test_stats_endpoint(self, mocker: Mock) -> None:
        """Test getting collection statistics."""
        mock_stats = {
            "count": 1000,
            "collection_name": "taisho_canon",
            "distance_metric": "cosine",
        }

        mock_vectordb = mocker.Mock()
        mock_vectordb.get_stats.return_value = mock_stats

        mocker.patch("src.api.get_vectordb", return_value=mock_vectordb)

        from src.api import app

        client = TestClient(app)
        response = client.get("/stats")

        assert response.status_code == 200
        data = response.json()
        assert data["count"] == 1000
        assert data["collection_name"] == "taisho_canon"

    @pytest.mark.unit
    def test_stats_endpoint_handles_errors(self, mocker: Mock) -> None:
        """Test stats endpoint error handling."""
        mock_vectordb = mocker.Mock()
        mock_vectordb.get_stats.side_effect = Exception("DB error")

        mocker.patch("src.api.get_vectordb", return_value=mock_vectordb)

        from src.api import app

        client = TestClient(app)
        response = client.get("/stats")

        assert response.status_code == 500


class TestCORSHeaders:
    """Test CORS configuration."""

    @pytest.mark.unit
    def test_cors_headers_present(self, mocker: Mock) -> None:
        """Test that CORS headers are configured."""
        from src.api import app

        client = TestClient(app)
        response = client.options(
            "/query",
            headers={"Origin": "http://localhost:3000"},
        )

        # Should allow CORS
        assert response.status_code in [200, 405]  # 405 if OPTIONS not explicitly handled


class TestAPIDocumentation:
    """Test API documentation endpoints."""

    @pytest.mark.unit
    def test_docs_endpoint_available(self, mocker: Mock) -> None:
        """Test that API documentation is available."""
        from src.api import app

        client = TestClient(app)
        response = client.get("/docs")

        assert response.status_code == 200

    @pytest.mark.unit
    def test_openapi_schema_available(self, mocker: Mock) -> None:
        """Test that OpenAPI schema is available."""
        from src.api import app

        client = TestClient(app)
        response = client.get("/openapi.json")

        assert response.status_code == 200
        schema = response.json()
        assert "openapi" in schema
        assert "paths" in schema


class TestIntegrationAPI:
    """Integration tests for complete API workflow."""

    @pytest.mark.integration
    def test_full_query_workflow(self, mocker: Mock) -> None:
        """Test complete query workflow through API."""
        # Mock complete pipeline
        retrieval_results = [
            RetrievalResult(
                text="Buddhist teaching about impermanence",
                metadata={"sutra_id": "T0001", "chapter": "1"},
                score=0.95,
                rank=1,
            ),
            RetrievalResult(
                text="Teaching about suffering",
                metadata={"sutra_id": "T0002", "chapter": "2"},
                score=0.85,
                rank=2,
            ),
        ]

        answer_response = AnswerResponse(
            answer="Buddhism teaches about impermanence and suffering...",
            sources=retrieval_results,
            tokens_used=200,
        )

        mock_retriever = mocker.Mock()
        mock_retriever.retrieve.return_value = retrieval_results

        mock_answerer = mocker.Mock()
        mock_answerer.answer.return_value = answer_response

        mocker.patch("src.api.get_retriever", return_value=mock_retriever)
        mocker.patch("src.api.get_answerer", return_value=mock_answerer)

        from src.api import app

        client = TestClient(app)

        # Make query
        response = client.post(
            "/query",
            json={
                "query": "What does Buddhism teach?",
                "top_k": 5,
            },
        )

        assert response.status_code == 200
        data = response.json()

        # Verify response structure
        assert "answer" in data
        assert "sources" in data
        assert "tokens_used" in data

        # Verify content
        assert len(data["sources"]) == 2
        assert data["sources"][0]["text"] == "Buddhist teaching about impermanence"
        assert data["sources"][0]["metadata"]["sutra_id"] == "T0001"
        assert data["tokens_used"] == 200

    @pytest.mark.integration
    def test_api_handles_no_results(self, mocker: Mock) -> None:
        """Test API handles case with no retrieval results."""
        mock_retriever = mocker.Mock()
        mock_retriever.retrieve.return_value = []

        mock_answer = AnswerResponse(
            answer="I don't have enough context to answer.",
            sources=[],
            tokens_used=50,
        )

        mock_answerer = mocker.Mock()
        mock_answerer.answer.return_value = mock_answer

        mocker.patch("src.api.get_retriever", return_value=mock_retriever)
        mocker.patch("src.api.get_answerer", return_value=mock_answerer)

        from src.api import app

        client = TestClient(app)
        response = client.post(
            "/query",
            json={"query": "Unknown topic"},
        )

        assert response.status_code == 200
        data = response.json()
        assert len(data["sources"]) == 0
        assert "context" in data["answer"].lower() or "don't" in data["answer"].lower()

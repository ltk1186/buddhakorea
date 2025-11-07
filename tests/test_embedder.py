"""Test suite for Embedder module.

This module tests embedding generation using OpenAI and local models with
adapter pattern for dependency injection.

Following TDD: These tests are written BEFORE implementation.
"""

from typing import List
from unittest.mock import Mock, patch

import numpy as np
import pytest

from src.embedder import (
    EmbedderConfig,
    Embedder,
    OpenAIEmbeddingAdapter,
    LocalEmbeddingAdapter,
    EmbeddingAdapter,
    EmbeddingError,
    InvalidDimensionError,
)


class TestEmbedderConfig:
    """Test EmbedderConfig data class."""

    def test_default_openai_config(self) -> None:
        """Test default OpenAI configuration."""
        config = EmbedderConfig(backend="openai")

        assert config.backend == "openai"
        assert config.openai_model == "text-embedding-3-small"
        assert config.embedding_dim == 1536
        assert config.batch_size == 100

    def test_custom_config(self) -> None:
        """Test custom configuration."""
        config = EmbedderConfig(
            backend="local",
            local_model="sentence-transformers/all-MiniLM-L6-v2",
            embedding_dim=384,
            batch_size=32,
        )

        assert config.backend == "local"
        assert config.local_model == "sentence-transformers/all-MiniLM-L6-v2"
        assert config.embedding_dim == 384
        assert config.batch_size == 32


class TestEmbeddingAdapter:
    """Test EmbeddingAdapter protocol."""

    def test_adapter_protocol(self) -> None:
        """Test that adapters must implement embed method."""
        # This test verifies the protocol exists
        # Actual implementations will be tested separately
        assert hasattr(EmbeddingAdapter, "embed")


class TestOpenAIEmbeddingAdapter:
    """Test OpenAI embedding adapter."""

    @pytest.mark.unit
    def test_adapter_initialization(self) -> None:
        """Test OpenAI adapter initializes correctly."""
        adapter = OpenAIEmbeddingAdapter(
            api_key="test-key", model="text-embedding-3-small"
        )

        assert adapter.model == "text-embedding-3-small"

    @pytest.mark.unit
    def test_embed_single_text(self, mocker: Mock) -> None:
        """Test embedding single text with mocked OpenAI API."""
        # Mock OpenAI response
        mock_embedding = [0.1] * 1536
        mock_response = mocker.Mock()
        mock_response.data = [mocker.Mock(embedding=mock_embedding)]

        mock_client = mocker.Mock()
        mock_client.embeddings.create.return_value = mock_response

        # Patch OpenAI constructor
        with patch("src.embedder.OpenAI", return_value=mock_client):
            adapter = OpenAIEmbeddingAdapter(api_key="test-key")
            result = adapter.embed(["Test text"])

        assert result.shape == (1, 1536)
        assert np.allclose(result[0], mock_embedding)

    @pytest.mark.unit
    def test_embed_multiple_texts(self, mocker: Mock) -> None:
        """Test embedding multiple texts."""
        # Mock multiple embeddings
        mock_embeddings = [[0.1] * 1536, [0.2] * 1536, [0.3] * 1536]
        mock_response = mocker.Mock()
        mock_response.data = [
            mocker.Mock(embedding=emb) for emb in mock_embeddings
        ]

        mock_client = mocker.Mock()
        mock_client.embeddings.create.return_value = mock_response

        with patch("src.embedder.OpenAI", return_value=mock_client):
            adapter = OpenAIEmbeddingAdapter(api_key="test-key")
            result = adapter.embed(["Text 1", "Text 2", "Text 3"])

        assert result.shape == (3, 1536)

    @pytest.mark.unit
    def test_embed_handles_api_error(self, mocker: Mock) -> None:
        """Test that adapter handles OpenAI API errors."""
        mock_client = mocker.Mock()
        mock_client.embeddings.create.side_effect = Exception("API Error")

        with patch("src.embedder.OpenAI", return_value=mock_client):
            adapter = OpenAIEmbeddingAdapter(api_key="test-key")

            with pytest.raises(EmbeddingError) as exc_info:
                adapter.embed(["Test text"])

            assert "API Error" in str(exc_info.value)

    @pytest.mark.unit
    def test_embed_validates_dimension(self, mocker: Mock) -> None:
        """Test that adapter validates embedding dimensions."""
        # Return wrong dimension
        mock_embedding = [0.1] * 100  # Wrong dimension
        mock_response = mocker.Mock()
        mock_response.data = [mocker.Mock(embedding=mock_embedding)]

        mock_client = mocker.Mock()
        mock_client.embeddings.create.return_value = mock_response

        with patch("src.embedder.OpenAI", return_value=mock_client):
            adapter = OpenAIEmbeddingAdapter(
                api_key="test-key", expected_dim=1536
            )

            with pytest.raises(InvalidDimensionError):
                adapter.embed(["Test text"])


class TestLocalEmbeddingAdapter:
    """Test local (sentence-transformers) embedding adapter."""

    @pytest.mark.unit
    def test_adapter_initialization(self, mocker: Mock) -> None:
        """Test local adapter initializes with model."""
        mock_model = mocker.Mock()

        with patch(
            "src.embedder.SentenceTransformer", return_value=mock_model
        ):
            adapter = LocalEmbeddingAdapter(
                model_name="sentence-transformers/all-MiniLM-L6-v2"
            )

            assert adapter.model_name == "sentence-transformers/all-MiniLM-L6-v2"

    @pytest.mark.unit
    def test_embed_single_text(self, mocker: Mock) -> None:
        """Test local embedding of single text."""
        # Mock sentence transformer model
        mock_embeddings = np.array([[0.1] * 384])
        mock_model = mocker.Mock()
        mock_model.encode.return_value = mock_embeddings

        with patch(
            "src.embedder.SentenceTransformer", return_value=mock_model
        ):
            adapter = LocalEmbeddingAdapter(
                model_name="sentence-transformers/all-MiniLM-L6-v2"
            )
            result = adapter.embed(["Test text"])

        assert result.shape == (1, 384)

    @pytest.mark.unit
    def test_embed_multiple_texts(self, mocker: Mock) -> None:
        """Test local embedding of multiple texts."""
        mock_embeddings = np.array([[0.1] * 384, [0.2] * 384])
        mock_model = mocker.Mock()
        mock_model.encode.return_value = mock_embeddings

        with patch(
            "src.embedder.SentenceTransformer", return_value=mock_model
        ):
            adapter = LocalEmbeddingAdapter(model_name="test-model")
            result = adapter.embed(["Text 1", "Text 2"])

        assert result.shape == (2, 384)

    @pytest.mark.unit
    def test_embed_handles_model_error(self, mocker: Mock) -> None:
        """Test that adapter handles model errors."""
        mock_model = mocker.Mock()
        mock_model.encode.side_effect = Exception("Model Error")

        with patch(
            "src.embedder.SentenceTransformer", return_value=mock_model
        ):
            adapter = LocalEmbeddingAdapter(model_name="test-model")

            with pytest.raises(EmbeddingError):
                adapter.embed(["Test text"])


class TestEmbedder:
    """Test Embedder class with dependency injection."""

    @pytest.mark.unit
    def test_embedder_initialization_with_adapter(self, mocker: Mock) -> None:
        """Test embedder initializes with custom adapter."""
        mock_adapter = mocker.Mock(spec=EmbeddingAdapter)
        config = EmbedderConfig(backend="openai")

        embedder = Embedder(adapter=mock_adapter, config=config)

        assert embedder.adapter == mock_adapter
        assert embedder.config == config

    @pytest.mark.unit
    def test_embedder_creates_openai_adapter(self, mocker: Mock) -> None:
        """Test embedder creates OpenAI adapter from config."""
        config = EmbedderConfig(backend="openai", openai_api_key="test-key")

        with patch("src.embedder.OpenAIEmbeddingAdapter") as mock_adapter_class:
            embedder = Embedder.from_config(config)

            mock_adapter_class.assert_called_once()

    @pytest.mark.unit
    def test_embedder_creates_local_adapter(self, mocker: Mock) -> None:
        """Test embedder creates local adapter from config."""
        config = EmbedderConfig(
            backend="local", local_model="test-model"
        )

        with patch("src.embedder.LocalEmbeddingAdapter") as mock_adapter_class:
            embedder = Embedder.from_config(config)

            mock_adapter_class.assert_called_once()

    @pytest.mark.unit
    def test_embedder_call_interface(self, mocker: Mock) -> None:
        """Test embedder __call__ method."""
        mock_embeddings = np.array([[0.1] * 384, [0.2] * 384])
        mock_adapter = mocker.Mock()
        mock_adapter.embed.return_value = mock_embeddings

        embedder = Embedder(adapter=mock_adapter)
        result = embedder(["Text 1", "Text 2"])

        assert result.shape == (2, 384)
        mock_adapter.embed.assert_called_once_with(["Text 1", "Text 2"])

    @pytest.mark.unit
    def test_embedder_handles_empty_input(self, mocker: Mock) -> None:
        """Test embedder handles empty input list."""
        mock_adapter = mocker.Mock()

        embedder = Embedder(adapter=mock_adapter)

        with pytest.raises(ValueError) as exc_info:
            embedder([])

        assert "Cannot embed empty" in str(exc_info.value)

    @pytest.mark.unit
    def test_embedder_batching(self, mocker: Mock) -> None:
        """Test embedder processes texts in batches."""
        # Create 250 texts to test batching (batch_size=100)
        texts = [f"Text {i}" for i in range(250)]

        mock_embeddings_batch1 = np.random.rand(100, 384)
        mock_embeddings_batch2 = np.random.rand(100, 384)
        mock_embeddings_batch3 = np.random.rand(50, 384)

        mock_adapter = mocker.Mock()
        mock_adapter.embed.side_effect = [
            mock_embeddings_batch1,
            mock_embeddings_batch2,
            mock_embeddings_batch3,
        ]

        config = EmbedderConfig(batch_size=100)
        embedder = Embedder(adapter=mock_adapter, config=config)

        result = embedder(texts)

        assert result.shape == (250, 384)
        assert mock_adapter.embed.call_count == 3

    @pytest.mark.unit
    def test_embedder_preserves_order(self, mocker: Mock) -> None:
        """Test that batching preserves text order."""
        texts = ["First", "Second", "Third"]

        # Return distinct embeddings
        mock_adapter = mocker.Mock()
        mock_adapter.embed.return_value = np.array([
            [1.0] * 384,
            [2.0] * 384,
            [3.0] * 384,
        ])

        embedder = Embedder(adapter=mock_adapter)
        result = embedder(texts)

        assert np.allclose(result[0], [1.0] * 384)
        assert np.allclose(result[1], [2.0] * 384)
        assert np.allclose(result[2], [3.0] * 384)

    @pytest.mark.unit
    def test_embedder_validates_output_shape(self, mocker: Mock) -> None:
        """Test embedder validates output shape matches input."""
        mock_adapter = mocker.Mock()
        # Return wrong number of embeddings
        mock_adapter.embed.return_value = np.array([[0.1] * 384])

        embedder = Embedder(adapter=mock_adapter)

        with pytest.raises(InvalidDimensionError):
            embedder(["Text 1", "Text 2"])  # 2 texts but only 1 embedding

    @pytest.mark.unit
    def test_embedder_with_korean_text(self, mocker: Mock) -> None:
        """Test embedder handles Korean text correctly."""
        korean_texts = [
            "사성제는 불교의 핵심 가르침입니다.",
            "팔정도는 해탈에 이르는 길입니다.",
        ]

        mock_embeddings = np.array([[0.1] * 384, [0.2] * 384])
        mock_adapter = mocker.Mock()
        mock_adapter.embed.return_value = mock_embeddings

        embedder = Embedder(adapter=mock_adapter)
        result = embedder(korean_texts)

        assert result.shape == (2, 384)
        # Verify Korean text was passed to adapter
        called_texts = mock_adapter.embed.call_args[0][0]
        assert "사성제" in called_texts[0]


class TestIntegrationEmbedder:
    """Integration tests for complete embedding workflow."""

    @pytest.mark.integration
    @pytest.mark.slow
    def test_end_to_end_openai_embedding(self, mocker: Mock) -> None:
        """Test complete workflow with mocked OpenAI."""
        texts = [
            "The Four Noble Truths",
            "The Noble Eightfold Path",
        ]

        # Mock OpenAI response
        mock_embeddings = [[0.1] * 1536, [0.2] * 1536]
        mock_response = mocker.Mock()
        mock_response.data = [
            mocker.Mock(embedding=emb) for emb in mock_embeddings
        ]

        mock_client = mocker.Mock()
        mock_client.embeddings.create.return_value = mock_response

        with patch("src.embedder.OpenAI", return_value=mock_client):
            config = EmbedderConfig(backend="openai", openai_api_key="test")
            embedder = Embedder.from_config(config)

            result = embedder(texts)

            assert result.shape == (2, 1536)
            assert isinstance(result, np.ndarray)

    @pytest.mark.integration
    @pytest.mark.slow
    def test_end_to_end_local_embedding(self, mocker: Mock) -> None:
        """Test complete workflow with mocked local model."""
        texts = ["Buddhist teaching", "Meditation practice"]

        # Mock sentence transformer
        mock_embeddings = np.array([[0.1] * 384, [0.2] * 384])
        mock_model = mocker.Mock()
        mock_model.encode.return_value = mock_embeddings

        with patch(
            "src.embedder.SentenceTransformer", return_value=mock_model
        ):
            config = EmbedderConfig(
                backend="local", local_model="test-model"
            )
            embedder = Embedder.from_config(config)

            result = embedder(texts)

            assert result.shape == (2, 384)

    @pytest.mark.integration
    def test_embedder_performance_batch_vs_single(
        self, mocker: Mock, benchmark: callable = None
    ) -> None:
        """Test that batching improves performance."""
        # This is a conceptual test - actual benchmarking would require
        # pytest-benchmark plugin
        texts = [f"Text {i}" for i in range(100)]

        mock_adapter = mocker.Mock()
        mock_adapter.embed.return_value = np.random.rand(100, 384)

        embedder = Embedder(adapter=mock_adapter)
        result = embedder(texts)

        # With batch_size=100, should be called once
        assert mock_adapter.embed.call_count == 1
        assert result.shape == (100, 384)

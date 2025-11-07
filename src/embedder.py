"""Embedder module for generating text embeddings.

This module provides adapters for different embedding backends (OpenAI, local)
using clean architecture with dependency injection.

Example:
    ```python
    # Using OpenAI
    config = EmbedderConfig(backend="openai", openai_api_key="...")
    embedder = Embedder.from_config(config)
    embeddings = embedder(["Buddhist teaching", "Meditation"])

    # Using local model
    config = EmbedderConfig(backend="local")
    embedder = Embedder.from_config(config)
    embeddings = embedder(["Text 1", "Text 2"])
    ```
"""

from dataclasses import dataclass, field
from typing import List, Optional, Protocol

import numpy as np
from openai import OpenAI
from sentence_transformers import SentenceTransformer


class EmbeddingError(Exception):
    """Raised when embedding generation fails."""

    pass


class InvalidDimensionError(Exception):
    """Raised when embedding dimensions are invalid."""

    pass


@dataclass
class EmbedderConfig:
    """Configuration for embedder.

    Attributes:
        backend: "openai" or "local"
        openai_api_key: OpenAI API key (required for openai backend)
        openai_model: OpenAI embedding model name
        local_model: Local model name for sentence-transformers
        embedding_dim: Expected embedding dimension
        batch_size: Number of texts to process in one batch
    """

    backend: str = "openai"
    openai_api_key: Optional[str] = None
    openai_model: str = "text-embedding-3-small"
    local_model: str = "sentence-transformers/paraphrase-multilingual-mpnet-base-v2"
    embedding_dim: int = 1536  # Default for text-embedding-3-small
    batch_size: int = 100


class EmbeddingAdapter(Protocol):
    """Protocol for embedding adapters.

    All embedding adapters must implement the embed method.
    """

    def embed(self, texts: List[str]) -> np.ndarray:
        """Generate embeddings for texts.

        Args:
            texts: List of text strings

        Returns:
            NumPy array of shape (len(texts), embedding_dim)

        Raises:
            EmbeddingError: If embedding generation fails
        """
        ...


class OpenAIEmbeddingAdapter:
    """OpenAI embedding adapter.

    Uses OpenAI's embedding API to generate embeddings.
    """

    def __init__(
        self,
        api_key: str,
        model: str = "text-embedding-3-small",
        expected_dim: Optional[int] = None,
    ):
        """Initialize OpenAI adapter.

        Args:
            api_key: OpenAI API key
            model: Model name (e.g., "text-embedding-3-small")
            expected_dim: Expected embedding dimension (for validation)
        """
        self.api_key = api_key
        self.model = model
        self.expected_dim = expected_dim
        self.client = OpenAI(api_key=api_key)

    def embed(self, texts: List[str]) -> np.ndarray:
        """Generate embeddings using OpenAI API.

        Args:
            texts: List of text strings

        Returns:
            NumPy array of embeddings

        Raises:
            EmbeddingError: If API call fails
            InvalidDimensionError: If embedding dimension is wrong
        """
        try:
            response = self.client.embeddings.create(model=self.model, input=texts)

            # Extract embeddings
            embeddings = [item.embedding for item in response.data]
            result = np.array(embeddings, dtype=np.float32)

            # Validate dimensions if expected_dim is set
            if self.expected_dim is not None:
                if result.shape[1] != self.expected_dim:
                    raise InvalidDimensionError(
                        f"Expected dimension {self.expected_dim}, "
                        f"got {result.shape[1]}"
                    )

            return result

        except InvalidDimensionError:
            raise
        except Exception as e:
            raise EmbeddingError(f"OpenAI embedding failed: {e}") from e


class LocalEmbeddingAdapter:
    """Local embedding adapter using sentence-transformers.

    Uses HuggingFace sentence-transformers models for local embedding generation.
    """

    def __init__(
        self,
        model_name: str = "sentence-transformers/paraphrase-multilingual-mpnet-base-v2",
    ):
        """Initialize local embedding adapter.

        Args:
            model_name: HuggingFace model name or path
        """
        self.model_name = model_name
        try:
            self.model = SentenceTransformer(model_name)
        except Exception as e:
            raise EmbeddingError(f"Failed to load model {model_name}: {e}") from e

    def embed(self, texts: List[str]) -> np.ndarray:
        """Generate embeddings using local model.

        Args:
            texts: List of text strings

        Returns:
            NumPy array of embeddings

        Raises:
            EmbeddingError: If embedding generation fails
        """
        try:
            embeddings = self.model.encode(texts, show_progress_bar=False)
            return np.array(embeddings, dtype=np.float32)
        except Exception as e:
            raise EmbeddingError(f"Local embedding failed: {e}") from e


class Embedder:
    """Embedder with dependency injection for different backends.

    Example:
        ```python
        # With custom adapter
        adapter = OpenAIEmbeddingAdapter(api_key="...")
        embedder = Embedder(adapter=adapter)

        # From config
        config = EmbedderConfig(backend="openai")
        embedder = Embedder.from_config(config)

        # Use it
        embeddings = embedder(["Text 1", "Text 2"])
        ```
    """

    def __init__(
        self, adapter: Optional[EmbeddingAdapter] = None, config: Optional[EmbedderConfig] = None
    ):
        """Initialize embedder.

        Args:
            adapter: Custom embedding adapter
            config: Embedder configuration
        """
        self.adapter = adapter
        self.config = config if config is not None else EmbedderConfig()

    @classmethod
    def from_config(cls, config: EmbedderConfig) -> "Embedder":
        """Create embedder from configuration.

        Args:
            config: Embedder configuration

        Returns:
            Configured Embedder instance

        Raises:
            ValueError: If backend is invalid or required config is missing
        """
        if config.backend == "openai":
            if not config.openai_api_key:
                raise ValueError("openai_api_key required for OpenAI backend")

            adapter = OpenAIEmbeddingAdapter(
                api_key=config.openai_api_key,
                model=config.openai_model,
                expected_dim=config.embedding_dim,
            )
        elif config.backend == "local":
            adapter = LocalEmbeddingAdapter(model_name=config.local_model)
        else:
            raise ValueError(f"Invalid backend: {config.backend}")

        return cls(adapter=adapter, config=config)

    def __call__(self, texts: List[str]) -> np.ndarray:
        """Generate embeddings for texts.

        Args:
            texts: List of text strings

        Returns:
            NumPy array of shape (len(texts), embedding_dim)

        Raises:
            ValueError: If texts is empty
            InvalidDimensionError: If output shape doesn't match input
        """
        if not texts:
            raise ValueError("Cannot embed empty list of texts")

        if self.adapter is None:
            raise ValueError("No adapter configured. Use from_config() or provide adapter.")

        # Process in batches
        batch_size = self.config.batch_size
        all_embeddings = []

        for i in range(0, len(texts), batch_size):
            batch = texts[i : i + batch_size]
            batch_embeddings = self.adapter.embed(batch)
            all_embeddings.append(batch_embeddings)

        # Concatenate all batches
        result = np.vstack(all_embeddings)

        # Validate output shape
        if result.shape[0] != len(texts):
            raise InvalidDimensionError(
                f"Expected {len(texts)} embeddings, got {result.shape[0]}"
            )

        return result

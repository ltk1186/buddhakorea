"""Retriever module for semantic search.

This module combines the embedder and vector database to perform
semantic search over Buddhist text chunks.

Example:
    ```python
    # Setup components
    embedder = Embedder.from_config(embedder_config)
    vectordb = VectorDB.from_config(vectordb_config)

    # Create retriever
    config = RetrieverConfig(top_k=5, similarity_threshold=0.7)
    retriever = Retriever(embedder, vectordb, config)

    # Retrieve relevant chunks
    results = retriever.retrieve("What are the Four Noble Truths?")

    for result in results:
        print(f"Rank {result.rank}: {result.text} (score: {result.score})")
    ```
"""

from dataclasses import dataclass
from typing import Any, Dict, List, Optional

import numpy as np

from src.buddhist_thesaurus import expand_query
from src.embedder import Embedder
from src.vectordb import VectorDB


class RetrievalError(Exception):
    """Raised when retrieval fails."""

    pass


@dataclass
class RetrieverConfig:
    """Configuration for retriever.

    Attributes:
        top_k: Number of top results to return
        similarity_threshold: Minimum similarity score (0.0-1.0)
        enable_reranking: Whether to enable reranking (future feature)
    """

    top_k: int = 5
    similarity_threshold: float = 0.0
    enable_reranking: bool = False


@dataclass
class RetrievalResult:
    """Single retrieval result.

    Attributes:
        text: The retrieved text chunk
        metadata: Metadata dictionary (sutra_id, chapter, etc.)
        score: Similarity score (0.0-1.0, higher is better)
        rank: Rank in results (1-indexed)
    """

    text: str
    metadata: Dict[str, Any]
    score: float
    rank: int


class Retriever:
    """Semantic search retriever.

    Combines embedder and vector database to find relevant text chunks.

    Example:
        ```python
        retriever = Retriever(embedder, vectordb, config)
        results = retriever.retrieve("Buddhist teaching query")
        ```
    """

    def __init__(
        self,
        embedder: Embedder,
        vectordb: VectorDB,
        config: Optional[RetrieverConfig] = None,
    ):
        """Initialize retriever.

        Args:
            embedder: Embedder instance for query encoding
            vectordb: VectorDB instance for similarity search
            config: Retriever configuration
        """
        self.embedder = embedder
        self.vectordb = vectordb
        self.config = config if config is not None else RetrieverConfig()

    def retrieve(
        self,
        query: str,
        filter_metadata: Optional[Dict[str, Any]] = None,
        top_k: Optional[int] = None,
    ) -> List[RetrievalResult]:
        """Retrieve relevant chunks for a text query.

        Args:
            query: Text query string
            filter_metadata: Optional metadata filter (e.g., {"sutra_id": "T0001"})
            top_k: Override default top_k

        Returns:
            List of RetrievalResult objects, ranked by relevance

        Raises:
            RetrievalError: If retrieval fails
        """
        try:
            # Expand query with Buddhist term synonyms
            expanded_query = expand_query(query)

            # Embed expanded query
            query_embedding = self.embedder([expanded_query])

            # Flatten to 1D if needed
            if query_embedding.ndim > 1:
                query_embedding = query_embedding.flatten()

            # Retrieve by embedding
            return self.retrieve_by_embedding(
                query_embedding=query_embedding,
                filter_metadata=filter_metadata,
                top_k=top_k,
            )

        except Exception as e:
            raise RetrievalError(f"Retrieval failed for query '{query}': {e}") from e

    def retrieve_by_embedding(
        self,
        query_embedding: np.ndarray,
        filter_metadata: Optional[Dict[str, Any]] = None,
        top_k: Optional[int] = None,
    ) -> List[RetrievalResult]:
        """Retrieve relevant chunks using pre-computed embedding.

        Args:
            query_embedding: Query embedding vector
            filter_metadata: Optional metadata filter
            top_k: Override default top_k

        Returns:
            List of RetrievalResult objects, ranked by relevance

        Raises:
            RetrievalError: If retrieval fails
        """
        try:
            # Use provided top_k or default
            k = top_k if top_k is not None else self.config.top_k

            # Search vector database
            raw_results = self.vectordb.search(
                query_embedding=query_embedding,
                top_k=k,
                filter_metadata=filter_metadata,
            )

            # Filter by similarity threshold
            filtered_results = [
                result
                for result in raw_results
                if result["score"] >= self.config.similarity_threshold
            ]

            # Convert to RetrievalResult objects with ranks
            results = []
            for rank, result in enumerate(filtered_results, start=1):
                retrieval_result = RetrievalResult(
                    text=result["text"],
                    metadata=result["metadata"],
                    score=result["score"],
                    rank=rank,
                )
                results.append(retrieval_result)

            return results

        except Exception as e:
            raise RetrievalError(f"Retrieval by embedding failed: {e}") from e

"""VectorDB module for storing and querying embeddings.

This module provides a ChromaDB adapter for storing text chunks with embeddings
and querying them for the Buddhist RAG system.

Example:
    ```python
    config = VectorDBConfig(
        collection_name="taisho_canon",
        persist_directory="./data/chroma"
    )
    vectordb = VectorDB.from_config(config)

    # Add chunks with embeddings
    vectordb.add_chunks(chunks, embeddings)

    # Search
    results = vectordb.search(query_embedding, top_k=5)
    ```
"""

import uuid
from dataclasses import dataclass
from typing import Any, Dict, List, Optional

import chromadb
import numpy as np
from chromadb.config import Settings


class VectorDBError(Exception):
    """Raised when vector database operations fail."""

    pass


class CollectionNotFoundError(Exception):
    """Raised when collection doesn't exist."""

    pass


@dataclass
class VectorDBConfig:
    """Configuration for VectorDB.

    Attributes:
        collection_name: Name of the ChromaDB collection
        persist_directory: Directory for persistent storage (None for in-memory)
        distance_metric: Distance metric ("cosine", "l2", "ip")
    """

    collection_name: str = "taisho_canon"
    persist_directory: Optional[str] = None
    distance_metric: str = "cosine"


class ChromaDBAdapter:
    """ChromaDB adapter for vector storage.

    Wraps ChromaDB client operations with clean interface.
    """

    def __init__(
        self,
        collection_name: str,
        persist_directory: Optional[str] = None,
        distance_metric: str = "cosine",
    ):
        """Initialize ChromaDB adapter.

        Args:
            collection_name: Name of collection
            persist_directory: Path for persistence (None for in-memory)
            distance_metric: Distance metric to use
        """
        self.collection_name = collection_name
        self.persist_directory = persist_directory
        self.distance_metric = distance_metric

        # Map distance metric to ChromaDB metadata
        metric_map = {
            "cosine": "cosine",
            "l2": "l2",
            "ip": "ip",  # inner product
        }
        self.chroma_metric = metric_map.get(distance_metric, "cosine")

        # Initialize ChromaDB client
        if persist_directory:
            self.client = chromadb.PersistentClient(path=persist_directory)
        else:
            self.client = chromadb.Client()

        # Get or create collection
        try:
            self.collection = self.client.get_or_create_collection(
                name=collection_name,
                metadata={"hnsw:space": self.chroma_metric},
            )
        except Exception as e:
            raise VectorDBError(f"Failed to initialize collection: {e}") from e

    def add(
        self,
        embeddings: np.ndarray,
        texts: List[str],
        ids: Optional[List[str]] = None,
        metadatas: Optional[List[Dict[str, Any]]] = None,
    ) -> List[str]:
        """Add documents to collection.

        Args:
            embeddings: Array of embeddings (n_docs, embedding_dim)
            texts: List of text documents
            ids: Optional list of document IDs (auto-generated if None)
            metadatas: Optional list of metadata dicts

        Returns:
            List of document IDs

        Raises:
            VectorDBError: If adding documents fails
        """
        try:
            # Generate IDs if not provided
            if ids is None:
                ids = [str(uuid.uuid4()) for _ in range(len(texts))]

            # Convert embeddings to list format
            embeddings_list = embeddings.tolist()

            # ChromaDB requires non-empty metadata dicts or None
            # Replace empty dicts with None
            if metadatas is not None:
                metadatas = [
                    meta if meta else None
                    for meta in metadatas
                ]
                # If all metadatas are None, pass None to ChromaDB
                if all(m is None for m in metadatas):
                    metadatas = None

            # Add to collection
            self.collection.add(
                ids=ids,
                embeddings=embeddings_list,
                documents=texts,
                metadatas=metadatas,
            )

            return ids

        except Exception as e:
            raise VectorDBError(f"Failed to add documents: {e}") from e

    def query(
        self,
        query_embeddings: np.ndarray,
        n_results: int = 5,
        where: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        """Query collection by embedding.

        Args:
            query_embeddings: Query embedding(s) (n_queries, embedding_dim)
            n_results: Number of results to return
            where: Optional metadata filter

        Returns:
            Dict with keys: ids, embeddings, documents, metadatas, distances

        Raises:
            VectorDBError: If query fails
        """
        try:
            # Convert to list format
            query_list = query_embeddings.tolist()

            # Query collection
            results = self.collection.query(
                query_embeddings=query_list,
                n_results=n_results,
                where=where,
            )

            return results

        except Exception as e:
            raise VectorDBError(f"Query failed: {e}") from e

    def get(
        self,
        ids: Optional[List[str]] = None,
        where: Optional[Dict[str, Any]] = None,
        limit: Optional[int] = None,
    ) -> Dict[str, Any]:
        """Get documents from collection.

        Args:
            ids: Optional list of document IDs to retrieve
            where: Optional metadata filter
            limit: Maximum number of results

        Returns:
            Dict with keys: ids, embeddings, documents, metadatas

        Raises:
            VectorDBError: If get fails
        """
        try:
            results = self.collection.get(
                ids=ids,
                where=where,
                limit=limit,
            )
            return results

        except Exception as e:
            raise VectorDBError(f"Get failed: {e}") from e

    def update(
        self,
        ids: List[str],
        embeddings: Optional[np.ndarray] = None,
        texts: Optional[List[str]] = None,
        metadatas: Optional[List[Dict[str, Any]]] = None,
    ) -> None:
        """Update existing documents.

        Args:
            ids: List of document IDs to update
            embeddings: Optional new embeddings
            texts: Optional new texts
            metadatas: Optional new metadata

        Raises:
            VectorDBError: If update fails
        """
        try:
            update_args = {"ids": ids}

            if embeddings is not None:
                update_args["embeddings"] = embeddings.tolist()
            if texts is not None:
                update_args["documents"] = texts
            if metadatas is not None:
                update_args["metadatas"] = metadatas

            self.collection.update(**update_args)

        except Exception as e:
            raise VectorDBError(f"Update failed: {e}") from e

    def delete(
        self,
        ids: Optional[List[str]] = None,
        where: Optional[Dict[str, Any]] = None,
    ) -> None:
        """Delete documents from collection.

        Args:
            ids: Optional list of document IDs to delete
            where: Optional metadata filter for deletion

        Raises:
            VectorDBError: If deletion fails
        """
        try:
            self.collection.delete(ids=ids, where=where)
        except Exception as e:
            raise VectorDBError(f"Delete failed: {e}") from e

    def count(self) -> int:
        """Get count of documents in collection.

        Returns:
            Number of documents

        Raises:
            VectorDBError: If count fails
        """
        try:
            return self.collection.count()
        except Exception as e:
            raise VectorDBError(f"Count failed: {e}") from e

    def delete_collection(self) -> None:
        """Delete the entire collection.

        Raises:
            VectorDBError: If deletion fails
        """
        try:
            self.client.delete_collection(name=self.collection_name)
            self.collection = None
        except Exception as e:
            raise VectorDBError(f"Failed to delete collection: {e}") from e


class VectorDB:
    """High-level interface for vector database operations.

    Example:
        ```python
        config = VectorDBConfig(collection_name="test")
        vectordb = VectorDB.from_config(config)

        # Add chunks
        vectordb.add_chunks(chunks, embeddings)

        # Search
        results = vectordb.search(query_embedding, top_k=5)
        ```
    """

    def __init__(
        self,
        adapter: ChromaDBAdapter,
        config: VectorDBConfig,
    ):
        """Initialize VectorDB.

        Args:
            adapter: ChromaDB adapter instance
            config: VectorDB configuration
        """
        self.adapter = adapter
        self.config = config
        self._expected_dim: Optional[int] = None

    @classmethod
    def from_config(cls, config: VectorDBConfig) -> "VectorDB":
        """Create VectorDB from configuration.

        Args:
            config: VectorDB configuration

        Returns:
            Configured VectorDB instance
        """
        adapter = ChromaDBAdapter(
            collection_name=config.collection_name,
            persist_directory=config.persist_directory,
            distance_metric=config.distance_metric,
        )
        return cls(adapter=adapter, config=config)

    def add_chunks(
        self,
        chunks: List[Dict[str, Any]],
        embeddings: np.ndarray,
        ids: Optional[List[str]] = None,
    ) -> List[str]:
        """Add text chunks with embeddings.

        Args:
            chunks: List of chunk dicts with 'text' and 'metadata' keys
            embeddings: Array of embeddings (n_chunks, embedding_dim)
            ids: Optional list of IDs

        Returns:
            List of document IDs

        Raises:
            VectorDBError: If adding fails or dimensions mismatch
        """
        # Validate embedding dimensions
        if self._expected_dim is None:
            self._expected_dim = embeddings.shape[1]
        elif embeddings.shape[1] != self._expected_dim:
            raise VectorDBError(
                f"Embedding dimension mismatch: expected {self._expected_dim}, "
                f"got {embeddings.shape[1]}"
            )

        # Validate input lengths match
        if len(chunks) != embeddings.shape[0]:
            raise VectorDBError(
                f"Number of chunks ({len(chunks)}) doesn't match "
                f"number of embeddings ({embeddings.shape[0]})"
            )

        # Extract texts and metadatas
        texts = [chunk["text"] for chunk in chunks]
        metadatas = [chunk["metadata"] for chunk in chunks]

        # Add to database
        return self.adapter.add(
            embeddings=embeddings,
            texts=texts,
            ids=ids,
            metadatas=metadatas,
        )

    def search(
        self,
        query_embedding: np.ndarray,
        top_k: int = 5,
        filter_metadata: Optional[Dict[str, Any]] = None,
    ) -> List[Dict[str, Any]]:
        """Search for similar chunks.

        Args:
            query_embedding: Query embedding vector (embedding_dim,)
            top_k: Number of results to return
            filter_metadata: Optional metadata filter

        Returns:
            List of result dicts with keys: text, metadata, score

        Raises:
            VectorDBError: If search fails
        """
        # Reshape query if needed
        if query_embedding.ndim == 1:
            query_embedding = query_embedding.reshape(1, -1)

        # Query database
        raw_results = self.adapter.query(
            query_embeddings=query_embedding,
            n_results=top_k,
            where=filter_metadata,
        )

        # Format results
        results = []
        if raw_results["ids"] and len(raw_results["ids"][0]) > 0:
            for i in range(len(raw_results["ids"][0])):
                result = {
                    "text": raw_results["documents"][0][i],
                    "metadata": raw_results["metadatas"][0][i],
                    "score": 1.0 - raw_results["distances"][0][i],  # Convert distance to similarity
                }
                results.append(result)

        return results

    def get_stats(self) -> Dict[str, Any]:
        """Get collection statistics.

        Returns:
            Dict with collection stats
        """
        count = self.adapter.count()
        return {
            "count": count,
            "collection_name": self.config.collection_name,
            "distance_metric": self.config.distance_metric,
        }

    def clear(self) -> None:
        """Clear all documents from collection.

        Raises:
            VectorDBError: If clearing fails
        """
        # Delete all documents
        all_docs = self.adapter.get()
        if all_docs["ids"]:
            self.adapter.delete(ids=all_docs["ids"])

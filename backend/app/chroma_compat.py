"""
Minimal Chroma adapter built directly on top of chromadb.

This avoids the deprecated langchain_community Chroma wrapper while keeping
the current Buddha Korea retrieval flow stable on chromadb 1.x.
"""

from __future__ import annotations

import json
import uuid
from typing import Any, Iterable, List, Optional

import chromadb
from langchain_core.documents import Document
from langchain_core.vectorstores import VectorStore


class ChromaCompat(VectorStore):
    """Thin VectorStore wrapper for the subset of Chroma features we use."""

    def __init__(
        self,
        client: chromadb.ClientAPI,
        collection_name: str,
        embedding_function: Any,
    ) -> None:
        self._client = client
        self._collection_name = collection_name
        self._embedding_function = embedding_function
        self._collection = client.get_or_create_collection(name=collection_name)

    @property
    def embeddings(self) -> Any:
        return self._embedding_function

    @staticmethod
    def _sanitize_metadata(metadata: Optional[dict[str, Any]]) -> dict[str, Any]:
        if not metadata:
            return {}

        cleaned: dict[str, Any] = {}
        for key, value in metadata.items():
            if value is None:
                continue
            if isinstance(value, (str, int, float, bool)):
                cleaned[key] = value
                continue
            cleaned[key] = json.dumps(value, ensure_ascii=False)
        return cleaned

    def add_texts(
        self,
        texts: Iterable[str],
        metadatas: Optional[List[dict]] = None,
        ids: Optional[List[str]] = None,
        **kwargs: Any,
    ) -> List[str]:
        text_list = list(texts)
        if not text_list:
            return []

        metadata_list = metadatas or [{} for _ in text_list]
        id_list = ids or [str(uuid.uuid4()) for _ in text_list]
        embeddings = self._embedding_function.embed_documents(text_list)

        self._collection.add(
            ids=id_list,
            documents=text_list,
            metadatas=[self._sanitize_metadata(metadata) for metadata in metadata_list],
            embeddings=embeddings,
        )
        return id_list

    def similarity_search(
        self,
        query: str,
        k: int = 4,
        filter: Optional[dict[str, Any]] = None,
        **kwargs: Any,
    ) -> List[Document]:
        query_embedding = self._embedding_function.embed_query(query)
        result = self._collection.query(
            query_embeddings=[query_embedding],
            n_results=k,
            where=filter,
            include=["documents", "metadatas"],
        )

        documents = result.get("documents", [[]])[0]
        metadatas = result.get("metadatas", [[]])[0]

        return [
            Document(page_content=page_content or "", metadata=metadata or {})
            for page_content, metadata in zip(documents, metadatas)
        ]

    @classmethod
    def from_texts(
        cls,
        texts: List[str],
        embedding: Any,
        metadatas: Optional[List[dict]] = None,
        ids: Optional[List[str]] = None,
        collection_name: str = "langchain",
        persist_directory: Optional[str] = None,
        client: Optional[chromadb.ClientAPI] = None,
        **kwargs: Any,
    ) -> "ChromaCompat":
        chroma_client = client
        if chroma_client is None:
            chroma_client = (
                chromadb.PersistentClient(path=persist_directory)
                if persist_directory
                else chromadb.Client()
            )

        store = cls(
            client=chroma_client,
            collection_name=collection_name,
            embedding_function=embedding,
        )
        store.add_texts(texts=texts, metadatas=metadatas, ids=ids)
        return store

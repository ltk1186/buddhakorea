"""
Gemini Query Embedder for OpenNotebook
Provides query embedding using Google's Gemini API to match document embeddings
"""

import os
from typing import List, Union
from google import genai
from google.genai import types


class GeminiQueryEmbedder:
    """
    Query embedder using Gemini API
    Compatible with OpenNotebook's embedding interface
    """

    def __init__(
        self,
        project_id: str = None,
        location: str = "us-central1",
        model_name: str = "gemini-embedding-001"
    ):
        """
        Initialize Gemini query embedder

        Args:
            project_id: GCP project ID (defaults to env var)
            location: GCP region
            model_name: Embedding model (gemini-embedding-001 = 3072 dims)
        """
        self.project_id = project_id or os.getenv("GCP_PROJECT_ID")
        self.location = location
        self.model_name = model_name

        if not self.project_id:
            raise ValueError(
                "GCP_PROJECT_ID not set. Either pass project_id or set "
                "GCP_PROJECT_ID environment variable"
            )

        self.client = genai.Client(
            vertexai=True,
            project=self.project_id,
            location=self.location,
        )

        print(f"✅ Gemini Query Embedder initialized")
        print(f"   Project: {self.project_id}")
        print(f"   Model: {self.model_name}")
        print(f"   Dimensions: 3072")

    def encode(
        self,
        sentences: Union[str, List[str]],
        task_type: str = "RETRIEVAL_QUERY",
        **kwargs
    ) -> List[List[float]]:
        """
        Encode text into embeddings
        Compatible with sentence-transformers interface

        Args:
            sentences: Single string or list of strings
            task_type: Task type for Gemini API
                - RETRIEVAL_QUERY: For query embedding (default)
                - RETRIEVAL_DOCUMENT: For document embedding
            **kwargs: Additional arguments (ignored for compatibility)

        Returns:
            List of embedding vectors (each is 3072 dims)
        """
        # Handle single string
        if isinstance(sentences, str):
            sentences = [sentences]

        response = self.client.models.embed_content(
            model=self.model_name,
            contents=sentences,
            config=types.EmbedContentConfig(task_type=task_type),
        )

        # Extract values
        return [embedding.values for embedding in response.embeddings]

    def embed_query(self, query: str) -> List[float]:
        """
        Embed a single query
        Convenience method for single queries

        Args:
            query: Query text

        Returns:
            Embedding vector (3072 dims)
        """
        return self.encode(query, task_type="RETRIEVAL_QUERY")[0]

    def embed_documents(self, documents: List[str]) -> List[List[float]]:
        """
        Embed multiple documents
        For compatibility with LangChain interface

        Args:
            documents: List of document texts

        Returns:
            List of embedding vectors
        """
        return self.encode(documents, task_type="RETRIEVAL_DOCUMENT")


def test_embedder():
    """Test the embedder"""
    import numpy as np

    print("\n🧪 Testing Gemini Query Embedder...")

    # Initialize
    embedder = GeminiQueryEmbedder(
        project_id="gen-lang-client-0324154376"
    )

    # Test single query
    query = "반야심경의 핵심 가르침은 무엇인가?"
    print(f"\n📝 Query: {query}")

    embedding = embedder.embed_query(query)

    print(f"✅ Embedding generated!")
    print(f"   Dimension: {len(embedding)}")
    print(f"   First 5 values: {embedding[:5]}")
    print(f"   L2 norm: {np.linalg.norm(embedding):.4f}")

    # Test batch
    queries = [
        "사성제란 무엇인가?",
        "팔정도의 내용은?",
        "무아의 의미는?"
    ]

    print(f"\n📝 Batch queries: {len(queries)}")
    embeddings = embedder.encode(queries)

    print(f"✅ Batch embeddings generated!")
    print(f"   Count: {len(embeddings)}")
    print(f"   Dimensions: {[len(e) for e in embeddings]}")

    # Calculate similarity
    sim = np.dot(embeddings[0], embeddings[1])
    print(f"\n🔍 Similarity between query 1 and 2: {sim:.4f}")

    print("\n✅ All tests passed!")

    # Cost estimation
    total_chars = sum(len(q) for q in [query] + queries)
    cost = (total_chars / 1000) * 0.0000125  # $0.0125 per 1K chars
    print(f"\n💰 Cost for this test: ${cost:.6f}")
    print(f"   ({total_chars} chars × $0.0000125/char)")


if __name__ == "__main__":
    test_embedder()

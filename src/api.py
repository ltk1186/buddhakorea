"""FastAPI REST API for Buddhist RAG System.

This module provides HTTP endpoints for querying the RAG system.

Example:
    ```bash
    # Start server
    uvicorn src.api:app --reload

    # Query
    curl -X POST http://localhost:8000/query \
      -H "Content-Type: application/json" \
      -d '{"query": "What are the Four Noble Truths?"}'
    ```
"""

import os
from typing import Any, Dict, List, Optional

from fastapi import FastAPI, HTTPException, status
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field

from src import __version__
from src.answerer import Answerer, AnswererConfig
from src.embedder import Embedder, EmbedderConfig
from src.retriever import Retriever, RetrieverConfig
from src.vectordb import VectorDB, VectorDBConfig

# Create FastAPI app
app = FastAPI(
    title="Buddhist RAG API",
    description="REST API for querying Buddhist texts using RAG (Retrieval-Augmented Generation)",
    version=__version__,
)

# Configure CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Configure appropriately for production
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# Request/Response Models
class QueryRequest(BaseModel):
    """Request model for query endpoint."""

    query: str = Field(..., description="User's question", min_length=1)
    top_k: Optional[int] = Field(5, description="Number of results to retrieve", ge=1, le=20)
    filter_metadata: Optional[Dict[str, Any]] = Field(
        None, description="Metadata filters (e.g., {'sutra_id': 'T0001'})"
    )


class SourceResponse(BaseModel):
    """Source document in response."""

    text: str
    metadata: Dict[str, Any]
    score: float
    rank: int


class QueryResponse(BaseModel):
    """Response model for query endpoint."""

    answer: str
    sources: List[SourceResponse]
    tokens_used: int


class HealthResponse(BaseModel):
    """Response model for health endpoint."""

    status: str
    version: str


class StatsResponse(BaseModel):
    """Response model for stats endpoint."""

    count: int
    collection_name: str
    distance_metric: str


# Global components (lazily initialized)
retriever: Optional[Retriever] = None
answerer: Optional[Answerer] = None
vectordb: Optional[VectorDB] = None


def get_retriever() -> Retriever:
    """Get or create retriever instance."""
    global retriever
    if retriever is None:
        # Initialize embedder
        embedder_config = EmbedderConfig(
            backend=os.getenv("EMBEDDER_BACKEND", "openai"),
            openai_api_key=os.getenv("OPENAI_API_KEY"),
            local_model=os.getenv("LOCAL_EMBEDDING_MODEL"),
        )
        embedder = Embedder.from_config(embedder_config)

        # Initialize vectordb
        vectordb_config = VectorDBConfig(
            collection_name=os.getenv("CHROMA_COLLECTION_NAME", "taisho_canon"),
            persist_directory=os.getenv("CHROMA_PERSIST_DIRECTORY", "./data/chroma_db"),
        )
        vectordb_instance = VectorDB.from_config(vectordb_config)

        # Initialize retriever
        retriever_config = RetrieverConfig(
            top_k=int(os.getenv("TOP_K_RESULTS", "5")),
            similarity_threshold=float(os.getenv("SIMILARITY_THRESHOLD", "0.0")),
        )
        retriever = Retriever(embedder, vectordb_instance, retriever_config)

    return retriever


def get_answerer() -> Answerer:
    """Get or create answerer instance."""
    global answerer
    if answerer is None:
        answerer_config = AnswererConfig(
            llm_backend=os.getenv("LLM_BACKEND", "openai"),
            openai_api_key=os.getenv("OPENAI_API_KEY"),
            openai_model=os.getenv("OPENAI_CHAT_MODEL", "gpt-4-turbo-preview"),
            claude_api_key=os.getenv("ANTHROPIC_API_KEY"),
            claude_model=os.getenv("ANTHROPIC_MODEL", "claude-3-5-sonnet-20241022"),
            temperature=float(os.getenv("TEMPERATURE", "0.7")),
            max_tokens=int(os.getenv("MAX_TOKENS", "1000")),
        )
        answerer = Answerer.from_config(answerer_config)

    return answerer


def get_vectordb() -> VectorDB:
    """Get or create vectordb instance."""
    global vectordb
    if vectordb is None:
        vectordb_config = VectorDBConfig(
            collection_name=os.getenv("CHROMA_COLLECTION_NAME", "taisho_canon"),
            persist_directory=os.getenv("CHROMA_PERSIST_DIRECTORY", "./data/chroma_db"),
        )
        vectordb = VectorDB.from_config(vectordb_config)

    return vectordb


@app.get("/health", response_model=HealthResponse, tags=["System"])
def health_check() -> HealthResponse:
    """Health check endpoint.

    Returns:
        Health status and version information
    """
    return HealthResponse(status="healthy", version=__version__)


@app.post("/query", response_model=QueryResponse, tags=["RAG"])
def query(request: QueryRequest) -> QueryResponse:
    """Query the Buddhist RAG system.

    Args:
        request: Query request with question and optional filters

    Returns:
        Answer with sources and token usage

    Raises:
        HTTPException: If query processing fails
    """
    try:
        # Validate query
        if not request.query.strip():
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Query cannot be empty",
            )

        # Get components
        retriever_instance = get_retriever()
        answerer_instance = get_answerer()

        # Retrieve relevant chunks
        retrieval_results = retriever_instance.retrieve(
            query=request.query,
            filter_metadata=request.filter_metadata,
            top_k=request.top_k,
        )

        # Generate answer
        answer_response = answerer_instance.answer(
            query=request.query,
            context_results=retrieval_results,
        )

        # Format response
        sources = [
            SourceResponse(
                text=source.text,
                metadata=source.metadata,
                score=source.score,
                rank=source.rank,
            )
            for source in answer_response.sources
        ]

        return QueryResponse(
            answer=answer_response.answer,
            sources=sources,
            tokens_used=answer_response.tokens_used,
        )

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Query processing failed: {str(e)}",
        )


@app.get("/stats", response_model=StatsResponse, tags=["System"])
def get_stats() -> StatsResponse:
    """Get collection statistics.

    Returns:
        Database statistics

    Raises:
        HTTPException: If stats retrieval fails
    """
    try:
        vectordb_instance = get_vectordb()
        stats = vectordb_instance.get_stats()

        return StatsResponse(
            count=stats["count"],
            collection_name=stats["collection_name"],
            distance_metric=stats["distance_metric"],
        )

    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to get stats: {str(e)}",
        )


@app.get("/", tags=["System"])
def root() -> Dict[str, str]:
    """Root endpoint with API information.

    Returns:
        Welcome message and documentation link
    """
    return {
        "message": "Buddhist RAG API",
        "version": __version__,
        "docs": "/docs",
        "health": "/health",
    }

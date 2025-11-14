"""
Buddhist AI Chatbot - FastAPI Application
OpenNotebook experiment for buddhakorea.com

Provides RAG-powered chat interface for Taishō Tripiṭaka and Pali Canon texts.
"""

import os
import json
import time
from typing import List, Optional, Dict, Any
from contextlib import asynccontextmanager

from fastapi import FastAPI, HTTPException, Request, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse, HTMLResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field
from pydantic_settings import BaseSettings
from loguru import logger
import chromadb
from chromadb.config import Settings as ChromaSettings
from langchain_anthropic import ChatAnthropic
from langchain_openai import ChatOpenAI, OpenAIEmbeddings
from langchain_google_vertexai import ChatVertexAI
from langchain_community.vectorstores import Chroma
from langchain_community.embeddings import HuggingFaceEmbeddings
from langchain_classic.chains import RetrievalQA
from langchain_core.prompts import PromptTemplate


# ============================================================================
# Configuration
# ============================================================================

class AppConfig(BaseSettings):
    """Application configuration from environment variables."""

    # API Keys
    openai_api_key: Optional[str] = None
    anthropic_api_key: Optional[str] = None

    # Model Configuration
    llm_model: str = "claude-3-5-sonnet-20241022"
    embedding_model: str = "BAAI/bge-m3"  # Better for Classical Chinese (75-80% vs 60-70%)

    # Vector Database
    chroma_db_path: str = "./chroma_db"
    chroma_collection_name: str = "buddhist_texts"

    # Google Cloud Configuration (for Gemini embeddings)
    gcp_project_id: Optional[str] = None
    gcp_location: str = "us-central1"
    use_gemini_for_queries: bool = False

    # HyDE Configuration
    use_hyde: bool = False
    hyde_weight: float = 0.5
    hyde_model: str = "gemini-1.5-flash-002"

    # API Settings
    api_host: str = "0.0.0.0"
    api_port: int = 8000
    allowed_origins: str = "http://localhost:8000,https://buddhakorea.com,https://www.buddhakorea.com,null,file://"

    # Rate Limiting
    rate_limit_per_hour: int = 100

    # Logging
    log_level: str = "info"

    # Retrieval Configuration
    top_k_retrieval: int = 10
    max_context_tokens: int = 8000

    # Chunking Configuration
    chunk_size: int = 1024
    chunk_overlap: int = 200

    # Performance
    max_workers: int = 4
    batch_size: int = 32

    class Config:
        env_file = ".env"
        case_sensitive = False


config = AppConfig()

# Configure logging
logger.remove()
logger.add(
    "logs/app.log",
    rotation="500 MB",
    retention="10 days",
    level=config.log_level.upper(),
    format="{time:YYYY-MM-DD HH:mm:ss} | {level} | {message}"
)
logger.add(lambda msg: print(msg, end=""), level=config.log_level.upper())


# ============================================================================
# Pydantic Models
# ============================================================================

class ChatRequest(BaseModel):
    """Request model for chat endpoint."""
    query: str = Field(..., min_length=1, max_length=2000, description="User question")
    language: Optional[str] = Field(default="auto", description="Interface language (ko/en/auto)")
    collection: Optional[str] = Field(default="all", description="Text collection to search (all/chinese/english/korean)")
    max_sources: int = Field(default=5, ge=1, le=20, description="Maximum number of source citations")
    sutra_filter: Optional[str] = Field(default=None, description="Filter by specific sutra ID (e.g., 'T01n0001' for 장아함경)")
    detailed_mode: bool = Field(default=False, description="Enable detailed mode for comprehensive answers (activated by /자세히 prefix)")


class SourceDocument(BaseModel):
    """Source document citation."""
    title: str
    text_id: str
    excerpt: str
    score: Optional[float] = None
    metadata: Dict[str, Any] = {}


class ChatResponse(BaseModel):
    """Response model for chat endpoint."""
    response: str
    sources: List[SourceDocument]
    model: str
    latency_ms: int
    collection: str


class CollectionInfo(BaseModel):
    """Information about a text collection."""
    name: str
    document_count: int
    language: str
    description: str


class HealthResponse(BaseModel):
    """Health check response."""
    status: str
    version: str
    chroma_connected: bool
    llm_configured: bool


# ============================================================================
# Global State & Dependencies
# ============================================================================

class AppState:
    """Global application state."""
    def __init__(self):
        self.chroma_client: Optional[chromadb.Client] = None
        self.vectorstore: Optional[Chroma] = None
        self.llm: Optional[Any] = None
        self.qa_chain: Optional[RetrievalQA] = None
        self.embeddings: Optional[Any] = None
        self.hyde_expander: Optional[Any] = None


app_state = AppState()


# ============================================================================
# Startup & Shutdown
# ============================================================================

@asynccontextmanager
async def lifespan(app: FastAPI):
    """Initialize and cleanup application resources."""

    logger.info("Starting Buddhist AI Chatbot...")

    # Initialize embeddings
    if config.use_gemini_for_queries:
        logger.info("🚀 Using Gemini API for query embeddings")
        from gemini_query_embedder import GeminiQueryEmbedder

        app_state.embeddings = GeminiQueryEmbedder(
            project_id=config.gcp_project_id,
            location=config.gcp_location
        )
    else:
        logger.info(f"Loading embedding model: {config.embedding_model}")
        if "text-embedding" in config.embedding_model:
            # OpenAI embeddings
            if not config.openai_api_key:
                logger.error("OpenAI API key not found for embedding model")
                raise ValueError("OPENAI_API_KEY required for OpenAI embeddings")
            app_state.embeddings = OpenAIEmbeddings(
                model=config.embedding_model,
                openai_api_key=config.openai_api_key
            )
        else:
            # Sentence Transformers (local)
            app_state.embeddings = HuggingFaceEmbeddings(
                model_name=config.embedding_model,
                model_kwargs={'device': 'cpu'},
                encode_kwargs={'normalize_embeddings': True}
            )
    logger.info("✓ Embeddings loaded")

    # Initialize ChromaDB
    logger.info(f"Connecting to ChromaDB at {config.chroma_db_path}")
    try:
        app_state.chroma_client = chromadb.PersistentClient(
            path=config.chroma_db_path,
            settings=ChromaSettings(
                anonymized_telemetry=False,
                allow_reset=False
            )
        )

        # Check if collection exists
        try:
            collection = app_state.chroma_client.get_collection(config.chroma_collection_name)
            logger.info(f"✓ Connected to ChromaDB")
            logger.info(f"   Collection: {config.chroma_collection_name}")
            logger.info(f"   Documents: {collection.count():,}")
        except Exception:
            logger.warning(f"No '{config.chroma_collection_name}' collection found - run embedding script first")
            collection = None

        if collection:
            app_state.vectorstore = Chroma(
                client=app_state.chroma_client,
                collection_name=config.chroma_collection_name,
                embedding_function=app_state.embeddings
            )
    except Exception as e:
        logger.error(f"Failed to connect to ChromaDB: {e}")
        app_state.chroma_client = None

    # Initialize LLM
    logger.info(f"Initializing LLM: {config.llm_model}")
    if "claude" in config.llm_model:
        if not config.anthropic_api_key:
            logger.error("Anthropic API key not found")
            raise ValueError("ANTHROPIC_API_KEY required for Claude models")
        app_state.llm = ChatAnthropic(
            model=config.llm_model,
            anthropic_api_key=config.anthropic_api_key,
            temperature=0.3,
            max_tokens=2000
        )
    elif "gemini" in config.llm_model:
        # Gemini models via Vertex AI
        logger.info(f"Using Vertex AI for Gemini model")
        app_state.llm = ChatVertexAI(
            model=config.llm_model,
            project=config.gcp_project_id,
            location=config.gcp_location,
            temperature=0.3,
            max_tokens=6144  # Increased from 2048 to 6144 for longer responses (3x increase)
        )
    else:
        if not config.openai_api_key:
            logger.error("OpenAI API key not found")
            raise ValueError("OPENAI_API_KEY required for GPT models")
        app_state.llm = ChatOpenAI(
            model=config.llm_model,
            openai_api_key=config.openai_api_key,
            temperature=0.3,
            max_tokens=2000
        )
    logger.info("✓ LLM initialized")

    # Initialize HyDE if enabled
    if config.use_hyde:
        logger.info(f"Initializing HyDE with {config.hyde_model}")
        from hyde import HyDEQueryExpander

        if not config.openai_api_key:
            logger.warning("HyDE requires OpenAI API key - disabling")
            app_state.hyde_expander = None
        else:
            app_state.hyde_expander = HyDEQueryExpander(
                api_key=config.openai_api_key,
                model=config.hyde_model
            )
            logger.info(f"✓ HyDE initialized (weight: {config.hyde_weight})")

    # Create RAG chain if vectorstore exists
    if app_state.vectorstore:
        prompt_template = """아래 제공된 불교 경전 내용을 참고하여 질문에 상세하게 답변하세요.

**답변 지침:**
- 경전의 내용을 기반으로 정확하고 명확하게 설명하세요
- 여러 전통(초기불교, 대승불교 등)의 관점이 다를 수 있다면 각 관점을 소개하세요
- 경전 내용을 인용할 때는 인용 표시를 하세요
- 마크다운 헤더(#, ##, ###)를 사용하지 말고 일반 텍스트로 작성하세요
- 자기소개나 서두 없이 바로 본론으로 시작하세요

참고 경전:
{context}

Question: {question}

Answer (한국어 또는 영어로 상세히 답변):"""

        PROMPT = PromptTemplate(
            template=prompt_template,
            input_variables=["context", "question"]
        )

        app_state.qa_chain = RetrievalQA.from_chain_type(
            llm=app_state.llm,
            chain_type="stuff",
            retriever=app_state.vectorstore.as_retriever(
                search_kwargs={"k": config.top_k_retrieval}
            ),
            return_source_documents=True,
            chain_type_kwargs={"prompt": PROMPT}
        )
        logger.info("✓ RAG chain created")

    logger.info("🚀 Buddhist AI Chatbot ready!")

    yield

    # Cleanup
    logger.info("Shutting down...")


# ============================================================================
# FastAPI App
# ============================================================================

app = FastAPI(
    title="Buddhist AI Chatbot",
    description="RAG-powered chatbot for Buddhist texts (CBETA + Pali Canon)",
    version="0.1.0",
    lifespan=lifespan
)

# CORS middleware - Allow all origins for local development
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Allow all origins for local testing
    allow_credentials=False,  # Must be False when allow_origins is ["*"]
    allow_methods=["*"],
    allow_headers=["*"],
)


# ============================================================================
# Rate Limiting (Simple in-memory)
# ============================================================================

from collections import defaultdict, deque

rate_limiter = defaultdict(deque)

def check_rate_limit(client_ip: str) -> bool:
    """Check if client has exceeded rate limit."""
    now = time.time()
    hour_ago = now - 3600

    # Remove old requests
    while rate_limiter[client_ip] and rate_limiter[client_ip][0] < hour_ago:
        rate_limiter[client_ip].popleft()

    # Check limit
    if len(rate_limiter[client_ip]) >= config.rate_limit_per_hour:
        return False

    rate_limiter[client_ip].append(now)
    return True


# ============================================================================
# API Endpoints
# ============================================================================

@app.get("/api/health", response_model=HealthResponse)
async def health_check():
    """Health check endpoint."""
    return HealthResponse(
        status="healthy",
        version="0.1.0",
        chroma_connected=app_state.chroma_client is not None,
        llm_configured=app_state.llm is not None
    )


@app.get("/api/collections", response_model=List[CollectionInfo])
async def list_collections():
    """List available text collections."""
    if not app_state.chroma_client:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="ChromaDB not connected. Run embedding script first."
        )

    collections = []
    try:
        all_collections = app_state.chroma_client.list_collections()

        for coll in all_collections:
            collections.append(CollectionInfo(
                name=coll.name,
                document_count=coll.count(),
                language="multilingual",
                description=f"Buddhist texts collection: {coll.name}"
            ))
    except Exception as e:
        logger.error(f"Error listing collections: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=str(e)
        )

    return collections


@app.post("/api/chat", response_model=ChatResponse)
async def chat(request: ChatRequest, http_request: Request):
    """
    Main chat endpoint - send a question and receive AI response with citations.
    """
    start_time = time.time()

    # Rate limiting
    client_ip = http_request.client.host
    if not check_rate_limit(client_ip):
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail=f"Rate limit exceeded. Maximum {config.rate_limit_per_hour} requests per hour."
        )

    # Check if RAG chain is ready
    if not app_state.qa_chain:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="RAG system not initialized. Ensure ChromaDB has embedded documents."
        )

    logger.info(f"Query from {client_ip}: {request.query[:100]}...")

    try:
        # Apply HyDE query expansion if enabled
        query = request.query
        if app_state.hyde_expander:
            expanded_query = app_state.hyde_expander.expand_query(
                query,
                weight_original=config.hyde_weight
            )
            logger.debug(f"HyDE expansion: {query[:50]}... -> {expanded_query[:100]}...")
            query = expanded_query

        # Prepare detailed mode configuration if requested
        detailed_llm = None
        detailed_k = 20  # More chunks for detailed mode (2x normal mode, supports 16K context)
        if request.detailed_mode:
            logger.info("Detailed mode activated - using extended configuration")
            # Create LLM with higher max_tokens for detailed responses
            if "gemini" in config.llm_model:
                from langchain_google_vertexai import ChatVertexAI
                detailed_llm = ChatVertexAI(
                    model=config.llm_model,
                    project=config.gcp_project_id,
                    location=config.gcp_location,
                    temperature=0.3,
                    max_tokens=8192  # 4x normal for comprehensive answers
                )
            elif "claude" in config.llm_model:
                from langchain_anthropic import ChatAnthropic
                detailed_llm = ChatAnthropic(
                    model=config.llm_model,
                    anthropic_api_key=config.anthropic_api_key,
                    temperature=0.3,
                    max_tokens=8000  # 4x normal
                )
            else:
                from langchain_openai import ChatOpenAI
                detailed_llm = ChatOpenAI(
                    model=config.llm_model,
                    openai_api_key=config.openai_api_key,
                    temperature=0.3,
                    max_tokens=8000  # 4x normal
                )

        # Run RAG query with optional sutra filtering and detailed mode
        if request.sutra_filter:
            # User specified a sutra filter (e.g., "/장아함경" -> "T01n0001")
            logger.info(f"Applying sutra filter: {request.sutra_filter}")

            # Determine retrieval k based on detailed mode
            retrieval_k = (detailed_k * 2) if request.detailed_mode else (config.top_k_retrieval * 2)

            # Create filtered retriever
            filtered_retriever = app_state.vectorstore.as_retriever(
                search_kwargs={
                    "k": retrieval_k,
                    "filter": {"sutra_id": request.sutra_filter}
                }
            )

            # Select prompt template based on detailed mode
            if request.detailed_mode:
                prompt_template = """아래 경전 내용을 바탕으로 **가능한 한 상세하고 포괄적으로** 답변하세요.

**답변 지침:**
1. 경전에 제공된 모든 관련 내용을 최대한 활용하여 **깊이 있게** 설명하세요
2. 여러 관점과 해석이 있다면 모두 소개하세요
3. 경전 원문을 인용할 때는 인용 표시를 하고, 그 의미를 자세히 풀어 설명하세요
4. 역사적 배경, 맥락, 다른 가르침과의 연결고리를 포함하여 종합적으로 설명하세요
5. 다른 경전이나 일반적인 불교 지식은 언급하지 마세요 (오직 이 경전의 내용만)
6. 경전에 전혀 관련이 없는 질문이라면, "이 경전에서는 해당 주제를 다루지 않습니다"라고 답변하세요
7. **마크다운 헤더(#, ##, ###)를 절대 사용하지 마세요**
8. **자기소개나 서두 없이 바로 본론으로 시작하세요**

참고 경전:
{context}

Question: {question}

Answer:"""
            else:
                prompt_template = """아래 경전 내용을 바탕으로 답변하세요.

**답변 지침:**
1. 경전에 제공된 내용을 최대한 활용하여 답변하세요
2. 직접적인 언급이 없더라도 경전에 관련된 내용이 있다면 그것을 바탕으로 설명하세요
3. 경전의 내용을 인용할 때는 인용 표시를 하세요
4. 다른 경전이나 일반적인 불교 지식은 언급하지 마세요 (오직 이 경전의 내용만)
5. 경전에 전혀 관련이 없는 질문이라면, "이 경전에서는 해당 주제를 다루지 않습니다"라고 답변하세요
6. 마크다운 헤더(#, ##, ###)를 사용하지 말고 일반 텍스트로 작성하세요
7. 자기소개나 서두 없이 바로 본론으로 시작하세요

참고 경전:
{context}

Question: {question}

Answer:"""

            PROMPT = PromptTemplate(
                template=prompt_template,
                input_variables=["context", "question"]
            )

            # Create temporary QA chain with filtered retriever
            filtered_qa_chain = RetrievalQA.from_chain_type(
                llm=detailed_llm if detailed_llm else app_state.llm,
                chain_type="stuff",
                retriever=filtered_retriever,
                return_source_documents=True,
                chain_type_kwargs={"prompt": PROMPT}
            )

            result = filtered_qa_chain({"query": query})
            logger.info(f"Filtered query completed for sutra: {request.sutra_filter}")
        elif request.detailed_mode:
            # Detailed mode without sutra filter
            logger.info("Running detailed mode query without sutra filter")

            # Create detailed retriever
            detailed_retriever = app_state.vectorstore.as_retriever(
                search_kwargs={"k": detailed_k}
            )

            # Create detailed prompt
            prompt_template = """아래 제공된 불교 경전 내용을 참고하여 **가능한 한 상세하고 포괄적으로** 답변하세요.

**답변 지침:**
1. 경전에 제공된 모든 관련 내용을 최대한 활용하여 **깊이 있게** 설명하세요
2. 여러 전통(초기불교, 대승불교 등)의 관점이 다를 수 있다면 각 관점을 자세히 소개하세요
3. 경전 원문을 인용할 때는 인용 표시를 하고, 그 의미를 자세히 풀어 설명하세요
4. 역사적 배경, 맥락, 다른 가르침과의 연결고리를 포함하여 종합적으로 설명하세요
5. 가능한 한 구체적인 예시와 비유를 들어 설명하세요
6. **마크다운 헤더(#, ##, ###)를 절대 사용하지 마세요**
7. **자기소개나 서두 없이 바로 본론으로 시작하세요**

참고 경전:
{context}

Question: {question}

Answer:"""

            PROMPT = PromptTemplate(
                template=prompt_template,
                input_variables=["context", "question"]
            )

            # Create detailed QA chain
            detailed_qa_chain = RetrievalQA.from_chain_type(
                llm=detailed_llm,
                chain_type="stuff",
                retriever=detailed_retriever,
                return_source_documents=True,
                chain_type_kwargs={"prompt": PROMPT}
            )

            result = detailed_qa_chain({"query": query})
            logger.info("Detailed query completed")
        else:
            # Use default QA chain (no filtering, no detailed mode)
            result = app_state.qa_chain({"query": query})

        # Format response
        response_text = result["result"]
        source_docs = result.get("source_documents", [])

        # Extract top sources
        sources = []
        for doc in source_docs[:request.max_sources]:
            metadata = doc.metadata
            sources.append(SourceDocument(
                title=metadata.get("title", "Unknown"),
                text_id=metadata.get("sutra_id", "N/A"),
                excerpt=doc.page_content[:300] + "..." if len(doc.page_content) > 300 else doc.page_content,
                metadata=metadata
            ))

        latency_ms = int((time.time() - start_time) * 1000)

        logger.info(f"Response generated in {latency_ms}ms with {len(sources)} sources")

        return ChatResponse(
            response=response_text,
            sources=sources,
            model=config.llm_model,
            latency_ms=latency_ms,
            collection=request.collection
        )

    except Exception as e:
        logger.error(f"Error processing chat request: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error generating response: {str(e)}"
        )


@app.get("/")
async def root():
    """Root endpoint - redirect to test frontend."""
    return HTMLResponse(content=open("test_frontend.html", encoding="utf-8").read())


@app.get("/api/sources")
async def list_sources(
    search: Optional[str] = None,
    tradition: Optional[str] = None,
    period: Optional[str] = None,
    limit: int = 50,
    offset: int = 0
):
    """
    List Buddhist source texts with Korean summaries.

    Query parameters:
    - search: Search in titles and summaries (Korean or Chinese)
    - tradition: Filter by Buddhist tradition (초기불교, 대승불교, 선종, etc.)
    - period: Filter by historical period
    - limit: Number of results (default 50, max 3000)
    - offset: Pagination offset
    """
    try:
        # Load source summaries
        summaries_path = "source_explorer/source_data/source_summaries_ko.json"

        if not os.path.exists(summaries_path):
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail="Source summaries not yet generated. Please run generate_summaries.py first."
            )

        with open(summaries_path, 'r', encoding='utf-8') as f:
            data = json.load(f)

        summaries = data.get('summaries', {})

        # Filter sources
        filtered = []
        for sutra_id, source in summaries.items():
            # Search filter
            if search:
                search_lower = search.lower()
                title_ko = source.get('title_ko', '').lower()
                original_title = source.get('original_title', '').lower()
                brief = source.get('brief_summary', '').lower()

                if not (search_lower in title_ko or search_lower in original_title or search_lower in brief):
                    continue

            # Tradition filter
            if tradition and source.get('tradition', '').lower() != tradition.lower():
                continue

            # Period filter
            if period and source.get('period', '').lower() != period.lower():
                continue

            filtered.append({
                'sutra_id': sutra_id,
                'title_ko': source.get('title_ko', ''),
                'original_title': source.get('original_title', ''),
                'author': source.get('author', ''),
                'brief_summary': source.get('brief_summary', ''),
                'tradition': source.get('tradition', ''),
                'period': source.get('period', ''),
                'volume': source.get('volume', ''),
                'juan': source.get('juan', '')
            })

        # Sort by sutra_id
        filtered.sort(key=lambda x: x['sutra_id'])

        # Pagination
        limit = min(limit, 3000)
        paginated = filtered[offset:offset + limit]

        return {
            'total': len(filtered),
            'limit': limit,
            'offset': offset,
            'sources': paginated
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error listing sources: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=str(e)
        )


@app.get("/api/sources/{sutra_id}")
async def get_source_detail(sutra_id: str):
    """
    Get detailed information about a specific Buddhist text.

    Returns:
    - Full Korean translation and detailed summary
    - Key themes and historical context
    - Original metadata
    """
    try:
        # Load source summaries
        summaries_path = "source_explorer/source_data/source_summaries_ko.json"

        if not os.path.exists(summaries_path):
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail="Source summaries not yet generated."
            )

        with open(summaries_path, 'r', encoding='utf-8') as f:
            data = json.load(f)

        summaries = data.get('summaries', {})

        if sutra_id not in summaries:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Source {sutra_id} not found"
            )

        source = summaries[sutra_id]

        return {
            'sutra_id': sutra_id,
            'title_ko': source.get('title_ko', ''),
            'original_title': source.get('original_title', ''),
            'author': source.get('author', ''),
            'volume': source.get('volume', ''),
            'juan': source.get('juan', ''),
            'brief_summary': source.get('brief_summary', ''),
            'detailed_summary': source.get('detailed_summary', ''),
            'key_themes': source.get('key_themes', []),
            'period': source.get('period', ''),
            'tradition': source.get('tradition', '')
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error getting source detail: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=str(e)
        )


@app.get("/api")
async def api_info():
    """API information endpoint."""
    return {
        "message": "Buddhist AI Chatbot API",
        "version": "0.1.0",
        "endpoints": {
            "health": "/api/health",
            "chat": "/api/chat (POST)",
            "collections": "/api/collections",
            "sources": "/api/sources (GET) - List Buddhist texts",
            "source_detail": "/api/sources/{sutra_id} (GET) - Get text details",
            "docs": "/docs",
            "test_ui": "/"
        }
    }


# ============================================================================
# Error Handlers
# ============================================================================

@app.exception_handler(Exception)
async def global_exception_handler(request: Request, exc: Exception):
    """Global exception handler."""
    logger.error(f"Unhandled exception: {exc}")
    return JSONResponse(
        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        content={"detail": "Internal server error occurred"}
    )


# ============================================================================
# Main Entry Point
# ============================================================================

if __name__ == "__main__":
    import uvicorn

    # Create logs directory
    os.makedirs("logs", exist_ok=True)

    uvicorn.run(
        "main:app",
        host=config.api_host,
        port=config.api_port,
        reload=True,
        log_level=config.log_level.lower()
    )

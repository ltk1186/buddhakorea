"""
Buddhist AI Chatbot - FastAPI Application
OpenNotebook experiment for buddhakorea.com

Provides RAG-powered chat interface for Taishō Tripiṭaka and Pali Canon texts.
"""

import os
import json
import time
import uuid
import asyncio
import sys # ADDED
from pathlib import Path
from datetime import datetime, timedelta
from typing import List, Optional, Dict, Any
from contextlib import asynccontextmanager

from fastapi import FastAPI, HTTPException, Request, status, BackgroundTasks
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse, HTMLResponse, StreamingResponse
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

# Usage tracking
from usage_tracker import log_token_usage, analyze_usage_logs, get_recent_queries, export_usage_csv
from qa_logger import log_qa_pair, get_qa_pairs, export_to_json, analyze_popular_queries

# Tradition normalization
from tradition_normalizer import normalize_tradition, get_normalized_traditions


# ============================================================================
# Configuration
# ============================================================================

class AppConfig(BaseSettings):
    """Application configuration from environment variables."""

    # API Keys
    openai_api_key: Optional[str] = None
    anthropic_api_key: Optional[str] = None

    # Model Configuration
    llm_model: str = "gemini-2.5-pro"  # For detailed/academic modes
    llm_model_fast: str = "gemini-2.5-flash"  # For normal mode (faster responses)
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
    top_k_retrieval_fast: int = 5  # For normal mode (faster responses)
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
# Commented out file logging for production - use stdout/stderr instead
# logger.add(
#     "logs/app.log",
#     rotation="500 MB",
#     retention="10 days",
#     level=config.log_level.upper(),
#     format="{time:YYYY-MM-DD HH:mm:ss} | {level} | {message}"
# )
logger.add(sys.stdout, level=config.log_level.upper(), serialize=True, enqueue=True)


# ============================================================================
# Session Management for Follow-up Questions
# ============================================================================

# In-memory session storage (for production, consider Redis)
CONVERSATION_SESSIONS: Dict[str, Dict[str, Any]] = {}
SESSION_TTL_SECONDS = 3600  # 1 hour
MAX_MESSAGES_PER_SESSION = 20
MAX_CONVERSATION_HISTORY_TURNS = 5  # Keep last 5 turns in context


# ============================================================================
# Response Caching for High-Quality Answers
# ============================================================================

CACHE_FILE_PATH = "cached_responses.json"
RESPONSE_CACHE: Dict[str, Dict[str, Any]] = {}


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
    tradition_filter: Optional[str] = Field(default=None, description="Filter by Buddhist tradition (초기불교, 대승불교, 선종, etc.)")
    detailed_mode: bool = Field(default=False, description="Enable detailed mode for comprehensive answers (activated by /자세히 prefix)")
    # Follow-up question support
    session_id: Optional[str] = Field(default=None, description="Session ID for follow-up questions (optional, created automatically if not provided)")
    is_followup: bool = Field(default=False, description="Whether this is a follow-up question in an existing conversation")


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
    # Follow-up question support
    session_id: str = Field(..., description="Session ID for this conversation (use this for follow-up questions)")
    can_followup: bool = Field(default=True, description="Whether follow-up questions are supported for this response")
    conversation_depth: int = Field(default=1, description="Number of exchanges in this conversation (1 = first question)")
    # Cache support
    from_cache: bool = Field(default=False, description="Whether this response was served from cache")


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


class CacheRequest(BaseModel):
    """Request model for adding to cache."""
    cache_key: str = Field(..., description="Unique identifier for this cached response")
    keywords: List[str] = Field(..., description="Keywords that trigger this cached response")
    response: str = Field(..., description="The response text to cache")
    sources: List[SourceDocument] = Field(..., description="Source documents for this response")
    model: str = Field(..., description="Model name used to generate the response")
    metadata: Dict[str, Any] = Field(default_factory=dict, description="Additional metadata")


class CachedResponseInfo(BaseModel):
    """Information about a cached response."""
    cache_key: str
    keywords: List[str]
    response_preview: str  # First 200 chars
    model: str
    created_at: str
    hit_count: int
    last_hit: Optional[str]


# ============================================================================
# Sutra Library Cache
# ============================================================================

class SutraCache:
    """Simple async cache for sutra library data."""
    def __init__(self):
        self._data: Optional[Dict] = None
        self._metadata: Optional[Dict] = None
        self._lock = asyncio.Lock()

    async def load(self) -> bool:
        """Load sutra data and compute metadata."""
        try:
            path = Path(__file__).parent / "source_explorer/source_data/source_summaries_ko.json"
            # Read file in thread to avoid blocking
            content = await asyncio.to_thread(path.read_text, encoding='utf-8')
            data = json.loads(content)

            # Compute metadata
            summaries = data.get('summaries', {})
            traditions = set()
            themes = set()
            periods = set()

            for source in summaries.values():
                if t := source.get('tradition'):
                    traditions.add(t.strip())
                if p := source.get('period'):
                    periods.add(p.strip())
                # Handle key_themes as string or list
                kt = source.get('key_themes', [])
                if isinstance(kt, str):
                    kt = [kt]
                for theme in kt:
                    if theme.strip():
                        themes.add(theme.strip())

            metadata = {
                'total': len(summaries),
                'traditions': sorted(traditions),
                'themes': sorted(themes),
                'periods': sorted(periods)
            }

            async with self._lock:
                self._data = data
                self._metadata = metadata
                logger.info(f"Sutra cache loaded: {metadata['total']} sutras")
            return True
        except Exception as e:
            logger.error(f"Failed to load sutra cache: {e}")
            return False

    async def get_data(self) -> Dict:
        """Get cached data, load if needed."""
        if self._data is None:
            await self.load()
        if self._data is None:
            raise HTTPException(503, "Sutra data unavailable")
        return self._data

    async def get_metadata(self) -> Dict:
        """Get precomputed metadata."""
        if self._metadata is None:
            await self.load()
        if self._metadata is None:
            raise HTTPException(503, "Sutra metadata unavailable")
        return self._metadata

# Initialize global sutra cache
sutra_cache = SutraCache()


# ============================================================================
# Global State & Dependencies
# ============================================================================

class AppState:
    """Global application state."""
    def __init__(self):
        self.chroma_client: Optional[chromadb.Client] = None
        self.vectorstore: Optional[Chroma] = None
        self.llm: Optional[Any] = None  # For detailed/academic modes
        self.llm_fast: Optional[Any] = None  # For normal mode (faster)
        self.qa_chain: Optional[RetrievalQA] = None
        self.embeddings: Optional[Any] = None
        self.hyde_expander: Optional[Any] = None


app_state = AppState()


# ============================================================================
# Session Management Helper Functions
# ============================================================================

def create_or_get_session(session_id: Optional[str] = None) -> str:
    """
    Create a new session or retrieve existing one.

    Args:
        session_id: Optional existing session ID

    Returns:
        Session ID (new or existing)
    """
    # If session_id provided, check if it exists and is not expired
    if session_id and session_id in CONVERSATION_SESSIONS:
        session = CONVERSATION_SESSIONS[session_id]
        # Check if session expired
        if datetime.now() - session['last_accessed'] > timedelta(seconds=SESSION_TTL_SECONDS):
            logger.info(f"Session {session_id[:8]}... expired, creating new session")
            del CONVERSATION_SESSIONS[session_id]
            session_id = None
        else:
            # Update last accessed time
            session['last_accessed'] = datetime.now()
            logger.info(f"Reusing session {session_id[:8]}... (depth: {len(session['messages'])//2})")
            return session_id

    # Create new session
    new_session_id = str(uuid.uuid4())
    CONVERSATION_SESSIONS[new_session_id] = {
        'session_id': new_session_id,
        'created_at': datetime.now(),
        'last_accessed': datetime.now(),
        'messages': [],  # List of {'role': 'user'|'assistant', 'content': str}
        'context_chunks': [],  # Retrieved document chunks
        'metadata': {}  # Store query parameters (detailed_mode, sutra_filter, etc.)
    }
    logger.info(f"Created new session {new_session_id[:8]}...")
    return new_session_id


def update_session(
    session_id: str,
    user_message: str,
    assistant_message: str,
    context_chunks: List[Any],
    metadata: Dict[str, Any]
):
    """
    Update session with new message exchange and context.

    Args:
        session_id: Session ID
        user_message: User's question
        assistant_message: Assistant's response
        context_chunks: Retrieved context chunks
        metadata: Query metadata (detailed_mode, sutra_filter, etc.)
    """
    if session_id not in CONVERSATION_SESSIONS:
        logger.warning(f"Session {session_id[:8]}... not found, cannot update")
        return

    session = CONVERSATION_SESSIONS[session_id]

    # Add messages
    session['messages'].append({'role': 'user', 'content': user_message})
    session['messages'].append({'role': 'assistant', 'content': assistant_message})

    # Store context chunks (only if this is the first query or context changed significantly)
    if not session['context_chunks'] or not metadata.get('is_followup', False):
        session['context_chunks'] = context_chunks

    # Update metadata
    session['metadata'].update(metadata)

    # Enforce max messages limit
    if len(session['messages']) > MAX_MESSAGES_PER_SESSION * 2:  # *2 because user+assistant pair
        # Remove oldest pair
        session['messages'] = session['messages'][2:]
        logger.info(f"Session {session_id[:8]}... trimmed to {len(session['messages'])//2} exchanges")

    session['last_accessed'] = datetime.now()


def get_session_context(session_id: str) -> Dict[str, Any]:
    """
    Get session conversation history and context.

    Args:
        session_id: Session ID

    Returns:
        Dict with 'messages', 'context_chunks', 'metadata'
    """
    if session_id not in CONVERSATION_SESSIONS:
        return {'messages': [], 'context_chunks': [], 'metadata': {}}

    session = CONVERSATION_SESSIONS[session_id]

    # Get last N turns for context (to avoid overwhelming LLM)
    recent_messages = session['messages'][-MAX_CONVERSATION_HISTORY_TURNS * 2:]

    return {
        'messages': recent_messages,
        'context_chunks': session['context_chunks'],
        'metadata': session['metadata'],
        'conversation_depth': len(session['messages']) // 2
    }


def cleanup_expired_sessions():
    """Remove sessions that have exceeded TTL."""
    now = datetime.now()
    expired = [
        sid for sid, session in CONVERSATION_SESSIONS.items()
        if now - session['last_accessed'] > timedelta(seconds=SESSION_TTL_SECONDS)
    ]

    for sid in expired:
        del CONVERSATION_SESSIONS[sid]

    if expired:
        logger.info(f"Cleaned up {len(expired)} expired sessions")


def format_conversation_history(messages: List[Dict[str, str]]) -> str:
    """
    Format conversation history for prompt inclusion.

    Args:
        messages: List of message dicts with 'role' and 'content'

    Returns:
        Formatted string for prompt
    """
    if not messages:
        return ""

    formatted = "\n\n이전 대화:\n"
    for msg in messages:
        role_label = "질문" if msg['role'] == 'user' else "답변"
        formatted += f"- {role_label}: {msg['content'][:200]}{'...' if len(msg['content']) > 200 else ''}\n"

    return formatted + "\n"


# ============================================================================
# Response Cache Helper Functions
# ============================================================================

def load_response_cache():
    """Load cached responses from JSON file."""
    global RESPONSE_CACHE

    try:
        if os.path.exists(CACHE_FILE_PATH):
            with open(CACHE_FILE_PATH, 'r', encoding='utf-8') as f:
                data = json.load(f)
                RESPONSE_CACHE = data.get('cached_responses', {})
            logger.info(f"Loaded {len(RESPONSE_CACHE)} cached responses")
        else:
            RESPONSE_CACHE = {}
            logger.info("No cache file found, starting with empty cache")
    except Exception as e:
        logger.error(f"Error loading cache: {e}")
        RESPONSE_CACHE = {}


def save_response_cache():
    """Save cached responses to JSON file."""
    try:
        data = {
            'version': '1.0',
            'cached_responses': RESPONSE_CACHE
        }
        with open(CACHE_FILE_PATH, 'w', encoding='utf-8') as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
        logger.info(f"Saved {len(RESPONSE_CACHE)} cached responses")
    except Exception as e:
        logger.error(f"Error saving cache: {e}")


def check_cached_response(query: str) -> Optional[Dict[str, Any]]:
    """
    Check if query matches any cached response keywords.

    Args:
        query: User's question

    Returns:
        Cached response dict if match found, None otherwise
    """
    query_lower = query.lower().strip()

    for cache_key, cache_data in RESPONSE_CACHE.items():
        keywords = cache_data.get('keywords', [])

        # Check if any keyword matches the query
        for keyword in keywords:
            if keyword.lower() in query_lower:
                # Increment hit count
                cache_data['hit_count'] = cache_data.get('hit_count', 0) + 1
                cache_data['last_hit'] = datetime.now().isoformat()
                save_response_cache()

                logger.info(f"✓ Cache hit for '{cache_key}' (keyword: '{keyword}', hits: {cache_data['hit_count']})")
                return cache_data

    return None


def add_to_cache(
    cache_key: str,
    keywords: List[str],
    response: str,
    sources: List[Dict[str, Any]],
    model: str,
    metadata: Dict[str, Any] = None
):
    """
    Add a response to the cache.

    Args:
        cache_key: Unique identifier for this cached response
        keywords: List of keywords that should trigger this cached response
        response: The response text
        sources: List of source documents
        model: Model name used to generate the response
        metadata: Additional metadata
    """
    RESPONSE_CACHE[cache_key] = {
        'keywords': keywords,
        'response': response,
        'sources': sources,
        'model': model,
        'created_at': datetime.now().isoformat(),
        'hit_count': 0,
        'last_hit': None,
        'metadata': metadata or {}
    }
    save_response_cache()
    logger.info(f"Added '{cache_key}' to cache with {len(keywords)} keywords")


def remove_from_cache(cache_key: str) -> bool:
    """
    Remove a response from the cache.

    Args:
        cache_key: Key to remove

    Returns:
        True if removed, False if not found
    """
    if cache_key in RESPONSE_CACHE:
        del RESPONSE_CACHE[cache_key]
        save_response_cache()
        logger.info(f"Removed '{cache_key}' from cache")
        return True
    return False


def estimate_tokens(text: str) -> int:
    """
    Estimate token count for a text.
    Rough estimation: ~4 characters per token for English, ~2-3 for Korean/Chinese.

    Args:
        text: Text to estimate tokens for

    Returns:
        Estimated token count
    """
    # Average estimate: 2.5 chars per token for multilingual content
    return int(len(text) / 2.5)


def extract_token_usage(result: Dict[str, Any], query: str, model: str) -> Dict[str, int]:
    """
    Extract token usage from LangChain result or estimate if not available.

    Args:
        result: LangChain result dictionary
        query: Original query text
        model: Model name

    Returns:
        Dictionary with input_tokens and output_tokens
    """
    # Try to extract from llm_output (if available)
    if isinstance(result, dict) and "llm_output" in result:
        llm_output = result["llm_output"]
        if llm_output and isinstance(llm_output, dict):
            token_usage = llm_output.get("token_usage", {})
            if token_usage:
                return {
                    "input_tokens": token_usage.get("prompt_tokens", 0),
                    "output_tokens": token_usage.get("completion_tokens", 0)
                }

    # Fallback: estimate tokens from text
    response_text = result.get("result", "") if isinstance(result, dict) else ""

    # Estimate input tokens (query + context)
    # Context estimation: assume average of 10 chunks × 800 tokens
    estimated_context_tokens = 8000
    estimated_query_tokens = estimate_tokens(query)

    # Estimate output tokens from response
    estimated_output_tokens = estimate_tokens(response_text)

    logger.debug(f"Token estimation (fallback): {estimated_query_tokens + estimated_context_tokens}in + {estimated_output_tokens}out")

    return {
        "input_tokens": estimated_query_tokens + estimated_context_tokens,
        "output_tokens": estimated_output_tokens
    }


# ============================================================================
# Startup & Shutdown
# ============================================================================

@asynccontextmanager
async def lifespan(app: FastAPI):
    """Initialize and cleanup application resources."""

    logger.info("Starting Buddhist AI Chatbot...")

    # Load response cache
    load_response_cache()

    # Load sutra library cache
    logger.info("Loading sutra library cache...")
    await sutra_cache.load()

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
            max_tokens=8192  # Increased to 8192 for comprehensive answers (same as detailed mode)
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

    # Initialize Fast LLM for normal mode (streaming + speed)
    logger.info(f"Initializing Fast LLM: {config.llm_model_fast}")
    if "gemini" in config.llm_model_fast:
        app_state.llm_fast = ChatVertexAI(
            model=config.llm_model_fast,
            project=config.gcp_project_id,
            location=config.gcp_location,
            temperature=0.3,
            max_tokens=8192,
            streaming=True  # Enable streaming for fast responses
        )
    elif "claude" in config.llm_model_fast:
        app_state.llm_fast = ChatAnthropic(
            model=config.llm_model_fast,
            anthropic_api_key=config.anthropic_api_key,
            temperature=0.3,
            max_tokens=8192,
            streaming=True
        )
    else:
        app_state.llm_fast = ChatOpenAI(
            model=config.llm_model_fast,
            openai_api_key=config.openai_api_key,
            temperature=0.3,
            max_tokens=8192,
            streaming=True
        )
    logger.info("✓ Fast LLM initialized")

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
        prompt_template = """아래 제공된 불교 문헌 내용을 참고하여 질문에 상세하게 답변하세요.

**답변 지침:**
- 문헌의 내용을 기반으로 정확하고 명확하게 설명하세요
- 여러 전통(초기불교, 대승불교 등)의 관점이 다를 수 있다면 각 관점을 소개하세요
- 문헌 내용을 인용할 때는 인용 표시를 하세요
- 마크다운 헤더(#, ##, ###)를 사용하지 말고 일반 텍스트로 작성하세요
- 자기소개나 서두 없이 바로 본론으로 시작하세요

참고 문헌:
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

# Mount static files for library CSS and JS
app.mount("/css", StaticFiles(directory="css"), name="css")
app.mount("/js", StaticFiles(directory="js"), name="js")


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

    # Check cache for this query (only for non-follow-up questions)
    if not request.is_followup:
        cached_response = check_cached_response(request.query)
        if cached_response:
            # Return cached response immediately
            latency_ms = int((time.time() - start_time) * 1000)

            # Convert cached sources to SourceDocument objects
            cached_sources = [
                SourceDocument(**source) if isinstance(source, dict) else source
                for source in cached_response.get('sources', [])
            ]

            # Create new session for cached response
            session_id = create_or_get_session(request.session_id)

            # Log cached query (no tokens used)
            log_token_usage(
                query=request.query,
                response=cached_response['response'],
                input_tokens=0,
                output_tokens=0,
                model=cached_response.get('model', config.llm_model),
                mode="cached",
                session_id=session_id,
                latency_ms=latency_ms,
                from_cache=True
            )

            return ChatResponse(
                response=cached_response['response'],
                sources=cached_sources[:request.max_sources],
                model=cached_response.get('model', config.llm_model),
                latency_ms=latency_ms,
                collection=request.collection,
                session_id=session_id,
                can_followup=True,
                conversation_depth=1,
                from_cache=True
            )

    # Session management for follow-up questions
    session_id = create_or_get_session(request.session_id)
    session_context = get_session_context(session_id)
    is_followup = request.is_followup and len(session_context['messages']) > 0

    if is_followup:
        logger.info(f"Follow-up question (depth: {session_context['conversation_depth'] + 1})")

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

        # Normalize tradition filter if provided (e.g., "선불교" -> "선종")
        tradition_filter_normalized = None
        tradition_sutra_ids = None
        if request.tradition_filter:
            tradition_filter_normalized = normalize_tradition(request.tradition_filter)
            logger.info(f"Tradition filter: {request.tradition_filter} -> normalized to: {tradition_filter_normalized}")

            # Get list of sutra_ids matching this tradition from cache
            try:
                cache_data = await sutra_cache.get_data()
                summaries = cache_data.get('summaries', {})
                tradition_sutra_ids = []
                for sutra_id, source in summaries.items():
                    raw_trad = source.get('tradition', '')
                    normalized_trad = normalize_tradition(raw_trad)
                    if normalized_trad == tradition_filter_normalized:
                        tradition_sutra_ids.append(sutra_id)
                logger.info(f"Found {len(tradition_sutra_ids)} sutras for tradition: {tradition_filter_normalized}")
            except Exception as e:
                logger.warning(f"Failed to get tradition sutra list: {e}")
                tradition_sutra_ids = None

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
                prompt_template = """아래 문헌 내용을 바탕으로 **가능한 한 상세하고 포괄적으로** 답변하세요.

**답변 지침:**
1. 문헌에 제공된 모든 관련 내용을 최대한 활용하여 **깊이 있게** 설명하세요
2. 여러 관점과 해석이 있다면 모두 소개하세요
3. 문헌 원문을 인용할 때는 인용 표시를 하고, 그 의미를 자세히 풀어 설명하세요
4. 역사적 배경, 맥락, 다른 가르침과의 연결고리를 포함하여 종합적으로 설명하세요
5. 다른 문헌이나 일반적인 불교 지식은 언급하지 마세요 (오직 이 문헌의 내용만)
6. 문헌에 전혀 관련이 없는 질문이라면, "이 문헌에서는 해당 주제를 다루지 않습니다"라고 답변하세요
7. **마크다운 헤더(#, ##, ###)를 절대 사용하지 마세요**
8. **자기소개나 서두 없이 바로 본론으로 시작하세요**

참고 문헌:
{context}

Question: {question}

Answer:"""
            else:
                prompt_template = """아래 문헌 내용을 바탕으로 답변하세요.

**답변 지침:**
1. 문헌에 제공된 내용을 최대한 활용하여 답변하세요
2. 직접적인 언급이 없더라도 문헌에 관련된 내용이 있다면 그것을 바탕으로 설명하세요
3. 문헌의 내용을 인용할 때는 인용 표시를 하세요
4. 다른 문헌이나 일반적인 불교 지식은 언급하지 마세요 (오직 이 문헌의 내용만)
5. 문헌에 전혀 관련이 없는 질문이라면, "이 문헌에서는 해당 주제를 다루지 않습니다"라고 답변하세요
6. 마크다운 헤더(#, ##, ###)를 사용하지 말고 일반 텍스트로 작성하세요
7. 자기소개나 서두 없이 바로 본론으로 시작하세요

참고 문헌:
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
        elif tradition_sutra_ids and len(tradition_sutra_ids) > 0:
            # Tradition filter active - search only within matching sutras
            logger.info(f"Applying tradition filter: {tradition_filter_normalized} ({len(tradition_sutra_ids)} sutras)")

            # Determine retrieval k based on detailed mode
            retrieval_k = (detailed_k * 2) if request.detailed_mode else (config.top_k_retrieval * 2)

            # Create filtered retriever using $in operator for multiple sutra_ids
            filtered_retriever = app_state.vectorstore.as_retriever(
                search_kwargs={
                    "k": retrieval_k,
                    "filter": {"sutra_id": {"$in": tradition_sutra_ids}}
                }
            )

            # Select prompt template based on detailed mode
            if request.detailed_mode:
                prompt_template = """아래 {tradition} 문헌 내용을 바탕으로 **가능한 한 상세하고 포괄적으로** 답변하세요.

**답변 지침:**
1. 문헌에 제공된 모든 관련 내용을 최대한 활용하여 **깊이 있게** 설명하세요
2. {tradition}의 관점과 해석을 중심으로 답변하세요
3. 문헌 원문을 인용할 때는 인용 표시를 하고, 그 의미를 자세히 풀어 설명하세요
4. 역사적 배경, 맥락을 포함하여 종합적으로 설명하세요
5. **마크다운 헤더(#, ##, ###)를 절대 사용하지 마세요**
6. **자기소개나 서두 없이 바로 본론으로 시작하세요**

참고 문헌:
{{context}}

Question: {{question}}

Answer:""".replace("{tradition}", tradition_filter_normalized)
            else:
                prompt_template = """아래 {tradition} 문헌 내용을 바탕으로 답변하세요.

**답변 지침:**
1. 문헌에 제공된 내용을 최대한 활용하여 답변하세요
2. {tradition}의 관점에서 설명하세요
3. 문헌의 내용을 인용할 때는 인용 표시를 하세요
4. 마크다운 헤더(#, ##, ###)를 사용하지 말고 일반 텍스트로 작성하세요
5. 자기소개나 서두 없이 바로 본론으로 시작하세요

참고 문헌:
{{context}}

Question: {{question}}

Answer:""".replace("{tradition}", tradition_filter_normalized)

            PROMPT = PromptTemplate(
                template=prompt_template,
                input_variables=["context", "question"]
            )

            # Create QA chain with tradition filter
            tradition_qa_chain = RetrievalQA.from_chain_type(
                llm=detailed_llm if detailed_llm else app_state.llm,
                chain_type="stuff",
                retriever=filtered_retriever,
                return_source_documents=True,
                chain_type_kwargs={"prompt": PROMPT}
            )

            result = tradition_qa_chain({"query": query})
            logger.info(f"Tradition-filtered query completed: {tradition_filter_normalized}")
        elif request.detailed_mode:
            # Detailed mode without sutra filter
            logger.info("Running detailed mode query without sutra filter")

            # Create detailed retriever
            detailed_retriever = app_state.vectorstore.as_retriever(
                search_kwargs={"k": detailed_k}
            )

            # Create detailed prompt
            prompt_template = """아래 제공된 불교 문헌 내용을 참고하여 **가능한 한 상세하고 포괄적으로** 답변하세요.

**답변 지침:**
1. 문헌에 제공된 모든 관련 내용을 최대한 활용하여 **깊이 있게** 설명하세요
2. 여러 전통(초기불교, 대승불교 등)의 관점이 다를 수 있다면 각 관점을 자세히 소개하세요
3. 문헌 원문을 인용할 때는 인용 표시를 하고, 그 의미를 자세히 풀어 설명하세요
4. 역사적 배경, 맥락, 다른 가르침과의 연결고리를 포함하여 종합적으로 설명하세요
5. 가능한 한 구체적인 예시와 비유를 들어 설명하세요
6. **마크다운 헤더(#, ##, ###)를 절대 사용하지 마세요**
7. **자기소개나 서두 없이 바로 본론으로 시작하세요**

참고 문헌:
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

        # Get title lookup from cache
        try:
            cache_data = await sutra_cache.get_data()
            summaries = cache_data.get('summaries', {})
        except:
            summaries = {}

        # Extract top sources with proper titles
        sources = []
        seen_sutras = set()  # Deduplicate
        for doc in source_docs[:request.max_sources]:
            metadata = doc.metadata
            sutra_id = metadata.get("sutra_id", "N/A")

            # Skip duplicates
            if sutra_id in seen_sutras:
                continue
            seen_sutras.add(sutra_id)

            # Look up proper title from cache
            cached_info = summaries.get(sutra_id, {})
            title = cached_info.get("title_ko") or metadata.get("title_ko") or metadata.get("title", sutra_id)

            sources.append(SourceDocument(
                title=title,
                text_id=sutra_id,
                excerpt=doc.page_content[:300] + "..." if len(doc.page_content) > 300 else doc.page_content,
                metadata=metadata
            ))

        latency_ms = int((time.time() - start_time) * 1000)

        logger.info(f"Response generated in {latency_ms}ms with {len(sources)} sources")

        # Update session with this exchange
        update_session(
            session_id=session_id,
            user_message=request.query,
            assistant_message=response_text,
            context_chunks=source_docs,
            metadata={
                'detailed_mode': request.detailed_mode,
                'sutra_filter': request.sutra_filter,
                'is_followup': is_followup
            }
        )

        # Get updated conversation depth
        updated_context = get_session_context(session_id)
        conversation_depth = updated_context['conversation_depth']

        # Track token usage
        token_usage = extract_token_usage(result, request.query, config.llm_model)

        # Log token usage to file
        log_token_usage(
            query=request.query,
            response=response_text,
            input_tokens=token_usage["input_tokens"],
            output_tokens=token_usage["output_tokens"],
            model=config.llm_model,
            mode="detailed" if request.detailed_mode else "normal",
            session_id=session_id,
            latency_ms=latency_ms,
            from_cache=False
        )

        # Log complete Q&A pair
        # Extract source IDs from SourceDocument objects
        source_ids = []
        for s in sources:
            if isinstance(s, SourceDocument):
                source_ids.append(s.text_id)
            elif isinstance(s, dict):
                source_ids.append(s.get('source_id', s.get('text_id', '')))
            else:
                source_ids.append(str(s))

        log_qa_pair(
            query=request.query,
            response=response_text,
            detailed_mode=request.detailed_mode,
            sutra_filter=request.sutra_filter,
            session_id=session_id,
            model=config.llm_model,
            sources=source_ids,
            input_tokens=token_usage["input_tokens"],
            output_tokens=token_usage["output_tokens"],
            latency_ms=latency_ms,
            from_cache=False
        )

        return ChatResponse(
            response=response_text,
            sources=sources,
            model=config.llm_model,
            latency_ms=latency_ms,
            collection=request.collection,
            session_id=session_id,
            can_followup=True,
            conversation_depth=conversation_depth
        )

    except Exception as e:
        logger.error(f"Error processing chat request: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error generating response: {str(e)}"
        )


# ============================================================================
# Streaming Chat Endpoint
# ============================================================================

@app.post("/api/chat/stream")
async def chat_stream(request: ChatRequest, http_request: Request):
    """
    Streaming chat endpoint - sends responses as Server-Sent Events (SSE).
    Provides real-time progress updates and token-by-token response streaming.

    SSE Event Types:
    - stage: Progress updates (searching, analyzing, generating)
    - content: Streaming response content
    - sources: Source documents (sent at end)
    - done: Stream completion signal
    - error: Error message
    """
    start_time = time.time()

    # Rate limiting
    client_ip = http_request.client.host
    if not check_rate_limit(client_ip):
        async def rate_limit_error():
            yield f"data: {json.dumps({'type': 'error', 'message': 'Rate limit exceeded'})}\n\n"
        return StreamingResponse(rate_limit_error(), media_type="text/event-stream")

    # Check if RAG system is ready
    if not app_state.vectorstore:
        async def system_error():
            yield f"data: {json.dumps({'type': 'error', 'message': 'RAG system not initialized'})}\n\n"
        return StreamingResponse(system_error(), media_type="text/event-stream")

    logger.info(f"[Stream] Query from {client_ip}: {request.query[:100]}...")

    async def generate():
        try:
            # Stage 1: Searching
            yield f"data: {json.dumps({'type': 'stage', 'stage': 'searching', 'message': '문헌 검색 중...'})}\n\n"
            await asyncio.sleep(0.1)  # Small delay for UI update

            # Determine retrieval k based on detailed mode
            is_detailed = request.detailed_mode
            retrieval_k = config.top_k_retrieval if is_detailed else config.top_k_retrieval_fast

            # Select LLM based on mode
            llm = app_state.llm if is_detailed else app_state.llm_fast
            model_name = config.llm_model if is_detailed else config.llm_model_fast

            logger.info(f"[Stream] Mode: {'detailed' if is_detailed else 'normal'}, k={retrieval_k}, model={model_name}")

            # Apply HyDE if enabled
            query = request.query
            if app_state.hyde_expander and not is_detailed:
                query = app_state.hyde_expander.expand_query(query, weight_original=config.hyde_weight)

            # Vector search with optional sutra/tradition filter
            search_kwargs = {"k": retrieval_k}

            # Handle tradition filter - get matching sutra_ids
            tradition_sutra_ids = None
            tradition_filter_normalized = None
            if request.tradition_filter:
                tradition_filter_normalized = normalize_tradition(request.tradition_filter)
                logger.info(f"[Stream] Tradition filter: {request.tradition_filter} -> {tradition_filter_normalized}")

                try:
                    cache_data = await sutra_cache.get_data()
                    summaries = cache_data.get('summaries', {})
                    tradition_sutra_ids = []
                    for sutra_id, source in summaries.items():
                        raw_trad = source.get('tradition', '')
                        normalized_trad = normalize_tradition(raw_trad)
                        if normalized_trad == tradition_filter_normalized:
                            tradition_sutra_ids.append(sutra_id)
                    logger.info(f"[Stream] Found {len(tradition_sutra_ids)} sutras for tradition: {tradition_filter_normalized}")
                except Exception as e:
                    logger.warning(f"[Stream] Failed to get tradition sutra list: {e}")

            # Apply filter based on priority: sutra_filter > tradition_filter
            if request.sutra_filter:
                search_kwargs["filter"] = {"sutra_id": request.sutra_filter}
            elif tradition_sutra_ids and len(tradition_sutra_ids) > 0:
                search_kwargs["filter"] = {"sutra_id": {"$in": tradition_sutra_ids}}

            docs = app_state.vectorstore.similarity_search(query, **search_kwargs)

            # Stage 2: Analyzing
            yield f"data: {json.dumps({'type': 'stage', 'stage': 'analyzing', 'message': '관련 구절 분석 중...'})}\n\n"
            await asyncio.sleep(0.1)

            # Prepare context from retrieved documents
            context = "\n\n---\n\n".join([doc.page_content for doc in docs])

            # Prepare sources with proper titles from cache
            sources = []
            seen_sutras = set()  # Deduplicate sources by sutra_id

            # Get title lookup from cache
            try:
                cache_data = await sutra_cache.get_data()
                summaries = cache_data.get('summaries', {})
            except:
                summaries = {}

            for doc in docs:
                meta = doc.metadata
                sutra_id = meta.get("sutra_id", meta.get("text_id", "unknown"))

                # Skip duplicates
                if sutra_id in seen_sutras:
                    continue
                seen_sutras.add(sutra_id)

                # Look up proper title from cache
                cached_info = summaries.get(sutra_id, {})
                title = cached_info.get("title_ko") or meta.get("title_ko") or meta.get("title", sutra_id)

                sources.append({
                    "text_id": sutra_id,
                    "title": title,
                    "chunk_index": meta.get("chunk_index", 0),
                    "relevance_score": meta.get("relevance_score", 0.0)
                })

            # Stage 3: Generating
            yield f"data: {json.dumps({'type': 'stage', 'stage': 'generating', 'message': '답변 작성 중...'})}\n\n"
            await asyncio.sleep(0.1)

            # Build prompt
            if is_detailed:
                prompt_template = """아래 문헌 내용을 바탕으로 **가능한 한 상세하고 포괄적으로** 답변하세요.

**답변 지침:**
1. 문헌에 제공된 모든 관련 내용을 최대한 활용하여 **깊이 있게** 설명하세요
2. 여러 관점과 해석이 있다면 모두 소개하세요
3. 문헌 원문을 인용할 때는 인용 표시를 하고, 그 의미를 자세히 풀어 설명하세요
4. **마크다운 헤더(#, ##, ###)를 절대 사용하지 마세요**
5. **자기소개나 서두 없이 바로 본론으로 시작하세요**

참고 문헌:
{context}

Question: {question}

Answer:"""
            else:
                prompt_template = """아래 제공된 불교 문헌 내용을 참고하여 질문에 답변하세요.

**답변 지침:**
- 문헌의 내용을 기반으로 정확하고 명확하게 설명하세요
- 문헌 내용을 인용할 때는 인용 표시를 하세요
- 마크다운 헤더(#, ##, ###)를 사용하지 말고 일반 텍스트로 작성하세요
- 자기소개나 서두 없이 바로 본론으로 시작하세요

참고 문헌:
{context}

Question: {question}

Answer:"""

            prompt = prompt_template.format(context=context, question=request.query)

            # Stream response from LLM
            full_response = ""
            async for chunk in llm.astream(prompt):
                if hasattr(chunk, 'content') and chunk.content:
                    content = chunk.content
                    full_response += content
                    yield f"data: {json.dumps({'type': 'content', 'content': content})}\n\n"

            # Send sources
            yield f"data: {json.dumps({'type': 'sources', 'sources': sources})}\n\n"

            # Calculate latency
            latency_ms = int((time.time() - start_time) * 1000)

            # Log usage (async, don't wait)
            log_token_usage(
                query=request.query,
                response=full_response[:500],  # Truncate for logging
                input_tokens=0,  # Streaming doesn't provide token counts easily
                output_tokens=0,
                model=model_name,
                mode="stream_detailed" if is_detailed else "stream_normal",
                session_id=None,
                latency_ms=latency_ms,
                from_cache=False
            )

            # Send completion signal
            yield f"data: {json.dumps({'type': 'done', 'latency_ms': latency_ms, 'model': model_name})}\n\n"

            logger.info(f"[Stream] Completed in {latency_ms}ms, model={model_name}")

        except Exception as e:
            logger.error(f"[Stream] Error: {e}")
            yield f"data: {json.dumps({'type': 'error', 'message': str(e)})}\n\n"

    return StreamingResponse(
        generate(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no"  # Disable nginx buffering
        }
    )


@app.get("/api/qa-pairs")
async def get_qa_pairs_endpoint(
    days: int = 7,
    limit: Optional[int] = None,
    detailed_mode_only: bool = False,
    sutra_filter_only: bool = False,
    sutra_filter: Optional[str] = None
):
    """
    Retrieve logged Q&A pairs with optional filtering.

    Query parameters:
    - days: Number of days to retrieve (default 7)
    - limit: Maximum number of pairs to return (most recent first)
    - detailed_mode_only: Only return pairs with detailed_mode=True
    - sutra_filter_only: Only return pairs with sutra_filter set
    - sutra_filter: Only return pairs with specific T-number (e.g., "T0262")

    Returns:
    - List of Q&A pairs with full metadata
    """
    try:
        pairs = get_qa_pairs(
            days=days,
            limit=limit,
            detailed_mode_only=detailed_mode_only,
            sutra_filter_only=sutra_filter_only,
            sutra_filter=sutra_filter
        )

        return {
            "count": len(pairs),
            "days": days,
            "qa_pairs": pairs
        }

    except Exception as e:
        logger.error(f"Error retrieving Q&A pairs: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error retrieving Q&A pairs: {str(e)}"
        )


@app.get("/api/qa-pairs/export")
async def export_qa_pairs_endpoint(
    days: int = 30,
    detailed_mode_only: bool = False,
    sutra_filter_only: bool = False,
    format: str = "json"
):
    """
    Export Q&A pairs to JSON file.

    Query parameters:
    - days: Number of days to export (default 30)
    - detailed_mode_only: Only export pairs with detailed_mode=True
    - sutra_filter_only: Only export pairs with sutra_filter set
    - format: Export format (currently only "json" is supported)

    Returns:
    - Success/failure message with file path
    """
    try:
        if format != "json":
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Only 'json' format is currently supported"
            )

        output_file = "logs/qa_pairs_export.json"
        success = export_to_json(
            output_file=output_file,
            days=days,
            detailed_mode_only=detailed_mode_only,
            sutra_filter_only=sutra_filter_only
        )

        if success:
            return {
                "status": "success",
                "output_file": output_file,
                "days": days,
                "filters": {
                    "detailed_mode_only": detailed_mode_only,
                    "sutra_filter_only": sutra_filter_only
                }
            }
        else:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Export failed"
            )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error exporting Q&A pairs: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error exporting Q&A pairs: {str(e)}"
        )


@app.get("/api/qa-pairs/analytics")
async def get_qa_analytics(days: int = 7, top_n: int = 10):
    """
    Get analytics on Q&A patterns.

    Query parameters:
    - days: Number of days to analyze (default 7)
    - top_n: Number of top queries to return (default 10)

    Returns:
    - Statistics on query patterns, detailed mode usage, sutra filters, and models
    """
    try:
        stats = analyze_popular_queries(days=days, top_n=top_n)

        return {
            "days": days,
            "statistics": stats
        }

    except Exception as e:
        logger.error(f"Error analyzing Q&A pairs: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error analyzing Q&A pairs: {str(e)}"
        )


@app.get("/")
async def home_page():
    """Home page with new UI."""
    return HTMLResponse(content=open("index.html", encoding="utf-8").read())


@app.get("/chat")
async def chat_page():
    """Chat interface (legacy) - redirects to home."""
    return HTMLResponse(content=open("index.html", encoding="utf-8").read())


@app.get("/methodology", response_class=HTMLResponse)
async def methodology_page():
    """Methodology page - shows same page with methodology section."""
    return HTMLResponse(content=open("index.html", encoding="utf-8").read())


@app.get("/api/sutras/meta")
async def get_sutra_metadata():
    """
    Get precomputed metadata for scripture library filters.

    Returns:
    - total: Total sutra count
    - traditions: List of unique Buddhist traditions (raw)
    - traditions_normalized: List of canonical tradition categories
    - themes: List of unique key themes
    - periods: List of unique historical periods
    """
    try:
        metadata = await sutra_cache.get_metadata()
        # Add normalized traditions for cleaner filtering
        metadata['traditions_normalized'] = get_normalized_traditions()
        return metadata
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error getting sutra metadata: {e}")
        raise HTTPException(500, str(e))


@app.get("/api/sources")
async def list_sources(
    search: Optional[str] = None,
    tradition: Optional[str] = None,
    period: Optional[str] = None,
    theme: Optional[str] = None,
    limit: int = 50,
    offset: int = 0
):
    """
    List Buddhist source texts with Korean summaries.

    Query parameters:
    - search: Search in titles and summaries (Korean or Chinese)
    - tradition: Filter by Buddhist tradition (초기불교, 대승불교, 선종, etc.)
    - period: Filter by historical period
    - theme: Filter by key theme (열반, 무상, 인연, etc.)
    - limit: Number of results (default 50, max 3000)
    - offset: Pagination offset
    """
    try:
        # Use cached data
        data = await sutra_cache.get_data()
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

            # Tradition filter - supports both raw and normalized values
            if tradition:
                raw_trad = source.get('tradition', '')
                normalized_trad = normalize_tradition(raw_trad)
                # Match if tradition equals raw value OR normalized value
                if tradition.lower() != raw_trad.lower() and tradition != normalized_trad:
                    continue

            # Period filter
            if period and source.get('period', '').lower() != period.lower():
                continue

            # Theme filter
            if theme:
                key_themes = source.get('key_themes', [])
                if isinstance(key_themes, str):
                    key_themes = [key_themes]
                if theme not in key_themes:
                    continue

            raw_tradition = source.get('tradition', '')
            filtered.append({
                'sutra_id': sutra_id,
                'title_ko': source.get('title_ko', ''),
                'original_title': source.get('original_title', ''),
                'author': source.get('author', ''),
                'brief_summary': source.get('brief_summary', ''),
                'tradition': raw_tradition,
                'tradition_normalized': normalize_tradition(raw_tradition),
                'period': source.get('period', ''),
                'volume': source.get('volume', ''),
                'juan': source.get('juan', ''),
                'key_themes': source.get('key_themes', [])
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

        raw_tradition = source.get('tradition', '')
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
            'tradition': raw_tradition,
            'tradition_normalized': normalize_tradition(raw_tradition)
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error getting source detail: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=str(e)
        )


@app.post("/api/cache")
async def add_cache(request: CacheRequest):
    """
    Add a response to the cache.

    This allows you to save high-quality responses for frequently asked questions.
    """
    try:
        # Convert SourceDocument objects to dicts for JSON serialization
        sources_dict = [
            source.model_dump() if hasattr(source, 'model_dump') else source
            for source in request.sources
        ]

        add_to_cache(
            cache_key=request.cache_key,
            keywords=request.keywords,
            response=request.response,
            sources=sources_dict,
            model=request.model,
            metadata=request.metadata
        )

        return {
            "status": "success",
            "message": f"Response cached with key '{request.cache_key}'",
            "keywords": request.keywords
        }
    except Exception as e:
        logger.error(f"Error adding to cache: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=str(e)
        )


@app.get("/api/cache", response_model=List[CachedResponseInfo])
async def list_cache():
    """
    List all cached responses.

    Returns summary information about each cached response.
    """
    try:
        cached_list = []
        for cache_key, cache_data in RESPONSE_CACHE.items():
            cached_list.append(CachedResponseInfo(
                cache_key=cache_key,
                keywords=cache_data.get('keywords', []),
                response_preview=cache_data.get('response', '')[:200],
                model=cache_data.get('model', ''),
                created_at=cache_data.get('created_at', ''),
                hit_count=cache_data.get('hit_count', 0),
                last_hit=cache_data.get('last_hit')
            ))

        return cached_list
    except Exception as e:
        logger.error(f"Error listing cache: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=str(e)
        )


@app.get("/api/cache/{cache_key}")
async def get_cache(cache_key: str):
    """
    Get a specific cached response by key.

    Returns the full cached response including all sources.
    """
    try:
        if cache_key not in RESPONSE_CACHE:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Cache key '{cache_key}' not found"
            )

        return RESPONSE_CACHE[cache_key]
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error getting cache: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=str(e)
        )


@app.get("/api/usage-stats")
async def get_usage_stats(
    days: int = 7,
    format: str = "json"
):
    """
    Get token usage statistics for the specified period.

    Args:
        days: Number of days to analyze (default: 7, max: 90)
        format: Output format ("json" or "csv")

    Returns:
        Usage statistics including total queries, costs, and breakdowns by mode/model/day
    """
    try:
        # Validate days parameter
        days = min(max(1, days), 90)

        # Get usage statistics
        stats = analyze_usage_logs(days=days)

        if format == "csv":
            # Export to CSV and return file
            import tempfile
            csv_file = tempfile.NamedTemporaryFile(mode='w', delete=False, suffix='.csv')
            csv_path = csv_file.name
            csv_file.close()

            success = export_usage_csv(output_file=csv_path, days=days)

            if success:
                from fastapi.responses import FileResponse
                return FileResponse(
                    csv_path,
                    media_type='text/csv',
                    filename=f'usage_stats_{days}days.csv'
                )
            else:
                raise HTTPException(
                    status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                    detail="Failed to export CSV"
                )

        # Return JSON stats
        return {
            "period_days": days,
            "total_queries": stats['total_queries'],
            "cached_queries": stats.get('cached_queries', 0),
            "api_queries": stats['total_queries'] - stats.get('cached_queries', 0),
            "total_cost_usd": round(stats['total_cost'], 4),
            "tokens": {
                "input": stats['input_tokens'],
                "output": stats['output_tokens'],
                "total": stats['total_tokens']
            },
            "by_mode": {
                mode: {
                    "queries": data['queries'],
                    "cost_usd": round(data['cost'], 4),
                    "tokens": data['tokens'],
                    "avg_cost_per_query": round(data['cost'] / data['queries'], 6) if data['queries'] > 0 else 0
                }
                for mode, data in stats.get('by_mode', {}).items()
            },
            "by_model": {
                model: {
                    "queries": data['queries'],
                    "cost_usd": round(data['cost'], 4),
                    "tokens": data['tokens']
                }
                for model, data in stats.get('by_model', {}).items()
            },
            "by_day": {
                day: {
                    "queries": data['queries'],
                    "cost_usd": round(data['cost'], 4),
                    "tokens": data['tokens']
                }
                for day, data in sorted(stats.get('by_day', {}).items())
            }
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error getting usage stats: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=str(e)
        )


@app.get("/api/recent-queries")
async def get_recent_queries_endpoint(limit: int = 10):
    """
    Get recent queries from usage logs.

    Args:
        limit: Maximum number of queries to return (default: 10, max: 100)

    Returns:
        List of recent query entries with token usage and cost
    """
    try:
        limit = min(max(1, limit), 100)
        queries = get_recent_queries(limit=limit)

        return {
            "count": len(queries),
            "queries": queries
        }

    except Exception as e:
        logger.error(f"Error getting recent queries: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=str(e)
        )


@app.delete("/api/cache/{cache_key}")
async def delete_cache(cache_key: str):
    """
    Delete a cached response by key.
    """
    try:
        if remove_from_cache(cache_key):
            return {
                "status": "success",
                "message": f"Cache key '{cache_key}' deleted"
            }
        else:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Cache key '{cache_key}' not found"
            )
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error deleting cache: {e}")
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

# trigger






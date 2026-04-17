"""
Buddhist AI Chatbot - FastAPI Application
OpenNotebook experiment for buddhakorea.com

Provides RAG-powered chat interface for Taishō Tripiṭaka and Pali Canon texts.
"""

import os
import sys
import json
import time
import asyncio
import uuid
from pathlib import Path
from datetime import datetime, timedelta, timezone, date
from typing import List, Optional, Dict, Any
from contextlib import asynccontextmanager

from fastapi import FastAPI, HTTPException, Request, status, BackgroundTasks, Depends
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from fastapi.staticfiles import StaticFiles
from starlette.middleware.sessions import SessionMiddleware
from pydantic_settings import BaseSettings, SettingsConfigDict
from loguru import logger
import chromadb
from chromadb.config import Settings as ChromaSettings
from langchain_openai import OpenAIEmbeddings
from langchain_community.embeddings import HuggingFaceEmbeddings

# Internal modules
from . import auth, database

# Auth dependencies and quota management
from .dependencies import get_current_user_optional, get_current_user_required
from .quota import get_usage_info
from .chroma_compat import ChromaCompat
from .llm import (
    ChatModelRequest,
    LLMProviderConfig,
    create_chat_llm as create_provider_chat_llm,
    get_provider_for_model,
)
from .rag.chains import create_rag_chain, invoke_rag_chain
from .rag.prompts import NORMAL_PROMPT_ID, build_prompt

# Usage tracking
from .usage_tracker import analyze_usage_logs, export_usage_csv, get_recent_queries

# Pali Studio API (integrated from nikaya_gemini)
# Use absolute import since pali is a sibling package at container root (/app)
from pali.api import router as pali_router
from .admin import router as admin_router
from .api_schemas import ChatRequest, ChatResponse, CachedResponseInfo, CacheRequest, CollectionInfo, HealthResponse, SourceDocument
from .chat_history_service import get_chat_messages, get_user_chat_sessions, save_chat_to_db
from .routers.auth import create_auth_router
from .routers.chat import create_chat_router
from .routers.chat_history import create_chat_history_router
from .routers.public import create_public_router
from pali.db.database import Base as PaliBase, engine as pali_engine, SessionLocal as PaliSessionLocal
from pali.db import models as pali_models  # Ensure models are registered


# ============================================================================
# Configuration
# ============================================================================

class AppConfig(BaseSettings):
    """Application configuration from environment variables."""

    # API Keys
    openai_api_key: Optional[str] = None
    anthropic_api_key: Optional[str] = None
    gemini_api_key: Optional[str] = None
    
    # Auth & Security
    secret_key: str = "your-secret-key-please-change"
    cookie_domain: Optional[str] = None  # None for localhost, ".buddhakorea.com" for production
    cookie_samesite: str = "lax"  # lax, strict, none
    cookie_secure: Optional[bool] = None  # None = auto-detect via proxy headers
    google_client_id: Optional[str] = None
    google_client_secret: Optional[str] = None
    naver_client_id: Optional[str] = None
    naver_client_secret: Optional[str] = None
    kakao_client_id: Optional[str] = None
    kakao_client_secret: Optional[str] = None

    # Admin Login (optional, enables password-based admin access)
    admin_email: Optional[str] = None
    admin_password: Optional[str] = None
    admin_password_hash: Optional[str] = None  # sha256 hex of password
    
    # Database Configuration
    postgres_user: Optional[str] = None
    postgres_password: Optional[str] = None
    postgres_db: Optional[str] = None

    # Model Configuration
    llm_model: str = "gemini-2.5-pro"  # For detailed/academic modes
    llm_model_fast: str = "gemini-2.5-flash"  # For normal mode (faster responses)
    embedding_model: str = "BAAI/bge-m3"  # Better for Classical Chinese (75-80% vs 60-70%)

    # Vector Database
    chroma_db_path: str = "buddhakorea/data/chroma_db"
    chroma_collection_name: str = "cbeta_sutras_gemini"

    # Google Cloud Configuration (for Gemini embeddings)
    gemini_provider: str = "vertex"
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

    model_config = SettingsConfigDict(
        env_file="../.env",  # .env is in project root, not backend/
        case_sensitive=False,
        extra="ignore",
    )


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
# Session Management - Redis (Persistent)
# ============================================================================

from .redis_session import get_session_manager, RedisSessionManager

# Initialize session manager lazily in lifespan
session_manager: Optional[RedisSessionManager] = None
MAX_CONVERSATION_HISTORY_TURNS = 5  # Keep for local context usage if needed


# ============================================================================
# Response Caching for High-Quality Answers
# ============================================================================

CACHE_FILE_PATH = "cached_responses.json"
RESPONSE_CACHE: Dict[str, Dict[str, Any]] = {}


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
            path = Path(__file__).parent.parent.parent / "data/source_data/source_summaries_ko.json"
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
        self.vectorstore: Optional[ChromaCompat] = None
        self.llm: Optional[Any] = None  # For detailed/academic modes
        self.llm_fast: Optional[Any] = None  # For normal mode (faster)
        self.qa_chain: Optional[Any] = None
        self.embeddings: Optional[Any] = None
        self.hyde_expander: Optional[Any] = None


app_state = AppState()


# ============================================================================
# Session Management Helper Functions
# ============================================================================

def create_or_get_session(session_id: Optional[str] = None) -> str:
    """
    Create a new session or retrieve existing one (Redis-backed).

    Args:
        session_id: Optional existing session ID

    Returns:
        Session ID (new or existing)
    """
    if not session_manager:
        logger.warning("Session manager not initialized, using temporary ID")
        return str(uuid.uuid4())
    return session_manager.create_or_get_session(session_id)


def update_session(
    session_id: str,
    user_message: str,
    assistant_message: str,
    context_chunks: List[Any],
    metadata: Dict[str, Any]
):
    """
    Update session with new message exchange and context (Redis-backed).
    """
    if session_manager:
        session_manager.update_session(
            session_id, user_message, assistant_message, context_chunks, metadata
        )


def get_session_context(session_id: str) -> Dict[str, Any]:
    """
    Get session conversation history and context (Redis-backed).
    """
    if not session_manager:
        return {'messages': [], 'context_chunks': [], 'metadata': {}, 'conversation_depth': 0}
    return session_manager.get_session_context(session_id)


def cleanup_expired_sessions():
    """Remove sessions that have exceeded TTL (handled by Redis or fallback)."""
    if session_manager:
        session_manager.cleanup_expired()


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


def create_chat_llm(
    model: str,
    *,
    temperature: float,
    max_tokens: int,
    streaming: bool = False,
) -> Optional[Any]:
    """Create a chat LLM through the provider adapter layer."""

    return create_provider_chat_llm(
        ChatModelRequest(
            model=model,
            temperature=temperature,
            max_tokens=max_tokens,
            streaming=streaming,
        ),
        LLMProviderConfig(
            openai_api_key=config.openai_api_key,
            anthropic_api_key=config.anthropic_api_key,
            gemini_api_key=config.gemini_api_key,
            gemini_provider=config.gemini_provider,
            gcp_project_id=config.gcp_project_id,
            gcp_location=config.gcp_location,
        ),
    )


# ============================================================================
# Startup & Shutdown
# ============================================================================

@asynccontextmanager
async def lifespan(app: FastAPI):
    """Initialize and cleanup application resources."""

    logger.info("Starting Buddhist AI Chatbot...")

    # Initialize Redis session manager first (needed for auth)
    global session_manager
    session_manager = get_session_manager()
    stats = session_manager.get_stats()
    logger.info(f"✓ Session manager initialized: {stats}")

    # Initialize Auth with Redis for CSRF state storage
    redis_client = session_manager.redis_client if session_manager else None
    auth.setup_auth(config, redis_client=redis_client)
    logger.info("✓ Auth initialized")

    # Initialize DB (create tables)
    await database.init_db()
    logger.info("✓ Database initialized")

    # Initialize Pali DB (Sync)
    try:
        PaliBase.metadata.create_all(bind=pali_engine)
        logger.info("✓ Pali Database initialized")
    except Exception as e:
        logger.error(f"Failed to initialize Pali DB: {e}")

    # Load response cache
    load_response_cache()

    # Load sutra library cache
    logger.info("Loading sutra library cache...")
    await sutra_cache.load()

    # Initialize embeddings
    if config.use_gemini_for_queries:
        logger.info("🚀 Using Gemini API for query embeddings")
        from .gemini_query_embedder import GeminiQueryEmbedder

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
            app_state.vectorstore = ChromaCompat(
                client=app_state.chroma_client,
                collection_name=config.chroma_collection_name,
                embedding_function=app_state.embeddings
            )
    except Exception as e:
        logger.error(f"Failed to connect to ChromaDB: {e}")
        app_state.chroma_client = None

    # Initialize LLM
    try:
        logger.info(f"Initializing LLM: {config.llm_model}")
        main_max_tokens = 8192 if "gemini" in config.llm_model.lower() else 2000
        app_state.llm = create_chat_llm(
            config.llm_model,
            temperature=0.3,
            max_tokens=main_max_tokens,
        )
        
        if app_state.llm:
            logger.info("✓ LLM initialized")

        # Initialize Fast LLM
        if app_state.llm:  # Only if main LLM succeeded
            logger.info(f"Initializing Fast LLM: {config.llm_model_fast}")
            app_state.llm_fast = create_chat_llm(
                config.llm_model_fast,
                temperature=0.3,
                max_tokens=8192,
                streaming=True,
            )
            if app_state.llm_fast:
                logger.info("✓ Fast LLM initialized")
    except Exception as e:
        logger.warning(f"LLM initialization failed: {e} - Chat features disabled")
        app_state.llm = None
        app_state.llm_fast = None

    # Initialize HyDE if enabled
    if config.use_hyde:
        logger.info(f"Initializing HyDE with {config.hyde_model}")
        from .hyde import HyDEQueryExpander

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
        app_state.qa_chain = create_rag_chain(
            app_state.llm,
            app_state.vectorstore.as_retriever(
                search_kwargs={"k": config.top_k_retrieval}
            ),
            build_prompt(NORMAL_PROMPT_ID),
        )
        logger.info("✓ LCEL RAG chain created")

    logger.info("🚀 Buddhist AI Chatbot ready!")

    # Initialize scheduler for background tasks
    from .scheduler import scheduler
    from .tasks import run_cleanup

    scheduler.schedule_daily("cleanup_sessions", run_cleanup)
    scheduler_task = asyncio.create_task(scheduler.start())

    yield

    # Cleanup
    logger.info("Shutting down...")
    scheduler.stop()
    try:
        scheduler_task.cancel()
        await scheduler_task
    except asyncio.CancelledError:
        pass


# ============================================================================
# FastAPI App
# ============================================================================

app = FastAPI(
    title="Buddhist AI Chatbot",
    description="RAG-powered chatbot for Buddhist texts (CBETA + Pali Canon)",
    version="0.1.0",
    lifespan=lifespan
)

# Session Middleware for OAuth (important: same_site="lax" allows OAuth redirects)
# Note: https_only=False because nginx terminates SSL and proxies HTTP to backend
app.add_middleware(
    SessionMiddleware,
    secret_key=config.secret_key,
    same_site="lax",  # Required for OAuth redirect flow
    https_only=False,  # nginx handles SSL, backend sees HTTP
    max_age=600,  # 10 minutes for OAuth state
)

# CORS middleware - Allow specific origins with credentials
ALLOWED_ORIGINS = [
    origin.strip()
    for origin in config.allowed_origins.split(",")
    if origin.strip()
]
app.add_middleware(
    CORSMiddleware,
    allow_origins=ALLOWED_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Mount Pali Studio API router
app.include_router(pali_router, prefix="/api/v1/pali")

# Mount Admin API router
app.include_router(admin_router)

# Docker: /app/frontend, Local: ../../frontend relative to backend/app/
FRONTEND_DIR = Path(__file__).parent.parent / "frontend"  # /app/app/../frontend = /app/frontend
if not FRONTEND_DIR.exists():
    FRONTEND_DIR = Path(__file__).parent.parent.parent / "frontend"

# Mount auth and chat history routers
app.include_router(
    create_auth_router(
        config=config,
        auth_module=auth,
        get_current_user_optional_dep=get_current_user_optional,
    )
)
app.include_router(
    create_chat_history_router(
        auth_module=auth,
        logger=logger,
        get_current_user_optional_dep=get_current_user_optional,
        get_current_user_required_dep=get_current_user_required,
        get_user_chat_sessions_fn=get_user_chat_sessions,
        get_chat_messages_fn=get_chat_messages,
    )
)
app.include_router(
    create_chat_router(
        config=config,
        app_state=app_state,
        logger=logger,
        sutra_cache=sutra_cache,
        check_cached_response_fn=check_cached_response,
        create_or_get_session_fn=create_or_get_session,
        get_session_context_fn=get_session_context,
        update_session_fn=update_session,
        create_chat_llm_fn=create_chat_llm,
        extract_token_usage_fn=extract_token_usage,
        invoke_rag_chain_fn=invoke_rag_chain,
        create_rag_chain_fn=create_rag_chain,
        get_provider_for_model_fn=get_provider_for_model,
    )
)
app.include_router(
    create_public_router(
        app_state=app_state,
        logger=logger,
        frontend_dir=FRONTEND_DIR,
        sutra_cache=sutra_cache,
        response_cache=RESPONSE_CACHE,
        add_to_cache_fn=add_to_cache,
        remove_from_cache_fn=remove_from_cache,
        get_usage_info_fn=get_usage_info,
    )
)

if FRONTEND_DIR.exists():
    app.mount("/css", StaticFiles(directory=str(FRONTEND_DIR / "css")), name="css")
    app.mount("/js", StaticFiles(directory=str(FRONTEND_DIR / "js")), name="js")
    app.mount("/assets", StaticFiles(directory=str(FRONTEND_DIR / "assets")), name="assets")
    app.mount("/data", StaticFiles(directory=str(FRONTEND_DIR / "data")), name="data")
    app.mount("/admin", StaticFiles(directory=str(FRONTEND_DIR / "admin"), html=True), name="admin")

    # Mount Pali Studio SPA (React)
    PALI_DIR = FRONTEND_DIR / "pali"
    if PALI_DIR.exists():
        app.mount("/pali", StaticFiles(directory=str(PALI_DIR), html=True), name="pali")
else:
    logger.warning(f"Frontend directory not found at {FRONTEND_DIR}")


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

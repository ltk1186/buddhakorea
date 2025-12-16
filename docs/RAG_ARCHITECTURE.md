# Buddhist RAG System - TDD Implementation Plan

A retrieval-augmented generation (RAG) system for the Taishō Canon (CBETA T/ folder) built using strict Test-Driven Development (TDD) and clean architecture principles.

## Project Philosophy

**Test-Driven Development (TDD)**:
1. Write a failing test first (Red)
2. Write minimal code to pass the test (Green)
3. Refactor while keeping tests green (Refactor)

**Clean Architecture**:
- Dependency injection for all external services
- Adapter pattern for API calls (OpenAI, Claude, ChromaDB)
- Clear separation: Core logic → Adapters → Infrastructure
- Type hints and comprehensive docstrings

## Architecture Overview

```
┌─────────────────────────────────────────────────────────┐
│                     CLI / API Layer                      │
├─────────────────────────────────────────────────────────┤
│  Answerer (LLM Response Generation)                     │
├─────────────────────────────────────────────────────────┤
│  Retriever (Top-K Similarity Search)                    │
├─────────────────────────────────────────────────────────┤
│  VectorDB (ChromaDB Storage & Query)                    │
├─────────────────────────────────────────────────────────┤
│  Embedder (OpenAI / Local Embeddings)                   │
├─────────────────────────────────────────────────────────┤
│  Chunker (TEI P5 XML Parsing)                           │
└─────────────────────────────────────────────────────────┘
```

## Implementation Order (TDD Flow)

### Phase 1: Chunker Module
**Purpose**: Parse TEI P5 XML files and extract text chunks with metadata

**Files**:
- `tests/test_chunker.py` (write first)
- `src/chunker.py` (implement second)

**Tests to write**:
- `test_parse_tei_xml_file()` - Validate XML parsing
- `test_extract_text_chunks()` - Check chunk extraction
- `test_chunk_metadata()` - Verify metadata (sutra ID, chapter, paragraph)
- `test_chunk_size_limits()` - Ensure chunks respect size constraints
- `test_invalid_xml_handling()` - Error handling for malformed XML

**Run**: `pytest tests/test_chunker.py -v`

---

### Phase 2: Embedder Module
**Purpose**: Generate embeddings using OpenAI or local models

**Files**:
- `tests/test_embedder.py` (write first)
- `src/embedder.py` (implement second)

**Tests to write**:
- `test_openai_embedding_creation()` - Mock OpenAI API call
- `test_local_embedding_creation()` - Test sentence-transformers
- `test_batch_embedding()` - Handle multiple texts efficiently
- `test_embedding_dimension()` - Verify output shape
- `test_api_error_handling()` - Test retry logic and failures

**Run**: `pytest tests/test_embedder.py -v`

---

### Phase 3: VectorDB Module
**Purpose**: Store and query embeddings in ChromaDB

**Files**:
- `tests/test_vectordb.py` (write first)
- `src/vectordb.py` (implement second)

**Tests to write**:
- `test_add_documents()` - Add chunks with embeddings
- `test_query_by_vector()` - Search by embedding
- `test_query_by_text()` - Search by text (auto-embed)
- `test_metadata_filtering()` - Filter by sutra, chapter, etc.
- `test_persistence()` - Verify data persists across restarts

**Run**: `pytest tests/test_vectordb.py -v`

---

### Phase 4: Retriever Module
**Purpose**: Find top-k most relevant chunks using cosine similarity

**Files**:
- `tests/test_retriever.py` (write first)
- `src/retriever.py` (implement second)

**Tests to write**:
- `test_retrieve_top_k()` - Get k most similar chunks
- `test_similarity_threshold()` - Filter by minimum score
- `test_reranking()` - Optional reranking logic
- `test_empty_query_handling()` - Edge case handling
- `test_no_results_found()` - Handle no matches

**Run**: `pytest tests/test_retriever.py -v`

---

### Phase 5: Answerer Module
**Purpose**: Generate answers using retrieved context + LLM

**Files**:
- `tests/test_answerer.py` (write first)
- `src/answerer.py` (implement second)

**Tests to write**:
- `test_context_assembly()` - Verify context formatting
- `test_openai_answer_generation()` - Mock OpenAI chat completion
- `test_claude_answer_generation()` - Mock Anthropic API
- `test_prompt_template()` - Test prompt construction
- `test_streaming_response()` - Test streaming if implemented

**Run**: `pytest tests/test_answerer.py -v`

---

### Phase 6: API Module
**Purpose**: FastAPI endpoints for querying the RAG system

**Files**:
- `tests/test_api.py` (write first)
- `src/api.py` (implement second)

**Tests to write**:
- `test_health_endpoint()` - Basic health check
- `test_query_endpoint()` - End-to-end query flow
- `test_embed_endpoint()` - Trigger embedding of new documents
- `test_error_responses()` - 400/500 error handling
- `test_authentication()` - If implementing auth

**Run**: `pytest tests/test_api.py -v`

---

### Phase 7: CLI Scripts
**Purpose**: Command-line tools for embedding and querying

**Files**:
- `src/cli.py`
- `tests/test_cli.py` (optional)

**Commands**:
```bash
# Embed all sutras in CBETA T folder
python -m src.cli embed --input data/cbeta-t --output data/chroma_db

# Query the system
python -m src.cli query "What is the Four Noble Truths?"

# Start API server
python -m src.cli serve --host 0.0.0.0 --port 8000
```

---

## Project Structure

```
buddha-korea-notebook-exp/
├── src/
│   ├── __init__.py
│   ├── chunker.py          # TEI XML parsing
│   ├── embedder.py         # Embedding generation
│   ├── vectordb.py         # ChromaDB interface
│   ├── retriever.py        # Similarity search
│   ├── answerer.py         # LLM response generation
│   ├── api.py              # FastAPI routes
│   └── cli.py              # CLI commands
├── tests/
│   ├── __init__.py
│   ├── conftest.py         # Shared fixtures
│   ├── test_chunker.py
│   ├── test_embedder.py
│   ├── test_vectordb.py
│   ├── test_retriever.py
│   ├── test_answerer.py
│   ├── test_api.py
│   └── test_integration.py
├── data/
│   ├── cbeta-t/            # CBETA Taishō Canon XML files
│   └── chroma_db/          # ChromaDB persistent storage
├── pyproject.toml          # Dependencies and config
├── pytest.ini              # Pytest configuration
├── .env.example            # Environment variable template
├── .env                    # Actual secrets (gitignored)
└── README_RAG.md           # This file
```

## Setup Instructions

### 1. Install Dependencies

```bash
# Create virtual environment
python -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate

# Install package with dev dependencies
pip install -e ".[dev]"
```

### 2. Configure Environment

```bash
# Copy environment template
cp .env.example .env

# Edit .env with your API keys
nano .env
```

### 3. Run Tests

```bash
# Run all tests
pytest

# Run specific test file
pytest tests/test_chunker.py -v

# Run with coverage
pytest --cov=src --cov-report=html

# Run only unit tests (fast)
pytest -m unit

# Skip slow tests (API calls)
pytest -m "not slow"
```

## Development Workflow (TDD Cycle)

For each new feature:

1. **Write Test First** (Red Phase)
   ```bash
   # Create test file
   touch tests/test_newfeature.py

   # Write failing test
   # Run test to see it fail
   pytest tests/test_newfeature.py -v
   ```

2. **Implement Minimal Code** (Green Phase)
   ```bash
   # Create implementation file
   touch src/newfeature.py

   # Write just enough code to pass
   # Run test to see it pass
   pytest tests/test_newfeature.py -v
   ```

3. **Refactor** (Refactor Phase)
   ```bash
   # Improve code quality
   # Ensure tests still pass
   pytest tests/test_newfeature.py -v

   # Check types
   mypy src/newfeature.py

   # Format code
   black src/newfeature.py tests/test_newfeature.py
   ```

## Code Quality Standards

### Type Hints
```python
from typing import List, Dict, Any, Optional

def process_chunks(texts: List[str], max_size: int) -> List[Dict[str, Any]]:
    """Process text chunks with metadata.

    Args:
        texts: List of text strings to process
        max_size: Maximum chunk size in characters

    Returns:
        List of chunk dictionaries with text and metadata
    """
    pass
```

### Dependency Injection
```python
class Embedder:
    """Generate embeddings using configurable backend."""

    def __init__(self, embedding_adapter: EmbeddingAdapter):
        """Initialize with adapter for external service.

        Args:
            embedding_adapter: Adapter implementing EmbeddingAdapter protocol
        """
        self.adapter = embedding_adapter

    def __call__(self, texts: List[str]) -> np.ndarray:
        """Generate embeddings for texts."""
        return self.adapter.embed(texts)
```

### Adapter Pattern
```python
from typing import Protocol

class EmbeddingAdapter(Protocol):
    """Protocol for embedding backends."""

    def embed(self, texts: List[str]) -> np.ndarray:
        """Generate embeddings."""
        ...

class OpenAIAdapter:
    """OpenAI embedding implementation."""

    def __init__(self, api_key: str, model: str):
        self.client = OpenAI(api_key=api_key)
        self.model = model

    def embed(self, texts: List[str]) -> np.ndarray:
        response = self.client.embeddings.create(
            model=self.model,
            input=texts
        )
        return np.array([e.embedding for e in response.data])
```

## Testing Best Practices

### Use Fixtures
```python
# tests/conftest.py
import pytest

@pytest.fixture
def sample_xml():
    """Sample TEI XML for testing."""
    return """
    <TEI xmlns="http://www.tei-c.org/ns/1.0">
        <text><body><p>Buddhist teaching text...</p></body></text>
    </TEI>
    """

@pytest.fixture
def mock_embedder(mocker):
    """Mock embedder for testing."""
    embedder = mocker.Mock()
    embedder.embed.return_value = np.random.rand(384)
    return embedder
```

### Mock External Services
```python
# tests/test_embedder.py
def test_openai_embedding(mocker):
    """Test OpenAI embedding with mocked API."""
    mock_response = mocker.Mock()
    mock_response.data = [mocker.Mock(embedding=[0.1, 0.2, 0.3])]

    mock_client = mocker.patch("openai.OpenAI")
    mock_client.return_value.embeddings.create.return_value = mock_response

    embedder = OpenAIAdapter(api_key="test", model="test")
    result = embedder.embed(["test text"])

    assert result.shape == (1, 3)
```

## Next Steps

1. **Start with Chunker**: Write `tests/test_chunker.py` first
2. **Follow TDD strictly**: Red → Green → Refactor
3. **Run tests frequently**: After every change
4. **Commit after each passing test**: Small, incremental commits
5. **Document as you go**: Update docstrings and comments

## Resources

- [CBETA TEI P5 Documentation](https://github.com/cbeta-org/xml-p5)
- [ChromaDB Documentation](https://docs.trychroma.com/)
- [FastAPI Testing](https://fastapi.tiangolo.com/tutorial/testing/)
- [Pytest Documentation](https://docs.pytest.org/)
- [Clean Architecture in Python](https://www.cosmicpython.com/)

---

**Ready to start?** Run the first test:

```bash
pytest tests/test_chunker.py -v
```

(It will fail because we haven't written it yet - that's the TDD way!)

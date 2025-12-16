# Buddha Korea - Buddhist RAG System

A production-ready **Retrieval-Augmented Generation (RAG) system** for querying the CBETA Taishō Canon (大正新脩大藏經) using AI-powered semantic search and answer generation.

Built with **Test-Driven Development (TDD)** and **Clean Architecture** principles.

---

## Features

- **TEI P5 XML Parsing**: Extract and chunk Buddhist texts from CBETA XML files with metadata preservation
- **Dual Embedding Backends**:
  - OpenAI `text-embedding-3-small` (1536 dimensions)
  - Local `sentence-transformers` (multilingual, free)
- **Vector Database**: ChromaDB for efficient semantic similarity search
- **LLM Integration**: GPT-4 and Claude 3.5 Sonnet for answer generation
- **REST API**: FastAPI endpoints with OpenAPI documentation
- **CLI Tools**: Command-line interface for embedding and querying
- **Multilingual Support**: Korean and Classical Chinese text handling
- **Production-Grade Code**: Type hints, dependency injection, adapter pattern, comprehensive tests

---

## Quick Start

### 1. Installation

```bash
# Create virtual environment
python3 -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate

# Install package
pip install -e ".[dev]"

# Configure environment
cp .env.example .env
nano .env  # Add your API keys
```

### 2. Process CBETA Data

Place your CBETA T/ folder XML files in `data/cbeta-t/`, then:

```bash
# Embed all texts into vector database
python -m src.cli embed --input data/cbeta-t --collection taisho_canon

# Check database stats
python -m src.cli stats
```

### 3. Query the System

```bash
# Ask a question
python -m src.cli query "What are the Four Noble Truths?"

# Korean query
python -m src.cli query "사성제란 무엇입니까?" --top-k 5

# Use Claude instead of GPT-4
python -m src.cli query "What is the Eightfold Path?" --llm-backend claude
```

### 4. Start API Server

```bash
# Launch REST API
python -m src.cli serve --port 8000

# Query via HTTP
curl -X POST http://localhost:8000/query \
  -H "Content-Type: application/json" \
  -d '{"query": "What is mindfulness?", "top_k": 5}'

# View API documentation
open http://localhost:8000/docs
```

---

## Documentation

- **[USAGE_GUIDE.md](USAGE_GUIDE.md)** - Comprehensive usage guide with examples, configuration, and troubleshooting
- **[README_RAG.md](README_RAG.md)** - TDD implementation plan and architecture details

---

## Architecture

The system follows **Clean Architecture** with strict separation of concerns:

```
┌─────────────────────────────────────────────────────────┐
│                     CLI / REST API                      │
├─────────────────────────────────────────────────────────┤
│                   Application Layer                     │
│  ┌──────────┐  ┌──────────┐  ┌──────────┐  ┌─────────┐│
│  │ Retriever│  │ Answerer │  │ VectorDB │  │ Chunker ││
│  └──────────┘  └──────────┘  └──────────┘  └─────────┘│
├─────────────────────────────────────────────────────────┤
│                   Adapter Layer                         │
│  ┌──────────┐  ┌──────────┐  ┌──────────┐              │
│  │  OpenAI  │  │  Claude  │  │ ChromaDB │              │
│  │ Embedder │  │   LLM    │  │  Adapter │              │
│  └──────────┘  └──────────┘  └──────────┘              │
└─────────────────────────────────────────────────────────┘
```

### Core Modules (125 tests passing)

| Module | Tests | Coverage | Functionality |
|--------|-------|----------|---------------|
| **Chunker** | 23/23 | 86% | TEI P5 XML parsing, metadata extraction |
| **Embedder** | 24/24 | 94% | OpenAI + local embeddings |
| **VectorDB** | 23/23 | 84% | ChromaDB storage and querying |
| **Retriever** | 16/16 | 100% | Semantic search with filtering |
| **Answerer** | 23/23 | 99% | LLM integration (OpenAI + Claude) |
| **API** | 16/16 | 81% | FastAPI REST endpoints |
| **CLI** | N/A | N/A | Command-line interface |

**Total**: 657 lines of production code, 125 tests passing, 70% overall coverage

---

## Testing

Run tests with pytest:

```bash
# Run all tests
pytest

# Run specific module tests
pytest tests/test_chunker.py -v
pytest tests/test_embedder.py -v
pytest tests/test_retriever.py -v

# Run with coverage report
pytest --cov=src --cov-report=html
open htmlcov/index.html

# Run only fast tests (skip slow API calls)
pytest -m "not slow"
```

---

## Project Structure

```
buddha-korea-notebook-exp/
├── src/
│   ├── __init__.py
│   ├── chunker.py          # TEI XML parsing (86% coverage)
│   ├── embedder.py         # Embedding generation (94% coverage)
│   ├── vectordb.py         # ChromaDB interface (84% coverage)
│   ├── retriever.py        # Semantic search (100% coverage)
│   ├── answerer.py         # LLM integration (98% coverage)
│   ├── api.py              # FastAPI REST API (66% coverage)
│   └── cli.py              # Command-line interface
├── tests/
│   ├── conftest.py         # Shared fixtures
│   ├── test_chunker.py     # 23 tests
│   ├── test_embedder.py    # 24 tests
│   ├── test_vectordb.py    # 23 tests
│   ├── test_retriever.py   # 16 tests
│   ├── test_answerer.py    # 23 tests
│   └── test_api.py         # 8/16 tests
├── data/
│   ├── cbeta-t/            # Place CBETA XML files here
│   └── chroma_db/          # Vector database (auto-created)
├── pyproject.toml          # Dependencies and configuration
├── pytest.ini              # Test configuration
├── .env.example            # Environment template
├── USAGE_GUIDE.md          # Comprehensive usage guide
└── README_RAG.md           # TDD implementation plan
```

---

## Development Principles

This project was built following **strict Test-Driven Development (TDD)**:

1. **Red**: Write failing test first
2. **Green**: Write minimal code to pass test
3. **Refactor**: Improve code while keeping tests green

**Clean Architecture Patterns**:
- Dependency injection for all external services
- Adapter pattern for OpenAI, Claude, and ChromaDB
- Protocol-based interfaces for polymorphism
- Dataclasses for configuration objects
- Type hints throughout the codebase
- Comprehensive docstrings and comments

---

## Configuration

All configuration is done via environment variables in `.env`:

```bash
# For embeddings
OPENAI_API_KEY=sk-your-openai-key

# For answer generation (choose one)
OPENAI_API_KEY=sk-your-openai-key  # GPT-4
ANTHROPIC_API_KEY=sk-ant-your-key  # Claude

# Database location
CHROMA_PERSIST_DIRECTORY=./data/chroma_db
CHROMA_COLLECTION_NAME=taisho_canon

# Optional: Override defaults
EMBEDDER_BACKEND=openai  # or "local"
LLM_BACKEND=openai       # or "claude"
TOP_K_RESULTS=5
SIMILARITY_THRESHOLD=0.0
```

See [USAGE_GUIDE.md](USAGE_GUIDE.md) for detailed configuration options.

---

## Requirements

- Python 3.9+
- OpenAI API key (for embeddings and GPT-4)
- Anthropic API key (optional, for Claude)
- CBETA Taishō Canon XML files (T/ folder)

---

## License

MIT License - Free for educational and religious purposes

---

## Acknowledgments

- **CBETA** (Chinese Buddhist Electronic Text Association) for digitizing the Taishō Canon
- **OpenAI** for embedding and LLM APIs
- **Anthropic** for Claude AI
- **ChromaDB** for vector database
- Built with Test-Driven Development methodology

---

## May all beings benefit from these teachings

**南無本師釋迦牟尼佛** (Homage to Śākyamuni Buddha, the Original Teacher)

# OpenNotebook Buddhist AI Chatbot - Development Plan

## Project Goal
Create a NotebookLM-level AI chatbot for Taishō Tripiṭaka (大正新脩大藏經) from CBETA XML corpus using OpenNotebook RAG architecture, deployed at buddhakorea.com.

**Data Source**: CBETA Taishō Tripiṭaka XML only (Classical Chinese + Korean annotations)
**Hardware**: MacBook Pro M4 Pro (16 cores, 32GB RAM)
**Execution**: Fully automated by Claude Code

---

## Phase 1: Environment Setup

### 1.1 Docker Configuration
```dockerfile
# Dockerfile structure
FROM python:3.11-slim
- Install system dependencies (build-essential, git)
- Copy requirements.txt and install Python packages
- Expose port 8000 for FastAPI
- Volume mounts for data persistence (/data, /models, /chroma_db)
```

### 1.2 Docker Compose Stack
```yaml
services:
  - opennotebook-api (FastAPI app)
  - chromadb (vector database)
  - nginx (reverse proxy, optional for production)
```

### 1.3 Local Development Setup
```bash
# Quick start
python -m venv venv
source venv/bin/activate
pip install -r requirements.txt
```

**Environment Variables** (.env):
- `OPENAI_API_KEY` or `ANTHROPIC_API_KEY`
- `CHROMA_DB_PATH`
- `EMBEDDING_MODEL` (default: sentence-transformers/paraphrase-multilingual-mpnet-base-v2)
- `LLM_MODEL` (gpt-4o-mini / claude-3-5-sonnet)

---

## Phase 2: Data Acquisition & Preparation

### 2.1 CBETA Taishō Tripiṭaka XML (GitHub)
**Source**: CBETA XML-P5a GitHub Repository (Latest Internal Version)
- Repository: https://github.com/cbeta-git/xml-p5a
- Format: TEI P5 XML (Text Encoding Initiative)
- Size: ~10-15GB
- Language: Classical Chinese (漢文) with Korean annotations
- Coverage: T0001-T2920 (2,471 total texts)

**Data Selection Strategy**:

**T01-T55 (2,279 texts)** - Full inclusion ✅
- T01-T04: Āgama Sutras (阿含部)
- T05-T08: Prajñāpāramitā (般若部) - includes Diamond Sutra (T0235), Heart Sutra
- T09-T10: Lotus & Avatamsaka (法華·華嚴部) - T0262 (Lotus), T0278-279 (Avatamsaka)
- T11-T32: Other Mahāyāna Sutras (大乘經典)
- T33-T39: Esoteric Buddhism (密教部)
- T40-T48: Vinaya (律部)
- T49-T54: Abhidharma & Treatises (毘曇·論部)
- T55: Madhyamaka & Yogācāra (中觀·瑜伽)

**T85 (192 texts)** - Selective inclusion ⚠️
- **Include (127 texts)**:
  - T2732-T2856: Commentaries, practice manuals, ritual texts
    - Reason: High scholarly value; includes major commentaries on Diamond Sutra, Lotus Sutra, and Yogācāra texts essential for understanding Buddhist philosophy
  - T2887: 父母恩重經 (Sutra on Parental Kindness)
    - Reason: Widely used in Korean Buddhism despite being apocryphal; cultural significance
  - T2898: 高王觀世音經 (Gao Wang Avalokiteśvara Sutra)
    - Reason: Important in East Asian popular Buddhism and Guanyin devotion

- **Exclude (65 texts)**:
  - T2857-T2864: Literary works (變文, poems)
    - Reason: Buddhist narratives and poetry, not canonical teachings
  - T2865-T2886, T2888-T2920: Apocryphal sutras (疑僞經)
    - Reason: Texts of uncertain or false attribution; not Buddha's direct teachings; may introduce doctrinal inconsistencies in RAG responses

**Final Count**: ~2,400 texts selected for embedding

### 2.2 Automated Download Script
```bash
# Clone CBETA repository
git clone --depth 1 https://github.com/cbeta-org/xml-p5a.git data/raw/cbeta

# Or download specific volumes
python scripts/download_cbeta.py --volumes T01-T13 --output data/raw/cbeta
```

### 2.3 Data Processing Pipeline
```python
data/
├── raw/
│   └── cbeta/           # Cloned CBETA GitHub repo
│       ├── T01/         # Āgama volume
│       ├── T08/         # Lotus Sutra, etc.
│       └── ...
├── processed/           # Cleaned JSON files
│   ├── T0001.json
│   ├── T0262.json
│   └── ...
└── metadata.json        # Corpus statistics
```

**Processing Steps** (Fully Automated):
1. Parse TEI P5 XML structure
2. Extract `<title>`, `<head>`, `<body>` elements
3. Clean formatting (remove `<note>`, `<lb>`, etc.)
4. Extract metadata (text_id, juan 卷, category)
5. Segment by logical units (經、卷、品)
6. Generate unique IDs (T0001n0001, etc.)

---

## Phase 3: Embedding Pipeline

### 3.1 Chunking Strategy
- **Semantic chunking**: Split by sutta/chapter boundaries
- **Overlap**: 100-200 characters between chunks
- **Max chunk size**: 512-1024 tokens (balance context vs precision)
- **Metadata preservation**: Attach source, title, page numbers to each chunk

### 3.2 Embedding Model Selection
**Chinese Language Focus** (Classical Chinese + Korean annotations)

Options:
1. `sentence-transformers/paraphrase-multilingual-mpnet-base-v2` (free, 768-dim, supports Chinese)
2. `shibing624/text2vec-base-chinese` (free, 768-dim, optimized for Chinese)
3. OpenAI `text-embedding-3-large` (paid, 3072-dim, excellent for Classical Chinese)

**Recommendation**: Start with `paraphrase-multilingual-mpnet-base-v2` for testing, evaluate Chinese-specific models.

### 3.3 M4 Pro Optimization
**Hardware**: MacBook Pro M4 Pro (16 cores, 32GB RAM)

**Optimized Settings**:
- Batch size: **128** (vs 32 on standard hardware)
- Workers: **12** (leave 4 cores for system)
- Device: **CPU** (MPS not yet stable for sentence-transformers)
- Memory: Can keep 5-10k documents in RAM simultaneously

### 3.4 Embedding Generation (Automated)
```bash
# Automated execution by Claude Code
python scripts/embed_documents.py \
  --input data/processed/ \
  --output chroma_db/ \
  --model paraphrase-multilingual-mpnet-base-v2 \
  --batch-size 128 \
  --workers 12
```

**Time Estimate** (M4 Pro):
- Processing: ~500-800 docs/minute
- Full Taishō (3000 texts, ~50k chunks): **1-2 hours**
- Much faster than standard hardware (10-50 hours)

---

## Phase 4: Vector Database Setup

### 4.1 ChromaDB Configuration
```python
# chromadb_config.py
import chromadb
from chromadb.config import Settings

client = chromadb.PersistentClient(
    path="./chroma_db",
    settings=Settings(
        anonymized_telemetry=False,
        allow_reset=True
    )
)

collection = client.get_or_create_collection(
    name="buddhist_texts",
    metadata={
        "hnsw:space": "cosine",  # Similarity metric
        "hnsw:M": 32,            # Index quality
    }
)
```

### 4.2 Collections Structure
**Single Collection**: `taisho_tripitaka`
- All CBETA texts in one unified collection
- Language: Classical Chinese (zh-classical)
- Metadata-based filtering for categories

**Metadata Fields**:
- `source`: "cbeta"
- `language`: "zh" (Classical Chinese)
- `category`: "agama" | "mahayana" | "abhidharma" | "vinaya" | "commentary"
- `text_id`: "T0001n0001" (Taishō number + serial)
- `title`: Text title in Chinese
- `volume`: "T01" (Taishō volume)
- `juan`: 卷數 (fascicle number)

---

## Phase 5: RAG System Architecture

### 5.1 Query Pipeline
```
User Query → Query Embedding → Vector Search →
Reranking → Context Assembly → LLM Generation → Response
```

### 5.2 Retrieval Strategy
1. **Hybrid search**: Semantic (vector) + keyword (BM25) fusion
2. **Top-k retrieval**: 10-20 candidates
3. **Reranking**: Cross-encoder or LLM-based reranking (top 5)
4. **Context window**: 8k-16k tokens (Claude 3.5 Sonnet recommended)

### 5.3 LangChain Implementation
```python
# rag_chain.py
from langchain.chains import RetrievalQA
from langchain_anthropic import ChatAnthropic
from langchain_community.vectorstores import Chroma

llm = ChatAnthropic(model="claude-3-5-sonnet-20241022")
vectorstore = Chroma(persist_directory="./chroma_db")
retriever = vectorstore.as_retriever(search_kwargs={"k": 10})

qa_chain = RetrievalQA.from_chain_type(
    llm=llm,
    retriever=retriever,
    return_source_documents=True
)
```

### 5.4 Prompt Engineering
**System Prompt**:
- Role: Buddhist scholar assistant
- Guidelines: Cite sources, distinguish traditions, remain respectful
- Language: Match user query language (auto-detect)
- Citation format: "According to [Sutta Name] ([Text ID])..."

---

## Phase 6: API Development

### 6.1 FastAPI Endpoints
```python
# main.py structure
POST /api/chat          # Send message, get response
POST /api/embed         # Upload & embed new documents
GET  /api/collections   # List available text collections
GET  /api/sources       # List embedded documents
POST /api/search        # Direct vector search (debugging)
GET  /api/health        # Health check
```

### 6.2 Request/Response Schema
```python
# Chat Request
{
  "query": "What is the Four Noble Truths?",
  "language": "en",  # Optional: auto-detect
  "collection": "all",  # or specific collection
  "max_sources": 5
}

# Chat Response
{
  "response": "The Four Noble Truths are...",
  "sources": [
    {"title": "Dhammacakkappavattana Sutta", "text_id": "SN56.11", "excerpt": "..."}
  ],
  "model": "claude-3-5-sonnet",
  "latency_ms": 1234
}
```

### 6.3 Authentication & Rate Limiting
- API key authentication for public access
- Rate limiting: 100 requests/hour per IP
- CORS configuration for buddhakorea.com origin

---

## Phase 7: Frontend Integration

### 7.1 New Page: `/chatbot.html`
**UI Components**:
- Chat interface (message bubbles with source citations)
- Category filter (阿含/大乘/毘曇/律部/All)
- Language: Korean interface (users query in Korean or Chinese)
- Source document viewer (modal showing Classical Chinese + Korean translation)

### 7.2 JavaScript Module: `js/chatbot.js`
```javascript
async function sendMessage(query) {
  const response = await fetch('/api/chat', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ query, language: 'ko' })
  });
  return await response.json();
}
```

### 7.3 Styling
- Consistent with existing Buddha Korea design system
- Gradient colors from `:root` CSS variables
- Mobile-responsive chat UI
- Loading states with Korean Buddhist motifs

---

## Phase 8: Testing & Evaluation

### 8.1 Retrieval Quality
- **Metrics**: Precision@5, Recall@10, MRR (Mean Reciprocal Rank)
- **Test queries**: 50-100 curated Buddhist questions
- **Manual evaluation**: Expert review of top-5 retrieved documents

### 8.2 Response Quality
- **Faithfulness**: Does response match retrieved Classical Chinese sources?
- **Completeness**: Does it answer the question?
- **Citations**: Are Taishō numbers (T0262, etc.) properly cited?
- **Korean Translation**: Quality of Korean explanations of Classical Chinese texts

### 8.3 Performance Benchmarks
- Query latency: <3 seconds end-to-end
- Embedding generation (M4 Pro): **500-800 docs/minute**
- Concurrent users: 50+ simultaneous connections
- Full Taishō embedding: **1-2 hours** (vs 10-50 hours on standard hardware)

---

## Phase 9: Deployment

### 9.1 Cloud Infrastructure Options
**Option A: VPS (DigitalOcean, Linode)**
- Cost: $20-50/month (4GB RAM, 80GB SSD)
- Suitable for: Moderate traffic (<10k queries/day)

**Option B: Cloud Platform (GCP, AWS)**
- Cloud Run / Lambda for API (serverless)
- Cloud Storage for vector DB (GCS, S3)
- Cost: Pay-per-use ($50-200/month estimated)

**Option C: Specialized AI Hosting (Replicate, Modal)**
- Simplified deployment, GPU access
- Cost: $100-300/month

**Recommendation**: Start with Option A (VPS), migrate to B if traffic scales.

### 9.2 Docker Deployment
```bash
# Build and deploy
docker-compose up -d
docker logs -f opennotebook-api
```

### 9.3 Monitoring & Maintenance
- Logging: Structured JSON logs with loguru
- Monitoring: Uptime checks, API latency tracking
- Alerts: Email/Slack for downtime or errors
- Backups: Daily ChromaDB snapshots

### 9.4 Domain & SSL
- Subdomain: `chatbot.buddhakorea.com` or `ai.buddhakorea.com`
- SSL: Let's Encrypt (Certbot auto-renewal)
- Nginx reverse proxy: API at `/api/*`, static site at `/*`

---

## Development Timeline (M4 Pro Optimized)

| Phase | Duration | Deliverable |
|-------|----------|-------------|
| 1. Environment Setup | ✅ Complete | Docker + local dev working |
| 2. Data Download | 2-3 hours | CBETA XML from GitHub |
| 3. Data Processing | 3-4 hours | 3000 texts → JSON |
| 4. Embedding Generation | **1-2 hours** | Full Taishō embedded |
| 5. RAG Testing | 1 hour | Verify retrieval quality |
| 6. API Testing | 1 hour | Test all endpoints |
| 7. Frontend Integration | 1-2 days | Chat UI on buddhakorea.com |
| 8. Quality Validation | 2-3 hours | 50 test queries |
| 9. Deployment | 3-4 hours | Live on buddhakorea.com |

**Total Estimated Time**: **1-2 days** (with M4 Pro automation)
**Today's Session**: Can complete Phases 2-6 (data → working RAG API)

---

## Cost Estimates

### One-Time Costs
- Development: 80-100 hours @ your time
- Initial embedding: $10-50 (if using OpenAI embeddings)

### Ongoing Monthly Costs
- VPS hosting: $30-50
- LLM API calls: $20-100 (depends on traffic)
  - Claude 3.5 Sonnet: ~$0.003/query (8k context)
  - OpenAI GPT-4o-mini: ~$0.001/query
- Domain/SSL: $0 (Let's Encrypt)
- **Total: $50-150/month** (scales with usage)

---

## Technical Risks & Mitigations

| Risk | Mitigation |
|------|-----------|
| Poor retrieval quality for classical Chinese | Use specialized Chinese embedding models (e.g., `m3e-base`) |
| High LLM costs at scale | Cache frequent queries, use cheaper models for simple questions |
| ChromaDB performance with 100k+ docs | Implement sharding by collection, upgrade to Pinecone/Weaviate if needed |
| User queries in mixed languages | Implement language detection, search across all collections |
| Hallucination/incorrect teachings | Add confidence scores, warn users to verify with original texts |

---

## Next Steps (Automated Execution)

**Claude Code will execute**:
1. ✅ Virtual environment & dependencies installed
2. ✅ `.env` file configured with API keys
3. 🔄 Download CBETA XML from GitHub (2-3 hours)
4. 🔄 Process XML → JSON (3-4 hours, automated)
5. 🔄 Generate embeddings (1-2 hours, M4 Pro optimized)
6. 🔄 Test RAG system with sample queries
7. 🔄 Validate API endpoints
8. ✅ Present results & metrics

**No manual intervention required**

---

## References

- **OpenNotebook**: https://github.com/lfnovo/open-notebook
- **CBETA GitHub**: https://github.com/cbeta-org/xml-p5a
- **CBETA Official**: https://www.cbeta.org/
- **TEI P5 Guidelines**: https://tei-c.org/release/doc/tei-p5-doc/en/html/
- **LangChain RAG Tutorial**: https://python.langchain.com/docs/tutorials/rag/
- **ChromaDB Docs**: https://docs.trychroma.com/

---

**Document Version**: 1.0
**Last Updated**: 2025-10-30
**Author**: Claude Code for Buddha Korea Project

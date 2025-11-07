# Buddhist AI Chatbot - OpenNotebook Experiment

A NotebookLM-level AI chatbot for Taishō Tripiṭaka (大正新脩大藏經) using RAG (Retrieval-Augmented Generation) with CBETA XML corpus.

**Data Source**: CBETA Taishō Tripiṭaka XML from [cbeta-git/xml-p5a](https://github.com/cbeta-git/xml-p5a) (T0001-T2920, 2,471 texts)
**Selected Texts**: ~2,400 texts (T01-T55 fully + T85 selectively filtered)
**Hardware**: Optimized for MacBook Pro M4 Pro (16 cores, 32GB RAM)
**Embedding Model**: BAAI/bge-m3 (75-80% accuracy for Classical Chinese)
**Chunk Size**: 1024 tokens (72-75% retrieval accuracy)

## Quick Start

### Option 1: Docker (Recommended)

```bash
# 1. Copy environment template
cp .env.example .env

# 2. Edit .env and add your API keys
nano .env  # or use your preferred editor

# 3. Build and run with Docker Compose
docker-compose up --build

# API will be available at http://localhost:8000
```

### Option 2: Local Development

```bash
# 1. Create virtual environment
python3.11 -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate

# 2. Install dependencies
pip install -r requirements.txt

# 3. Set up environment
cp .env.example .env
# Edit .env with your API keys

# 4. Run the API server
uvicorn main:app --reload --port 8000
```

## Project Structure

```
opennotebook/
├── README.md                           # This file
├── OpenNotebook_development_plan.md    # Comprehensive development guide
├── requirements.txt                    # Python dependencies
├── Dockerfile                          # Docker configuration
├── docker-compose.yml                  # Multi-container setup
├── .env.example                        # Environment variables template
├── main.py                             # FastAPI application (to be created)
├── data/
│   ├── raw/                           # Original CBETA & Pali texts
│   └── processed/                     # Cleaned & segmented texts
├── scripts/
│   ├── embed_documents.py             # Embedding generation script
│   └── data_preprocessing.py          # Text cleaning & segmentation
├── chroma_db/                         # Vector database storage
└── models/                            # Downloaded embedding models
```

## Next Steps

1. **Read the development plan**: `OpenNotebook_development_plan.md` covers everything from data preparation to deployment

2. **Download CBETA XML**:
   ```bash
   # Automated download script (2-3 hours for full corpus)
   python scripts/download_cbeta.py --full --output data/raw/cbeta

   # Or download specific volumes for testing
   python scripts/download_cbeta.py --volumes T01 T08 --output data/raw/cbeta
   ```

3. **Process XML to JSON** (applies T85 filtering automatically):
   ```bash
   # Process all CBETA XML files
   python scripts/preprocess_data.py \
     --input data/raw/cbeta/ \
     --output data/processed/chinese/ \
     --format xml

   # This will:
   # - Include ALL T01-T55 texts (2,279 texts)
   # - Filter T85 to exclude apocryphal sutras (keep ~127 valuable texts)
   # - Extract Classical Chinese text and metadata
   ```

4. **Generate embeddings** (1-2 hours on M4 Pro):
   ```bash
   # Embed all processed texts using BAAI/bge-m3
   python scripts/embed_documents.py \
     --input data/processed/ \
     --collection buddhist_texts \
     --batch-size 128 \
     --workers 12

   # M4 Pro optimization: 500-800 docs/minute
   ```

5. **Start the API server**:
   ```bash
   uvicorn main:app --reload --port 8000
   # Or: python main.py

   # Test: http://localhost:8000/docs (FastAPI interactive docs)
   ```

6. **Test with sample queries**:
   ```bash
   curl -X POST "http://localhost:8000/api/chat" \
     -H "Content-Type: application/json" \
     -d '{"query": "사성제란 무엇인가?", "language": "ko", "max_sources": 5}'
   ```

## API Endpoints (Planned)

- `POST /api/chat` - Send query, receive AI response with citations
- `GET /api/collections` - List available text collections
- `GET /api/health` - Health check
- `POST /api/embed` - Upload and embed new documents (admin)

## Requirements

- **Python**: 3.11+
- **Hardware**: MacBook Pro M4 Pro (16 cores, 32GB RAM)
- **RAM**: 32GB (can process full Taishō in 1-2 hours)
- **Disk**: 30GB (15GB CBETA XML + 10GB embeddings + 5GB processed)
- **API Keys**: Anthropic (Claude recommended for Classical Chinese)

## Technology Stack

- **Web Framework**: FastAPI
- **LLM**: Claude 3.5 Sonnet (excellent for Classical Chinese translation)
- **Vector DB**: ChromaDB with HNSW indexing
- **RAG Framework**: LangChain
- **Embeddings**: BAAI/bge-m3 (1024-dim, optimized for Classical Chinese)
- **XML Parser**: lxml (TEI P5 format)
- **Document Processing**: RecursiveCharacterTextSplitter with Chinese-specific separators

## Data Selection Strategy

### T01-T55 (Full Inclusion - 2,279 texts)
- **T01-T04**: Āgama Sutras (阿含部)
- **T05-T08**: Prajñāpāramitā (般若部) - includes Diamond Sutra (T0235), Heart Sutra
- **T09-T10**: Lotus & Avatamsaka (法華·華嚴部) - T0262 (Lotus), T0278-279 (Avatamsaka)
- **T11-T32**: Other Mahāyāna Sutras
- **T33-T39**: Esoteric Buddhism (密教部)
- **T40-T48**: Vinaya (律部)
- **T49-T54**: Abhidharma & Treatises (毘曇·論部)
- **T55**: Madhyamaka & Yogācāra (中觀·瑜伽)

### T85 (Selective Inclusion - ~127 texts)
**Included**:
- T2732-T2856: Commentaries, practice manuals, ritual texts (high scholarly value)
- T2887: 父母恩重經 (Sutra on Parental Kindness) - cultural significance in Korean Buddhism
- T2898: 高王觀世音經 (Gao Wang Avalokiteśvara Sutra) - important in popular devotion

**Excluded**:
- T2857-T2864: Literary works (變文, poems) - Buddhist narratives, not canonical teachings
- T2865-T2886, T2888-T2920: Apocryphal sutras (疑僞經) - uncertain attribution, may introduce doctrinal inconsistencies

**Final Count**: ~2,400 texts selected for embedding

## Cost Estimates

- **Development**: Free (local execution on M4 Pro)
- **Embedding**: Free (local sentence-transformers)
- **LLM API calls**: ~$0.003 per query (Claude 3.5 Sonnet)
- **Hosting**: $30-50/month (VPS)
- **Expected monthly cost**: $50-150 at moderate traffic (1000-5000 queries/month)

## Contributing

This is an experimental setup for the Buddha Korea project. For questions or improvements, contact the project maintainer.

## Performance (M4 Pro)

- **Embedding Speed**: 500-800 documents/minute
- **Full Taishō Processing**: 1-2 hours (vs 10-50 hours on standard hardware)
- **Query Latency**: <3 seconds end-to-end
- **Memory Usage**: ~8-12GB during embedding

## License

This codebase follows the Buddha Korea project license. CBETA Taishō Tripiṭaka texts are used with permission and follow CBETA licensing.

---

**Status**: Automated setup ready for execution
**Hardware**: Optimized for MacBook Pro M4 Pro
**Last Updated**: 2025-10-30

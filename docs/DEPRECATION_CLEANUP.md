# Deprecation Cleanup Notes

This document tracks SDK deprecation cleanup work that affects production
startup logs and future deployment safety.

## Current Status

### Completed: LangChain Chroma Wrapper

The deprecated `langchain_community.vectorstores.Chroma` wrapper has been
removed from the runtime RAG path.

- Runtime replacement: `backend/app/chroma_compat.py`
- Main app usage: `backend/app/main.py`
- Embedding script usage: `backend/scripts/embed_documents.py`

The local adapter wraps direct `chromadb` calls and preserves the subset of the
LangChain vector store interface the app uses:

- `add_texts`
- `add_documents`
- `similarity_search`
- `as_retriever`
- `from_texts`

Reason: adding `langchain-chroma` directly conflicted with the current pinned
`langchain==0.3.7` and `chromadb==1.3.0` dependency set.

### Completed: Google GenAI Runtime Migration

The deprecated `google.generativeai` package has been removed from runtime code.

- Pali Studio Gemini client now uses `google-genai`.
- Gemini query embeddings now use `google-genai` instead of
  `vertexai.language_models.TextEmbeddingModel`.
- Maintenance scripts used for normalization/style conversion were updated to
  use `google-genai` where practical.
- `requirements.txt` now declares `google-genai>=1.2.0`.

Runtime files changed:

- `backend/pali/services/gemini_client.py`
- `backend/pali/config.py`
- `backend/app/gemini_query_embedder.py`

Script files changed:

- `backend/scripts/run_normalization.py`
- `backend/scripts/convert_detailed_style.py`

### Completed: Low-Risk Warning Hygiene

Non-behavioral deprecation cleanup has also been applied:

- Pydantic settings and response schemas now use Pydantic v2 `model_config`.
- Pali database setup now imports `declarative_base` from `sqlalchemy.orm`.
- Backend pytest config now sets `asyncio_default_fixture_loop_scope`.

## Verification Commands

Compile changed files:

```bash
python3 -m compileall \
  backend/app/main.py \
  backend/pali/services/gemini_client.py \
  backend/pali/config.py \
  backend/pali/schemas/literature.py \
  backend/pali/db/database.py \
  backend/app/gemini_query_embedder.py \
  backend/scripts/run_normalization.py \
  backend/scripts/convert_detailed_style.py
```

Run backend admin tests in the dev container:

```bash
docker exec -w /app/backend -e PYTHONPATH=/app/backend:/app buddhakorea-dev-backend \
  pytest tests -q
```

Smoke-test Google GenAI imports and adapters in the dev container:

```bash
docker exec -e PYTHONPATH=/app/backend:/app buddhakorea-dev-backend \
  python -W default -c "from pali.services.gemini_client import GeminiClient; GeminiClient(); from app.gemini_query_embedder import GeminiQueryEmbedder; GeminiQueryEmbedder(project_id='dummy-project'); print('ok')"
```

## Deployment Notes

Production runs in `/opt/buddha-korea` and the backend image copies:

- `backend/app/` to `/app/app/`
- `backend/pali/` to `/app/pali/`

For pure Python runtime changes where dependencies are already present in the
image, a safe hot patch can be used:

```bash
docker cp backend/pali/services/gemini_client.py buddhakorea-backend:/app/pali/services/gemini_client.py
docker cp backend/pali/config.py buddhakorea-backend:/app/pali/config.py
docker cp backend/app/gemini_query_embedder.py buddhakorea-backend:/app/app/gemini_query_embedder.py
docker restart buddhakorea-backend
curl -fsS https://buddhakorea.com/api/health
```

Use a full image rebuild when dependency versions change or when the current
production image does not already include `google-genai`.

### Torch Dependency Pin

`requirements.txt` pins CPU-only Torch:

```txt
--extra-index-url https://download.pytorch.org/whl/cpu
torch==2.5.1+cpu
```

Do not loosen this back to `torch>=2.0.0` for production. On Hetzner, an
unbounded Torch install can resolve to CUDA wheels, causing very large images,
slow exports, and disk-pressure failures during deploy.

## Remaining Cleanup

`backend/app/main.py` still uses `langchain_google_vertexai.ChatVertexAI` for the
main RAG LLM path. Replacing it should be handled as a separate migration
because it affects answer generation behavior, credentials, streaming semantics,
and LangChain integration.

Before replacing this path, run the RAG golden-query checks documented in
`docs/RAG_REGRESSION_TESTING.md`. The current safety harness lives in:

- `backend/app/rag_regression.py`
- `backend/app/rag_golden_queries.json`
- `scripts/rag_regression_check.py`

A production pre-migration baseline was captured on 2026-04-15 at commit
`92088fb`; see `docs/RAG_REGRESSION_TESTING.md` for the recorded latencies,
source counts, and pass/fail results.

### Completed: LLM Factory Preparation

`backend/app/main.py` now routes chat model creation through `create_chat_llm`.
This is intentionally behavior-preserving: it keeps the current
`ChatVertexAI`/Claude/OpenAI provider routing, model names, token limits,
temperature, and streaming settings, but removes duplicated initialization
branches. This reduces the risk of a future `ChatVertexAI` replacement because
the migration target is now one factory function instead of several scattered
call sites.

### Completed: LangChain Chain Invocation Cleanup

`backend/app/main.py` now calls RetrievalQA chains through
`invoke_retrieval_qa`, which uses `.invoke({"query": ...})` instead of the
deprecated `chain({"query": ...})` shorthand. LangChain 0.3.7 can still emit the
same `Chain.__call__` warning from inside `RetrievalQA.invoke`, so the helper
also suppresses that exact internal warning. This is intentionally scoped and
should be removed when `RetrievalQA` is replaced with a newer LCEL-style
retrieval chain.

Some non-runtime source explorer/evaluation scripts still use direct Vertex AI
SDK imports:

- `backend/source_explorer/*.py`
- `backend/evaluation/golden_set_builder.py`

Those scripts are not part of the FastAPI startup path, so they should not
produce production backend startup warnings unless executed manually.

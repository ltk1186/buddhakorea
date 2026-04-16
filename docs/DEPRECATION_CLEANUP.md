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

### Completed: LLM Factory Preparation

`backend/app/main.py` no longer imports provider SDKs directly for the runtime
chat path. Chat model creation now flows through a provider adapter layer in:

- `backend/app/llm/factory.py`
- `backend/app/llm/gemini_vertex.py`
- `backend/app/llm/anthropic.py`
- `backend/app/llm/openai.py`

This is intentionally behavior-preserving:

- Gemini still routes to `ChatVertexAI`
- Claude still routes to `ChatAnthropic`
- OpenAI fallback still routes to `ChatOpenAI`
- API-key gating, token limits, temperatures, and streaming kwargs are preserved

This reduces migration risk because a future Gemini adapter replacement no
longer requires edits inside the FastAPI request/runtime module.

### Completed: LangChain LCEL Retrieval Chain

`backend/app/main.py` no longer uses the deprecated `RetrievalQA` chain for the
runtime chat path. The RAG chain helpers now live in
`backend/app/rag/chains.py` and build the runtime path with LangChain Expression
Language helpers:

- `create_stuff_documents_chain`
- `create_retrieval_chain`

The local wrapper functions preserve the public API response contract:

- `create_rag_chain` constructs the LCEL retrieval chain.
- `invoke_rag_chain` invokes the chain with both `input` and `question` keys.
- LCEL output (`answer`, `context`) is mapped back to the existing response shape
  (`result`, `source_documents`) used by the chat endpoint, token estimation,
  logging, and citation formatting.

Because `RetrievalQA` has been removed from the runtime path, the previous
`Chain.__call__` warning suppression was also removed.

### Completed: Code-Owned Prompt Registry

Runtime chat prompts have been moved out of `backend/app/main.py` and into
`backend/app/rag/prompts.py`.

The registry currently covers:

- normal chat
- detailed chat
- sutra-filtered chat
- detailed sutra-filtered chat
- tradition-filtered chat
- detailed tradition-filtered chat
- streaming normal chat
- streaming detailed chat

Prompt entries have stable ids and versions such as `normal_v1` and
`sutra_filter_detailed_v1`. They are still code-owned and are not editable from
the admin UI. This is intentional for the current phase: prompt changes should
remain reviewable, testable, rollbackable code changes until query tracing,
admin audit logging, and prompt change governance are stronger.

The tradition-filtered prompt path now uses the registry renderer so `tradition`,
`context`, and `question` are all formatted explicitly.

References checked before this migration:

- LangChain Retrieval docs: https://docs.langchain.com/oss/python/langchain/retrieval
- LangChain `create_retrieval_chain` / `create_stuff_documents_chain` APIs as
  installed in the pinned `langchain==0.3.7` dev container.

### Deployment Note: Backend Rebuild Required

Backend source files are copied into the production Docker image. A plain
`docker compose up -d --force-recreate` does not update `/app/app/main.py`
inside the running backend image. The Hetzner GitHub Actions workflow now
rebuilds the image when `backend/**`, `requirements.txt`, `pyproject.toml`,
`Dockerfile`, or `frontend/pali-studio/**` changes.

### Completed: LLM Factory Unit Coverage

`backend/tests/test_llm_factory.py` now locks down the behavior-preserving LLM
provider adapter layer before any provider migration:

- Gemini routes to `ChatVertexAI`.
- Claude and OpenAI require their API keys before construction.
- Streaming arguments are preserved for the fast model.
- `main.py` delegates to the provider factory instead of importing SDKs
  directly.

### Completed: Provider Metadata in Query Trace

Structured query traces now include both the requested model name and the
resolved provider route, for example:

- `model = gemini-2.5-pro`
- `provider = gemini_vertex`

This keeps future provider migration analysis grounded in real production logs.

### Completed: Phase 5 Google Provider Migration Spike

An opt-in `langchain-google-genai` adapter has been added without changing the
production default route.

- Added dependency pin: `langchain-google-genai==2.0.11`
- Added runtime adapter: `backend/app/llm/gemini_google_genai.py`
- Added config knob: `GEMINI_PROVIDER=vertex|google_genai`
- Default remains `vertex`

Why this shape:

- `langchain-google-genai` 2.0.11 is the newest line that fits the current
  `langchain==0.3.7` / `langchain-core==0.3.x` stack without forcing a larger
  LangChain upgrade.
- The compatible 2.0.x line still centers on Google API key semantics and does
  not offer a clean Vertex-project/location constructor matching the current
  `ChatVertexAI` path.
- Buddha Korea production currently runs on Vertex/service-account credentials,
  so switching the default route now would change both the wrapper and the
  backend API surface at once.

Result:

- Production keeps using `ChatVertexAI`
- The migration path is now testable in code
- A future switch can compare `gemini_vertex` vs `gemini_google_genai` with the
  golden-query harness before any default change

## Remaining Cleanup

The remaining provider work is no longer about architecture isolation. It is a
runtime migration decision:

- keep `backend/app/llm/gemini_vertex.py` on `ChatVertexAI`, or
- replace it with a `ChatGoogleGenerativeAI`-style adapter after comparative
  regression testing

That decision should still be handled as a separate migration because it affects
answer generation behavior, credentials, streaming semantics, usage metadata,
and LangChain integration.

Before replacing this path, run the RAG golden-query checks documented in
`docs/RAG_REGRESSION_TESTING.md`. The current safety harness lives in:

- `backend/app/rag_regression.py`
- `backend/app/rag_golden_queries.json`
- `scripts/rag_regression_check.py`

A production pre-migration baseline was captured on 2026-04-15 at commit
`92088fb`; see `docs/RAG_REGRESSION_TESTING.md` for the recorded latencies,
source counts, and pass/fail results.

### Remaining: Google Provider Adapter Review

The Gemini runtime path still uses `langchain_google_vertexai.ChatVertexAI`.
The latest LangChain Google GenAI documentation now documents
`langchain_google_genai.ChatGoogleGenerativeAI` for Gemini and Vertex AI usage.
That migration is still intentionally left as a separate default-switch step
because it changes credential semantics, model output metadata, and potentially
streaming behavior even though the experimental adapter now exists in-tree.

Reference:

- LangChain Google Generative AI integration:
  https://docs.langchain.com/oss/python/integrations/chat/google_generative_ai

Some non-runtime source explorer/evaluation scripts still use direct Vertex AI
SDK imports:

- `backend/source_explorer/*.py`
- `backend/evaluation/golden_set_builder.py`

Those scripts are not part of the FastAPI startup path, so they should not
produce production backend startup warnings unless executed manually.

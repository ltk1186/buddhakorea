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

## Verification Commands

Compile changed files:

```bash
python3 -m compileall \
  backend/pali/services/gemini_client.py \
  backend/pali/config.py \
  backend/app/gemini_query_embedder.py \
  backend/scripts/run_normalization.py \
  backend/scripts/convert_detailed_style.py
```

Run backend admin tests in the dev container:

```bash
docker exec -e PYTHONPATH=/app/backend:/app buddhakorea-dev-backend \
  pytest /app/backend/tests -q
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

Some non-runtime source explorer/evaluation scripts still use direct Vertex AI
SDK imports:

- `backend/source_explorer/*.py`
- `backend/evaluation/golden_set_builder.py`

Those scripts are not part of the FastAPI startup path, so they should not
produce production backend startup warnings unless executed manually.

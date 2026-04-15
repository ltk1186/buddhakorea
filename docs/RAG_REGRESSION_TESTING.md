# RAG Regression Testing

This document defines the safe verification layer to run before changing the
main RAG answer-generation path, especially before replacing
`langchain_google_vertexai.ChatVertexAI`.

## Purpose

The golden-query checks are not exact-answer tests. LLM wording changes between
runs, so the test contract intentionally checks stable operational signals:

- `/api/health` is reachable.
- `/api/chat` returns the expected response schema.
- Responses are non-empty and long enough to be useful.
- Citations are present.
- Source objects include `title`, `text_id`, and `excerpt`.
- Sutra-filtered queries keep expected source IDs when sources are returned.
- Response latency stays under a generous smoke-test ceiling.
- Markdown headers are not emitted where the product prompt forbids them.

## Golden Query File

Default cases live in:

```bash
backend/app/rag_golden_queries.json
```

Each case includes:

- `id`: stable case identifier
- `description`: what behavior the case protects
- `request`: payload sent to `/api/chat`
- `expect`: coarse assertions applied to the JSON response

Keep this set small. These checks call the live LLM when executed, so they cost
money and consume user quota.

## Local Usage

Health only, no LLM call:

```bash
python3 scripts/rag_regression_check.py --base-url http://localhost:8000 --health-only
```

One anonymous chat case:

```bash
python3 scripts/rag_regression_check.py \
  --base-url http://localhost:8000 \
  --max-cases 1
```

If the local development container has ChromaDB connected but the QA chain is
not initialized, use this only to verify script plumbing:

```bash
python3 scripts/rag_regression_check.py \
  --base-url http://localhost:8000 \
  --max-cases 1 \
  --allow-rag-unavailable
```

Do not use `--allow-rag-unavailable` for production migration checks.

All cases with admin login, using environment variables:

```bash
ADMIN_EMAIL="..." ADMIN_PASSWORD="..." \
python3 scripts/rag_regression_check.py \
  --base-url http://localhost:8000 \
  --login
```

## Production Usage

Run health-only checks after every deployment:

```bash
python3 scripts/rag_regression_check.py \
  --base-url https://buddhakorea.com \
  --health-only
```

Run one full case when validating risky RAG changes:

```bash
ADMIN_EMAIL="..." ADMIN_PASSWORD="..." \
python3 scripts/rag_regression_check.py \
  --base-url https://buddhakorea.com \
  --login \
  --max-cases 1
```

Run the full set only before/after answer-generation migrations:

```bash
ADMIN_EMAIL="..." ADMIN_PASSWORD="..." \
python3 scripts/rag_regression_check.py \
  --base-url https://buddhakorea.com \
  --login
```

## Required Before ChatVertexAI Migration

Before changing the LLM adapter or RetrievalQA path:

1. Run the full golden set against the current production behavior.
2. Save the output in the deployment notes or PR summary.
3. Apply the migration behind a rollbackable commit.
4. Run the same full golden set locally.
5. Deploy.
6. Run health-only first, then one full production case.
7. Run the full production set if the one-case smoke check is clean.

## Rollback Rule

If any case fails after an LLM/RAG migration and the failure is not an expected
prompt-quality change, rollback the migration commit first. Tune the golden case
only after confirming the production behavior is acceptable.

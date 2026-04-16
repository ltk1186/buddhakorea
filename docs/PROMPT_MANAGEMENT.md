# Prompt Management

Buddha Korea prompts are currently code-owned runtime artifacts. They are not
admin-editable yet because prompt changes directly affect answer quality,
citations, token usage, and user trust.

## Runtime Location

Prompt definitions live in:

```text
backend/app/rag/prompts.py
```

The FastAPI chat runtime imports prompt ids from the registry and calls
`build_prompt(prompt_id, **template_vars)` before constructing the LCEL RAG
chain.

## Current Prompt IDs

| Prompt ID | Purpose |
| --- | --- |
| `normal_v1` | Default cross-corpus chat answer |
| `detailed_v1` | Detailed cross-corpus answer |
| `sutra_filter_v1` | Single-sutra constrained answer |
| `sutra_filter_detailed_v1` | Detailed single-sutra constrained answer |
| `tradition_filter_v1` | Tradition-constrained answer |
| `tradition_filter_detailed_v1` | Detailed tradition-constrained answer |
| `streaming_normal_v1` | Streaming endpoint default answer |
| `streaming_detailed_v1` | Streaming endpoint detailed answer |

## Change Policy

Prompt changes should be treated like production behavior changes.

Before changing a prompt:

1. Run the backend prompt tests.
2. Run the RAG golden-query set against the current baseline.
3. Make the prompt change in a small rollbackable commit.
4. Run backend tests and admin E2E.
5. Deploy.
6. Run production health and at least one RAG smoke case.
7. Run the full production golden set if the one-case smoke is clean.

Recommended local test command:

```bash
docker exec -w /app/backend -e PYTHONPATH=/app/backend:/app buddhakorea-dev-backend \
  pytest tests/test_rag_prompts.py tests/test_rag_chains.py -q
```

## Commercial Roadmap

The next maturity step is not admin-editable prompts. The safer sequence is:

1. Store `prompt_id` and `prompt_version` in query traces.
2. Show prompt metadata read-only in the admin query detail view.
3. Add prompt diff history and audit logging.
4. Add approval/rollback controls for prompt changes.
5. Only then consider limited admin-editable prompt configuration.

This keeps answer-quality changes visible, reviewable, and reversible as the
platform grows commercially.

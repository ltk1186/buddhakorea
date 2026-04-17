# Production Status

Last updated: 2026-04-16

This file is the shortest current-state snapshot for Buddha Korea production.

## Current Runtime

- Domain: `https://buddhakorea.com`
- Host: Hetzner VM `157.180.72.0`
- Repo path: `/opt/buddha-korea`
- Reverse proxy: `nginx`
- App: FastAPI backend in Docker
- Data services: PostgreSQL, Redis, ChromaDB

## Current Admin Scope

- Dashboard
- Usage & cost view
- Reliability view
- User support controls
- Query monitor
- Query investigation detail
- Query review workflow
- Read-only data explorer
- Audit logs

Admin entrypoint:

- `https://buddhakorea.com/admin/`

## Current RAG Runtime

- LangChain LCEL retrieval chain
- Prompt registry with stable ids/versions
- Query trace capture
- Provider adapter layer
- Default provider route for Gemini: `gemini_vertex`
- Experimental provider route available: `gemini_google_genai`

## Production Caveats

- File-based usage metrics are not currently available in production:
  - `usage_log_available = false`
  - latency/cache/cost reliability metrics are therefore shown as unavailable
- DB-based quality metrics are available:
  - answers in last 24h
  - zero-source rate
  - average sources per answer
- Admin assets require cache-busting query strings on CSS/JS updates because Cloudflare caches aggressively.

## Migration Status

Canonical migration path is now:

```bash
./scripts/migrate.sh <alembic args>
```

Examples:

```bash
./scripts/migrate.sh heads
./scripts/migrate.sh current
./scripts/migrate.sh upgrade head
./scripts/migrate.sh stamp 009
```

See [MIGRATIONS_AND_SCHEMA.md](./MIGRATIONS_AND_SCHEMA.md) for the full runbook.

## Canonical Docs

- [PRODUCTION_RUNBOOK.md](./PRODUCTION_RUNBOOK.md)
- [MIGRATIONS_AND_SCHEMA.md](./MIGRATIONS_AND_SCHEMA.md)
- [OBSERVABILITY_STATUS.md](./OBSERVABILITY_STATUS.md)
- [DEPLOYMENT_QUICKSTART.md](./DEPLOYMENT_QUICKSTART.md)

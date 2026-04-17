# Migrations and Schema

Last updated: 2026-04-16

This is the canonical database migration document for Buddha Korea production.

## Goal

Schema changes must run through a single, repeatable path instead of ad hoc SQL
or installing tooling into running containers.

Canonical runner:

```bash
./scripts/migrate.sh <alembic args>
```

The script uses the `migrate` service defined in
`config/docker-compose.yml` and the dedicated image in `Dockerfile.migrate`.

## Why This Exists

Previous production work exposed three gaps:

1. `alembic upgrade head` was documented, but the runtime backend image was not
   a reliable migration environment.
2. Production had no `alembic_version` table.
3. One schema change (`chat_messages.trace_json`) had to be applied manually.

This document formalizes the path going forward.

## Migration Runner

Files:

- `Dockerfile.migrate`
- `config/docker-compose.yml` (`migrate` service, `tools` profile)
- `scripts/migrate.sh`

Runner properties:

- manual only
- not part of normal app startup
- uses the same `.env` database target as production
- keeps migration concerns separate from runtime app startup
- PostgreSQL runtime startup must not create new tables implicitly; schema changes go through Alembic only

## Common Commands

Show heads:

```bash
./scripts/migrate.sh heads
```

Show history:

```bash
./scripts/migrate.sh history
```

Show current revision:

```bash
./scripts/migrate.sh current
```

Upgrade:

```bash
./scripts/migrate.sh upgrade head
```

Stamp without applying DDL:

```bash
./scripts/migrate.sh stamp 009
```

## First-Time Production Normalization

Use this only when production schema is already aligned with the latest Alembic
revision but `alembic_version` is missing.

Checklist:

1. Inspect the current schema directly in PostgreSQL.
2. Confirm that the expected latest columns/tables already exist.
3. Stamp the DB to the matching revision.
4. Verify `./scripts/migrate.sh current` returns that revision.

For the current admin/query-trace rollout, the expected baseline revision is:

- `009`

Do not run `upgrade head` as the first normalization step against an old DB that
already contains the tables, because revision `001` is a baseline create step.

## Verification Before Stamp

Minimum checks:

- `users.role`
- `users.is_active`
- `users.daily_chat_limit`
- `chat_sessions.summary`
- `chat_sessions.is_archived`
- `chat_messages.sources_json`
- `chat_messages.tokens_used`
- `chat_messages.latency_ms`
- `chat_messages.trace_json`
- `social_accounts`
- `user_usage`
- `anonymous_usage`
- `admin_audit_logs`

If those are already present, stamping to `009` is the correct normalization.

## After Every Migration

1. Run:

```bash
./scripts/migrate.sh current
```

2. Verify API health:

```bash
curl https://buddhakorea.com/api/health
```

3. Verify core admin/API path affected by the migration.

4. Run one production RAG smoke case:

```bash
ADMIN_EMAIL="..." ADMIN_PASSWORD="..." \
python3 scripts/rag_regression_check.py \
  --base-url https://buddhakorea.com \
  --login \
  --max-cases 1
```

## Rollback

Preferred rollback order:

1. Revert the application commit if needed.
2. Only downgrade schema if the migration itself introduced an incompatible DB
   state.

Example:

```bash
./scripts/migrate.sh downgrade -1
```

Use schema downgrade sparingly. Nullable additive columns are often safer to
leave in place during an application rollback.

## Known Limitation

The migration runner is now formalized, but production log-based observability is
still not fully normalized. See [OBSERVABILITY_STATUS.md](./OBSERVABILITY_STATUS.md).

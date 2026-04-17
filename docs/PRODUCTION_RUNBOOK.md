# Production Runbook

Last updated: 2026-04-16

This is the canonical operational runbook for Buddha Korea production.

## Canonical Environment

- Host: Hetzner VM `157.180.72.0`
- Repo path: `/opt/buddha-korea`
- Domain: `https://buddhakorea.com`
- Reverse proxy: `nginx`
- App stack: FastAPI, PostgreSQL, Redis, ChromaDB, Docker Compose

## Normal Deploy Path

Primary path:

1. Push to `main`
2. Let `.github/workflows/deploy-hetzner.yml` deploy
3. Run post-deploy verification

Auto-deploy triggers on changes to:

- `backend/**`
- `config/**`
- `frontend/**`
- `scripts/**`
- `Dockerfile`
- `Dockerfile.migrate`
- `requirements.txt`
- `pyproject.toml`
- `.github/workflows/deploy-hetzner.yml`

## Manual Deploy Path

Use this when GitHub Actions is unavailable or when supervised recovery is
needed.

```bash
ssh root@157.180.72.0
cd /opt/buddha-korea
git pull origin main
docker compose -f config/docker-compose.yml up -d --build
```

Use `--build` whenever backend image inputs changed. `--force-recreate` is only
for cases where you are certain no image rebuild is required.

## Migration Path

Canonical migration path:

```bash
./scripts/migrate.sh <alembic args>
```

Examples:

```bash
./scripts/migrate.sh heads
./scripts/migrate.sh current
./scripts/migrate.sh upgrade head
```

If production schema is already aligned but `alembic_version` is missing, follow
[MIGRATIONS_AND_SCHEMA.md](./MIGRATIONS_AND_SCHEMA.md) and stamp the matching
revision instead of blindly upgrading.

Do not rely on app startup to create PostgreSQL tables. Runtime startup should
not substitute for Alembic.

## Post-Deploy Verification

Run these checks after every production deploy.

### 1. Container status

```bash
ssh root@157.180.72.0
cd /opt/buddha-korea
docker compose -f config/docker-compose.yml ps
```

Expected: `nginx`, `backend`, `postgres`, and `redis` are running.

### 2. Public health check

```bash
curl -s https://buddhakorea.com/api/health
```

Expected:

```json
{"status":"healthy"}
```

### 3. Backend logs

```bash
docker logs buddhakorea-backend --tail 100 2>&1
```

For RAG/runtime changes, also check:

```bash
docker logs --timestamps buddhakorea-backend --since 5m 2>&1 | \
  grep -Ei 'RetrievalQA|Chain\.__call__|LangChainDeprecationWarning|Traceback|ERROR'
```

### 4. Admin asset freshness

When `frontend/admin/*.css` or `frontend/admin/*.js` changes:

- confirm `frontend/admin/index.html` includes a bumped `?v=...` query string
- reload `/admin/`
- if stale assets persist, recreate nginx and purge Cloudflare cache

### 5. Admin verification

Check:

- `https://buddhakorea.com/admin/`
- admin login works
- `/api/admin/summary` returns `200`
- `/api/admin/observability` returns `200`

If the deployment touched admin query investigation detail, also verify:

- `/api/admin/queries/{message_id}` on a fresh traced message

### 6. Production RAG smoke

```bash
ADMIN_EMAIL="..." ADMIN_PASSWORD="..." \
python3 scripts/rag_regression_check.py \
  --base-url https://buddhakorea.com \
  --login \
  --max-cases 1
```

Expected:

- login succeeds
- one case passes
- answer returns sources

## Rollback

Preferred rollback order:

1. Revert the offending application commit on `main`
2. Redeploy
3. Downgrade schema only if the migration itself caused an incompatible state

Typical application rollback:

```bash
git revert <bad_commit>
git push origin main
```

Schema downgrade, only if necessary:

```bash
./scripts/migrate.sh downgrade -1
```

Additive nullable columns are often safer to leave in place during an app
rollback.

## Common Failure Patterns

### Health endpoint not returning `200`

- inspect `docker compose ps`
- inspect `docker logs buddhakorea-backend`
- inspect `docker logs buddhakorea-nginx`

### Admin UI looks old after deploy

- check versioned CSS/JS query strings in `frontend/admin/index.html`
- recreate nginx
- purge Cloudflare cache if still stale

### Migration docs and server state disagree

- inspect PostgreSQL schema directly
- run `./scripts/migrate.sh current`
- do not guess; stamp only after schema verification

### Reliability panel shows unavailable metrics

- `usage_log_available = false`여도 latency/slow/cost/cache cards는 채워져 있어야 한다.
- 이 값은 local usage-log analytics 부재로 해석한다.
- see [OBSERVABILITY_STATUS.md](./OBSERVABILITY_STATUS.md)

## Related Docs

- [DEPLOYMENT_QUICKSTART.md](./DEPLOYMENT_QUICKSTART.md)
- [MIGRATIONS_AND_SCHEMA.md](./MIGRATIONS_AND_SCHEMA.md)
- [PRODUCTION_STATUS.md](./PRODUCTION_STATUS.md)
- [OBSERVABILITY_STATUS.md](./OBSERVABILITY_STATUS.md)

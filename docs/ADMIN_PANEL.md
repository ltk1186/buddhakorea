# Buddha Korea Admin Panel

This document describes the MVP admin/backoffice implementation for Buddha Korea, including endpoints, data sources, and operational usage.

## Scope (MVP)
The admin panel focuses on:
- Operational visibility (health, usage, cost)
- Reliability visibility (latency, cache rate, zero-source answers, rate-limit pressure)
- User support (quota + status)
- Query monitoring (PII-masked)
- Query investigation detail (prompt/retrieval/provider trace)
- Session timeline investigation
- Query review workflow
- Read-only data explorer
- Audit logging of admin actions

It does not include corpus editing, re-embedding triggers, or advanced configuration controls yet.

## Access & Roles
Admin endpoints require authenticated users with an admin role. Roles are stored in `users.role`.

Roles recognized:
- `admin` (super admin)
- `ops`
- `support`
- `analyst`
- `curator` (not used in MVP)

Role gating (MVP):
- Read: `admin`, `ops`, `support`, `analyst`
- User edits: `admin`, `ops`, `support`
- Audit logs: `admin`, `ops`

Currently, role assignment is manual (database update).

### Password-Based Admin Login (Optional)
To enable admin login without OAuth, set the following environment variables:

```
ADMIN_EMAIL=admin@yourdomain.com
ADMIN_PASSWORD=your-strong-password
```

Alternatively, store a SHA-256 hash:
```
ADMIN_PASSWORD_HASH=<sha256-hex>
```

Password login endpoint:
- `POST /api/admin/login`

This endpoint issues the same cookies as OAuth (`access_token`, `refresh_token`).

## UI Entry Point
- Production: `https://buddhakorea.com/admin/`
- Static file: `frontend/admin/index.html`

The admin UI calls `/api/admin/*` endpoints with cookie-based auth (OAuth login required).

## Backend Endpoints (MVP)
All endpoints are under `/api/admin` and require admin roles.

### GET /api/admin/me
Returns the current admin user and role.

### GET /api/admin/summary
Operational summary:
- user counts (total/active/suspended)
- today’s usage (logged-in + anonymous)
- tokens used today (logged-in)
- messages in last 24h
- 7-day usage stats (from usage logs)

### GET /api/admin/users
List users with optional filters:
- `search` (email or nickname)
- `status` (`active`/`suspended`)

Includes today’s usage for each user (from `user_usage`).

### GET /api/admin/users/{user_id}
User support detail:
- linked OAuth identities
- recent sessions
- recent usage
- recent admin audit related to that user

### GET /api/admin/users/{user_id}/sessions
Recent sessions for one user.

### GET /api/admin/users/{user_id}/usage
Recent daily usage rows for one user.

### PATCH /api/admin/users/{user_id}
Update user controls:
- `daily_chat_limit`
- `is_active`

This action is audited.

### GET /api/admin/queries
Query monitoring (PII-masked):
- Filters: `role`, `session_uuid`, `user_id`
- Returns chat messages with session/user context
- Content is PII-masked and truncated to 400 chars for list views

### GET /api/admin/queries/{message_id}
Read-only investigation detail for a selected query or answer row:
- Resolves the selected message plus its paired query/answer in the same session
- Returns masked query/answer content, session/user context, source payload, and stored trace metadata
- Intended for operator investigation, not editing

Returned investigation fields include:
- `answer.model_used`
- `answer.provider`
- `answer.response_mode`
- `answer.tokens_used`
- `answer.latency_ms`
- `answer.sources_count`
- `answer.sources_json`
- `answer.trace_json`
- `review_target_message_id`
- `review`

### PATCH /api/admin/queries/{message_id}/review
Create or update operator review state for one target message.

Supported statuses:
- `open`
- `resolved`
- `ignored`

Supported reasons:
- `bad_answer`
- `hallucination`
- `missing_source`
- `bad_source`
- `abuse`
- `other`

This action is audited.

### GET /api/admin/sessions/{session_uuid}
Session investigation detail:
- session metadata
- masked timeline of user/assistant turns
- provider and response metadata
- review status per message

### GET /api/admin/usage-stats
Usage + cost stats from `logs/usage.jsonl` via `usage_tracker.analyze_usage_logs`.
This remains a secondary analytics path, not the source of truth for admin
reliability.

### GET /api/admin/usage/recent
Recent usage entries from `logs/usage.jsonl` (PII masked).

### GET /api/admin/observability
Read-only reliability metrics for operators:
- `metrics_source` and per-metric availability flags indicate whether latency,
  cache, and cost came from PostgreSQL, usage logs, or both
- latency sample count, average latency, P50, P95
- slow-query count using a fixed threshold
- cache hit rate from persisted assistant messages, including cached replies
- average cost per query, estimated from stored total-token counts when needed
- zero-source answer count/rate over the last 24 hours
- average sources per answer over the last 24 hours
- rate-limited logged-in and anonymous users for today
- daily trend rows for query volume, cost, cache rate, and latency

### GET /api/admin/audit-logs
Admin action history from `admin_audit_logs`.

### GET /api/admin/data/tables
List whitelist-based read-only explorer tables.

### GET /api/admin/data/tables/{table_name}/schema
Return visible schema metadata for one allowed table.

### GET /api/admin/data/tables/{table_name}/rows
Return paginated rows for one allowed table with optional search.

This is intentionally:
- read-only
- whitelist-based
- not a SQL console

## Audit Logging
Admin write operations insert rows into `admin_audit_logs`.

Schema:
- `admin_user_id` (FK to users)
- `action`, `target_type`, `target_id`
- `before_state`, `after_state`, `context`
- `ip_hash`, `user_agent`
- `created_at`

PII is minimized by storing IP hashes (SHA-256) instead of raw IPs.

## Database Migration
The admin audit log table is created via Alembic:
- `backend/alembic/versions/008_add_admin_audit_logs.py`

Query investigation detail adds stored trace metadata on chat messages:
- `backend/alembic/versions/009_add_chat_message_trace.py`

Query review workflow adds:
- `backend/alembic/versions/010_add_admin_query_reviews.py`

Apply in production:
```bash
cd /opt/buddha-korea
./scripts/migrate.sh upgrade head
```

## Data Sources
- Users / sessions / chat: PostgreSQL
- Usage stats: `logs/usage.jsonl`
- Q&A logs (if needed): `logs/qa_pairs.jsonl` (PII masked)

`chat_messages.trace_json` now stores the structured query trace used by the admin investigation panel. The trace is write-on-response and read-only in the admin UI.

`admin_query_reviews` stores operator review state separately from chat runtime data.

Reliability metrics are database-first:
- `chat_messages` is the source of truth for latency, cache-hit, estimated cost,
  and query volume.
- `logs/usage.jsonl` is optional supplemental input and is only merged when DB
  cache metrics are unavailable in a given window.

This keeps the admin panel grounded in already collected runtime data without exposing raw server internals or requiring SSH access.

If `logs/usage.jsonl` is not present in a given environment, `usage_log_available`
may be false while reliability cards remain populated from DB.

## Observability Performance Guardrail

Admin observability queries rely on the composite index below to avoid
assistant-message full scans:

- `chat_messages(role, created_at)` via Alembic revision
  `011_add_chat_messages_role_created_at_index`.

## Phase 8 Governance Docs

Operational policy now also lives in:

- [PRIVACY_AND_DATA_RETENTION.md](./PRIVACY_AND_DATA_RETENTION.md)
- [ADMIN_SECURITY.md](./ADMIN_SECURITY.md)
- [SOURCE_GOVERNANCE.md](./SOURCE_GOVERNANCE.md)

## Local Development
1) Start dev stack:
   - `make dev`
2) Open admin console:
   - `http://localhost:8000/admin/`
3) Log in via OAuth:
   - `/auth/login/google` (or naver/kakao)

Note: Admin UI uses the same auth cookies as the public site.

## Production Deployment Notes
- Nginx serves `/admin/` as static content (see `config/nginx.conf`).
- If CSS/JS changes, use cache-busting query strings or restart nginx to refresh mounts.
- If Alembic revisions changed, run `./scripts/migrate.sh upgrade head` after deploy before validating admin query detail.
- After deployment, verify:
  - `/admin/` loads
  - `/api/admin/summary` returns 200 for admin users
  - `/api/admin/queries/{message_id}` returns 200 for a fresh traced message

## Future Phases (Planned)
- Corpus metadata editing + translation progress
- Feedback management workflow
- Re-embedding triggers and config diffing
- Incident management and site notices
- Deeper auth/session failure tracking once explicit login-failure metrics are collected

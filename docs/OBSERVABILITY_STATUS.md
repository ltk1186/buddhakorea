# Observability Status

Last updated: 2026-04-19

This document records which operational metrics are currently available in
production, where they come from, and what is still incomplete.

## Current Production Reality

Admin reliability metrics are now primarily database-backed, with usage logs
remaining optional for secondary usage analytics.

Performance guardrail:
- `chat_messages(role, created_at)` composite index is required to keep
  `/api/admin/observability` query latency stable under growth.

## Metrics Available Now

These metrics are currently available from persisted `chat_messages` and usage
tables:

- answered-query volume over the selected window
- latency sample count
- average latency
- P50 / P95 latency
- slow-query count
- cache-hit count
- cache-hit rate
- estimated average cost per query
- daily latency trend
- daily estimated cost trend
- answers in the last 24 hours
- zero-source answer count
- zero-source answer rate
- average sources per answer
- rate-limit pressure from daily usage tables

These are surfaced in:

- `GET /api/admin/observability`
- the admin Reliability panel

## What Usage Logs Still Provide

`logs/usage.jsonl` is still useful for local/debug usage analytics, but it is no
longer required for the admin reliability panel.

When that file is missing, the API may still report:

- `usage_log_available = false`

That now means only that local file-based usage analytics are absent. It no
longer means reliability cards should go blank.

## Why This Gap Exists

The current app persists assistant-message latency/tokens/model metadata in
PostgreSQL, and cached answers are also stored as assistant messages. That lets
admin reliability compute latency, cost, and cache-hit rate without depending
on a local file sink.

This is a data collection gap, not an admin rendering bug.

## Current Safe Interpretation

- DB-backed latency, quality, estimated cost, and cache-hit metrics are
  trustworthy enough
  for daily operations.
- Cost figures in reliability are estimated from stored total-token counts when
  usage logs are absent.

## Recommended Next Normalization

The next normalization target is now outside the admin reliability panel:

1. Keep DB-backed reliability aggregation as-is.
2. Move remaining local-file usage analytics to a durable structured sink.
3. Decide whether usage trends should live in PostgreSQL, Redis aggregates, or
   external structured logging.

## Verification

Check current production observability status with:

```bash
curl -s https://buddhakorea.com/api/admin/observability
```

For authenticated admin verification, use the admin UI:

- `https://buddhakorea.com/admin/`

## Related Docs

- [PRODUCTION_STATUS.md](./PRODUCTION_STATUS.md)
- [PRODUCTION_RUNBOOK.md](./PRODUCTION_RUNBOOK.md)
- [LOGGING.md](./LOGGING.md)

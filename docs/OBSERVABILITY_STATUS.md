# Observability Status

Last updated: 2026-04-16

This document records which operational metrics are currently available in
production, where they come from, and what is still incomplete.

## Current Production Reality

Admin reliability metrics are split across two sources:

1. PostgreSQL-backed application data
2. File-based usage logs (`logs/usage.jsonl`)

Today, production only has the first category reliably available.

## Metrics Available Now

These metrics are currently available in production because they come from the
database:

- answers in the last 24 hours
- zero-source answer count
- zero-source answer rate
- average sources per answer
- rate-limit pressure from daily usage tables

These are surfaced in:

- `GET /api/admin/observability`
- the admin Reliability panel

## Metrics Currently Unavailable in Production

These metrics depend on `logs/usage.jsonl`:

- latency distribution
- P50 / P95 latency
- cache hit rate
- slow-query count
- average cost per query
- daily cost trend from usage logs

When that file is missing, the API returns:

- `usage_log_available = false`

The admin UI intentionally renders those fields as unavailable instead of `0`.

## Why This Gap Exists

The current app already emits structured runtime data, but the admin reliability
panel still expects a local file-based sink for some metrics. Production does
not currently persist that file in a dependable way.

This is a data collection gap, not an admin rendering bug.

## Current Safe Interpretation

- DB-backed quality metrics are trustworthy.
- File-based latency/cache/cost metrics should be treated as not collected in
  production.
- Operators should not infer healthy latency or low cost from blank values.

## Recommended Next Normalization

Move reliability metrics off local file assumptions and onto a production-safe
source of truth:

1. Keep DB-backed quality metrics as-is.
2. Normalize latency/cache/cost metrics from one of:
   - structured application logs
   - PostgreSQL
   - Redis aggregates
3. Update `GET /api/admin/observability` to prefer that source over local files.

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

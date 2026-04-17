# Observability Status

Last updated: 2026-04-17

This document records which operational metrics are currently available in
production, where they come from, and what is still incomplete.

## Current Production Reality

Admin reliability metrics are now split across two explicit sources:

1. PostgreSQL-backed application data
2. File-based usage logs (`logs/usage.jsonl`)

Production can operate with the first source alone. The second source is now an
optional cache sample, not a hard dependency for latency/cost visibility.

## Metrics Available Now

These metrics are currently available from persisted `chat_messages` and usage
tables:

- answered-query volume over the selected window
- latency sample count
- average latency
- P50 / P95 latency
- slow-query count
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

## Metrics Still Dependent on Usage Logs

These metrics still depend on `logs/usage.jsonl`:

- cache hit rate
- cached query count
- daily cache-hit sample

When that file is missing, the API now returns:

- `usage_log_available = false`
- `cache_metrics_available = false`

The admin UI renders cache-specific fields as unavailable, while still showing
DB-backed latency and estimated cost metrics.

## Why This Gap Exists

The current app persists assistant-message latency/tokens/model metadata in
PostgreSQL, so reliability no longer needs to block on local files for its core
operator view. Cache-hit sampling still needs a log sink because cached answers
do not create assistant message rows today.

This is a data collection gap, not an admin rendering bug.

## Current Safe Interpretation

- DB-backed latency, quality, and estimated cost metrics are trustworthy enough
  for daily operations.
- Cache-hit rate should still be treated as not collected when the usage log
  sample is missing.
- Cost figures in reliability are estimated from stored total-token counts when
  usage logs are absent.

## Recommended Next Normalization

The next normalization target is narrower now:

1. Keep DB-backed latency/quality/cost estimation as-is.
2. Move cache-hit sampling to a production-safe source of truth:
   - structured application logs
   - PostgreSQL event rows
   - Redis aggregates
3. Remove the remaining cache-specific dependence on local `usage.jsonl`.

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

# Privacy and Data Retention

Last updated: 2026-04-17

This document defines the current operating policy for user data, chat data,
admin access, and log retention in Buddha Korea.

## Scope

Applies to:

- public user accounts
- OAuth identities
- chat sessions and chat messages
- admin investigation access
- usage and observability logs
- source metadata and corpus operations

## Core Principles

1. Minimize collection.
2. Prefer masked or derived operational data over raw personal data.
3. Separate public-user permissions from admin access.
4. Keep retention rules explicit enough that operators can explain them.
5. Avoid using raw database/SSH access for routine support work.

## Data Classes

### Account Data

- user email
- nickname
- profile image
- OAuth provider linkage
- internal role

Purpose:

- authentication
- account support
- access control

### Session and Chat Data

- chat session UUID
- user/assistant messages
- source references
- prompt/retrieval/provider trace
- latency and token totals

Purpose:

- conversation continuity
- answer investigation
- quality monitoring
- reliability and cost analysis

### Usage Data

- daily chat counts per user
- daily chat counts per anonymous IP hash
- token totals
- rate-limit state

Purpose:

- quota enforcement
- abuse control
- product operations

### Admin Data

- admin identity
- admin actions
- before/after state diffs
- review notes

Purpose:

- auditability
- internal accountability

## Current Retention Expectations

Current implementation keeps operational data until an explicit cleanup or
future retention job says otherwise. That is acceptable for internal beta
operations, but not strong enough for commercial maturity.

Recommended default targets:

- `chat_sessions` / `chat_messages`
  - keep while account is active and investigation needs exist
  - define archival/deletion policy before broad paid launch
- `user_usage` / `anonymous_usage`
  - keep at least 90 days for abuse and quota review
  - consider aggregation for older data
- `admin_audit_logs`
  - keep at least 1 year
- local analytics files
  - do not treat local files as long-term source of truth
  - move to structured log sink or DB-backed aggregation

## Existing Controls

- masked email exposure for read-only roles
- PII masking in usage and Q&A logs
- read-only admin data explorer
- role-gated admin endpoints
- audit logging for write actions

## Gaps To Close Before Broad Commercial Rollout

1. User deletion/export workflow is not formalized.
2. Retention schedules are not enforced by jobs yet.
3. Public privacy-policy text should explicitly cover:
   - chat storage
   - source trace storage
   - admin review access
   - OAuth profile data

## Operational Rules

- Do not expose raw OAuth tokens in admin UI.
- Do not add arbitrary SQL consoles to admin.
- Do not unmask logs for analyst/read-only roles.
- Use admin UI or audited scripts for routine support actions.
- Treat Buddhist chat questions as potentially sensitive user content.

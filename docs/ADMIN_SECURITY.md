# Admin Security

Last updated: 2026-04-17

This document defines the minimum security posture for Buddha Korea admin
operations.

## Admin Access Model

Admin access is internal-only and role-gated.

Current roles:

- `admin`
- `ops`
- `support`
- `analyst`

Rules:

- public users and admins remain logically separate in permissions
- admin routes stay under `/api/admin`
- admin writes must be auditable

## Authentication

Current admin entry paths:

- OAuth login followed by role-gated access
- password-based admin login via `POST /api/admin/login`

Operational requirements:

- keep admin password in GitHub Secrets only
- never hand-edit production `.env`
- rotate admin credentials after staff/ownership changes
- prefer explicit logout on shared machines

## Authorization

Least-privilege rules:

- `analyst`
  - read-only dashboards and investigation views
  - no user edits
  - no query review writes
- `support`
  - user quota/status changes
  - query review updates
  - no secret/infra access
- `ops`
  - all support actions
  - audit log access
  - operational controls
- `admin`
  - full internal access
  - still subject to audit logging

## Dangerous Actions

These actions should always be treated as high-risk:

- disabling users
- changing quota policy
- editing source metadata
- changing prompt/model/provider behavior
- triggering expensive background jobs
- changing production secrets

Requirements:

- explicit confirmation in UI
- audit log entry with before/after state
- clear operator identity

## Infrastructure Access

Admin UI is meant to reduce SSH usage, not replace controlled server access for
maintenance.

Rules:

- routine support and investigation should use the admin UI
- schema changes use `./scripts/migrate.sh`
- emergency shell access stays restricted to trusted operators
- do not expose raw infra commands through admin UI

## Data Explorer Rules

The admin data explorer must remain:

- whitelist-based
- read-only
- paginated
- masked where required

It must not become:

- an arbitrary SQL console
- a secret viewer
- a bypass around audit logging

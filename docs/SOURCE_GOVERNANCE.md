# Source Governance

Last updated: 2026-04-17

This document defines how Buddha Korea should treat Buddhist source data,
metadata, and retrieval-facing corpus state.

## Why This Matters

Buddha Korea is not a generic chat product. Its trust depends on:

- stable source identifiers
- citation quality
- retrievable metadata
- operator ability to trace answers back to texts

## Source Objects

Primary source-facing objects in the current system:

- sutra/source summary records
- source metadata used by `/api/sources`
- retrieval-facing chunk metadata in ChromaDB
- assistant citations stored in `chat_messages.sources_json`

## Governance Rules

1. Stable identifiers first.
   - `sutra_id` remains the canonical retrieval key.
2. Metadata edits must be traceable.
   - who changed it
   - when
   - what changed
3. Retrieval and metadata must not silently drift apart.
4. Source titles shown to users should prefer curated metadata over raw chunk data.

## Current State

Current strengths:

- `sutra_id` is used consistently across source APIs and retrieval traces
- answer rows store `sources_json`
- admin query investigation can inspect source payloads

Current gaps:

- source metadata version history is not formalized
- metadata edits are not yet first-class admin workflows
- re-embedding / vector refresh controls are not yet operationalized in admin

## Minimum Change-Control Standard

Before operators can edit source metadata in production, the system should
support:

1. before/after diff storage
2. change reason
3. editor identity
4. rollback path
5. explicit note when metadata changes require vector refresh

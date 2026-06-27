# Pāli Step 7 Pilot 1,000 Live Pipeline

Step 7 implements the guarded live pipeline for the fixed Pilot 1,000 request preview produced by Step 6. This file documents the operator workflow and the safety boundary.

## Boundary

Codex implementation work must run only local preflight and tests. It must not submit, poll, fetch, retry, or call any provider.

Operator-run live modes are explicit:

- `--submit`
- `--poll`
- `--fetch`
- `--parse`
- `--qa`
- `--report`
- `--retry-bracket`

The CLI does not auto-chain modes. `--submit` does not poll, `--poll` does not fetch, and `--fetch` does not parse.

## Inputs

- Step 6 request preview: `data/reports/pali/pilot_1000_batch/pilot_1000_request_preview.jsonl`
- Step 6 dry-run manifest: `data/reports/pali/pilot_1000_batch/pilot_1000_dry_run_manifest.json`
- Step 6 validation report: `data/reports/pali/pilot_1000_batch/pilot_1000_validation_report.json`
- Step 5 selection manifest: `data/pilot_sets/pali/pilot_1000_v1_manifest.json`
- Inventory source commit: `49bc86914748589a2501b548cc6b3e97a8abe018`
- Prompt variant: `natural_ko_v2_2`
- Output mode: Gemini `response_schema`
- Parse fallback: strict JSON, raw decode salvage, stack reclose salvage
- QA model: `PASS`, `FAIL_RETRY_ONLY`, `FAIL_BLOCKING`

## Preflight

Preflight is local-only and writes:

- `pilot_1000_submit_preflight.json`
- `pilot_1000_submit_preflight.md`

It verifies:

- request preview has exactly 1,000 rows;
- preview key order matches the Step 5 manifest;
- inventory source commit matches the pinned commit;
- Step 6 dry-run status is `PASS`;
- Step 6 `submit_ready` and `cap_passed` are true;
- estimated p90 cost is under the hard cap;
- response schema is Gemini dialect valid, has `propertyOrdering`, and has no `additionalProperties`;
- generation config is identical across all requests;
- `reader_ko` is absent;
- `natural_ko_v2_2` marker is present;
- old stiff literal anchors are absent;
- no provider batch id already exists.

## Duplicate-Spend Guard

Live submit is blocked unless the latest preflight passed and the current request preview SHA-256 still matches the preflight SHA-256. If any existing provider batch id is present in `submit_run_manifest.json` or `pilot_1000_provider_status.json`, submit returns `BLOCKED_ALREADY_SUBMITTED`.

## Operator Commands

Preflight:

```bash
./venv/bin/python -m backend.pali.scripts.submit_pilot_1000_batch \
  --preflight \
  --request-preview data/reports/pali/pilot_1000_batch/pilot_1000_request_preview.jsonl \
  --manifest data/pilot_sets/pali/pilot_1000_v1_manifest.json \
  --out data/reports/pali/pilot_1000_batch \
  --hard-cap-usd 50 \
  --pretty
```

Submit, real cost, operator only:

```bash
./venv/bin/python -m backend.pali.scripts.submit_pilot_1000_batch \
  --submit \
  --request-preview data/reports/pali/pilot_1000_batch/pilot_1000_request_preview.jsonl \
  --manifest data/pilot_sets/pali/pilot_1000_v1_manifest.json \
  --out data/reports/pali/pilot_1000_batch \
  --hard-cap-usd 50 \
  --pretty
```

Poll:

```bash
./venv/bin/python -m backend.pali.scripts.submit_pilot_1000_batch \
  --poll \
  --out data/reports/pali/pilot_1000_batch \
  --pretty
```

Fetch:

```bash
./venv/bin/python -m backend.pali.scripts.submit_pilot_1000_batch \
  --fetch \
  --out data/reports/pali/pilot_1000_batch \
  --pretty
```

Parse:

```bash
./venv/bin/python -m backend.pali.scripts.submit_pilot_1000_batch \
  --parse \
  --request-preview data/reports/pali/pilot_1000_batch/pilot_1000_request_preview.jsonl \
  --manifest data/pilot_sets/pali/pilot_1000_v1_manifest.json \
  --out data/reports/pali/pilot_1000_batch \
  --pretty
```

QA:

```bash
./venv/bin/python -m backend.pali.scripts.submit_pilot_1000_batch \
  --qa \
  --out data/reports/pali/pilot_1000_batch \
  --pretty
```

Report:

```bash
./venv/bin/python -m backend.pali.scripts.submit_pilot_1000_batch \
  --report \
  --out data/reports/pali/pilot_1000_batch \
  --pretty
```

Optional bracket retry plan:

```bash
./venv/bin/python -m backend.pali.scripts.submit_pilot_1000_batch \
  --retry-bracket \
  --out data/reports/pali/pilot_1000_batch \
  --retry-hard-cap-usd 5 \
  --pretty
```

The retry mode currently writes a plan only. It does not submit retry requests.

## Raw Result Policy

Raw provider results are written only under `data/reports/pali/pilot_1000_batch/`, which is covered by the repository `data/reports/` ignore rule. Parsed and Markdown reports must not copy raw provider response bodies, thought signatures, credentials, or request headers.

## Cost

Step 6 estimated the real Pilot 1,000 cost at about `$28-32` with a hard cap of `$50`. Live submit is blocked if the p90 estimate exceeds the configured cap.

## QA Model

Per-segment QA uses three states:

- `PASS`: no blocking and no retry-only failure.
- `FAIL_RETRY_ONLY`: only retryable mechanical defects, currently bracket supplementation.
- `FAIL_BLOCKING`: provider error, schema invalid, empty translation, unsupported insertion, known content omission, negation-scope risk, or hard glossary violation.

Hard glossary checks use co-occurrence gating: a disallowed Korean rendering only fires when the relevant Pāli term appears in source text or parsed terms.

Manual review remains required. The final recommendation after report generation stays `pending_operator_and_scholar_review`.

## Not In Scope

Step 7 does not start the full 200k corpus run and does not provide any executable path for it.


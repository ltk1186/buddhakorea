# Pali Step 6 Pilot 1,000 Dry-Run

## Purpose

Step 6 prepares the existing Step 5 `pilot_1000_v1_manifest` for a later live batch. It creates a local request preview, cost estimate, corpus-reweighted extrapolation, submit plan, validation report, and QA/retry plan.

This step is dry-run only. It does not submit, poll, fetch, parse, or generate live translations.

## Boundary

- No Gemini/API/Batch/provider/network calls.
- No live 1,000 submit.
- No re-selection of the 1,000 segments.
- No production prompt, response schema, glossary, gold set, source XML, or corpus mutation.
- No `reader_ko` field.

## Inputs

- Selection manifest: `data/pilot_sets/pali/pilot_1000_v1_manifest.json`
- Inventory cache: `data/pilot_sets/pali/pilot_300_v1_inventory_cache_49bc869.json`
- Inventory source commit: `49bc86914748589a2501b548cc6b3e97a8abe018`
- Prompt candidate: `natural_ko_v2_2`
- Adoption record: `docs/translation/PALI_NATURAL_KO_V2_2_ADOPTION.md`
- Output mode: Gemini-dialect `response_schema`
- Fallback plan: salvage cascade remains enabled for later live parse.

## Outputs

Artifacts are written under:

```text
data/reports/pali/pilot_1000_batch/
```

Key files:

- `pilot_1000_request_preview.jsonl`
- `pilot_1000_cost_estimate.json/.md`
- `pilot_1000_corpus_extrapolation.json/.md`
- `pilot_1000_submit_plan.md`
- `pilot_1000_qa_retry_plan.md`
- `pilot_1000_validation_report.json/.md`
- `pilot_1000_dry_run_manifest.json`
- `pilot_1000_no_api_executed.md`

## Hard Cap

Default cap:

```text
hard_cap_usd = 50
```

The dry-run computes mean and p90 estimates. Submit readiness requires:

```text
estimated_cost_usd_p90 <= hard_cap_usd
```

If the cap fails, artifacts are still written but `submit_ready=false`.

## Corpus Extrapolation

The Pilot 1,000 intentionally over-samples hard buckets such as long and tika. Do not multiply the pilot average by the full corpus count.

Step 6 uses corpus bucket weights from the pinned inventory cache when available:

```text
corpus_weighting_method = joint_inventory_counts
```

If joint counts are unavailable, the fallback is explicitly marked:

```text
corpus_weighting_method = marginal_independence_approximation
```

## QA / Retry Plan

Later live output uses the 3-state gate:

- `PASS`
- `FAIL_RETRY_ONLY`
- `FAIL_BLOCKING`

Blocking categories include provider errors, schema invalid output, empty translations, unsupported insertions, known omissions, negation-scope risk, and hard glossary violations with co-occurrence gating.

Retry-only categories currently include bracket violations and future isolated salvageable parse defects.

Advisory glossary warnings and general content-omission scholar review are tracked but do not block automatically.

## Dry-Run Command

```bash
./venv/bin/python -m backend.pali.scripts.run_pilot_1000_dry_run \
  --manifest data/pilot_sets/pali/pilot_1000_v1_manifest.json \
  --out data/reports/pali/pilot_1000_batch \
  --prompt-variant natural_ko_v2_2 \
  --response-schema \
  --dry-run \
  --pretty
```

Optional:

```bash
--hard-cap-usd 50
```

## Later Live Submit

Later live submit is a separate task. This Step 6 dry-run CLI intentionally has no live submit path.

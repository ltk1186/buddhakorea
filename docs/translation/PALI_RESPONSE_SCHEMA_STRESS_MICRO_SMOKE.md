# Pāli Step 4 Response Schema Stress Micro-Smoke

## Purpose

Step 4 asks whether Gemini `response_schema` reduces strict JSON parse failures
compared with the current free-form JSON output plus the salvage cascade.

This is an A/B batch-path experiment only. It produces a recommendation; it
does not change production prompt behavior.

## Scope

Arm A uses the current verified prompt payload and generation config with no
`response_schema`.

Arm B uses the same prompt payload and generation config, plus an API-level
experiment copy of the current translation output schema under
`response_schema`.

The prompt text is not re-rendered. The experiment reads the existing verified
300-pilot unsubmitted JSONL and selects lines from it.

## Default Safety

Default execution is dry-run and local-only:

```bash
./venv/bin/python -m backend.pali.scripts.run_response_schema_smoke --pretty
```

This writes the selection, A/B JSONL, response schema copy, cost estimate,
submit plan, placeholder status files, recommendation placeholder, and run
manifest under:

```text
data/reports/pali/step4_response_schema_smoke/
```

No API call is made unless `--submit` is explicitly supplied.

## Hard Cap

The Step 4 hard cap is `$4`.

If the selected 50 × 2 request estimate exceeds the cap, submit is blocked.
If planned requests exceed 100, submit is blocked unless the operator supplies
an explicit override.

## Selection

The selection is deterministic and SHA-256 based.

It includes:

- all 34 known 300-batch strict-parse failures recovered by `raw_decode` or
  `stack_reclose`
- 16 additional vulnerable strict-passed segments selected from risky buckets

If the 34 known failures cannot be found, selection readiness is blocked.

## Silver Canary Policy

Step 3G-B silver canary remains advisory only.

- silver canary is not gold accuracy
- active silver items are advisory regression signals
- `needs_pali_expert=true` is `needs_review`, not a failure

## Recommendation Criteria

Adopt `response_schema` for the 1,000 pilot only if the batch path supports it,
Arm B strict parse behavior is near-perfect and clearly better, schema validity
does not regress, mechanical content suppression is not detected, and cost
overhead is acceptable.

Otherwise keep the current free-form JSON plus salvage cascade. This is an
acceptable recommendation because the current salvage cascade recovered all
34/34 failures in the 300 pilot.

## Non-Mutations

Step 4 does not modify:

- production prompts
- prompt templates
- translation schema files
- glossary files
- gold sets
- source XML
- existing 300 parsed outputs
- holdout gold state


# Pali natural_ko v2.2 Adoption Decision

## Decision

Adopt `natural_ko_v2_2` as the Step 6 dry-run default prompt candidate.

## Scope

- This is adoption for the Step 6 dry-run and cost-gated submit plan.
- This is not a live 1,000 batch start.
- The live 1,000 run requires a separate preflight, cost-cap pass, and explicit submit.
- Step 6 must use the existing Step 5 `pilot_1000_v1_manifest` selection rather than reselecting 1,000 segments.

## Rationale

- D-arm 30/30 items parsed successfully.
- D-arm 30/30 items were schema-valid.
- `response_schema` remained enabled.
- Salvage fallback remained enabled.
- No `reader_ko` field was added.
- Readability improved substantially over A-prime/C while avoiding B-style unsupported additions.
- Known-risk insertions did not recur.
- Known deterministic omissions: 0.
- Negation-scope risks: 0.
- Hard glossary violations: 0 after co-occurrence gating.
- `khandha -> 무더기` remains a hard lock.
- `khandha:무리` was a checker false positive caused by unscoped substring matching and was fixed by co-occurrence gating.
- Manual sample review passed for first-draft use.

## Remaining Issue

- One bracket violation remains in the D-arm sample.
- This is classified as `retry_only`, not prompt redesign.
- The affected segment should be routed to automatic retry/QA.

## Gate Status

- `objective_gate_status`: `FAIL_RETRY_ONLY`
- `blocking_failures`: 0
- `retry_only_failures`: 1
- Retry-only item: `vri:romn:e0103n.att:355746de2b2a`
- Retry-only type: `bracket_violation`
- Retry-only details: `[그것은]`, `square_bracket_present`

## Not Done

- Step 6 dry-run CLI was not implemented in this task.
- Step 6 live 1,000 was not started.
- No provider/API/network/batch calls were made in this task.
- No production prompt, response schema, Step 5 selection, source XML, or translation corpus mutation was made.

## Detailed Local Artifacts

Detailed generated reports are under:

```text
data/reports/pali/natural_ko_calibration_v2_2/
```

These are local generated artifacts and may be gitignored. This document is the tracked decision record.

## Date And Commit

- Date: 2026-06-26
- Branch: `codex/translation`
- Commit at decision-record creation: `3a4cdfb`

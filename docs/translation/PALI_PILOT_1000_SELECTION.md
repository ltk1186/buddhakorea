# Pāli Pilot 1,000 Selection

## Purpose

Step 5 fixes the input set for the next Pāli translation pilot:

```text
pilot_1000_new = 1,000 new production-like segments
```

This is a selection-only step. It does not call Gemini, submit Batch jobs,
generate translations, build final Batch JSONL, estimate the full 1,000 cost,
or start Step 6.

## Pinned Corpus Snapshot

Selection uses the existing local inventory cache:

```text
data/pilot_sets/pali/pilot_300_v1_inventory_cache_49bc869.json
```

The pinned source commit is:

```text
49bc86914748589a2501b548cc6b3e97a8abe018
```

This cache is the authority for `stable_segment_key`, `source_text_hash`,
`source_path`, `text_layer`, `length_bucket`, `chunk_type`, `pitaka`, and
`nikaya`.

The cache predates Step 3H importer note preservation, so Step 5 reparses the
local source XML read-only with `preserve_source_apparatus=True` to populate
`has_source_apparatus` and `source_apparatus_count`. Apparatus is source
metadata for QA/review only. It is not prompt input and is not merged into
`original_text`.

## Scope Note

The pinned inventory excludes `nrf` / anya at inventory level. Step 5 preserves
that scope and records a scoping note. Permanent exclusion of this layer from
full-corpus translation should be explicitly confirmed by the operator in a
separate scope decision.

## Selection Design

The manifest contains:

- representative: 700
- hard: 300

Representative selection is stratified toward corpus-like axes:

- text layer target: `mula 365`, `atthakatha 265`, `tika 70`
- length target: `short 233`, `medium 233`, `long 234`
- chunk target: `prose 530`, `verse/mixed 170`

Hard selection uses one primary bucket per item with this fixed priority:

```text
apparatus_bearing > tika_long > atthakatha_long >
mula_long_or_dense_abhidhamma > verse_or_mixed >
citation_heavy_or_commentarial_dense
```

The hard quotas are:

```text
apparatus_bearing: 40
tika_long: 80
atthakatha_long: 70
mula_long_or_dense_abhidhamma: 40
verse_or_mixed: 35
citation_heavy_or_commentarial_dense: 35
```

## Disjointness

The selected 1,000 must be disjoint from:

- pilot 75
- pilot 300
- Step 4 A/B selection
- silver canary candidates
- gold set keys

Silver canary items are not merged into the main 1,000. They are represented in
`pilot_1000_v1_silver_append_plan.json`.

## Carry-Forward Policy

From finalized Step 4:

- `response_schema` is the default output mode for the 1,000 pilot.
- salvage cascade remains enabled as fallback.
- optional-array and uncertainties shifts must be tracked in later QA.
- gold holdout is not frozen.
- gold accuracy must not be claimed.
- silver canary remains advisory only.

Production-new request count is 1,000. The 20 silver canary items may be
optionally appended as advisory regression monitors, for a maximum of 1,020
requests if appended. They are not gold holdout and must be excluded from gold
accuracy scoring.

## CLI

```bash
./venv/bin/python -m backend.pali.scripts.select_pilot_1000 \
  --out data/pilot_sets/pali \
  --pretty
```

The command writes:

```text
data/pilot_sets/pali/pilot_1000_v1_manifest.json
data/pilot_sets/pali/pilot_1000_v1_summary.md
data/pilot_sets/pali/pilot_1000_v1_validation.json
data/pilot_sets/pali/pilot_1000_v1_silver_append_plan.json
data/pilot_sets/pali/pilot_1000_v1_run_manifest.json
```

## Validation

Hard failures:

- selected count is not 1,000
- representative count is not 700
- hard count is not 300
- duplicate key
- overlap with pilot 75, pilot 300, or Step 4
- missing identity fields
- gold holdout item in the main manifest
- silver canary item in the main manifest

Soft guardrails produce `PASS_WITH_WARNINGS` rather than failure:

- tika total outside `[140, 240]`
- long total below `250`
- short total above `450`
- verse/mixed total below `80`
- apparatus-bearing total below `30`

## Next Step

Step 6 should perform response_schema-based cost estimate and dry-run JSONL
generation from this fixed manifest. Step 5 does not start Step 6.


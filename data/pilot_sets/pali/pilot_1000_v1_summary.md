# Pāli Pilot 1,000 Selection

## Purpose

Step 5 selected exactly 1,000 new production-like Pāli segments for the next pilot.
No Gemini/API/Batch calls were made. No translations were generated.

## Carry-Forward Policy

- response_schema is the intended default output mode for Step 6/7/8.
- salvage cascade remains enabled as fallback.
- optional-array and uncertainties shifts must be tracked in later QA.
- gold holdout is not frozen and gold accuracy is unavailable.
- silver canary remains advisory-only and is not included in the main 1,000.

## Corpus Snapshot

- inventory source commit: `49bc86914748589a2501b548cc6b3e97a8abe018`
- inventory cache: `data/pilot_sets/pali/pilot_300_v1_inventory_cache_49bc869.json`
- nrf/anya layer is excluded at inventory level. This scope is preserved here; permanent full-corpus exclusion should be operator-confirmed.

## Counts

- selected_count: `1000`
- representative_count: `700`
- hard_count: `300`
- duplicate_count: `0`
- overlap_with_75/300/step4: `0` / `0` / `0`
- apparatus_bearing_count: `80`
- validation_status: `PASS_WITH_WARNINGS`

## Distribution

### By Text Layer

| Value | Count |
|---|---:|
| `atthakatha` | 373 |
| `mula` | 469 |
| `tika` | 158 |

### By Length Bucket

| Value | Count |
|---|---:|
| `long` | 401 |
| `medium` | 302 |
| `short` | 297 |

### By Chunk Type

| Value | Count |
|---|---:|
| `prose` | 804 |
| `verse` | 196 |

### By Selection Group

| Value | Count |
|---|---:|
| `hard` | 300 |
| `representative` | 700 |

### By Selection Bucket

| Value | Count |
|---|---:|
| `apparatus_bearing` | 40 |
| `atthakatha_long` | 70 |
| `citation_heavy_or_commentarial_dense` | 35 |
| `mula_long_or_dense_abhidhamma` | 40 |
| `representative_stratified` | 700 |
| `tika_long` | 80 |
| `verse_or_mixed` | 35 |

## Representative Targets

- corpus layer proportions: `{'mula': '52.2%', 'atthakatha': '37.7%', 'tika': '10.0%'}`
- representative layer target: `{'mula': 365, 'atthakatha': 265, 'tika': 70}`
- representative length target: `{'short': 233, 'medium': 233, 'long': 234}`
- representative chunk target: `{'prose': 530, 'verse': 170}`

## Silver Canary Append Plan

- silver candidate count: `20`
- active silver count: `18`
- max request count if appended: `1020`
- silver items are advisory regression monitors and excluded from gold accuracy scoring.

## Guardrail Warnings

- representative cell ('atthakatha', 'long', 'verse') underfilled: target 22, selected 2
- representative cell ('mula', 'long', 'verse') underfilled: target 30, selected 8
- representative cell ('tika', 'long', 'verse') underfilled: target 6, selected 0
- representative group used deterministic backfill count 48
- pinned inventory contains duplicate stable_segment_key rows; deduped 8354 rows across 2724 keys

## Next Step

Step 6: response_schema-based cost estimate and dry-run JSONL. Do not start Step 6 from this selection command.

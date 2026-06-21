# Pāli Step 3G-A Post-hoc Review Harvest

## Purpose

Step 3G-A is the code/scaffolding portion of the post-hoc review harvest after the 300 pilot. It prepares review artifacts from existing local outputs only:

- Step 3E reclassified QA findings
- Step 3F VRI XML `<note>` apparatus evidence
- 300 pilot parsed translations
- 300 pilot selection manifest
- optional manual seed decisions

It does not freeze `holdout_gold`. Human adjudication happens later in Step 3G-B.

## Scope Boundary

Step 3G-A is apparatus-aware QA/review, not apparatus-aware translation.

It does not:

- inject XML `<note>` apparatus into translation prompts
- modify translation prompts
- modify translated outputs
- modify source XML
- modify glossary files
- modify frozen gold data
- call Gemini, Batch, second-model judges, or any network service
- select the 1,000 pilot
- submit any batch

## Manual Seed Decisions

The remaining review decisions are not inferred by code.

If `data/review_seeds/pali/step_3g_remaining_seed_decisions.json` exists, the pipeline ingests it and writes it back to `seed_decisions_ingested.json`.

If the seed file does not exist, the pipeline creates `seed_decisions_template.json`. Each remaining item is marked:

```json
{
  "seed_decision": "unadjudicated",
  "decision_source": "needs_manual_review_seed",
  "blocks_1000_pilot": false,
  "llm_retry_required": false,
  "expert_review_required": false
}
```

Missing seed decisions do not create glossary, reference, targeted retry, or expert-review candidates.

## Internal Notes

Apparatus-bearing segments receive internal note records.

These notes are:

- internal review metadata only
- not public reader notes
- not automatic source changes
- not automatic translation changes
- not LLM retry instructions

The status names preserve the Step 3F distinction:

- `apparatus_attests_variant`
- `apparatus_has_variant_nearby`
- `no_apparatus_variant`

Apparatus evidence is attestation for review. The VRI main text remains the current source reading unless a later reviewed process records an explicit adopted variant decision.

## Candidate Files

Step 3G-A writes candidate files for later review:

```text
glossary_candidates.json
reference_table_candidates.json
targeted_retry_candidates.json
expert_review_candidates.json
```

Candidate policy:

- glossary candidates require explicit manual seed decisions or later reviewed mechanical metadata rules
- reference table candidates require explicit manual seed decisions or later reviewed mechanical reference rules
- targeted retry candidates require explicit manual seed decisions
- expert review candidates require manual seed decisions or pre-existing expert-review flags

The current step records candidates; it does not apply them.

## Holdout Drafts

Step 3G-A creates:

```text
holdout_adjudication_template.json
holdout_gold_manifest_draft.json
```

Both are draft-only:

- `frozen=false`
- `holdout_gold_frozen=false`
- needs human adjudication
- not usable for prompt tuning
- not usable for glossary tuning

Step 3G-B is the later human review step that decides acceptance type, constraints, exact expected behavior, or reference-only criteria.

## Future 1,020 Request Rule

The later 1,000 pilot uses:

```text
pilot_1000_new = 1,000 new segments, disjoint from pilot_75 and pilot_300
holdout_gold_regression = 20 frozen holdout items intentionally re-included
total future batch requests = 1,020
```

Step 3G-A records this rule only. It does not select the 1,000 new segments and does not submit a batch.

## CLI

```bash
./venv/bin/python -m backend.pali.scripts.run_step_3g_posthoc_review_harvest \
  --review-queue-reclassified data/qa_reports/pali/qa_report_300_live_salvaged_integrated/review_queue_reclassified.json \
  --findings data/qa_reports/pali/qa_report_300_live_salvaged_integrated/findings.json \
  --parsed data/reports/pali/pilot_300_batch/pilot_300_batch_parsed_salvaged.json \
  --apparatus-crosscheck data/qa_reports/pali/variant_apparatus_v0/apparatus_qa_crosscheck.json \
  --variant-apparatus data/qa_reports/pali/variant_apparatus_v0/variant_apparatus.json \
  --pilot-300-manifest data/pilot_sets/pali/pilot_300_v1_manifest.json \
  --gold-set data/gold_set.json \
  --seed-decisions data/review_seeds/pali/step_3g_remaining_seed_decisions.json \
  --out data/qa_reports/pali/step_3g_posthoc_review_harvest \
  --pretty
```

## Outputs

```text
data/qa_reports/pali/step_3g_posthoc_review_harvest/
  seed_decisions_ingested.json
  seed_decisions_template.json        # only when seed file is missing
  internal_notes.json
  glossary_candidates.json
  reference_table_candidates.json
  targeted_retry_candidates.json
  expert_review_candidates.json
  holdout_adjudication_template.json
  holdout_gold_manifest_draft.json
  step_3g_summary.md
  run_manifest.json
```

## Run Manifest Invariants

`run_manifest.json` must record:

```json
{
  "step": "3G-A",
  "api_llm_calls": 0,
  "network_calls": 0,
  "translation_mutation": false,
  "source_mutation": false,
  "prompt_mutation": false,
  "glossary_mutation": false,
  "gold_set_mutation": false,
  "holdout_gold_frozen": false,
  "manual_adjudication_required": true,
  "future_total_batch_requests": 1020
}
```

## Next Step

Step 3G-B is human adjudication:

- review remaining seed decisions
- decide whether any candidates should be kept for later work
- adjudicate the 20 holdout candidates
- freeze holdout gold only after explicit human review

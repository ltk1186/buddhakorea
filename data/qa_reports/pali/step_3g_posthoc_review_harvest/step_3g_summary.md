# Pāli Step 3G-A Post-hoc Review Harvest

## Purpose

Step 3G-A prepares review harvest artifacts only. It does not freeze holdout gold, modify translations, update prompts, or apply apparatus readings.

## Policy

- Apparatus is used for QA/review evidence, not translation prompt injection.
- Internal notes are review metadata only and are not public reader notes.
- Manual seed decisions are not inferred by code.
- Holdout files are draft-only until human adjudication in Step 3G-B.
- API/LLM/network calls: 0.

## Counts

- expert_review_candidates: 12
- glossary_candidates: 2
- holdout_template_items: 20
- internal_note_records: 12
- internal_note_segments: 10
- reference_table_candidates: 1
- remaining_review_items: 12
- seed_decisions_ingested: 12
- targeted_retry_candidates: 0

## Seed Decisions

- seed decision file present: true
- missing seed decisions produce a template; they do not produce semantic candidate decisions.

## Holdout Draft

- holdout adjudication template items: 20
- frozen: false
- not usable for prompt tuning: true
- not usable for glossary tuning: true

## Future 1,020 Request Rule

- pilot_1000_new = 1,000 new segments, disjoint from pilot_75 and pilot_300
- holdout_gold_regression = 20 frozen holdout items intentionally re-included
- total future batch requests = 1,020
- Step 3G-A does not select the 1,000 new segments and does not submit a batch.

## Warnings

- none

## Next Step

Step 3G-B is human adjudication of the holdout candidates and remaining review seeds. No code in this step freezes holdout_gold.

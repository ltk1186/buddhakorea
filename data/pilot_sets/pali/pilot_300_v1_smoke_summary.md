# Pāli 300 Pilot Step 2.5 Live Micro-Smoke

## Purpose
Validate live model / prompt / schema / parser behavior for 3-5 selected segments before any 300 Batch submission.

## Safety Gate
- status: `PASS`
- blocking_reasons: none
- batch_submission_allowed_now: `false`

## Credential Handling
- credential source: environment_variable
- credential present: True
- credential value logged: false

## Sample Selection
- sample_count_requested: 5
- holdout candidates excluded.

## Payload Source
- payload_source: `pilot_300_v1_batch_unsubmitted.jsonl`
- prompt_reassembled: false

## Model / Observed modelVersion
- requested_model: `models/gemini-3.1-pro-preview`
- observed_model_versions: ['gemini-3.1-pro-preview']
- model_version_drift: True

## Schema Validation Result
- schema_valid_count: 5
- schema_invalid_count: 0

## Parse Result
- parse_failed_count: 0

## Token / Cost Result
- actual_usage: {'input_tokens': 17065, 'output_tokens': 5725, 'thinking_tokens': 14524, 'total_tokens': 37314}
- estimated_cost_usd: $0.205228
- actual_cost_usd: $0.138559

## Estimate Divergence
- warnings: model_version_drift

## Budget Status
- budget_usd: $0.50
- under_budget: True

## Limitations
- This smoke validates live model / prompt / schema / parser behavior only.
- It does not validate Gemini Batch submission mechanics.
- Batch submission is a separate path and must still be guarded in Step 3.
- Smoke output is not a translation quality signal and must not be used for glossary/gold/prompt tuning.

## Next Step
Smoke PASS여도 300 Batch 제출은 자동 허용되지 않는다. Step 3에서는 manifest hash, JSONL hash, readiness, budget gate, smoke result를 다시 확인한 뒤 사용자 승인 하에 제출한다.

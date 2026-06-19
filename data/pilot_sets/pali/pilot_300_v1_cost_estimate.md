# Pāli 300 Pilot Cost Estimate

## Purpose
Step 3 제출 전 local-only cost estimate와 preflight gate를 기록한다. Gemini/API/LLM 호출은 없다.

## Manifest Identity
- selection_content_sha256: `06f0d35a7eeebdb23c23fb5dd78bf34739a65abc41ffe45c5311212f6e12cc93`
- inventory_sha256: `0cf74813283ee50ea649dcd14f52eb13fd37f98ca46084cd96c0a3ac09c328ca`
- source_commit: `49bc86914748589a2501b548cc6b3e97a8abe018`

## 75 Actuals Calibration
- input/output/thinking: 242651 / 56043 / 142478
- actual cost: $1.433777

## Pricing Self-Check
- result: {'recomputed_cost_usd': '1.433777', 'actual_cost_usd': '1.433777', 'delta_usd': '0.000000', 'pass': True}

## Cost Estimate
- expected mean official cost: $7.091905
- planning p90 official cost: $8.459241
- conservative gate: $8.459241

## Bucket Backoff Method
Primary bucket is text_layer × length_bucket × chunk_type. If n < 5, the estimator backs off through layer/length, length/chunk, length, layer, then overall.

## Special Slices
- s05: count 116, p90 cost $3.093683
- heading_title_probe: count 5
- hard: count 100
- holdout_candidates: count 20

## Known Limitations
- No countTokens API was called in Step 2.
- Input tokens are estimated from existing calibration and 75 actual prompt usage.
- Output and thinking token p90 use 75 observed bucket ratios, with deterministic backoff where n < 5.
- This is a preflight estimate, not a production cost commitment.

## Next Step
GO 상태여도 Step 3 제출은 사용자 green-light 전까지 금지. Step 3에서는 JSONL hash, manifest hash, budget readiness를 재검증한 뒤 제출한다.

# Pāli 300 Pilot Cost And Local Dry-Run Plan

## Purpose
이 문서는 300 pilot Step 2 local preflight gate의 운영 기준과 산출물을 기록한다.

## Manifest Identity
- selection_content_sha256: `5cc83c232a8a62ea9345132cb66b9e74d6f911d2ff125f8b727ea0537150e705`
- manifest_sha256: `2a6de4a79ae51230c82d0d2bb0b14977cfcb684dea1ead81703c33d5e99dd883`

## 75 Actuals Calibration
75 pilot actual usage에서 output/thinking ratio를 계산하고, prompt/input overhead는 source token proxy와 분리한다.

## Pricing Self-Check
- pass: True

## Cost Estimate
- expected_mean: $4.586552
- planning_p90: $4.714526
- conservative_gate: $5.045906

## Bucket Backoff Method
text_layer × length_bucket × chunk_type bucket이 n < 5이면 parent bucket으로 deterministic backoff한다.

## Bucket Cost Table
상세 bucket stats는 `pilot_300_v1_cost_estimate.json`의 `bucket_stats`를 기준으로 본다.

## Special Slices
- s05: 0
- heading_title_probe: 5
- hard: 95
- holdout_candidates: 20

## Unsubmitted JSONL Validation
- passed: True

## Source Integrity Precheck
- passed: True

## Mock QA Dry-Run Result
- passed: True
- mock QA dry-run is not a translation quality signal.
- gold empty is expected because current gold seeds are disjoint from 300.

## Budget Guardrail Test
- passed: True

## Shard Recommendation
- recommended_shards: 1
- alternative: 2 shards if Step 3 operator wants failure isolation.

## Step 2.5 Live Smoke Plan
- not implemented in Step 2
- separate user approval required
- 3-5 segments only
- hard cap <= $0.50
- generateContent allowed only in Step 2.5

## GO / NO-GO
- readiness_status: `PASS_READY_FOR_USER_APPROVAL`
- GO 상태여도 Step 3 제출은 사용자 green-light 전까지 금지.

## Known Limitations
- No live provider call is made.
- Cost estimate depends on 75 pilot actuals and bucket backoff.
- Correctness quality is not evaluated in mock QA dry-run.

## Next Step
GO 상태여도 Step 3 제출은 사용자 green-light 전까지 금지. Step 3에서는 JSONL hash, manifest hash, budget readiness를 재검증한 뒤 제출한다.

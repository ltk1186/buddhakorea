# Pāli 300 Pilot Cost And Local Dry-Run Plan

## Purpose
이 문서는 300 pilot Step 2 local preflight gate의 운영 기준과 산출물을 기록한다.

## Manifest Identity
- selection_content_sha256: `06f0d35a7eeebdb23c23fb5dd78bf34739a65abc41ffe45c5311212f6e12cc93`
- manifest_sha256: `a79e65e39bf622b7994acc40df5ca7ba30fea392341c3d95d6a3b2b78f72428f`
- inventory_sha256: `0cf74813283ee50ea649dcd14f52eb13fd37f98ca46084cd96c0a3ac09c328ca`
- source_commit: `49bc86914748589a2501b548cc6b3e97a8abe018`

## 75 Actuals Calibration
75 pilot actual usage에서 output/thinking ratio를 계산하고, prompt/input overhead는 source token proxy와 분리한다.

## Pricing Self-Check
- pass: True

## Cost Estimate
- expected_mean: $7.091905
- planning_p90: $8.459241
- conservative_gate: $8.459241
- budget_usd: $20
- Decimal budget gate: PASS_READY_FOR_USER_APPROVAL (`Decimal(str(value))`)

## Bucket Backoff Method
text_layer × length_bucket × chunk_type bucket이 n < 5이면 parent bucket으로 deterministic backoff한다.

## Bucket Cost Table
상세 bucket stats는 `pilot_300_v1_cost_estimate.json`의 `bucket_stats`를 기준으로 본다.

## Special Slices
- s05: 116
- heading_title_probe: 5
- hard: 100
- holdout_candidates: 20

## Unsubmitted JSONL Validation
- passed: True
- request_count: 300
- submitted: False

## Source Integrity Precheck
- passed: True
- checked_count: 300
- mismatches: 0

## Mock QA Dry-Run Result
- passed: True
- report_path: `data/qa_reports/pali/qa_report_300_dryrun/review_report.md`
- mock QA dry-run is not a translation quality signal.
- gold empty is expected because current gold seeds are disjoint from 300.

## Budget Guardrail Test
- passed: True
- synthetic under-budget: True
- synthetic over-budget blocked: True
- actual gate status: PASS_READY_FOR_USER_APPROVAL

## Decimal Budget Parsing
- Cost/readiness JSON의 USD 값은 Decimal-safe string으로 저장될 수 있다.
- 소비자는 `Decimal(str(value))`로 파싱해야 한다.
- 문자열 비교와 float 직접 비교는 금지한다.
- Step 3 제출 직전에는 readiness JSON을 다시 읽고 Decimal budget gate를 재검증한다.

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
- batch_submission_allowed_now: `false`
- requires_user_approval: `true`
- user_approval_received: `false`
- GO 상태여도 Step 3 제출은 사용자 green-light 전까지 금지.

## Known Limitations
- No live provider call is made.
- Cost estimate depends on 75 pilot actuals and bucket backoff.
- Correctness quality is not evaluated in mock QA dry-run.

## Next Step
GO 상태여도 Step 3 제출은 사용자 green-light 전까지 금지. Step 3에서는 JSONL hash, manifest hash, budget readiness를 재검증한 뒤 제출한다.

# Pāli 300 Pilot Step 3A Batch Execution Plan

이 문서는 300개 Pāli segment를 Gemini Batch로 제출하기 위한 실행 harness와 운영 절차를 정의한다. Step 1에서 selection manifest가 고정되었고, Step 2 local preflight와 Step 2.5 live micro-smoke가 통과한 상태를 전제로 한다.

중요: 이 단계의 코드 작성자는 실제 Batch submit, polling, result download를 실행하지 않는다. 실제 API 호출은 사용자가 로컬 Terminal에서 별도 승인 후 실행한다.

## 1. Purpose

Step 3A의 목적은 실제 제출 직전의 safety gate와 실행 경로를 고정하는 것이다.

- Step 2에서 검증된 `pilot_300_v1_batch_unsubmitted.jsonl`을 그대로 사용한다.
- manifest hash, JSONL hash, readiness, smoke result, source integrity, budget cap을 다시 검증한다.
- double-submit 방지 장치를 둔다.
- submit 후 `provider_batch_id`를 즉시 기록해 crash recovery가 가능하게 한다.
- poll, fetch, parse, QA report까지 이어지는 운영 명령을 제공한다.

## 2. No Codex Submit

Codex는 다음을 실행하지 않는다.

- Gemini Batch submit
- Gemini polling
- Gemini result download
- 300개 번역 호출
- 실패분 자동 재제출

Codex가 실행해도 되는 것은 `--mode dry-run`뿐이다. `--mode submit`, `--mode poll`, `--mode fetch`, `--mode full-after-submit`은 사용자의 로컬 Terminal에서만 실행한다.

## 3. Fixed Inputs

필수 입력은 다음이다.

```text
data/pilot_sets/pali/pilot_300_v1_manifest.json
data/pilot_sets/pali/pilot_300_v1_batch_readiness.json
data/pilot_sets/pali/pilot_300_v1_smoke_results.json
data/pilot_sets/pali/pilot_300_v1_batch_unsubmitted.jsonl
data/pilot_sets/pali/pilot_300_v1_batch_unsubmitted_manifest.json
data/pilot_sets/pali/pilot_300_v1_cost_estimate.json
data/pilot_sets/pali/pilot_300_v1_source_integrity_precheck.json
```

고정 hash:

```text
selection_content_sha256 = 06f0d35a7eeebdb23c23fb5dd78bf34739a65abc41ffe45c5311212f6e12cc93
manifest_sha256 = a79e65e39bf622b7994acc40df5ca7ba30fea392341c3d95d6a3b2b78f72428f
inventory_sha256 = 0cf74813283ee50ea649dcd14f52eb13fd37f98ca46084cd96c0a3ac09c328ca
```

## 4. Verified JSONL Reuse

Step 3는 prompt를 다시 조립하지 않는다.

금지:

- `render_korean_advanced_prompt_v1(...)` 재호출
- source text에서 prompt 새로 생성
- glossary 재삽입
- generation config 재구성

허용되는 작업은 Step 2 JSONL line을 Gemini Batch API envelope로 보내는 것뿐이다. 목표는 Step 3에서 제출되는 request body가 Step 2에서 검증된 request body와 동일한 상태를 유지하는 것이다.

## 5. Credential Handling

Gemini credential은 환경변수에서만 읽는다.

허용 환경변수:

```text
GEMINI_API_KEY
GOOGLE_API_KEY
GOOGLE_GENAI_API_KEY
PALI_GEMINI_API_KEY
```

금지:

- `--api-key` CLI 인자
- repo 파일에서 key 읽기
- `.env` 내용 출력
- 환경변수 dump
- API key prefix/suffix/hash 기록

run manifest에는 다음만 기록한다.

```json
{
  "credential_source": "environment_variable",
  "credential_present": true,
  "credential_value_logged": false
}
```

## 6. Pre-Submit Gate

실제 submit은 다음 조건이 모두 통과해야 한다.

- `--mode submit`
- `--enable-submit`
- `--user-green-light`
- Gemini credential present
- 기존 `provider_batch_id` 없음
- submitted sentinel 없음
- `readiness_status == PASS_READY_FOR_USER_APPROVAL`
- Step 2.5 `smoke_status == PASS`
- smoke succeeded count가 3 이상
- smoke schema valid count가 attempted count와 같음
- smoke parse failed count가 0
- Step 2 `batch_submission_allowed_now == false`
- source integrity valid
- JSONL request count가 300
- selection hash가 expected hash와 일치
- JSONL sha256이 JSONL manifest와 일치
- conservative gate cost가 budget 이하
- budget이 20 USD 이하

차단 status:

```text
BLOCKED_SUBMIT_NOT_ENABLED
BLOCKED_USER_GREEN_LIGHT_REQUIRED
BLOCKED_MISSING_GEMINI_CREDENTIAL
BLOCKED_ALREADY_SUBMITTED
BLOCKED_READINESS_NOT_PASS
BLOCKED_SMOKE_NOT_PASS
BLOCKED_SMOKE_SCHEMA_OR_PARSE_FAILURE
BLOCKED_SOURCE_INTEGRITY
BLOCKED_HASH_MISMATCH
BLOCKED_JSONL_HASH_MISMATCH
BLOCKED_JSONL_COUNT_MISMATCH
BLOCKED_OVER_BUDGET
BLOCKED_UNSAFE_BATCH_FLAG
```

`batch_submission_allowed_now`는 Step 2 artifact에서 계속 `false`여야 한다. 실제 제출 허용은 Step 3 CLI의 `--enable-submit --user-green-light` 조합으로만 판단한다.

## 7. Double-Submit Protection

제출 상태는 두 파일에 기록한다.

```text
data/reports/pali/pilot_300_batch/pilot_300_batch_run_manifest.json
data/reports/pali/pilot_300_batch/.pilot_300_v1_batch_submitted.lock
```

submit mode 시작 시 둘 중 하나에 `provider_batch_id`가 있으면 새 submit을 차단한다.

```text
status = BLOCKED_ALREADY_SUBMITTED
instruction = Already submitted. Use --mode poll or --mode fetch with the existing provider_batch_id.
```

submit 성공 직후 처리 순서:

1. pre-submit gate 통과
2. Gemini Batch create 호출
3. `provider_batch_id` 추출
4. run manifest atomic write
5. submitted sentinel atomic write
6. provider status 저장
7. 이후 poll/fetch/parse 진행

이 순서 때문에 submit 직후 process가 crash되어도 `provider_batch_id`가 남고, 같은 batch의 중복 제출을 막을 수 있다.

## 8. Atomic Write And Lock

run manifest와 sentinel은 temp file write 후 rename하는 방식으로 기록한다. submit 중에는 `.pilot_300_v1_batch_submit.in_progress.lock`을 생성해 동시 실행을 줄인다. 이 lock은 provider batch id sentinel과 별도이며, crash recovery의 기준은 run manifest/sentinel의 provider id다.

## 9. Model Version Drift Normalization

Step 2.5 smoke에서 provider가 `gemini-3.1-pro-preview`처럼 `models/` prefix 없는 값을 반환할 수 있다. Step 3 gate는 비교 전에 `models/` prefix를 제거한다.

```python
normalize_model_name("models/gemini-3.1-pro-preview") == "gemini-3.1-pro-preview"
```

prefix 차이만 있는 경우 blocker가 아니다.

## 10. Commands

### Dry-Run

Codex와 운영자 모두 실행 가능하다. 네트워크/API 호출이 없다.

```bash
./venv/bin/python -m backend.pali.scripts.run_pilot_300_batch \
  --mode dry-run \
  --manifest data/pilot_sets/pali/pilot_300_v1_manifest.json \
  --readiness data/pilot_sets/pali/pilot_300_v1_batch_readiness.json \
  --smoke-results data/pilot_sets/pali/pilot_300_v1_smoke_results.json \
  --jsonl data/pilot_sets/pali/pilot_300_v1_batch_unsubmitted.jsonl \
  --jsonl-manifest data/pilot_sets/pali/pilot_300_v1_batch_unsubmitted_manifest.json \
  --cost-estimate data/pilot_sets/pali/pilot_300_v1_cost_estimate.json \
  --source-integrity data/pilot_sets/pali/pilot_300_v1_source_integrity_precheck.json \
  --out data/reports/pali/pilot_300_batch \
  --expected-selection-sha 06f0d35a7eeebdb23c23fb5dd78bf34739a65abc41ffe45c5311212f6e12cc93 \
  --budget-usd 20 \
  --pretty
```

### Submit

사용자 로컬 Terminal에서만 실행한다.

```bash
./venv/bin/python -m backend.pali.scripts.run_pilot_300_batch \
  --mode submit \
  --manifest data/pilot_sets/pali/pilot_300_v1_manifest.json \
  --readiness data/pilot_sets/pali/pilot_300_v1_batch_readiness.json \
  --smoke-results data/pilot_sets/pali/pilot_300_v1_smoke_results.json \
  --jsonl data/pilot_sets/pali/pilot_300_v1_batch_unsubmitted.jsonl \
  --jsonl-manifest data/pilot_sets/pali/pilot_300_v1_batch_unsubmitted_manifest.json \
  --cost-estimate data/pilot_sets/pali/pilot_300_v1_cost_estimate.json \
  --source-integrity data/pilot_sets/pali/pilot_300_v1_source_integrity_precheck.json \
  --out data/reports/pali/pilot_300_batch \
  --expected-selection-sha 06f0d35a7eeebdb23c23fb5dd78bf34739a65abc41ffe45c5311212f6e12cc93 \
  --budget-usd 20 \
  --enable-submit \
  --user-green-light \
  --pretty
```

### Poll

run manifest 사용:

```bash
./venv/bin/python -m backend.pali.scripts.run_pilot_300_batch \
  --mode poll \
  --batch-run-manifest data/reports/pali/pilot_300_batch/pilot_300_batch_run_manifest.json \
  --out data/reports/pali/pilot_300_batch \
  --pretty
```

provider id 복구:

```bash
./venv/bin/python -m backend.pali.scripts.run_pilot_300_batch \
  --mode poll \
  --provider-batch-id "batches/..." \
  --out data/reports/pali/pilot_300_batch \
  --pretty
```

### Fetch

```bash
./venv/bin/python -m backend.pali.scripts.run_pilot_300_batch \
  --mode fetch \
  --batch-run-manifest data/reports/pali/pilot_300_batch/pilot_300_batch_run_manifest.json \
  --out data/reports/pali/pilot_300_batch \
  --pretty
```

provider id 복구:

```bash
./venv/bin/python -m backend.pali.scripts.run_pilot_300_batch \
  --mode fetch \
  --provider-batch-id "batches/..." \
  --out data/reports/pali/pilot_300_batch \
  --pretty
```

### Parse

```bash
./venv/bin/python -m backend.pali.scripts.run_pilot_300_batch \
  --mode parse \
  --batch-run-manifest data/reports/pali/pilot_300_batch/pilot_300_batch_run_manifest.json \
  --out data/reports/pali/pilot_300_batch \
  --pretty
```

### QA

```bash
./venv/bin/python -m backend.pali.scripts.run_pilot_300_batch \
  --mode qa \
  --batch-run-manifest data/reports/pali/pilot_300_batch/pilot_300_batch_run_manifest.json \
  --out data/reports/pali/pilot_300_batch \
  --qa-out data/qa_reports/pali/qa_report_300_live \
  --pretty
```

## 11. Terminal States

```text
SUCCEEDED -> fetch / parse / qa 진행
FAILED -> raw provider status 저장, 재제출 금지, 원인 분석
CANCELLED -> 재제출 금지, 원인 분석
EXPIRED -> 재제출 금지, 별도 rerun plan 작성
RUNNING / PENDING -> poll 재실행
```

run manifest를 잃었으면 `--provider-batch-id`로 poll/fetch를 복구한다. provider id가 있는 상태에서 새 submit을 먼저 실행하지 않는다.

## 12. Result Parsing

fetch 후 parse는 다음을 수행한다.

1. raw provider output 보존
2. response를 stable segment key와 매핑
3. model output JSON parse
4. KoreanAdvancedTranslation schema validation
5. usage metadata 추출
6. actual cost 계산
7. parsed result JSON 생성
8. summary JSON/Markdown 생성

partial failure가 있어도 자동 재제출하지 않는다.

## 13. Partial Failure Handling

부분 실패가 있으면 먼저 전체 artifact를 만든다.

- raw results
- parsed result
- summary
- QA report

그 뒤 실패 유형을 분류한다.

```text
provider_error
parse_failed
schema_invalid
empty_response
safety_blocked
timeout_or_expired
```

실패분 재제출은 Step 3B 또는 별도 rerun plan으로 분리하고 사용자 승인을 받아야 한다.

## 14. Budget

가격 계산:

```text
input_tokens * 1 / 1M + (output_tokens + thinking_tokens) * 6 / 1M
```

Summary에는 expected mean, planning p90, conservative gate, actual usage, actual cost, budget status를 기록한다. actual cost가 conservative gate의 1.5배를 넘으면 warning을 남긴다.

## 15. Output Artifacts

```text
data/reports/pali/pilot_300_batch/pilot_300_batch_dry_run.json
data/reports/pali/pilot_300_batch/pilot_300_batch_submit_plan.md
data/reports/pali/pilot_300_batch/pilot_300_batch_run_manifest.json
data/reports/pali/pilot_300_batch/.pilot_300_v1_batch_submitted.lock
data/reports/pali/pilot_300_batch/pilot_300_batch_provider_status.json
data/reports/pali/pilot_300_batch/pilot_300_batch_raw_results.jsonl
data/reports/pali/pilot_300_batch/pilot_300_batch_parsed.json
data/reports/pali/pilot_300_batch/pilot_300_batch_summary.json
data/reports/pali/pilot_300_batch/pilot_300_batch_summary.md
data/qa_reports/pali/qa_report_300_live/review_report.md
data/qa_reports/pali/qa_report_300_live/run_manifest.json
```

raw results에는 API key, secret, environment dump가 없어야 한다.

## 16. Operational Sequence

1. dry-run 실행
2. dry-run PASS 확인
3. submit 실행
4. `provider_batch_id`가 run manifest에 기록됐는지 확인
5. poll을 terminal state까지 반복
6. `SUCCEEDED`이면 fetch
7. parse
8. qa
9. summary 확인
10. artifact commit/push 여부 결정

## 17. What Not To Do

- Batch를 두 번 제출하지 않는다.
- provider id를 잃었다고 새 submit을 먼저 실행하지 않는다.
- 실패분을 자동 재제출하지 않는다.
- Step 2 JSONL을 다시 생성하거나 prompt를 재조립하지 않는다.
- cost warning을 무시하고 production으로 확대하지 않는다.
- QA report를 최종 정확성 판정으로 취급하지 않는다.

## 18. Next Step

이 문서와 dry-run이 통과하면, 사용자는 로컬 Terminal에서 submit 명령을 실행할 수 있다. submit 후에는 run manifest의 `provider_batch_id`를 먼저 확인하고, poll/fetch/parse/qa 순서로 진행한다.

Pāli Translation Pipeline — 1,000 Pilot까지 최종 수정 로드맵
0. 최종 운영 원칙
이번 국면의 핵심 방향은 다음으로 고정한다.
apparatus-aware translation이 아니라 apparatus-aware QA/review로 간다.
즉 VRI XML <note> apparatus를 번역 시점에 LLM input으로 넣지 않는다. 기존 prompt는 유지한다. notes/apparatus는 번역 후 QA, 리뷰, 독자 주석 후보, internal note로만 사용한다.
확정 원칙:
1. prompt를 다시 열지 않는다.
2. notes/apparatus를 번역 input에 넣지 않는다.
3. main text와 variant note를 섞지 않는다.
4. apparatus evidence는 proof가 아니라 attestation이다.
5. notes가 있다는 이유만으로 자동 수정하지 않는다.
6. notes가 있다는 이유만으로 전부 LLM 재호출하지 않는다.
7. 필요한 소수만 targeted retry 후보로 둔다.
8. glossary/prompt는 1,000 pilot 동안 frozen에 가깝게 유지한다.
9. 1,000 pilot 전 holdout_gold를 동결한다.
10. 1,000 batch에는 신규 1,000개와 holdout_gold 20개를 함께 실행한다.
중요한 구조:
pilot_1000_new = 신규 1,000개
holdout_gold_regression = 기존 300에서 동결한 20개 평가셋
total_batch_requests = 1,020개
신규 1,000개는 기존 75개와 300개와 중복되면 안 된다. 단, holdout_gold 20개는 정확도 회귀 측정을 위해 의도적으로 재포함한다.

Step 3G — Apparatus-Aware Post-hoc Review Harvest + Holdout Gold Freeze
목적
Step 3G의 목적은 네 가지다.
1. Step 3E 이후 남은 12개 remaining human-needed 항목을 구조화한다.
2. Step 3F에서 발견한 source apparatus evidence를 internal note로 연결한다.
3. glossary/reference/table 후보를 수확하되, 아직 적용하지 않는다.
4. Step 1의 holdout 후보 20개를 사람이 판정하여 holdout_gold로 동결한다.
Step 3G는 코드 작업과 사람 판정 작업이 섞여 있다. 반드시 구분해야 한다.
Step 3G-A = 코드 작업
- seed decision ingest
- internal note join
- review queue 생성
- candidate 파일 출력

Step 3G-B = 사람 판정 작업
- holdout 후보 20개 직접 검토
- exact / constraint / reference 기준 작성
- holdout_gold로 freeze
3G-A. 12개 remaining 항목 seed decision ingest
12개 항목의 의미 판단은 Python이 자동 도출하지 않는다. 이미 사람이 판단한 seed decision을 구조화해서 ingest한다.
예시 분류:
apparatus_internal_note
glossary_candidate
reference_table_candidate
low_severity
expert_review_candidate
targeted_retry_candidate
no_action
예시 레코드:
{
  "stable_segment_key": "vri:romn:s0519m.mul:f43a9c761757",
  "seed_decision": "apparatus_internal_note",
  "decision_source": "manual_review_seed",
  "apparatus_classification": "apparatus_attests_variant",
  "blocks_1000_pilot": false,
  "llm_retry_required": false,
  "expert_review_required": false
}
중요:
이 단계는 자동 학술 판단이 아니다.
manual seed decision을 데이터로 보존하는 단계다.
3G-A. apparatus-bearing 세그먼트 internal note 생성
300개 중 source apparatus가 있는 세그먼트를 찾아 internal note로 연결한다.
source apparatus 있음
→ internal note 생성
→ 번역문 유지
→ source 유지
→ prompt 변경 없음
→ LLM 재호출 없음
예시:
{
  "stable_segment_key": "vri:romn:s0519m.mul:f43a9c761757",
  "internal_note_type": "source_variant_apparatus",
  "visibility": "internal",
  "main_reading": "accantadiṭṭhaṃ",
  "variant_reading": "antaṃ niṭṭhaṃ",
  "sigla": ["sī"],
  "apparatus_status": "apparatus_attests_variant",
  "review_policy": "internal_note_only",
  "auto_modify_source": false,
  "auto_modify_translation": false,
  "llm_retry_required": false
}
3G-A. glossary/reference/table candidates 수확
3G에서 발견되는 glossary 후보나 reference table 후보는 저장만 한다.1,000 pilot 전에는 적용하지 않는다.
출력 예시:
glossary_candidates.json
reference_table_candidates.json
term_policy_candidates.json
원칙:
1,000 pilot 동안 glossary frozen.
candidate는 유실되지 않게 저장.
실제 glossary patch는 1,000 pilot 이후 reviewed 단계에서 적용.
3G-A. targeted retry 후보 제한
LLM 재호출 후보는 아주 제한적으로만 뽑는다.
후보 조건:
1. source apparatus 또는 grammar uncertainty가 있고
2. 기존 번역이 의미상 위험해 보이며
3. internal note만으로는 부족하고
4. 사람이 바로 판정하기 어렵고
5. LLM이 검토 보조자로 도움이 될 가능성이 있을 때
정상 범위:
targeted_retry_candidate = 0~2개 정도
실행 위치:
targeted retry는 1,000 batch 본체에 섞지 않는다.
필요하면 별도 소형 targeted review batch로 실행한다.
3G-B. holdout_gold 20개 사람 판정 및 동결
이 단계는 코드가 아니라 사람의 학술 판정 작업이다.
목적:
1,000 pilot에서 번역 정확도를 측정할 고정 평가셋을 만든다.
holdout_gold는 완전한 정답 번역문일 수도 있고, constraint 기반 평가일 수도 있다.
예시 constraint:
- 특정 용어는 반드시 정해진 한국어로 번역되어야 한다.
- 부정 범위가 뒤집히면 fail.
- khandha는 “무더기”로 처리.
- manasikāra는 “마음에 잡도리함” 계열로 처리.
- variant apparatus를 main text처럼 조용히 채택하면 fail.
- literal_ko에서 문법 관계가 드러나야 함.
예시:
{
  "stable_segment_key": "...",
  "pool": "holdout_gold",
  "acceptance_type": "constraint",
  "constraints": [
    {
      "type": "terminology",
      "source_term": "khandha",
      "required_ko": "무더기",
      "forbidden_ko": ["무리"]
    }
  ],
  "do_not_use_for_prompt_tuning": true,
  "frozen": true
}
중요:
holdout_gold는 prompt tuning이나 glossary tuning에 사용하지 않는다.
평가 때마다 재번역해서 회귀 측정에만 사용한다.
Step 3G 출력
data/qa_reports/pali/step_3g_posthoc_review_harvest/
  seed_decisions_ingested.json
  internal_notes.json
  glossary_candidates.json
  reference_table_candidates.json
  targeted_retry_candidates.json
  expert_review_candidates.json
  holdout_gold_frozen.json
  holdout_gold_manifest.json
  step_3g_summary.md
  run_manifest.json
Step 3G 금지
- LLM/API 호출
- 번역문 수정
- source XML 수정
- prompt 수정
- glossary 본체 수정
- holdout_gold를 prompt/glossary tuning에 사용
Step 3G 통과 기준
- 12개 remaining 항목이 모두 seed decision으로 구조화됨
- apparatus-bearing 세그먼트가 internal note로 연결됨
- glossary/reference candidates가 저장됨
- targeted_retry_candidate 수가 제한됨
- holdout_gold 20개가 사람 판정으로 동결됨
- holdout_gold 20개를 1,000 batch에 재포함한다는 manifest rule이 기록됨

Step 3H — Importer Note Preservation
목적
VRI XML <note>를 importer 단계에서 보존한다. 단, main text에 섞지 않는다.
<note>는 source_apparatus metadata로만 저장한다.
해야 할 일
각 segment에 source_apparatus metadata를 추가한다.
예시:
{
  "source_apparatus": [
    {
      "note_type": "variant",
      "raw_note_text": "antaṃ niṭṭhaṃ (sī.)",
      "variant_text": "antaṃ niṭṭhaṃ",
      "sigla": ["sī"],
      "anchor_text": "accantadiṭṭhaṃ",
      "xml_node_path": "...",
      "source_path": "romn/s0519m.mul.xml",
      "auto_apply": false
    }
  ]
}
순수 additive 원칙
바뀌면 안 되는 것:
original_text
stable_segment_key
source_path
xml_node_path
segment boundary
source hash
translation prompt input
추가만 되는 것:
source_apparatus
note_type
variant_text
sigla
citation_refs
anchor_text
evidence_strength_hint
검증
재import 또는 fixture reparse 후 비교한다.
original_text byte 동일
stable_segment_key 동일
segment count 동일
source hash 동일
source_apparatus만 추가됨
출력
docs/translation/PALI_IMPORTER_NOTE_PRESERVATION.md
data/reports/pali/importer_note_preservation_check.json
통과 기준
- source_apparatus metadata 보존
- original_text/stable key/source hash 불변
- citation vs variant 구분 유지
- prompt input 변경 없음
- tests 통과
위치
Step 3H는 1,000 전에 끝내는 것이 바람직하다. 다만 1,000 번역 prompt에 apparatus를 넣는 것은 아니다. 1,000 QA 후처리에서 metadata join을 빠르고 안정적으로 하기 위한 기반이다.

Step 4 — Response Schema Stress Micro-Smoke
목적
300 pilot에서 schema invalid가 발생했기 때문에, 1,000 전에 response_schema 또는 generation config를 검증한다.
단, apparatus와 무관하다.
기존 prompt 유지
apparatus 주입 없음
번역 input 변경 없음
대상
랜덤이 아니라 실패 취약 bucket에서 고른다.
추천 대상:
long tika
long atthakatha
긴 주석문
terms가 많이 나오는 세그먼트
grammar_notes가 길어질 가능성이 큰 세그먼트
verse + prose 혼합
300에서 schema invalid와 유사한 유형
개수:
5~10개
비교
가능하면 두 조건을 비교한다.
A. current config
B. response_schema config
비교 항목:
schema_valid
parse_failed
required fields completeness
literal_ko/natural_ko 내용 손상 여부
terms/notes/list field 정상 여부
output length 변화
thinking token 변화
cost 변화
modelVersion drift
통과 기준
- schema_valid 100%
- parse_failed 0
- required fields 정상
- 번역 내용이 baseline보다 명백히 손상되지 않음
- 비용 변화 허용 범위
- response_schema 채택 여부 명확히 결정
중요
Step 4에서 response_schema config를 채택하면, Step 6 비용 추정은 반드시 그 config 기준으로 다시 계산한다.

Step 5 — Pilot 1,000 + Holdout Selection
목적
1,000개 신규 segment로 scale을 검증하고, holdout 20개로 정확도 회귀를 측정한다.
구성
pilot_1000_new = 신규 1,000개
holdout_gold_regression = 기존 300에서 동결한 20개
total_batch_requests = 1,020개
disjoint 규칙
pilot_1000_new ∩ pilot_75 = empty
pilot_1000_new ∩ pilot_300 = empty
예외:
holdout_gold 20개는 정확도 회귀 측정을 위해 의도적으로 재포함한다.
즉 disjoint 규칙은 신규 1,000개에만 적용한다.
pilot_1000_new 구성 원칙
representative segments
hard cases
long prose
verse
atthakatha
tika
abhidhamma definitions
glossary-risk terms
apparatus-bearing segments
주의:
apparatus-bearing segment를 소량 포함하되 과도하게 oversample하지 않는다.
holdout_gold_regression 태그
holdout 20개는 batch 안에서 명확히 태그한다.
{
  "batch_group": "holdout_gold_regression",
  "exclude_from_scale_metrics": true,
  "include_in_accuracy_metrics": true
}
신규 1,000개는 이렇게 태그한다.
{
  "batch_group": "pilot_1000_new",
  "include_in_scale_metrics": true,
  "include_in_accuracy_metrics": false
}
출력
data/pilot_sets/pali/pilot_1000_v1_manifest.json
data/pilot_sets/pali/pilot_1000_v1_summary.md
data/pilot_sets/pali/pilot_1000_v1_validation.json
data/pilot_sets/pali/pilot_1000_plus_holdout_v1_manifest.json
검증 항목
pilot_1000_new_count = 1000
holdout_gold_regression_count = 20
total_batch_requests = 1020
pilot_75 overlap for new set = 0
pilot_300 overlap for new set = 0
holdout intentional overlap recorded = true
layer distribution
length bucket distribution
chunk type distribution
hard bucket distribution
apparatus-bearing count
deterministic selection hash
holdout_gold hash
통과 기준
- 신규 1,000개 정확히 선택
- holdout 20개 재포함
- 총 1,020 요청 manifest 생성
- disjoint exception이 명시됨
- deterministic hash 기록

Step 6 — Pilot 1,000 + Holdout Cost Estimate & Dry Run
목적
1,020개 batch를 실제 제출하기 전에 비용, JSONL, source integrity, prompt hash, selection hash를 검증한다.
비용 추정 기준
300 실제 결과를 기반으로 bucket-based estimate를 사용한다.
반영 요소:
layer
length bucket
chunk type
hard bucket
300 actual input/output/thinking tokens
Step 4 response_schema config 채택 여부
holdout 20개 추가 비용
예산 cap
초기 가이드:
expected: 약 $27~37
conservative cap: $45
hard stop: $50
최종 cap은 1,020개 manifest 기준으로 다시 산정한다.
dry run 출력
data/reports/pali/pilot_1000_batch/
  pilot_1000_plus_holdout_cost_estimate.json
  pilot_1000_plus_holdout_dry_run.json
  pilot_1000_plus_holdout_unsubmitted.jsonl
  pilot_1000_plus_holdout_preflight.md
통과 기준
request_count = 1020
pilot_1000_new_count = 1000
holdout_gold_regression_count = 20
JSONL valid
source integrity mismatch = 0
selection hash 기록
holdout hash 기록
prompt hash 기록
config hash 기록
budget cap 기록
submitted = false
batch_submission_allowed_now = false
requires_user_approval = true

Step 7 — Pilot 1,000 + Holdout Live Smoke
목적
1,020개 batch 제출 전에 실제 JSONL payload가 API에서 정상 작동하는지 확인한다.
Step 4와 다르다.
Step 4 = response_schema/config 검증
Step 7 = 실제 1,020 JSONL payload 사전검증
방식
1,020 unsubmitted JSONL에서 5~10개 payload를 그대로 추출한다.
절대 prompt를 재조립하지 않는다.
추천 샘플:
- pilot_1000_new에서 long/hard 4~8개
- holdout_gold_regression에서 1~2개
검증 항목:
API success
schema_valid
parse_failed
modelVersion
token usage
cost
credential safety
payload_source = JSONL
prompt_reassembled = false
통과 기준
5~10개 성공
schema_valid 100%
parse_failed 0
budget 내
modelVersion 기록
API key 노출 없음
batch_submission_allowed_now = false

Step 8 — Pilot 1,000 + Holdout Batch Execution
목적
신규 1,000개와 holdout 20개를 함께 실행한다.
total requests = 1,020
실행 전 blocker
반드시 확인:
Step 3G 완료
Step 3H 완료 또는 최소 source_apparatus join 경로 확정
Step 4 response_schema 결정 완료
Step 5 selection PASS
Step 6 dry run PASS
Step 7 live smoke PASS
salvage cascade parse pipeline 자동 통합 완료
user approval 있음
salvage 자동 통합
1,000에서는 수동 salvage 병목을 허용하지 않는다.
파이프라인:
raw result
→ strict parse
→ 실패 시 salvage cascade
→ salvaged parsed output
→ QA
batch 실행 순서
1. pre-submit gate 확인
2. submit
3. provider_batch_id 즉시 저장
4. poll
5. fetch
6. parse + salvage cascade
7. QA
8. findings classifier
9. apparatus/internal notes join
10. holdout_gold evaluation
11. final report
출력
data/reports/pali/pilot_1000_batch/
  pilot_1000_plus_holdout_run_manifest.json
  pilot_1000_plus_holdout_provider_status.json
  pilot_1000_plus_holdout_raw_results.jsonl
  pilot_1000_plus_holdout_parsed.json
  pilot_1000_plus_holdout_parsed_salvaged.json
  pilot_1000_plus_holdout_summary.json
  pilot_1000_plus_holdout_summary.md
  pilot_1000_plus_holdout_salvage_report.md
주의:
raw_results와 provider_status는 민감 정보/large artifact 가능성이 있으므로 commit 정책 별도 확인.
thoughtSignature나 credential-like string이 있으면 commit 금지.

Step 9 — Pilot 1,000 QA + Holdout Accuracy Report
목적
Step 9의 최종 평가는 두 축이다.
1. 운영 안정성
2. 번역 정확도
신규 1,000개와 holdout 20개를 분리해서 보고한다.
9-A. 신규 1,000개 운영 안정성 지표
대상:
batch_group = pilot_1000_new
보고 항목:
schema invalid count
parse failed count
salvage recovered count
QA Priority A/B/C
raw human-needed
effective human-needed
grammar_uncertain
contains_untranslated_pali
glossary conflict
apparatus internal notes count
targeted retry candidates
expert review candidates
cost actual vs estimate
9-B. holdout 20개 정확도 평가
대상:
batch_group = holdout_gold_regression
보고 항목:
holdout_gold total
passed
failed
needs_review
pass_rate
failure categories
failure severity
예시:
{
  "holdout_gold_evaluation": {
    "total": 20,
    "passed": 17,
    "failed": 2,
    "needs_review": 1,
    "pass_rate": 0.85,
    "failures_by_category": {
      "terminology": 1,
      "grammar_scope": 1
    },
    "failures_by_severity": {
      "critical_doctrinal": 0,
      "major_semantic": 1,
      "minor_style": 1
    }
  }
}
severity 기준
pass_rate만으로 production 판단하지 않는다.
실패 severity를 반드시 본다.
critical_doctrinal
- 교리 의미를 크게 왜곡.
- production blocker.

major_semantic
- 문장 의미, 부정 범위, 주체/객체 관계가 크게 틀림.
- 강한 blocker 또는 patch 필요.

terminology
- 핵심 용어 번역 불일치.
- glossary/review 필요.

source_apparatus
- main reading과 variant 처리 문제.
- internal note 또는 reviewer judgment 필요.

minor_style
- 의미는 맞지만 문체/자연스러움 문제.
- production blocker 아님.
production decision
Step 9의 최종 결정은 다음 중 하나다.
A. production text 1개로 진행
B. 1,000 result patch 후 진행
C. glossary/gold 보강 후 재평가
D. targeted retry 소형 batch 필요
E. expert review 먼저 필요
F. prompt/schema 재검토 필요
판단 기준은 단순 pass_rate가 아니라 severity-weighted decision이다.
예시:
pass_rate 90%라도 critical_doctrinal failure가 있으면 blocker.
pass_rate 80%라도 실패가 minor_style 중심이면 진행 가능.
1,000 pilot 성공 기준
1,000 pilot의 성공은 “완벽한 번역 1,000개”가 아니다.
성공 기준:
- batch execution이 안정적
- 비용이 예측 범위 안
- schema/salvage가 감당 가능
- human-needed가 폭발하지 않음
- apparatus/internal note workflow가 작동
- holdout_gold 평가가 가능
- holdout 실패 severity가 감당 가능
- production text로 넘어갈 판단 기준이 생김

전체 순서 요약
Step 3G
Apparatus-Aware Post-hoc Review Harvest + Holdout Gold Freeze
→ 12개 seed decision ingest
→ internal notes 생성
→ glossary/reference candidates 수확
→ holdout_gold 20개 사람 판정으로 동결

Step 3H
Importer Note Preservation
→ <note>를 source_apparatus metadata로 보존
→ original_text/stable_key 불변

Step 4
Response Schema Stress Micro-Smoke
→ 실패 취약 bucket 5~10개
→ current vs response_schema 비교
→ config 채택 여부 결정

Step 5
Pilot 1,000 + Holdout Selection
→ 신규 1,000개는 75∪300과 disjoint
→ holdout_gold 20개는 평가용으로 재포함
→ total requests = 1,020

Step 6
Pilot 1,000 + Holdout Cost Estimate & Dry Run
→ budget cap
→ unsubmitted JSONL
→ request_count = 1,020
→ preflight PASS

Step 7
Pilot 1,000 + Holdout Live Smoke
→ 실제 1,020 JSONL payload에서 5~10개
→ prompt 재조립 금지
→ schema/cost/modelVersion 확인

Step 8
Pilot 1,000 + Holdout Batch Execution
→ submit/poll/fetch
→ parse + salvage 자동
→ QA/classifier/apparatus join
→ holdout evaluation

Step 9
Pilot 1,000 QA + Holdout Accuracy Report
→ 신규 1,000개 운영 안정성 보고
→ holdout 20개 정확도/심각도 보고
→ production 가능 여부 판단

최종 핵심
이번 로드맵의 핵심은 다음이다.
prompt를 더 복잡하게 만들지 않는다.
source metadata를 보존한다.
QA/review workflow를 정교화한다.
holdout_gold로 정확도를 측정한다.
가장 중요한 구조는 이것이다.
1,000 pilot은 사실상 두 개의 시험이다.

1. 신규 1,000개
   → scale, cost, schema, QA, review burden 측정

2. holdout_gold 20개
   → 정확도 회귀 측정
따라서 최종 실행 단위는 1,000개가 아니라 1,020개다.
1,000 new + 20 holdout regression = 1,020 batch requests
이렇게 해야 1,000 pilot이 단순 대량 번역 테스트가 아니라, production 직전의 실질 검증 단계가 된다.

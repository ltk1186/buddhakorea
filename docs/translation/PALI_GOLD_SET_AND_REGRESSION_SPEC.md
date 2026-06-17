# Pāli Gold Set and Regression Spec v0

## Purpose

이 문서는 Buddha Korea Pāli 번역 파이프라인에서 구조적 QA가 잡지 못하는 의미 정확성(correctness)을 추적하기 위한 gold set과 regression harness v0의 기준이다.

현재 기준 Prompt는 `korean_advanced_v1_schemafix_qa_patch_v2`로 고정한다. 이 문서는 Prompt 수정 문서가 아니며, Gemini Batch 제출, generateContent 호출, GPT 호출, DB migration, RAG/embedding, production 번역을 다루지 않는다.

핵심 전제는 다음과 같다.

- schema valid는 정확성을 보장하지 않는다.
- glossary conflict 0도 정확성을 보장하지 않는다.
- 일관성은 정확성의 필요조건일 수 있지만 충분조건은 아니다. 일관되게 틀릴 수 있다.
- solo project에서는 전체 expert review를 전제로 하지 않는다.
- 사람 검수는 risk-based sampling과 high-leverage issue 중심으로 한다.

## Gold Set Pools

Gold set은 하나의 단일 목록이 아니라 목적별 pool로 나눈다.

- `discovery`: pilot에서 발견된 문제를 기록하고 정책화하기 위한 후보 pool이다. 자동 pass/fail보다 관찰과 분류가 중요하다.
- `regression_gold`: 이미 알려진 실패 유형이 다시 나오는지 확인하는 회귀 pool이다. Prompt, glossary, validator, model 변경 전후 비교에 사용한다.
- `holdout_gold`: 모델/Prompt/QA 수정에 노출하지 않는 평가 pool이다. 300 pilot 이후부터 작게 구축한다.

초기 seed는 대부분 `discovery`와 `regression_gold`에 둔다. `holdout_gold`는 현재 단계에서 오염될 위험이 크므로 비워 두거나 최소화한다.

## Gold Entry Schema

`data/gold_set.json`의 각 항목은 다음 필드를 가진다.

- `gold_set_id`: 사람이 추적 가능한 고유 ID.
- `pool`: `discovery`, `holdout_gold`, `regression_gold`.
- `stable_segment_key`: canonical segment identity.
- `source_path`: VRI XML source path.
- `source_text_hash`: canonical source hash, 있으면 기록.
- `source_text`: 검수 대상 Pāli source. VRI 원문 source이므로 저장 가능하다.
- `issue_tags`: `khandha`, `manasikara`, `cross_term`, `uncertainty`, `source_normalization` 등.
- `acceptance_type`: `exact`, `constraint`, `reference`.
- `accepted_literal_ko`: project-adjudicated 직역. 없으면 `null`.
- `accepted_natural_ko`: project-adjudicated 자연역. 없으면 `null`.
- `required_terms`: 반드시 충족해야 하는 `pali`, `ko` pair 목록.
- `forbidden_terms`: 나오면 안 되는 `pali`, `ko` pair 목록.
- `acceptable_variants`: 허용 가능한 변이 목록.
- `rationale`: 프로젝트 내부 판단 근거.
- `external_references`: 외부 병행 번역은 edition/ref locator/divergence note만 저장한다. 보호되는 번역 본문은 저장하지 않는다.
- `difficulty`: `low`, `medium`, `high`.
- `leverage`: `low`, `medium`, `high`.
- `reviewer_type`: `operator`, `internal_buddhist_terms`, `pali_expert`.
- `expert_question_status`: `not_needed`, `queued`, `asked`, `answered`.
- `adjudication_status`: `pending`, `accepted`, `rejected`, `needs_expert`.
- `gold_version`: gold set 자체 version.
- `created_from_pilot`: 예: `pilot75_schemafix`, `pilot75_qa_patch_v2`.

보호되는 외부 번역 본문을 저장하지 않는다. Bodhi, Walshe, Ñāṇamoli 등 외부 번역은 internal divergence reference로만 사용하며, 저장 가능한 것은 edition name, ref locator, divergence category, 짧은 자체 메모뿐이다.

## Acceptance Types

`exact`는 project-adjudicated literal/natural translation과 비교할 수 있는 경우만 사용한다. 현재 v0에서는 남용하지 않는다.

`constraint`는 특정 용어, 금지 역어, ambiguity 처리 여부 같은 구조적 조건을 검사한다. 대부분의 초기 seed는 이 형식이 적합하다.

`reference`는 외부 병행 번역 또는 전문가 검토가 필요한 항목이다. 자동 pass/fail을 하지 않으며, regression 결과는 `escalate`로 보낸다.

## Initial Seed Strategy

초기 seed는 75 pilot에서 실제로 드러난 항목을 중심으로 한다.

- `khandha`: `무더기` 기본, 자연역 첫 출현 보조 `무더기(오온)` 허용, `무리` 회피.
- `manasikāra`: `마음에 잡도리함`, `yoniso manasikāra`는 `여리작의`, `ayoniso manasikāra`는 `비여리작의`.
- `dhīra` / `paṇḍita`: 각각 `슬기로운 이` / `현자`로 구별.
- `uppala` / `paduma`: 각각 `수련/청련` / `연꽃`으로 구별.
- `abbokiṇṇa`: 아직 needs human 계열이다. 확정 역어처럼 주입하지 않는다.
- `anulomika khanti`: 인욕 계열 과잉해석 위험을 확인한다.
- source normalization: `akicchāni`를 `akiccāni`처럼 무언 정규화하지 않는다.

이 seed들은 holdout이 아니라 regression/discovery에 둔다. 이미 알려진 문제를 다시 찾는 것이 목적이기 때문이다.

## Expert Question Queue

Pāli expert는 희소 자원으로 본다. expert에게 전체 검수를 요청하지 않는다.

원칙:

- 한 번에 5~10개 high-leverage 질문만 묶는다.
- 질문은 source text, 가능한 해석 A/B, 왜 production에 영향이 큰지, 현재 project policy를 포함한다.
- 실제 전문가 이름은 repo나 문서에 저장하지 않는다.
- 답변은 project-adjudicated note로 요약하고, 보호되는 외부 번역 본문을 저장하지 않는다.

## Regression Harness v0

Regression harness v0는 고정 eval set을 새 model/prompt/glossary/validator 조합의 결과와 비교한다.

입력:

- 기존 parsed result.
- 새 parsed result.
- `data/gold_set.json`.
- optional QA report.

출력:

- segment별 `before_eval`, `after_eval`.
- verdict: `improved`, `worsened`, `neutral`, `escalate`.
- review queue candidate.

verdict 원칙:

- 이전 fail, 이후 pass: `improved`.
- 이전 pass, 이후 fail: `worsened`.
- 동일한 pass/fail 상태: `neutral`.
- gold가 reference-only이거나 자동 판정 불가: `escalate`.

이 단계에서 LLM 호출은 하지 않는다. 기존 artifact를 read-only로 평가한다.

## Baseline Artifacts

v1.2 baseline은 gitignored `data/reports/`가 아니라 durable commit-target 경로에 둔다.

- `data/gold_set.json`: seed gold set.
- `data/regression_baseline_v1_2.json`: 현재 75 pilot artifacts에 대한 read-only baseline.

이 파일들은 production DB가 아니며, schema 확정 전의 lightweight artifact다.

## Known Limitations

- v0는 semantic correctness를 자동으로 완전히 판정하지 않는다.
- `reference` acceptance는 자동 pass/fail 대상이 아니다.
- context-sensitive term correctness, 예를 들어 `saṅkhāra`의 해당 문맥 적합성은 v0가 판정하지 않는다.
- 외부 번역과의 의미 차이는 사람이 divergence note로 기록해야 한다.

## Out of Scope

- Prompt 수정.
- Gemini Batch 제출.
- generateContent 호출.
- GPT 호출.
- DB migration/write.
- RAG/embedding.
- fuzzy matching.
- production translation.
- 외부 번역 본문 저장.

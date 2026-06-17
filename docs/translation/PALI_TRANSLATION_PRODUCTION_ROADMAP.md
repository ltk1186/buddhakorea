# Pāli Translation Production Roadmap

이 문서는 Buddha Korea Pali Studio의 UI 개발 이전 번역 production 준비 로드맵이다. 현재까지 구축된 VRI XML import, Gemini Batch pilot, Korean Advanced Prompt v1, QA Patch v2, Glossary Infrastructure v1, QA Infrastructure v1.1을 기준으로, 앞으로 어떤 순서로 production 번역을 안전하게 진행할지 정리한다.

이 문서는 구현 문서가 아니라 운영 기준 문서다. 새 코드 작성, Prompt 수정, Gemini/API 호출, DB migration, RAG/embedding, UI 구현은 이 문서의 범위 밖이다.

## 1. Executive Summary

현재까지의 pilot 결과로 “가능한가?”라는 질문은 통과했다. VRI Romanized XML에서 안정적인 segment를 만들고, Gemini 3.1 Pro Preview Batch로 75개 segment를 번역하고, schema validation과 read-only QA 계측까지 수행했다.

이제 핵심 질문은 “어떤 순서로 안전하게, 비용을 통제하며, 품질을 측정하면서 대량 번역할 것인가?”이다.

UI 이전까지 해야 할 일은 네 축으로 나뉜다.

1. **Production pipeline**: segment 선택, routing, shard 계획, Batch 실행, 결과 parsing, version 저장까지 이어지는 production 흐름.
2. **QA measurement pipeline**: schema, validator, glossary, citation, source display, priority queue를 통해 사람이 볼 대상을 줄이는 흐름.
3. **Correctness evaluation pipeline**: 구조적 QA가 보장하지 못하는 의미 정확성을 gold set과 regression harness로 측정하는 흐름.
4. **Cost/risk control pipeline**: token, thinking token, shard budget, retry, human review 시간을 함께 관리하는 흐름.

현재 상태 요약:

- VRI Romanized XML importer가 구현되어 있다.
- `stable_segment_key`와 `source_text_hash` 기반 segment 구조가 확보되어 있다.
- corpus layer는 `mula`, `atthakatha`, `tika`로 구분된다.
- Gemini 3.1 Pro Preview smoke/pilot Batch가 성공했다.
- 현재 Prompt baseline은 `korean_advanced_v1_schemafix_qa_patch_v2`이다.
- QA Patch v2 75-segment pilot 결과: request `75`, succeeded `75`, failed `0`, schema valid `75`, schema invalid `0`, parse failed `0`.
- QA Patch v2 75-segment pilot token/cost: input `242,651`, output `56,043`, thinking `142,478`, actual cost `$1.433777`.
- Glossary Infrastructure v1이 완료되어 `fixed`, `context_variant`, `needs_human` 용어 계층을 분리했다.
- QA Infrastructure v1.1이 완료되어 validator/citation/glossary QA read-only report가 가능하다.
- QA v1.1 baseline for QA Patch v2: cross-term collision `0`, avoid conflict `0`, `contains_untranslated_pali` 14건 전부 allowed 재분류, citation mapping `32/32`.
- 아직 production 번역은 시작하지 않았다.

핵심 운영 원칙:

- Prompt를 계속 만지는 단계는 끝났다. 다음 병목은 Prompt가 아니라 운영, QA, 정확성 평가, 비용 통제다.
- 전체 corpus를 한 번에 번역하지 않는다.
- `mula`, `atthakatha`, `tika`를 동시에 production으로 보내지 않는다.
- 논리적 번역 순서는 문헌 단위로 유지하되, 실제 Batch 제출은 shard 단위로 나눈다.
- 사람은 전체를 검수하지 않는다. 위험한 것과 표본만 본다.
- 구조적 QA만으로 정확성을 보장할 수 없으므로 gold set 정확성 track이 필요하다.
- 모든 번역은 segment 단위 version으로 관리한다.
- 공개 후 독자 피드백으로 segment 단위 개선을 계속한다.
- UI 개발은 이 문서의 범위 밖이지만, 이후 독자용 UI와 관리자/검수용 UI가 필요하다.

## 2. Current Infrastructure Inventory

현재 repo 기준으로 확인된 번역 관련 문서, 모듈, artifact는 다음과 같다.

### 2.1 문서

- `docs/translation/PALI_XML_TRANSLATION_SPEC.md`: VRI XML canonical segment와 token count 설계.
- `docs/translation/PALI_TRANSLATION_WORKFLOW_SPEC.md`: Gemini calibration, Batch workflow, Prompt v1, budget guardrail, smoke/pilot 설계.
- `docs/translation/PALI_GLOSSARY_INFRASTRUCTURE_SPEC.md`: deterministic glossary infrastructure v1.
- `docs/translation/PALI_QA_INFRASTRUCTURE_V1_1.md`: cross-term collision, validator reclassification, citation mapping QA layer.
- `../PALI_STUDIO_INTEGRATION_PLAN.md`: Pali Studio 앱 통합 관련 참고 문서. 이 roadmap의 production 번역 근거 문서가 아니라 UI/backend integration 참고 문서로만 취급한다.

### 2.2 구현 모듈

- `backend/pali/importers/vri_xml.py`: VRI XML importer.
- `backend/pali/translation/prompts.py`: active Prompt baseline과 Korean Advanced schema prompt rendering.
- `backend/pali/translation/schemas.py`: translation schema와 quality flag schema.
- `backend/pali/translation/quality.py`: local deterministic quality flag helper.
- `backend/pali/translation/glossary.py`: deterministic glossary loading, matching, consistency metrics.
- `backend/pali/translation/glossary_qa.py`: read-only QA v1.1 report layer.
- `backend/pali/translation/budget.py`: local budget/cost helper.
- `backend/pali/translation/batch_plan.py`: local Batch JSONL/sidecar planning helper.
- `backend/pali/translation/workflow.py`: workflow skeleton. Production orchestration은 아직 not yet implemented.

### 2.3 Script / artifact pipeline

- `backend/pali/scripts/select_vri_translation_samples.py`: sample selector.
- `backend/pali/scripts/calibrate_gemini_tokens.py`: Gemini countTokens calibration.
- `backend/pali/scripts/calibrate_prompt_v1_tokens.py`: Prompt token calibration.
- `backend/pali/scripts/estimate_gemini_pilot_batch.py`: pilot estimate.
- `backend/pali/scripts/plan_gemini_smoke_batch.py`: smoke Batch JSONL/manifest planner.
- `backend/pali/scripts/plan_gemini_pilot_batch.py`: 75 pilot JSONL/manifest planner.
- `backend/pali/scripts/submit_gemini_smoke_batch.py`: smoke/pilot submitter and parser. Production submitter는 not yet implemented.
- `backend/pali/scripts/count_vri_corpus_tokens.py`: VRI corpus token summary.
- `backend/pali/scripts/apply_gemini_token_calibration.py`: Gemini source token correction report.

### 2.4 Data / reports

`data/reports/pali/`는 gitignored artifact 영역이다. 문서상 참조할 수는 있지만 source of truth로 commit하지 않는다.

확인된 주요 artifact:

- `data/reports/pali/vri_translation_sample_candidates_49bc869.json`
- `data/reports/pali/gemini_token_calibration_49bc869.json`
- `data/reports/pali/gemini_prompt_v1_schemafix_token_calibration_49bc869.json`
- `data/reports/pali/gemini_pilot_75_49bc869_prompt_v1_schemafix_summary.json`
- `data/reports/pali/gemini_pilot_75_49bc869_prompt_qa_patch_v2_summary.json`
- `data/reports/pali/gemini_pilot_75_qa_patch_v2_comparison_49bc869.json`
- `data/reports/pali/gemini_pilot_75_qa_analysis_49bc869.json`
- `data/reports/pali/translation_qa_v1_1_baseline_49bc869.json`

### 2.5 Seed glossary

- `data/controlled_glossary.json`: seed controlled glossary. 대규모 glossary가 아니라 infrastructure seed다.

### 2.6 Not yet implemented

- Production QA report generator CLI.
- Gold set schema and regression harness.
- Translation Memory duplicate-rate estimator.
- Segment routing/preprocessing production module.
- Translation Memory v1.
- Production DB schema and migrations.
- Production Batch orchestration and storage integration.
- Reader feedback and segment re-translation loop.
- Reader UI and admin/review UI.

## 3. Production Readiness Gap

현재 상태는 pilot 성공 단계이지 production readiness 단계가 아니다. 바로 production에 들어가지 않는 이유는 다음과 같다.

1. **QA report generator가 운영 흐름에 완전히 연결되지 않음**  
   `glossary_qa.py`는 read-only report layer를 제공하지만, Batch parsed artifact에서 사람 검수용 priority queue와 representative sample package를 자동 생성하는 production report generator는 아직 not yet implemented다.

2. **Segment routing/preprocessing 미완성**  
   number-only, title-only, citation-only, metadata-only, body prose, verse, commentary/tika prose를 같은 Prompt/Batch 비용으로 처리하면 비용과 품질 모두 불안정하다.

3. **Translation Memory ROI와 구현 미완성**  
   exact duplicate가 어느 정도인지, normalization level별 savings가 있는지 아직 corpus 전체에서 측정되지 않았다.

4. **300/1,000 pilot 미실행**  
   75 pilot은 기술 가능성과 schema 안정성을 확인한 단계다. 300/1,000 pilot 없이는 layer별, 길이별, verse/tika-long별 실패율을 신뢰하기 어렵다.

5. **DB schema production 확정 전**  
   현재는 artifact 중심 실험 단계다. `translation_versions`, `translation_jobs`, `qa_reports`, `gold_set_items`, `reader_feedback` 등 production 저장 구조가 확정되지 않았다.

6. **Gold set 정확성 평가 track 부재**  
   schema valid와 glossary conflict 0은 의미 정확성을 보장하지 않는다. 일관되게 틀릴 수 있다.

7. **Regression harness 부재**  
   Prompt, glossary, model, parser 변경 시 기존 승인본이 개선/악화되는지 자동 비교할 고정 eval set이 없다.

8. **Human review capacity model 부재**  
   Gemini 비용만으로 production feasibility를 판단할 수 없다. Priority A/B/C와 reviewer tier별 검토 시간이 필요하다.

9. **Source integrity check 부재**  
   displayed Pāli source가 VRI XML segment에서 추적 가능한지, raw source와 normalized source가 구분되는지, silent correction이 없는지 검사해야 한다.

10. **Model version contingency 부재**  
    `models/gemini-3.1-pro-preview`는 preview model이다. retire, rename, capability change가 발생할 경우 gold set 재검증과 regression rerun이 필요하다.

## 4. Roadmap Overview

UI 이전까지의 권장 순서는 다음과 같다.

### Step 0 — Roadmap 문서화

- **Purpose**: 현재 상태와 production 이전 개발 순서를 공식화한다.
- **Why this step exists**: pilot 이후 무작정 대량 번역으로 넘어가는 것을 막고, 개발/운영/검수 기준을 맞춘다.
- **Inputs**: 기존 translation docs, pilot artifacts, QA v1.1 baseline.
- **Outputs**: `docs/translation/PALI_TRANSLATION_PRODUCTION_ROADMAP.md`.
- **Implementation scope**: 문서 작성만.
- **Out of scope**: 코드, Prompt, API, DB, UI 변경.
- **Success criteria**: 현재 상태, gap, 단계별 roadmap, risk, UI handoff가 한 문서에 정리된다.
- **Risks**: 문서가 실제 artifact 수치와 어긋날 수 있음.
- **Next dependency**: Gold Set & Regression Harness v0.

### Step 1 — Gold Set & Regression Harness v0

- **Purpose**: 구조적 QA가 잡지 못하는 의미 정확성을 측정한다.
- **Why this step exists**: schema valid와 glossary consistency는 정확성의 충분조건이 아니다.
- **Inputs**: 75 pilot parsed results, QA analysis, representative samples.
- **Outputs**: gold set seed, expected translation/adjudication records, regression diff format.
- **Implementation scope**: 문서와 skeleton 설계. 초기에는 기존 pilot artifact read-only 분석.
- **Out of scope**: LLM 호출, 새 번역 생성, full evaluator 구현.
- **Success criteria**: 10~20개 seed case와 diff/review workflow가 정의된다.
- **Risks**: gold set이 너무 작으면 편향될 수 있음.
- **Next dependency**: Pilot QA Report Generator.

### Step 2 — Pilot QA Report Generator

- **Purpose**: 사람이 볼 대상을 자동으로 줄인다.
- **Why this step exists**: 대량 번역에서 전체 수동 검수는 불가능하다.
- **Inputs**: parsed result JSON, summary JSON, glossary QA report, local validator flags.
- **Outputs**: Priority A/B/C review package, representative samples, reviewer handoff report.
- **Implementation scope**: local deterministic report generator.
- **Out of scope**: UI, DB write, LLM 호출.
- **Success criteria**: 300/1,000/production artifact 모두 같은 report format으로 처리된다.
- **Risks**: flag가 없는 의미 오류를 놓칠 수 있음.
- **Next dependency**: Validator/Citation/Source Display 연결.

### Step 3 — Validator / Citation / Source Display 연결

- **Purpose**: QA signal과 display reference를 안정화한다.
- **Why this step exists**: raw citation/source를 LLM이 임의로 번역하면 citation과 표시가 흔들린다.
- **Inputs**: `glossary_qa.py`, citation mapping table, VRI source metadata.
- **Outputs**: citation display mapping, source display mapping, untranslated target policy.
- **Implementation scope**: backend/display 기준과 deterministic mapper.
- **Out of scope**: UI rendering.
- **Success criteria**: raw citation 보존, display label 생성, mapping coverage report 가능.
- **Risks**: abbreviation coverage가 부족할 수 있음.
- **Next dependency**: TM Duplicate-Rate Estimator.

### Step 4 — Translation Memory Duplicate-Rate Estimator

- **Purpose**: Translation Memory v1 구현 전 ROI를 측정한다.
- **Why this step exists**: 반복구가 많아도 raw hash 기준으로는 duplicate가 낮게 보일 수 있다.
- **Inputs**: VRI canonical segments, source hashes, citation/parser normalization 후보.
- **Outputs**: duplicate-rate report, estimated token savings, implement/defer recommendation.
- **Implementation scope**: read-only corpus analysis.
- **Out of scope**: fuzzy matching, semantic similarity, LLM 호출.
- **Success criteria**: normalization level별 duplicate rate와 savings가 나온다.
- **Risks**: normalization이 과하면 false reuse 위험이 생김.
- **Next dependency**: Segment Routing / Preprocessing.

### Step 5 — Segment Routing / Preprocessing

- **Purpose**: 모든 segment를 같은 방식으로 번역하지 않도록 routing한다.
- **Why this step exists**: title, number, metadata, body prose, verse, tika-long은 비용/품질 profile이 다르다.
- **Inputs**: canonical segments, QA analysis, TM estimator 결과.
- **Outputs**: routing categories, route-level token/cost estimate, skip/deterministic policy.
- **Implementation scope**: deterministic classifier and route manifest.
- **Out of scope**: model downgrade routing, semantic validation.
- **Success criteria**: production batch 전에 route distribution과 cost 재추정 가능.
- **Risks**: 잘못 skip하면 번역 누락이 생김.
- **Next dependency**: TM v1 구현 여부 결정.

### Step 6 — Translation Memory v1

- **Purpose**: 동일 또는 정규화상 동일한 segment를 재번역하지 않는다.
- **Why this step exists**: 비용 절감과 반복구 일관성을 동시에 얻을 수 있다.
- **Inputs**: Step 4 duplicate-rate estimator, Step 5 normalization policy.
- **Outputs**: exact normalized hash 기반 TM policy and optional implementation.
- **Implementation scope**: estimator 결과가 충분할 때만 exact normalized hash TM 구현.
- **Out of scope**: fuzzy TM, embedding, semantic similarity.
- **Success criteria**: TM hit는 Gemini로 보내지 않고 provenance가 보존된다.
- **Risks**: normalization false reuse.
- **Next dependency**: 300-segment Expanded Pilot.

### Step 7 — 300-segment Expanded Pilot

- **Purpose**: 75 pilot에서 나오지 않은 failure mode를 찾는다.
- **Why this step exists**: layer, length, genre, citation-heavy, glossary-heavy case를 더 넓게 봐야 한다.
- **Inputs**: sample selector, routing policy, QA report generator, budget guardrail.
- **Outputs**: 300 parsed result, summary, QA report, cost distribution.
- **Implementation scope**: `mula 100`, `atthakatha 100`, `tika 100` controlled pilot.
- **Out of scope**: production corpus run.
- **Success criteria**: 새 failure mode, token p50/p90, review time estimate, gold set 후보 확보.
- **Risks**: 75 pilot보다 thinking/output token이 높게 나올 수 있음.
- **Next dependency**: 300 Pilot QA & Glossary Expansion.

### Step 8 — 300 Pilot QA & Glossary Expansion

- **Purpose**: 실제 문제를 일으킨 용어만 glossary에 추가한다.
- **Why this step exists**: 대규모 수작업 glossary는 overfitting과 관리 불가능성을 만든다.
- **Inputs**: 300 QA report, reviewer decisions, gold set findings.
- **Outputs**: glossary diff, fixed/context_variant/needs_human candidates, regression additions.
- **Implementation scope**: failure-driven glossary expansion.
- **Out of scope**: 대량 glossary 구축.
- **Success criteria**: glossary 변경이 근거 segment와 review decision을 가진다.
- **Risks**: 소수 pilot에 과적합될 수 있음.
- **Next dependency**: 1,000-segment Controlled Pilot.

### Step 9 — 1,000-segment Controlled Pilot

- **Purpose**: production 직전 리허설.
- **Why this step exists**: production threshold와 review capacity를 수치로 확정해야 한다.
- **Inputs**: updated glossary, QA generator, routing, TM policy, gold set.
- **Outputs**: 1,000 pilot results, production readiness assessment.
- **Implementation scope**: controlled pilot only.
- **Out of scope**: full corpus translation.
- **Success criteria**: proposed threshold 충족 여부와 production 진입 판단 가능.
- **Risks**: tika-long, verse, citation-heavy bucket에서 비용/품질이 악화될 수 있음.
- **Next dependency**: DB Schema Production 확정.

### Step 10 — DB Schema Production 확정

- **Purpose**: artifact 실험에서 production 저장 구조로 전환한다.
- **Why this step exists**: segment versioning, provenance, QA status, feedback loop는 artifact만으로 운영할 수 없다.
- **Inputs**: 1,000 pilot findings, source integrity policy, review workflow.
- **Outputs**: schema design and migration plan.
- **Implementation scope**: schema 확정과 migration 설계. 실제 migration은 별도 승인 후.
- **Out of scope**: 즉시 DB migration 생성.
- **Success criteria**: source, translation, QA, review, feedback provenance가 추적 가능.
- **Risks**: schema를 너무 빨리 확정하면 feedback loop가 막힐 수 있음.
- **Next dependency**: First Text Production.

### Step 11 — First Text Production

- **Purpose**: 전체 corpus가 아니라 첫 문헌 또는 첫 문헌 일부를 production 처리한다.
- **Why this step exists**: 문헌 단위 logical order와 shard 단위 execution을 실제로 검증한다.
- **Inputs**: production schema, routing, QA generator, budget guardrail, review capacity model.
- **Outputs**: first production text machine draft and QA package.
- **Implementation scope**: one prose-heavy text or text subset.
- **Out of scope**: full corpus or simultaneous layer production.
- **Success criteria**: source order, translation versioning, QA, review, cost가 함께 작동한다.
- **Risks**: 첫 문헌 선택이 너무 어려우면 production flow 검증보다 번역 난도가 병목이 됨.
- **Next dependency**: Publish / Feedback / Segment Re-translation Loop.

### Step 12 — Publish / Feedback / Segment Re-translation Loop 준비

- **Purpose**: beta 공개와 segment 단위 개선 흐름을 준비한다.
- **Why this step exists**: 전체 완전 수동 검수를 기다리면 공개가 지연된다.
- **Inputs**: translation_versions, QA status, publication status, reader feedback policy.
- **Outputs**: publication status model, feedback intake policy, retranslation rules.
- **Implementation scope**: workflow and backend policy. UI는 별도 단계.
- **Out of scope**: UI 구현.
- **Success criteria**: high-risk 보류, QA 통과 beta 공개, segment feedback/retranslation이 가능해진다.
- **Risks**: beta translation임을 명확히 표시하지 않으면 사용자 신뢰 리스크가 생김.
- **Next dependency**: UI 개발 handoff 문서.

### Step 13 — UI 개발 handoff 문서 작성

- **Purpose**: 독자용 UI와 관리자/검수 UI 요구사항을 명확히 넘긴다.
- **Why this step exists**: UI는 production data model과 QA workflow를 정확히 반영해야 한다.
- **Inputs**: production schema, QA report format, publication policy, feedback policy.
- **Outputs**: UI handoff spec.
- **Implementation scope**: UI 요구사항 문서.
- **Out of scope**: UI 구현.
- **Success criteria**: reader UI와 admin/review UI에서 필요한 data/API/status가 정리된다.
- **Risks**: UI가 너무 빨리 시작되면 backend/QA model 변경 비용이 커짐.
- **Next dependency**: UI implementation phase.

## 5. Step 1 — Gold Set & Regression Harness v0

Gold set은 구조적 QA가 잡지 못하는 의미 정확성을 측정하기 위한 최소 기준 세트다.

중요한 원리:

- schema valid는 정확성을 보장하지 않는다.
- glossary conflict 0도 정확성을 보장하지 않는다.
- citation mapping 100%도 번역 의미 정확성을 보장하지 않는다.
- 일관되게 틀릴 수 있다.
- 그러므로 human-adjudicated 또는 project-adjudicated gold set이 필요하다.

초기 전략:

- 처음부터 100개를 완벽히 만들지 않는다.
- 기존 75 pilot에서 문제가 드러난 10~20개를 seed로 시작한다.
- 300 pilot 후 50개로 확장한다.
- 1,000 pilot 후 100개로 확장한다.

초기 gold set 후보 유형:

- `khandha`
- `manasikāra`
- `dhīra / paṇḍita`
- `abbokiṇṇa`
- `anulomika khanti`
- `saṅkhāra`
- `dhamma`
- 게송 통사 생략
- citation 포함 주석
- long tika prose
- title/metadata cases
- possible true untranslated Pāli

Regression harness 원리:

- 고정 eval set을 새 prompt/glossary/model로 다시 번역한다.
- 기존 승인본과 diff한다.
- 변경된 segment만 review queue로 보낸다.
- 개선, 악화, 중립 판정을 기록한다.
- model migration 전에는 gold set revalidation을 필수로 한다.

이 단계에서는 LLM 호출을 하지 않는다. 문서와 skeleton 설계만 할 수 있으며, 기존 pilot artifact를 read-only로 사용하는 것은 허용한다.

## 6. Step 2 — Pilot QA Report Generator

Pilot QA Report Generator의 목적은 대량 번역 결과에서 사람이 볼 대상을 자동으로 줄이는 것이다.

운영 원리:

- 사람은 전체를 검수하지 않는다.
- QA report가 high-risk segment와 representative sample을 추출한다.
- random sample은 flag가 없는 오류를 찾기 위해 필요하다.
- verse, tika, long segment sample은 구조적으로 실패 가능성이 높은 계층을 감시하기 위해 필요하다.
- 이 기능은 75개 pilot에서 끝나는 기능이 아니라 300/1,000/production 전체에 적용되어야 한다.

Priority A:

- `schema_invalid`
- `parse_failed`
- `possible_true_untranslated_pali`
- `glossary_conflict`
- `avoid_ko_conflict_candidate`
- `cross_term_collision_review`

Priority B:

- `grammar_uncertain`
- `doctrinal_risk`
- `low_confidence`
- `needs_human_glossary_review`
- `unexpected_variant`

Priority C:

- random sample
- long segment sample
- verse sample
- tika sample
- title sample
- citation-heavy sample

필수 output:

- review queue JSON
- human-readable MD/HTML report
- layer/length/chunk/source_path distribution
- flag counts
- representative sample package
- estimated review time by priority

Out of scope:

- UI 구현
- DB write
- LLM arbitration

## 7. Step 3 — Validator / Citation / Source Display 연결

목적은 QA signal과 사용자 표시 정보를 안정화하는 것이다.

포함 범위:

1. `contains_untranslated_pali` reclassification
2. citation display mapping
3. composite citation parsing
4. source display mapping
5. untranslated citation target 처리

운영 원칙:

- raw source와 raw citation은 보존한다.
- display label은 별도로 생성한다.
- LLM에게 citation 번역을 맡기지 않는다.

예:

- raw: `dī. ni. aṭṭha. 2.95`
- display: `디가 니까야 주석 2.95`

Untranslated citation target 처리:

- citation 대상 문헌이 아직 번역되지 않은 경우 raw citation은 보존한다.
- display label은 표시한다.
- link는 disabled 또는 Pāli-only target으로 연결한다.
- “아직 번역되지 않음” 상태 표시가 가능해야 한다.

UI 구현은 하지 않는다. 이 단계는 backend/display mapping 기준을 정하는 단계다.

## 8. Step 4 — Translation Memory Duplicate-Rate Estimator

목적은 Translation Memory v1을 구현하기 전에 ROI를 측정하는 것이다.

배경:

- 75 pilot에서는 exact duplicate가 거의 없을 수 있다.
- VRI 반복구는 citation, locator, punctuation, peyyāla 때문에 raw hash가 다르게 보일 수 있다.
- TM을 구현하기 전, normalization별 duplicate rate와 estimated token savings가 필요하다.

측정할 normalization levels:

1. raw exact
2. whitespace normalized
3. punctuation normalized
4. citation stripped
5. citation + locator stripped
6. peyyāla normalized
7. citation + peyyāla normalized

출력:

- corpus 전체 duplicate rate
- layer별 duplicate rate
- length bucket별 duplicate rate
- estimated token savings
- high-repeat candidate examples
- recommendation: implement now / defer / implement limited

금지:

- fuzzy matching
- semantic similarity matching
- LLM 호출

이 단계는 read-only 분석만 수행한다.

## 9. Step 5 — Segment Routing / Preprocessing

목적은 모든 segment를 같은 방식으로 번역하지 않도록 routing하는 것이다.

Routing categories:

- `skip`
- `deterministic`
- `light_prompt`
- `heavy_prompt`
- `needs_manual_policy`
- `already_translated_by_tm`

예시:

- `skip`: blank-only, metadata-only, source body 없는 note-only.
- `deterministic`: number-only, page marker, simple structural label.
- `light_prompt`: title-only, short heading, section heading.
- `heavy_prompt`: normal body prose, verse, commentary prose, tika prose, doctrinal analysis.

목표:

- 비용 절감
- 품질 안정화
- title/number 이상치 제거
- production cost 재추정 가능화

주의:

- Gemini Flash로 routing하는 방안은 이 roadmap의 기본 전략이 아니다.
- 비용 최적화의 1차 수단은 skip/deterministic/light/heavy Pro routing과 TM이다.
- 잘못 skip하면 번역 누락이 생기므로 source integrity check가 필요하다.

## 10. Step 6 — Translation Memory v1

목적은 동일 또는 정규화상 동일한 segment를 재번역하지 않는 것이다.

원칙:

- v1은 exact normalized hash만 사용한다.
- fuzzy matching은 금지한다.
- citation normalization은 Step 3/Step 4의 공용 parser를 재사용한다.
- TM hit는 Gemini로 보내지 않는다.
- `prompt_version`, `glossary_version`, `model_version` compatibility를 고려한다.

구현 여부:

- Step 4 estimator 결과에 따라 결정한다.
- TM hit rate가 낮으면 production 이후로 미룰 수 있다.
- TM hit rate가 의미 있으면 300 pilot 전에 구현한다.

필수 provenance:

- original source hash
- normalized source hash
- prompt version
- glossary version
- model name
- provider
- source artifact version
- translation version copied from TM

## 11. Step 7 — 300-segment Expanded Pilot

목적은 75 pilot에서 나오지 않은 실패 유형을 발견하는 것이다.

샘플 설계:

- `mula`: 100
- `atthakatha`: 100
- `tika`: 100

각 layer 안에서 가능한 한 균형 있게 포함한다:

- short
- medium
- long
- prose
- verse
- title
- body
- citation-heavy
- glossary-heavy
- source-layer 다양성

목표:

- 새 failure mode 발견
- glossary 확장 후보 발견
- QA report generator 검증
- routing 검증
- token/cost p50/p90 수집
- human review time 추정 시작
- gold set 확장 후보 수집

주의:

- 300 pilot은 production이 아니다.
- 300 pilot 후 바로 corpus 전체로 가지 않는다.
- 300 pilot 결과는 glossary expansion과 routing correction에 사용한다.

## 12. Step 8 — 300 Pilot QA & Glossary Expansion

목적은 300 pilot에서 실제 문제를 일으킨 용어만 glossary에 추가하는 것이다.

원칙:

- glossary를 대량 수작업 구축하지 않는다.
- 실제 failure-driven expansion만 한다.
- `fixed`, `context_variant`, `needs_human`, `avoid_ko`, `cross_avoid`로 분류한다.

산출물:

- glossary diff
- new fixed candidates
- new context_variant candidates
- needs_human / pending_standardization candidates
- avoid_ko additions
- cross_avoid additions
- gold set additions
- regression cases

다음 단계 진입 조건:

- 신규 glossary entry가 근거 segment와 review decision을 가진다.
- regression case가 gold set에 반영된다.
- 300 pilot에서 발견된 high-risk failure가 1,000 pilot 전에 처리된다.

## 13. Step 9 — 1,000-segment Controlled Pilot

목적은 production 직전 리허설이다.

측정 항목:

- schema valid rate
- parse fail rate
- QA flag rate
- possible true untranslated rate
- glossary conflict rate
- cross collision rate
- citation mapping coverage
- routing distribution
- TM hit rate
- input/output/thinking token p50/p90
- estimated vs actual cost
- human review time per priority bucket
- gold set correctness
- regression harness result

중요:

- 비용 추정은 평균뿐 아니라 p90 기준으로 한다.
- `tika-long`, verse, citation-heavy segment는 별도 bucket으로 본다.
- production threshold는 이 단계 후 확정한다.

Production 진입 조건은 1,000 pilot 후 확정한다. 현재 proposed threshold 예시는 다음과 같다.

- schema valid >= 99%
- parse fail <= 1%
- high-risk QA manageable
- possible_true_untranslated_pali very low
- gold set correctness 기준 충족
- regression no major degradation
- p90 cost estimate within acceptable budget
- human review capacity model 확보
- source integrity check 설계 완료
- model version contingency 문서화

이 수치는 proposed threshold이며, 1,000 pilot 후 확정한다.

## 14. Step 10 — DB Schema Production 확정

목적은 artifact 기반 실험에서 production 저장 구조로 전환하는 것이다.

필수 개념:

- source integrity
- translation versioning
- model/prompt/glossary provenance
- batch/job tracking
- reader feedback
- review queue

핵심 테이블 후보:

- `literatures`
- `segments`
- `translation_jobs`
- `translation_batches`
- `translation_job_items`
- `translation_versions`
- `glossary_entries`
- `glossary_observations`
- `qa_reports`
- `gold_set_items`
- `regression_runs`
- `reader_feedback`

필수 필드 원칙:

- `stable_segment_key`
- `source_text_hash`
- `raw_source_text_hash` if applicable
- `normalized_source_text_hash`
- `source_path`
- `edition_ref`
- `segment_order`
- `prompt_version`
- `glossary_version`
- `model_name`
- `provider`
- `generation_config`
- `provider_batch_id`
- `translation_status`
- `qa_status`
- `publication_status`

Source integrity check:

- displayed Pāli source must be traceable to imported VRI XML segment.
- raw source and normalized source must be distinguished.
- no silent source correction.
- source normalization notes must be recorded.

Model version contingency:

- preview model retirement scenario.
- forced model migration.
- gold set revalidation.
- regression rerun before model switch.

이 단계에서 migration을 바로 만들지 않는다. schema 확정과 migration plan을 작성한 뒤 별도 승인으로 진행한다.

## 15. Step 11 — First Text Production

목적은 전체 corpus가 아니라 첫 문헌 또는 첫 문헌 일부를 production으로 처리하는 것이다.

전략:

- logical order: 문헌 단위
- execution: shard 단위
- storage: `segment_order`와 `stable_segment_key`로 재결합

주의:

- `mula`부터 시작하되 “mula = always easy”라고 가정하지 않는다.
- 게송 중심 문헌은 어렵다.
- Suttanipāta, Dhammapada, Theragāthā, Therīgāthā는 별도 전략이 필요하다.

첫 production 후보:

- Dīgha Nikāya 산문 일부
- Sīlakkhandhavagga
- 접근 쉬운 prose-heavy sutta
- 또는 작은 산문 중심 문헌

Dhammapada 등 게송 중심 대중 콘텐츠는 별도 전략으로 다룬다.

Atthakathā 번역 전 원칙:

- 해당 `mula` 번역에서 glossary observations를 harvest한다.
- lemma/quoted source relationship을 확인한다.
- `mula` 번역어를 주석 번역의 기준으로 사용한다.

첫 production 진입 전 필수 조건:

- 1,000 pilot 결과 승인.
- production DB schema 확정.
- QA report generator와 review queue 준비.
- source integrity check 준비.
- budget cap과 shard cancellation policy 확인.

## 16. Step 12 — Publish / Feedback / Segment Re-translation Loop

목적은 전체 완전 수동 검수를 기다리지 않고, 자동 QA 통과본을 beta 공개하고 피드백으로 개선하는 것이다.

Publication statuses:

- `machine_draft`
- `qa_checked`
- `sample_reviewed`
- `beta_published`
- `published`
- `needs_revision`
- `superseded`

운영 원칙:

- high-risk flag가 있는 segment는 공개 보류 또는 warning을 사용한다.
- QA 통과 segment는 beta 공개 가능하다.
- 독자 피드백은 segment 단위로 받는다.
- 수정은 `translation_versions`로 누적한다.
- 기존 번역은 `superseded` 처리한다.
- 재번역은 필요한 segment만 수행한다.

주의:

- “AI 초벌 번역이며 지속적으로 개선 중”임을 명확히 표시하는 정책이 필요하다.
- UI 구현은 후속 문서에서 다룬다.

## 17. Human Review Capacity Model

Gemini 비용뿐 아니라 인간 검토 시간이 production 병목이다. 사람 검토는 전체 검수가 아니라 risk-based sampling이다.

Review tiers:

- **Tier 0 — automated QA only**: schema, validator, glossary, citation, routing, cost checks.
- **Tier 1 — non-specialist operator review**: 명백한 한국어 문제, formatting, citation display, untranslated Pāli candidate, broken JSON/rendering.
- **Tier 2 — trained internal Buddhist terminology review**: glossary conflict, known doctrinal term, cross-term collision, needs_human/pending_standardization candidate.
- **Tier 3 — Pāli expert review**: genuinely ambiguous Pāli, difficult verse, rare commentary/tika passage, source integrity dispute, gold set adjudication.

측정 항목:

- segments per hour by tier
- review minutes per Priority A/B/C
- expected review hours per 1,000 segments
- expected expert hours per text
- review bottleneck risk
- policy for proceeding without full expert review

운영 정책:

- Priority A는 반드시 검토한다.
- Priority B는 trained reviewer 중심으로 검토하되, volume에 따라 sampling을 허용한다.
- Priority C는 random/stratified sampling으로 처리한다.
- Tier 3는 bottleneck이므로 gold set, rare ambiguity, source dispute에 집중한다.

TBD:

- 각 tier별 실제 review speed.
- 1,000 segment당 예상 review hours.
- Tier 3 expert availability.

## 18. Correctness vs Consistency

일관성은 정확성의 필요조건일 수 있지만 충분조건은 아니다. 일관되게 틀릴 수 있다.

Consistency metrics:

- glossary conflict
- avoid_ko
- cross-term collision
- untranslated Pāli
- citation coverage
- schema validity

Correctness metrics:

- gold set accuracy
- human adjudication
- regression diff
- source integrity
- context-sensitive term correctness

운영 의미:

- consistency 0 conflict는 “검토할 구조적 문제를 줄였다”는 뜻이지 “번역이 정확하다”는 뜻이 아니다.
- correctness는 gold set과 human adjudication이 있어야 측정된다.
- `saṅkhāra`, `dhamma`, `khanti` 같은 context_variant는 허용 variant 안에 있어도 해당 문맥에 정확한지 별도 판단이 필요하다.

## 19. Cost Model

Production cost는 Gemini API 비용만이 아니다.

비용 구성:

- Gemini input token
- Gemini output token
- Gemini thinking token
- p50/p90 by layer/length/type
- shard budget cap
- retry cost
- human review cost/time
- retranslation cost
- model migration cost

현재 확인된 QA Patch v2 75 pilot 수치:

- request: `75`
- actual input tokens: `242,651`
- actual output tokens: `56,043`
- actual thinking tokens: `142,478`
- actual cost: `$1.433777`

주의:

- production cost는 routing/TM/300/1,000 pilot 이전에 확정하지 않는다.
- 평균 cost만 보지 않는다. p90 기준을 봐야 한다.
- thinking token underestimation은 주요 리스크다.
- tika-long과 verse는 별도 cost bucket으로 추적한다.
- human review time은 Gemini cost와 별도로 추정한다.

## 20. Risk Register

| Risk | Impact | Mitigation |
|---|---|---|
| consistent but wrong translations | 일관되게 틀린 번역이 production으로 들어감 | gold set, regression harness, Tier 2/3 review |
| over-reliance on schema validity | schema valid를 품질 보증으로 오해 | Correctness vs Consistency 원칙 문서화 |
| preview model retirement | Gemini 3.1 Pro Preview 사용 불가 | model version contingency, gold set rerun |
| human expert bottleneck | 검수 지연 | risk-based sampling, tier model |
| source text normalization drift | source와 번역 provenance 깨짐 | source integrity check |
| citation target missing/untranslated | 링크/표시 혼란 | raw citation 보존, display mapping, disabled/Pāli-only target |
| glossary overfitting | pilot에만 맞춘 용어 정책 | failure-driven expansion, review lifecycle |
| fuzzy TM false reuse | 다른 문맥 번역 재사용 | v1 fuzzy 금지, exact normalized hash only |
| shard failure | Batch 일부 실패 | shard size cap, retry policy, failure isolation |
| cost underestimation from thinking tokens | 예산 초과 | p90 thinking tracking, pilot-based estimate |
| verse difficulty underestimation | 게송 번역 품질 저하 | verse bucket, gold set, expert review |
| tika-long cost explosion | 장문 복주석 비용 급증 | routing, shard cap, p90 tracking |
| user trust risk from beta translation | AI 번역 신뢰 문제 | beta label, feedback loop, publication status |

## 21. UI Handoff Notes

UI 구현은 이 문서의 범위 밖이다. 그러나 후속 UI 개발에 필요한 요구사항은 남겨야 한다.

독자용 UI 필요:

- `natural_ko` 중심 읽기
- `literal_ko` toggle
- Pāli original toggle
- terms/notes expandable
- citation display
- source reference display
- segment-level feedback
- publication status 표시
- beta/AI draft disclosure

관리자/검수 UI 필요:

- QA priority queue
- gold set view
- regression diff view
- translation version history
- glossary observation view
- segment retranslation trigger
- publication status control
- source integrity warning
- citation mapping review

UI handoff 전 필요한 backend/data 준비:

- stable display reference
- translation version model
- QA report format
- review priority taxonomy
- reader feedback schema
- publication status policy

## 22. Final Recommended Sequence

권장 실행 순서:

1. Roadmap 문서화.
2. Gold Set & Regression Harness v0.
3. Pilot QA Report Generator.
4. Validator/Citation/Source Display 연결.
5. TM Duplicate-Rate Estimator.
6. Segment Routing / Preprocessing.
7. TM v1 여부 결정 및 구현.
8. 300 Expanded Pilot.
9. 300 QA + Glossary Expansion.
10. 1,000 Controlled Pilot.
11. DB Schema Production 확정.
12. First Text Production.
13. Publish/Feedback Loop 준비.
14. UI Roadmap 작성.

Production 전 반드시 확보해야 할 것:

- gold set과 regression harness
- QA report generator
- source display/citation mapping
- routing/preprocessing
- TM 여부 판단
- 300/1,000 pilot 결과
- production DB schema
- human review capacity model
- source integrity check
- model version contingency

최종 판단 기준:

- production은 “번역이 가능하다”가 아니라 “측정, 중단, 재시도, 검수, 공개, 개선이 segment 단위로 통제된다”가 확인된 뒤 시작한다.

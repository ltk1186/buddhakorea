# Pāli Model Migration Playbook

## Purpose

이 문서는 Buddha Korea Pāli 번역 파이프라인이 `models/gemini-3.1-pro-preview` 같은 preview model에 의존할 때, model string 변경이나 model retirement가 발생하면 어떻게 안전하게 전환할지 정의한다.

현재 baseline Prompt는 `korean_advanced_v1_schemafix_qa_patch_v2`이며, 이 문서는 Prompt 수정 문서가 아니다.

## When Migration Is Needed

- provider가 현재 model string을 retire한다.
- same model name의 behavior가 silent drift를 보인다.
- countTokens 결과나 usage_metadata 구조가 바뀐다.
- schema valid rate 또는 QA flag rate가 갑자기 악화된다.
- 비용 구조가 크게 바뀐다.

## Pre-Migration Freeze

모델 전환 전에는 다음을 고정한다.

- Prompt version.
- glossary version.
- sample set.
- generation_config.
- source artifacts.
- gold set version.

하나만 바꿔야 원인을 해석할 수 있다.

## Discovery and Smoke

1. Pro 계열 model string만 조회한다.
2. Flash 계열 fallback은 번역 품질 baseline으로 쓰지 않는다.
3. countTokens smoke test를 먼저 수행한다.
4. generateContent 또는 Batch submit은 별도 승인 전 금지한다.

## Silent Drift Canary

정기적으로 작은 canary set을 사용한다.

Canary 후보:

- khandha.
- manasikāra.
- dhīra/paṇḍita.
- uppala/paduma.
- abbokiṇṇa.
- anulomika khanti.
- verse.
- long tika prose.
- citation-heavy commentary.

Canary는 model drift detection용이며 production 번역을 대체하지 않는다.

## Migration Procedure

1. model discovery.
2. countTokens calibration.
3. 3~5 smoke Batch.
4. 75 same-segment A/B pilot.
5. gold set regression.
6. QA report comparison.
7. cost delta comparison.
8. human review of worsened/escalate items.
9. migration decision.

## Decision Rules

Adopt candidate model only if:

- schema valid rate가 baseline보다 나빠지지 않는다.
- gold regression `worsened`가 허용 가능한 수준이다.
- high-risk QA signal이 증가하지 않거나 원인이 설명된다.
- cost p90가 budget guardrail 안에 있다.
- source integrity와 usage metadata 수집이 유지된다.

Reject or defer if:

- silent source normalization이 증가한다.
- glossary/cross-term 문제가 증가한다.
- output이 장황해져 human review 부담이 커진다.
- thinking tokens가 통제 불가능하게 증가한다.

## Rollback

모델 전환은 translation version provenance에 기록되어야 한다.

Rollback 기준:

- 새 model batch에서 production QA fail 증가.
- canary regression worsened.
- 비용 초과.
- provider API instability.

Rollback은 이전 model/prompt/glossary version으로 신규 batch 제출을 중단하고, 이미 생성된 결과는 `needs_review` 또는 `superseded` 후보로 둔다.

## Out of Scope

- Flash를 번역 baseline으로 채택.
- GPT fallback 자동화.
- DB migration.
- Prompt 재작성.
- production batch 자동 재실행.

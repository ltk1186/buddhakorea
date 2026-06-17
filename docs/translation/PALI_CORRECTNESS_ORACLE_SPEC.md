# Pāli Correctness Oracle Spec

## Purpose

이 문서에서 `oracle`이라는 단어는 정답기를 뜻하지 않는다. 정확한 의미는 correctness triage amplifier, 즉 불일치 감지기다.

반드시 다음 원칙을 유지한다.

- oracle 일치 = 정답 확정 아님.
- oracle 불일치 = 오역 확정 아님.
- oracle 불일치 = review queue로 escalate.
- 전체 세그먼트 전수 검증 금지.
- flagged subset에만 적용.
- live API 호출은 이번 단계에서 금지.

현재 baseline prompt는 `korean_advanced_v1_schemafix_qa_patch_v2`로 고정한다.

## Tier 1: CC0 Parallel Candidates

SuttaCentral/Bilara published branch의 CC0 번역 후보, 특히 Sujato 계열 mula 평행본은 자동 대조 가능성이 있다.

단, 구현 전 반드시 확인해야 한다.

- 실제 coverage.
- license metadata.
- repo / branch / file path.
- source commit 또는 provenance pin.
- 저장 가능한 데이터 범위.

문서와 코드에서는 4부 니까야 전체가 확실히 있다고 단정하지 않는다. coverage/license/provenance 확인 후 사용한다.

`source_type = cc0_storable`은 자동 대조 가능 후보일 뿐이다. live comparison은 별도 사용자 green-light 전까지 금지한다.

## Tier 2: Copyright Eyes-Only References

비구 보디, 월시, 냐나몰리 등 보호 번역본은 눈으로만 spot-check한다.

금지:

- 본문 저장.
- 본문 복제.
- 자동 비교.
- fetch.
- repo 산출물에 보호 번역문 저장.
- report에 보호 번역문 인용.

허용:

- edition name.
- ref locator.
- operator-written divergence note.
- divergence category.

`source_type = copyright_eyes_only`는 자동 비교 후보가 아니다.

## Tier 3: No Parallel Available

aṭṭhakathā / ṭīkā 대부분은 신뢰할 평행 번역본이 없다고 가정한다. 제외하지 않고 `oracle_unavailable`로 표시한다.

평행본이 없는 경우 2차 모델 judge를 correctness triage 보조 장치로 설계할 수 있다. 그러나 2차 모델도 정답자가 아니다.

- 일치 = 정답 확정 아님.
- 불일치 = 오역 확정 아님.
- 불일치 = Priority B 또는 escalate signal.

이번 단계에서는 live 호출 금지이며, `backend/pali/translation/second_model_verifier.py`는 `enabled=False`가 기본이다. `enabled=True`는 명시적 guard로 막는다.

## Review Queue Mapping

- `second_model_disagreement` → Priority B.
- `cc0_parallel_disagreement` → Priority B.
- `cc0_parallel_disagreement` + `second_model_disagreement` → `high_divergence_candidate`.
- `high_divergence_candidate`는 Priority A 또는 Priority B 상단으로 올릴 수 있다.

그래도 오역 확정이 아니라 검토 우선순위 상승일 뿐이다.

## Cost Control

Correctness triage는 flagged subset에만 적용한다.

전수 검증 금지 이유:

- 비용 폭주.
- false positive 증가.
- 검수 queue 폭발.
- triage signal을 correctness score로 오해할 위험.

## Source Type Enum

Reference registry는 다음 `source_type`만 허용한다.

- `cc0_storable`: 자동 대조 가능 후보. 실제 사용 전 coverage/license/provenance 확인 필요.
- `copyright_eyes_only`: 눈으로만 확인. 본문 저장/복제/자동 비교 금지.
- `unknown_unverified`: license/coverage 미확인. 자동 대조 금지. safe default.

## Out of Scope

- live CC0 comparison.
- live second-model verification.
- external protected translation text storage.
- automatic EN-KO comparison.
- fuzzy matching.
- semantic similarity matching.
- RAG/embedding.
- production correctness score 산정.

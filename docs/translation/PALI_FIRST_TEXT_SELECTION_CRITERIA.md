# First Text Production Selection Criteria

## Purpose

첫 production 번역 대상은 전체 corpus가 아니라 하나의 문헌 또는 문헌 일부여야 한다. 이 문서는 UI 이전 production 준비 단계에서 첫 텍스트를 고르는 기준을 정한다.

## Principles

- `mula`, `atthakatha`, `tika`를 동시에 production으로 보내지 않는다.
- 논리적 순서는 문헌 단위로 유지하되, Batch 실행은 shard 단위로 나눈다.
- 첫 production은 성공 가능성과 학습 가치의 균형을 본다.
- 대중성이 높다는 이유만으로 게송 중심 난해 문헌을 먼저 선택하지 않는다.

## Weighted Criteria

후보 문헌은 다음 기준으로 평가한다.

- prose ratio: 산문 비중이 높을수록 초기 production에 유리하다.
- segment count: 너무 크면 첫 production 위험이 높다.
- average length and p90 length: long/tika-heavy 비용 폭주 위험.
- citation density: citation mapping 미완성 시 위험.
- glossary risk: known problematic terms 밀도.
- verse difficulty: 게송 통사 생략이 많으면 위험.
- external locator support: 외부 병행 번역 본문이 아니라 edition/ref locator가 있는지.
- reader value: 독자에게 바로 가치가 있는지.
- source display clarity: 문헌명/주석 계층 표시가 가능한지.

## Exclusions for First Production

다음은 첫 production 후보로 신중히 다룬다.

- Dhammapada.
- Suttanipāta.
- Theragāthā.
- Therīgāthā.
- verse-heavy Khuddaka texts.
- long tika prose-heavy 문헌.
- source display mapping이 불명확한 주석/복주석 묶음.

이 문헌들이 중요하지 않다는 뜻이 아니다. 첫 production에서 실패 유형이 겹칠 가능성이 높다는 뜻이다.

## Shortlist Template

각 후보는 다음 형식으로 기록한다.

- `candidate_id`
- `source_path_scope`
- `pitaka`
- `nikaya`
- `text_layer`
- `book_title_pali`
- `book_title_ko`
- `segment_count`
- `prose_ratio`
- `verse_ratio`
- `citation_density`
- `known_glossary_risk`
- `estimated_input_tokens_p90`
- `estimated_output_tokens_p90`
- `review_burden_estimate`
- `external_reference_locators`
- `pros`
- `risks`
- `decision`

## External References

외부 병행 번역은 internal divergence reference로만 쓴다. 보호되는 번역 본문은 저장하지 않는다.

저장 가능한 정보:

- edition name.
- ref locator.
- has parallel.
- divergence category.
- project-written note.

저장하지 않는 정보:

- protected translation text.
- long quotes.
- copied English/Korean translation body.

Early Buddhist Institute Korean consistency는 직접 접근 가능한 기준 corpus가 아니므로 controlled glossary와 project-adjudicated gold set으로 관리한다.

## Recommended First Direction

현재 단계에서는 첫 production 후보를 확정하지 않는다. 300 pilot과 1,000 pilot 후 다음을 보고 결정한다.

- QA report high-risk rate.
- gold set correctness.
- routing/TM impact.
- p90 cost.
- human review burden.

산문 중심의 작은 `mula` 범위가 우선 후보가 될 가능성이 높지만, `mula = easy`로 가정하지 않는다.

## Out of Scope

- 실제 첫 production 실행.
- UI 구현.
- DB migration.
- 외부 번역 본문 수집.

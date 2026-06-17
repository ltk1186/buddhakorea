# Pāli QA Report Generator Spec v0

## Purpose

QA report generator는 대량 번역 결과에서 사람이 볼 대상을 줄이는 deterministic layer다. 목표는 모든 segment를 사람이 검수하는 것이 아니라, high-risk segment와 representative sample을 안정적으로 추출하는 것이다.

이 문서는 구현 기준을 정의한다. 현재 단계에서는 Prompt 수정, Gemini 호출, DB write, RAG/embedding, UI 구현을 하지 않는다.

## Inputs

- parsed batch result JSON.
- local validator flags.
- glossary consistency report.
- glossary QA v1.1 report.
- gold set regression result.
- source integrity report.
- sample distribution metadata.

모든 입력은 read-only artifact로 다룬다.

## Output Schema

QA report는 다음 top-level 구조를 가진다.

- `generated_at`
- `input_artifacts`
- `summary`
- `priority_a`
- `priority_b`
- `priority_c`
- `auto_resolvable`
- `human_needed`
- `dedup_groups`
- `sample_recommendations`
- `warnings`

각 queue item은 다음 필드를 가진다.

- `stable_segment_key`
- `source_path`
- `text_layer`
- `chunk_type`
- `length_bucket`
- `priority`: `A`, `B`, `C`.
- `signals`
- `dedup_group_key`
- `recurrence_count`
- `auto_resolvable`
- `recommended_action`
- `review_tier`
- `estimated_review_minutes`

## Priority Rules

Priority A는 production 전에 반드시 사람이 보거나 deterministic fix가 필요한 항목이다.

- `schema_invalid`
- `parse_failed`
- `possible_true_untranslated_pali`
- `glossary_conflict`
- `avoid_ko_conflict_candidate`
- `cross_term_collision_review`
- `gold_regression_worsened`
- source hash mismatch
- silent source normalization

Priority B는 의미 위험이 있거나 glossary/human policy 검토가 필요한 항목이다.

- `grammar_uncertain`
- `doctrinal_risk`
- `low_confidence`
- `needs_human_glossary_review`
- `unexpected_variant`
- reference-only gold item

Priority C는 QA flag가 없더라도 표본 검수를 위해 뽑는다.

- random sample
- long segment sample
- verse sample
- tika sample
- title sample
- citation-heavy sample

random sample은 flag가 없는 오류를 찾기 위해 필요하다. verse, tika, long segment는 구조적으로 실패 가능성이 높은 bucket을 감시하기 위해 필요하다.

## Deduplication

동일 원인 issue가 여러 segment에서 반복될 수 있다. QA report는 같은 issue를 모두 사람이 따로 보게 하지 않는다.

예:

- 같은 citation abbreviation mapping 누락 80건.
- 같은 allowed Pāli whitelist 누락 30건.
- 같은 source display mapping 누락.

dedup 원칙:

- `dedup_group_key`가 같으면 하나의 representative item으로 묶는다.
- `recurrence_count`를 기록한다.
- 대표 segment 1~3개만 review queue에 올린다.
- recurrence가 큰 항목은 deterministic fix 후보로 올린다.

## Auto-Resolvable vs Human-Needed

Auto-resolvable은 사람이 번역 의미를 판단하지 않아도 deterministic policy로 해결 가능한 항목이다.

예:

- citation mapping 누락.
- allowed parenthetical Pāli whitelist.
- source display label 누락.
- number-only/title-only routing.

Human-needed는 의미 판단이나 project policy가 필요한 항목이다.

예:

- gold regression worsened.
- possible true untranslated Pāli.
- cross-term collision.
- needs_human glossary term.
- source normalization dispute.

## Review Tiers

- Tier 0: automated QA only.
- Tier 1: non-specialist operator review. formatting, citation display, obvious untranslated Pāli candidate.
- Tier 2: trained internal Buddhist terminology review. glossary conflict, doctrinal term, cross-term collision.
- Tier 3: Pāli expert review. ambiguous Pāli, difficult verse, source integrity dispute, gold adjudication.

solo project에서는 전체 expert review를 전제로 하지 않는다. Expert는 rare oracle로만 사용한다.

## Gold Regression Integration

Gold set 결과는 일반 QA flag보다 강한 신호다.

- `worsened`: Priority A.
- `improved`: summary에 기록하고 추가 검수는 optional.
- `neutral`: 기록만.
- `escalate`: Priority B 또는 A. reference-only이거나 자동 판정 불가인 경우다.

## Source Integrity Integration

source integrity는 번역 품질 이전의 전제다.

다음은 Priority A다.

- raw source hash mismatch.
- normalized source hash mismatch.
- translation source와 display source가 다르지만 normalization note가 없음.
- stable_segment_key/source_text_hash 누락.

## Success Criteria

v0 generator는 다음을 만족해야 한다.

- 75/300/1000/production artifact 모두 같은 schema로 처리한다.
- high-risk item을 Priority A/B/C로 나눈다.
- 반복 issue를 dedup한다.
- auto-resolvable과 human-needed를 분리한다.
- review minutes rough estimate를 제공한다.
- DB나 API 없이 실행 가능하다.

## Out of Scope

- 자동 semantic correctness 판정.
- Prompt 수정.
- Gemini 호출.
- DB write.
- UI queue 구현.
- RAG/embedding.
- fuzzy matching.

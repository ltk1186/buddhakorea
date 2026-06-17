# Pāli Source Integrity Spec v0

## Purpose

Source integrity는 번역 결과가 어떤 VRI XML 원문 segment에서 왔는지, 어떤 정규화를 거쳤는지, 표시되는 원문과 번역에 사용된 원문이 일치하는지 추적하는 규칙이다.

번역 품질 검토는 source integrity가 안정적일 때 의미가 있다. 원문이 조용히 바뀌면 번역과 검수의 기준이 사라진다.

## Invariants

필수 불변조건:

1. 모든 segment는 `stable_segment_key`를 가진다.
2. 모든 segment는 `source_text_hash`를 가진다.
3. raw source와 normalized source는 구분한다.
4. 표시용 Pāli source는 imported VRI XML segment로 추적 가능해야 한다.
5. translation source가 raw/normalized source와 다르면 normalization note를 남긴다.
6. 저본 철자 정규화는 무언으로 하지 않는다.
7. `source_path`, `xml_node_path`, `canonical_ref`는 가능한 한 유지한다.

## Source Fields

Production schema 후보:

- `stable_segment_key`
- `source_path`
- `xml_node_path`
- `canonical_ref`
- `raw_source_text`
- `display_source_text`
- `translation_source_text`
- `raw_source_text_hash`
- `normalized_source_text`
- `normalized_source_text_hash`
- `normalization_notes`
- `source_commit`
- `source_repo`

현재 pilot parsed artifact에는 이 필드들이 모두 있지 않다. v1.2 skeleton은 누락을 gap으로 보고하고, DB migration은 만들지 않는다.

## Hash Policy

Hash는 `sha256`을 사용한다.

- raw hash는 VRI importer에서 얻은 raw source 기준이다.
- normalized hash는 deterministic normalization 이후 source 기준이다.
- translation source hash는 실제 Prompt에 넣은 source 기준이다.

hash mismatch는 Priority A source integrity issue다.

## Silent Normalization

다음은 silent normalization으로 본다.

- raw source와 translation source가 다름.
- normalization note가 없음.
- spelling variant를 다른 형태로 읽어 번역했지만 uncertainty/note가 없음.

예:

- `akicchāni`를 `akiccāni`처럼 읽고 번역했지만 기록하지 않음.

silent normalization은 번역 품질 문제가 아니라 source integrity 문제로 먼저 다룬다.

## Display Source vs Translation Source

display source는 독자에게 보여주는 원문이다. translation source는 모델에 실제로 전달한 원문이다.

둘은 같을 수 있지만, 다음 경우 다를 수 있다.

- XML entity decoding.
- whitespace normalization.
- page break/note 제거.
- deterministic citation cleanup.

다를 경우 normalization note가 있어야 한다.

## Skeleton Functions

`backend/pali/translation/source_integrity.py`는 다음 순수 함수를 제공한다.

- `compute_source_hashes(raw_source_text, normalized_source_text)`
- `detect_silent_normalization(raw_source_text, translation_source_text, normalization_notes)`
- `validate_source_integrity_record(record)`
- `check_integrity(segment_record)`

이 함수들은 DB나 API를 호출하지 않는다.

## Baseline Gap Reporting

현재 75 pilot artifact에 대해 source integrity gap을 측정한다.

예상되는 gap:

- raw/normalized source field 미분리.
- `original_text`는 있으나 raw/translation/display source 구분 부족.
- normalization note field 없음.

이 gap은 production blocker다. 다만 기존 pilot 결과를 무효화하지는 않는다.

## Out of Scope

- VRI importer 변경.
- DB migration.
- source correction 자동화.
- LLM 호출.
- UI 표시 구현.

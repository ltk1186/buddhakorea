# Tripitaka Data Normalization Plan (Detailed)

Strategy for unifying terminology and writing style in `source_summaries_ko.json`, with explicit checkpoints for testing and rollback.

## 1. Objectives & Success Criteria

| Field | Current State | Target State | Success Check |
|-------|---------------|--------------|---------------|
| `period` | ~257 varied values | **14 카테고리** | 100% 값이 14개 목록에 속함 |
| `tradition` | ~173 varied values | **12 카테고리** (`tradition_normalizer.py` 활용) | 100% 값이 12개 목록에 속함 |
| `brief_summary` | 혼합 문체 (합니다/해요/한다) | **100% 한다/이다체** | 금지 어미(습니다/해요/시요 등) 0건 |
| 데이터 무결성 | 정규화 중 필드 손실 위험 | `_original_*` 필드로 보존 | 레코드 수 및 ID 100% 일치 |

완료된 작업: 본 계획서 초안 작성 완료.

## 2. Normalization Schema (확정할 세부 기준)

### Tradition (12)
`opennotebook/tradition_normalizer.py`의 매핑을 단일 소스로 사용. 매핑 테이블을 `schema/tradition_map.json`에 추출하여 스크립트/테스트가 동일한 소스를 참조하도록 함.

### Period (14)
동일 명칭·번역·오타를 모두 포괄하는 매핑 테이블을 `schema/period_map.json`으로 분리. 각 항목에 예시 원문과 우선순위 regex를 포함:
1. `초기불교` / 2. `부파불교` / 3. `후한` / 4. `삼국` / 5. `서진` / 6. `동진` / 7. `남북조` / 8. `수` / 9. `당` / 10. `오대십국` / 11. `송` / 12. `원` / 13. `명` / 14. `청` / Fallback: `기타`, `미상`

### Writing Style (한다/이다)
- 금지 어미 패턴: `(습니다|옵니다|합니다|해요|해요.|해요!|시요|이옵나이다)` 등.
- 허용 패턴: `(한다|이다|였다|였다.)` 등 평서 종결형 유지.
- 따옴표·괄호·HTML 태그·고유명사 표기는 원문 유지.

## 3. Implementation Roadmap

### Phase 1: 스키마·분석 도구 (승인 후 즉시)
- [ ] **스키마 파일화:** `schema/tradition_map.json`, `schema/period_map.json`, `schema/style_rules.json`(금지/허용 어미 목록, 예외 규칙) 생성.
- [ ] **정규화 설계 메모:** ambiguous 값 리스트 작성 (`당대`, `당(당나라)`, `동한` 등)과 우선순위 매칭 규칙 문서화.
- [ ] **분포 분석 도구:** `analyze_distribution.py`
  - tradition/period 분포 및 미매핑 값 출력
  - 요약문에서 금지 어미 건수와 예문 20개 샘플 추출
  - dry-run 리포트: JSON + Markdown(요약) 동시 생성

### Phase 2: 데이터 변환 (dry-run → 실행)
- [ ] **메인 스크립트:** `run_normalization.py`
  - 입력: `source_summaries_ko.json`; 출력: `source_summaries_ko_normalized.json`
  - 백업: `source_summaries_ko.backup_{timestamp}.json` 자동 생성
  - `_original_tradition`, `_original_period`, `_original_brief_summary`에 원본 저장
  - 매핑 적용 순서: tradition → period → 스타일
  - 스타일 변환:
    - 금지 어미 탐지 후에만 변환 요청
    - 따옴표·괄호·HTML 태그 보존 (간단한 토큰 잠금)
    - API 호출 실패 시 해당 레코드에 `style_normalization_status: "pending"` 표기, 재시도 가능하도록 기록
  - dry-run 옵션: 실제 파일 쓰기 대신 diff 리포트만 생성
  - 로그: 매핑 실패 목록, 스타일 변환 실패 목록을 별도 TSV로 저장

### Phase 3: 검증 및 테스트
- [ ] **테스트 스위트:** `test_normalization.py` (unittest 또는 pytest)
  - `test_tradition_categories`: 12개 집합 내 포함
  - `test_period_categories`: 14개 집합 내 포함
  - `test_style_endings`: 금지 어미 regex 0건
  - `test_integrity_counts`: 레코드 수, ID 유일성 동일
  - `test_original_fields`: `_original_*` 필드 존재·비어있지 않음
  - `test_no_html_damage`: `<`, `>` 수가 원본과 동일 (태그 보존)
- [ ] **샘플 수기 검수:** tradition/period 각 10건, 스타일 변환 20건 랜덤 추출해 의미 보존 여부 확인.
- [ ] **리포트:** 테스트 결과 + 샘플 검수 메모를 `reports/normalization_validation.md`로 저장.

### Phase 4: 배포 (Blue-Green)
- [ ] **스테이징 파일 고정:** `source_summaries_ko_normalized.json`을 최종 검증본으로 확정.
- [ ] **파일 스와핑:** `source_summaries_ko.json` → `.old`, normalized 파일을 본선으로 교체.
- [ ] **롤백 스위치:** 이상 발생 시 `.old` 복원 및 `_original_*` 필드 확인.
- [ ] **모니터링:** 배포 후 검색/필터 기능 수동 점검 (period, tradition 필터, 요약 노출).

## 4. 안전 조치
- **GCP 배포물 무변경:** 로컬/스테이징에서만 파일 교체.
- **비파괴 처리:** `_original_*` 필드 유지, 백업 파일 보관.
- **재현성:** 스키마·로그·리포트를 Git에 함께 기록하여 동일 결과 재생산 가능하도록 함.

## 5. 승인 후 바로 착수할 작업
1. 스키마 JSON 3종 초안 작성 후, 실제 데이터 대비 미매핑 값 목록 추출.
2. `analyze_distribution.py`로 현황 리포트 생성 및 공유.
3. 테스트 스켈레톤(`test_normalization.py`)과 샘플 데이터 1~2레코드로 로컬 실행 확인.

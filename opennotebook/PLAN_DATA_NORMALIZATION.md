# 불교 경전 데이터 정규화 최종 계획서

> **버전**: 2.0 (Final)
> **작성일**: 2024-12-02
> **상태**: 완료 (Phase 1-4 모두 구현됨)
> **최종 업데이트**: 2024-12-02

## 구현 완료 요약

| Phase | 상태 | 산출물 |
|-------|------|--------|
| Phase 1: 스키마 정의 | DONE | `schema/tradition_map.json`, `schema/period_map.json`, `schema/style_rules.json` |
| Phase 2: 분석 도구 | DONE | `analyze_distribution.py` |
| Phase 3: 정규화 도구 | DONE | `run_normalization.py` |
| Phase 4: 테스트 스위트 | DONE | `test_normalization.py` (11/11 테스트 통과) |
| Phase 5: 배포 스크립트 | DONE | `deploy_normalized_data.sh` |

### 정규화 결과
- **Tradition**: 173개 → 12개 (100% 매핑)
- **Period**: 257개 → 16개 (97.8% 매핑)
- **Style**: 195건 pending (API 연동 시 처리 가능)

---

---

## 1. 현황 분석

### 1.1 발견된 문제점

| 필드 | 현재 상태 | 목표 | 문제 유형 |
|------|----------|------|----------|
| `period` | 257개 고유값 | 15개 카테고리 | "당나라" vs "중국 당나라" 등 중복 |
| `tradition` | 173개 고유값 | 12개 카테고리 | "대승불교" vs "대승불교 (Mahayana)" |
| `brief_summary` | 혼합 문체 | 100% 해라체 | 합니다체(5.7%) vs 한다체(58.6%) |

### 1.2 근본 원인

- AI 생성 요약의 일관성 부족 (다양한 프롬프트/모델 버전 사용)
- 명확한 스키마 정의 없이 데이터 생성
- 후처리 정규화 단계 부재

### 1.3 기존 자산

- `tradition_normalizer.py`: 12개 정규 카테고리 매핑 로직 **이미 구현됨**
- 기존 API 엔드포인트에서 tradition 필터 정상 작동 중

---

## 2. 목표 스키마 정의

### 2.1 Tradition (전통) - 12개 카테고리

> **상태**: `tradition_normalizer.py`에 이미 구현됨

| 정규값 | 영문명 | 매핑 패턴 |
|--------|--------|----------|
| `초기불교` | Early Buddhism | 초기불교, 부파불교, 소승, 상좌부, 아함, 니까야 |
| `대승불교` | Mahayana | 대승불교, 대승, Mahayana (하위 종파 제외) |
| `밀교` | Esoteric | 밀교, 탄트라, 진언, 금강승, 다라니 |
| `선종` | Zen/Chan | 선종, 선불교, 참선, 조동종, 임제종 |
| `천태종` | Tiantai | 천태종, 천태, 법화종 |
| `화엄종` | Huayan | 화엄종, 화엄, 현수종 |
| `정토종` | Pure Land | 정토종, 정토, 염불, 아미타 |
| `유식불교` | Yogacara | 유식, 법상종, 유가 |
| `율종` | Vinaya | 율종, 율장, 계율, 사분율 |
| `삼론종` | Sanlun | 삼론종, 삼론, 중관 |
| `기타` | Other | 중국 불교, 티베트 불교, 일본불교 |
| `미상` | Unknown | 값 없음, 불명 |

### 2.2 Period (시대) - 15개 카테고리 (신규 구현 필요)

| 정규값 | 영문명 | 매핑 패턴 |
|--------|--------|----------|
| `초기불교` | Early Buddhism | 초기불교, 기원전, 붓다 재세시 |
| `부파불교` | Sectarian | 부파불교, 아비달마 시대 |
| `후한` | Eastern Han | 후한, 동한, 後漢 |
| `삼국` | Three Kingdoms | 삼국, 위, 오, 촉, 위진 |
| `서진` | Western Jin | 서진, 西晉 |
| `동진` | Eastern Jin | 동진, 東晉 |
| `남북조` | N/S Dynasties | 남북조, 유송, 양, 북위, 북제, 진(陳) |
| `수` | Sui | 수나라, 수, 隋 |
| `당` | Tang | 당나라, 중국 당나라, 당, 唐 |
| `오대십국` | Five Dynasties | 오대, 십국, 후량, 후당 |
| `송` | Song | 송나라, 북송, 남송, 宋 |
| `원` | Yuan | 원나라, 몽골, 元 |
| `명` | Ming | 명나라, 명, 明 |
| `청` | Qing | 청나라, 청, 淸 |
| `미상` | Unknown | 값 없음, 불명, 미상 |

**처리 규칙:**
1. "(추정)" 접미사 제거 → `_is_estimated: true` 플래그로 분리
2. "중국" 접두사 제거 (모든 왕조가 중국 기준)
3. 복합값 → 첫 번째 값 사용, 나머지 `_period_notes`로

### 2.3 Brief Summary 문체 - 해라체(한다체) 통일

**목표 문체**: 해라체 (Encyclopedia/Plain Style)

| 변환 대상 | 변환 결과 | 예시 |
|-----------|-----------|------|
| ~합니다 | ~한다 | "설명합니다" → "설명한다" |
| ~됩니다 | ~된다 | "강조됩니다" → "강조된다" |
| ~있습니다 | ~있다 | "있습니다" → "있다" |
| ~입니다 | ~이다 | "입니다" → "이다" |
| ~겠습니다 | ~겠다 | "하겠습니다" → "하겠다" |
| ~습니다/~ㅂ니다 | ~다 | "말씀하셨습니다" → "말씀하셨다" |
| ~해요/~에요 | ~다/~이다 | "중요해요" → "중요하다" |

**선택 근거:**
- 백과사전적 서술에 적합 (위키백과, 브리태니커 스타일)
- 기존 데이터의 58.6%가 이미 해라체
- 학술적 글쓰기 표준

---

## 3. 구현 계획

### 3.1 디렉토리 구조

```
opennotebook/
├── data_normalization/
│   ├── __init__.py
│   ├── schemas/
│   │   └── normalization_schema.json    # 통합 스키마 정의
│   ├── analyzers/
│   │   └── analyze_distribution.py      # 현재 분포 분석
│   ├── normalizers/
│   │   ├── period_normalizer.py         # 시대 정규화 (신규)
│   │   ├── tradition_normalizer.py      # 전통 정규화 (기존 복사)
│   │   └── style_normalizer.py          # 문체 정규화 (신규)
│   ├── tests/
│   │   └── test_normalization.py        # 테스트 스위트
│   └── run_normalization.py             # 메인 실행 스크립트
└── source_explorer/
    └── source_data/
        └── source_summaries_ko.json     # 원본 데이터
```

### 3.2 Phase 1: 분석 및 스키마 정의

**목표:** 현재 데이터 상태 파악 및 매핑 규칙 확정

**작업 항목:**

1. **`normalization_schema.json` 생성**
   ```json
   {
     "version": "1.0",
     "tradition": {
       "canonical": ["초기불교", "대승불교", ...],
       "mappings": { "대승불교 (Mahayana)": "대승불교", ... }
     },
     "period": {
       "canonical": ["초기불교", "부파불교", "후한", ...],
       "mappings": { "중국 당나라": "당", "당나라": "당", ... },
       "regex_rules": [
         { "pattern": "당.*", "canonical": "당" }
       ]
     },
     "style": {
       "banned_endings": ["습니다", "ㅂ니다", "해요", "에요"],
       "target": "해라체"
     }
   }
   ```

2. **`analyze_distribution.py` 개발**
   - 모든 고유 `tradition` 값 추출 및 빈도 분석
   - 모든 고유 `period` 값 추출 및 빈도 분석
   - `brief_summary` 문체 분석 (정규식 기반)
   - 리포트 출력: `analysis_report.json`

**산출물:**
- [ ] `normalization_schema.json`
- [ ] `analyze_distribution.py`
- [ ] `analysis_report.json` (현재 상태 스냅샷)

### 3.3 Phase 2: 정규화 도구 개발

**목표:** 재사용 가능한 정규화 함수 구현

**작업 항목:**

1. **`period_normalizer.py`**
   ```python
   def normalize_period(raw_value: str) -> tuple[str, dict]:
       """
       Returns: (canonical_period, metadata)
       metadata: { 'is_estimated': bool, 'original': str, 'notes': str }
       """
   ```

2. **`style_normalizer.py`**
   - 1차: 정규식 기반 패턴 치환 (90%+ 커버)
   - 2차 (옵션): 복잡한 문장은 Gemini Flash API 활용
   ```python
   def normalize_style(text: str, use_llm_fallback: bool = False) -> str:
       """
       Converts polite/formal endings to plain/expository style.
       """
   ```

3. **기존 `tradition_normalizer.py` 활용**
   - 이미 구현된 로직 그대로 사용
   - `data_normalization/normalizers/`에 복사

**산출물:**
- [ ] `period_normalizer.py`
- [ ] `style_normalizer.py`
- [ ] `tradition_normalizer.py` (복사)

### 3.4 Phase 3: 데이터 변환 실행

**목표:** 안전하게 데이터 변환 수행

**작업 항목:**

1. **`run_normalization.py` 개발**
   ```python
   # 실행 예시
   python -m data_normalization.run_normalization \
       --input source_explorer/source_data/source_summaries_ko.json \
       --output source_explorer/source_data/source_summaries_ko_normalized.json \
       --dry-run  # 먼저 dry-run으로 미리보기
   ```

2. **변환 프로세스**
   ```
   ┌─────────────────────────────────────────────────────────────┐
   │ 1. 백업 생성                                                │
   │    source_summaries_ko.backup_{timestamp}.json              │
   ├─────────────────────────────────────────────────────────────┤
   │ 2. 원본값 보존                                              │
   │    _original_tradition, _original_period, _original_summary │
   ├─────────────────────────────────────────────────────────────┤
   │ 3. 정규화 적용                                              │
   │    tradition → 12개 카테고리                                │
   │    period → 15개 카테고리                                   │
   │    brief_summary → 해라체                                   │
   ├─────────────────────────────────────────────────────────────┤
   │ 4. 스테이징 파일 생성                                       │
   │    source_summaries_ko_normalized.json                      │
   └─────────────────────────────────────────────────────────────┘
   ```

3. **변환 리포트 생성**
   ```json
   {
     "total_records": 1234,
     "tradition_changes": { "before": 173, "after": 12, "changed": 450 },
     "period_changes": { "before": 257, "after": 15, "changed": 800 },
     "style_changes": { "converted": 70, "unchanged": 1164 },
     "manual_review_needed": ["T01n0001", "T02n0123"]
   }
   ```

**산출물:**
- [ ] `run_normalization.py`
- [ ] `source_summaries_ko_normalized.json` (스테이징)
- [ ] `transformation_report.json`

### 3.5 Phase 4: 검증 및 테스트

**목표:** 데이터 무결성 및 품질 보장

**작업 항목:**

1. **`test_normalization.py` 테스트 스위트**
   ```python
   def test_tradition_categories():
       """모든 tradition이 12개 카테고리 내에 있는지 확인"""

   def test_period_categories():
       """모든 period가 15개 카테고리 내에 있는지 확인"""

   def test_summary_style():
       """banned_endings ('습니다', '해요' 등) 0% 확인"""

   def test_data_integrity():
       """레코드 수, sutra_id 고유성, 필수 필드 검증"""

   def test_original_preserved():
       """_original_* 필드가 모두 존재하는지 확인"""
   ```

2. **검증 체크리스트**

   | 검증 항목 | 기준 | 통과 조건 |
   |----------|------|----------|
   | 레코드 수 | 원본과 동일 | 100% |
   | tradition 카테고리 | 12개 이하 | 100% |
   | period 카테고리 | 15개 이하 | 100% |
   | 합니다체 비율 | 0% | 100% |
   | 원본값 보존 | _original_* | 100% |
   | API 정상 작동 | /api/sources | 200 OK |

3. **수동 검토**
   - 랜덤 샘플 50건 육안 검사
   - 문체 변환 품질 확인
   - 의미 변질 여부 확인

**산출물:**
- [ ] `test_normalization.py`
- [ ] 테스트 결과 리포트
- [ ] 수동 검토 체크리스트

### 3.6 Phase 5: 배포

**전략:** Blue-Green Deployment (무중단 배포)

**배포 단계:**

```bash
# 1. 스테이징 파일 업로드
gcloud compute scp \
    source_summaries_ko_normalized.json \
    buddhakorea-rag-server:/tmp/

# 2. VM 접속 후 파일 교체
ssh buddhakorea-rag-server

# 2a. 현재 파일 백업 (프로덕션)
sudo cp /opt/buddha-korea/source_explorer/source_data/source_summaries_ko.json \
       /opt/buddha-korea/source_explorer/source_data/source_summaries_ko.old

# 2b. 새 파일로 교체
sudo mv /tmp/source_summaries_ko_normalized.json \
       /opt/buddha-korea/source_explorer/source_data/source_summaries_ko.json

# 3. 컨테이너 재시작 (빌드 불필요 - 데이터만 변경)
cd /opt/buddha-korea
sudo docker-compose -f docker-compose.production.yml restart fastapi

# 4. 헬스체크
curl -s https://ai.buddhakorea.com/api/health | jq .
```

**롤백 계획 (5분 이내):**
```bash
# 즉시 롤백
sudo mv /opt/buddha-korea/source_explorer/source_data/source_summaries_ko.json \
       /opt/buddha-korea/source_explorer/source_data/source_summaries_ko.failed
sudo mv /opt/buddha-korea/source_explorer/source_data/source_summaries_ko.old \
       /opt/buddha-korea/source_explorer/source_data/source_summaries_ko.json
sudo docker-compose -f docker-compose.production.yml restart fastapi
```

---

## 4. 안전 프로토콜

### 4.1 핵심 원칙

| 원칙 | 설명 |
|------|------|
| **GCP 직접 수정 금지** | 모든 작업은 로컬에서 수행, 검증 후 배포 |
| **비파괴적 변환** | 원본값은 `_original_*` 필드에 항상 보존 |
| **타임스탬프 백업** | 변환 전 원본 파일 백업 필수 |
| **점진적 배포** | 한 번에 모든 변경 대신 단계별 배포 |

### 4.2 위험 관리

| 위험 | 영향 | 발생 확률 | 대응 방안 |
|------|------|----------|----------|
| 매핑 규칙 누락 | 일부 데이터 미처리 | 중 | 분석 단계에서 100% 커버리지 확인 |
| 의미 손실 | 정보 유실 | 하 | `_original_*` 필드 보존 |
| 문체 변환 오류 | 어색한 문장 | 중 | 정규식 테스트, 샘플 검증 |
| 배포 실패 | 서비스 중단 | 하 | 롤백 계획 준비, 백업 유지 |

### 4.3 점진적 배포 전략 (권장)

더 안전한 배포를 위해 3단계로 나누어 배포:

```
Week 1: tradition 정규화만 배포 → 1주일 모니터링
Week 2: period 정규화 추가 배포 → 1주일 모니터링
Week 3: style 정규화 최종 배포 → 안정화
```

---

## 5. 성공 기준

### 5.1 정량적 목표

| 지표 | 현재 | 목표 | 측정 방법 |
|------|------|------|----------|
| tradition 고유값 | 173개 | 12개 | `SELECT DISTINCT tradition` |
| period 고유값 | 257개 | 15개 | `SELECT DISTINCT period` |
| 합니다체 비율 | 5.7% | 0% | 정규식 매칭 |
| 데이터 손실 | - | 0건 | 레코드 수 비교 |
| 원본 보존율 | - | 100% | `_original_*` 필드 존재 확인 |

### 5.2 정성적 목표

- UI 필터 목록이 깔끔하게 12개/15개로 표시
- 일관된 문체로 전문성 있는 사용자 경험
- 유지보수 용이성 향상
- 향후 데이터 추가 시 스키마 준수 가능

---

## 6. 모니터링 계획

### 6.1 배포 후 모니터링 (24시간)

```bash
# 에러 로그 확인
sudo docker logs buddhakorea-fastapi --since 24h | grep -i error

# API 응답 확인
curl -s "https://ai.buddhakorea.com/api/sutras/meta" | jq '.traditions | length'
curl -s "https://ai.buddhakorea.com/api/sutras/meta" | jq '.periods | length'
```

### 6.2 장기 모니터링

- 사용자 피드백 수집
- 필터 사용 패턴 분석
- 검색 품질 모니터링

---

## 7. 승인 체크리스트

이 계획을 실행하기 전에 다음 사항을 확인해 주세요:

- [ ] Period 15개 카테고리 적절성 확인
- [ ] Tradition 12개 카테고리 (기존 유지) 확인
- [ ] 목표 문체 (해라체/한다체) 확정
- [ ] 점진적 배포 vs 일괄 배포 결정
- [ ] 배포 일정 협의

---

## 8. 다음 단계

승인 후 즉시 진행:

1. **Phase 1 시작**: `normalization_schema.json` 및 `analyze_distribution.py` 생성
2. **분석 리포트 공유**: 현재 데이터 상태 정확히 파악
3. **정규화 도구 개발**: period_normalizer, style_normalizer 구현
4. **테스트 환경 구축**: 로컬에서 전체 파이프라인 검증

---

*이 계획서는 업계 최고 관행(원본 보존, 점진적 배포, 롤백 계획, 자동화된 테스트)을 기반으로 작성되었습니다.*

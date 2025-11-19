# Buddha Korea RAG - 사용량 추적 가이드 📊

**토큰 사용량과 API 비용을 추적하는 시스템**

---

## ✨ 기능

✅ **개별 쿼리 토큰 수 추적** - 입력/출력 토큰 개별 기록
✅ **실시간 비용 계산** - Gemini, Claude, GPT 모델 모두 지원
✅ **모드별 통계** - 일반/자세히/캐시 모드 구분
✅ **일별/모델별 분석** - 시간대별 사용 패턴 분석
✅ **CSV/JSON 내보내기** - 데이터 분석 및 보고서 작성

---

## 📁 파일 구조

```
opennotebook/
├── usage_tracker.py          # 핵심 추적 모듈
├── main.py                    # 통합된 FastAPI (자동 로깅)
├── logs/
│   └── usage.jsonl            # 사용량 로그 (JSON Lines 형식)
└── check_usage.sh             # CLI 통계 확인 스크립트
```

---

## 🚀 사용법

### 1. 자동 추적 (기본)

**아무것도 하지 않아도 됩니다!**

`/api/chat` 엔드포인트로 쿼리를 보내면 자동으로 로깅됩니다:

```bash
curl -X POST http://localhost:8000/api/chat \
  -H "Content-Type: application/json" \
  -d '{
    "query": "무상에 대해 설명해주세요",
    "max_sources": 5
  }'
```

**자동으로 기록됨**:
- 입력 토큰 수
- 출력 토큰 수
- 예상 비용 (USD)
- 쿼리 모드 (normal/detailed/cached)
- 모델명
- 응답 시간

---

### 2. CLI로 통계 확인

#### 빠른 확인:
```bash
./check_usage.sh
```

**출력 예시**:
```
🔍 Buddha Korea RAG - 사용량 통계
==================================

총 쿼리 수: 15

최근 5개 쿼리:
────────────────────────────────────────────────────────────────
Query: 무상에 대해 설명해주세요...
Mode: normal | Model: gemini-2.5-pro
Tokens: 8543in + 2011out | Cost: $0.030786

Query: 사성제를 자세히 알려줘...
Mode: detailed | Model: gemini-2.5-pro
Tokens: 16234in + 7892out | Cost: $0.099213

────────────────────────────────────────────────────────────────
총 비용: $0.435678 USD

모드별 통계:
  normal: 10회 | $0.235678 | 평균: $0.023568/query
  detailed: 5회 | $0.200000 | 평균: $0.040000/query
```

---

### 3. API로 상세 통계 조회

#### 기본 통계 (최근 7일):
```bash
curl http://localhost:8000/api/usage-stats
```

**응답**:
```json
{
  "period_days": 7,
  "total_queries": 15,
  "cached_queries": 2,
  "api_queries": 13,
  "total_cost_usd": 0.4357,
  "tokens": {
    "input": 125430,
    "output": 38920,
    "total": 164350
  },
  "by_mode": {
    "normal": {
      "queries": 10,
      "cost_usd": 0.2357,
      "tokens": 98543,
      "avg_cost_per_query": 0.023570
    },
    "detailed": {
      "queries": 5,
      "cost_usd": 0.2000,
      "tokens": 65807,
      "avg_cost_per_query": 0.040000
    }
  },
  "by_day": {
    "2025-01-17": {
      "queries": 10,
      "cost_usd": 0.3000,
      "tokens": 120000
    },
    "2025-01-18": {
      "queries": 5,
      "cost_usd": 0.1357,
      "tokens": 44350
    }
  }
}
```

#### 최근 30일 통계:
```bash
curl "http://localhost:8000/api/usage-stats?days=30"
```

#### CSV 다운로드:
```bash
curl "http://localhost:8000/api/usage-stats?format=csv" -o usage_stats.csv
```

---

### 4. 최근 쿼리 조회

```bash
curl "http://localhost:8000/api/recent-queries?limit=10"
```

**응답**:
```json
{
  "count": 10,
  "queries": [
    {
      "timestamp": "2025-01-17T10:23:45",
      "query": "무상에 대해 설명해주세요",
      "mode": "normal",
      "model": "gemini-2.5-pro",
      "tokens": {
        "input": 8543,
        "output": 2011,
        "total": 10554
      },
      "cost_usd": 0.030786,
      "from_cache": false,
      "latency_ms": 3245
    }
  ]
}
```

---

## 💰 비용 계산 방식

### 지원 모델 가격표 (per 1M tokens):

| 모델 | 입력 | 출력 |
|------|------|------|
| **Gemini 2.5 Pro** | $1.25 | $10.00 |
| **Gemini 2.0 Flash** | $0 (Free) | $0.82 |
| **Gemini 1.5 Pro** | $1.25 | $5.00 |
| **Claude 3.5 Sonnet** | $3.00 | $15.00 |
| **GPT-4o** | $2.50 | $10.00 |

### 계산 공식:
```
비용 = (입력_토큰 / 1,000,000 × 입력_가격) + (출력_토큰 / 1,000,000 × 출력_가격)
```

### 예시:
```
Gemini 2.5 Pro로 일반 쿼리:
- 입력: 8,500 토큰 → $0.0106
- 출력: 2,048 토큰 → $0.0205
─────────────────────────
총 비용: $0.0311
```

---

## 📊 로그 파일 형식

**`logs/usage.jsonl`** (JSON Lines 형식):

```jsonl
{"timestamp": "2025-01-17T10:23:45", "query": "무상에 대해 설명해주세요", "response_preview": "무상(無常, anicca)은 불교의 핵심 가르침...", "mode": "normal", "model": "gemini-2.5-pro", "tokens": {"input": 8543, "output": 2011, "total": 10554}, "cost_usd": 0.030786, "from_cache": false, "session_id": "abc123", "latency_ms": 3245}
```

### 필드 설명:
- `timestamp`: ISO 8601 형식 시간
- `query`: 사용자 질문 (첫 100자)
- `response_preview`: LLM 응답 미리보기 (첫 100자)
- `mode`: `normal` | `detailed` | `cached`
- `model`: 사용된 LLM 모델명
- `tokens.input`: 입력 토큰 수
- `tokens.output`: 출력 토큰 수
- `cost_usd`: 비용 (USD, 소수점 6자리)
- `from_cache`: 캐시 사용 여부
- `session_id`: 세션 ID (optional)
- `latency_ms`: 응답 시간 (밀리초)

---

## 🔧 고급 사용법

### 1. Python으로 직접 분석

```python
import json

# 전체 로그 읽기
with open('logs/usage.jsonl', 'r') as f:
    logs = [json.loads(line) for line in f]

# 총 비용 계산
total_cost = sum(log['cost_usd'] for log in logs)
print(f"총 비용: ${total_cost:.4f}")

# 모드별 평균 비용
from collections import defaultdict

mode_stats = defaultdict(lambda: {'count': 0, 'cost': 0.0})

for log in logs:
    mode = log['mode']
    mode_stats[mode]['count'] += 1
    mode_stats[mode]['cost'] += log['cost_usd']

for mode, stats in mode_stats.items():
    avg = stats['cost'] / stats['count']
    print(f"{mode}: {stats['count']}회, 평균 ${avg:.6f}/query")
```

### 2. jq로 로그 분석

```bash
# 최근 10개 쿼리의 비용
cat logs/usage.jsonl | tail -10 | jq '{query, cost: .cost_usd}'

# 총 비용 계산
cat logs/usage.jsonl | jq -s 'map(.cost_usd) | add'

# 모드별 평균 비용
cat logs/usage.jsonl | jq -s '
  group_by(.mode) |
  map({
    mode: .[0].mode,
    avg_cost: (map(.cost_usd) | add / length)
  })
'

# 일별 비용 합계
cat logs/usage.jsonl | jq -s '
  group_by(.timestamp[:10]) |
  map({
    date: .[0].timestamp[:10],
    total_cost: (map(.cost_usd) | add)
  })
'
```

### 3. CSV로 변환 후 Excel 분석

```bash
# API로 CSV 다운로드
curl "http://localhost:8000/api/usage-stats?format=csv" -o usage_30days.csv

# Excel이나 Google Sheets에서 열기
open usage_30days.csv
```

---

## 📈 대시보드 통합 (선택사항)

### Grafana 연동 (권장)

1. **Loki 설치** (로그 수집)
```bash
docker run -d --name=loki -p 3100:3100 grafana/loki:latest
```

2. **Promtail 설정** (logs/usage.jsonl 전송)
```yaml
# promtail-config.yaml
server:
  http_listen_port: 9080

positions:
  filename: /tmp/positions.yaml

clients:
  - url: http://localhost:3100/loki/api/v1/push

scrape_configs:
  - job_name: usage
    static_configs:
      - targets:
          - localhost
        labels:
          job: buddha-korea-usage
          __path__: /path/to/logs/usage.jsonl
```

3. **Grafana 대시보드** 생성

---

## ⚠️ 주의사항

### 1. **토큰 추정의 정확도**

현재 시스템은 다음 방법으로 토큰을 추적합니다:

- **LangChain 응답 메타데이터** (가장 정확)
  - LLM이 반환하는 token_usage 정보 사용
  - Gemini API는 이 정보를 제공하지 않을 수 있음

- **폴백: 텍스트 기반 추정** (±10-20% 오차)
  - 문자 수 ÷ 2.5 = 토큰 수 (다국어 평균)
  - 입력 컨텍스트: 10 chunks × 800 tokens 가정

### 2. **비용은 예상치입니다**

- 실제 청구는 GCP/Anthropic/OpenAI 계정에서 확인하세요
- 이 시스템은 **추적 및 모니터링 목적**입니다

### 3. **로그 파일 관리**

```bash
# 로그 파일 크기 확인
du -h logs/usage.jsonl

# 오래된 로그 정리 (30일 이상)
python3 << EOF
import json
from datetime import datetime, timedelta

cutoff = (datetime.now() - timedelta(days=30)).isoformat()

with open('logs/usage.jsonl', 'r') as f:
    lines = [
        line for line in f
        if json.loads(line)['timestamp'] >= cutoff
    ]

with open('logs/usage.jsonl', 'w') as f:
    f.writelines(lines)
EOF
```

---

## 🎯 사용 시나리오

### Scenario 1: 월간 비용 리포트
```bash
# 이번 달 총 비용 확인
curl "http://localhost:8000/api/usage-stats?days=30" | jq '{
  total_cost: .total_cost_usd,
  queries: .total_queries,
  avg_per_query: (.total_cost_usd / .total_queries)
}'
```

### Scenario 2: 모델 비교
```bash
# 모델별 비용 효율성 비교
curl "http://localhost:8000/api/usage-stats?days=7" | jq '.by_model'
```

### Scenario 3: 캐시 효율성
```bash
# 캐시로 절약한 비용 계산
curl "http://localhost:8000/api/usage-stats?days=7" | jq '{
  cached: .cached_queries,
  api: .api_queries,
  cache_rate: (.cached_queries / .total_queries * 100)
}'
```

---

## 📞 문제 해결

### Q: 로그가 기록되지 않아요
**A**:
1. `logs/` 디렉토리 권한 확인: `chmod 755 logs/`
2. `usage.jsonl` 파일 확인: `ls -lh logs/usage.jsonl`
3. FastAPI 로그 확인: `docker compose logs fastapi`

### Q: 토큰 수가 0으로 나와요
**A**:
- Gemini API는 토큰 정보를 반환하지 않을 수 있습니다
- 폴백 추정 로직이 작동하는지 확인하세요
- `logs/app.log`에서 "Token estimation" 메시지 확인

### Q: 비용이 너무 높아요!
**A**:
1. **모델 변경**: Gemini 2.0 Flash로 전환 (92% 절감)
   ```bash
   # .env 파일에서
   LLM_MODEL=gemini-2.0-flash-exp
   ```
2. **캐시 활용**: 자주 묻는 질문은 `/api/cache`로 캐싱
3. **detailed 모드 제한**: 필요할 때만 사용

---

**구현 완료! 🎉**

이제 모든 쿼리의 토큰 수와 비용을 정확히 추적할 수 있습니다.

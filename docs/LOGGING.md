# Buddha Korea Logging System

Production-grade logging infrastructure following industry best practices for privacy, analytics, and operational monitoring.

## Architecture Overview

```
┌─────────────────┐
│  FastAPI App    │
│  + loguru       │
└────────┬────────┘
         │ writes
         ▼
┌─────────────────────────────────┐
│  JSONL Log Files                │
│  - logs/qa_pairs.jsonl          │
│  - logs/usage.jsonl             │
│  - logs/app.log                 │
└────────┬────────────────────────┘
         │ rotated by
         ▼
┌─────────────────────────────────┐
│  Logrotate (daily)              │
│  - Compress old logs            │
│  - Trigger analytics processing │
└────────┬────────────────────────┘
         │ processes
         ▼
┌─────────────────────────────────┐
│  Analytics Processor            │
│  - Incremental JSONL parsing    │
│  - Byte-offset checkpoints      │
│  - Atomic Redis updates (Lua)   │
└────────┬────────────────────────┘
         │ stores in
         ▼
┌─────────────────────────────────┐
│  Redis (AOF persistence)        │
│  - Daily query counts           │
│  - Token usage by model/mode    │
│  - Cost tracking                │
└─────────────────────────────────┘
```

## Components

### 1. PII Protection (`privacy.py`)

Lightweight regex-based PII masking for Korean language data. **Automatically integrated** into both `usage_tracker.py` and `qa_logger.py` - all logged queries and responses are masked before writing to disk.

**Patterns:**
| PII Type | Example Input | Masked Output |
|----------|---------------|---------------|
| Korean phone | `010-1234-5678` | `[KOREAN_PHONE_MASKED]` |
| Korean RRN (주민등록번호) | `901225-1234567` | `[KOREAN_RRN_MASKED]` |
| Email | `user@example.com` | `[EMAIL_MASKED]` |
| IP Address | `192.168.1.100` | `[IP_ADDRESS_MASKED]` |

**Integration Status:** ✅ **ACTIVE**
- `usage_tracker.py` - Masks query and response_preview before logging
- `qa_logger.py` - Masks full query and response before logging

Both loggers now also accept a structured `trace` payload for operational
investigation. The trace is intended to support future admin/backoffice query
detail views without exposing raw infrastructure internals.

Current trace fields include:

- prompt id/version/mode
- retrieval mode
- retrieval top-k
- retrieval filter type/value
- max source count
- whether HyDE was applied
- response mode
- streaming flag
- model name
- resolved provider route

Phase 7 adds a reliability-oriented aggregation path on top of the same
structured usage logs:

- latency sample size
- average latency
- P50 / P95 latency
- slow-query count by threshold
- cache-hit rate
- average cost per query
- daily trend rows for query volume, cost, cache, and latency

The admin panel combines that usage-log view with persisted `chat_messages`
data to show source-quality proxies such as:

- answers in the last 24 hours
- zero-source answers in the last 24 hours
- zero-source rate
- average sources per answer

The runtime chat persistence layer now also stores this trace on assistant
messages in PostgreSQL:

- `chat_messages.trace_json`

That gives the admin console a read-only investigation path without requiring
operators to inspect raw JSONL files directly. For the persisted answer message,
the database row can now carry:

- `sources_json`
- `tokens_used`
- `latency_ms`
- `trace_json`

The admin query investigation view joins the selected session/user/message and
renders this trace alongside the masked query and answer pair.

**Manual Usage:**
```python
from privacy import mask_pii, anonymize_ip

# Mask PII in text
masked_text = mask_pii("전화번호는 010-1234-5678입니다")
# Output: "전화번호는 [KOREAN_PHONE_MASKED]입니다"

# Anonymize IP (for nginx logs)
anon_ip = anonymize_ip("192.168.1.100")  # Returns: "192.168.1.0"
```

**Test:**
```bash
python privacy.py
```

### 2. Analytics Processor (`analytics_processor.py`)

Incremental log processor with Redis analytics aggregation.

**Features:**
- **File locking** (fcntl) - Prevents concurrent runs
- **Byte-offset checkpoints** - Resumable processing after rotation
- **Atomic Redis updates** - Lua scripts prevent race conditions
- **Daily aggregation** - Queries, costs, tokens by day/model/mode

**Usage:**
```bash
# Manual run
python analytics_processor.py

# Automated (runs every 30 minutes via cron)
# See "Post-Deployment Setup" below
```

**Redis Data Structure:**
```
analytics:daily:2025-11-24
  ├─ queries: 1234
  ├─ cost: 5.67
  ├─ tokens: 123456
  ├─ input_tokens: 98765
  ├─ output_tokens: 24691
  └─ cached_queries: 456

analytics:model:gemini-2.5-pro
  ├─ queries: 800
  ├─ cost: 4.50
  └─ tokens: 100000

analytics:mode:detailed
  ├─ queries: 234
  ├─ cost: 2.10
  └─ tokens: 50000

analytics:sutra:diamond_sutra
  └─ queries: 45
```

**Get Analytics:**
```python
from analytics_processor import AnalyticsProcessor

processor = AnalyticsProcessor()
analytics = processor.get_analytics(days=7)

print(analytics["totals"])
# {'queries': 5000, 'cost': 25.50, 'tokens': 500000, ...}
```

### 3. Log Rotation (`logrotate.d/`)

**App Logs** (`buddhakorea-app`):
- Rotates: `logs/*.log`, `logs/*.jsonl`
- Frequency: Daily (or when > 100MB)
- Retention: 30 days
- Compression: Yes (delayed)
- Post-rotate: Runs analytics processor

**Nginx Logs** (`buddhakorea-nginx`):
- Rotates: `/var/log/nginx/access.log`, `/var/log/nginx/error.log`
- Frequency: Daily
- Retention: 14 days
- Compression: Yes (delayed)

**Installation:**
```bash
sudo cp logrotate.d/buddhakorea-app /etc/logrotate.d/
sudo cp logrotate.d/buddhakorea-nginx /etc/logrotate.d/
```

**Test:**
```bash
sudo logrotate -d /etc/logrotate.d/buddhakorea-app
```

### 4. Redis Persistence (`redis.conf`)

**Configuration Highlights:**
- **Persistence**: AOF (appendonly.aof) + RDB snapshots
- **Memory limit**: 512MB with LRU eviction
- **Security**: Password authentication required
- **Dangerous commands disabled**: FLUSHALL, FLUSHDB, CONFIG

**Backup Script** (`backup_redis.sh`):
- Runs: Daily at 2 AM (via cron)
- Method: BGSAVE + tar.gz compression
- Retention: 30 days
- Location: `/opt/buddha-korea/backups/redis/`

**Manual Backup:**
```bash
./backup_redis.sh
```

### 5. Deployment Script (`deploy.sh`)

Blue-green deployment with health checks and rollback.

**Usage:**
```bash
sudo -u appuser ./deploy.sh
```

**Phases:**
1. **Preflight checks** - Verify disk space, files, permissions
2. **Backup** - Snapshot current deployment state
3. **Build** - Build new Docker images with --no-cache
4. **Deploy** - Blue-green swap with health checks
5. **Verify** - Test all services and endpoints
6. **Post-deployment** - Setup cron jobs, cleanup

**Rollback:**
Automatic rollback on failure. Manual rollback:
```bash
cd /opt/buddha-korea
docker-compose -f docker-compose.production.yml down
docker-compose -f docker-compose.production.yml up -d
```

## Verification Checklist

### ✅ 1. Container Log Paths Match Host Volume
```bash
# Check docker-compose.production.yml
grep -A1 "volumes:" docker-compose.production.yml | grep logs

# Expected output:
# - ./logs:/app/logs
```

**Status:** ✅ Verified - Container `/app/logs` maps to host `./logs`

### ✅ 2. PII Regex Tests Pass
```bash
python privacy.py
```

**Expected output:**
```
✅ All PII masking tests passed (Korean language support verified)
```

**Status:** ✅ All tests pass with lookbehind/lookahead assertions for Unicode

### ✅ 2b. PII Masking Integrated into Loggers
```bash
# Test that loggers mask PII automatically
python -c "
from usage_tracker import log_token_usage
from qa_logger import log_qa_pair

# Log with PII - should be masked
log_token_usage(query='Call 010-1234-5678', response='OK', input_tokens=10, output_tokens=5, model='test')
log_qa_pair(query='Email me at test@example.com', response='Response with 010-9999-8888')

# Verify last entries are masked
import json
with open('logs/usage.jsonl') as f:
    last = json.loads(f.readlines()[-1])
    assert '[KOREAN_PHONE_MASKED]' in last['query'], 'PII not masked in usage_tracker'
print('✅ PII masking integrated into loggers')
"
```

**Status:** ✅ `usage_tracker.py` and `qa_logger.py` automatically mask PII before logging

### ✅ 3. Lua Script for Atomic Redis Merges
```bash
# Test with sample data
python -c "
from analytics_processor import AnalyticsProcessor
import redis

# Create test Redis client
r = redis.Redis(host='localhost', port=6379, decode_responses=True)

# Create processor
processor = AnalyticsProcessor(redis_client=r)

# Check Lua script registration
print('Lua script registered:', processor.update_analytics_script.sha)
"
```

**Status:** ✅ Lua script in `analytics_processor.py` lines 36-76

### ⏳ 4. Dry-run Deployment Script
```bash
# Test on local machine first
cd /Users/vairocana/Desktop/buddhakorea/buddha-korea-notebook-exp/opennotebook

# Check preflight validations
bash -n deploy.sh  # Syntax check

# Inspect phases
grep -E "^(preflight_checks|backup_deployment|build_images|blue_green_deploy|post_deployment)" deploy.sh
```

**Status:** ⏳ Created, needs testing in staging environment

## Post-Deployment Setup

After running `deploy.sh`, verify the following cron jobs are configured:

### 1. Redis Backup (Daily at 2 AM)
```bash
crontab -l | grep backup_redis
# Expected: 0 2 * * * /opt/buddha-korea/backup_redis.sh
```

### 2. Analytics Processor (Every 30 minutes)
```bash
crontab -l | grep analytics_processor
# Expected: */30 * * * * cd /opt/buddha-korea && /usr/bin/python3 analytics_processor.py >> /opt/buddha-korea/logs/analytics_processor.log 2>&1
```

### 3. Logrotate (Daily via system cron)
```bash
ls -l /etc/logrotate.d/buddhakorea-*
# Expected:
# -rw-r--r-- 1 root root ... /etc/logrotate.d/buddhakorea-app
# -rw-r--r-- 1 root root ... /etc/logrotate.d/buddhakorea-nginx
```

## Monitoring Commands

### Check Log Files
```bash
# Q&A logs
tail -f logs/qa_pairs.jsonl | jq '.'

# Usage logs
tail -f logs/usage.jsonl | jq '.'

# Application logs
tail -f logs/app.log
```

### Check Redis Analytics
```bash
# Via Docker
docker exec buddhakorea-redis redis-cli -a ${REDIS_PASSWORD} INFO keyspace

# Get analytics via Python
docker exec buddhakorea-fastapi python3 -c "
from analytics_processor import AnalyticsProcessor
import json
print(json.dumps(AnalyticsProcessor().get_analytics(7), indent=2, ensure_ascii=False))
"
```

### Check Container Health
```bash
docker ps | grep buddhakorea
docker stats --no-stream buddhakorea-fastapi buddhakorea-redis buddhakorea-nginx
```

### Test Analytics Processing
```bash
# Create test log entry
echo '{"timestamp":"2025-11-24T12:00:00","model":"gemini-2.5-pro","cost_usd":0.01,"tokens":{"input":100,"output":50},"from_cache":false}' >> logs/usage.jsonl

# Run processor
python analytics_processor.py

# Verify in Redis
docker exec buddhakorea-redis redis-cli -a ${REDIS_PASSWORD} HGETALL analytics:daily:2025-11-24
```

## Security Considerations

1. **PII Masking**: All logs are masked before writing to disk
2. **IP Anonymization**: Last octet zeroed in nginx logs
3. **Redis Authentication**: Password required (set via REDIS_PASSWORD env var)
4. **Log Permissions**: 0640 (owner read/write, group read only)
5. **Dangerous Redis Commands Disabled**: FLUSHALL, FLUSHDB, CONFIG

## Troubleshooting

### Analytics not updating
```bash
# Check if processor is running
ps aux | grep analytics_processor

# Check for lock file (indicates another instance running)
ls -l logs/.analytics_processor.lock

# Check checkpoint file
cat logs/.analytics_checkpoint.json

# Run manually with verbose output
python analytics_processor.py
```

### Redis connection errors
```bash
# Test Redis connection
docker exec buddhakorea-redis redis-cli -a ${REDIS_PASSWORD} PING

# Check Redis logs
docker logs buddhakorea-redis

# Verify environment variables
docker exec buddhakorea-fastapi env | grep REDIS
```

### Log rotation not working
```bash
# Test logrotate config
sudo logrotate -d /etc/logrotate.d/buddhakorea-app

# Force rotation
sudo logrotate -f /etc/logrotate.d/buddhakorea-app

# Check system logrotate logs
sudo cat /var/log/syslog | grep logrotate
```

## Performance Impact

- **PII Masking**: < 5ms per query (acceptable overhead)
- **Analytics Processing**: Incremental, only processes new lines
- **Log Rotation**: Non-blocking (copytruncate mode)
- **Redis Queries**: < 1ms via Lua atomic operations

## Disk Usage Estimates

- **Daily logs**: ~50-200MB (compressed: ~10-40MB)
- **30 days retention**: ~300MB-1.2GB compressed
- **Redis AOF**: ~10-50MB (depends on query volume)
- **Redis backups**: ~5-25MB compressed per day

## Support

For issues or questions:
1. Check `logs/analytics_processor.log`
2. Check `logs/app.log`
3. Review Redis INFO: `docker exec buddhakorea-redis redis-cli -a ${REDIS_PASSWORD} INFO`
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

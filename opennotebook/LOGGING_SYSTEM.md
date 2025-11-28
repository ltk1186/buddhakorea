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

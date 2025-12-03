# DevOps 로드맵 (VM 유지 + 안정성 중심)

> **결정사항**: GCE VM 유지, Cloud Run은 비활성화
> **마지막 업데이트**: 2025-12-03
> **검토자**: GCP DevOps Advisor

## 현재 상태 → 목표

```
현재                                목표
─────────────────────────────────────────────────────────────
인프라:      VM + Cloud Run 혼재     VM 단일화 (Cloud Run 비활성화)
CI/CD:       수동 배포              GitHub Actions + IAP 자동 배포
보안:        SSH 키 기반            Workload Identity Federation
모니터링:    없음                   Cloud Monitoring + 구조화된 로깅
백업:        없음                   자동 백업 (ChromaDB, Redis)
비용:        최적화 없음            LLM 캐싱으로 40% 절감
```

---

## 전체 로드맵

| Phase | 내용 | 우선순위 | 예상 시간 |
|-------|------|----------|----------|
| **0** | 인프라 정리 (Cloud Run 비활성화) | 🔴 높음 | 15분 |
| **1** | 보안 강화 CI/CD (WIF + IAP) | 🔴 높음 | 1.5시간 |
| **2** | 모니터링 + 구조화된 로깅 | 🔴 높음 | 1시간 |
| **3** | Alerting 설정 | 🟡 중간 | 30분 |
| **4** | 백업/재해 복구 | 🟡 중간 | 1시간 |
| **5** | LLM 비용 최적화 | 🟡 중간 | 1시간 |
| **6** | Staging 환경 (선택) | 🟢 낮음 | 2시간 |

---

# Phase 0: 인프라 정리

## 0.1 현재 상태 분석

```
문제: 두 개의 인프라가 혼재
─────────────────────────────────────────────
1. GCE VM (buddhakorea-rag-server)
   - ai.buddhakorea.com 서빙 중 (실제 서비스)
   - Docker Compose (nginx + fastapi + redis)
   - 수동 배포 필요

2. Cloud Run (buddha-korea-chatbot)
   - cloudbuild.yaml로 자동 배포
   - DNS 연결 안 됨 (사용되지 않음)
   - 불필요한 빌드 비용 발생
```

## 0.2 Cloud Run 비활성화

```bash
# Cloud Build 트리거 비활성화
gcloud builds triggers list --format="table(name,id)"
gcloud builds triggers delete TRIGGER_NAME --quiet

# 또는 Cloud Run 서비스 삭제 (선택)
# gcloud run services delete buddha-korea-chatbot --region=us-central1 --quiet
```

## 0.3 cloudbuild.yaml 비활성화

```bash
# cloudbuild.yaml을 archive 폴더로 이동
mkdir -p opennotebook/archive
mv opennotebook/cloudbuild.yaml opennotebook/archive/cloudbuild.yaml.disabled
```

**체크포인트 Phase 0:**
- [ ] Cloud Build 트리거 비활성화/삭제
- [ ] cloudbuild.yaml 비활성화
- [ ] Cloud Run 서비스 삭제 또는 유지 결정

---

# Phase 1: 보안 강화 CI/CD

> **핵심 변경**: SSH 키 대신 Workload Identity Federation + IAP 사용

## 1.1 왜 SSH 키가 위험한가?

```
❌ 기존 방식 (위험)
─────────────────────────────────────────────
GitHub Secrets에 SSH 프라이빗 키 저장
→ 키 유출 시 VM 무제한 접근 가능
→ 키 교체가 수동이며 번거로움

✅ 개선 방식 (권장)
─────────────────────────────────────────────
Workload Identity Federation + IAP 터널
→ 임시 토큰 사용 (자동 만료)
→ GCP IAM으로 세밀한 권한 제어
→ 키 관리 불필요
```

## 1.2 Workload Identity Federation 설정

```bash
# 1. Workload Identity Pool 생성
gcloud iam workload-identity-pools create "github-pool" \
  --location="global" \
  --display-name="GitHub Actions Pool"

# 2. OIDC Provider 추가
gcloud iam workload-identity-pools providers create-oidc "github-provider" \
  --location="global" \
  --workload-identity-pool="github-pool" \
  --display-name="GitHub Provider" \
  --attribute-mapping="google.subject=assertion.sub,attribute.actor=assertion.actor,attribute.repository=assertion.repository" \
  --issuer-uri="https://token.actions.githubusercontent.com"

# 3. 서비스 계정 생성
gcloud iam service-accounts create deploy-sa \
  --display-name="GitHub Actions Deploy SA"

# 4. 서비스 계정에 필요한 권한 부여
gcloud projects add-iam-policy-binding gen-lang-client-0324154376 \
  --member="serviceAccount:deploy-sa@gen-lang-client-0324154376.iam.gserviceaccount.com" \
  --role="roles/compute.instanceAdmin.v1"

gcloud projects add-iam-policy-binding gen-lang-client-0324154376 \
  --member="serviceAccount:deploy-sa@gen-lang-client-0324154376.iam.gserviceaccount.com" \
  --role="roles/iap.tunnelResourceAccessor"

# 5. GitHub 저장소에 Workload Identity 연결
gcloud iam service-accounts add-iam-policy-binding \
  "deploy-sa@gen-lang-client-0324154376.iam.gserviceaccount.com" \
  --role="roles/iam.workloadIdentityUser" \
  --member="principalSet://iam.googleapis.com/projects/5222548937/locations/global/workloadIdentityPools/github-pool/attribute.repository/YOUR_GITHUB_USERNAME/buddha-korea-notebook-exp"
```

## 1.3 IAP 터널 활성화

```bash
# VM에 IAP 터널 접근 허용
gcloud compute firewall-rules create allow-iap-ssh \
  --direction=INGRESS \
  --priority=1000 \
  --network=default \
  --action=ALLOW \
  --rules=tcp:22 \
  --source-ranges=35.235.240.0/20 \
  --target-tags=iap-ssh

# VM에 태그 추가
gcloud compute instances add-tags buddhakorea-rag-server \
  --zone=us-central1-a \
  --tags=iap-ssh
```

## 1.4 GitHub Secrets 설정

```
GitHub Repository > Settings > Secrets and variables > Actions

필요한 Secrets:
─────────────────────────────────────────────
WIF_PROVIDER: projects/5222548937/locations/global/workloadIdentityPools/github-pool/providers/github-provider
WIF_SERVICE_ACCOUNT: deploy-sa@gen-lang-client-0324154376.iam.gserviceaccount.com
GCP_PROJECT_ID: gen-lang-client-0324154376
VM_ZONE: us-central1-a
VM_NAME: buddhakorea-rag-server
```

## 1.5 GitHub Actions 워크플로우

```yaml
# .github/workflows/deploy-vm.yml
name: Deploy to VM

on:
  push:
    branches: [main]
    paths:
      - 'opennotebook/**'
      - '!opennotebook/archive/**'

jobs:
  deploy:
    runs-on: ubuntu-latest
    permissions:
      id-token: write
      contents: read

    steps:
      - name: Checkout
        uses: actions/checkout@v4

      - name: Authenticate to GCP
        id: auth
        uses: google-github-actions/auth@v2
        with:
          workload_identity_provider: ${{ secrets.WIF_PROVIDER }}
          service_account: ${{ secrets.WIF_SERVICE_ACCOUNT }}

      - name: Setup gcloud
        uses: google-github-actions/setup-gcloud@v2

      - name: Deploy via IAP tunnel
        run: |
          # 파일 복사
          gcloud compute scp \
            --tunnel-through-iap \
            --zone=${{ secrets.VM_ZONE }} \
            opennotebook/index.html \
            opennotebook/main.py \
            opennotebook/tradition_normalizer.py \
            ${{ secrets.VM_NAME }}:/tmp/

          # VM에서 배포 스크립트 실행
          gcloud compute ssh ${{ secrets.VM_NAME }} \
            --tunnel-through-iap \
            --zone=${{ secrets.VM_ZONE }} \
            --command="
              # 백업 생성
              sudo cp /opt/buddha-korea/index.html /opt/buddha-korea/index.html.bak 2>/dev/null || true

              # 파일 복사
              sudo mv /tmp/index.html /opt/buddha-korea/
              sudo mv /tmp/main.py /opt/buddha-korea/
              sudo mv /tmp/tradition_normalizer.py /opt/buddha-korea/

              # 권한 설정
              sudo chown appuser:appuser /opt/buddha-korea/*.html
              sudo chown appuser:appuser /opt/buddha-korea/*.py

              # 컨테이너에 복사
              sudo docker cp /opt/buddha-korea/index.html buddhakorea-fastapi:/app/
              sudo docker cp /opt/buddha-korea/main.py buddhakorea-fastapi:/app/
              sudo docker cp /opt/buddha-korea/tradition_normalizer.py buddhakorea-fastapi:/app/

              # 컨테이너 내 권한 설정
              sudo docker exec -u root buddhakorea-fastapi chown buddha:buddha /app/index.html /app/main.py /app/tradition_normalizer.py

              echo 'Deployment completed!'
            "

      - name: Health Check
        run: |
          sleep 10
          STATUS=$(curl -s -o /dev/null -w "%{http_code}" https://ai.buddhakorea.com/api/health)
          if [ "$STATUS" != "200" ]; then
            echo "Health check failed with status: $STATUS"
            exit 1
          fi
          echo "Health check passed!"

      - name: Rollback on Failure
        if: failure()
        run: |
          gcloud compute ssh ${{ secrets.VM_NAME }} \
            --tunnel-through-iap \
            --zone=${{ secrets.VM_ZONE }} \
            --command="
              if [ -f /opt/buddha-korea/index.html.bak ]; then
                sudo mv /opt/buddha-korea/index.html.bak /opt/buddha-korea/index.html
                sudo docker cp /opt/buddha-korea/index.html buddhakorea-fastapi:/app/
                echo 'Rollback completed!'
              fi
            "
```

## 1.6 브랜치 보호 규칙 설정

```
GitHub Repository > Settings > Branches > Add rule

main 브랜치:
- [x] Require pull request before merging
- [x] Require status checks to pass before merging
  - [x] Require branches to be up to date
  - Status check: "Deploy to VM"
- [x] Do not allow bypassing the above settings
```

## 1.7 시크릿 스캐닝 활성화

```bash
# .pre-commit-config.yaml 생성
cat > .pre-commit-config.yaml << 'EOF'
repos:
  - repo: https://github.com/Yelp/detect-secrets
    rev: v1.4.0
    hooks:
      - id: detect-secrets
        args: ['--baseline', '.secrets.baseline']

  - repo: https://github.com/pre-commit/pre-commit-hooks
    rev: v4.5.0
    hooks:
      - id: check-added-large-files
      - id: check-merge-conflict
EOF

# 초기 시크릿 베이스라인 생성
detect-secrets scan > .secrets.baseline
```

**체크포인트 Phase 1:**
- [ ] Workload Identity Pool 생성
- [ ] OIDC Provider 설정
- [ ] 서비스 계정 생성 및 권한 부여
- [ ] IAP 터널 설정
- [ ] GitHub Secrets 설정
- [ ] 워크플로우 파일 작성
- [ ] 브랜치 보호 규칙 설정
- [ ] 테스트 배포 성공

---

# Phase 2: 모니터링 + 구조화된 로깅

## 2.1 Cloud Ops Agent 설치

```bash
# VM에 SSH 접속
gcloud compute ssh buddhakorea-rag-server --zone=us-central1-a --tunnel-through-iap

# Ops Agent 설치
curl -sSO https://dl.google.com/cloudagents/add-google-cloud-ops-agent-repo.sh
sudo bash add-google-cloud-ops-agent-repo.sh --also-install

# 상태 확인
sudo systemctl status google-cloud-ops-agent
```

## 2.2 Docker 컨테이너 로그 수집

```bash
sudo tee /etc/google-cloud-ops-agent/config.yaml << 'EOF'
logging:
  receivers:
    docker_logs:
      type: files
      include_paths:
        - /var/lib/docker/containers/*/*.log
      record_log_file_path: true

    app_json_logs:
      type: files
      include_paths:
        - /opt/buddha-korea/logs/*.json
      record_log_file_path: true

  processors:
    parse_json:
      type: parse_json
      field: message
      time_key: timestamp
      time_format: "%Y-%m-%dT%H:%M:%S.%LZ"

  service:
    pipelines:
      default_pipeline:
        receivers: [docker_logs, app_json_logs]
        processors: [parse_json]

metrics:
  receivers:
    hostmetrics:
      type: hostmetrics
      collection_interval: 60s
  service:
    pipelines:
      default_pipeline:
        receivers: [hostmetrics]
EOF

sudo systemctl restart google-cloud-ops-agent
```

## 2.3 구조화된 로깅 적용 (FastAPI)

`/opt/buddha-korea/logging_config.py` 추가:

```python
import json
import logging
import sys
from datetime import datetime
from typing import Optional

class GCPJSONFormatter(logging.Formatter):
    """Cloud Logging에 최적화된 JSON 포맷터"""

    def format(self, record):
        # 심각도 매핑
        severity_map = {
            'DEBUG': 'DEBUG',
            'INFO': 'INFO',
            'WARNING': 'WARNING',
            'ERROR': 'ERROR',
            'CRITICAL': 'CRITICAL'
        }

        log_entry = {
            "severity": severity_map.get(record.levelname, 'DEFAULT'),
            "message": record.getMessage(),
            "timestamp": datetime.utcnow().isoformat() + "Z",
            "logging.googleapis.com/sourceLocation": {
                "file": record.pathname,
                "line": record.lineno,
                "function": record.funcName
            }
        }

        # 요청 ID가 있으면 추가 (분산 추적용)
        if hasattr(record, 'request_id'):
            log_entry["logging.googleapis.com/trace"] = record.request_id

        # 추가 컨텍스트
        if hasattr(record, 'user_query'):
            log_entry["user_query"] = record.user_query
        if hasattr(record, 'tradition'):
            log_entry["tradition"] = record.tradition

        # 예외 정보
        if record.exc_info:
            log_entry["exception"] = self.formatException(record.exc_info)

        return json.dumps(log_entry, ensure_ascii=False)

def setup_gcp_logging():
    """GCP 최적화 로깅 설정"""
    handler = logging.StreamHandler(sys.stdout)
    handler.setFormatter(GCPJSONFormatter())

    root_logger = logging.getLogger()
    root_logger.handlers = [handler]
    root_logger.setLevel(logging.INFO)

    # 노이즈 줄이기
    logging.getLogger("uvicorn.access").setLevel(logging.WARNING)
    logging.getLogger("chromadb").setLevel(logging.WARNING)
    logging.getLogger("httpx").setLevel(logging.WARNING)
```

## 2.4 Uptime Check 설정

```bash
# GCP Console 또는 CLI
gcloud monitoring uptime-check-configs create ai-buddhakorea-health \
  --display-name="ai.buddhakorea.com Health" \
  --resource-type=uptime-url \
  --monitored-resource-labels=host=ai.buddhakorea.com \
  --http-check-path=/api/health \
  --http-check-port=443 \
  --timeout=10s \
  --period=60s
```

## 2.5 대시보드 생성

```bash
cat > /tmp/dashboard.json << 'EOF'
{
  "displayName": "Buddha Korea - Production",
  "gridLayout": {
    "columns": "2",
    "widgets": [
      {
        "title": "CPU Usage",
        "xyChart": {
          "dataSets": [{
            "timeSeriesQuery": {
              "timeSeriesFilter": {
                "filter": "resource.type=\"gce_instance\" AND metric.type=\"compute.googleapis.com/instance/cpu/utilization\"",
                "aggregation": {"alignmentPeriod": "60s", "perSeriesAligner": "ALIGN_MEAN"}
              }
            }
          }]
        }
      },
      {
        "title": "Memory Usage",
        "xyChart": {
          "dataSets": [{
            "timeSeriesQuery": {
              "timeSeriesFilter": {
                "filter": "resource.type=\"gce_instance\" AND metric.type=\"agent.googleapis.com/memory/percent_used\"",
                "aggregation": {"alignmentPeriod": "60s", "perSeriesAligner": "ALIGN_MEAN"}
              }
            }
          }]
        }
      },
      {
        "title": "Uptime Check",
        "xyChart": {
          "dataSets": [{
            "timeSeriesQuery": {
              "timeSeriesFilter": {
                "filter": "metric.type=\"monitoring.googleapis.com/uptime_check/check_passed\"",
                "aggregation": {"alignmentPeriod": "60s", "perSeriesAligner": "ALIGN_FRACTION_TRUE"}
              }
            }
          }]
        }
      },
      {
        "title": "Disk Usage",
        "xyChart": {
          "dataSets": [{
            "timeSeriesQuery": {
              "timeSeriesFilter": {
                "filter": "resource.type=\"gce_instance\" AND metric.type=\"agent.googleapis.com/disk/percent_used\"",
                "aggregation": {"alignmentPeriod": "60s", "perSeriesAligner": "ALIGN_MEAN"}
              }
            }
          }]
        }
      }
    ]
  }
}
EOF

gcloud monitoring dashboards create --config-from-file=/tmp/dashboard.json
```

**체크포인트 Phase 2:**
- [ ] Ops Agent 설치 완료
- [ ] Docker 로그 수집 설정
- [ ] 구조화된 로깅 적용
- [ ] Uptime Check 동작 확인
- [ ] 대시보드 생성 완료

---

# Phase 3: Alerting 설정

## 3.1 알림 채널 생성

```bash
# 이메일 알림
gcloud beta monitoring channels create \
  --display-name="Admin Email" \
  --type=email \
  --channel-labels=email_address=YOUR_EMAIL@gmail.com

# Slack 알림 (선택)
# gcloud beta monitoring channels create \
#   --display-name="Buddha Korea Slack" \
#   --type=slack \
#   --channel-labels=channel_name=#buddha-korea-alerts,auth_token=xoxb-...
```

## 3.2 알림 정책

| 알림 | 조건 | 심각도 | 조치 |
|------|------|--------|------|
| 서비스 다운 | Uptime check 3분간 실패 | 🔴 Critical | 즉시 확인 |
| 고 CPU | CPU > 80% 5분간 지속 | 🟡 Warning | 모니터링 |
| 디스크 부족 | 디스크 > 85% | 🟡 Warning | 정리 필요 |
| 메모리 부족 | 메모리 > 90% | 🟡 Warning | 스케일업 검토 |
| 비용 초과 | 월 $50 초과 | 🟡 Warning | 비용 최적화 |

```bash
# 서비스 다운 알림
gcloud alpha monitoring policies create \
  --display-name="Service Down Alert" \
  --condition-display-name="Uptime check failed" \
  --condition-filter='metric.type="monitoring.googleapis.com/uptime_check/check_passed" AND resource.type="uptime_url"' \
  --condition-threshold-value=1 \
  --condition-threshold-comparison=COMPARISON_LT \
  --condition-threshold-duration=180s \
  --notification-channels=YOUR_CHANNEL_ID \
  --combiner=OR
```

**체크포인트 Phase 3:**
- [ ] 이메일 알림 채널 생성
- [ ] 서비스 다운 알림 테스트
- [ ] CPU/디스크/메모리 알림 생성
- [ ] 비용 알림 설정

---

# Phase 4: 백업/재해 복구

## 4.1 백업 전략

| 데이터 | 백업 주기 | 보관 기간 | 위치 |
|--------|----------|----------|------|
| ChromaDB | 일간 | 7일 | GCS |
| Redis | 일간 | 3일 | GCS |
| .env | 변경 시 | 30일 | Secret Manager |

## 4.2 GCS 버킷 생성

```bash
# 백업 버킷 생성
gsutil mb -l us-central1 gs://buddhakorea-backups

# 수명 주기 정책 (7일 후 자동 삭제)
cat > /tmp/lifecycle.json << 'EOF'
{
  "lifecycle": {
    "rule": [
      {
        "action": {"type": "Delete"},
        "condition": {"age": 7}
      }
    ]
  }
}
EOF
gsutil lifecycle set /tmp/lifecycle.json gs://buddhakorea-backups
```

## 4.3 백업 스크립트

```bash
# /opt/buddha-korea/scripts/backup.sh
#!/bin/bash
set -e

DATE=$(date +%Y%m%d_%H%M%S)
BUCKET=gs://buddhakorea-backups
LOG_FILE=/var/log/backup.log

log() {
    echo "[$(date '+%Y-%m-%d %H:%M:%S')] $1" | tee -a $LOG_FILE
}

log "Starting backup..."

# ChromaDB 백업
log "Backing up ChromaDB..."
tar -czf /tmp/chroma_db_$DATE.tar.gz -C /opt/buddha-korea chroma_db
gsutil cp /tmp/chroma_db_$DATE.tar.gz $BUCKET/chroma/
rm /tmp/chroma_db_$DATE.tar.gz

# Redis 백업
log "Backing up Redis..."
docker exec buddhakorea-redis redis-cli BGSAVE
sleep 5
docker cp buddhakorea-redis:/data/dump.rdb /tmp/redis_$DATE.rdb
gsutil cp /tmp/redis_$DATE.rdb $BUCKET/redis/
rm /tmp/redis_$DATE.rdb

log "Backup completed!"

# 오래된 백업 정리 (로컬)
find /tmp -name "*.tar.gz" -mtime +1 -delete 2>/dev/null || true
find /tmp -name "*.rdb" -mtime +1 -delete 2>/dev/null || true
```

## 4.4 Cron 설정

```bash
# 매일 새벽 3시 백업
sudo crontab -e
# 추가:
0 3 * * * /opt/buddha-korea/scripts/backup.sh >> /var/log/backup.log 2>&1
```

## 4.5 복구 절차

```bash
# ChromaDB 복구
gsutil cp gs://buddhakorea-backups/chroma/chroma_db_YYYYMMDD.tar.gz /tmp/
tar -xzf /tmp/chroma_db_YYYYMMDD.tar.gz -C /opt/buddha-korea/
docker restart buddhakorea-fastapi

# Redis 복구
gsutil cp gs://buddhakorea-backups/redis/redis_YYYYMMDD.rdb /tmp/
docker cp /tmp/redis_YYYYMMDD.rdb buddhakorea-redis:/data/dump.rdb
docker restart buddhakorea-redis
```

**체크포인트 Phase 4:**
- [ ] GCS 백업 버킷 생성
- [ ] 백업 스크립트 작성
- [ ] Cron 설정
- [ ] 복구 테스트 실행

---

# Phase 5: LLM 비용 최적화

## 5.1 Redis 기반 응답 캐싱

```python
# /opt/buddha-korea/cache_llm.py
import hashlib
from typing import Optional
from redis import Redis

def get_semantic_cache_key(query: str, tradition: str) -> str:
    """쿼리와 전통을 기반으로 캐시 키 생성"""
    normalized = f"{tradition}:{query.strip().lower()}"
    return f"llm:v1:{hashlib.sha256(normalized.encode()).hexdigest()[:16]}"

async def get_cached_response(
    query: str,
    tradition: str,
    redis_client: Redis
) -> Optional[str]:
    """캐시된 응답 조회"""
    cache_key = get_semantic_cache_key(query, tradition)

    if cached := redis_client.get(cache_key):
        # 캐시 히트 메트릭 기록
        redis_client.incr("metrics:cache:hits")
        return cached.decode("utf-8")

    redis_client.incr("metrics:cache:misses")
    return None

async def cache_response(
    query: str,
    tradition: str,
    response: str,
    redis_client: Redis,
    ttl_hours: int = 24
) -> None:
    """응답 캐싱"""
    cache_key = get_semantic_cache_key(query, tradition)
    redis_client.setex(cache_key, ttl_hours * 3600, response)
```

## 5.2 캐시 히트율 모니터링

```bash
# 캐시 통계 확인
redis-cli -a YOUR_PASSWORD <<EOF
GET metrics:cache:hits
GET metrics:cache:misses
EOF
```

## 5.3 비용 절감 예상

| 항목 | 현재 | 캐싱 후 | 절감 |
|------|------|---------|------|
| Gemini API 호출 | 100회/일 | 60회/일 | 40% |
| 월간 API 비용 | ~$30 | ~$18 | ~$12 |

**체크포인트 Phase 5:**
- [ ] cache_llm.py 구현
- [ ] main.py에 캐싱 로직 통합
- [ ] 캐시 히트율 모니터링 설정

---

# Phase 6: Staging 환경 (선택)

## 6.1 Cloud Run으로 Staging (비용 효율)

```bash
# 기존 Cloud Run을 Staging으로 사용
# cloudbuild.yaml 수정하여 staging 브랜치에서만 배포

# DNS 설정
# staging.buddhakorea.com → Cloud Run URL
```

## 6.2 워크플로우

```
feature 브랜치 작업
       ↓
   PR → staging 브랜치
       ↓
   Cloud Run 자동 배포 → staging.buddhakorea.com
       ↓
   테스트 확인
       ↓
   PR → main 브랜치
       ↓
   VM 자동 배포 → ai.buddhakorea.com (Production)
```

---

# 실행 순서 요약

```
Week 1:
├── Day 1: Phase 0 - 인프라 정리 (15분)
├── Day 1: Phase 1 - 보안 강화 CI/CD (1.5시간)
├── Day 2: Phase 2 - 모니터링 설치 (1시간)
└── Day 2: Phase 3 - Alerting 설정 (30분)

Week 2:
├── Day 3: Phase 4 - 백업/재해 복구 (1시간)
└── Day 3: Phase 5 - LLM 비용 최적화 (1시간)

Week 3+ (선택):
└── Phase 6 - Staging 환경 구축 (2시간)
```

---

# 비용 예상

| 항목 | 현재 | 변경 후 | 비고 |
|------|------|---------|------|
| VM (Production) | ~$25/월 | ~$25/월 | 변경 없음 |
| Cloud Monitoring | $0 | $0 | 무료 티어 |
| GitHub Actions | $0 | $0 | 무료 2000분/월 |
| GCS (백업) | - | ~$1/월 | 5GB 이하 |
| LLM API | ~$30/월 | ~$18/월 | 캐싱 적용 |
| Cloud Run | ~$5/월 | $0 | 비활성화 |

**예상 월 절감: ~$17/월**

---

# 완료 후 아키텍처

```
┌─────────────────────────────────────────────────────────────────┐
│                         개발자                                   │
└───────────────────────────┬─────────────────────────────────────┘
                            │ git push (main)
                            ▼
┌─────────────────────────────────────────────────────────────────┐
│                      GitHub Actions                              │
│  ┌─────────────────────────────────────────────────────────────┐│
│  │ Workload Identity Federation → GCP 인증 → IAP 터널 배포      ││
│  └─────────────────────────────────────────────────────────────┘│
└───────────────────────────┬─────────────────────────────────────┘
                            │ IAP tunnel (SSH 키 불필요)
                            ▼
┌─────────────────────────────────────────────────────────────────┐
│                    GCE VM (Production)                           │
│  ┌─────────┐  ┌─────────┐  ┌─────────┐  ┌─────────┐            │
│  │  Nginx  │→ │ FastAPI │→ │ ChromaDB│  │  Redis  │            │
│  │  :443   │  │  :8000  │  │ (벡터DB)│  │ (캐시)  │            │
│  └─────────┘  └─────────┘  └─────────┘  └─────────┘            │
│                     │                                            │
│           ┌─────────┴─────────┐                                  │
│           ▼                   ▼                                  │
│  ┌──────────────┐    ┌──────────────┐                           │
│  │ Ops Agent    │    │ 백업 스크립트 │                           │
│  │ (모니터링)    │    │ (Cron 3AM)   │                           │
│  └──────┬───────┘    └──────┬───────┘                           │
└─────────┼───────────────────┼───────────────────────────────────┘
          │                   │
          ▼                   ▼
┌─────────────────────┐ ┌─────────────────────┐
│  Cloud Monitoring   │ │   GCS Backup        │
│  ├── Dashboard      │ │   ├── chroma/       │
│  ├── Uptime Check   │ │   └── redis/        │
│  └── Alerts → Email │ └─────────────────────┘
└─────────────────────┘
```

---

# 전체 체크리스트

## Phase 0: 인프라 정리
- [ ] Cloud Build 트리거 비활성화
- [ ] cloudbuild.yaml 비활성화

## Phase 1: 보안 강화 CI/CD
- [ ] Workload Identity Pool 생성
- [ ] OIDC Provider 설정
- [ ] 서비스 계정 생성/권한 부여
- [ ] IAP 터널 설정
- [ ] GitHub Secrets 설정
- [ ] 워크플로우 파일 작성
- [ ] 브랜치 보호 규칙 설정
- [ ] 테스트 배포 성공

## Phase 2: 모니터링
- [ ] Ops Agent 설치
- [ ] Docker 로그 수집 설정
- [ ] 구조화된 로깅 적용
- [ ] Uptime Check 생성
- [ ] 대시보드 생성

## Phase 3: Alerting
- [ ] 알림 채널 생성
- [ ] 서비스 다운 알림
- [ ] 리소스 알림 (CPU, 디스크, 메모리)
- [ ] 비용 알림

## Phase 4: 백업/재해 복구
- [ ] GCS 백업 버킷 생성
- [ ] 백업 스크립트 작성
- [ ] Cron 설정
- [ ] 복구 테스트

## Phase 5: LLM 비용 최적화
- [ ] Redis 캐싱 구현
- [ ] 캐시 히트율 모니터링

## Phase 6: Staging (선택)
- [ ] Staging 환경 결정
- [ ] 브랜치 전략 적용

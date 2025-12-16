# Buddha Korea 배포 가이드

이 문서는 여러 배포 관련 문서를 통합한 것입니다.

---

## 목차

1. [빠른 시작](#빠른-시작)
2. [Hetzner 서버 배포](#hetzner-서버-배포)
3. [Docker 배포](#docker-배포)
4. [프로덕션 설정](#프로덕션-설정)
5. [롤백 절차](#롤백-절차)

---

# Buddha Korea RAG - Quick Start Guide 🚀

**ChromaDB 호스팅 및 Beta 서비스 론칭**

예상 소요 시간: **2-3시간**

---

## 📝 준비물 체크리스트

- [x] ChromaDB 데이터베이스 (3.5GB) ✅
- [x] 99,723 embedded documents ✅
- [ ] VPS 계정 (Hetzner/DigitalOcean/Vultr)
- [ ] 도메인 (buddhakorea.com 소유 확인)
- [ ] API 키 (OpenAI/Anthropic)

---

## ⚡ 5단계 빠른 배포

### Step 1: VPS 구매 (10분)

**추천: Hetzner CPX21** - €5.83/월 (~$6)
- https://www.hetzner.com/cloud
- 3 vCPU, 4GB RAM, 80GB SSD
- 위치: Finland (한국과 가까움)

**대안: DigitalOcean** - $24/월
- https://www.digitalocean.com/
- 2 vCPU, 4GB RAM, 80GB SSD
- 위치: Singapore

**서버 생성 시**:
```
OS: Ubuntu 24.04 LTS
SSH Key: 업로드 (또는 비밀번호 사용)
Hostname: buddhakorea-beta
```

### Step 2: 서버 기본 세팅 (15분)

**로컬에서 서버 접속**:
```bash
ssh root@YOUR_SERVER_IP
```

**Docker 설치**:
```bash
# 시스템 업데이트
apt update && apt upgrade -y

# Docker 설치
curl -fsSL https://get.docker.com | sh

# Docker Compose 설치
apt install -y docker-compose-plugin

# 타임존 설정
timedatectl set-timezone Asia/Seoul

# 방화벽 설정
apt install -y ufw
ufw allow ssh
ufw allow 80/tcp
ufw allow 443/tcp
ufw enable
```

### Step 3: ChromaDB 업로드 (30-60분)

**로컬 컴퓨터에서**:
```bash
# 프로젝트 디렉토리로 이동
cd /Users/vairocana/Desktop/buddhakorea/buddha-korea-notebook-exp/opennotebook

# ChromaDB 압축 (3.5GB -> ~1.5GB)
tar -czf chroma_db.tar.gz chroma_db/

# 서버에 업로드 (10-20분 소요)
scp chroma_db.tar.gz root@YOUR_SERVER_IP:~/
```

**서버에서**:
```bash
# 압축 해제
cd ~
tar -xzf chroma_db.tar.gz
rm chroma_db.tar.gz

# 확인
ls -lh chroma_db/
# chroma.sqlite3 파일이 ~3.5GB여야 함
```

### Step 4: 애플리케이션 배포 (20분)

**로컬에서 파일 업로드**:
```bash
cd /Users/vairocana/Desktop/buddhakorea/buddha-korea-notebook-exp/opennotebook

# 배포 패키지 생성
tar -czf buddha-app.tar.gz \
  main.py \
  gemini_query_embedder.py \
  hyde.py \
  reranker.py \
  test_frontend.html \
  requirements.txt \
  docker-compose.yml \
  Dockerfile \
  nginx.conf \
  .dockerignore \
  source_explorer/

# 업로드
scp buddha-app.tar.gz root@YOUR_SERVER_IP:~/
```

**서버에서 배포**:
```bash
# 압축 해제
cd ~
tar -xzf buddha-app.tar.gz
rm buddha-app.tar.gz

# 디렉토리 구조 확인
ls -la
# main.py, docker-compose.yml, chroma_db/ 등이 있어야 함
```

**환경 변수 설정**:
```bash
# .env 파일 생성
nano .env
```

**아래 내용 붙여넣기** (API 키는 실제 값으로 변경):
```bash
# API Keys (실제 키로 변경!)
OPENAI_API_KEY=sk-your-openai-key-here
ANTHROPIC_API_KEY=sk-ant-your-anthropic-key-here

# Model Configuration
LLM_MODEL=claude-3-5-sonnet-20241022
EMBEDDING_MODEL=BAAI/bge-m3

# ChromaDB
CHROMA_COLLECTION_NAME=cbeta_sutras_gemini

# API
ALLOWED_ORIGINS=https://buddhakorea.com,https://www.buddhakorea.com,https://beta.buddhakorea.com

# Rate Limiting
RATE_LIMIT_PER_HOUR=100

# HyDE (optional)
USE_HYDE=false
USE_GEMINI_FOR_QUERIES=false
```

저장: `Ctrl+O` → `Enter` → `Ctrl+X`

**SSL 디렉토리 생성** (임시):
```bash
mkdir -p ssl static logs

# 임시 자체 서명 인증서 (나중에 Let's Encrypt로 교체)
openssl req -x509 -nodes -days 365 -newkey rsa:2048 \
  -keyout ssl/privkey.pem -out ssl/fullchain.pem \
  -subj "/CN=beta.buddhakorea.com"
```

**Docker 실행**:
```bash
# 빌드 및 시작 (첫 실행: 5-10분)
docker compose build
docker compose up -d

# 상태 확인
docker compose ps
```

**기대 출력**:
```
NAME                   STATUS    PORTS
buddhakorea-chromadb   Up        0.0.0.0:8001->8000/tcp
buddhakorea-fastapi    Up        0.0.0.0:8000->8000/tcp
buddhakorea-nginx      Up        0.0.0.0:80->80/tcp, 0.0.0.0:443->443/tcp
```

### Step 5: DNS 설정 및 SSL (15분)

**DNS 레코드 추가** (buddhakorea.com 관리 페이지에서):
```
Type: A
Name: beta
Value: YOUR_SERVER_IP
TTL: 3600
```

**DNS 전파 대기** (5-10분):
```bash
# 로컬에서 확인
nslookup beta.buddhakorea.com
# YOUR_SERVER_IP가 나와야 함
```

**Let's Encrypt SSL 인증서 발급** (서버에서):
```bash
# Certbot 설치
apt install -y certbot

# 인증서 발급 (임시로 nginx 중지)
docker compose stop nginx

certbot certonly --standalone \
  -d beta.buddhakorea.com \
  --email your-email@example.com \
  --agree-tos \
  --no-eff-email

# SSL 파일 복사
cp /etc/letsencrypt/live/beta.buddhakorea.com/fullchain.pem ssl/
cp /etc/letsencrypt/live/beta.buddhakorea.com/privkey.pem ssl/

# Nginx 재시작
docker compose start nginx
```

---

## ✅ 테스트

### 1. Health Check
```bash
curl https://beta.buddhakorea.com/api/health
```

**기대 출력**:
```json
{
  "status": "healthy",
  "version": "0.1.0",
  "chroma_connected": true,
  "llm_configured": true
}
```

### 2. Collections 확인
```bash
curl https://beta.buddhakorea.com/api/collections
```

**기대 출력**:
```json
[
  {
    "name": "cbeta_sutras_gemini",
    "document_count": 99723,
    "language": "multilingual",
    "description": "..."
  }
]
```

### 3. 실제 검색 테스트
```bash
curl -X POST https://beta.buddhakorea.com/api/chat \
  -H "Content-Type: application/json" \
  -d '{
    "query": "무상에 대해 설명해주세요",
    "max_sources": 3
  }'
```

### 4. 브라우저 테스트
https://beta.buddhakorea.com 접속

---

## 🎉 완료!

Buddha Korea RAG Beta가 라이브되었습니다!

**URL**: https://beta.buddhakorea.com

---

## 📊 비용 요약

| 항목 | 비용 |
|------|------|
| VPS (Hetzner) | $6/월 |
| SSL (Let's Encrypt) | $0 |
| OpenAI API | $5-20/월 (사용량) |
| Anthropic API | $10-30/월 (사용량) |
| **총 예상** | **$21-56/월** |

---

## 🔧 관리 명령어

```bash
# 로그 확인
docker compose logs -f

# 특정 서비스 로그
docker compose logs -f fastapi

# 재시작
docker compose restart

# 중지
docker compose stop

# 시작
docker compose start

# 완전 재빌드
docker compose down
docker compose build --no-cache
docker compose up -d

# 디스크 사용량 확인
df -h
docker system df

# 리소스 모니터링
docker stats
```

---

## 🚨 문제 해결

### ChromaDB 연결 실패
```bash
# ChromaDB 로그 확인
docker compose logs chromadb

# 권한 확인
ls -la chroma_db/

# 재시작
docker compose restart chromadb
```

### FastAPI 오류
```bash
# 로그 확인
docker compose logs fastapi
tail -f logs/app.log

# 환경변수 확인
docker compose exec fastapi env | grep API_KEY

# 재시작
docker compose restart fastapi
```

### SSL 인증서 오류
```bash
# 인증서 확인
certbot certificates

# 갱신
certbot renew

# Docker에 복사
cp /etc/letsencrypt/live/beta.buddhakorea.com/*.pem ssl/
docker compose restart nginx
```

---

## 📈 다음 단계

1. ✅ Beta 서비스 론칭 완료
2. 🔄 사용자 피드백 수집
3. 🔧 성능 모니터링 (Grafana 설치 권장)
4. 📊 사용량 분석
5. 🚀 정식 서비스로 확대

---

## 💡 추가 최적화 (선택사항)

### Uptime 모니터링
- **UptimeRobot** (무료): https://uptimerobot.com/
- 5분마다 https://beta.buddhakorea.com/api/health 체크

### 백업 자동화
```bash
# Cron job 추가
crontab -e

# 매일 새벽 3시 백업
0 3 * * * cd ~/buddhakorea && tar -czf backup_$(date +\%Y\%m\%d).tar.gz chroma_db/
```

### 로그 로테이션
```bash
# logrotate 설정
sudo nano /etc/logrotate.d/buddhakorea

# 내용:
/root/logs/*.log {
    daily
    rotate 7
    compress
    delaycompress
    missingok
    notifempty
}
```

---

**질문이나 문제가 있으면 DEPLOYMENT.md의 상세 가이드를 참고하세요!**


---


# Hetzner VM 배포 가이드

> **서버**: prod-main-01 (CX33)
> **사양**: 4 vCPU | 8GB RAM | 80GB SSD
> **비용**: €4.99/월 (~$5.50)
> **IP**: 157.180.72.0
> **접속**: `ssh prod`
> **마지막 업데이트**: 2025-12-09

---

## 목차

1. [아키텍처 개요](#1-아키텍처-개요)
2. [사전 요구사항](#2-사전-요구사항)
3. [Fix 1: docker-compose.yml 통일](#3-fix-1-docker-composeyml-통일)
4. [Fix 2: Redis 세션 통합](#4-fix-2-redis-세션-통합)
5. [배포 전 체크리스트](#5-배포-전-체크리스트)
6. [배포 절차](#6-배포-절차)
7. [배포 후 검증](#7-배포-후-검증)
8. [롤백 절차](#8-롤백-절차)
9. [모니터링 및 유지보수](#9-모니터링-및-유지보수)

---

## 1. 아키텍처 개요

### 목표 아키텍처

```
┌─────────────────────────────────────────────────────────────────────────┐
│  Hetzner VM: prod-main-01 (CX33)                                        │
│  4 vCPU | 8GB RAM | 80GB SSD | €4.99/mo                                │
├─────────────────────────────────────────────────────────────────────────┤
│                                                                         │
│  ┌─────────────────────────────────────────────────────────────────┐   │
│  │  Docker Engine (dockerd)                                         │   │
│  │                                                                   │   │
│  │  ┌─────────────┐  ┌─────────────┐  ┌─────────────────────────┐  │   │
│  │  │   nginx     │  │    redis    │  │        backend          │  │   │
│  │  │   :80/:443  │  │    :6379    │  │        :8000            │  │   │
│  │  │             │  │             │  │                         │  │   │
│  │  │ • SSL/TLS   │  │ • Sessions  │  │ • FastAPI + Gunicorn    │  │   │
│  │  │ • HTTPS     │  │ • Cache     │  │ • ChromaDB (파일 기반)  │  │   │
│  │  │ • Rate Limit│  │ • Analytics │  │ • Vertex AI 연동        │  │   │
│  │  └──────┬──────┘  └──────┬──────┘  └───────────┬─────────────┘  │   │
│  │         │                │                     │                 │   │
│  │         └────────────────┴─────────────────────┘                 │   │
│  │                          │                                       │   │
│  │                   buddhist-ai-network                            │   │
│  └─────────────────────────────────────────────────────────────────┘   │
│                                                                         │
│  ┌─────────────────────────────────────────────────────────────────┐   │
│  │  Volumes (Persistent Data)                                       │   │
│  │  ├── ./chroma_db/        (~3GB, 벡터 DB)                        │   │
│  │  ├── ./redis-data/       (세션 + 캐시)                          │   │
│  │  ├── ./logs/             (앱 로그)                              │   │
│  │  └── ./ssl/              (Let's Encrypt 인증서)                 │   │
│  └─────────────────────────────────────────────────────────────────┘   │
│                                                                         │
│  Ubuntu 22.04 LTS                                                       │
└─────────────────────────────────────────────────────────────────────────┘
```

### 외부 의존성

```
┌─────────────────────────────────────────────────────────────────────────┐
│                        External Services                                 │
├─────────────────────────────────────────────────────────────────────────┤
│                                                                         │
│  ┌─────────────────────────┐    ┌─────────────────────────────────┐   │
│  │  Google Cloud (Vertex)  │    │  Cloudflare / DNS Provider      │   │
│  │  └── us-central1        │    │  └── ai.buddhakorea.com         │   │
│  │      ├── gemini-embed   │    │      → 157.180.72.0             │   │
│  │      └── gemini-2.5-pro │    └─────────────────────────────────┘   │
│  └─────────────────────────┘                                           │
│                                                                         │
│  ┌─────────────────────────┐    ┌─────────────────────────────────┐   │
│  │  GitHub                 │    │  Let's Encrypt                  │   │
│  │  └── Actions (CI/CD)    │    │  └── SSL 인증서 자동 갱신       │   │
│  └─────────────────────────┘    └─────────────────────────────────┘   │
│                                                                         │
└─────────────────────────────────────────────────────────────────────────┘
```

### GCP → Hetzner 비용 비교

| 항목 | GCP (현재) | Hetzner (목표) | 절감 |
|------|-----------|----------------|------|
| VM 비용 | ~$120/월 | €4.99/월 (~$5.50) | **95%** |
| Vertex AI | ~$50-200/월 | ~$50-200/월 | 동일 |
| **총합** | **~$170-320/월** | **~$55-205/월** | **~$115/월** |

---

## 2. 사전 요구사항

### 2.1 Hetzner VM 초기 설정

```bash
# SSH 접속
ssh prod

# 시스템 업데이트
sudo apt update && sudo apt upgrade -y

# 필수 패키지 설치
sudo apt install -y \
    apt-transport-https \
    ca-certificates \
    curl \
    gnupg \
    lsb-release \
    git \
    htop \
    tmux \
    jq

# Docker 설치 (공식 방법)
curl -fsSL https://get.docker.com -o get-docker.sh
sudo sh get-docker.sh

# Docker Compose V2 설치
sudo apt install docker-compose-plugin -y

# 현재 사용자를 docker 그룹에 추가 (sudo 없이 docker 사용)
sudo usermod -aG docker $USER

# 로그아웃 후 재접속 필요
exit
ssh prod

# Docker 버전 확인
docker --version
docker compose version
```

### 2.2 방화벽 설정 (ufw)

```bash
# UFW 활성화 및 기본 규칙
sudo ufw default deny incoming
sudo ufw default allow outgoing

# SSH 허용 (반드시 먼저!)
sudo ufw allow ssh

# HTTP/HTTPS 허용
sudo ufw allow 80/tcp
sudo ufw allow 443/tcp

# UFW 활성화
sudo ufw enable

# 상태 확인
sudo ufw status verbose
```

### 2.3 디렉토리 구조 생성

```bash
# 앱 디렉토리 생성
sudo mkdir -p /opt/buddha-korea
sudo chown $USER:$USER /opt/buddha-korea
cd /opt/buddha-korea

# 필요한 하위 디렉토리
mkdir -p chroma_db logs redis-data ssl source_explorer css js
```

### 2.4 GCP 인증 설정 (Vertex AI용)

```bash
# 서비스 계정 키 파일 업로드 (로컬에서)
scp /path/to/service-account-key.json prod:/opt/buddha-korea/gcp-key.json

# VM에서 환경변수 설정
echo 'export GOOGLE_APPLICATION_CREDENTIALS="/opt/buddha-korea/gcp-key.json"' >> ~/.bashrc
source ~/.bashrc
```

---

## 3. Fix 1: docker-compose.yml 통일

### 3.1 문제점

```
현재 상태 (지킬 앤 하이드)
─────────────────────────────────────────────
docker-compose.yml (Dev)        docker-compose.production.yml (Prod)
├── ChromaDB (서버 모드)        ├── Redis ✓
├── FastAPI                     ├── FastAPI (파일 기반 Chroma)
├── Nginx                       └── Nginx
└── Redis ✗ (없음)

문제:
1. Dev에서 테스트한 것이 Prod에서 다르게 동작
2. 두 파일을 동기화해야 하는 부담
3. "내 컴퓨터에서는 되는데..." 문제 발생
```

### 3.2 해결: 단일 docker-compose.yml

`/opt/buddha-korea/docker-compose.yml`:

```yaml
# ============================================================
# Buddha Korea RAG Chatbot - Unified Docker Compose
# ============================================================
# 환경: 개발 + 프로덕션 통합 (Dev/Prod Parity)
# ChromaDB: 파일 기반 (./chroma_db)
# 마지막 업데이트: 2025-12-09

version: '3.8'

services:
  # ──────────────────────────────────────────────────────────
  # Redis: 세션 저장소 + LLM 응답 캐시 + 분석 데이터
  # ──────────────────────────────────────────────────────────
  redis:
    image: redis:7-alpine
    container_name: buddhakorea-redis
    command: redis-server /usr/local/etc/redis/redis.conf
    volumes:
      - ./redis.conf:/usr/local/etc/redis/redis.conf:ro
      - ./redis-data:/data
    environment:
      - REDIS_PASSWORD=${REDIS_PASSWORD:-buddha-korea-redis-2024}
    ports:
      - "127.0.0.1:6379:6379"  # 로컬만 노출 (보안)
    restart: unless-stopped
    healthcheck:
      test: ["CMD", "redis-cli", "-a", "${REDIS_PASSWORD:-buddha-korea-redis-2024}", "ping"]
      interval: 10s
      timeout: 5s
      retries: 5
      start_period: 10s
    networks:
      - buddhist-ai-network
    deploy:
      resources:
        limits:
          cpus: '0.5'
          memory: 512M
        reservations:
          cpus: '0.25'
          memory: 256M
    logging:
      driver: "json-file"
      options:
        max-size: "10m"
        max-file: "3"

  # ──────────────────────────────────────────────────────────
  # Backend: FastAPI + 파일 기반 ChromaDB
  # ──────────────────────────────────────────────────────────
  backend:
    build:
      context: .
      dockerfile: Dockerfile
    container_name: buddhakorea-backend
    depends_on:
      redis:
        condition: service_healthy
    volumes:
      - ./chroma_db:/app/chroma_db        # ChromaDB 벡터 데이터
      - ./logs:/app/logs                   # 앱 로그
      - ./source_explorer:/app/source_explorer  # 경전 요약 데이터
    environment:
      # ─── GCP Vertex AI ───
      - GCP_PROJECT_ID=${GCP_PROJECT_ID}
      - GCP_LOCATION=${GCP_LOCATION:-us-central1}
      - GOOGLE_APPLICATION_CREDENTIALS=/app/gcp-key.json

      # ─── 모델 설정 ───
      - LLM_MODEL=${LLM_MODEL:-gemini-2.5-pro}
      - LLM_MODEL_FAST=${LLM_MODEL_FAST:-gemini-2.5-flash}
      - USE_GEMINI_FOR_QUERIES=${USE_GEMINI_FOR_QUERIES:-true}

      # ─── ChromaDB (파일 기반) ───
      - CHROMA_DB_PATH=./chroma_db
      - CHROMA_COLLECTION_NAME=${CHROMA_COLLECTION_NAME:-cbeta_sutras_gemini}

      # ─── Redis ───
      - REDIS_HOST=redis
      - REDIS_PORT=6379
      - REDIS_PASSWORD=${REDIS_PASSWORD:-buddha-korea-redis-2024}
      - REDIS_DB=0

      # ─── API 설정 ───
      - API_HOST=0.0.0.0
      - API_PORT=8000
      - ALLOWED_ORIGINS=${ALLOWED_ORIGINS:-https://ai.buddhakorea.com,https://buddhakorea.com}
      - RATE_LIMIT_PER_HOUR=${RATE_LIMIT_PER_HOUR:-100}
      - LOG_LEVEL=${LOG_LEVEL:-info}

      # ─── 검색 설정 ───
      - TOP_K_RETRIEVAL=${TOP_K_RETRIEVAL:-10}
      - TOP_K_RETRIEVAL_FAST=${TOP_K_RETRIEVAL_FAST:-5}
      - USE_HYDE=${USE_HYDE:-false}
    env_file:
      - .env
    ports:
      - "127.0.0.1:8000:8000"  # 로컬만 노출 (nginx가 프록시)
    restart: unless-stopped
    healthcheck:
      test: ["CMD", "curl", "-f", "http://localhost:8000/api/health"]
      interval: 30s
      timeout: 10s
      retries: 3
      start_period: 60s
    networks:
      - buddhist-ai-network
    deploy:
      resources:
        limits:
          cpus: '3'
          memory: 6G
        reservations:
          cpus: '1'
          memory: 2G
    logging:
      driver: "json-file"
      options:
        max-size: "50m"
        max-file: "5"

  # ──────────────────────────────────────────────────────────
  # Nginx: 리버스 프록시 + SSL + Rate Limiting
  # ──────────────────────────────────────────────────────────
  nginx:
    image: nginx:alpine
    container_name: buddhakorea-nginx
    depends_on:
      backend:
        condition: service_healthy
    volumes:
      - ./nginx.conf:/etc/nginx/nginx.conf:ro
      - ./ssl:/etc/nginx/ssl:ro
      - /var/www/certbot:/var/www/certbot:ro
    ports:
      - "80:80"
      - "443:443"
    restart: unless-stopped
    healthcheck:
      test: ["CMD", "curl", "-f", "http://localhost/api/health"]
      interval: 30s
      timeout: 5s
      retries: 3
    networks:
      - buddhist-ai-network
    logging:
      driver: "json-file"
      options:
        max-size: "20m"
        max-file: "3"

# ──────────────────────────────────────────────────────────
# Networks
# ──────────────────────────────────────────────────────────
networks:
  buddhist-ai-network:
    driver: bridge
    ipam:
      config:
        - subnet: 172.28.0.0/16

# ──────────────────────────────────────────────────────────
# Named Volumes (optional, for better management)
# ──────────────────────────────────────────────────────────
# volumes:
#   chroma-data:
#   redis-data:
```

### 3.3 환경 분리: .env 파일로

```bash
# .env.example (템플릿)
# ─────────────────────────────────────────────────────────────
# GCP Vertex AI
GCP_PROJECT_ID=gen-lang-client-0324154376
GCP_LOCATION=us-central1

# 모델 설정
LLM_MODEL=gemini-2.5-pro
LLM_MODEL_FAST=gemini-2.5-flash
USE_GEMINI_FOR_QUERIES=true

# ChromaDB
CHROMA_COLLECTION_NAME=cbeta_sutras_gemini

# Redis (프로덕션에서는 강력한 비밀번호 사용!)
REDIS_PASSWORD=your-strong-password-here

# API
ALLOWED_ORIGINS=https://ai.buddhakorea.com,https://buddhakorea.com
RATE_LIMIT_PER_HOUR=100
LOG_LEVEL=info

# 검색
TOP_K_RETRIEVAL=10
TOP_K_RETRIEVAL_FAST=5
USE_HYDE=false
```

---

## 4. Fix 2: Redis 세션 통합

### 4.1 문제점

```python
# 현재 main.py (line 122-123)
# In-memory session storage (for production, consider Redis)
CONVERSATION_SESSIONS: Dict[str, Dict[str, Any]] = {}

# 문제:
# 1. 서버 재시작 시 모든 세션 손실
# 2. 사용자의 후속 질문 컨텍스트 사라짐
# 3. "앞서 말한 내용" 참조 불가능
```

### 4.2 해결: Redis 세션 매니저

`/opt/buddha-korea/redis_session.py` (새 파일):

```python
"""
Redis Session Manager for Buddha Korea
======================================
서버 재시작에도 세션이 유지되는 Redis 기반 세션 관리

사용법:
    from redis_session import RedisSessionManager
    session_mgr = RedisSessionManager()

    # 세션 생성/조회
    session_id = session_mgr.create_or_get_session()

    # 세션 업데이트
    session_mgr.update_session(session_id, user_msg, assistant_msg, context, metadata)

    # 세션 컨텍스트 조회
    context = session_mgr.get_session_context(session_id)
"""

import os
import json
import uuid
from datetime import datetime, timedelta
from typing import Dict, List, Any, Optional
from loguru import logger

try:
    import redis
    REDIS_AVAILABLE = True
except ImportError:
    REDIS_AVAILABLE = False
    logger.warning("redis-py not installed. Falling back to in-memory sessions.")


class RedisSessionManager:
    """
    Redis 기반 세션 매니저
    Redis 사용 불가 시 자동으로 in-memory 폴백
    """

    # 설정 상수
    SESSION_TTL_SECONDS = 3600  # 1시간
    MAX_MESSAGES_PER_SESSION = 20
    MAX_CONVERSATION_HISTORY_TURNS = 5
    SESSION_PREFIX = "buddha:session:"

    def __init__(
        self,
        host: str = None,
        port: int = None,
        password: str = None,
        db: int = 0
    ):
        """
        Redis 세션 매니저 초기화

        환경변수 또는 매개변수로 설정:
        - REDIS_HOST
        - REDIS_PORT
        - REDIS_PASSWORD
        - REDIS_DB
        """
        self.host = host or os.getenv("REDIS_HOST", "localhost")
        self.port = port or int(os.getenv("REDIS_PORT", "6379"))
        self.password = password or os.getenv("REDIS_PASSWORD")
        self.db = db or int(os.getenv("REDIS_DB", "0"))

        self.redis_client: Optional[redis.Redis] = None
        self._fallback_sessions: Dict[str, Dict[str, Any]] = {}

        self._connect()

    def _connect(self) -> bool:
        """Redis 연결 시도"""
        if not REDIS_AVAILABLE:
            logger.warning("Redis not available, using in-memory fallback")
            return False

        try:
            self.redis_client = redis.Redis(
                host=self.host,
                port=self.port,
                password=self.password,
                db=self.db,
                decode_responses=True,
                socket_timeout=5,
                socket_connect_timeout=5,
                retry_on_timeout=True
            )
            # 연결 테스트
            self.redis_client.ping()
            logger.info(f"✅ Redis connected: {self.host}:{self.port}")
            return True
        except Exception as e:
            logger.warning(f"Redis connection failed: {e}. Using in-memory fallback.")
            self.redis_client = None
            return False

    def _get_key(self, session_id: str) -> str:
        """Redis 키 생성"""
        return f"{self.SESSION_PREFIX}{session_id}"

    def _serialize(self, data: Dict[str, Any]) -> str:
        """세션 데이터 직렬화"""
        # datetime 객체 처리
        def convert(obj):
            if isinstance(obj, datetime):
                return obj.isoformat()
            return obj

        return json.dumps(data, default=convert, ensure_ascii=False)

    def _deserialize(self, data: str) -> Dict[str, Any]:
        """세션 데이터 역직렬화"""
        parsed = json.loads(data)

        # datetime 문자열 복원
        for key in ['created_at', 'last_accessed']:
            if key in parsed and isinstance(parsed[key], str):
                try:
                    parsed[key] = datetime.fromisoformat(parsed[key])
                except:
                    pass

        return parsed

    def create_or_get_session(self, session_id: Optional[str] = None) -> str:
        """
        세션 생성 또는 기존 세션 조회

        Args:
            session_id: 기존 세션 ID (없으면 새로 생성)

        Returns:
            세션 ID
        """
        # 기존 세션 확인
        if session_id:
            session = self._get_session(session_id)
            if session:
                # 세션 갱신
                self._touch_session(session_id)
                logger.debug(f"Reusing session {session_id[:8]}...")
                return session_id

        # 새 세션 생성
        new_id = str(uuid.uuid4())
        session_data = {
            'session_id': new_id,
            'created_at': datetime.now(),
            'last_accessed': datetime.now(),
            'messages': [],
            'context_chunks': [],
            'metadata': {}
        }

        self._set_session(new_id, session_data)
        logger.info(f"Created new session {new_id[:8]}...")
        return new_id

    def _get_session(self, session_id: str) -> Optional[Dict[str, Any]]:
        """세션 조회"""
        if self.redis_client:
            try:
                data = self.redis_client.get(self._get_key(session_id))
                if data:
                    return self._deserialize(data)
            except Exception as e:
                logger.error(f"Redis get error: {e}")

        # Fallback
        return self._fallback_sessions.get(session_id)

    def _set_session(self, session_id: str, data: Dict[str, Any]):
        """세션 저장"""
        if self.redis_client:
            try:
                self.redis_client.setex(
                    self._get_key(session_id),
                    self.SESSION_TTL_SECONDS,
                    self._serialize(data)
                )
                return
            except Exception as e:
                logger.error(f"Redis set error: {e}")

        # Fallback
        self._fallback_sessions[session_id] = data

    def _touch_session(self, session_id: str):
        """세션 TTL 갱신"""
        if self.redis_client:
            try:
                self.redis_client.expire(
                    self._get_key(session_id),
                    self.SESSION_TTL_SECONDS
                )
            except Exception as e:
                logger.error(f"Redis expire error: {e}")

    def update_session(
        self,
        session_id: str,
        user_message: str,
        assistant_message: str,
        context_chunks: List[Any],
        metadata: Dict[str, Any]
    ):
        """
        세션에 새 메시지 교환 추가

        Args:
            session_id: 세션 ID
            user_message: 사용자 질문
            assistant_message: AI 응답
            context_chunks: 검색된 컨텍스트 청크
            metadata: 추가 메타데이터
        """
        session = self._get_session(session_id)
        if not session:
            logger.warning(f"Session {session_id[:8]}... not found")
            return

        # 메시지 추가
        session['messages'].append({'role': 'user', 'content': user_message})
        session['messages'].append({'role': 'assistant', 'content': assistant_message})

        # 컨텍스트 업데이트 (첫 질문이거나 팔로업이 아닌 경우)
        if not session['context_chunks'] or not metadata.get('is_followup', False):
            # 직렬화 가능한 형태로 변환
            session['context_chunks'] = [
                {
                    'content': chunk.page_content if hasattr(chunk, 'page_content') else str(chunk),
                    'metadata': chunk.metadata if hasattr(chunk, 'metadata') else {}
                }
                for chunk in context_chunks[:10]  # 최대 10개
            ]

        # 메타데이터 업데이트
        session['metadata'].update(metadata)

        # 메시지 수 제한
        max_messages = self.MAX_MESSAGES_PER_SESSION * 2
        if len(session['messages']) > max_messages:
            session['messages'] = session['messages'][-max_messages:]

        # 타임스탬프 갱신
        session['last_accessed'] = datetime.now()

        # 저장
        self._set_session(session_id, session)

    def get_session_context(self, session_id: str) -> Dict[str, Any]:
        """
        세션의 대화 컨텍스트 조회

        Returns:
            {
                'messages': [...],
                'context_chunks': [...],
                'metadata': {...},
                'conversation_depth': int
            }
        """
        session = self._get_session(session_id)
        if not session:
            return {
                'messages': [],
                'context_chunks': [],
                'metadata': {},
                'conversation_depth': 0
            }

        # 최근 N개 턴만 반환
        max_turns = self.MAX_CONVERSATION_HISTORY_TURNS * 2
        recent_messages = session['messages'][-max_turns:]

        return {
            'messages': recent_messages,
            'context_chunks': session['context_chunks'],
            'metadata': session['metadata'],
            'conversation_depth': len(session['messages']) // 2
        }

    def delete_session(self, session_id: str) -> bool:
        """세션 삭제"""
        if self.redis_client:
            try:
                result = self.redis_client.delete(self._get_key(session_id))
                return result > 0
            except Exception as e:
                logger.error(f"Redis delete error: {e}")

        if session_id in self._fallback_sessions:
            del self._fallback_sessions[session_id]
            return True
        return False

    def cleanup_expired(self) -> int:
        """만료된 세션 정리 (in-memory fallback용)"""
        if self.redis_client:
            return 0  # Redis는 자동 TTL 처리

        now = datetime.now()
        expired = []
        for sid, session in self._fallback_sessions.items():
            last_accessed = session.get('last_accessed', now)
            if isinstance(last_accessed, str):
                last_accessed = datetime.fromisoformat(last_accessed)
            if now - last_accessed > timedelta(seconds=self.SESSION_TTL_SECONDS):
                expired.append(sid)

        for sid in expired:
            del self._fallback_sessions[sid]

        if expired:
            logger.info(f"Cleaned up {len(expired)} expired sessions")
        return len(expired)

    def get_stats(self) -> Dict[str, Any]:
        """세션 통계 조회"""
        if self.redis_client:
            try:
                keys = self.redis_client.keys(f"{self.SESSION_PREFIX}*")
                return {
                    'backend': 'redis',
                    'active_sessions': len(keys),
                    'redis_connected': True
                }
            except Exception as e:
                logger.error(f"Redis stats error: {e}")

        return {
            'backend': 'in-memory',
            'active_sessions': len(self._fallback_sessions),
            'redis_connected': False
        }


# 전역 싱글톤 인스턴스
_session_manager: Optional[RedisSessionManager] = None


def get_session_manager() -> RedisSessionManager:
    """세션 매니저 싱글톤 조회"""
    global _session_manager
    if _session_manager is None:
        _session_manager = RedisSessionManager()
    return _session_manager
```

### 4.3 main.py 수정 사항

`main.py`에서 변경해야 할 부분:

```python
# ============================================================================
# 변경 전 (line 119-127)
# ============================================================================
# Session Management for Follow-up Questions
# In-memory session storage (for production, consider Redis)
CONVERSATION_SESSIONS: Dict[str, Dict[str, Any]] = {}
SESSION_TTL_SECONDS = 3600  # 1 hour
MAX_MESSAGES_PER_SESSION = 20
MAX_CONVERSATION_HISTORY_TURNS = 5

# ============================================================================
# 변경 후
# ============================================================================
# Session Management - Redis 기반 (서버 재시작에도 유지)
from redis_session import get_session_manager, RedisSessionManager

# 세션 매니저 지연 초기화 (lifespan에서 실행)
session_manager: Optional[RedisSessionManager] = None


# ============================================================================
# lifespan 함수 내 추가 (async def lifespan 안에)
# ============================================================================
    # Initialize Redis session manager
    global session_manager
    session_manager = get_session_manager()
    stats = session_manager.get_stats()
    logger.info(f"✓ Session manager initialized: {stats}")


# ============================================================================
# 헬퍼 함수 교체
# ============================================================================

def create_or_get_session(session_id: Optional[str] = None) -> str:
    """세션 생성/조회 - Redis 기반"""
    return session_manager.create_or_get_session(session_id)


def update_session(
    session_id: str,
    user_message: str,
    assistant_message: str,
    context_chunks: List[Any],
    metadata: Dict[str, Any]
):
    """세션 업데이트 - Redis 기반"""
    session_manager.update_session(
        session_id, user_message, assistant_message, context_chunks, metadata
    )


def get_session_context(session_id: str) -> Dict[str, Any]:
    """세션 컨텍스트 조회 - Redis 기반"""
    return session_manager.get_session_context(session_id)


def cleanup_expired_sessions():
    """만료 세션 정리 - Redis 기반"""
    return session_manager.cleanup_expired()
```

### 4.4 requirements.txt에 추가

```
redis>=5.0.0
```

---

## 5. 배포 전 체크리스트

### 5.1 코드 준비 체크리스트

| # | 항목 | 상태 | 담당 | 비고 |
|---|------|------|------|------|
| 1 | docker-compose.yml 통일 | ⬜ | Dev | Fix 1 적용 |
| 2 | redis_session.py 생성 | ⬜ | Dev | Fix 2 신규 파일 |
| 3 | main.py Redis 통합 | ⬜ | Dev | Fix 2 수정 |
| 4 | requirements.txt 업데이트 | ⬜ | Dev | redis>=5.0.0 추가 |
| 5 | .env.example 작성 | ⬜ | Dev | 템플릿 |
| 6 | nginx.conf 도메인 수정 | ⬜ | Dev | ai.buddhakorea.com |
| 7 | 로컬 테스트 통과 | ⬜ | Dev | docker compose up |

### 5.2 인프라 준비 체크리스트

| # | 항목 | 상태 | 명령어/설명 |
|---|------|------|------------|
| 1 | SSH 접속 확인 | ⬜ | `ssh prod` |
| 2 | Docker 설치 | ⬜ | `docker --version` |
| 3 | Docker Compose 설치 | ⬜ | `docker compose version` |
| 4 | 방화벽 설정 | ⬜ | `sudo ufw status` |
| 5 | 디렉토리 생성 | ⬜ | `/opt/buddha-korea/` |
| 6 | GCP 키 업로드 | ⬜ | `gcp-key.json` |
| 7 | DNS 레코드 추가 | ⬜ | ai.buddhakorea.com → 157.180.72.0 |
| 8 | 디스크 공간 확인 | ⬜ | `df -h` (80GB 중 최소 10GB 여유) |
| 9 | 메모리 확인 | ⬜ | `free -h` (8GB) |

### 5.3 데이터 마이그레이션 체크리스트

| # | 항목 | 크기 | 방법 |
|---|------|------|------|
| 1 | ChromaDB 벡터 DB | ~3GB | rsync 또는 tar + scp |
| 2 | source_explorer 데이터 | ~50MB | git clone 또는 scp |
| 3 | SSL 인증서 | <1MB | Let's Encrypt 신규 발급 |
| 4 | .env 파일 | <1KB | 수동 작성 |

### 5.4 보안 체크리스트

| # | 항목 | 상태 | 설명 |
|---|------|------|------|
| 1 | SSH 키 인증만 허용 | ⬜ | Password auth 비활성화 |
| 2 | root 로그인 비활성화 | ⬜ | `PermitRootLogin no` |
| 3 | Redis 비밀번호 설정 | ⬜ | 강력한 비밀번호 |
| 4 | Redis 로컬만 노출 | ⬜ | `127.0.0.1:6379` |
| 5 | .env 파일 권한 | ⬜ | `chmod 600 .env` |
| 6 | GCP 키 파일 권한 | ⬜ | `chmod 600 gcp-key.json` |
| 7 | HTTPS 강제 | ⬜ | HTTP → HTTPS 리다이렉트 |
| 8 | 시크릿 Git 제외 | ⬜ | `.gitignore`에 .env, *.json 키 |

### 5.5 성능/안정성 체크리스트

| # | 항목 | 목표 | 확인 방법 |
|---|------|------|----------|
| 1 | Health check 응답 | <1s | `curl /api/health` |
| 2 | 첫 쿼리 응답 | <30s | 브라우저 테스트 |
| 3 | 메모리 사용량 | <6GB | `docker stats` |
| 4 | 컨테이너 자동 재시작 | Yes | `restart: unless-stopped` |
| 5 | 로그 로테이션 | 설정됨 | `max-size: 50m` |
| 6 | 벡터 DB 로드 | 성공 | 로그 확인 |

---

## 6. 배포 절차

### 6.1 Step 1: 파일 전송

```bash
# 로컬에서 실행
cd /path/to/buddhakorea/opennotebook

# 1. 소스 코드 전송 (Git 사용 권장)
# Option A: Git clone (권장)
ssh prod "cd /opt/buddha-korea && git clone https://github.com/your-repo/buddhakorea.git ."

# Option B: rsync (Git 없이)
rsync -avz --progress \
  --exclude='chroma_db' \
  --exclude='__pycache__' \
  --exclude='.env' \
  --exclude='*.pyc' \
  ./ prod:/opt/buddha-korea/

# 2. ChromaDB 전송 (대용량, 압축 전송)
tar -czvf chroma_db.tar.gz chroma_db/
scp chroma_db.tar.gz prod:/opt/buddha-korea/
ssh prod "cd /opt/buddha-korea && tar -xzvf chroma_db.tar.gz && rm chroma_db.tar.gz"

# 3. GCP 키 전송
scp gcp-key.json prod:/opt/buddha-korea/
ssh prod "chmod 600 /opt/buddha-korea/gcp-key.json"
```

### 6.2 Step 2: 환경 설정

```bash
# VM에서 실행
ssh prod
cd /opt/buddha-korea

# .env 파일 생성
cat > .env << 'EOF'
# GCP Vertex AI
GCP_PROJECT_ID=gen-lang-client-0324154376
GCP_LOCATION=us-central1

# 모델
LLM_MODEL=gemini-2.5-pro
LLM_MODEL_FAST=gemini-2.5-flash
USE_GEMINI_FOR_QUERIES=true

# ChromaDB
CHROMA_COLLECTION_NAME=cbeta_sutras_gemini

# Redis (강력한 비밀번호로 변경!)
REDIS_PASSWORD=your-very-strong-password-change-this

# API
ALLOWED_ORIGINS=https://ai.buddhakorea.com,https://buddhakorea.com
RATE_LIMIT_PER_HOUR=100
LOG_LEVEL=info
EOF

# 권한 설정
chmod 600 .env
```

### 6.3 Step 3: SSL 인증서 (Let's Encrypt)

```bash
# Certbot 설치
sudo apt install -y certbot

# 인증서 발급 (nginx 중지 상태에서)
sudo certbot certonly --standalone -d ai.buddhakorea.com

# 인증서 복사
sudo cp /etc/letsencrypt/live/ai.buddhakorea.com/fullchain.pem /opt/buddha-korea/ssl/
sudo cp /etc/letsencrypt/live/ai.buddhakorea.com/privkey.pem /opt/buddha-korea/ssl/
sudo chown $USER:$USER /opt/buddha-korea/ssl/*.pem

# ⚠️ 자동 갱신 deploy-hook 설정 (필수! 없으면 90일 후 HTTPS 에러)
sudo mkdir -p /etc/letsencrypt/renewal-hooks/deploy
sudo tee /etc/letsencrypt/renewal-hooks/deploy/reload-nginx.sh << 'EOF'
#!/bin/bash
DOMAIN="ai.buddhakorea.com"
cp /etc/letsencrypt/live/$DOMAIN/fullchain.pem /opt/buddha-korea/ssl/
cp /etc/letsencrypt/live/$DOMAIN/privkey.pem /opt/buddha-korea/ssl/
chmod 644 /opt/buddha-korea/ssl/fullchain.pem
chmod 600 /opt/buddha-korea/ssl/privkey.pem
docker compose -f /opt/buddha-korea/docker-compose.yml exec -T nginx nginx -s reload 2>/dev/null || \
    docker compose -f /opt/buddha-korea/docker-compose.yml restart nginx
echo "[$(date)] SSL renewed and Nginx reloaded"
EOF
sudo chmod +x /etc/letsencrypt/renewal-hooks/deploy/reload-nginx.sh

# 자동 갱신 타이머 활성화
sudo systemctl enable certbot.timer

# 자동 갱신 테스트 (dry-run)
sudo certbot renew --dry-run
```

### 6.4 Step 4: Docker 빌드 및 실행

```bash
cd /opt/buddha-korea

# 이미지 빌드
docker compose build --no-cache

# 컨테이너 시작
docker compose up -d

# 로그 확인
docker compose logs -f

# 상태 확인
docker compose ps
docker stats
```

### 6.5 Step 5: 검증

```bash
# Health check
curl http://localhost:8000/api/health
curl https://ai.buddhakorea.com/api/health

# 세션 테스트 (Redis 확인)
docker exec buddhakorea-redis redis-cli -a 'your-password' INFO keyspace

# 쿼리 테스트
curl -X POST https://ai.buddhakorea.com/api/chat \
  -H "Content-Type: application/json" \
  -d '{"query": "사성제란 무엇인가?"}'
```

---

## 7. 배포 후 검증

### 7.1 필수 검증 항목

```bash
#!/bin/bash
# verify_deployment.sh

echo "=== Buddha Korea Deployment Verification ==="

# 1. 컨테이너 상태
echo -e "\n[1/7] Container Status:"
docker compose ps

# 2. Health check
echo -e "\n[2/7] Health Check:"
curl -s https://ai.buddhakorea.com/api/health | jq .

# 3. Redis 연결
echo -e "\n[3/7] Redis Connection:"
docker exec buddhakorea-redis redis-cli -a "$REDIS_PASSWORD" PING

# 4. 세션 테스트
echo -e "\n[4/7] Session Test:"
docker exec buddhakorea-backend python -c "
from redis_session import get_session_manager
mgr = get_session_manager()
print(mgr.get_stats())
"

# 5. 메모리 사용량
echo -e "\n[5/7] Memory Usage:"
docker stats --no-stream --format "table {{.Name}}\t{{.MemUsage}}\t{{.MemPerc}}"

# 6. 디스크 사용량
echo -e "\n[6/7] Disk Usage:"
df -h /opt/buddha-korea

# 7. SSL 인증서
echo -e "\n[7/7] SSL Certificate:"
echo | openssl s_client -servername ai.buddhakorea.com -connect ai.buddhakorea.com:443 2>/dev/null | openssl x509 -noout -dates

echo -e "\n=== Verification Complete ==="
```

### 7.2 기능 테스트

| 테스트 | 예상 결과 | 확인 |
|--------|----------|------|
| `/api/health` | `{"status": "healthy"}` | ⬜ |
| `/api/chat` (첫 질문) | 응답 + session_id | ⬜ |
| `/api/chat` (후속 질문) | 이전 컨텍스트 유지 | ⬜ |
| 서버 재시작 후 세션 | 세션 유지됨 | ⬜ |
| `/api/sources` | 경전 목록 반환 | ⬜ |
| Rate limiting | 429 응답 (초과 시) | ⬜ |

---

## 8. 롤백 절차

### 8.1 빠른 롤백 (컨테이너 레벨)

```bash
# 이전 이미지로 롤백
docker compose down
docker tag buddhakorea-backend:latest buddhakorea-backend:broken
docker pull buddhakorea-backend:previous  # 또는 이전 빌드
docker compose up -d
```

### 8.2 전체 롤백 (GCP VM으로)

```bash
# 1. Hetzner nginx 중지
ssh prod "docker compose stop nginx"

# 2. DNS를 GCP VM IP로 변경
# ai.buddhakorea.com → [GCP VM IP]

# 3. GCP VM 서비스 재시작
gcloud compute ssh buddhakorea-rag-server --zone=us-central1-a \
  --command="cd /opt/buddha-korea && docker compose up -d"
```

---

## 9. 모니터링 및 유지보수

### 9.1 로그 확인

```bash
# 전체 로그
docker compose logs -f

# 특정 서비스
docker compose logs -f backend
docker compose logs -f nginx
docker compose logs -f redis

# 최근 100줄
docker compose logs --tail=100 backend
```

### 9.2 리소스 모니터링

```bash
# 실시간 리소스
docker stats

# 디스크 사용량
du -sh /opt/buddha-korea/chroma_db
du -sh /opt/buddha-korea/redis-data
du -sh /opt/buddha-korea/logs

# 시스템 전체
htop
```

### 9.3 백업 (로컬 + GCS 오프사이트)

> **3-2-1 백업 원칙**:
> - **3개 복사본**: 원본 + 로컬 백업 + GCS 오프사이트
> - **2가지 미디어**: 로컬 SSD + 클라우드 스토리지
> - **1개 오프사이트**: 디스크 장애 시에도 복구 가능
>
> **Redis 백업 방식**: `BGSAVE` + `sleep` 대신 **호스트 볼륨 전체 백업**
> - `redis-data/` 폴더에 `dump.rdb` + `appendonly.aof` 모두 포함
> - 데이터 크기와 관계없이 안전

#### GCS 버킷 사전 설정

```bash
# 1. 버킷 생성 (최초 1회)
gcloud storage buckets create gs://buddhakorea-backups \
    --location=asia-northeast3 \
    --uniform-bucket-level-access

# 2. 수명 주기 정책 (7일 후 자동 삭제)
cat > /tmp/lifecycle.json << 'EOF'
{
  "rule": [
    {
      "action": {"type": "Delete"},
      "condition": {"age": 7}
    }
  ]
}
EOF

gcloud storage buckets update gs://buddhakorea-backups \
    --lifecycle-file=/tmp/lifecycle.json

# 3. 서비스 계정 권한 (Hetzner VM에서 접근용)
# VM에 gcloud CLI 설치 및 인증 필요
```

#### 백업 스크립트

```bash
# /opt/buddha-korea/scripts/backup.sh
#!/bin/bash
set -e

APP_DIR="/opt/buddha-korea"
BACKUP_DIR="/opt/backups"
GCS_BUCKET="gs://buddhakorea-backups"
DATE=$(date +%Y%m%d_%H%M%S)
DATE_PATH=$(date +%Y/%m/%d)

mkdir -p $BACKUP_DIR

echo "[$(date)] 🚀 백업 시작..."

# ChromaDB 백업 (~3GB)
tar -czf $BACKUP_DIR/chroma_db_$DATE.tar.gz -C $APP_DIR chroma_db

# Redis 백업 (전체 폴더 - RDB + AOF 포함)
tar -czf $BACKUP_DIR/redis_data_$DATE.tar.gz -C $APP_DIR redis-data

# 환경 설정 백업
tar -czf $BACKUP_DIR/config_$DATE.tar.gz -C $APP_DIR \
    docker-compose.yml .env nginx.conf redis.conf 2>/dev/null || true

# GCS 오프사이트 업로드
echo "[$(date)] ☁️ GCS로 전송 중..."
if gcloud storage cp $BACKUP_DIR/*_$DATE.tar.gz "$GCS_BUCKET/$DATE_PATH/"; then
    # GCS 업로드 성공 시에만 로컬 정리 (3일 이상)
    find $BACKUP_DIR -name "*.tar.gz" -mtime +3 -delete
    echo "[$(date)] ✅ 백업 완료! (로컬: 3일, GCS: 7일 보관)"
else
    echo "[$(date)] ❌ GCS 업로드 실패 - 로컬 백업 유지"
    exit 1
fi
```

```bash
# 스크립트 권한 설정
chmod +x /opt/buddha-korea/scripts/backup.sh

# 크론 설정 (매일 새벽 3시)
sudo crontab -e
# 추가:
0 3 * * * /opt/buddha-korea/scripts/backup.sh >> /var/log/buddha-backup.log 2>&1
```

#### 복구 방법

```bash
# 로컬 백업에서 복구 (빠름)
cd /opt/buddha-korea && docker compose down
tar -xzf /opt/backups/chroma_db_YYYYMMDD.tar.gz -C /opt/buddha-korea/
tar -xzf /opt/backups/redis_data_YYYYMMDD.tar.gz -C /opt/buddha-korea/
docker compose up -d

# GCS에서 복구 (로컬 손실 시)
gcloud storage cp "gs://buddhakorea-backups/2025/01/15/*" /opt/backups/
tar -xzf /opt/backups/chroma_db_*.tar.gz -C /opt/buddha-korea/
tar -xzf /opt/backups/redis_data_*.tar.gz -C /opt/buddha-korea/
docker compose up -d
```

### 9.4 SSL 인증서 갱신 (Critical - 90일 자동화)

> **⚠️ 주의**: Certbot은 `/etc/letsencrypt/`에 인증서를 갱신하지만,
> Nginx 컨테이너는 `/opt/buddha-korea/ssl/`을 바라봅니다.
> **deploy-hook 없이는 90일 후 HTTPS 에러가 발생합니다!**

#### 자동 갱신 설정 (필수)

```bash
# 1. deploy-hook 스크립트 생성
sudo mkdir -p /etc/letsencrypt/renewal-hooks/deploy
sudo tee /etc/letsencrypt/renewal-hooks/deploy/reload-nginx.sh << 'EOF'
#!/bin/bash
# Let's Encrypt 갱신 후 자동 실행되는 스크립트
# 인증서를 앱 디렉토리로 복사하고 Nginx 재시작

DOMAIN="ai.buddhakorea.com"
APP_SSL_DIR="/opt/buddha-korea/ssl"
COMPOSE_FILE="/opt/buddha-korea/docker-compose.yml"

echo "[$(date)] SSL certificate renewed for $DOMAIN"

# 인증서 복사
cp /etc/letsencrypt/live/$DOMAIN/fullchain.pem $APP_SSL_DIR/
cp /etc/letsencrypt/live/$DOMAIN/privkey.pem $APP_SSL_DIR/

# 권한 설정
chmod 644 $APP_SSL_DIR/fullchain.pem
chmod 600 $APP_SSL_DIR/privkey.pem

# Nginx 재시작 (graceful reload)
docker compose -f $COMPOSE_FILE exec -T nginx nginx -s reload 2>/dev/null || \
    docker compose -f $COMPOSE_FILE restart nginx

echo "[$(date)] Nginx reloaded with new certificate"
EOF

# 2. 실행 권한 부여
sudo chmod +x /etc/letsencrypt/renewal-hooks/deploy/reload-nginx.sh

# 3. 자동 갱신 테스트 (실제 갱신 없이 시뮬레이션)
sudo certbot renew --dry-run
```

#### 수동 갱신 (필요 시)

```bash
# 인증서 수동 갱신
sudo certbot renew

# deploy-hook이 자동 실행되지만, 수동으로 해야 한다면:
sudo /etc/letsencrypt/renewal-hooks/deploy/reload-nginx.sh
```

#### 갱신 상태 확인

```bash
# 인증서 만료일 확인
sudo certbot certificates

# 또는 OpenSSL로 직접 확인
echo | openssl s_client -servername ai.buddhakorea.com -connect ai.buddhakorea.com:443 2>/dev/null | openssl x509 -noout -dates

# 갱신 타이머 상태 (Ubuntu)
sudo systemctl status certbot.timer
```

#### 트러블슈팅

```bash
# 갱신 로그 확인
sudo tail -f /var/log/letsencrypt/letsencrypt.log

# deploy-hook 수동 테스트
sudo /etc/letsencrypt/renewal-hooks/deploy/reload-nginx.sh
```

---

## 부록: 명령어 치트시트

```bash
# ═══════════════════════════════════════════════════════════
# 자주 쓰는 명령어
# ═══════════════════════════════════════════════════════════

# 접속
ssh prod

# 서비스 시작/중지
cd /opt/buddha-korea
docker compose up -d      # 시작
docker compose down       # 중지
docker compose restart    # 재시작

# 로그
docker compose logs -f              # 전체
docker compose logs -f backend      # 백엔드만

# 상태
docker compose ps
docker stats

# 빌드 (코드 변경 후)
docker compose build backend
docker compose up -d backend

# Redis CLI
docker exec -it buddhakorea-redis redis-cli -a 'password'

# 컨테이너 쉘 접속
docker exec -it buddhakorea-backend /bin/bash

# 디스크 정리
docker system prune -af
```

---

> **문서 작성**: Claude Code
> **버전**: 1.0
> **다음 단계**: Fix 1, Fix 2 적용 후 배포 진행


---


# Buddha Korea RAG System - Production Deployment Guide

Complete guide for deploying Buddha Korea Buddhist AI Chatbot to production.

---

## 📋 Table of Contents

1. [Prerequisites](#prerequisites)
2. [VPS Selection & Setup](#vps-selection--setup)
3. [Server Preparation](#server-preparation)
4. [SSL Certificate Setup](#ssl-certificate-setup)
5. [Application Deployment](#application-deployment)
6. [Database Migration](#database-migration)
7. [Monitoring & Maintenance](#monitoring--maintenance)
8. [Troubleshooting](#troubleshooting)

---

## 1. Prerequisites

### Local Requirements
- ✅ ChromaDB database (3.5GB) - **Already created**
- ✅ 99,723 embedded documents - **Already created**
- ✅ API Keys (OpenAI/Anthropic)
- ✅ Domain name (beta.buddhakorea.com)

### Server Requirements
- **CPU**: 2+ vCPUs
- **RAM**: 4GB minimum (8GB recommended)
- **Storage**: 25GB SSD
- **Bandwidth**: Unlimited or 2TB+
- **OS**: Ubuntu 22.04/24.04 LTS

---

## 2. VPS Selection & Setup

### Recommended Providers

#### Option 1: Hetzner (Best Value) ⭐
```
Server: CPX21
- 3 vCPU AMD
- 4GB RAM
- 80GB SSD
- 20TB traffic
- Cost: €5.83/month (~$6)
- Location: Germany/Finland
```

#### Option 2: DigitalOcean
```
Droplet: Basic
- 2 vCPU
- 4GB RAM
- 80GB SSD
- 4TB traffic
- Cost: $24/month
- Location: Singapore/US
```

#### Option 3: Vultr
```
Cloud Compute: Regular
- 2 vCPU
- 4GB RAM
- 80GB SSD
- 3TB traffic
- Cost: $18/month
- Location: Tokyo/Seoul
```

### VPS Creation Steps

1. **Sign up** for chosen provider
2. **Create server**:
   - OS: Ubuntu 24.04 LTS
   - Region: Closest to Korea (Tokyo/Singapore)
   - SSH key: Upload your public key
   - Hostname: `buddhakorea-beta`

3. **Note down**:
   - IP address (e.g., `123.45.67.89`)
   - Root password (if no SSH key)

---

## 3. Server Preparation

### 3.1 Initial Connection

```bash
# Connect to server
ssh root@YOUR_SERVER_IP

# Update system
apt update && apt upgrade -y

# Set timezone
timedatectl set-timezone Asia/Seoul
```

### 3.2 Install Docker

```bash
# Install Docker
curl -fsSL https://get.docker.com -o get-docker.sh
sh get-docker.sh

# Install Docker Compose
apt install -y docker-compose-plugin

# Verify installation
docker --version
docker compose version

# Enable Docker on boot
systemctl enable docker
systemctl start docker
```

### 3.3 Create Application User

```bash
# Create non-root user
adduser buddha
usermod -aG sudo,docker buddha

# Switch to buddha user
su - buddha
```

### 3.4 Firewall Setup

```bash
# Install UFW
sudo apt install -y ufw

# Configure firewall
sudo ufw default deny incoming
sudo ufw default allow outgoing
sudo ufw allow ssh
sudo ufw allow 80/tcp
sudo ufw allow 443/tcp
sudo ufw enable

# Check status
sudo ufw status
```

---

## 4. SSL Certificate Setup

### 4.1 DNS Configuration

**Before continuing**, configure your domain DNS:

```
Type: A Record
Name: beta
Value: YOUR_SERVER_IP
TTL: 3600
```

**Verify DNS propagation**:
```bash
nslookup beta.buddhakorea.com
```

### 4.2 Install Certbot

```bash
# Install Certbot
sudo apt install -y certbot python3-certbot-nginx

# Create directory for ACME challenge
sudo mkdir -p /var/www/certbot
```

### 4.3 Obtain SSL Certificate

```bash
# Get certificate
sudo certbot certonly --webroot \
  -w /var/www/certbot \
  -d beta.buddhakorea.com \
  --email your-email@example.com \
  --agree-tos \
  --no-eff-email

# Certificates will be saved to:
# /etc/letsencrypt/live/beta.buddhakorea.com/
```

### 4.4 Auto-renewal Setup

```bash
# Test renewal
sudo certbot renew --dry-run

# Certbot auto-renewal is already configured via systemd timer
sudo systemctl status certbot.timer
```

---

## 5. Application Deployment

### 5.1 Upload ChromaDB Database

**On your local machine**:

```bash
# Navigate to project directory
cd /Users/vairocana/Desktop/buddhakorea/buddha-korea-notebook-exp/opennotebook

# Compress ChromaDB (3.5GB -> ~1.5GB compressed)
tar -czf chroma_db.tar.gz chroma_db/

# Upload to server (will take 10-20 minutes)
scp chroma_db.tar.gz buddha@YOUR_SERVER_IP:~/
```

**On the server**:

```bash
# Create application directory
mkdir -p ~/buddhakorea-beta
cd ~/buddhakorea-beta

# Extract ChromaDB
tar -xzf ~/chroma_db.tar.gz
rm ~/chroma_db.tar.gz

# Verify
ls -lh chroma_db/
# Should show chroma.sqlite3 (~3.5GB)
```

### 5.2 Upload Application Files

**On your local machine**:

```bash
# Create deployment package
cd /Users/vairocana/Desktop/buddhakorea/buddha-korea-notebook-exp/opennotebook

# Copy necessary files to a clean directory
mkdir -p deploy_package
cp main.py deploy_package/
cp gemini_query_embedder.py deploy_package/
cp hyde.py deploy_package/
cp reranker.py deploy_package/
cp test_frontend.html deploy_package/
cp requirements.txt deploy_package/
cp docker-compose.yml deploy_package/
cp Dockerfile deploy_package/
cp nginx.conf deploy_package/
cp .dockerignore deploy_package/
cp -r source_explorer deploy_package/

# Create tarball
tar -czf buddha-app.tar.gz deploy_package/

# Upload
scp buddha-app.tar.gz buddha@YOUR_SERVER_IP:~/
```

**On the server**:

```bash
cd ~/buddhakorea-beta

# Extract
tar -xzf ~/buddha-app.tar.gz
mv deploy_package/* .
rmdir deploy_package
rm ~/buddha-app.tar.gz
```

### 5.3 Configure Environment

```bash
# Create .env file
nano .env
```

**Paste this configuration**:

```bash
# LLM API Keys
OPENAI_API_KEY=sk-your-openai-key-here
ANTHROPIC_API_KEY=sk-ant-your-anthropic-key-here

# Model Configuration
LLM_MODEL=claude-3-5-sonnet-20241022
EMBEDDING_MODEL=BAAI/bge-m3

# ChromaDB
CHROMA_COLLECTION_NAME=cbeta_sutras_gemini

# API Configuration
ALLOWED_ORIGINS=https://buddhakorea.com,https://www.buddhakorea.com,https://beta.buddhakorea.com

# Rate Limiting
RATE_LIMIT_PER_HOUR=100

# Logging
LOG_LEVEL=info

# Retrieval
TOP_K_RETRIEVAL=10
MAX_CONTEXT_TOKENS=8000

# HyDE (optional)
USE_HYDE=false
HYDE_WEIGHT=0.5

# Google Cloud (if using Gemini)
USE_GEMINI_FOR_QUERIES=false
GCP_PROJECT_ID=
GCP_LOCATION=us-central1
```

Save with `Ctrl+O`, exit with `Ctrl+X`.

### 5.4 Setup SSL Certificates for Docker

```bash
# Create SSL directory
mkdir -p ssl

# Copy Let's Encrypt certificates
sudo cp /etc/letsencrypt/live/beta.buddhakorea.com/fullchain.pem ssl/
sudo cp /etc/letsencrypt/live/beta.buddhakorea.com/privkey.pem ssl/
sudo chown buddha:buddha ssl/*.pem
sudo chmod 600 ssl/*.pem
```

### 5.5 Create Logs Directory

```bash
mkdir -p logs
```

### 5.6 Build and Start Services

```bash
# Build Docker images (first time only)
docker compose build

# Start all services
docker compose up -d

# Check status
docker compose ps

# View logs
docker compose logs -f
```

**Expected output**:
```
NAME                      STATUS    PORTS
buddhakorea-chromadb      Up        0.0.0.0:8001->8000/tcp
buddhakorea-fastapi       Up        0.0.0.0:8000->8000/tcp
buddhakorea-nginx         Up        0.0.0.0:80->80/tcp, 0.0.0.0:443->443/tcp
```

---

## 6. Database Migration

### 6.1 Verify ChromaDB Connection

```bash
# Check ChromaDB health
curl http://localhost:8001/api/v1/heartbeat

# Should return: {"nanosecond heartbeat": ...}
```

### 6.2 Verify FastAPI Connection

```bash
# Check API health
curl http://localhost:8000/api/health

# Should return:
# {
#   "status": "healthy",
#   "version": "0.1.0",
#   "chroma_connected": true,
#   "llm_configured": true
# }
```

### 6.3 Test Collections

```bash
# List collections
curl http://localhost:8000/api/collections

# Should return:
# [
#   {
#     "name": "cbeta_sutras_gemini",
#     "document_count": 99723,
#     "language": "multilingual",
#     "description": "..."
#   }
# ]
```

### 6.4 Test Search

```bash
# Test query
curl -X POST http://localhost:8000/api/chat \
  -H "Content-Type: application/json" \
  -d '{
    "query": "무상에 대해 설명해주세요",
    "max_sources": 3
  }'
```

---

## 7. Monitoring & Maintenance

### 7.1 View Logs

```bash
# All services
docker compose logs -f

# Specific service
docker compose logs -f fastapi
docker compose logs -f chromadb
docker compose logs -f nginx

# FastAPI application logs
tail -f logs/app.log
```

### 7.2 Monitor Resources

```bash
# Install htop
sudo apt install -y htop

# Monitor in real-time
htop

# Docker stats
docker stats
```

### 7.3 Disk Usage

```bash
# Check disk usage
df -h

# Check Docker disk usage
docker system df
```

### 7.4 Backup ChromaDB

```bash
# Stop services
docker compose stop

# Backup database
tar -czf chroma_db_backup_$(date +%Y%m%d).tar.gz chroma_db/

# Restart services
docker compose start

# Upload backup to remote storage (recommended)
# e.g., rclone, S3, etc.
```

### 7.5 Update Application

```bash
# Pull latest code
cd ~/buddhakorea-beta

# Stop services
docker compose down

# Update files (upload new versions)
# ...

# Rebuild and restart
docker compose build
docker compose up -d

# Check logs
docker compose logs -f
```

---

## 8. Troubleshooting

### 8.1 ChromaDB Not Connecting

```bash
# Check ChromaDB logs
docker compose logs chromadb

# Restart ChromaDB
docker compose restart chromadb

# Verify file permissions
ls -la chroma_db/
```

### 8.2 FastAPI Errors

```bash
# Check FastAPI logs
docker compose logs fastapi

# Check application logs
tail -f logs/app.log

# Restart FastAPI
docker compose restart fastapi

# Check environment variables
docker compose exec fastapi env | grep -E "API_KEY|MODEL"
```

### 8.3 Nginx 502 Bad Gateway

```bash
# Check Nginx logs
docker compose logs nginx

# Check upstream (FastAPI)
docker compose ps fastapi

# Test FastAPI directly
curl http://localhost:8000/api/health

# Restart Nginx
docker compose restart nginx
```

### 8.4 SSL Certificate Issues

```bash
# Check certificate validity
sudo certbot certificates

# Renew manually
sudo certbot renew

# Update Docker SSL files
sudo cp /etc/letsencrypt/live/beta.buddhakorea.com/fullchain.pem ~/buddhakorea-beta/ssl/
sudo cp /etc/letsencrypt/live/beta.buddhakorea.com/privkey.pem ~/buddhakorea-beta/ssl/
sudo chown buddha:buddha ~/buddhakorea-beta/ssl/*.pem

# Restart Nginx
cd ~/buddhakorea-beta
docker compose restart nginx
```

### 8.5 High Memory Usage

```bash
# Check memory
free -h

# Check which service is using memory
docker stats

# Restart services
docker compose restart
```

### 8.6 Rate Limiting Issues

```bash
# Check Nginx rate limit logs
docker compose logs nginx | grep "limiting requests"

# Adjust rate limits in nginx.conf
nano nginx.conf

# Reload Nginx
docker compose restart nginx
```

---

## 9. Performance Optimization

### 9.1 Enable Docker Logging Rotation

```bash
# Edit Docker daemon config
sudo nano /etc/docker/daemon.json
```

Add:
```json
{
  "log-driver": "json-file",
  "log-opts": {
    "max-size": "10m",
    "max-file": "3"
  }
}
```

```bash
# Restart Docker
sudo systemctl restart docker
```

### 9.2 Optimize ChromaDB

Already configured in docker-compose.yml:
- Persistent storage
- Health checks
- Resource limits

### 9.3 Add Swap Memory (if needed)

```bash
# Create 4GB swap
sudo fallocate -l 4G /swapfile
sudo chmod 600 /swapfile
sudo mkswap /swapfile
sudo swapon /swapfile

# Make permanent
echo '/swapfile none swap sw 0 0' | sudo tee -a /etc/fstab
```

---

## 10. Cost Summary

### Monthly Costs

| Item | Cost |
|------|------|
| VPS (Hetzner CPX21) | $6/month |
| Domain (already owned) | $0 |
| SSL (Let's Encrypt) | $0 |
| **OpenAI API** | ~$5-20 (usage-based) |
| **Anthropic API** | ~$10-30 (usage-based) |
| **Total** | **$21-56/month** |

### Cost Optimization
- Use Claude 3.5 Sonnet (better quality, similar cost to GPT-4o)
- Enable rate limiting (100/hour already configured)
- Cache common queries (future: Redis)
- Monitor API usage daily

---

## 11. Security Checklist

- ✅ SSL/TLS enabled (Let's Encrypt)
- ✅ Firewall configured (UFW)
- ✅ Non-root user for Docker
- ✅ Rate limiting (Nginx)
- ✅ Security headers (Nginx)
- ✅ Environment variables secured (.env not in git)
- ✅ ChromaDB authentication enabled
- ✅ Docker resource limits
- ✅ Automatic security updates

**Enable unattended upgrades**:
```bash
sudo apt install -y unattended-upgrades
sudo dpkg-reconfigure --priority=low unattended-upgrades
```

---

## 12. Going Live

### Pre-Launch Checklist

- [ ] DNS configured and propagated
- [ ] SSL certificate obtained and valid
- [ ] ChromaDB uploaded and verified (99,723 docs)
- [ ] API keys configured
- [ ] All services running and healthy
- [ ] Test queries working
- [ ] Rate limiting tested
- [ ] Logs monitoring working
- [ ] Backup strategy in place
- [ ] Monitoring alerts configured

### Launch Commands

```bash
# Final check
cd ~/buddhakorea-beta
docker compose ps
docker compose logs --tail=50

# If all green, you're live! 🚀
echo "Buddha Korea RAG is now live at https://beta.buddhakorea.com"
```

### Post-Launch

1. **Monitor logs** for first 24 hours
2. **Test from different locations/devices**
3. **Set up uptime monitoring** (e.g., UptimeRobot - free)
4. **Create status page** (optional)
5. **Document known issues**
6. **Plan for scaling** (if traffic grows)

---

## 13. Support

### Useful Commands

```bash
# Quick health check
docker compose ps && curl -s http://localhost:8000/api/health | jq

# Restart everything
docker compose restart

# View real-time logs
docker compose logs -f --tail=100

# Check disk space
df -h && docker system df

# Backup database
tar -czf backup_$(date +%Y%m%d_%H%M%S).tar.gz chroma_db/
```

### Getting Help

- **Docker issues**: `docker compose logs [service]`
- **API errors**: `tail -f logs/app.log`
- **Nginx issues**: `docker compose logs nginx`
- **ChromaDB issues**: Check `chroma_db/chroma.sqlite3` permissions

---

## 14. Next Steps (Future Enhancements)

1. **Monitoring Dashboard** (Grafana + Prometheus)
2. **Redis Caching** (for common queries)
3. **CDN Integration** (CloudFlare)
4. **Auto-scaling** (Kubernetes)
5. **A/B Testing** (different models)
6. **Analytics** (query patterns, popular topics)
7. **Reranking** (MiniLM-L-12)
8. **HyDE** (query expansion)

---

## Congratulations! 🎉

Buddha Korea RAG system is now running in production!

**Access your beta site**: https://beta.buddhakorea.com

**Questions?** Check logs or troubleshooting section above.


---


# Rollback Procedure for Gunicorn Timeout Change

**Date**: 2025-11-22
**Change**: Gunicorn timeout increased from 120s to 300s
**Backup**: `/opt/buddha-korea/Dockerfile.backup-20251122-104329` (on GCP server)
**New Image**: `01dd3030954c`

## When to Rollback

Rollback if you observe:
- Detailed mode queries hanging longer than expected (>5 minutes)
- Increased memory usage or worker issues
- Any unexpected behavior in production

## Rollback Steps

### 1. Restore Original Dockerfile

```bash
cd /opt/buddha-korea
sudo cp Dockerfile.backup-20251122-104329 Dockerfile
```

Verify restoration:
```bash
grep "timeout" Dockerfile
# Should show: "--timeout", "120"
```

### 2. Rebuild Docker Image with Original Configuration

```bash
sudo docker-compose -f docker-compose.production.yml build fastapi
```

This creates a new image with the original 120s timeout.

### 3. Stop and Remove Current Container

```bash
# Find current container ID
sudo docker ps | grep fastapi

# Remove container (replace <container-id> with actual ID)
sudo docker rm -f <container-id>
```

### 4. Start Fresh Container

```bash
sudo docker-compose -f docker-compose.production.yml up -d fastapi
```

### 5. Verify Rollback

```bash
# Check container is running
sudo docker ps | grep fastapi

# Verify Gunicorn timeout is back to 120s
sudo docker exec <container-id> ps aux | grep gunicorn
# Look for: --timeout 120
```

### 6. Test Production Endpoint

```bash
curl -X POST 'https://ai.buddhakorea.com/api/chat' \
  -H 'Content-Type: application/json' \
  -d '{"query":"불교의 사성제는 무엇인가요?","detailed_mode":false}' \
  -w '\nHTTP_CODE:%{http_code}\nTIME_TOTAL:%{time_total}s\n'
```

Expected: HTTP 200, response in <10 seconds for regular mode.

⚠️ **Note**: After rollback, detailed mode will likely return to showing 502 errors for queries taking >65 seconds.

## Current State (Before Rollback)

- **Dockerfile**: Timeout set to 300s
- **Container**: `17ba0597ac08` (running with 300s timeout)
- **Image**: `01dd3030954c` (buddha-korea_fastapi:latest)
- **Status**: ✅ Working - detailed mode queries completing successfully in ~72s

## Alternative: Partial Rollback (Reduce Timeout)

If 300s seems too long but 120s is too short, you can set an intermediate value:

```dockerfile
"--timeout", "180",  # 3 minutes instead of 5
```

Then rebuild and restart as above.

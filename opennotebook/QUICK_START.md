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

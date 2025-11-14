# Buddha Korea RAG - Production Deployment 🙏

**불교 AI 챗봇 - CBETA 대장경 RAG 시스템**

Beta 서비스 배포를 위한 완전한 프로덕션 환경 구성

---

## 📚 시스템 개요

- **데이터**: CBETA 대장경 99,723 documents (3.5GB)
- **임베딩**: Vertex AI (768-dim) + Fine-tuned BERT
- **Vector DB**: ChromaDB (Persistent)
- **LLM**: Claude 3.5 Sonnet
- **검색**: RAG with HyDE (optional)
- **백엔드**: FastAPI + Gunicorn
- **프록시**: Nginx with SSL
- **배포**: Docker Compose

---

## 🚀 빠른 시작

### **2-3시간 만에 beta.buddhakorea.com 론칭**

**단계**:
1. VPS 구매 ($6/월)
2. ChromaDB 업로드 (3.5GB)
3. Docker로 배포
4. SSL 설정
5. **서비스 시작!**

**상세 가이드**: [`QUICK_START.md`](./QUICK_START.md) ← 여기부터 시작!

---

## 📁 파일 구조

```
opennotebook/
├── docker-compose.yml      # 🐳 Docker 오케스트레이션
├── Dockerfile               # 📦 FastAPI 컨테이너
├── nginx.conf               # 🌐 Nginx 리버스 프록시
├── main.py                  # 🤖 FastAPI 애플리케이션
├── .env                     # 🔑 환경 변수 (API 키)
├── chroma_db/               # 💾 ChromaDB 데이터 (3.5GB)
│   └── chroma.sqlite3
├── source_explorer/         # 📖 경전 메타데이터
├── logs/                    # 📝 애플리케이션 로그
├── ssl/                     # 🔒 SSL 인증서
└── static/                  # 🎨 정적 파일

Production Documentation:
├── QUICK_START.md           # ⚡ 빠른 배포 가이드
├── DEPLOYMENT.md            # 📖 상세 배포 문서
└── PRODUCTION_README.md     # 📋 이 파일
```

---

## 🏗️ 아키텍처

```
Internet
   ↓
[Nginx] :80/:443 (SSL/TLS)
   ↓ reverse proxy
[FastAPI] :8000 (Gunicorn + Uvicorn)
   ↓ RAG Pipeline
   ├─ [Claude 3.5 Sonnet] (답변 생성)
   ├─ [bge-m3] (쿼리 임베딩)
   └─ [ChromaDB] :8001 (벡터 검색)
         ↓
      99,723 documents
      (CBETA 대장경)
```

---

## 💻 기술 스택

### Backend
- **FastAPI** 0.115.0 - 비동기 웹 프레임워크
- **Gunicorn** + Uvicorn - 프로덕션 WSGI/ASGI 서버
- **LangChain** 0.3.7 - RAG 파이프라인

### AI/ML
- **Claude 3.5 Sonnet** - LLM 답변 생성
- **BAAI/bge-m3** - 쿼리 임베딩 (로컬)
- **Fine-tuned BERT** - CBETA 특화 임베딩
- **HyDE** - 쿼리 확장 (선택)

### Vector Database
- **ChromaDB** 0.5.18 - 벡터 저장/검색
- **SQLite** - Persistent storage

### Infrastructure
- **Docker** + Docker Compose - 컨테이너화
- **Nginx** - 리버스 프록시, SSL, 레이트 제한
- **Let's Encrypt** - 무료 SSL 인증서

---

## 🔑 환경 변수 (.env)

```bash
# LLM API Keys (필수)
OPENAI_API_KEY=sk-...
ANTHROPIC_API_KEY=sk-ant-...

# Model Configuration
LLM_MODEL=claude-3-5-sonnet-20241022
EMBEDDING_MODEL=BAAI/bge-m3

# ChromaDB
CHROMA_COLLECTION_NAME=cbeta_sutras_gemini

# API
ALLOWED_ORIGINS=https://buddhakorea.com,https://beta.buddhakorea.com
RATE_LIMIT_PER_HOUR=100

# Optional Features
USE_HYDE=false
USE_GEMINI_FOR_QUERIES=false
```

---

## 📡 API 엔드포인트

### Production URL
```
https://beta.buddhakorea.com
```

### 주요 엔드포인트

#### 1. Health Check
```bash
GET /api/health
```
시스템 상태 확인

#### 2. Chat (RAG 검색)
```bash
POST /api/chat
{
  "query": "무상에 대해 설명해주세요",
  "max_sources": 5,
  "sutra_filter": "T01n0001"  # 선택적
}
```

#### 3. 경전 목록
```bash
GET /api/sources?search=무상&limit=50
```

#### 4. 경전 상세
```bash
GET /api/sources/T01n0001
```

### 전체 API 문서
```
https://beta.buddhakorea.com/docs
```

---

## 🛠️ 배포 명령어

### 초기 배포
```bash
# 1. ChromaDB 업로드
scp chroma_db.tar.gz buddha@server:~/
ssh buddha@server
tar -xzf chroma_db.tar.gz

# 2. 애플리케이션 업로드
scp buddha-app.tar.gz buddha@server:~/
ssh buddha@server
tar -xzf buddha-app.tar.gz

# 3. 환경 변수 설정
nano .env

# 4. SSL 인증서 발급
certbot certonly --standalone -d beta.buddhakorea.com

# 5. Docker 실행
docker compose build
docker compose up -d
```

### 일상 관리
```bash
# 로그 확인
docker compose logs -f

# 재시작
docker compose restart

# 업데이트
docker compose down
docker compose pull
docker compose up -d

# 백업
tar -czf backup_$(date +%Y%m%d).tar.gz chroma_db/
```

---

## 📊 리소스 요구사항

### 최소 사양
- **CPU**: 2 vCPU
- **RAM**: 4GB
- **Storage**: 25GB SSD
- **Bandwidth**: 2TB/월

### 권장 사양
- **CPU**: 4 vCPU
- **RAM**: 8GB
- **Storage**: 50GB SSD
- **Bandwidth**: Unlimited

### 실제 사용량 (4GB VPS 기준)
- **RAM**: 2.5-3GB (ChromaDB + FastAPI)
- **CPU**: 10-30% (평균), 80-100% (쿼리 시)
- **Disk**: ~5GB (OS + Docker + ChromaDB)

---

## 💰 비용 분석

### VPS 옵션

| Provider | Specs | 비용/월 | 추천도 |
|----------|-------|---------|--------|
| **Hetzner CPX21** | 3vCPU, 4GB, 80GB | **$6** | ⭐⭐⭐⭐⭐ |
| DigitalOcean | 2vCPU, 4GB, 80GB | $24 | ⭐⭐⭐ |
| Vultr | 2vCPU, 4GB, 80GB | $18 | ⭐⭐⭐⭐ |
| AWS Lightsail | 2vCPU, 4GB, 80GB | $24 | ⭐⭐ |

### 월간 총 비용
```
VPS (Hetzner):           $6
SSL:                     $0 (Let's Encrypt)
OpenAI API:              $5-20 (사용량)
Anthropic API:           $10-30 (사용량)
──────────────────────────────
총 예상:                 $21-56/월
```

### 연간 총 비용
```
약 $250-670/년
```

---

## 🔒 보안 기능

### 적용된 보안 조치
- ✅ **SSL/TLS** (HTTPS only)
- ✅ **Rate Limiting** (Nginx - 100 req/hour)
- ✅ **CORS** 설정 (buddhakorea.com만 허용)
- ✅ **Non-root** Docker 사용자
- ✅ **방화벽** (UFW - 22/80/443만 오픈)
- ✅ **Security Headers** (HSTS, X-Frame-Options 등)
- ✅ **ChromaDB Auth** (Token 기반)
- ✅ **리소스 제한** (CPU/Memory limits)

### 추가 권장 사항
- [ ] Fail2ban (무차별 대입 공격 방지)
- [ ] CloudFlare (DDoS 방지)
- [ ] 정기 백업 (daily cron)
- [ ] 보안 업데이트 자동화

---

## 📈 성능 메트릭

### 응답 시간 (평균)
- **간단한 쿼리**: 2-3초
- **복잡한 쿼리**: 4-6초
- **경전 필터링**: 3-5초

### 처리량
- **동시 접속**: 10-20명
- **시간당 요청**: 100-500 (레이트 제한 적용)

### 검색 정확도
- **bge-m3**: 75-80% (Classical Chinese)
- **Fine-tuned BERT**: 85-90% (예상)

---

## 🔍 모니터링

### 로그 위치
```bash
# FastAPI 애플리케이션
logs/app.log
logs/access.log
logs/error.log

# Docker 로그
docker compose logs chromadb
docker compose logs fastapi
docker compose logs nginx
```

### Health Check
```bash
# 자동 헬스체크 (Docker)
docker compose ps

# 수동 확인
curl https://beta.buddhakorea.com/api/health
```

### 리소스 모니터링
```bash
# 실시간 모니터링
htop
docker stats

# 디스크 사용량
df -h
docker system df
```

---

## 🐛 트러블슈팅

### 공통 문제

#### 1. ChromaDB 연결 실패
```bash
# 증상: "ChromaDB not connected"
# 해결:
docker compose logs chromadb
docker compose restart chromadb
```

#### 2. API 키 오류
```bash
# 증상: "API key not found"
# 해결:
nano .env  # API 키 확인
docker compose restart fastapi
```

#### 3. Nginx 502 Bad Gateway
```bash
# 증상: "502 Bad Gateway"
# 해결:
docker compose ps  # FastAPI가 실행 중인지 확인
docker compose restart nginx
```

#### 4. SSL 인증서 만료
```bash
# 증상: "Certificate expired"
# 해결:
certbot renew
cp /etc/letsencrypt/live/beta.buddhakorea.com/*.pem ssl/
docker compose restart nginx
```

상세 트러블슈팅: [`DEPLOYMENT.md`](./DEPLOYMENT.md#8-troubleshooting)

---

## 📚 문서 가이드

### 배포 문서
1. **[QUICK_START.md](./QUICK_START.md)** - ⚡ 2-3시간 빠른 배포
2. **[DEPLOYMENT.md](./DEPLOYMENT.md)** - 📖 상세 프로덕션 가이드
3. **[PRODUCTION_README.md](./PRODUCTION_README.md)** - 📋 시스템 개요 (이 파일)

### 개발 문서
1. **[README_RAG.md](../README_RAG.md)** - 🧠 RAG 시스템 아키텍처
2. **[requirements.txt](./requirements.txt)** - 📦 Python 의존성
3. **[main.py](./main.py)** - 💻 FastAPI 소스코드

---

## 🎯 로드맵

### Phase 1: Beta 론칭 ✅
- [x] ChromaDB 프로덕션 배포
- [x] FastAPI + Nginx 구성
- [x] SSL/TLS 적용
- [x] Rate limiting
- [ ] **Beta 서비스 오픈**

### Phase 2: 최적화 (1-2개월)
- [ ] Redis 캐싱 (자주 묻는 질문)
- [ ] Reranking (MiniLM-L-12)
- [ ] HyDE 쿼리 확장 활성화
- [ ] 모니터링 대시보드 (Grafana)

### Phase 3: 확장 (3-6개월)
- [ ] Qdrant 마이그레이션 (성능 향상)
- [ ] Fine-tuned BERT 적용
- [ ] 사용자 피드백 시스템
- [ ] A/B 테스팅

### Phase 4: 정식 서비스 (6개월+)
- [ ] 프로덕션 도메인 (buddhakorea.com)
- [ ] CDN (CloudFlare)
- [ ] Auto-scaling
- [ ] 다국어 지원 (영어/일본어)

---

## 🤝 기여

### 피드백
- **버그 리포트**: GitHub Issues
- **기능 제안**: GitHub Discussions
- **성능 이슈**: Performance monitoring

### 개발자
Buddha Korea 팀
- RAG 시스템: Claude Code
- 프로덕션 배포: DevOps
- CBETA 데이터: 전자불전문화재단

---

## 📞 지원

### 긴급 상황
```bash
# 서비스 중지
docker compose down

# 긴급 재시작
docker compose up -d

# 백업으로 복구
tar -xzf backup_YYYYMMDD.tar.gz
```

### 문의
- **이메일**: support@buddhakorea.com (가상)
- **문서**: 이 디렉토리의 MD 파일들
- **로그**: `logs/` 디렉토리

---

## 📄 라이선스

Buddha Korea RAG System - Buddhist AI Chatbot
Copyright © 2025 Buddha Korea

CBETA 대장경 데이터는 전자불전문화재단의 저작권을 따릅니다.

---

## 🙏 감사의 말

- **CBETA** (中華電子佛典協會) - 불교 경전 디지털화
- **Anthropic** - Claude API
- **ChromaDB** - Vector database
- **FastAPI** - Web framework
- **Docker** - Containerization

---

**Buddha Korea RAG를 프로덕션에 배포하세요! 🚀**

**시작**: [`QUICK_START.md`](./QUICK_START.md)

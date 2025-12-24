# Buddha Korea 개발 및 배포 가이드

> 최종 업데이트: 2024-12-24

## 목차
1. [인프라 구조](#1-인프라-구조)
2. [로컬 개발 환경](#2-로컬-개발-환경)
3. [배포 프로세스](#3-배포-프로세스)
4. [배포 체크리스트](#4-배포-체크리스트)
5. [트러블슈팅](#5-트러블슈팅)
6. [환경변수 참조](#6-환경변수-참조)

---

## 1. 인프라 구조

### 1.1 도메인 구성

| 도메인 | 호스팅 | 용도 |
|--------|--------|------|
| `buddhakorea.com` | GitHub Pages | 정적 프론트엔드 (index.html, sutra-writing.html 등) |
| `ai.buddhakorea.com` | Hetzner VM (157.180.72.0) | AI 챗봇 백엔드 + chat.html |

### 1.2 Hetzner 서버 Docker 컨테이너

```
┌─────────────────────────────────────────────────────────────┐
│                    Hetzner VM (157.180.72.0)                │
├─────────────────────────────────────────────────────────────┤
│  ┌─────────────┐  ┌─────────────┐  ┌─────────────┐         │
│  │   nginx     │  │   backend   │  │  postgres   │         │
│  │  (SSL/프록시) │  │  (FastAPI)  │  │  (사용자DB)  │         │
│  │  :80/:443   │  │   :8000     │  │   :5432     │         │
│  └─────────────┘  └─────────────┘  └─────────────┘         │
│                   ┌─────────────┐                           │
│                   │    redis    │                           │
│                   │  (세션/캐시)  │                           │
│                   │   :6379     │                           │
│                   └─────────────┘                           │
└─────────────────────────────────────────────────────────────┘
```

### 1.3 nginx 프록시 경로

| 경로 | 대상 | 설명 |
|------|------|------|
| `/api/*` | backend:8000 | REST API |
| `/auth/*` | backend:8000 | OAuth 인증 |
| `/*.html` | backend:8000 | HTML 페이지 (FastAPI StaticFiles) |
| `/css/*`, `/js/*`, `/assets/*`, `/data/*` | backend:8000 | 정적 파일 |
| `/docs`, `/redoc` | backend:8000 | API 문서 |

---

## 2. 로컬 개발 환경

### 2.1 필수 요구사항

- Python 3.11+
- Node.js (선택, 프론트엔드 개발 시)
- Docker & Docker Compose (선택, 전체 스택 테스트 시)

### 2.2 백엔드 로컬 실행

```bash
cd buddhakorea

# 가상환경 생성 및 활성화
python -m venv venv
source venv/bin/activate  # Windows: venv\Scripts\activate

# 의존성 설치
pip install -r requirements.txt

# 환경변수 설정 (.env 파일 확인)
cp .env.example .env  # 필요시

# 서버 실행
cd backend
uvicorn app.main:app --reload --port 8000
```

### 2.3 로컬 환경변수 (.env)

```bash
# 로컬 개발용 설정
COOKIE_DOMAIN=           # 비워둠 (localhost용)
DATABASE_URL=            # 비워둠 (SQLite 사용)
CHROMA_DB_PATH=../data/chroma_db

# OAuth (Google Console에 localhost callback 추가 필요)
# http://localhost:8000/auth/callback/google
```

### 2.4 로컬 OAuth 테스트

Google Cloud Console에서 승인된 리디렉션 URI에 추가:
- `http://localhost:8000/auth/callback/google`
- `http://localhost:8000/auth/callback/naver`
- `http://localhost:8000/auth/callback/kakao`

---

## 3. 배포 프로세스

### 3.1 GitHub Actions 자동 배포

| 워크플로우 | 트리거 경로 | 대상 |
|-----------|------------|------|
| `deploy-pages.yml` | `frontend/**` | GitHub Pages (buddhakorea.com) |
| `deploy-hetzner.yml` | `backend/**`, `config/**`, `Dockerfile` | Hetzner (ai.buddhakorea.com) |

### 3.2 자동 배포 흐름

```
git push origin main
       │
       ├─► frontend/** 변경 → deploy-pages.yml → GitHub Pages
       │
       └─► backend/** 변경 → deploy-hetzner.yml → Hetzner VM
                                    │
                                    ├─► git pull
                                    ├─► docker compose up -d --build (Dockerfile 변경 시)
                                    └─► docker compose up -d --force-recreate (코드만 변경 시)
```

### 3.3 수동 배포 (긴급 시)

```bash
# SSH 접속
ssh root@157.180.72.0

# 코드 업데이트
cd /opt/buddha-korea
git pull origin main

# 컨테이너 재시작
docker compose -f config/docker-compose.yml down
docker compose -f config/docker-compose.yml up -d --build

# 로그 확인
docker logs buddhakorea-backend -f
```

---

## 4. 배포 체크리스트

### 4.1 코드 변경 전 체크리스트

- [ ] 로컬에서 `uvicorn app.main:app --reload` 실행 확인
- [ ] 주요 기능 테스트 (채팅, 로그인 등)
- [ ] `.env` 파일이 `.gitignore`에 포함되어 있는지 확인
- [ ] 민감 정보 (API 키, 비밀번호) 코드에 하드코딩되지 않았는지 확인

### 4.2 배포 후 체크리스트

- [ ] Health Check: `curl https://ai.buddhakorea.com/api/health`
- [ ] 프론트엔드 로드: `https://ai.buddhakorea.com/chat.html`
- [ ] CSS/JS 로드 확인 (브라우저 개발자 도구 Network 탭)
- [ ] Google 로그인 테스트 (시크릿 모드 권장)
- [ ] 채팅 기능 테스트
- [ ] 컨테이너 상태: `docker compose ps`

### 4.3 Dockerfile 변경 시 추가 체크리스트

- [ ] 새 모듈/폴더가 COPY 명령에 포함되었는지 확인
- [ ] `requirements.txt` 변경 시 빌드 시간 증가 예상
- [ ] 빌드 후 컨테이너 내부 파일 구조 확인:
  ```bash
  docker exec buddhakorea-backend ls -la /app/
  ```

### 4.4 nginx 설정 변경 시 체크리스트

- [ ] 문법 검증: `docker exec buddhakorea-nginx nginx -t`
- [ ] 새 경로 프록시 설정 확인
- [ ] SSL 인증서 유효 기간 확인

---

## 5. 트러블슈팅

### 5.1 자주 발생하는 문제

#### CSS/JS 404 에러
```
원인: nginx가 해당 경로를 백엔드로 프록시하지 않음
해결: config/nginx.conf에 location 블록 추가
     location /css/ { proxy_pass http://fastapi_backend; ... }
```

#### OAuth "mismatching_state" 에러
```
원인: SessionMiddleware 쿠키 설정 문제
해결: main.py의 SessionMiddleware 설정 확인
     - same_site="lax"
     - https_only=False (nginx SSL 종료 환경)
```

#### "No module named 'xxx'" 에러
```
원인: Dockerfile에서 해당 모듈 폴더를 복사하지 않음
해결: Dockerfile에 COPY 명령 추가
     COPY --chown=buddha:buddha backend/xxx/ ./xxx/
```

#### Redis 연결 실패
```
원인: redis.conf의 환경변수 미치환
해결: 서버의 redis.conf에 비밀번호 직접 설정
     requirepass your-password-here
```

#### 컨테이너 충돌/중복
```
원인: 이전 컨테이너가 제대로 정리되지 않음
해결: docker compose down --remove-orphans && docker compose up -d
```

### 5.2 로그 확인 명령어

```bash
# 백엔드 로그
docker logs buddhakorea-backend -f --tail 100

# nginx 로그
docker logs buddhakorea-nginx -f --tail 100

# 특정 에러 검색
docker logs buddhakorea-backend 2>&1 | grep -i error

# 전체 컨테이너 상태
docker compose -f config/docker-compose.yml ps
```

### 5.3 서버 리소스 확인

```bash
# 디스크 사용량
df -h /

# 메모리 사용량
free -h

# Docker 이미지 정리 (디스크 부족 시)
docker image prune -a
docker system prune
```

---

## 6. 환경변수 참조

### 6.1 서버 환경변수 (/opt/buddha-korea/.env)

| 변수 | 설명 | 예시 |
|------|------|------|
| `COOKIE_DOMAIN` | 쿠키 도메인 (서브도메인 공유) | `.buddhakorea.com` |
| `SECRET_KEY` | JWT 서명 키 | `random-secret-key` |
| `GOOGLE_CLIENT_ID` | Google OAuth Client ID | `xxx.apps.googleusercontent.com` |
| `GOOGLE_CLIENT_SECRET` | Google OAuth Secret | `GOCSPX-xxx` |
| `REDIS_PASSWORD` | Redis 비밀번호 | `your-redis-password` |
| `GCP_PROJECT_ID` | GCP 프로젝트 (Vertex AI용) | `gen-lang-client-xxx` |
| `LLM_MODEL` | 기본 LLM 모델 | `gemini-2.5-pro` |
| `LLM_MODEL_FAST` | 빠른 응답용 모델 | `gemini-2.5-flash` |

### 6.2 로컬 vs 서버 환경변수 차이

| 변수 | 로컬 | 서버 |
|------|------|------|
| `COOKIE_DOMAIN` | (비움) | `.buddhakorea.com` |
| `DATABASE_URL` | (비움 → SQLite) | `postgresql+asyncpg://...` |
| `REDIS_PASSWORD` | (없음) | `설정됨` |

---

## 7. SSL 인증서 관리

### 7.1 현재 인증서 정보

```bash
# 만료일 확인
openssl x509 -in /opt/buddha-korea/config/ssl/fullchain.pem -noout -dates
```

### 7.2 인증서 갱신 (Let's Encrypt)

```bash
# certbot으로 갱신 (서버에서 실행)
certbot renew

# nginx 재시작
docker compose -f config/docker-compose.yml restart nginx
```

---

## 8. GitHub Secrets 설정

GitHub 리포지토리 → Settings → Secrets and variables → Actions

| Secret 이름 | 설명 |
|------------|------|
| `HETZNER_HOST` | `157.180.72.0` |
| `HETZNER_USERNAME` | `root` |
| `HETZNER_SSH_KEY` | SSH 개인 키 전체 내용 |

---

## 9. 주요 파일 구조

```
buddhakorea/
├── .github/workflows/
│   ├── deploy-pages.yml      # GitHub Pages 배포
│   └── deploy-hetzner.yml    # Hetzner 배포
├── backend/
│   ├── app/
│   │   ├── main.py           # FastAPI 앱, 라우트
│   │   ├── auth.py           # OAuth, JWT
│   │   ├── database.py       # DB 연결
│   │   └── models.py         # SQLAlchemy 모델
│   └── rag/
│       └── buddhist_thesaurus.py  # 불교 용어 확장
├── frontend/
│   ├── chat.html             # AI 챗봇 페이지
│   ├── index.html            # 메인 페이지
│   ├── css/
│   └── js/
├── config/
│   ├── docker-compose.yml
│   ├── nginx.conf
│   └── redis.conf
├── Dockerfile
├── requirements.txt
└── .env                      # 환경변수 (git 제외)
```

---

## 10. 연락처 및 참고 자료

- GitHub: https://github.com/ltk1186/buddhakorea
- 서버 IP: 157.180.72.0
- API 문서: https://ai.buddhakorea.com/docs

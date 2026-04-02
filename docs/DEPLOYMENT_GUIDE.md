# Buddha Korea 개발 및 배포 가이드

> 최종 업데이트: 2026-04-02

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

모든 서비스는 `buddhakorea.com` 단일 도메인으로 통합되어 있습니다.

| 도메인 | 호스팅 | 용도 |
|--------|--------|------|
| `buddhakorea.com` | Hetzner VM (157.180.72.0) | 프론트엔드 + AI 챗봇 백엔드 통합 |
| `www.buddhakorea.com` | Hetzner VM (157.180.72.0) | 위와 동일 (www 리다이렉트) |

> **참고**: 과거에는 `ai.buddhakorea.com` 서브도메인을 별도로 사용했으나, 2026년 4월 도메인 통합 작업으로 제거되었습니다.

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
- Docker & Docker Compose (전체 스택 테스트 시)

### 2.2 백엔드 로컬 실행

```bash
cd buddhakorea

# 가상환경 생성 및 활성화
python -m venv venv
source venv/bin/activate  # Windows: venv\Scripts\activate

# 의존성 설치
pip install -r requirements.txt

# 환경변수 설정 (.env 파일 확인)
cp .env.example .env  # 필요시 편집

# 서버 실행
cd backend
uvicorn app.main:app --reload --port 8000
```

### 2.3 로컬 환경변수 (.env)

```bash
# 로컬 개발용 핵심 설정
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

`main` 브랜치에 push하면 다음 경로가 변경된 경우 자동으로 Hetzner에 배포됩니다:

| 트리거 경로 | 워크플로우 |
|------------|-----------|
| `backend/**` | `.github/workflows/deploy-hetzner.yml` |
| `config/**` | 위와 동일 |
| `Dockerfile` | 위와 동일 |
| `.github/workflows/deploy-hetzner.yml` | 위와 동일 |

### 3.2 자동 배포 흐름

```
git push origin main
       │
       └─► backend/config/Dockerfile 변경 감지
                    │
                    ▼
           deploy-hetzner.yml 실행
                    │
           SSH → Hetzner VM (/opt/buddha-korea)
                    │
           ├─ git pull origin main
           ├─ GitHub Secrets → .env 파일 생성
           ├─ GCP 키 복원 (base64 디코딩)
           └─ docker compose up -d [--build | --force-recreate]
```

> **빌드 vs 재생성**: `Dockerfile` 또는 `requirements.txt` 변경 시 `--build`로 이미지 재빌드. 코드만 변경 시 `--force-recreate`로 빠르게 재시작.

### 3.3 수동 배포 (긴급 시)

```bash
# SSH 접속
ssh root@157.180.72.0

# 코드 업데이트
cd /opt/buddha-korea
git pull origin main

# 컨테이너 재시작 (코드 변경만)
docker compose -f config/docker-compose.yml up -d --force-recreate

# 이미지 재빌드 포함
docker compose -f config/docker-compose.yml up -d --build

# 로그 확인
docker logs buddhakorea-backend -f
```

### 3.4 GCP 서비스 계정 키 관리 (중요)

GCP 키는 JSON 파일을 그대로 GitHub Secret에 저장하면 줄바꿈 문자가 깨질 수 있습니다. **base64로 인코딩해서 저장**하는 방식을 권장합니다.

#### Secret 등록 방법 (최초 1회 또는 키 교체 시)

```bash
# 로컬에서 실행
base64 -i config/gcp-key.json | pbcopy  # macOS
# 출력값을 GitHub Secret 'GCP_SERVICE_ACCOUNT_KEY'에 붙여넣기
```

배포 스크립트는 이 값을 자동으로 디코딩합니다:
```bash
echo "$GCP_SERVICE_ACCOUNT_KEY" | base64 -d > config/gcp-key.json
```

> **현재 상태**: 현재 워크플로우는 base64가 아닌 raw JSON을 저장하고 Python 스크립트로 sanitize하는 방식을 사용 중입니다. 키 교체 시 위 base64 방식으로 전환을 권장합니다.

---

## 4. 배포 체크리스트

### 4.1 코드 변경 전

- [ ] 로컬에서 `uvicorn app.main:app --reload` 실행 확인
- [ ] 주요 기능 테스트 (채팅, 로그인 등)
- [ ] `.env` 파일이 `.gitignore`에 포함되어 있는지 확인
- [ ] 민감 정보 (API 키, 비밀번호) 코드에 하드코딩되지 않았는지 확인

### 4.2 배포 후

- [ ] GitHub Actions 녹색 체크 확인
- [ ] Health Check: `curl https://buddhakorea.com/api/health`
- [ ] 프론트엔드 로드: `https://buddhakorea.com/chat.html`
- [ ] 브라우저 개발자 도구 Console에서 404 에러 없는지 확인
- [ ] Google 로그인 테스트 (시크릿 모드 권장)
- [ ] 쿠키 확인: 로그인 후 개발자 도구 → Application → Cookies
  - `session` 쿠키 존재 확인
  - Domain이 `.buddhakorea.com`인지 확인
- [ ] 채팅 기능 테스트

### 4.3 Dockerfile/requirements.txt 변경 시

- [ ] 새 모듈/폴더가 COPY 명령에 포함되었는지 확인
- [ ] 빌드 후 컨테이너 내부 파일 구조 확인:
  ```bash
  docker exec buddhakorea-backend ls -la /app/
  ```

### 4.4 nginx 설정 변경 시

- [ ] 문법 검증: `docker exec buddhakorea-nginx nginx -t`
- [ ] SSL 인증서 유효 기간 확인

---

## 5. 트러블슈팅

### 5.1 자주 발생하는 문제

#### 백엔드 컨테이너가 unhealthy 상태로 크래시

```
원인: 앱 시작 시 초기화 실패 (GCP 인증, DB 연결 등)
진단: docker logs buddhakorea-backend --tail 50
해결: 로그에서 구체적인 에러 확인 후 조치
```

#### GCP 인증 실패 (GoogleAuthError)

```
원인: config/gcp-key.json이 유효하지 않은 JSON (줄바꿈 문자 깨짐)
진단: docker exec buddhakorea-backend cat /app/gcp-key.json | python3 -m json.tool
해결: GCP_SERVICE_ACCOUNT_KEY Secret을 base64 인코딩 방식으로 교체 (섹션 3.4 참조)
```

#### API 404 에러 (api/users/me, api/sutras/meta 등)

```
원인: 백엔드 컨테이너가 실행되지 않거나 nginx가 연결 못함
진단: docker compose -f config/docker-compose.yml ps
해결: 백엔드 로그 확인 → 크래시 원인 수정
```

#### OAuth "mismatching_state" 에러

```
원인: SessionMiddleware 쿠키 설정 문제
해결: main.py의 SessionMiddleware 설정 확인
     - same_site="none" (크로스 서브도메인)
     - https_only=False (nginx SSL 종료 환경)
```

#### CSS/JS 404 에러

```
원인: nginx가 해당 경로를 백엔드로 프록시하지 않음
해결: config/nginx.conf에 location 블록 추가
```

#### "No module named 'xxx'" 에러

```
원인: Dockerfile에서 해당 모듈 폴더를 복사하지 않음
해결: Dockerfile에 COPY 명령 추가
     COPY --chown=buddha:buddha backend/xxx/ ./xxx/
```

#### Redis 연결 실패

```
원인: redis.conf의 비밀번호 미설정
해결: REDIS_PASSWORD Secret이 올바른지 확인 후 재배포
```

### 5.2 로그 확인 명령어

```bash
# 백엔드 로그 실시간
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
docker image prune -f       # dangling 이미지만
docker system prune -f      # 미사용 컨테이너, 네트워크 포함
```

---

## 6. 환경변수 참조

### 6.1 GitHub Secrets 목록

GitHub 리포지토리 → Settings → Secrets and variables → Actions

| Secret 이름 | 설명 |
|------------|------|
| `HETZNER_HOST` | `157.180.72.0` |
| `HETZNER_USERNAME` | SSH 사용자명 |
| `HETZNER_SSH_KEY` | SSH 개인 키 전체 내용 |
| `SECRET_KEY` | FastAPI 세션 암호화 키 |
| `REDIS_PASSWORD` | Redis 인증 비밀번호 |
| `POSTGRES_PASSWORD` | PostgreSQL 비밀번호 |
| `GEMINI_API_KEY` | Gemini API 키 (기본) |
| `PALI_GEMINI_API_KEY` | Gemini API 키 (Pali Studio) |
| `GCP_PROJECT_ID` | GCP 프로젝트 ID |
| `GCP_SERVICE_ACCOUNT_KEY` | GCP 서비스 계정 키 (raw JSON 또는 base64) |
| `GOOGLE_CLIENT_ID` | Google OAuth Client ID |
| `GOOGLE_CLIENT_SECRET` | Google OAuth Secret |
| `NAVER_CLIENT_ID` | Naver OAuth Client ID |
| `NAVER_CLIENT_SECRET` | Naver OAuth Secret |
| `KAKAO_CLIENT_ID` | Kakao REST API 키 |
| `KAKAO_CLIENT_SECRET` | Kakao OAuth Secret |

### 6.2 서버 환경변수 (자동 생성됨)

배포 시 GitHub Secrets에서 `/opt/buddha-korea/.env`가 자동 생성됩니다. 수동으로 편집하지 마세요 — 다음 배포 시 덮어씌워집니다.

| 변수 | 설명 | 로컬 | 서버 |
|------|------|------|------|
| `COOKIE_DOMAIN` | 쿠키 도메인 | (비움) | `.buddhakorea.com` |
| `DATABASE_URL` | DB 연결 URL | (비움 → SQLite) | PostgreSQL URL |
| `ALLOWED_ORIGINS` | CORS 허용 도메인 | - | `https://buddhakorea.com,https://www.buddhakorea.com` |
| `LLM_MODEL` | 기본 LLM 모델 | - | `gemini-2.5-pro` |
| `LLM_MODEL_FAST` | 빠른 응답 모델 | - | `gemini-2.5-flash` |

### 6.3 쿠키 및 세션 설정

OAuth 로그인이 정상 작동하려면:

```python
# backend/app/main.py
app.add_middleware(
    SessionMiddleware,
    secret_key=SECRET_KEY,
    session_cookie="session",
    same_site="none",       # 크로스 도메인 허용
    https_only=False,       # nginx SSL 종료 환경
    max_age=86400 * 7,
)
```

| 환경 | same_site | https_only | COOKIE_DOMAIN |
|------|-----------|------------|---------------|
| 로컬 (localhost) | `lax` | `False` | (비움) |
| 서버 (단일도메인) | `none` | `False` | `.buddhakorea.com` |

---

## 7. SSL 인증서 관리

```bash
# 만료일 확인
openssl x509 -in /opt/buddha-korea/config/ssl/fullchain.pem -noout -dates

# 갱신 (서버에서 실행)
certbot renew
docker compose -f config/docker-compose.yml restart nginx
```

---

## 8. 롤백 절차

배포 후 문제 발생 시:

```bash
ssh root@157.180.72.0
cd /opt/buddha-korea

# 최근 커밋 확인
git log --oneline -5

# 이전 커밋으로 롤백
git reset --hard <이전-커밋-해시>

# 컨테이너 재시작
docker compose -f config/docker-compose.yml up -d --build
```

---

## 9. 주요 파일 구조

```
buddhakorea/
├── .github/workflows/
│   └── deploy-hetzner.yml    # Hetzner 자동 배포
├── backend/
│   ├── app/
│   │   ├── main.py           # FastAPI 앱, 라우트
│   │   ├── auth.py           # OAuth, JWT
│   │   ├── database.py       # DB 연결
│   │   └── models.py         # SQLAlchemy 모델
│   └── pali/
│       └── config.py         # Pali Studio CORS 설정
├── frontend/
│   ├── chat.html             # AI 챗봇 페이지
│   ├── index.html            # 메인 페이지
│   ├── css/
│   └── js/
│       └── library.js        # API 엔드포인트 설정
├── config/
│   ├── docker-compose.yml
│   ├── nginx.conf            # 리버스 프록시 설정
│   └── redis.conf
├── Dockerfile
├── requirements.txt
└── .env                      # 환경변수 (git 제외, 배포 시 자동 생성)
```

---

## 10. 참고 링크

- GitHub: https://github.com/ltk1186/buddhakorea
- 서버 IP: 157.180.72.0
- 사이트: https://buddhakorea.com
- API 문서: https://buddhakorea.com/docs
- Health Check: https://buddhakorea.com/api/health

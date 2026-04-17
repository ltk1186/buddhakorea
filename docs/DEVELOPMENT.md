# Buddha Korea 로컬 개발 환경 가이드

## 개요

이 문서는 Buddha Korea 프로젝트의 로컬 개발 환경 구성 방법을 설명합니다. Docker Compose를 사용하여 프론트엔드, 백엔드, 데이터베이스를 한번에 실행합니다.

## 아키텍처

### 프로덕션 환경
```
Cloudflare CDN (buddhakorea.com)
         ↓
    Nginx (포트 80, 443)
    ├── 정적 파일 제공 (프론트엔드)
    ├── SSL 인증서 (Let's Encrypt)
    └── 백엔드로 프록시
         ↓
    FastAPI Backend (포트 8000)
    ├── PostgreSQL
    ├── Redis
    └── ChromaDB
```

### 로컬 개발 환경 (Docker Compose)
```
브라우저
  │
  ↓ http://localhost (포트 80)
  │
┌─────────────────────────────────────────────────────────┐
│            Docker Network (내부)                          │
│                                                          │
│  ┌──────────────────────────────────────────────────┐   │
│  │  Nginx (포트 80)                                  │   │
│  │  ├── / → 프론트엔드 파일 제공                      │   │
│  │  ├── /api/* → FastAPI로 프록시                    │   │
│  │  ├── /auth/* → FastAPI로 프록시                   │   │
│  │  └── /pali/* → FastAPI로 프록시                   │   │
│  └──────────────────────────────────────────────────┘   │
│           │                                              │
│           ↓ (내부 통신 localhost:8000)                   │
│  ┌──────────────────────────────────────────────────┐   │
│  │  FastAPI Backend (포트 8000)                      │   │
│  │  ├── /api/* 엔드포인트                            │   │
│  │  ├── /auth/* OAuth 콜백                          │   │
│  │  └── 정적 파일 제공 (프론트엔드 fallback)         │   │
│  └──────────────────────────────────────────────────┘   │
│           │                                              │
│           ├─→ PostgreSQL (포트 5432)                     │
│           ├─→ Redis (포트 6379)                          │
│           └─→ ChromaDB (벡터 데이터베이스)               │
│                                                          │
└─────────────────────────────────────────────────────────┘
```

## 핵심 개념: Nginx 프록시와 CORS 해결

### 왜 Nginx가 필요한가?

#### ❌ 포트가 다른 경우 (이전 방식)
```
브라우저: http://localhost:3000 (프론트엔드)
백엔드:  http://localhost:8000 (API)
                    ↓
              CORS 에러!
        (다른 포트 = 다른 도메인 취급)
```

#### ✅ 같은 포트 (현재 방식)
```
브라우저: http://localhost (Nginx)
  ↓
Nginx이 요청을 분류
├── / → 프론트엔드 파일 제공
├── /api/ → 내부적으로 localhost:8000으로 프록시
└── /auth/ → 내부적으로 localhost:8000으로 프록시
                    ↓
              CORS 없음! (같은 origin)
```

### 프론트엔드 개발에서의 영향

**API 호출 방식:**

```javascript
// ❌ 포트 지정 (CORS 에러)
fetch('http://localhost:8000/api/chat')

// ✅ 포트 없음 (Nginx 경유)
fetch('/api/chat')
// 또는
fetch(`${window.location.origin}/api/chat`)
```

**설정 위치:** `frontend/js/library.js`
```javascript
if (typeof window.API_BASE_URL === 'undefined') {
    // 항상 같은 origin 사용 (Nginx가 라우팅 처리)
    window.API_BASE_URL = '';
}
```

### OAuth 설정

로컬과 프로덕션에서 **redirect URL이 정확히 일치**해야 OAuth가 작동합니다.

**로컬 개발:**
- Google: `http://localhost/auth/callback/google`
- Naver: `http://localhost/auth/callback/naver`
- Kakao: `http://localhost/auth/callback/kakao`

**프로덕션:**
- Google: `https://buddhakorea.com/auth/callback/google`
- Naver: `https://buddhakorea.com/auth/callback/naver`
- Kakao: `https://buddhakorea.com/auth/callback/kakao`

## 사전 요구사항

- **Docker Desktop** 설치 및 실행 중
- **Docker Compose** v2 이상
- **.env 파일** (프로젝트 루트에 존재)

## 빠른 시작

### 1. Docker 시작 확인

```bash
docker ps  # Docker daemon이 실행 중인지 확인
```

Docker Desktop이 시작되지 않았으면:
```bash
open -a Docker  # macOS
```

### 2. 환경 변수 복사

```bash
cd ~/Desktop/buddhakorea/config
cp ../.env .env  # .env를 config 폴더에 복사 (docker-compose 실행용)
```

### 3. Docker Compose 실행

```bash
cd ~/Desktop/buddhakorea/config

# 모든 컨테이너 시작 (처음 한 번만 --build 사용)
docker compose --env-file .env up -d --build

# 또는 기존 이미지 사용 (다시 실행할 때)
docker compose --env-file .env up -d
```

### 4. 상태 확인

```bash
docker ps --format "table {{.Names}}\t{{.Status}}"

# 예상 출력:
# buddhakorea-nginx      Up (healthy)
# buddhakorea-backend    Up (healthy)
# buddhakorea-postgres   Up (healthy)
# buddhakorea-redis      Up (healthy)
```

### 5. API 테스트

```bash
curl http://localhost/api/health
# {"status":"healthy","version":"0.1.0","chroma_connected":true,"llm_configured":true}
```

### 6. 웹 접속

- **메인 페이지**: http://localhost/
- **채팅 페이지**: http://localhost/chat.html
- **라이브러리**: 채팅 페이지 내 "라이브러리" 탭

## 컨테이너 관리

### 로그 확인

```bash
# 특정 컨테이너 로그
docker logs buddhakorea-backend

# 실시간 로그
docker logs -f buddhakorea-backend

# 최근 50줄
docker logs buddhakorea-backend | tail -50
```

### 컨테이너 재시작

```bash
# 모든 컨테이너 재시작
docker compose --env-file .env restart

# 특정 컨테이너만 재시작
docker compose --env-file .env restart backend
```

### 컨테이너 종료

```bash
# 모든 컨테이너 종료 (데이터 유지)
docker compose --env-file .env down

# 볼륨까지 삭제 (초기화)
docker compose --env-file .env down -v
```

## 데이터베이스 접근

### PostgreSQL에 접속

```bash
# psql 명령어로 접속
docker exec -it buddhakorea-postgres psql -U postgres -d buddhakorea

# 테이블 확인
\dt

# 사용자 조회
SELECT * FROM users;

# 나가기
\q
```

### Redis 데이터 확인

```bash
docker exec -it buddhakorea-redis redis-cli

# 모든 키 조회
keys *

# 특정 키 값 확인
get session:xxxxx

# 종료
exit
```

## 개발 중 변경사항 반영

### 프론트엔드 변경 (HTML/CSS/JS)

```bash
# Nginx 컨테이너는 자동으로 최신 파일 제공
# 브라우저에서 F5 또는 Cmd+Shift+R (하드 새로고침)
```

### 백엔드 변경 (Python)

```bash
# 컨테이너 재빌드 및 재시작
docker compose --env-file .env down
docker compose --env-file .env up -d --build
```

### 설정 파일 변경 (nginx.conf, docker-compose.yml)

```bash
# 컨테이너 재시작
docker compose --env-file .env down
docker compose --env-file .env up -d
```

## 문제 해결

### CORS 에러

**증상**: `Access to fetch at 'http://localhost:8000/api/...' from origin 'http://localhost' has been blocked by CORS policy`

**원인**: 프론트엔드가 직접 포트 8000으로 API 호출

**해결**:
1. `frontend/js/library.js` 확인: `window.API_BASE_URL = ''` (포트 없음)
2. API 호출: `fetch('/api/...')` (상대 경로)
3. 브라우저 캐시 삭제 (F12 → Application → Clear site data)

### OAuth redirect_uri_mismatch

**증상**: "Access blocked: This app's request is invalid"

**원인**: Google/Naver/Kakao 콘솔의 redirect URI와 실제 호출 URL이 불일치

**해결**: 각 OAuth 콘솔에 로컬 redirect URL 추가
- [Google Cloud Console](#google-oauth-설정)
- [Naver Developer Console](#naver-oauth-설정)
- [Kakao Developers](#kakao-oauth-설정)

### 포트 이미 사용 중

**증상**: `bind: address already in use`

**해결**:
```bash
# 포트 80을 사용하는 프로세스 확인 (macOS)
lsof -i :80

# 프로세스 종료
kill -9 <PID>

# 또는 Docker 전체 재시작
docker compose --env-file .env restart
```

### 데이터베이스 연결 에러

**증상**: `psycopg2.OperationalError: could not connect to server`

**해결**:
```bash
# PostgreSQL 컨테이너가 healthy 상태 확인
docker ps

# healthy가 아니면 로그 확인
docker logs buddhakorea-postgres

# 컨테이너 재시작
docker compose --env-file .env restart postgres
```

## OAuth 설정 가이드

### Google OAuth 설정

1. **Google Cloud Console** 접속: https://console.cloud.google.com
2. 프로젝트 선택
3. **APIs & Services** → **Credentials**
4. OAuth 2.0 Client ID 클릭
5. **Authorized redirect URIs** 섹션 수정:
   ```
   로컬:       http://localhost/auth/callback/google
   프로덕션:   https://buddhakorea.com/auth/callback/google
   ```
6. **저장**

### Naver OAuth 설정

1. **Naver Developers** 접속: https://developers.naver.com
2. 내 애플리케이션 → 애플리케이션 수정
3. **API 권한 관리** → OAuth 2.0 설정
4. **Authorized Redirect URI** 수정:
   ```
   로컬:       http://localhost/auth/callback/naver
   프로덕션:   https://buddhakorea.com/auth/callback/naver
   ```
5. **저장**

### Kakao OAuth 설정

1. **Kakao Developers** 접속: https://developers.kakao.com
2. 내 애플리케이션 → 기본 정보
3. **Redirect URI** 섹션 수정:
   ```
   로컬:       http://localhost/auth/callback/kakao
   프로덕션:   https://buddhakorea.com/auth/callback/kakao
   ```
4. **저장**

## 프로덕션 배포

로컬 개발이 완료되면 Hetzner 서버에 배포:

```bash
# 변경사항 커밋
git add .
git commit -m "feature: ..."
git push origin main

# Hetzner 서버에서 (SSH)
cd /opt/buddha-korea/config
git pull origin main
docker compose --env-file .env down
docker compose --env-file .env up -d
```

자세한 배포 방법은 `docs/DEPLOYMENT.md` 참고.
- **Redis**: localhost:6379

## 주요 명령어

### Make 명령어 (권장)

```bash
make dev          # 개발 서버 시작
make dev-stop     # 개발 서버 중지
make dev-restart  # 개발 서버 재시작
make dev-logs     # 로그 확인
make dev-status   # 컨테이너 상태 확인
make dev-shell    # Backend 컨테이너 접속
make dev-psql     # PostgreSQL CLI 접속
make dev-clean    # 모든 개발 데이터 삭제
make test         # 테스트 실행
```

### 스크립트 명령어

```bash
./scripts/dev.sh start     # 개발 서버 시작
./scripts/dev.sh stop      # 개발 서버 중지
./scripts/dev.sh logs      # 로그 확인
./scripts/dev.sh shell     # Backend 컨테이너 접속
./scripts/dev.sh psql      # PostgreSQL CLI
./scripts/dev.sh db-reset  # DB 초기화
```

## 개발 워크플로우

### Hot-Reload

Backend 코드 변경 시 자동으로 서버가 재시작됩니다.
- `backend/` 디렉토리의 모든 Python 파일이 감시됩니다.
- 저장하면 약 1-2초 후 변경 사항이 반영됩니다.

### 프론트엔드 개발

백엔드가 프론트엔드도 함께 서빙하므로, 별도 서버 실행 없이 개발 가능합니다.

```bash
# 1. 백엔드 실행 (프론트엔드도 함께 서빙)
make dev

# 2. 브라우저에서 접속
open http://localhost:8000
```

- `frontend/` 디렉토리의 HTML/CSS/JS 파일을 직접 수정
- 정적 파일은 즉시 반영됨 (브라우저 새로고침)
- API 호출은 상대 경로(`/api/chat`) 사용

### 데이터베이스 변경

1. 모델 변경 (`backend/app/models/`)
2. 서버 재시작 시 자동 마이그레이션 (개발 모드)

### 테스트 실행

```bash
# 전체 테스트
make test

# 특정 테스트
./scripts/dev.sh test tests/test_specific.py

# 커버리지 포함
make test-cov
```

## 디버깅

### VS Code 디버깅

1. 디버그 포트 (5678)가 이미 노출되어 있습니다
2. `.vscode/launch.json` 설정:

```json
{
  "version": "0.2.0",
  "configurations": [
    {
      "name": "Python: Remote Attach",
      "type": "debugpy",
      "request": "attach",
      "connect": {
        "host": "localhost",
        "port": 5678
      },
      "pathMappings": [
        {
          "localRoot": "${workspaceFolder}",
          "remoteRoot": "/app"
        }
      ]
    }
  ]
}
```

### 로그 확인

```bash
# 모든 서비스 로그
docker-compose -f config/docker-compose.dev.yml logs -f

# Backend만
make dev-logs

# 특정 서비스
docker-compose -f config/docker-compose.dev.yml logs -f postgres
```

## 문제 해결

### 포트 충돌

```bash
# 사용 중인 포트 확인
lsof -i :8000
lsof -i :5432
lsof -i :6379

# 기존 컨테이너 정리
make dev-clean
```

### ChromaDB 데이터 문제

```bash
# ChromaDB 디렉토리 삭제 후 재시작
rm -rf chroma_db/
make dev-restart
```

### 완전 초기화

```bash
# 모든 개발 데이터 삭제
make dev-clean

# Docker 볼륨까지 완전 삭제
make clean-all
```

## 파일 구조

```
buddhakorea/
├── backend/
│   ├── app/
│   │   ├── main.py               # FastAPI 앱 진입점, public chat/health/static 라우트
│   │   ├── auth.py               # OAuth/JWT 로직
│   │   ├── admin.py              # Admin API router
│   │   ├── chat_history_service.py  # 채팅 저장/조회 helper
│   │   ├── database.py           # DB 연결
│   │   ├── routers/
│   │   │   ├── auth.py           # 로그인/현재 유저 라우터
│   │   │   └── chat_history.py   # 세션/저장 질문 라우터
│   │   └── models/               # SQLAlchemy 모델
│   └── ...
├── frontend/
│   ├── index.html
│   ├── css/
│   └── js/
├── config/
│   ├── docker-compose.yml      # 프로덕션용
│   ├── docker-compose.dev.yml  # 개발용
│   └── nginx.conf
├── scripts/
│   └── dev.sh               # 개발 스크립트
├── tests/
├── .env                     # 환경 변수 (gitignore)
├── .env.example             # 환경 변수 템플릿
├── Dockerfile               # 프로덕션 이미지
├── Dockerfile.dev           # 개발 이미지
├── Makefile                 # 명령어 단축
└── requirements.txt
```

## 다음 단계

1. [API 문서](http://localhost:8000/docs) 확인
2. `backend/app/main.py`와 `backend/app/routers/`에서 엔드포인트 구조 파악
3. `tests/` 디렉토리에서 테스트 작성 방법 참고

# Buddha Korea 로컬 개발 환경 가이드

## 개요

이 문서는 Buddha Korea 프로젝트의 로컬 개발 환경 구성 방법을 설명합니다.

## 아키텍처

```
┌─────────────────────────────────────────────────────────────┐
│                 프론트엔드 (정적 호스팅)                      │
│  ┌──────────────────────────────────────────────────────┐   │
│  │  ./frontend/*  →  GitHub Pages  →  Cloudflare CDN   │   │
│  │                    (buddhakorea.com)                 │   │
│  └──────────────────────────────────────────────────────┘   │
└─────────────────────────────────────────────────────────────┘
                            │ API 호출
                            ▼
┌─────────────────────────────────────────────────────────────┐
│                    Backend (Docker)                          │
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐       │
│  │   FastAPI    │  │  PostgreSQL  │  │    Redis     │       │
│  │    :8000     │  │    :5432     │  │    :6379     │       │
│  │  (API Only)  │  │              │  │              │       │
│  └──────────────┘  └──────────────┘  └──────────────┘       │
│         │                                                    │
│         ▼                                                    │
│  ┌──────────────┐                                           │
│  │   ChromaDB   │  (벡터 DB - ./chroma_db)                  │
│  └──────────────┘                                           │
└─────────────────────────────────────────────────────────────┘
```

**프로덕션 배포 구조**
- 프론트엔드: GitHub Pages → Cloudflare CDN (www.buddhakorea.com)
- 백엔드: GCP Cloud Run (API Only)

### 로컬 개발 시: 백엔드에서 프론트엔드도 서빙

로컬 개발 환경에서는 백엔드(FastAPI)가 프론트엔드도 함께 서빙합니다.

```
localhost:8000
├── /           → frontend/index.html
├── /chat.html  → frontend/chat.html
├── /css/*      → frontend/css/*
├── /js/*       → frontend/js/*
└── /api/*      → FastAPI 엔드포인트
```

**왜 이렇게 하는가?**

| 분리 개발 | 통합 개발 (현재) |
|-----------|------------------|
| 서버 2개 실행 필요 | `make dev` 하나로 전부 실행 |
| CORS 설정 필요 | 같은 origin이라 CORS 불필요 |
| 포트 2개 관리 | localhost:8000 하나로 통합 |

프론트엔드가 프로덕션(GitHub Pages)과 개발(백엔드 서빙)에 중복 배포되지만, **개발 편의성이 훨씬 좋습니다**.

- 정적 파일(HTML/CSS/JS)이라 Hot-reload도 잘 동작
- API 호출 시 상대 경로(`/api/chat`) 사용 가능
- 프로덕션과 동일한 코드베이스 유지

## 사전 요구사항

- Docker Desktop 설치
- Docker Compose v2 이상
- (선택) Make 설치 (`brew install make`)

## 빠른 시작

### 1. 환경 변수 설정

```bash
# .env.example을 복사하여 .env 생성
cp .env.example .env

# .env 파일을 열어 API 키 설정
# 최소 OPENAI_API_KEY 또는 ANTHROPIC_API_KEY 필요
```

### 2. 개발 서버 시작

```bash
# 방법 1: Make 사용 (권장)
make dev

# 방법 2: 스크립트 직접 실행
./scripts/dev.sh start

# 방법 3: Docker Compose 직접 실행
docker-compose -f config/docker-compose.dev.yml up -d --build
```

### 3. 접속

- **웹 앱**: http://localhost:8000 (프론트엔드 + API 통합)
- **API 문서 (Swagger)**: http://localhost:8000/docs
- **PostgreSQL**: localhost:5432 (user: postgres, db: buddhakorea)
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
│   │   ├── main.py          # FastAPI 앱 진입점
│   │   ├── auth.py          # 인증 로직
│   │   ├── database.py      # DB 연결
│   │   └── models/          # SQLAlchemy 모델
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
2. `backend/app/main.py`에서 엔드포인트 구조 파악
3. `tests/` 디렉토리에서 테스트 작성 방법 참고

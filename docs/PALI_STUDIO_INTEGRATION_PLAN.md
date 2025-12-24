# Pāli Studio 통합 계획

> Buddha Korea + nikaya_gemini 합병 상세 계획서
>
> **Version:** 2.0 (수정본)
> **Date:** 2024-12-24
> **Status:** 승인됨

---

## 1. 핵심 결정 사항

| 항목 | 결정 | 근거 |
|------|------|------|
| **프론트엔드** | Option B: 하이브리드 | 기존 HTML 유지 + Pāli만 React |
| **백엔드** | Monolith 병합 | 1인 개발, 단일 컨테이너, 인증 공유 용이 |
| **Vector DB** | ChromaDB 유지 | 기존 10만 문서 활용, 별도 collection 추가 |

---

## 2. 최종 아키텍처

### 2.1 URL 구조

```
buddhakorea.com (GitHub Pages)
├── /                      → index.html (메인)
├── /sutra-writing.html    → 사경
├── /meditation.html       → 명상
└── /methodology.html      → 방법론

ai.buddhakorea.com (Hetzner VM)
├── /                      → /chat.html로 리다이렉트
├── /chat.html             → AI 챗봇 (기존)
├── /mypage.html           → 마이페이지 (기존)
├── /pali/                 → 빠알리 스튜디오 (React SPA) ← 신규
├── /api/v1/chat/*         → 챗봇 API (기존)
├── /api/v1/pali/*         → 빠알리 API ← 신규
└── /auth/*                → OAuth (기존)
```

### 2.2 시스템 아키텍처

```
┌─────────────────────────────────────────────────────────────────────┐
│                        Hetzner VM (157.180.72.0)                    │
├─────────────────────────────────────────────────────────────────────┤
│                                                                     │
│  ┌─────────────────────────────────────────────────────────────┐   │
│  │                      nginx (443/80)                          │   │
│  │                                                              │   │
│  │  /pali/*        → 정적 파일 (/app/frontend/pali/)           │   │
│  │  /api/v1/pali/* → FastAPI Backend                           │   │
│  │  /api/v1/chat/* → FastAPI Backend                           │   │
│  │  /auth/*        → FastAPI Backend                           │   │
│  │  /*.html        → FastAPI Backend (StaticFiles)             │   │
│  │  /css,/js/*     → FastAPI Backend (StaticFiles)             │   │
│  └─────────────────────────────────────────────────────────────┘   │
│                              │                                      │
│                              ▼                                      │
│  ┌─────────────────────────────────────────────────────────────┐   │
│  │              FastAPI Backend (단일 Monolith)                 │   │
│  │                                                              │   │
│  │  /api/v1/auth/*  ─── AuthRouter (Google/Naver/Kakao OAuth)  │   │
│  │  /api/v1/chat/*  ─── ChatRouter (AI 챗봇, RAG)              │   │
│  │  /api/v1/pali/*  ─── PaliRouter (번역, DPD 사전) ← 신규     │   │
│  │                                                              │   │
│  │  Services:                                                   │   │
│  │  ├── chat_service.py (기존)                                 │   │
│  │  ├── pali_service.py ← 신규                                 │   │
│  │  ├── dpd_service.py  ← 신규                                 │   │
│  │  └── gemini_client.py (통합)                                │   │
│  └─────────────────────────────────────────────────────────────┘   │
│                              │                                      │
│         ┌────────────────────┼────────────────────┐                │
│         ▼                    ▼                    ▼                │
│  ┌─────────────┐     ┌─────────────┐     ┌─────────────┐          │
│  │ PostgreSQL  │     │    Redis    │     │  ChromaDB   │          │
│  │             │     │             │     │             │          │
│  │ - users     │     │ - sessions  │     │ - cbeta_    │          │
│  │ - social_   │     │ - cache     │     │   sutras    │          │
│  │   accounts  │     │ - rate_     │     │   (기존)    │          │
│  │ - chat_*    │     │   limits    │     │ - pali_     │          │
│  │ - pali_*    │     │             │     │   texts     │          │
│  │   (신규)    │     │             │     │   (신규)    │          │
│  └─────────────┘     └─────────────┘     └─────────────┘          │
│                                                                     │
└─────────────────────────────────────────────────────────────────────┘
                              │
                              ▼
                    ┌─────────────────┐
                    │   GCP Vertex AI │
                    │   (Gemini 2.5)  │
                    └─────────────────┘
```

### 2.3 디렉토리 구조 (합병 후)

```
buddhakorea/
├── backend/
│   ├── app/
│   │   ├── main.py                 # FastAPI 앱 (라우터 통합)
│   │   ├── auth.py                 # OAuth 인증 (기존)
│   │   ├── database.py             # DB 연결 (기존)
│   │   ├── models.py               # SQLAlchemy 모델 (확장)
│   │   ├── config.py               # 설정 (확장)
│   │   │
│   │   ├── routers/                # API 라우터
│   │   │   ├── __init__.py
│   │   │   ├── chat.py             # 기존 채팅 라우터
│   │   │   └── pali/               # ← 신규
│   │   │       ├── __init__.py
│   │   │       ├── literature.py   # 문헌 조회
│   │   │       ├── translate.py    # 번역 API
│   │   │       ├── dpd.py          # DPD 사전
│   │   │       └── health.py       # 헬스체크
│   │   │
│   │   └── services/               # 비즈니스 로직
│   │       ├── __init__.py
│   │       ├── chat_service.py     # 기존
│   │       ├── pali_service.py     # ← 신규
│   │       ├── dpd_service.py      # ← 신규
│   │       ├── literature_service.py # ← 신규
│   │       └── gemini_client.py    # 통합 (기존 + Pāli)
│   │
│   ├── rag/                        # RAG 모듈 (기존)
│   │   └── buddhist_thesaurus.py
│   │
│   └── data/                       # 데이터 파일
│       └── dpd/
│           └── dpd.db              # DPD 사전 SQLite ← 신규
│
├── frontend/
│   ├── index.html                  # 메인 (기존, 헤더 수정)
│   ├── chat.html                   # AI 챗봇 (기존, 헤더 수정)
│   ├── mypage.html                 # 마이페이지 (기존)
│   ├── sutra-writing.html          # 사경 (기존)
│   ├── css/                        # 스타일 (기존)
│   ├── js/                         # JS (기존)
│   └── pali/                       # ← 신규 (React 빌드 결과)
│       ├── index.html
│       └── assets/
│           ├── index-[hash].js
│           └── index-[hash].css
│
├── config/
│   ├── docker-compose.yml          # 수정 (볼륨 추가)
│   ├── nginx.conf                  # 수정 (/pali/* 추가)
│   └── redis.conf                  # 기존
│
├── Dockerfile                      # 수정 (dpd.db, pali 포함)
└── requirements.txt                # 수정 (의존성 병합)
```

---

## 3. 상세 구현 계획

### Phase 0: 준비 (1일)

#### 0.1 백업 및 브랜치 생성

```bash
# 현재 상태 백업
cd /Users/vairocana/Desktop/buddhakorea/buddhakorea
git checkout -b backup/pre-pali-integration
git push origin backup/pre-pali-integration

# 통합 작업 브랜치
git checkout main
git checkout -b feature/pali-studio-integration
```

#### 0.2 의존성 분석

**nikaya_gemini/apps/backend/requirements.txt:**
```
fastapi>=0.100.0
uvicorn[standard]>=0.22.0
sqlalchemy>=2.0.0
pydantic-settings>=2.0.0
redis>=4.5.0
google-cloud-aiplatform>=1.38.0
sentry-sdk[fastapi]>=1.29.0
aiosqlite>=0.19.0  # DPD SQLite 비동기 접근
```

**추가 필요 패키지:**
```
aiosqlite>=0.19.0  # DPD 사전용
```

#### 0.3 DPD 데이터베이스 확인

```bash
# 크기 확인
ls -lh /Users/vairocana/Desktop/nikaya_gemini/data/dpd/dpd.db

# 스키마 확인
sqlite3 /Users/vairocana/Desktop/nikaya_gemini/data/dpd/dpd.db ".schema" | head -50
```

---

### Phase 1: 헤더 통합 (1일)

#### 1.1 공통 헤더 HTML 수정

**모든 HTML 파일의 헤더에 "빠알리 스튜디오" 링크 추가:**

```html
<!-- 네비게이션 -->
<nav class="header-nav">
    <a href="/" class="nav-link">홈</a>
    <a href="/chat.html" class="nav-link">AI</a>
    <a href="/pali/" class="nav-link">빠알리 스튜디오</a>  <!-- 신규 -->
    <a href="/sutra-writing.html" class="nav-link">사경</a>
    <span id="auth-container" style="margin-left: 10px;">
        <!-- Auth content injected by JS -->
    </span>
</nav>
```

**수정 대상 파일:**
- `frontend/index.html`
- `frontend/chat.html`
- `frontend/mypage.html`
- `frontend/sutra-writing.html`
- `frontend/meditation.html`
- `frontend/methodology.html`

#### 1.2 임시 Coming Soon 페이지

```bash
mkdir -p frontend/pali
```

**frontend/pali/index.html:**
```html
<!DOCTYPE html>
<html lang="ko">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>빠알리 스튜디오 | Buddha Korea</title>
    <link rel="stylesheet" href="/css/styles.css">
</head>
<body>
    <header class="site-header">
        <!-- 공통 헤더 -->
    </header>
    <main style="text-align: center; padding: 100px 20px;">
        <h1>빠알리 스튜디오</h1>
        <p style="font-size: 1.2em; color: #666;">Coming Soon</p>
        <p>빠알리어 경전 번역 서비스가 곧 출시됩니다.</p>
        <a href="/chat.html" class="btn-primary" style="margin-top: 20px;">
            AI 채팅으로 돌아가기
        </a>
    </main>
</body>
</html>
```

---

### Phase 2: 백엔드 병합 (3-4일)

#### 2.1 라우터 구조 생성

```bash
# 디렉토리 생성
mkdir -p backend/app/routers/pali
mkdir -p backend/app/services
```

#### 2.2 Pāli 라우터 이식

**backend/app/routers/pali/__init__.py:**
```python
"""Pāli Studio API routers."""
from fastapi import APIRouter
from .literature import router as literature_router
from .translate import router as translate_router
from .dpd import router as dpd_router
from .health import router as health_router

router = APIRouter()

router.include_router(health_router, tags=["pali-health"])
router.include_router(literature_router, prefix="/literature", tags=["pali-literature"])
router.include_router(translate_router, prefix="/translate", tags=["pali-translate"])
router.include_router(dpd_router, prefix="/dpd", tags=["pali-dpd"])
```

**이식 대상 파일 (nikaya_gemini → buddhakorea):**

| 원본 | 대상 | 수정 사항 |
|------|------|----------|
| `apps/backend/api/v1/literature.py` | `backend/app/routers/pali/literature.py` | import 경로 수정 |
| `apps/backend/api/v1/translate.py` | `backend/app/routers/pali/translate.py` | import 경로 수정 |
| `apps/backend/api/v1/dpd.py` | `backend/app/routers/pali/dpd.py` | import 경로 수정 |
| `apps/backend/api/v1/health.py` | `backend/app/routers/pali/health.py` | import 경로 수정 |

#### 2.3 서비스 레이어 이식

| 원본 | 대상 | 수정 사항 |
|------|------|----------|
| `apps/backend/services/dpd_service.py` | `backend/app/services/dpd_service.py` | DB 경로 설정 |
| `apps/backend/services/literature_service.py` | `backend/app/services/literature_service.py` | import 수정 |
| `apps/backend/services/gemini_client.py` | 기존 통합 | 기능 병합 |
| `apps/backend/services/hint_generator.py` | `backend/app/services/hint_generator.py` | import 수정 |

#### 2.4 main.py 수정

**backend/app/main.py에 추가:**
```python
# 기존 import 유지...
from app.routers.pali import router as pali_router

# 기존 라우터 등록 유지...

# Pāli API 라우터 추가
app.include_router(pali_router, prefix="/api/v1/pali")
```

#### 2.5 설정 확장

**backend/app/config.py 또는 환경변수 추가:**
```python
# Pāli 관련 설정
DPD_DATABASE_PATH: str = "/app/data/dpd/dpd.db"
PALI_GEMINI_MODEL: str = "gemini-2.5-pro"
PALI_MAX_CHUNK_SIZE: int = 2000
PALI_HINT_ENABLED: bool = True
```

#### 2.6 requirements.txt 병합

```
# 기존 의존성 유지...

# Pāli Studio 추가 의존성
aiosqlite>=0.19.0
```

---

### Phase 3: 데이터베이스 확장 (1-2일)

#### 3.1 PostgreSQL 스키마 확장

**새 테이블 (Alembic 마이그레이션):**

```sql
-- 빠알리 문헌 정보
CREATE TABLE pali_literatures (
    id VARCHAR(100) PRIMARY KEY,
    title_pali TEXT,
    title_korean TEXT,
    nikaya VARCHAR(50),          -- DN, MN, SN, AN, KN
    description TEXT,
    segment_count INTEGER DEFAULT 0,
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX idx_pali_literatures_nikaya ON pali_literatures(nikaya);

-- 빠알리 세그먼트 (문단)
CREATE TABLE pali_segments (
    id BIGSERIAL PRIMARY KEY,
    literature_id VARCHAR(100) REFERENCES pali_literatures(id),
    paragraph_id VARCHAR(50),
    pali_text TEXT NOT NULL,
    korean_translation TEXT,
    translation_metadata JSONB,  -- 번역 모델, 시간 등
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX idx_pali_segments_literature ON pali_segments(literature_id);
CREATE INDEX idx_pali_segments_paragraph ON pali_segments(literature_id, paragraph_id);

-- 사용자 저장 세그먼트 (즐겨찾기)
CREATE TABLE user_saved_pali_segments (
    id BIGSERIAL PRIMARY KEY,
    user_id BIGINT NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    segment_id BIGINT NOT NULL REFERENCES pali_segments(id) ON DELETE CASCADE,
    notes TEXT,
    created_at TIMESTAMPTZ DEFAULT NOW(),
    UNIQUE(user_id, segment_id)
);

CREATE INDEX idx_user_saved_pali ON user_saved_pali_segments(user_id);

-- 번역 로그 (사용량 추적)
CREATE TABLE pali_translation_logs (
    id BIGSERIAL PRIMARY KEY,
    user_id BIGINT REFERENCES users(id) ON DELETE SET NULL,
    session_id VARCHAR(100),
    segment_id BIGINT REFERENCES pali_segments(id),
    action VARCHAR(20),          -- 'translate', 'view', 'lookup'
    metadata JSONB,
    created_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX idx_pali_logs_user ON pali_translation_logs(user_id, created_at DESC);
```

#### 3.2 SQLAlchemy 모델 추가

**backend/app/models.py에 추가:**
```python
class PaliLiterature(Base):
    __tablename__ = "pali_literatures"

    id = Column(String(100), primary_key=True)
    title_pali = Column(Text)
    title_korean = Column(Text)
    nikaya = Column(String(50))
    description = Column(Text)
    segment_count = Column(Integer, default=0)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())

    segments = relationship("PaliSegment", back_populates="literature")


class PaliSegment(Base):
    __tablename__ = "pali_segments"

    id = Column(BigInteger, primary_key=True, autoincrement=True)
    literature_id = Column(String(100), ForeignKey("pali_literatures.id"))
    paragraph_id = Column(String(50))
    pali_text = Column(Text, nullable=False)
    korean_translation = Column(Text)
    translation_metadata = Column(JSONB)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())

    literature = relationship("PaliLiterature", back_populates="segments")
```

---

### Phase 4: 프론트엔드 통합 (2-3일)

#### 4.1 React 앱 빌드 설정 수정

**nikaya_gemini/apps/frontend/vite.config.ts:**
```typescript
export default defineConfig({
  base: '/pali/',  // 서브 경로 설정
  build: {
    outDir: 'dist',
    assetsDir: 'assets',
  },
  // ...
});
```

#### 4.2 API 엔드포인트 수정

**nikaya_gemini/apps/frontend/src/api/config.ts:**
```typescript
// 개발 환경
const DEV_API_URL = 'http://localhost:8000/api/v1/pali';

// 프로덕션 환경 (같은 도메인)
const PROD_API_URL = '/api/v1/pali';

export const API_BASE_URL = import.meta.env.DEV ? DEV_API_URL : PROD_API_URL;
```

#### 4.3 인증 상태 연동

**nikaya_gemini/apps/frontend/src/hooks/useAuth.ts:**
```typescript
export function useAuth() {
  const [user, setUser] = useState<User | null>(null);

  useEffect(() => {
    // 기존 Buddha Korea 인증 API 호출
    fetch('/api/users/me', { credentials: 'include' })
      .then(res => res.ok ? res.json() : null)
      .then(data => setUser(data))
      .catch(() => setUser(null));
  }, []);

  return { user, isLoggedIn: !!user };
}
```

#### 4.4 빌드 및 복사

```bash
# 빌드
cd /Users/vairocana/Desktop/nikaya_gemini/apps/frontend
npm run build

# 복사
cp -r dist/* /Users/vairocana/Desktop/buddhakorea/buddhakorea/frontend/pali/
```

---

### Phase 5: nginx 설정 수정 (1일)

#### 5.1 config/nginx.conf 수정

```nginx
# 기존 설정 유지...

server {
    listen 443 ssl http2;
    server_name ai.buddhakorea.com;

    # ... SSL 설정 ...

    # ============================================
    # Pāli Studio (React SPA) - 신규
    # ============================================

    # React 앱 정적 파일
    location /pali/ {
        alias /app/frontend/pali/;
        try_files $uri $uri/ /pali/index.html;

        # 정적 에셋 캐싱
        location ~* \.(js|css|png|jpg|jpeg|gif|ico|svg|woff|woff2)$ {
            expires 1y;
            add_header Cache-Control "public, immutable";
        }
    }

    # Pāli API
    location /api/v1/pali/ {
        proxy_pass http://fastapi_backend;
        proxy_http_version 1.1;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;

        # 번역 요청은 시간이 걸릴 수 있음
        proxy_connect_timeout 60s;
        proxy_send_timeout 120s;
        proxy_read_timeout 120s;
    }

    # ============================================
    # 기존 설정 유지
    # ============================================

    location /api/ {
        # ... 기존 설정 ...
    }

    location /auth/ {
        # ... 기존 설정 ...
    }

    # ... 나머지 기존 설정 ...
}
```

---

### Phase 6: Dockerfile 수정 (1일)

#### 6.1 Dockerfile 수정

```dockerfile
# ... 기존 빌드 스테이지 ...

# Final production stage
FROM python:3.11-slim

# ... 기존 설정 ...

# Copy application code
COPY --chown=buddha:buddha backend/app/ ./app/

# Copy RAG module
COPY --chown=buddha:buddha backend/rag/ ./rag/

# Copy DPD database (신규)
COPY --chown=buddha:buddha backend/data/dpd/ ./data/dpd/

# Copy frontend (including pali/)
COPY --chown=buddha:buddha frontend/ ./frontend/

# ... 나머지 기존 설정 ...
```

#### 6.2 docker-compose.yml 수정 (선택)

DPD DB가 크다면 볼륨으로 분리:

```yaml
services:
  backend:
    # ... 기존 설정 ...
    volumes:
      - ../data/chroma_db:/app/chroma_db
      - ../data/dpd:/app/data/dpd  # DPD 사전 볼륨 (신규)
      - ../data/logs:/app/logs
      # ...
```

---

### Phase 7: 배포 및 테스트 (1-2일)

#### 7.1 로컬 테스트

```bash
# 백엔드 테스트
cd backend
uvicorn app.main:app --reload --port 8000

# API 테스트
curl http://localhost:8000/api/v1/pali/health
curl http://localhost:8000/api/v1/pali/literature
curl http://localhost:8000/api/v1/pali/dpd/buddha
```

#### 7.2 Docker 로컬 테스트

```bash
# 이미지 빌드
docker build -t buddhakorea-test .

# 컨테이너 실행
docker run -p 8000:8000 buddhakorea-test

# 테스트
curl http://localhost:8000/api/v1/pali/health
```

#### 7.3 Hetzner 배포

```bash
# 커밋 및 푸시
git add .
git commit -m "feat: Pāli Studio 통합"
git push origin feature/pali-studio-integration

# PR 생성 및 머지 또는 직접 main에 머지
git checkout main
git merge feature/pali-studio-integration
git push origin main

# GitHub Actions가 자동 배포하거나 수동 배포
ssh root@157.180.72.0
cd /opt/buddha-korea
git pull origin main
docker compose -f config/docker-compose.yml up -d --build
```

#### 7.4 배포 후 검증

```bash
# Health check
curl https://ai.buddhakorea.com/api/health
curl https://ai.buddhakorea.com/api/v1/pali/health

# 페이지 로드
curl -s -o /dev/null -w "%{http_code}" https://ai.buddhakorea.com/pali/

# 기존 기능 확인
curl https://ai.buddhakorea.com/chat.html
```

---

## 4. 타임라인 요약

| Phase | 작업 | 예상 기간 | 의존성 |
|-------|------|----------|--------|
| 0 | 준비 (백업, 브랜치) | 1일 | - |
| 1 | 헤더 통합 + Coming Soon | 1일 | Phase 0 |
| 2 | 백엔드 병합 | 3-4일 | Phase 0 |
| 3 | DB 스키마 확장 | 1-2일 | Phase 2 |
| 4 | 프론트엔드 통합 | 2-3일 | Phase 2 |
| 5 | nginx 설정 | 1일 | Phase 4 |
| 6 | Dockerfile 수정 | 1일 | Phase 4, 5 |
| 7 | 배포 및 테스트 | 1-2일 | All |
| **총계** | | **11-15일** | |

---

## 5. 체크리스트

### Phase 0: 준비
- [ ] 현재 코드 백업 브랜치 생성
- [ ] nikaya_gemini 의존성 분석 완료
- [ ] DPD 데이터베이스 크기/스키마 확인
- [ ] 작업 브랜치 생성

### Phase 1: 헤더 통합
- [ ] index.html 헤더에 "빠알리 스튜디오" 추가
- [ ] chat.html 헤더 수정
- [ ] mypage.html 헤더 수정
- [ ] 기타 HTML 헤더 수정
- [ ] Coming Soon 페이지 생성
- [ ] 로컬 테스트

### Phase 2: 백엔드 병합
- [ ] routers/pali/ 디렉토리 생성
- [ ] literature.py 이식 및 수정
- [ ] translate.py 이식 및 수정
- [ ] dpd.py 이식 및 수정
- [ ] health.py 이식 및 수정
- [ ] dpd_service.py 이식
- [ ] literature_service.py 이식
- [ ] gemini_client.py 통합
- [ ] main.py에 라우터 등록
- [ ] requirements.txt 업데이트
- [ ] 로컬 API 테스트

### Phase 3: 데이터베이스
- [ ] Alembic 마이그레이션 생성
- [ ] pali_literatures 테이블 생성
- [ ] pali_segments 테이블 생성
- [ ] user_saved_pali_segments 테이블 생성
- [ ] pali_translation_logs 테이블 생성
- [ ] SQLAlchemy 모델 추가
- [ ] 마이그레이션 테스트

### Phase 4: 프론트엔드
- [ ] vite.config.ts base 경로 수정
- [ ] API URL 설정 수정
- [ ] 인증 훅 연동
- [ ] npm run build
- [ ] frontend/pali/에 복사
- [ ] 로컬 테스트

### Phase 5: nginx
- [ ] /pali/ location 추가
- [ ] /api/v1/pali/ location 추가
- [ ] nginx 설정 문법 검증
- [ ] 로컬 테스트

### Phase 6: Docker
- [ ] Dockerfile에 DPD 복사 추가
- [ ] Dockerfile에 pali/ 포함 확인
- [ ] docker-compose.yml 볼륨 추가 (필요시)
- [ ] 로컬 Docker 빌드 테스트

### Phase 7: 배포
- [ ] 코드 커밋 및 푸시
- [ ] Hetzner 배포
- [ ] Health check 확인
- [ ] Pāli 페이지 로드 확인
- [ ] 기존 기능 회귀 테스트
- [ ] 성능 모니터링

---

## 6. 롤백 계획

문제 발생 시:

```bash
# 1. nginx를 이전 설정으로 복원
ssh root@157.180.72.0
cd /opt/buddha-korea
git checkout HEAD~1 -- config/nginx.conf
docker compose -f config/docker-compose.yml restart nginx

# 2. 전체 롤백 필요 시
git reset --hard backup/pre-pali-integration
docker compose -f config/docker-compose.yml down
docker compose -f config/docker-compose.yml up -d --build

# 3. DB 롤백 필요 시 (마이그레이션 되돌리기)
alembic downgrade -1
```

---

## 7. 참고 자료

- 원본 계획서: `nikaya_gemini/docs/BUDDHA_KOREA_INTEGRATION_PLAN.md`
- Buddha Korea 배포 가이드: `docs/DEPLOYMENT_GUIDE.md`
- 빠른 체크리스트: `docs/QUICK_CHECKLIST.md`

---

*End of Document*

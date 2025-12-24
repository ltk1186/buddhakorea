# Pāli Studio 통합 계획

> Buddha Korea + nikaya_gemini 합병 상세 계획서
>
> **Version:** 2.1 (리뷰 반영)
> **Date:** 2024-12-25
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

#### 2.7 DPD 힌트 시스템 (핵심 기능)

번역 품질의 핵심은 **DPD (Digital Pali Dictionary) 힌트 시스템**입니다.

**작동 원리:**
1. 번역 전 각 빠알리 단어를 DPD에서 조회
2. 품사(POS), 성(gender), 격(case), 수(number) 정보 추출
3. LLM 프롬프트에 문법 힌트로 포함
4. 환각(hallucination) 감소 및 일관성 향상

**이식 대상:**
| 원본 | 대상 | 설명 |
|------|------|------|
| `apps/backend/services/hint_generator.py` | `backend/app/services/hint_generator.py` | 힌트 생성 로직 |
| `tools/dpd_lookup.py` | `backend/app/services/dpd_lookup.py` | DPD 조회 (선택) |

**프롬프트 예시:**
```
[DPD Hints for segment]
dhammā: noun, masc, nom/voc, pl (법)
sabbe: adj, masc, nom/voc, pl (모든)
manopubbaṅgamā: compound (마노+뿝방가마)

[Pali text to translate]
Manopubbaṅgamā dhammā...
```

---

### Phase 3: 데이터베이스 확장 및 데이터 이식 (1-2일)

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

#### 3.3 기존 번역 데이터 이식

**nikaya_gemini에 이미 번역된 데이터가 존재합니다:**

| 문헌 | 세그먼트 수 | 파일 위치 |
|------|------------|----------|
| Suttanipata Commentary | 637 | `data/projects/suttanipata_commentary/` |
| Mahaniddesa Commentary | 364 | `data/projects/mahaniddesa_commentary/` |
| Culaniddesa Full | 2 | `data/projects/culaniddesa_commentary/` |
| **총계** | **1,003+** | |

**이식 방법:**
```bash
# 1. JSON 데이터 복사
cp -r nikaya_gemini/data/projects/* buddhakorea/backend/data/pali_projects/

# 2. Admin API로 import (기존 엔드포인트 활용)
curl -X POST https://ai.buddhakorea.com/api/v1/pali/admin/import \
  -H "Authorization: Bearer $ADMIN_TOKEN" \
  -F "file=@Suttanipata_Commentary_Processed.json"

# 또는 직접 DB 스크립트
python scripts/import_pali_data.py --source data/pali_projects/
```

> **참고**: 새 PDF 파싱이 필요한 경우 `POST /api/v1/pali/admin/parse-pdf` 엔드포인트 사용

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

nikaya_gemini는 자체 인증이 없으므로, buddhakorea의 세션 기반 인증과 통합해야 합니다.

**nikaya_gemini/apps/frontend/src/hooks/useAuth.ts (신규 생성):**
```typescript
import { useState, useEffect } from 'react';

interface User {
  id: number;
  email: string;
  nickname: string;
  provider: string;
}

export function useAuth() {
  const [user, setUser] = useState<User | null>(null);
  const [isLoading, setIsLoading] = useState(true);

  useEffect(() => {
    // Buddha Korea 인증 API 호출
    // credentials: 'include'로 HttpOnly 쿠키 전송
    fetch('/api/users/me', {
      credentials: 'include',
      headers: { 'Accept': 'application/json' }
    })
      .then(res => {
        if (res.ok) return res.json();
        if (res.status === 401) return null; // 비로그인 상태
        throw new Error('Auth check failed');
      })
      .then(data => setUser(data))
      .catch(() => setUser(null))
      .finally(() => setIsLoading(false));
  }, []);

  const login = () => {
    // 로그인 페이지로 리다이렉트 (현재 URL을 redirect 파라미터로)
    window.location.href = `/auth/login/google?redirect=${encodeURIComponent(window.location.pathname)}`;
  };

  const logout = async () => {
    await fetch('/auth/logout', {
      method: 'POST',
      credentials: 'include'
    });
    setUser(null);
    window.location.reload();
  };

  return { user, isLoading, isLoggedIn: !!user, login, logout };
}
```

**기존 useSession.ts 수정 (sessionId → 실제 인증 연동):**
```typescript
// 기존: 로컬 sessionId만 관리
// 수정: useAuth 훅과 연동하여 로그인 사용자는 user.id 사용

import { useAuth } from './useAuth';

export function useSession() {
  const { user, isLoggedIn } = useAuth();

  // 로그인 시 user.id, 비로그인 시 localStorage sessionId
  const sessionId = isLoggedIn
    ? `user-${user.id}`
    : localStorage.getItem('pali-session-id') || generateSessionId();

  return { sessionId, isLoggedIn, user };
}
```

#### 4.4 인증 통합 테스트 체크리스트

배포 전 반드시 확인:

- [ ] `/pali/` 접속 시 `/api/users/me` 호출 확인 (DevTools → Network)
- [ ] 요청에 `Cookie: session=...` 헤더 포함 확인
- [ ] 비로그인 상태: 401 응답, `user = null`
- [ ] 로그인 상태: 200 응답, 사용자 정보 표시
- [ ] 로그인 버튼 → Google OAuth → `/pali/`로 리다이렉트
- [ ] 로그아웃 → 세션 쿠키 삭제 확인

**문제 발생 시 확인:**
```bash
# 쿠키 설정 확인
curl -v https://ai.buddhakorea.com/api/users/me \
  -H "Cookie: session=YOUR_SESSION_VALUE"

# CORS 확인 (same-origin이면 문제 없음)
# credentials: 'include' 시 SameSite 설정 확인
```

#### 4.5 빌드 및 복사

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

#### 6.3 배포 자동화 스크립트

수동 배포 명령을 스크립트로 자동화하여 휴먼 에러를 방지합니다.

**scripts/deploy_pali.sh:**
```bash
#!/bin/bash
set -e

# 색상 정의
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

echo -e "${YELLOW}[1/5] Pulling latest code...${NC}"
cd /opt/buddha-korea
git pull origin main

echo -e "${YELLOW}[2/5] Building Docker image...${NC}"
docker compose -f config/docker-compose.yml build --no-cache backend

echo -e "${YELLOW}[3/5] Restarting containers...${NC}"
docker compose -f config/docker-compose.yml up -d

echo -e "${YELLOW}[4/5] Waiting for health check (30s)...${NC}"
sleep 30

echo -e "${YELLOW}[5/5] Verifying deployment...${NC}"

# Health checks
MAIN_HEALTH=$(curl -s -o /dev/null -w "%{http_code}" https://ai.buddhakorea.com/api/health)
PALI_HEALTH=$(curl -s -o /dev/null -w "%{http_code}" https://ai.buddhakorea.com/api/v1/pali/health)
PALI_PAGE=$(curl -s -o /dev/null -w "%{http_code}" https://ai.buddhakorea.com/pali/)

if [ "$MAIN_HEALTH" = "200" ] && [ "$PALI_HEALTH" = "200" ] && [ "$PALI_PAGE" = "200" ]; then
    echo -e "${GREEN}✅ Deployment successful!${NC}"
    echo "  - Main API: $MAIN_HEALTH"
    echo "  - Pāli API: $PALI_HEALTH"
    echo "  - Pāli Page: $PALI_PAGE"
else
    echo -e "${RED}❌ Deployment verification failed!${NC}"
    echo "  - Main API: $MAIN_HEALTH (expected 200)"
    echo "  - Pāli API: $PALI_HEALTH (expected 200)"
    echo "  - Pāli Page: $PALI_PAGE (expected 200)"
    echo ""
    echo -e "${YELLOW}Rolling back...${NC}"
    git checkout HEAD~1
    docker compose -f config/docker-compose.yml up -d --build
    exit 1
fi
```

**사용법:**
```bash
# 서버에 스크립트 복사
scp scripts/deploy_pali.sh root@157.180.72.0:/opt/buddha-korea/scripts/

# 실행 권한 부여
ssh root@157.180.72.0 "chmod +x /opt/buddha-korea/scripts/deploy_pali.sh"

# 배포 실행
ssh root@157.180.72.0 "/opt/buddha-korea/scripts/deploy_pali.sh"
```

---

### Phase 7: 테스트 및 배포 (2일)

#### 7.1 자동화된 테스트 실행

nikaya_gemini에 이미 존재하는 테스트를 이식하고 확장합니다.

**기존 테스트 이식 (nikaya_gemini/apps/backend/tests/):**
```bash
# 테스트 디렉토리 복사
cp -r nikaya_gemini/apps/backend/tests/* buddhakorea/backend/tests/pali/

# 구조:
# backend/tests/
# ├── conftest.py          # 기존 + pali fixtures 추가
# ├── test_auth.py         # 기존 인증 테스트
# ├── test_chat.py         # 기존 채팅 테스트
# └── pali/                # ← 신규
#     ├── conftest.py      # Pāli 전용 fixtures
#     ├── test_literature.py  # ~45 테스트 케이스
#     └── test_dpd.py      # DPD 조회 테스트
```

**추가 테스트 작성:**
```python
# backend/tests/pali/test_translate.py
import pytest
from unittest.mock import AsyncMock, patch

@pytest.mark.asyncio
async def test_translate_segment_unauthorized(client):
    """비로그인 사용자 번역 요청 - 제한 확인"""
    response = await client.post("/api/v1/pali/translate/1")
    # 로그인 필요 또는 rate limit
    assert response.status_code in [401, 429]

@pytest.mark.asyncio
@patch('app.services.gemini_client.translate_with_hints_stream')
async def test_translate_segment_success(mock_gemini, client, auth_headers):
    """번역 요청 성공 - Gemini 응답 모킹"""
    mock_gemini.return_value = AsyncMock(return_value={
        "sentences": [{"original_pali": "test", "translation": "테스트"}]
    })
    response = await client.post(
        "/api/v1/pali/translate/1",
        headers=auth_headers
    )
    assert response.status_code == 200

# backend/tests/pali/test_integration.py
@pytest.mark.asyncio
async def test_auth_integration_with_pali(client, logged_in_session):
    """로그인 세션으로 Pāli API 접근"""
    response = await client.get(
        "/api/v1/pali/literature",
        cookies=logged_in_session
    )
    assert response.status_code == 200
```

**테스트 실행:**
```bash
cd backend

# 전체 테스트
pytest tests/ -v

# Pāli 테스트만
pytest tests/pali/ -v

# 커버리지 포함
pytest tests/ --cov=app --cov-report=html
```

#### 7.2 로컬 통합 테스트

```bash
# 백엔드 실행
cd backend
uvicorn app.main:app --reload --port 8000

# API 테스트
curl http://localhost:8000/api/v1/pali/health
curl http://localhost:8000/api/v1/pali/literature
curl http://localhost:8000/api/v1/pali/dpd/buddha
```

#### 7.3 Docker 로컬 테스트

```bash
# 이미지 빌드
docker build -t buddhakorea-test .

# 컨테이너 실행
docker run -p 8000:8000 buddhakorea-test

# 테스트
curl http://localhost:8000/api/v1/pali/health
```

#### 7.4 Hetzner 배포

```bash
# 커밋 및 푸시
git add .
git commit -m "feat: Pāli Studio 통합"
git push origin feature/pali-studio-integration

# PR 생성 및 머지 또는 직접 main에 머지
git checkout main
git merge feature/pali-studio-integration
git push origin main

# 자동화 스크립트로 배포 (권장)
ssh root@157.180.72.0 "/opt/buddha-korea/scripts/deploy_pali.sh"

# 또는 수동 배포
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
| 2 | 백엔드 병합 + DPD 힌트 | 3-4일 | Phase 0 |
| 3 | DB 스키마 확장 + 데이터 이식 | 1-2일 | Phase 2 |
| 4 | 프론트엔드 통합 + 인증 연동 | 2-3일 | Phase 2 |
| 5 | nginx 설정 | 1일 | Phase 4 |
| 6 | Dockerfile + 배포 스크립트 | 1일 | Phase 4, 5 |
| 7 | 테스트 및 배포 | 2일 | All |
| 8 | 문서 업데이트 | 0.5일 | Phase 7 |
| **총계** | | **12-16일** | |

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
- [ ] **hint_generator.py 이식** (DPD 힌트 시스템)
- [ ] gemini_client.py 통합
- [ ] main.py에 라우터 등록
- [ ] requirements.txt 업데이트 (aiosqlite)
- [ ] 로컬 API 테스트

### Phase 3: 데이터베이스 및 데이터 이식
- [ ] Alembic 마이그레이션 생성
- [ ] pali_literatures 테이블 생성
- [ ] pali_segments 테이블 생성
- [ ] user_saved_pali_segments 테이블 생성
- [ ] pali_translation_logs 테이블 생성
- [ ] SQLAlchemy 모델 추가
- [ ] 마이그레이션 테스트
- [ ] **기존 번역 데이터 복사** (data/projects/)
- [ ] **Admin API로 데이터 import 또는 스크립트 실행**

### Phase 4: 프론트엔드 및 인증 통합
- [ ] vite.config.ts base 경로 수정
- [ ] API URL 설정 수정
- [ ] **useAuth.ts 훅 생성** (Buddha Korea 세션 연동)
- [ ] **useSession.ts 수정** (로그인 사용자 ID 사용)
- [ ] npm run build
- [ ] frontend/pali/에 복사
- [ ] 로컬 테스트
- [ ] **인증 통합 테스트** (쿠키 전송 확인)

### Phase 5: nginx
- [ ] /pali/ location 추가
- [ ] /api/v1/pali/ location 추가
- [ ] nginx 설정 문법 검증
- [ ] 로컬 테스트

### Phase 6: Docker 및 배포 자동화
- [ ] Dockerfile에 DPD 복사 추가
- [ ] Dockerfile에 pali/ 포함 확인
- [ ] docker-compose.yml 볼륨 추가 (필요시)
- [ ] 로컬 Docker 빌드 테스트
- [ ] **deploy_pali.sh 스크립트 작성**
- [ ] **서버에 스크립트 복사 및 권한 부여**

### Phase 7: 테스트 및 배포
- [ ] 기존 테스트 이식 (tests/pali/)
- [ ] 추가 테스트 작성 (translate, auth integration)
- [ ] pytest 전체 실행 및 통과 확인
- [ ] 코드 커밋 및 푸시
- [ ] 배포 스크립트로 Hetzner 배포
- [ ] Health check 확인 (main + pali)
- [ ] Pāli 페이지 로드 확인
- [ ] 인증 통합 테스트 (DevTools에서 쿠키 확인)
- [ ] 기존 기능 회귀 테스트
- [ ] 성능 모니터링

### Phase 8: 문서 업데이트
- [ ] README.md에 Pāli Studio 섹션 추가
- [ ] API 문서 확인 (Swagger /docs)
- [ ] 배포 가이드에 Pāli 관련 내용 추가

---

## 6. 롤백 계획

> **중요**: `git reset --hard`는 프로덕션에서 위험합니다. 대신 `git revert` 또는 태그 기반 롤백을 사용하세요.

### 6.1 배포 전 태그 생성 (권장)

```bash
# 배포 전 현재 상태에 태그
git tag -a v1.0-pre-pali -m "Before Pāli Studio integration"
git push origin v1.0-pre-pali
```

### 6.2 롤백 시나리오

**시나리오 A: nginx 설정 문제만 있을 때**
```bash
ssh root@157.180.72.0
cd /opt/buddha-korea
git checkout HEAD~1 -- config/nginx.conf
docker compose -f config/docker-compose.yml restart nginx
```

**시나리오 B: 전체 롤백 필요 시 (revert 사용)**
```bash
ssh root@157.180.72.0
cd /opt/buddha-korea

# 마지막 커밋을 되돌리는 새 커밋 생성 (안전)
git revert HEAD --no-edit
git push origin main

# 또는 태그로 롤백
git checkout v1.0-pre-pali
docker compose -f config/docker-compose.yml up -d --build
```

**시나리오 C: DB 롤백 필요 시**
```bash
# 컨테이너 내부에서 Alembic 실행
docker exec buddhakorea-backend alembic downgrade -1

# 또는 특정 리비전으로
docker exec buddhakorea-backend alembic downgrade <revision_id>
```

### 6.3 롤백 체크리스트

- [ ] 롤백 후 `/api/health` 응답 확인
- [ ] 기존 기능 (채팅, 로그인) 정상 동작 확인
- [ ] Pāli 관련 경로가 404 반환하는지 확인 (예상 동작)
- [ ] 에러 로그 확인: `docker logs buddhakorea-backend --tail 100`

---

## 7. 참고 자료

### 문서
- 원본 계획서: `nikaya_gemini/docs/BUDDHA_KOREA_INTEGRATION_PLAN.md`
- Buddha Korea 배포 가이드: `docs/DEPLOYMENT_GUIDE.md`
- 빠른 체크리스트: `docs/QUICK_CHECKLIST.md`
- Cloudflare 마이그레이션: `docs/MIGRATION_NOTES.md`

### nikaya_gemini 주요 파일
| 파일 | 용도 |
|------|------|
| `apps/backend/tests/` | 테스트 코드 (~45 케이스) |
| `apps/frontend/src/hooks/useSSE.ts` | SSE 스트리밍 훅 |
| `apps/frontend/src/utils/paliTokenizer.ts` | 빠알리 단어 토크나이저 |
| `data/dpd/dpd.db` | DPD 사전 (2GB) |
| `data/projects/` | 번역된 세그먼트 JSON |
| `tools/` | CLI 배치 번역 도구 |

### 성능 목표

| 메트릭 | 목표 | 측정 방법 |
|--------|------|----------|
| 문헌 목록 조회 | < 200ms | `/api/v1/pali/literature` 응답 시간 |
| DPD 단어 조회 | < 100ms | `/api/v1/pali/dpd/{word}` 응답 시간 |
| 세그먼트 번역 | < 30s | SSE 첫 토큰까지 시간 |
| React 앱 초기 로드 | < 3s | Lighthouse Performance 점수 |

---

*End of Document*

# 프로젝트 구조 마이그레이션 노트 (2024-12-16)

## 변경 사항 요약

### 새로운 디렉토리 구조

```
buddhakorea/
├── frontend/          # 정적 웹사이트
├── backend/           # Python RAG 시스템
│   └── app/           # FastAPI 앱 (이전 opennotebook/)
├── data/              # 대용량 데이터 (gitignored)
│   ├── chroma_db/     # 벡터 DB
│   └── source_data/   # 소스 데이터
├── config/            # Docker/서버 설정
│   ├── docker-compose.yml
│   ├── nginx.conf
│   └── redis.conf
├── scripts/           # 배포 스크립트
└── docs/              # 문서
```

### Hetzner 서버 배포 시 필수 작업

#### 1. 서버에서 새 구조로 업데이트

```bash
cd /opt/buddha-korea
git pull origin main

# 데이터 디렉토리 구조 생성 (최초 1회)
mkdir -p data/chroma_db data/source_data data/logs

# 기존 데이터 이동 (필요시)
mv chroma_db/* data/chroma_db/
mv source_explorer/source_data/* data/source_data/
```

#### 2. Docker 재빌드 및 배포

```bash
cd /opt/buddha-korea/config
docker-compose down
docker-compose build --no-cache backend
docker-compose up -d
```

#### 3. 확인

```bash
# 컨테이너 상태 확인
docker-compose ps

# 헬스체크
curl http://localhost:8000/api/health

# 로그 확인
docker-compose logs -f backend
```

### 경로 변경 매핑

| 이전 경로 | 새 경로 |
|----------|---------|
| `opennotebook/main.py` | `backend/app/main.py` |
| `opennotebook/chroma_db/` | `data/chroma_db/` |
| `opennotebook/source_explorer/source_data/` | `data/source_data/` |
| `opennotebook/docker-compose.yml` | `config/docker-compose.yml` |
| `opennotebook/*.py` | `backend/app/*.py` |

### docker-compose 실행 위치

**중요**: docker-compose는 이제 `config/` 디렉토리에서 실행해야 합니다:

```bash
cd /opt/buddha-korea/config
docker-compose up -d
```

### 환경 변수

`.env` 파일은 프로젝트 루트에 위치해야 합니다:
- `/opt/buddha-korea/.env`

docker-compose.yml에서 `../.env`로 참조합니다.

### 롤백

문제 발생 시:

```bash
cd /opt/buddha-korea
git checkout HEAD~1  # 이전 커밋으로
cd config
docker-compose down
docker-compose up -d
```

또는 백업에서 복원:
```bash
cp -r /opt/buddha-korea_backup_YYYYMMDD/* /opt/buddha-korea/
```

---

# 단일 도메인 통합 마이그레이션 계획

> **목표:** Cloudflare 이전 시점에 서브도메인(ai.buddhakorea.com) → 단일 도메인(buddhakorea.com) 통합
>
> **상태:** 계획 단계 (현재는 서브도메인 구조 유지)
>
> **예상 시점:** Cloudflare 도입 시

---

## 1. 현재 vs 목표 구조

### 현재 구조 (서브도메인)

```
buddhakorea.com (GitHub Pages)
├── /                      → index.html (정적)
├── /sutra-writing.html    → 사경 (정적)
├── /meditation.html       → 명상 (정적)
└── /methodology.html      → 방법론 (정적)

ai.buddhakorea.com (Hetzner VM)
├── /                      → /chat.html 리다이렉트
├── /chat.html             → AI 챗봇
├── /mypage.html           → 마이페이지
├── /pali/                 → 빠알리 스튜디오 (예정)
├── /api/*                 → REST API
└── /auth/*                → OAuth
```

**문제점:**
- 크로스도메인 쿠키 복잡 (`SameSite=None` 필요)
- 브라우저 3rd-party cookie 제한 추세
- CORS 설정 필요
- 사용자 경험: 도메인 이동 느낌

### 목표 구조 (단일 도메인)

```
buddhakorea.com (Cloudflare → Hetzner VM)
├── /                      → index.html (정적, CDN 캐시)
├── /sutra-writing.html    → 사경 (정적, CDN 캐시)
├── /meditation.html       → 명상 (정적, CDN 캐시)
├── /methodology.html      → 방법론 (정적, CDN 캐시)
├── /css/*                 → CSS (정적, CDN 캐시)
├── /js/*                  → JS (정적, CDN 캐시)
├── /assets/*              → 이미지 등 (정적, CDN 캐시)
│
├── /chat                  → AI 챗봇 (동적, no-cache)
├── /mypage                → 마이페이지 (동적, no-cache)
├── /pali/*                → 빠알리 스튜디오 (React SPA)
│
├── /api/*                 → REST API (no-cache)
└── /auth/*                → OAuth (no-cache)

ai.buddhakorea.com → 301 Redirect to buddhakorea.com/*
```

**장점:**
- Same-origin 쿠키 (`SameSite=Lax` 충분)
- CORS 불필요
- 브라우저 제한 회피
- 일관된 UX
- 향후 기능 확장 용이

---

## 2. URL 설계

### 2.1 최종 URL 구조

| 경로 | 용도 | 캐시 정책 | 비고 |
|------|------|----------|------|
| `/` | 메인 페이지 | CDN 캐시 | index.html |
| `/sutra-writing` | 사경 | CDN 캐시 | .html 확장자 제거 |
| `/meditation` | 명상 | CDN 캐시 | .html 확장자 제거 |
| `/chat` | AI 챗봇 | no-cache | 동적 페이지 |
| `/mypage` | 마이페이지 | no-cache | 인증 필요 |
| `/pali/*` | 빠알리 스튜디오 | SPA 규칙 | React 앱 |
| `/api/v1/*` | REST API | no-cache | 백엔드 프록시 |
| `/auth/*` | OAuth | no-cache | 쿠키 설정 |
| `/css/*`, `/js/*`, `/assets/*` | 정적 파일 | CDN 캐시 (1년) | immutable |

### 2.2 301 리다이렉트 매핑

```
ai.buddhakorea.com/              → buddhakorea.com/chat
ai.buddhakorea.com/chat.html     → buddhakorea.com/chat
ai.buddhakorea.com/mypage.html   → buddhakorea.com/mypage
ai.buddhakorea.com/pali/*        → buddhakorea.com/pali/*
ai.buddhakorea.com/api/*         → buddhakorea.com/api/*
ai.buddhakorea.com/auth/*        → buddhakorea.com/auth/*
```

### 2.3 .html 확장자 제거 (Clean URLs)

**Before:**
```
/chat.html
/mypage.html
/sutra-writing.html
```

**After:**
```
/chat
/mypage
/sutra-writing
```

**nginx 설정:**
```nginx
# .html 확장자 없이 접근 가능하게
location / {
    try_files $uri $uri.html $uri/ =404;
}
```

---

## 3. 인프라 마이그레이션

### 3.1 DNS 변경 계획

**현재:**
```
buddhakorea.com      A     185.199.108.153 (GitHub Pages)
                     A     185.199.109.153
                     A     185.199.110.153
                     A     185.199.111.153

ai.buddhakorea.com   A     157.180.72.0 (Hetzner)
```

**변경 후:**
```
buddhakorea.com      CNAME  buddhakorea.com.cdn.cloudflare.net (Cloudflare 프록시)
ai.buddhakorea.com   CNAME  buddhakorea.com (리다이렉트용)
```

### 3.2 Cloudflare 설정

**DNS Records:**
```
Type    Name                  Content              Proxy
A       buddhakorea.com       157.180.72.0         Proxied (orange)
CNAME   ai.buddhakorea.com    buddhakorea.com      Proxied (orange)
```

**Page Rules / Cache Rules:**
```yaml
# 정적 파일 - 캐시
*.buddhakorea.com/css/*
*.buddhakorea.com/js/*
*.buddhakorea.com/assets/*
  Cache Level: Cache Everything
  Edge TTL: 1 year
  Browser TTL: 1 year

# HTML 페이지 - 단기 캐시
*.buddhakorea.com/*.html
*.buddhakorea.com/
  Cache Level: Cache Everything
  Edge TTL: 1 hour
  Browser TTL: 10 minutes

# API/Auth - 캐시 안함
*.buddhakorea.com/api/*
*.buddhakorea.com/auth/*
  Cache Level: Bypass

# Pāli SPA - HTML만 단기 캐시
*.buddhakorea.com/pali/*
  Cache Level: Standard
```

**Redirect Rules:**
```yaml
# ai.buddhakorea.com → buddhakorea.com 리다이렉트
If: (http.host eq "ai.buddhakorea.com")
Then: Dynamic Redirect to
      concat("https://buddhakorea.com", http.request.uri.path)
      Status: 301
```

### 3.3 Hetzner nginx 설정 (마이그레이션 후)

```nginx
server {
    listen 443 ssl http2;
    server_name buddhakorea.com www.buddhakorea.com;

    # SSL (Cloudflare Origin Certificate 또는 Let's Encrypt)
    ssl_certificate /etc/nginx/ssl/cloudflare-origin.pem;
    ssl_certificate_key /etc/nginx/ssl/cloudflare-origin.key;

    # =============================================
    # API & Auth (no-cache, 백엔드 프록시)
    # =============================================

    location /api/ {
        proxy_pass http://fastapi_backend;
        proxy_http_version 1.1;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;

        # Cloudflare는 X-Forwarded-Proto 대신 CF-Visitor 사용
        proxy_set_header CF-Visitor $http_cf_visitor;

        # 캐시 방지
        add_header Cache-Control "no-store, no-cache, must-revalidate";
    }

    location /auth/ {
        proxy_pass http://fastapi_backend;
        proxy_http_version 1.1;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto https;  # Cloudflare 뒤에서 항상 HTTPS

        add_header Cache-Control "no-store, no-cache, must-revalidate";
    }

    # =============================================
    # 동적 페이지 (chat, mypage)
    # =============================================

    location = /chat {
        proxy_pass http://fastapi_backend/chat.html;
        proxy_set_header Host $host;
        proxy_set_header X-Forwarded-Proto https;
    }

    location = /mypage {
        proxy_pass http://fastapi_backend/mypage.html;
        proxy_set_header Host $host;
        proxy_set_header X-Forwarded-Proto https;
    }

    # =============================================
    # Pāli Studio (React SPA)
    # =============================================

    location /pali/ {
        alias /app/frontend/pali/;
        try_files $uri $uri/ /pali/index.html;
    }

    # =============================================
    # 정적 파일 (CDN 캐시)
    # =============================================

    location /css/ {
        alias /app/frontend/css/;
        expires 1y;
        add_header Cache-Control "public, immutable";
    }

    location /js/ {
        alias /app/frontend/js/;
        expires 1y;
        add_header Cache-Control "public, immutable";
    }

    location /assets/ {
        alias /app/frontend/assets/;
        expires 1y;
        add_header Cache-Control "public, immutable";
    }

    # =============================================
    # HTML 페이지 (Clean URLs)
    # =============================================

    location / {
        root /app/frontend;
        try_files $uri $uri.html $uri/ /index.html;

        # HTML 단기 캐시
        location ~* \.html$ {
            add_header Cache-Control "public, max-age=600";  # 10분
        }
    }
}

# ai.buddhakorea.com 리다이렉트 (Cloudflare에서 처리하지만 fallback)
server {
    listen 443 ssl http2;
    server_name ai.buddhakorea.com;

    ssl_certificate /etc/nginx/ssl/cloudflare-origin.pem;
    ssl_certificate_key /etc/nginx/ssl/cloudflare-origin.key;

    return 301 https://buddhakorea.com$request_uri;
}
```

---

## 4. 인증/OAuth 마이그레이션

### 4.1 OAuth Redirect URI 변경

**Google Cloud Console:**
```
현재:
  https://ai.buddhakorea.com/auth/callback/google

추가:
  https://buddhakorea.com/auth/callback/google

마이그레이션 완료 후 제거:
  https://ai.buddhakorea.com/auth/callback/google
```

**Naver/Kakao 동일하게 처리**

### 4.2 환경변수 변경

**현재 (.env):**
```bash
ALLOWED_ORIGINS=https://ai.buddhakorea.com,https://buddhakorea.com
COOKIE_DOMAIN=.buddhakorea.com
```

**변경 후 (.env):**
```bash
# 단일 도메인이므로 CORS 불필요하거나 단순화
ALLOWED_ORIGINS=https://buddhakorea.com

# 쿠키 도메인 (same-origin이므로 비워도 됨)
COOKIE_DOMAIN=
# 또는 명시적으로
COOKIE_DOMAIN=buddhakorea.com
```

### 4.3 쿠키 설정 변경

**현재 (크로스도메인):**
```python
# backend/app/main.py
response.set_cookie(
    key="access_token",
    value=token,
    httponly=True,
    secure=True,
    samesite="none",      # 크로스도메인 필수
    domain=".buddhakorea.com",
    max_age=3600
)
```

**변경 후 (same-origin):**
```python
# backend/app/main.py
response.set_cookie(
    key="access_token",
    value=token,
    httponly=True,
    secure=True,
    samesite="lax",       # same-origin에서는 Lax로 충분
    # domain 생략 (same-origin)
    max_age=3600
)
```

### 4.4 SessionMiddleware 설정

**변경 후:**
```python
app.add_middleware(
    SessionMiddleware,
    secret_key=config.secret_key,
    same_site="lax",      # Lax로 변경 가능
    https_only=True,      # Cloudflare가 항상 HTTPS
    max_age=600,
)
```

---

## 5. 프론트엔드 마이그레이션

### 5.1 GitHub Pages 의존성 제거

**현재 GitHub Pages 의존 항목:**
- CNAME 파일 (buddhakorea.com)
- deploy-pages.yml GitHub Action
- GitHub Pages 설정

**제거 대상:**
- `.github/workflows/deploy-pages.yml` → 삭제 또는 비활성화
- `CNAME` → Hetzner로 이동

### 5.2 API Base URL 통일

**현재 (chat.html 내):**
```javascript
const API_BASE = 'https://ai.buddhakorea.com';
// 또는
const API_BASE = window.location.origin;
```

**변경 후:**
```javascript
// 상대 경로 사용 (same-origin)
const API_BASE = '';

// API 호출
fetch('/api/v1/chat', { credentials: 'include' });
```

### 5.3 정적 파일 경로

**현재:**
```html
<!-- buddhakorea.com (GitHub Pages) -->
<link rel="stylesheet" href="css/styles.css">

<!-- ai.buddhakorea.com (Hetzner) -->
<link rel="stylesheet" href="/css/styles.css">
```

**변경 후 (통일):**
```html
<!-- 모든 페이지에서 동일 -->
<link rel="stylesheet" href="/css/styles.css">
<script src="/js/main.js"></script>
```

### 5.4 React 앱 (Pāli Studio) 설정

**vite.config.ts:**
```typescript
export default defineConfig({
  base: '/pali/',  // 유지
  build: {
    outDir: 'dist',
  },
});
```

**API 호출:**
```typescript
// 상대 경로 사용
const API_BASE = '/api/v1/pali';

// 인증 상태 확인
fetch('/api/users/me', { credentials: 'include' });
```

---

## 6. 마이그레이션 실행 계획

### Phase 1: 준비 (D-7)

```
□ Cloudflare 계정 생성 및 도메인 추가
□ Cloudflare Origin Certificate 발급
□ Google/Naver/Kakao OAuth에 새 callback URI 추가
□ 테스트 서브도메인 설정 (test.buddhakorea.com)
□ 스테이징 환경에서 전체 플로우 테스트
```

### Phase 2: 코드 준비 (D-3)

```
□ nginx.conf 마이그레이션 버전 준비
□ .env 마이그레이션 버전 준비
□ 쿠키 설정 변경 (SameSite=Lax)
□ API Base URL 상대 경로로 변경
□ GitHub Pages 의존 코드 제거
□ 로컬 테스트 완료
```

### Phase 3: DNS TTL 준비 (D-1)

```
□ buddhakorea.com DNS TTL을 300초(5분)로 낮춤
□ ai.buddhakorea.com DNS TTL을 300초로 낮춤
□ 변경 전 전체 백업
□ 롤백 스크립트 준비
```

### Phase 4: 마이그레이션 실행 (D-Day)

```
□ 1. Hetzner에 새 nginx.conf 배포
□ 2. Hetzner에 새 .env 배포
□ 3. 백엔드 재시작
□ 4. 기능 테스트 (ai.buddhakorea.com에서)
□ 5. Cloudflare DNS 프록시 활성화
□ 6. DNS 변경: buddhakorea.com → Cloudflare
□ 7. DNS 전파 대기 (5-30분)
□ 8. 전체 기능 테스트 (buddhakorea.com에서)
□ 9. ai.buddhakorea.com 리다이렉트 확인
```

### Phase 5: 검증 (D+1)

```
□ 로그인 플로우 테스트 (Google/Naver/Kakao)
□ 쿠키 저장/전송 확인
□ API 호출 확인
□ CDN 캐시 동작 확인
□ 모바일 테스트
□ 성능 모니터링
```

### Phase 6: 정리 (D+7)

```
□ 구 OAuth callback URI 제거
□ GitHub Pages 비활성화
□ DNS TTL 복원 (3600초)
□ 모니터링 지속
□ 문서 업데이트
```

---

## 7. 롤백 계획

### 7.1 즉시 롤백 (DNS 전환 후 문제 발생 시)

```bash
# 1. Cloudflare에서 프록시 비활성화 (DNS Only로 변경)
# 또는 DNS를 GitHub Pages IP로 복원

# 2. ai.buddhakorea.com 리다이렉트 제거

# 3. Hetzner nginx를 이전 설정으로 복원
ssh root@157.180.72.0
cd /opt/buddha-korea
git checkout HEAD~1 -- config/nginx.conf
docker compose -f config/docker-compose.yml restart nginx

# 4. .env 복원
git checkout HEAD~1 -- .env
docker compose -f config/docker-compose.yml restart backend
```

### 7.2 부분 롤백 (특정 기능만 문제 시)

```bash
# OAuth만 문제인 경우: callback URI 확인
# 쿠키만 문제인 경우: SameSite 설정 확인
# 캐시만 문제인 경우: Cloudflare Cache Purge

# Cloudflare Dashboard → Caching → Configuration → Purge Everything
```

### 7.3 롤백 판단 기준

| 증상 | 롤백 여부 | 대응 |
|------|----------|------|
| 로그인 완전 불가 | 즉시 롤백 | DNS 복원 |
| 일부 페이지 404 | 조사 후 판단 | nginx 설정 확인 |
| CDN 캐시 이상 | 롤백 불필요 | Cache Purge |
| 성능 저하 | 롤백 불필요 | Cloudflare 설정 조정 |
| OAuth 일부 실패 | 조사 후 판단 | callback URI 확인 |

---

## 8. 테스트 체크리스트

### 8.1 마이그레이션 전 테스트 (스테이징)

```
□ 메인 페이지 로드: GET /
□ 정적 파일 로드: GET /css/styles.css, /js/main.js
□ 채팅 페이지: GET /chat
□ 마이페이지: GET /mypage
□ API Health: GET /api/health
□ Google 로그인 → 콜백 → 쿠키 설정 → /api/users/me
□ Naver 로그인 → 콜백 → 쿠키 설정 → /api/users/me
□ 채팅 메시지 전송 → 응답 수신
□ 로그아웃 → 쿠키 삭제
□ Pāli 페이지: GET /pali/
□ Pāli API: GET /api/v1/pali/health
```

### 8.2 마이그레이션 후 테스트 (프로덕션)

```
□ buddhakorea.com 접속 확인
□ ai.buddhakorea.com → buddhakorea.com 리다이렉트 확인
□ 모든 정적 파일 CDN 캐시 확인 (CF-Cache-Status: HIT)
□ API 응답 캐시 안됨 확인 (CF-Cache-Status: DYNAMIC)
□ 전체 로그인 플로우 테스트
□ 쿠키 확인:
  - Domain: buddhakorea.com (또는 비어있음)
  - SameSite: Lax
  - Secure: true
□ 모바일 브라우저 테스트
□ 시크릿 모드 테스트
```

### 8.3 쿠키 검증 방법

**브라우저 DevTools:**
```
1. Application → Cookies → buddhakorea.com
2. 확인 항목:
   - access_token 존재
   - refresh_token 존재
   - session 존재
   - Domain, Path, SameSite, Secure 값

3. Network → /api/users/me 요청
   - Request Headers에 Cookie 포함 확인
   - Response가 200 OK인지 확인
```

**curl로 테스트:**
```bash
# 로그인 후 쿠키 저장
curl -c cookies.txt -L "https://buddhakorea.com/auth/login/google"

# 쿠키로 API 호출
curl -b cookies.txt "https://buddhakorea.com/api/users/me"
```

---

## 9. 참고 사항

### 9.1 Cloudflare 무료 플랜 제한

- Page Rules: 3개
- Cache Rules: 10개
- Redirect Rules: 10개
- 충분함

### 9.2 예상 소요 시간

| 단계 | 시간 |
|------|------|
| Cloudflare 설정 | 1-2시간 |
| 코드 변경 | 2-3시간 |
| DNS 전파 | 5분-24시간 (TTL 의존) |
| 테스트 | 2-3시간 |
| **총계** | **1일** (DNS 전파 제외) |

### 9.3 관련 문서

- [Cloudflare Origin Server 설정](https://developers.cloudflare.com/fundamentals/concepts/how-cloudflare-works/)
- [Cloudflare Cache Rules](https://developers.cloudflare.com/cache/how-to/cache-rules/)
- [Cloudflare Redirect Rules](https://developers.cloudflare.com/rules/url-forwarding/)

---

*End of Migration Plan*

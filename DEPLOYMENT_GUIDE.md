# Buddha Korea - Production Deployment Guide

완벽한 배포 프로세스를 보장하기 위한 종합 가이드입니다.

## 🚀 시작하기

이 문서는 2026년 4월 4일 실제 배포 경험을 토대로 작성되었습니다. 캐싱 문제, Docker volume mount, Cloudflare CDN 상호작용 등 실무에서 만난 모든 문제와 해결책을 담고 있습니다.

## 프로덕션 환경 정보

- **서버**: Hetzner Cloud (독일)
- **IP**: 157.180.72.0
- **SSH Alias**: `Host prod` (in ~/.ssh/config)
- **애플리케이션 경로**: `/opt/buddha-korea`
- **도메인**: buddhakorea.com (Cloudflare CDN을 통한 외부 유저 접근)
- **SSL/TLS**: Let's Encrypt (자동 갱신, `/opt/buddha-korea/config/ssl/` 저장)
- **Docker Compose**: `/opt/buddha-korea/config/docker-compose.yml`
- **Nginx 설정**: `/opt/buddha-korea/config/nginx.conf`
- **프론트엔드 파일**: `/opt/buddha-korea/frontend/` (docker-compose에서 `../frontend`로 마운트)

## ⚠️ 배포 전 필독: 캐싱 인프라의 이해

배포하기 전에 **세 단계의 캐싱 레이어**를 이해해야 합니다:

### 1️⃣ Nginx 캐싱 (Origin Server)
- **위치**: `/opt/buddha-korea/frontend/` 파일을 서빙하는 Nginx
- **설정**: `/opt/buddha-korea/config/nginx.conf`
- **문제**: Docker 컨테이너가 처음 시작할 때만 volume을 마운트
- **해결책**: 파일 변경 후 `docker compose restart nginx` 실행 (단순 reload가 아님)

```nginx
# chat.html: 캐시 비활성화 (매번 새로 받음)
location = /chat.html {
    expires -1;
    add_header Cache-Control "no-store, no-cache, must-revalidate, max-age=0";
}

# CSS/JS: 1년 캐시
location /css/ {
    expires 1y;
    add_header Cache-Control "public, immutable";
}

# library.css 특수 처리: 1시간 캐시 (변경 빈번)
location = /css/library.css {
    expires 1h;
    add_header Cache-Control "public, max-age=3600";
}
```

**중요**: Nginx에서 1년 캐시로 설정한 파일을 변경하면, Cloudflare가 캐시한 이전 버전을 계속 보여줍니다.

### 2️⃣ Cloudflare CDN 캐싱 (Global Edge)
- **위치**: 전 세계 Cloudflare 에지 서버
- **문제**: Nginx의 `Last-Modified` 헤더를 보고 자신의 캐시 유효성 판단
- **현상**: `curl https://buddhakorea.com/css/library.css` 헤더에 12월 날짜가 뜨지만, 실제 프로덕션 서버는 4월 파일

```
# 프로덕션 서버 파일
$ stat /opt/buddha-korea/frontend/css/library.css
Modify: 2026-04-04 12:54:09 ✅ 최신

# Cloudflare가 반환하는 헤더
Last-Modified: Tue, 16 Dec 2025 09:15:58 GMT ❌ 구버전

# Nginx 컨테이너 내부
$ docker exec buddhakorea-nginx wc -c /usr/share/nginx/html/css/library.css
155887 bytes ✅ 최신 파일 있음

# 하지만 브라우저에서 받는 것은 구버전...
```

**해결책**: **캐시-버스팅 쿼리스트링** 추가
```html
<!-- 변경 전 (Cloudflare가 캐시한 구버전 계속 제공) -->
<link rel="stylesheet" href="css/library.css">

<!-- 변경 후 (새로운 URL이므로 Cloudflare가 origin에서 새로 받음) -->
<link rel="stylesheet" href="css/library.css?v=20260404">
```

### 3️⃣ 브라우저 캐시
- **문제**: 사용자의 로컬 캐시
- **해결책**: 사용자에게 `Cmd+Shift+Delete` (캐시 삭제) 또는 시크릿 모드 사용 요청

---

## 배포 전 체크리스트

배포 전에 다음을 확인하세요:

- [ ] 모든 로컬 변경사항이 커밋됨 (`git status` 확인)
- [ ] 최신 코드가 main 브랜치에 push됨 (`git log -1` 확인)
- [ ] 프로덕션 서버에 SSH 접근 가능함 (`ssh prod "echo ok"`)
- [ ] 자주 변경되는 CSS/JS 파일은 **캐시-버스팅 쿼리스트링 추가** (아래 참고)

## 단계별 배포 프로세스

### Step 1. 캐시-버스팅 쿼리스트링 추가 (변경 파일 있으면)

**변경된 CSS/JS 파일이 있으면**, HTML에서 참조할 때 버전을 추가하세요:

```bash
# 변경 전
<link rel="stylesheet" href="css/library.css">
<script src="js/chat.js"></script>

# 변경 후 (YYYYMMDD 형식 권장)
<link rel="stylesheet" href="css/library.css?v=20260404">
<script src="js/chat.js?v=20260404"></script>
```

**왜?**: Cloudflare가 새로운 URL을 보면, 캐시되지 않은 새 리소스로 인식해서 origin에서 새로 fetch합니다.

### Step 2. 로컬 코드 커밋 및 Push

```bash
# 변경사항 확인
git status

# 필요한 파일만 추가 (분리된 커밋 권장)
git add frontend/chat.html
git commit -m "feat: add action buttons to chat messages"

git add config/nginx.conf
git commit -m "fix: set shorter cache for library.css"

# 또는 한 번에
git add frontend/ config/
git commit -m "feat: add chat action buttons and optimize CSS caching"

# 원격 저장소에 push (필수!)
git push origin main
```

### Step 3. 프로덕션에서 코드 pull

```bash
# ✅ 반드시 /opt/buddha-korea에서 실행
ssh prod "cd /opt/buddha-korea && git pull origin main"

# 결과 확인
ssh prod "cd /opt/buddha-korea && git log --oneline -3"
```

### Step 4. Docker 컨테이너 재구축 (중요!)

**⚠️ 단순 `nginx -s reload`는 새 파일을 반영하지 않습니다.**

```bash
# 방법 1: 컨테이너 전체 재생성 (권장)
ssh prod "cd /opt/buddha-korea && \
  docker compose --env-file .env -f config/docker-compose.yml \
  down nginx && \
  docker compose --env-file .env -f config/docker-compose.yml \
  up -d nginx"

# 방법 2: 컨테이너 재시작 (빠르지만 덜 안정적)
ssh prod "cd /opt/buddha-korea && \
  docker compose --env-file .env -f config/docker-compose.yml \
  restart nginx"

# 3~5초 대기 후 헬스 확인
sleep 5 && ssh prod "curl -s https://buddhakorea.com/api/health"
```

**왜 restart가 필요한가?**
- Docker-compose는 `../frontend` 상대경로를 `/opt/buddha-korea/config` 기준으로 해석
- 컨테이너 시작 시점에 volume mount가 결정되므로, 파일 변경만으로는 새 버전이 mount되지 않음
- 컨테이너를 새로 생성(recreate)해야만 최신 파일이 mount됨

### Step 5. 배포 검증 (세 단계)

배포 후 다음 순서대로 검증하세요:

#### 5.1 Nginx 컨테이너 내부 확인 (Origin이 최신인지)

```bash
# 프로덕션 서버의 파일 수정 시간 확인
ssh prod "stat /opt/buddha-korea/frontend/chat.html | grep Modify"
# 응답: Modify: 2026-04-04 13:28:13 (최신 시간)

# Nginx 컨테이너 내부의 파일 확인
ssh prod "docker exec buddhakorea-nginx wc -c /usr/share/nginx/html/chat.html"
# 응답: 155887 (파일이 마운트되어 있음)

# 특정 콘텐츠 확인 (예: 새로운 버튼이 있나)
ssh prod "docker exec buddhakorea-nginx grep -c 'msg-action-btn' /usr/share/nginx/html/chat.html"
# 응답: 7 (원하는 변경이 반영됨)
```

#### 5.2 Nginx 헤더 확인 (HTTP 캐시 헤더)

```bash
# HTML 파일 헤더 (항상 최신을 받도록)
curl -I https://buddhakorea.com/chat.html 2>&1 | grep -E "HTTP|Cache-Control|Last-Modified"
# HTTP/2 200
# Cache-Control: no-store, no-cache, must-revalidate, max-age=0
# Last-Modified: Sat, 04 Apr 2026 13:28:13 GMT

# CSS 파일 헤더 (캐시 버스팅 쿼리스트링 필요)
curl -I 'https://buddhakorea.com/css/library.css?v=20260404' 2>&1 | grep -E "HTTP|Cache-Control"
# HTTP/2 200
# Cache-Control: public, max-age=3600  (1시간 캐시)

# ❌ 쿼리스트링 없으면 Cloudflare의 구버전 캐시 계속 받음
curl -I 'https://buddhakorea.com/css/library.css' 2>&1 | grep "Last-Modified"
# Last-Modified: Tue, 16 Dec 2025 09:15:58 GMT (구버전!)
```

#### 5.3 실제 콘텐츠 확인 (파일 내용)

```bash
# chat.html이 최신 내용을 가지는지 확인
curl -s https://buddhakorea.com/chat.html | grep -c 'msg-action-btn'
# 응답: 7 (변경이 반영됨)

# 캐시 버스팅 쿼리스트링이 HTML에 있는지 확인
curl -s https://buddhakorea.com/chat.html | grep 'library.css?v='
# 응답: <link rel="stylesheet" href="css/library.css?v=20260404">

# CSS 내용 확인 (변경된 스타일이 있는지)
curl -s 'https://buddhakorea.com/css/library.css?v=20260404' | grep 'overflow-y.*auto' | wc -l
# 응답: 3 (스크롤 설정이 있음)
```

#### 5.4 SSL/TLS 확인

```bash
# SSL 인증서 상태
openssl s_client -connect buddhakorea.com:443 -servername buddhakorea.com </dev/null 2>/dev/null | \
  openssl x509 -noout -dates

# 응답 예:
# notBefore=Dec 16 00:00:00 2025 GMT
# notAfter=Dec 31 23:59:59 2026 GMT (몇 개월 남아있어야 함)
```

#### 5.5 API 헬스 확인

```bash
# 백엔드 서비스 정상 작동
curl https://buddhakorea.com/api/health

# 응답:
# {"status":"healthy","version":"0.1.0","chroma_connected":true,"llm_configured":true}
```

#### 5.6 최종 브라우저 테스트

```bash
# ✨ 모든 검증이 통과했으면 다음을 브라우저에서 확인:

1. 시크릿 모드에서 https://buddhakorea.com/chat
   - 페이지 로드됨?
   - 채팅 메시지에 저장/복사/추가질문 버튼 보임? (msg-action-btn)
   - 라이브러리 페이지에 스크롤 가능?

2. 개발자 도구 (Network 탭)
   - css/library.css?v=20260404 요청 (캐시 버스팅 적용됨)
   - chat.html은 max-age=0 (캐시 안 함)
   - CSS/JS는 max-age=31536000 (1년 캐시)

3. 개발자 도구 (Console 탭)
   - 에러 없음?
   - 401 인증 에러 없음?
```

## Cloudflare 캐시 비우기

외부 사용자가 여전히 구버전을 보는 경우 Cloudflare 캐시를 비워야 합니다:

1. Cloudflare 대시보드 접속 (https://dash.cloudflare.com)
2. Buddha Korea 도메인 선택
3. "Caching" → "Purge Everything" 클릭
4. 또는 API 사용:

```bash
# Cloudflare API로 캐시 비우기 (API 토큰 필요)
curl -X POST "https://api.cloudflare.com/client/v4/zones/{ZONE_ID}/purge_cache" \
  -H "Authorization: Bearer YOUR_CLOUDFLARE_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"purge_everything":true}'
```

## 모니터링

배포 후 다음을 모니터링하세요:

### nginx 로그 확인
```bash
ssh prod "docker logs --tail=50 -f buddhakorea-nginx"

# 또는 로그 파일에서 에러 확인
ssh prod "docker exec buddhakorea-nginx tail -100 /var/log/nginx/error.log"
```

### 백엔드 로그 확인
```bash
ssh prod "docker logs --tail=50 -f buddhakorea-backend"
```

### 메모리/디스크 확인
```bash
ssh prod "df -h"
ssh prod "free -h"
ssh prod "docker stats"
```

## 🔧 일반적인 문제 해결

### 문제 1: 새 파일이 라이브에 반영되지 않음

**증상**: 
- 프로덕션 서버 파일은 최신인데 사용자가 구버전을 봄
- `curl https://buddhakorea.com/chat.html | grep 'msg-action-btn'` → 7개 있음
- 하지만 사용자는 버튼이 안 보임

**근본 원인**:
1. **Docker volume mount 문제**: 컨테이너를 시작할 때만 volume을 마운트하므로, 단순 reload로는 새 파일이 반영되지 않음
2. **Cloudflare CDN 캐싱**: Origin의 Last-Modified가 오래되면 Cloudflare가 자신의 캐시 유효성을 믿고 계속 제공
3. **Nginx 캐시**: 만료되지 않은 캐시 헤더 때문에

**진단**:
```bash
# 1단계: 프로덕션 파일이 최신인지 확인
ssh prod "stat /opt/buddha-korea/frontend/chat.html | grep Modify"
# 응답이 오늘 시간이어야 함

# 2단계: Nginx 컨테이너가 이 파일을 가지고 있나?
ssh prod "docker exec buddhakorea-nginx grep -c 'msg-action-btn' /usr/share/nginx/html/chat.html"
# 응답: 0이면 volume mount 실패, 7이면 OK

# 3단계: Cloudflare 캐시 문제인가? (쿼리스트링으로 테스트)
curl -s 'https://buddhakorea.com/chat.html?v=20260404' | grep -c 'msg-action-btn'
# 7이 나오면 Cloudflare 캐시 문제
```

**해결책** (우선순위대로):
```bash
# 1️⃣ Docker 컨테이너 재생성 (가장 확실함)
ssh prod "cd /opt/buddha-korea && \
  docker compose --env-file .env -f config/docker-compose.yml down nginx && \
  docker compose --env-file .env -f config/docker-compose.yml up -d nginx && \
  sleep 5"

# 2️⃣ 검증 (Nginx 컨테이너가 새 파일을 가지는지)
ssh prod "docker exec buddhakorea-nginx grep -c 'msg-action-btn' /usr/share/nginx/html/chat.html"

# 3️⃣ 캐시-버스팅 쿼리스트링 추가 (Cloudflare 캐시 우회)
# HTML에서: <link rel="stylesheet" href="css/library.css?v=20260404">
# 이미 적용되었으면 버전 번호만 변경

# 4️⃣ Cloudflare 캐시 강제 비우기 (대시보드 또는 API)
curl -X POST "https://api.cloudflare.com/client/v4/zones/{ZONE_ID}/purge_cache" \
  -H "Authorization: Bearer YOUR_CLOUDFLARE_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"purge_everything":true}'
```

### 문제 2: 521 에러 (Cloudflare에서 Origin 도달 불가)

**증상**: `curl https://buddhakorea.com` → `error code: 521`

**근본 원인**:
- Nginx 컨테이너가 실행 중이지 않음
- Nginx가 443 포트를 listening하지 않음 (HTTPS 설정 오류)
- SSL 인증서 파일이 없음

**진단**:
```bash
# 1단계: 컨테이너 상태 확인
ssh prod "docker ps -a | grep nginx"
# Status가 "Up"이어야 함, "Created"면 시작 안 됨

# 2단계: Nginx가 포트를 바인드했나?
ssh prod "docker port buddhakorea-nginx"
# 443/tcp → 0.0.0.0:443 이어야 함

# 3단계: Nginx 로그 확인
ssh prod "docker logs buddhakorea-nginx | tail -30"
# SSL 인증서 오류나 config 오류가 있나?
```

**해결책**:
```bash
# 1️⃣ 컨테이너 시작
ssh prod "cd /opt/buddha-korea && \
  docker compose --env-file .env -f config/docker-compose.yml up -d nginx"

# 2️⃣ 5초 대기 (health check 준비)
sleep 5

# 3️⃣ HTTPS 연결 확인
curl -I https://buddhakorea.com 2>&1 | head -5
# HTTP/2 200 이어야 함

# 만약 여전히 521이면:
# nginx.conf의 SSL 설정 확인 (ssl_certificate 경로가 올바른가?)
# 인증서 파일이 존재하는가?
ssh prod "ls -la /opt/buddha-korea/config/ssl/"
```

### 문제 3: Nginx 설정 오류

**증상**: 
- Nginx 로그에 "emerg: cannot load certificate"
- "listen ... http2 is deprecated" 경고

**근본 원인**:
- `/etc/nginx/ssl/chain.pem` 같은 존재하지 않는 파일 참조
- Nginx 버전에서 deprecated된 문법 사용

**진단**:
```bash
ssh prod "docker logs buddhakorea-nginx 2>&1 | grep -i 'emerg\|error'"
```

**해결책**:
```bash
# config/nginx.conf 편집
# ❌ 제거: ssl_stapling, ssl_trusted_certificate, resolver
# ✅ 유지: ssl_certificate, ssl_certificate_key만

# 변경 후:
git add config/nginx.conf
git commit -m "fix: remove missing SSL stapling references"
git push origin main
ssh prod "cd /opt/buddha-korea && git pull origin main && \
  docker compose --env-file .env -f config/docker-compose.yml restart nginx"
```

### 문제 4: localhost에서는 최신인데 외부에서는 구버전

**증상**:
```bash
# 로컬 테스트
ssh prod "curl -s http://localhost/chat.html | grep -c 'msg-action-btn'"
# 응답: 7 ✅

# 외부에서 테스트
curl -s https://buddhakorea.com/chat.html | grep -c 'msg-action-btn'
# 응답: 0 ❌ (또는 구버전 번호)
```

**근본 원인**: **Cloudflare CDN 캐싱**

**해결책**:
```bash
# 1️⃣ 캐시-버스팅 쿼리스트링 추가 (권장)
# HTML에서: <link rel="stylesheet" href="css/library.css?v=20260404">

# 2️⃣ Nginx 캐시 헤더 단축
# config/nginx.conf의 CSS 캐시를 1년에서 1시간으로 변경
# location = /css/library.css {
#     expires 1h;
#     add_header Cache-Control "public, max-age=3600";
# }

# 3️⃣ Cloudflare 대시보드에서 "Purge Everything" 클릭
# 또는 API 사용 (위의 "Cloudflare 캐시 비우기" 참고)
```

### 문제 5: API 401 인증 에러

**증상**: 콘솔에 `POST /auth/refresh 401` 에러

**근본 원인**: 
- 세션 쿠키가 설정되지 않음
- 백엔드 CORS 설정 문제
- OAuth 콜백 실패

**진단**:
```bash
# 백엔드 로그 확인
ssh prod "docker logs buddhakorea-backend 2>&1 | grep -i 'auth\|oauth\|cors' | tail -20"

# 응답 헤더 확인 (브라우저 개발자 도구)
# Set-Cookie 헤더가 있는가?
# Access-Control-Allow-Credentials: true?
```

**해결책**:
```bash
# 백엔드 설정 확인
# backend/.env에 CORS_ORIGINS와 SESSION_DOMAIN 설정
# OAuth 콜백 URL이 올바른가? (예: https://buddhakorea.com/auth/google/callback)

# 로그인 플로우 다시 시도
# 1. Google/Naver/Kakao 로그인 클릭
# 2. 로그인 완료 후 리다이렉트
# 3. 개발자 도구에서 응답 헤더 확인
```

## Rollback (이전 버전으로 되돌리기)

문제가 발생한 경우 이전 버전으로 복원:

```bash
# 1. 이전 커밋으로 reset
ssh prod "cd /opt/buddha-korea && git reset --hard HEAD~1"

# 2. nginx 재로드
ssh prod "docker exec buddhakorea-nginx nginx -s reload"

# 또는 컨테이너 재시작
ssh prod "cd /opt/buddha-korea && docker compose restart buddhakorea-nginx"

# 3. 복구 확인
ssh prod "curl https://buddhakorea.com/chat.html | grep -c 'msg-action-btn'"
```

## SSL 인증서 갱신

Let's Encrypt는 자동으로 갱신되므로 수동 개입이 필요하지 않습니다. 수동으로 확인하려면:

```bash
ssh prod "docker logs buddhakorea-nginx | grep -i certbot"

# 또는 직접 갱신
ssh prod "docker run --rm -v /opt/buddha-korea/ssl:/etc/letsencrypt certbot/certbot renew"
```

## 성능 최적화

### 캐시 헤더 검증

프로덕션 환경에서 캐시 전략:

- **chat.html**: no-cache (매번 새로 받음)
- **CSS/JS**: 1년 캐시 (변경 시 파일명 변경 권장)
- **이미지/에셋**: 1년 캐시

이를 통해 크기 큰 파일은 캐시되고, 자주 변경되는 HTML은 항상 최신을 받습니다.

### CDN 성능

Cloudflare를 통한 CDN 캐싱:
- 정적 파일(CSS, JS, 이미지)은 자동으로 전역 에지에서 캐시됨
- HTML 파일은 캐시하지 않음 (origin에서 항상 최신을 받음)
- 적절한 Cache-Control 헤더로 동작 제어됨

## 비상 연락처 정보

- **서버 제공자**: Hetzner Cloud
- **도메인**: Godaddy (buddhakorea.com)
- **CDN**: Cloudflare
- **SSL**: Let's Encrypt (자동 갱신)

프로덕션 이슈 발생 시 각 서비스 제공자의 상태 페이지 확인:
- Hetzner: https://status.hetzner.cloud
- Cloudflare: https://www.cloudflarestatus.com

---

## 최종 체크리스트

배포 후 완벽히 작동하는지 확인:

- [ ] HTTPS 연결 정상 (https://buddhakorea.com)
- [ ] 채팅 페이지 로드 정상 (/chat)
- [ ] 라이브러리 페이지 스크롤 정상 (/library)
- [ ] 방법론 페이지 스크롤 정상 (/methodology)
- [ ] 라이브러리 검색창에 돋보기 아이콘 없음
- [ ] 필터 버튼이 모바일에서 접혔다가 펼쳐짐
- [ ] API 헬스체크 정상 (/api/health)
- [ ] 로그인 가능 (OAuth)
- [ ] 채팅 메시지 저장 가능
- [ ] 성능: 페이지 로드 <2초, API 응답 <500ms

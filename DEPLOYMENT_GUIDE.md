# Buddha Korea - Production Deployment Guide

완벽한 배포 프로세스를 보장하기 위한 문서입니다.

## 프로덕션 환경 정보

- **서버**: Hetzner (독일)
- **IP**: 157.180.72.0
- **SSH 설정**: ~/.ssh/config에 `Host prod` alias로 등록됨
- **앱 경로**: `/opt/buddha-korea`
- **도메인**: buddhakorea.com (Cloudflare CDN 사용)
- **HTTPS**: Let's Encrypt SSL (자동 갱신)

## 배포 전 체크리스트

배포 전에 다음을 확인하세요:

- [ ] 모든 로컬 변경사항이 커밋됨 (`git status` 확인)
- [ ] 최신 코드가 main 브랜치에 push됨 (`git log -1` 확인)
- [ ] 프로덕션 서버에 SSH 접근 가능함 (`ssh prod "echo ok"`)

## 단계별 배포 프로세스

### 1. 로컬 코드 커밋 및 Push

```bash
# 변경사항 확인
git status

# 필요한 파일만 추가
git add frontend/chat.html config/nginx.conf

# 명확한 커밋 메시지로 커밋
git commit -m "fix: enable HTTPS and disable chat.html cache for production"

# 원격 저장소에 push
git push origin main
```

### 2. 프로덕션 배포 실행

```bash
# 프로덕션 서버에 접속하고 최신 코드 pull
ssh prod "cd /opt/buddha-korea && git pull origin main"

# nginx 설정을 다시 로드 (서비스 재시작 없음)
ssh prod "docker exec buddhakorea-nginx nginx -s reload"

# 배포 완료 확인
ssh prod "curl -s https://buddhakorea.com/api/health | head -20"
```

### 3. 배포 검증

배포 후 반드시 다음을 확인하세요:

#### a) HTTPS 작동 확인
```bash
# 캐시를 무시하고 최신 파일 받기
curl -i -H "Cache-Control: no-cache" https://buddhakorea.com/chat.html | head -20

# 응답 코드: 200, Content-Type: text/html
# Cache-Control: no-store, no-cache (chat.html은 캐시 비활성화)
```

#### b) 캐시 헤더 확인
```bash
# CSS/JS는 1년 캐시, chat.html은 캐시 비활성화
curl -I https://buddhakorea.com/css/library.css | grep Cache-Control
# 예상: Cache-Control: public, immutable, max-age=31536000

curl -I https://buddhakorea.com/chat.html | grep Cache-Control
# 예상: Cache-Control: no-store, no-cache, must-revalidate, max-age=0
```

#### c) SSL 인증서 확인
```bash
# SSL 상태 확인
openssl s_client -connect buddhakorea.com:443 -servername buddhakorea.com </dev/null 2>/dev/null | openssl x509 -noout -dates

# 만료일 확인 (몇 개월 남아있어야 함)
```

#### d) API 동작 확인
```bash
# 헬스체크
curl https://buddhakorea.com/api/health

# 응답: {"status":"ok"} 또는 유사한 응답
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

## 일반적인 문제 해결

### 문제 1: HTTPS 연결 거부

**증상**: `curl https://buddhakorea.com` → 521 에러 또는 연결 실패

**원인**: nginx가 443 포트를 수신하지 않음

**해결**:
```bash
ssh prod "docker port buddhakorea-nginx"
# 443/tcp 포트가 보이지 않으면:
ssh prod "cd /opt/buddha-korea && docker compose restart buddhakorea-nginx"
```

### 문제 2: 여전히 구버전 보임

**증상**: 페이지를 새로고침해도 변경사항이 안 보임

**원인**: 브라우저 캐시 또는 Cloudflare 캐시

**해결**:
1. 브라우저: Cmd+Shift+Delete (캐시 삭제) 또는 시크릿 모드
2. Cloudflare: 위의 "Cloudflare 캐시 비우기" 섹션 참고
3. 특정 파일만 재배포:
   ```bash
   ssh prod "curl -s https://localhost/chat.html | wc -l"
   # 프로덕션 서버의 localhost에서는 정상인지 확인
   ```

### 문제 3: API 401 에러

**증상**: 콘솔에 `POST /auth/refresh 401` 에러

**원인**: 세션 쿠키 문제 또는 백엔드 인증 설정 문제

**해결**:
```bash
# 백엔드 로그 확인
ssh prod "docker logs buddhakorea-backend | grep -i auth | tail -20"

# 쿠키가 올바르게 설정되는지 확인 (브라우저 개발자 도구)
# 응답 헤더에 Set-Cookie가 있는지 확인
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

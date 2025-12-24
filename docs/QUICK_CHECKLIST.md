# Buddha Korea 배포 Quick 체크리스트

> 배포 전/후 빠른 확인용

---

## 배포 전

```
□ 로컬 서버 실행 테스트 완료
□ 주요 기능 테스트 (채팅, 로그인)
□ git status로 불필요한 파일 확인
□ .env 파일 커밋되지 않는지 확인
```

---

## 배포 후 (필수)

```bash
# 1. Health Check
curl https://ai.buddhakorea.com/api/health
# 예상: {"status":"healthy","version":"0.1.0","chroma_connected":true,"llm_configured":true}

# 2. 페이지 로드
curl -s -o /dev/null -w "%{http_code}" https://ai.buddhakorea.com/chat.html
# 예상: 200

# 3. CSS/JS 로드
curl -s -o /dev/null -w "%{http_code}" https://ai.buddhakorea.com/css/styles.css
curl -s -o /dev/null -w "%{http_code}" https://ai.buddhakorea.com/js/main.js
# 예상: 200

# 4. 컨테이너 상태 (SSH 접속 후)
ssh root@157.180.72.0 "docker compose -f /opt/buddha-korea/config/docker-compose.yml ps"
# 예상: 4개 모두 healthy
```

---

## 브라우저 테스트 (시크릿 모드)

```
□ https://ai.buddhakorea.com 접속
□ 페이지 정상 렌더링 (CSS 적용됨)
□ "로그인" 버튼 클릭 → Google 로그인
□ 로그인 후 닉네임 표시됨
□ 쿠키 확인 (DevTools → Application → Cookies)
  - session 쿠키 존재
  - Domain: .buddhakorea.com
  - SameSite: None
□ 채팅 메시지 전송 → 응답 받음
□ 로그아웃 작동
```

---

## 문제 발생 시

### 500 에러
```bash
ssh root@157.180.72.0 "docker logs buddhakorea-backend --tail 50"
```

### 404 에러 (CSS/JS/HTML)
```bash
# nginx 설정 확인
ssh root@157.180.72.0 "docker exec buddhakorea-nginx cat /etc/nginx/nginx.conf | grep -A 3 'location /css'"
```

### OAuth 에러
```bash
# 백엔드 auth 로그
ssh root@157.180.72.0 "docker logs buddhakorea-backend 2>&1 | grep -i auth"
```

### 컨테이너 재시작 (코드 변경 반영)
```bash
# 반드시 --build 플래그 사용! (--force-recreate는 이미지 재빌드 안함)
ssh root@157.180.72.0 "cd /opt/buddha-korea && docker compose -f config/docker-compose.yml down && docker compose -f config/docker-compose.yml up -d --build"
```

---

## 자주 쓰는 SSH 명령어

```bash
# 접속
ssh root@157.180.72.0

# 로그 실시간 보기
docker logs buddhakorea-backend -f

# 컨테이너 내부 접속
docker exec -it buddhakorea-backend bash

# 전체 재시작 (코드 변경 시 --build 필수!)
cd /opt/buddha-korea && docker compose -f config/docker-compose.yml up -d --build

# 디스크 확인
df -h /

# 이미지 정리 (주의: -a 옵션은 롤백 이미지도 삭제함)
docker image prune  # dangling만 삭제 (안전)
```

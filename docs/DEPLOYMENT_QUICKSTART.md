# Buddha Korea - 배포 빠른 참조

**최종 업데이트:** 2026-04-02

---

## GitHub Secrets 목록 (16개)

GitHub Repository → Settings → Secrets and variables → Actions

| Secret | 설명 |
|--------|------|
| `HETZNER_HOST` | `157.180.72.0` |
| `HETZNER_USERNAME` | SSH 사용자명 |
| `HETZNER_SSH_KEY` | SSH 개인 키 |
| `SECRET_KEY` | FastAPI 세션 키 |
| `REDIS_PASSWORD` | Redis 비밀번호 |
| `POSTGRES_PASSWORD` | PostgreSQL 비밀번호 |
| `GEMINI_API_KEY` | Gemini API 키 |
| `PALI_GEMINI_API_KEY` | Pali Studio Gemini 키 |
| `GCP_PROJECT_ID` | GCP 프로젝트 ID |
| `GCP_SERVICE_ACCOUNT_KEY` | GCP 서비스 계정 JSON |
| `GOOGLE_CLIENT_ID` | Google OAuth ID |
| `GOOGLE_CLIENT_SECRET` | Google OAuth Secret |
| `NAVER_CLIENT_ID` | Naver OAuth ID |
| `NAVER_CLIENT_SECRET` | Naver OAuth Secret |
| `KAKAO_CLIENT_ID` | Kakao REST API 키 |
| `KAKAO_CLIENT_SECRET` | Kakao OAuth Secret |

---

## 자동 배포

`main` 브랜치 push 시 아래 경로 변경이 감지되면 자동 배포:

```
backend/** | config/** | Dockerfile | .github/workflows/deploy-hetzner.yml
```

**워크플로우:** `.github/workflows/deploy-hetzner.yml`

**수동 트리거:** Actions 탭 → Deploy to Hetzner → Run workflow

---

## 긴급 수동 배포 (SSH)

```bash
ssh root@157.180.72.0
cd /opt/buddha-korea
git pull origin main

# 코드만 변경된 경우 (빠름)
docker compose -f config/docker-compose.yml up -d --force-recreate

# Dockerfile/requirements 변경 시 (느림)
docker compose -f config/docker-compose.yml up -d --build
```

---

## 배포 후 검증

```bash
# 컨테이너 4개 모두 Up 확인
docker compose -f config/docker-compose.yml ps

# Health check
curl https://buddhakorea.com/api/health
# 예상: {"status": "healthy"}

# 백엔드 에러 확인
docker logs buddhakorea-backend --tail 50 2>&1 | grep -i error
```

브라우저: https://buddhakorea.com/chat.html → 콘솔에서 404 없는지 확인

---

## 트러블슈팅 빠른 진단

| 증상 | 원인 | 해결 |
|------|------|------|
| 백엔드 컨테이너 unhealthy | 시작 시 초기화 실패 | `docker logs buddhakorea-backend` 확인 |
| GCP 인증 에러 | gcp-key.json 손상 | GCP Secret 재등록 (base64 방식 권장) |
| API 404 에러 | 백엔드 미실행 | 컨테이너 상태 확인 후 재시작 |
| OAuth 로그인 실패 | 리다이렉트 URI 불일치 | OAuth 콘솔에서 `buddhakorea.com` URI 확인 |
| nginx 502 에러 | 백엔드 연결 불가 | 백엔드 로그 확인 |

---

## GCP 키 등록 권장 방식

```bash
# 로컬에서 base64 인코딩 후 Secret에 등록
base64 -i config/gcp-key.json | pbcopy  # macOS
# 출력값을 GCP_SERVICE_ACCOUNT_KEY Secret에 붙여넣기
```

이렇게 하면 줄바꿈 문자 문제가 없어 별도 sanitize 스크립트 불필요.

---

## 주요 링크

| 항목 | URL |
|------|-----|
| 사이트 | https://buddhakorea.com |
| Health Check | https://buddhakorea.com/api/health |
| API 문서 | https://buddhakorea.com/docs |
| GitHub | https://github.com/ltk1186/buddhakorea |
| 서버 IP | 157.180.72.0 |
| 서버 경로 | `/opt/buddha-korea` |

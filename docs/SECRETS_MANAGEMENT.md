# Secrets Management Guide

> 최종 업데이트: 2026-04-02

GitHub Actions Secrets → Hetzner 서버로 시크릿이 흐르는 방식을 설명합니다.

---

## 시크릿 흐름

```
GitHub Secrets
      │
      ▼ (deploy-hetzner.yml 실행 시)
SSH → Hetzner VM
      │
      ├─ .env 파일 생성 (Docker Compose용)
      ├─ config/gcp-key.json 생성 (GCP 인증용)
      └─ docker compose up (컨테이너에 환경변수 주입)
```

---

## GitHub Secrets 목록

| Secret 이름 | 용도 |
|-------------|------|
| `HETZNER_HOST` | 서버 IP (157.180.72.0) |
| `HETZNER_USERNAME` | SSH 사용자명 |
| `HETZNER_SSH_KEY` | SSH 개인 키 |
| `SECRET_KEY` | FastAPI 세션 암호화 키 |
| `REDIS_PASSWORD` | Redis 인증 |
| `POSTGRES_PASSWORD` | PostgreSQL 비밀번호 |
| `GEMINI_API_KEY` | Gemini API (기본) |
| `PALI_GEMINI_API_KEY` | Gemini API (Pali Studio) |
| `GCP_PROJECT_ID` | GCP 프로젝트 ID |
| `GCP_SERVICE_ACCOUNT_KEY` | GCP 서비스 계정 키 |
| `GOOGLE_CLIENT_ID` | Google OAuth |
| `GOOGLE_CLIENT_SECRET` | Google OAuth |
| `NAVER_CLIENT_ID` | Naver OAuth |
| `NAVER_CLIENT_SECRET` | Naver OAuth |
| `KAKAO_CLIENT_ID` | Kakao OAuth |
| `KAKAO_CLIENT_SECRET` | Kakao OAuth |
| `ADMIN_EMAIL` | Admin password login email (optional) |
| `ADMIN_PASSWORD` | Admin password login (optional) |
| `ADMIN_PASSWORD_HASH` | Admin password SHA-256 (optional) |

---

## 시크릿 적용 방식

### 1. .env 파일 자동 생성

배포 시 워크플로우가 서버의 `/opt/buddha-korea/.env`를 자동 생성합니다. 수동 편집 금지 — 다음 배포 시 덮어씌워집니다.

### 2. GCP 서비스 계정 키

#### 권장 방식 (base64 인코딩)

JSON 파일을 그대로 Secret에 저장하면 줄바꿈 문자가 깨질 수 있습니다. **base64로 인코딩해서 저장**하세요:

```bash
# 로컬에서 실행
base64 -i config/gcp-key.json | pbcopy  # macOS
base64 -w 0 config/gcp-key.json | xclip  # Linux

# 출력값을 GCP_SERVICE_ACCOUNT_KEY Secret에 저장
```

배포 시 자동 디코딩:
```bash
echo "$GCP_SERVICE_ACCOUNT_KEY" | base64 -d > config/gcp-key.json
```

#### 현재 방식 (raw JSON + sanitize)

현재 워크플로우는 raw JSON을 저장하고 Python 스크립트로 제어 문자를 정리하는 방식을 사용합니다. 키 교체 시 base64 방식으로 전환을 권장합니다.

### 3. PostgreSQL 비밀번호 동기화

배포 시 실행 중인 PostgreSQL 컨테이너의 비밀번호를 자동 동기화합니다:
```sql
ALTER USER postgres WITH PASSWORD '<POSTGRES_PASSWORD>';
```

---

## 시크릿 교체 방법

### 일반 시크릿 교체

1. GitHub → Repository → Settings → Secrets and variables → Actions
2. 해당 Secret 클릭 → 값 업데이트
3. `main` 브랜치에 push 또는 Actions에서 수동 트리거

### GCP 서비스 계정 키 교체

1. Google Cloud Console에서 새 키 생성 (JSON 형식)
2. 로컬에서 base64 인코딩:
   ```bash
   base64 -i new-gcp-key.json | pbcopy
   ```
3. `GCP_SERVICE_ACCOUNT_KEY` Secret 업데이트
4. 재배포
5. Google Cloud Console에서 구 키 삭제

### SSH 키 교체

1. 새 키 생성: `ssh-keygen -t ed25519 -f new_hetzner_key`
2. 공개 키를 서버에 추가: `/root/.ssh/authorized_keys`
3. `HETZNER_SSH_KEY` Secret을 새 개인 키로 업데이트
4. 배포 테스트 후 구 공개 키 서버에서 제거

---

## 보안 원칙

1. **절대 코드에 시크릿 하드코딩 금지** — 모든 민감 값은 GitHub Secrets
2. **`.env` 파일은 항상 `.gitignore`에 포함** — 자동 생성되므로 커밋 불필요
3. **GCP 서비스 계정은 최소 권한 원칙** — 필요한 API만 활성화
4. **정기적 교체 권장** — API 키, 비밀번호 분기 1회
5. **OAuth 리다이렉트 URI 관리** — 실제 사용 도메인만 등록
   - `https://buddhakorea.com/auth/callback/google`
   - `https://buddhakorea.com/auth/callback/naver`
   - `https://buddhakorea.com/auth/callback/kakao`

---

## 트러블슈팅

**배포 SSH 인증 실패:**
- `HETZNER_SSH_KEY`에 `-----BEGIN`과 `-----END` 라인 포함 확인

**GCP 인증 실패 (GoogleAuthError):**
- `docker logs buddhakorea-backend | grep -i gcp` 로 에러 확인
- `docker exec buddhakorea-backend python3 -c "import json; json.load(open('/app/gcp-key.json'))"` 으로 JSON 유효성 확인
- Secret을 base64 방식으로 교체

**OAuth 로그인 안 됨:**
- 각 OAuth 콘솔에서 `buddhakorea.com` 리다이렉트 URI 등록 확인
- `SECRET_KEY` 변경 시 기존 세션이 무효화됨 (재로그인 필요)

**DB 연결 실패:**
- `POSTGRES_PASSWORD` Secret과 실제 DB 비밀번호 일치 여부 확인
- 워크플로우 로그에서 `ALTER ROLE` 성공 메시지 확인

---

## 긴급 수동 시크릿 적용

GitHub Actions가 불가한 경우:

```bash
ssh root@157.180.72.0
nano /opt/buddha-korea/.env   # 직접 편집
docker compose -f /opt/buddha-korea/config/docker-compose.yml restart backend
```

**주의:** 수동 변경은 다음 자동 배포 시 덮어씌워집니다.

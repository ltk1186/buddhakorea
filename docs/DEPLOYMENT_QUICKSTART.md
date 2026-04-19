# Buddha Korea - Deployment Quickstart

최종 업데이트: 2026-04-19

이 문서는 가장 짧은 운영용 배포 참조다. 상세 절차는 아래 문서가 기준이다.

- [PRODUCTION_RUNBOOK.md](./PRODUCTION_RUNBOOK.md)
- [MIGRATIONS_AND_SCHEMA.md](./MIGRATIONS_AND_SCHEMA.md)
- [SECRETS_MANAGEMENT.md](./SECRETS_MANAGEMENT.md)

## 1. 자동 배포 트리거

`main` 브랜치 push 시 아래 경로 변경이 감지되면 자동 배포:

```text
backend/** | config/** | frontend/** | scripts/** | Dockerfile | Dockerfile.migrate
requirements.txt | pyproject.toml | .github/workflows/deploy-hetzner.yml
```

워크플로우:

- `.github/workflows/deploy-hetzner.yml`

수동 트리거:

- GitHub Actions -> `Deploy to Hetzner` -> `Run workflow`

## 2. 긴급 수동 배포

```bash
ssh root@157.180.72.0
cd /opt/buddha-korea
git pull origin main
docker compose -f config/docker-compose.yml up -d --build
```

`--force-recreate`는 이미지 재빌드가 필요 없다고 확신할 때만 사용한다.

## 3. 마이그레이션

배포 후 schema 변경이 포함됐다면 canonical path는 이 명령이다:

```bash
./scripts/migrate.sh <alembic args>
```

예:

```bash
./scripts/migrate.sh current
./scripts/migrate.sh upgrade head
```

주의:

- 더 이상 `cd backend && alembic upgrade head`를 기준으로 쓰지 않는다.
- production에 `alembic_version`이 없을 수 있으므로, 첫 정규화는
  [MIGRATIONS_AND_SCHEMA.md](./MIGRATIONS_AND_SCHEMA.md)를 먼저 따른다.

## 4. 배포 후 최소 검증

```bash
cd /opt/buddha-korea
docker compose -f config/docker-compose.yml ps
curl -s https://buddhakorea.com/api/health
docker logs buddhakorea-backend --tail 100 2>&1
```

추가 확인:

- `https://buddhakorea.com/admin/`
- admin login
- `/api/admin/summary`
- `/api/admin/observability`
- admin observability 테이블/카드가 정상 렌더링되고 5xx가 없는지 확인

RAG/provider/prompt/runtime 변경 후에는 production smoke를 최소 1건 실행:

```bash
ADMIN_EMAIL="..." ADMIN_PASSWORD="..." \
python3 scripts/rag_regression_check.py \
  --base-url https://buddhakorea.com \
  --login \
  --max-cases 1
```

## 5. 자주 틀리는 부분

- `.env`는 GitHub Actions가 생성한다. 서버에서 수동 편집하지 않는다.
- admin CSS/JS 변경 시 `frontend/admin/index.html`의 `?v=...`를 같이 올린다.
- Cloudflare 때문에 admin asset이 오래 보존될 수 있다.
- reliability 패널에서 `usage_log_available = false`가 보여도 latency/slow/cost/cache는 DB 기준으로 계속 보여야 한다.
- 이 값은 이제 local usage-log analytics 부재를 뜻한다.
- admin observability 성능 회귀 방지를 위해 `011_add_chat_messages_role_created_at_index`가 적용되어야 한다.

## 6. 실패 시 즉시 롤백

배포 직후 헬스체크/스모크 실패 시:

```bash
git revert <bad_commit_sha>
git push origin main
```

자동 배포 완료 후 아래 재확인:

```bash
curl -s https://buddhakorea.com/api/health
```

스키마 downgrade는 migration 자체가 원인일 때만 수행한다.

## 7. 주요 링크

| 항목 | URL |
|------|-----|
| 사이트 | https://buddhakorea.com |
| Health Check | https://buddhakorea.com/api/health |
| Admin | https://buddhakorea.com/admin/ |
| API 문서 | https://buddhakorea.com/docs |
| 서버 경로 | `/opt/buddha-korea` |

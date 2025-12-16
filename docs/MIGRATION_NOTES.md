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

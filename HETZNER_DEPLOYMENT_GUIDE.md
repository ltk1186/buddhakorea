# Hetzner VM 배포 가이드

> **서버**: prod-main-01 (CX33)
> **사양**: 4 vCPU | 8GB RAM | 80GB SSD
> **비용**: €4.99/월 (~$5.50)
> **IP**: 157.180.72.0
> **접속**: `ssh prod`
> **마지막 업데이트**: 2025-12-09

---

## 목차

1. [아키텍처 개요](#1-아키텍처-개요)
2. [사전 요구사항](#2-사전-요구사항)
3. [Fix 1: docker-compose.yml 통일](#3-fix-1-docker-composeyml-통일)
4. [Fix 2: Redis 세션 통합](#4-fix-2-redis-세션-통합)
5. [배포 전 체크리스트](#5-배포-전-체크리스트)
6. [배포 절차](#6-배포-절차)
7. [배포 후 검증](#7-배포-후-검증)
8. [롤백 절차](#8-롤백-절차)
9. [모니터링 및 유지보수](#9-모니터링-및-유지보수)

---

## 1. 아키텍처 개요

### 목표 아키텍처

```
┌─────────────────────────────────────────────────────────────────────────┐
│  Hetzner VM: prod-main-01 (CX33)                                        │
│  4 vCPU | 8GB RAM | 80GB SSD | €4.99/mo                                │
├─────────────────────────────────────────────────────────────────────────┤
│                                                                         │
│  ┌─────────────────────────────────────────────────────────────────┐   │
│  │  Docker Engine (dockerd)                                         │   │
│  │                                                                   │   │
│  │  ┌─────────────┐  ┌─────────────┐  ┌─────────────────────────┐  │   │
│  │  │   nginx     │  │    redis    │  │        backend          │  │   │
│  │  │   :80/:443  │  │    :6379    │  │        :8000            │  │   │
│  │  │             │  │             │  │                         │  │   │
│  │  │ • SSL/TLS   │  │ • Sessions  │  │ • FastAPI + Gunicorn    │  │   │
│  │  │ • HTTPS     │  │ • Cache     │  │ • ChromaDB (파일 기반)  │  │   │
│  │  │ • Rate Limit│  │ • Analytics │  │ • Vertex AI 연동        │  │   │
│  │  └──────┬──────┘  └──────┬──────┘  └───────────┬─────────────┘  │   │
│  │         │                │                     │                 │   │
│  │         └────────────────┴─────────────────────┘                 │   │
│  │                          │                                       │   │
│  │                   buddhist-ai-network                            │   │
│  └─────────────────────────────────────────────────────────────────┘   │
│                                                                         │
│  ┌─────────────────────────────────────────────────────────────────┐   │
│  │  Volumes (Persistent Data)                                       │   │
│  │  ├── ./chroma_db/        (~3GB, 벡터 DB)                        │   │
│  │  ├── ./redis-data/       (세션 + 캐시)                          │   │
│  │  ├── ./logs/             (앱 로그)                              │   │
│  │  └── ./ssl/              (Let's Encrypt 인증서)                 │   │
│  └─────────────────────────────────────────────────────────────────┘   │
│                                                                         │
│  Ubuntu 22.04 LTS                                                       │
└─────────────────────────────────────────────────────────────────────────┘
```

### 외부 의존성

```
┌─────────────────────────────────────────────────────────────────────────┐
│                        External Services                                 │
├─────────────────────────────────────────────────────────────────────────┤
│                                                                         │
│  ┌─────────────────────────┐    ┌─────────────────────────────────┐   │
│  │  Google Cloud (Vertex)  │    │  Cloudflare / DNS Provider      │   │
│  │  └── us-central1        │    │  └── ai.buddhakorea.com         │   │
│  │      ├── gemini-embed   │    │      → 157.180.72.0             │   │
│  │      └── gemini-2.5-pro │    └─────────────────────────────────┘   │
│  └─────────────────────────┘                                           │
│                                                                         │
│  ┌─────────────────────────┐    ┌─────────────────────────────────┐   │
│  │  GitHub                 │    │  Let's Encrypt                  │   │
│  │  └── Actions (CI/CD)    │    │  └── SSL 인증서 자동 갱신       │   │
│  └─────────────────────────┘    └─────────────────────────────────┘   │
│                                                                         │
└─────────────────────────────────────────────────────────────────────────┘
```

### GCP → Hetzner 비용 비교

| 항목 | GCP (현재) | Hetzner (목표) | 절감 |
|------|-----------|----------------|------|
| VM 비용 | ~$120/월 | €4.99/월 (~$5.50) | **95%** |
| Vertex AI | ~$50-200/월 | ~$50-200/월 | 동일 |
| **총합** | **~$170-320/월** | **~$55-205/월** | **~$115/월** |

---

## 2. 사전 요구사항

### 2.1 Hetzner VM 초기 설정

```bash
# SSH 접속
ssh prod

# 시스템 업데이트
sudo apt update && sudo apt upgrade -y

# 필수 패키지 설치
sudo apt install -y \
    apt-transport-https \
    ca-certificates \
    curl \
    gnupg \
    lsb-release \
    git \
    htop \
    tmux \
    jq

# Docker 설치 (공식 방법)
curl -fsSL https://get.docker.com -o get-docker.sh
sudo sh get-docker.sh

# Docker Compose V2 설치
sudo apt install docker-compose-plugin -y

# 현재 사용자를 docker 그룹에 추가 (sudo 없이 docker 사용)
sudo usermod -aG docker $USER

# 로그아웃 후 재접속 필요
exit
ssh prod

# Docker 버전 확인
docker --version
docker compose version
```

### 2.2 방화벽 설정 (ufw)

```bash
# UFW 활성화 및 기본 규칙
sudo ufw default deny incoming
sudo ufw default allow outgoing

# SSH 허용 (반드시 먼저!)
sudo ufw allow ssh

# HTTP/HTTPS 허용
sudo ufw allow 80/tcp
sudo ufw allow 443/tcp

# UFW 활성화
sudo ufw enable

# 상태 확인
sudo ufw status verbose
```

### 2.3 디렉토리 구조 생성

```bash
# 앱 디렉토리 생성
sudo mkdir -p /opt/buddha-korea
sudo chown $USER:$USER /opt/buddha-korea
cd /opt/buddha-korea

# 필요한 하위 디렉토리
mkdir -p chroma_db logs redis-data ssl source_explorer css js
```

### 2.4 GCP 인증 설정 (Vertex AI용)

```bash
# 서비스 계정 키 파일 업로드 (로컬에서)
scp /path/to/service-account-key.json prod:/opt/buddha-korea/gcp-key.json

# VM에서 환경변수 설정
echo 'export GOOGLE_APPLICATION_CREDENTIALS="/opt/buddha-korea/gcp-key.json"' >> ~/.bashrc
source ~/.bashrc
```

---

## 3. Fix 1: docker-compose.yml 통일

### 3.1 문제점

```
현재 상태 (지킬 앤 하이드)
─────────────────────────────────────────────
docker-compose.yml (Dev)        docker-compose.production.yml (Prod)
├── ChromaDB (서버 모드)        ├── Redis ✓
├── FastAPI                     ├── FastAPI (파일 기반 Chroma)
├── Nginx                       └── Nginx
└── Redis ✗ (없음)

문제:
1. Dev에서 테스트한 것이 Prod에서 다르게 동작
2. 두 파일을 동기화해야 하는 부담
3. "내 컴퓨터에서는 되는데..." 문제 발생
```

### 3.2 해결: 단일 docker-compose.yml

`/opt/buddha-korea/docker-compose.yml`:

```yaml
# ============================================================
# Buddha Korea RAG Chatbot - Unified Docker Compose
# ============================================================
# 환경: 개발 + 프로덕션 통합 (Dev/Prod Parity)
# ChromaDB: 파일 기반 (./chroma_db)
# 마지막 업데이트: 2025-12-09

version: '3.8'

services:
  # ──────────────────────────────────────────────────────────
  # Redis: 세션 저장소 + LLM 응답 캐시 + 분석 데이터
  # ──────────────────────────────────────────────────────────
  redis:
    image: redis:7-alpine
    container_name: buddhakorea-redis
    command: redis-server /usr/local/etc/redis/redis.conf
    volumes:
      - ./redis.conf:/usr/local/etc/redis/redis.conf:ro
      - ./redis-data:/data
    environment:
      - REDIS_PASSWORD=${REDIS_PASSWORD:-buddha-korea-redis-2024}
    ports:
      - "127.0.0.1:6379:6379"  # 로컬만 노출 (보안)
    restart: unless-stopped
    healthcheck:
      test: ["CMD", "redis-cli", "-a", "${REDIS_PASSWORD:-buddha-korea-redis-2024}", "ping"]
      interval: 10s
      timeout: 5s
      retries: 5
      start_period: 10s
    networks:
      - buddhist-ai-network
    deploy:
      resources:
        limits:
          cpus: '0.5'
          memory: 512M
        reservations:
          cpus: '0.25'
          memory: 256M
    logging:
      driver: "json-file"
      options:
        max-size: "10m"
        max-file: "3"

  # ──────────────────────────────────────────────────────────
  # Backend: FastAPI + 파일 기반 ChromaDB
  # ──────────────────────────────────────────────────────────
  backend:
    build:
      context: .
      dockerfile: Dockerfile
    container_name: buddhakorea-backend
    depends_on:
      redis:
        condition: service_healthy
    volumes:
      - ./chroma_db:/app/chroma_db        # ChromaDB 벡터 데이터
      - ./logs:/app/logs                   # 앱 로그
      - ./source_explorer:/app/source_explorer  # 경전 요약 데이터
    environment:
      # ─── GCP Vertex AI ───
      - GCP_PROJECT_ID=${GCP_PROJECT_ID}
      - GCP_LOCATION=${GCP_LOCATION:-us-central1}
      - GOOGLE_APPLICATION_CREDENTIALS=/app/gcp-key.json

      # ─── 모델 설정 ───
      - LLM_MODEL=${LLM_MODEL:-gemini-2.5-pro}
      - LLM_MODEL_FAST=${LLM_MODEL_FAST:-gemini-2.5-flash}
      - USE_GEMINI_FOR_QUERIES=${USE_GEMINI_FOR_QUERIES:-true}

      # ─── ChromaDB (파일 기반) ───
      - CHROMA_DB_PATH=./chroma_db
      - CHROMA_COLLECTION_NAME=${CHROMA_COLLECTION_NAME:-cbeta_sutras_gemini}

      # ─── Redis ───
      - REDIS_HOST=redis
      - REDIS_PORT=6379
      - REDIS_PASSWORD=${REDIS_PASSWORD:-buddha-korea-redis-2024}
      - REDIS_DB=0

      # ─── API 설정 ───
      - API_HOST=0.0.0.0
      - API_PORT=8000
      - ALLOWED_ORIGINS=${ALLOWED_ORIGINS:-https://ai.buddhakorea.com,https://buddhakorea.com}
      - RATE_LIMIT_PER_HOUR=${RATE_LIMIT_PER_HOUR:-100}
      - LOG_LEVEL=${LOG_LEVEL:-info}

      # ─── 검색 설정 ───
      - TOP_K_RETRIEVAL=${TOP_K_RETRIEVAL:-10}
      - TOP_K_RETRIEVAL_FAST=${TOP_K_RETRIEVAL_FAST:-5}
      - USE_HYDE=${USE_HYDE:-false}
    env_file:
      - .env
    ports:
      - "127.0.0.1:8000:8000"  # 로컬만 노출 (nginx가 프록시)
    restart: unless-stopped
    healthcheck:
      test: ["CMD", "curl", "-f", "http://localhost:8000/api/health"]
      interval: 30s
      timeout: 10s
      retries: 3
      start_period: 60s
    networks:
      - buddhist-ai-network
    deploy:
      resources:
        limits:
          cpus: '3'
          memory: 6G
        reservations:
          cpus: '1'
          memory: 2G
    logging:
      driver: "json-file"
      options:
        max-size: "50m"
        max-file: "5"

  # ──────────────────────────────────────────────────────────
  # Nginx: 리버스 프록시 + SSL + Rate Limiting
  # ──────────────────────────────────────────────────────────
  nginx:
    image: nginx:alpine
    container_name: buddhakorea-nginx
    depends_on:
      backend:
        condition: service_healthy
    volumes:
      - ./nginx.conf:/etc/nginx/nginx.conf:ro
      - ./ssl:/etc/nginx/ssl:ro
      - /var/www/certbot:/var/www/certbot:ro
    ports:
      - "80:80"
      - "443:443"
    restart: unless-stopped
    healthcheck:
      test: ["CMD", "curl", "-f", "http://localhost/api/health"]
      interval: 30s
      timeout: 5s
      retries: 3
    networks:
      - buddhist-ai-network
    logging:
      driver: "json-file"
      options:
        max-size: "20m"
        max-file: "3"

# ──────────────────────────────────────────────────────────
# Networks
# ──────────────────────────────────────────────────────────
networks:
  buddhist-ai-network:
    driver: bridge
    ipam:
      config:
        - subnet: 172.28.0.0/16

# ──────────────────────────────────────────────────────────
# Named Volumes (optional, for better management)
# ──────────────────────────────────────────────────────────
# volumes:
#   chroma-data:
#   redis-data:
```

### 3.3 환경 분리: .env 파일로

```bash
# .env.example (템플릿)
# ─────────────────────────────────────────────────────────────
# GCP Vertex AI
GCP_PROJECT_ID=gen-lang-client-0324154376
GCP_LOCATION=us-central1

# 모델 설정
LLM_MODEL=gemini-2.5-pro
LLM_MODEL_FAST=gemini-2.5-flash
USE_GEMINI_FOR_QUERIES=true

# ChromaDB
CHROMA_COLLECTION_NAME=cbeta_sutras_gemini

# Redis (프로덕션에서는 강력한 비밀번호 사용!)
REDIS_PASSWORD=your-strong-password-here

# API
ALLOWED_ORIGINS=https://ai.buddhakorea.com,https://buddhakorea.com
RATE_LIMIT_PER_HOUR=100
LOG_LEVEL=info

# 검색
TOP_K_RETRIEVAL=10
TOP_K_RETRIEVAL_FAST=5
USE_HYDE=false
```

---

## 4. Fix 2: Redis 세션 통합

### 4.1 문제점

```python
# 현재 main.py (line 122-123)
# In-memory session storage (for production, consider Redis)
CONVERSATION_SESSIONS: Dict[str, Dict[str, Any]] = {}

# 문제:
# 1. 서버 재시작 시 모든 세션 손실
# 2. 사용자의 후속 질문 컨텍스트 사라짐
# 3. "앞서 말한 내용" 참조 불가능
```

### 4.2 해결: Redis 세션 매니저

`/opt/buddha-korea/redis_session.py` (새 파일):

```python
"""
Redis Session Manager for Buddha Korea
======================================
서버 재시작에도 세션이 유지되는 Redis 기반 세션 관리

사용법:
    from redis_session import RedisSessionManager
    session_mgr = RedisSessionManager()

    # 세션 생성/조회
    session_id = session_mgr.create_or_get_session()

    # 세션 업데이트
    session_mgr.update_session(session_id, user_msg, assistant_msg, context, metadata)

    # 세션 컨텍스트 조회
    context = session_mgr.get_session_context(session_id)
"""

import os
import json
import uuid
from datetime import datetime, timedelta
from typing import Dict, List, Any, Optional
from loguru import logger

try:
    import redis
    REDIS_AVAILABLE = True
except ImportError:
    REDIS_AVAILABLE = False
    logger.warning("redis-py not installed. Falling back to in-memory sessions.")


class RedisSessionManager:
    """
    Redis 기반 세션 매니저
    Redis 사용 불가 시 자동으로 in-memory 폴백
    """

    # 설정 상수
    SESSION_TTL_SECONDS = 3600  # 1시간
    MAX_MESSAGES_PER_SESSION = 20
    MAX_CONVERSATION_HISTORY_TURNS = 5
    SESSION_PREFIX = "buddha:session:"

    def __init__(
        self,
        host: str = None,
        port: int = None,
        password: str = None,
        db: int = 0
    ):
        """
        Redis 세션 매니저 초기화

        환경변수 또는 매개변수로 설정:
        - REDIS_HOST
        - REDIS_PORT
        - REDIS_PASSWORD
        - REDIS_DB
        """
        self.host = host or os.getenv("REDIS_HOST", "localhost")
        self.port = port or int(os.getenv("REDIS_PORT", "6379"))
        self.password = password or os.getenv("REDIS_PASSWORD")
        self.db = db or int(os.getenv("REDIS_DB", "0"))

        self.redis_client: Optional[redis.Redis] = None
        self._fallback_sessions: Dict[str, Dict[str, Any]] = {}

        self._connect()

    def _connect(self) -> bool:
        """Redis 연결 시도"""
        if not REDIS_AVAILABLE:
            logger.warning("Redis not available, using in-memory fallback")
            return False

        try:
            self.redis_client = redis.Redis(
                host=self.host,
                port=self.port,
                password=self.password,
                db=self.db,
                decode_responses=True,
                socket_timeout=5,
                socket_connect_timeout=5,
                retry_on_timeout=True
            )
            # 연결 테스트
            self.redis_client.ping()
            logger.info(f"✅ Redis connected: {self.host}:{self.port}")
            return True
        except Exception as e:
            logger.warning(f"Redis connection failed: {e}. Using in-memory fallback.")
            self.redis_client = None
            return False

    def _get_key(self, session_id: str) -> str:
        """Redis 키 생성"""
        return f"{self.SESSION_PREFIX}{session_id}"

    def _serialize(self, data: Dict[str, Any]) -> str:
        """세션 데이터 직렬화"""
        # datetime 객체 처리
        def convert(obj):
            if isinstance(obj, datetime):
                return obj.isoformat()
            return obj

        return json.dumps(data, default=convert, ensure_ascii=False)

    def _deserialize(self, data: str) -> Dict[str, Any]:
        """세션 데이터 역직렬화"""
        parsed = json.loads(data)

        # datetime 문자열 복원
        for key in ['created_at', 'last_accessed']:
            if key in parsed and isinstance(parsed[key], str):
                try:
                    parsed[key] = datetime.fromisoformat(parsed[key])
                except:
                    pass

        return parsed

    def create_or_get_session(self, session_id: Optional[str] = None) -> str:
        """
        세션 생성 또는 기존 세션 조회

        Args:
            session_id: 기존 세션 ID (없으면 새로 생성)

        Returns:
            세션 ID
        """
        # 기존 세션 확인
        if session_id:
            session = self._get_session(session_id)
            if session:
                # 세션 갱신
                self._touch_session(session_id)
                logger.debug(f"Reusing session {session_id[:8]}...")
                return session_id

        # 새 세션 생성
        new_id = str(uuid.uuid4())
        session_data = {
            'session_id': new_id,
            'created_at': datetime.now(),
            'last_accessed': datetime.now(),
            'messages': [],
            'context_chunks': [],
            'metadata': {}
        }

        self._set_session(new_id, session_data)
        logger.info(f"Created new session {new_id[:8]}...")
        return new_id

    def _get_session(self, session_id: str) -> Optional[Dict[str, Any]]:
        """세션 조회"""
        if self.redis_client:
            try:
                data = self.redis_client.get(self._get_key(session_id))
                if data:
                    return self._deserialize(data)
            except Exception as e:
                logger.error(f"Redis get error: {e}")

        # Fallback
        return self._fallback_sessions.get(session_id)

    def _set_session(self, session_id: str, data: Dict[str, Any]):
        """세션 저장"""
        if self.redis_client:
            try:
                self.redis_client.setex(
                    self._get_key(session_id),
                    self.SESSION_TTL_SECONDS,
                    self._serialize(data)
                )
                return
            except Exception as e:
                logger.error(f"Redis set error: {e}")

        # Fallback
        self._fallback_sessions[session_id] = data

    def _touch_session(self, session_id: str):
        """세션 TTL 갱신"""
        if self.redis_client:
            try:
                self.redis_client.expire(
                    self._get_key(session_id),
                    self.SESSION_TTL_SECONDS
                )
            except Exception as e:
                logger.error(f"Redis expire error: {e}")

    def update_session(
        self,
        session_id: str,
        user_message: str,
        assistant_message: str,
        context_chunks: List[Any],
        metadata: Dict[str, Any]
    ):
        """
        세션에 새 메시지 교환 추가

        Args:
            session_id: 세션 ID
            user_message: 사용자 질문
            assistant_message: AI 응답
            context_chunks: 검색된 컨텍스트 청크
            metadata: 추가 메타데이터
        """
        session = self._get_session(session_id)
        if not session:
            logger.warning(f"Session {session_id[:8]}... not found")
            return

        # 메시지 추가
        session['messages'].append({'role': 'user', 'content': user_message})
        session['messages'].append({'role': 'assistant', 'content': assistant_message})

        # 컨텍스트 업데이트 (첫 질문이거나 팔로업이 아닌 경우)
        if not session['context_chunks'] or not metadata.get('is_followup', False):
            # 직렬화 가능한 형태로 변환
            session['context_chunks'] = [
                {
                    'content': chunk.page_content if hasattr(chunk, 'page_content') else str(chunk),
                    'metadata': chunk.metadata if hasattr(chunk, 'metadata') else {}
                }
                for chunk in context_chunks[:10]  # 최대 10개
            ]

        # 메타데이터 업데이트
        session['metadata'].update(metadata)

        # 메시지 수 제한
        max_messages = self.MAX_MESSAGES_PER_SESSION * 2
        if len(session['messages']) > max_messages:
            session['messages'] = session['messages'][-max_messages:]

        # 타임스탬프 갱신
        session['last_accessed'] = datetime.now()

        # 저장
        self._set_session(session_id, session)

    def get_session_context(self, session_id: str) -> Dict[str, Any]:
        """
        세션의 대화 컨텍스트 조회

        Returns:
            {
                'messages': [...],
                'context_chunks': [...],
                'metadata': {...},
                'conversation_depth': int
            }
        """
        session = self._get_session(session_id)
        if not session:
            return {
                'messages': [],
                'context_chunks': [],
                'metadata': {},
                'conversation_depth': 0
            }

        # 최근 N개 턴만 반환
        max_turns = self.MAX_CONVERSATION_HISTORY_TURNS * 2
        recent_messages = session['messages'][-max_turns:]

        return {
            'messages': recent_messages,
            'context_chunks': session['context_chunks'],
            'metadata': session['metadata'],
            'conversation_depth': len(session['messages']) // 2
        }

    def delete_session(self, session_id: str) -> bool:
        """세션 삭제"""
        if self.redis_client:
            try:
                result = self.redis_client.delete(self._get_key(session_id))
                return result > 0
            except Exception as e:
                logger.error(f"Redis delete error: {e}")

        if session_id in self._fallback_sessions:
            del self._fallback_sessions[session_id]
            return True
        return False

    def cleanup_expired(self) -> int:
        """만료된 세션 정리 (in-memory fallback용)"""
        if self.redis_client:
            return 0  # Redis는 자동 TTL 처리

        now = datetime.now()
        expired = []
        for sid, session in self._fallback_sessions.items():
            last_accessed = session.get('last_accessed', now)
            if isinstance(last_accessed, str):
                last_accessed = datetime.fromisoformat(last_accessed)
            if now - last_accessed > timedelta(seconds=self.SESSION_TTL_SECONDS):
                expired.append(sid)

        for sid in expired:
            del self._fallback_sessions[sid]

        if expired:
            logger.info(f"Cleaned up {len(expired)} expired sessions")
        return len(expired)

    def get_stats(self) -> Dict[str, Any]:
        """세션 통계 조회"""
        if self.redis_client:
            try:
                keys = self.redis_client.keys(f"{self.SESSION_PREFIX}*")
                return {
                    'backend': 'redis',
                    'active_sessions': len(keys),
                    'redis_connected': True
                }
            except Exception as e:
                logger.error(f"Redis stats error: {e}")

        return {
            'backend': 'in-memory',
            'active_sessions': len(self._fallback_sessions),
            'redis_connected': False
        }


# 전역 싱글톤 인스턴스
_session_manager: Optional[RedisSessionManager] = None


def get_session_manager() -> RedisSessionManager:
    """세션 매니저 싱글톤 조회"""
    global _session_manager
    if _session_manager is None:
        _session_manager = RedisSessionManager()
    return _session_manager
```

### 4.3 main.py 수정 사항

`main.py`에서 변경해야 할 부분:

```python
# ============================================================================
# 변경 전 (line 119-127)
# ============================================================================
# Session Management for Follow-up Questions
# In-memory session storage (for production, consider Redis)
CONVERSATION_SESSIONS: Dict[str, Dict[str, Any]] = {}
SESSION_TTL_SECONDS = 3600  # 1 hour
MAX_MESSAGES_PER_SESSION = 20
MAX_CONVERSATION_HISTORY_TURNS = 5

# ============================================================================
# 변경 후
# ============================================================================
# Session Management - Redis 기반 (서버 재시작에도 유지)
from redis_session import get_session_manager, RedisSessionManager

# 세션 매니저 지연 초기화 (lifespan에서 실행)
session_manager: Optional[RedisSessionManager] = None


# ============================================================================
# lifespan 함수 내 추가 (async def lifespan 안에)
# ============================================================================
    # Initialize Redis session manager
    global session_manager
    session_manager = get_session_manager()
    stats = session_manager.get_stats()
    logger.info(f"✓ Session manager initialized: {stats}")


# ============================================================================
# 헬퍼 함수 교체
# ============================================================================

def create_or_get_session(session_id: Optional[str] = None) -> str:
    """세션 생성/조회 - Redis 기반"""
    return session_manager.create_or_get_session(session_id)


def update_session(
    session_id: str,
    user_message: str,
    assistant_message: str,
    context_chunks: List[Any],
    metadata: Dict[str, Any]
):
    """세션 업데이트 - Redis 기반"""
    session_manager.update_session(
        session_id, user_message, assistant_message, context_chunks, metadata
    )


def get_session_context(session_id: str) -> Dict[str, Any]:
    """세션 컨텍스트 조회 - Redis 기반"""
    return session_manager.get_session_context(session_id)


def cleanup_expired_sessions():
    """만료 세션 정리 - Redis 기반"""
    return session_manager.cleanup_expired()
```

### 4.4 requirements.txt에 추가

```
redis>=5.0.0
```

---

## 5. 배포 전 체크리스트

### 5.1 코드 준비 체크리스트

| # | 항목 | 상태 | 담당 | 비고 |
|---|------|------|------|------|
| 1 | docker-compose.yml 통일 | ⬜ | Dev | Fix 1 적용 |
| 2 | redis_session.py 생성 | ⬜ | Dev | Fix 2 신규 파일 |
| 3 | main.py Redis 통합 | ⬜ | Dev | Fix 2 수정 |
| 4 | requirements.txt 업데이트 | ⬜ | Dev | redis>=5.0.0 추가 |
| 5 | .env.example 작성 | ⬜ | Dev | 템플릿 |
| 6 | nginx.conf 도메인 수정 | ⬜ | Dev | ai.buddhakorea.com |
| 7 | 로컬 테스트 통과 | ⬜ | Dev | docker compose up |

### 5.2 인프라 준비 체크리스트

| # | 항목 | 상태 | 명령어/설명 |
|---|------|------|------------|
| 1 | SSH 접속 확인 | ⬜ | `ssh prod` |
| 2 | Docker 설치 | ⬜ | `docker --version` |
| 3 | Docker Compose 설치 | ⬜ | `docker compose version` |
| 4 | 방화벽 설정 | ⬜ | `sudo ufw status` |
| 5 | 디렉토리 생성 | ⬜ | `/opt/buddha-korea/` |
| 6 | GCP 키 업로드 | ⬜ | `gcp-key.json` |
| 7 | DNS 레코드 추가 | ⬜ | ai.buddhakorea.com → 157.180.72.0 |
| 8 | 디스크 공간 확인 | ⬜ | `df -h` (80GB 중 최소 10GB 여유) |
| 9 | 메모리 확인 | ⬜ | `free -h` (8GB) |

### 5.3 데이터 마이그레이션 체크리스트

| # | 항목 | 크기 | 방법 |
|---|------|------|------|
| 1 | ChromaDB 벡터 DB | ~3GB | rsync 또는 tar + scp |
| 2 | source_explorer 데이터 | ~50MB | git clone 또는 scp |
| 3 | SSL 인증서 | <1MB | Let's Encrypt 신규 발급 |
| 4 | .env 파일 | <1KB | 수동 작성 |

### 5.4 보안 체크리스트

| # | 항목 | 상태 | 설명 |
|---|------|------|------|
| 1 | SSH 키 인증만 허용 | ⬜ | Password auth 비활성화 |
| 2 | root 로그인 비활성화 | ⬜ | `PermitRootLogin no` |
| 3 | Redis 비밀번호 설정 | ⬜ | 강력한 비밀번호 |
| 4 | Redis 로컬만 노출 | ⬜ | `127.0.0.1:6379` |
| 5 | .env 파일 권한 | ⬜ | `chmod 600 .env` |
| 6 | GCP 키 파일 권한 | ⬜ | `chmod 600 gcp-key.json` |
| 7 | HTTPS 강제 | ⬜ | HTTP → HTTPS 리다이렉트 |
| 8 | 시크릿 Git 제외 | ⬜ | `.gitignore`에 .env, *.json 키 |

### 5.5 성능/안정성 체크리스트

| # | 항목 | 목표 | 확인 방법 |
|---|------|------|----------|
| 1 | Health check 응답 | <1s | `curl /api/health` |
| 2 | 첫 쿼리 응답 | <30s | 브라우저 테스트 |
| 3 | 메모리 사용량 | <6GB | `docker stats` |
| 4 | 컨테이너 자동 재시작 | Yes | `restart: unless-stopped` |
| 5 | 로그 로테이션 | 설정됨 | `max-size: 50m` |
| 6 | 벡터 DB 로드 | 성공 | 로그 확인 |

---

## 6. 배포 절차

### 6.1 Step 1: 파일 전송

```bash
# 로컬에서 실행
cd /path/to/buddhakorea/opennotebook

# 1. 소스 코드 전송 (Git 사용 권장)
# Option A: Git clone (권장)
ssh prod "cd /opt/buddha-korea && git clone https://github.com/your-repo/buddhakorea.git ."

# Option B: rsync (Git 없이)
rsync -avz --progress \
  --exclude='chroma_db' \
  --exclude='__pycache__' \
  --exclude='.env' \
  --exclude='*.pyc' \
  ./ prod:/opt/buddha-korea/

# 2. ChromaDB 전송 (대용량, 압축 전송)
tar -czvf chroma_db.tar.gz chroma_db/
scp chroma_db.tar.gz prod:/opt/buddha-korea/
ssh prod "cd /opt/buddha-korea && tar -xzvf chroma_db.tar.gz && rm chroma_db.tar.gz"

# 3. GCP 키 전송
scp gcp-key.json prod:/opt/buddha-korea/
ssh prod "chmod 600 /opt/buddha-korea/gcp-key.json"
```

### 6.2 Step 2: 환경 설정

```bash
# VM에서 실행
ssh prod
cd /opt/buddha-korea

# .env 파일 생성
cat > .env << 'EOF'
# GCP Vertex AI
GCP_PROJECT_ID=gen-lang-client-0324154376
GCP_LOCATION=us-central1

# 모델
LLM_MODEL=gemini-2.5-pro
LLM_MODEL_FAST=gemini-2.5-flash
USE_GEMINI_FOR_QUERIES=true

# ChromaDB
CHROMA_COLLECTION_NAME=cbeta_sutras_gemini

# Redis (강력한 비밀번호로 변경!)
REDIS_PASSWORD=your-very-strong-password-change-this

# API
ALLOWED_ORIGINS=https://ai.buddhakorea.com,https://buddhakorea.com
RATE_LIMIT_PER_HOUR=100
LOG_LEVEL=info
EOF

# 권한 설정
chmod 600 .env
```

### 6.3 Step 3: SSL 인증서 (Let's Encrypt)

```bash
# Certbot 설치
sudo apt install -y certbot

# 인증서 발급 (nginx 중지 상태에서)
sudo certbot certonly --standalone -d ai.buddhakorea.com

# 인증서 복사
sudo cp /etc/letsencrypt/live/ai.buddhakorea.com/fullchain.pem /opt/buddha-korea/ssl/
sudo cp /etc/letsencrypt/live/ai.buddhakorea.com/privkey.pem /opt/buddha-korea/ssl/
sudo chown $USER:$USER /opt/buddha-korea/ssl/*.pem

# ⚠️ 자동 갱신 deploy-hook 설정 (필수! 없으면 90일 후 HTTPS 에러)
sudo mkdir -p /etc/letsencrypt/renewal-hooks/deploy
sudo tee /etc/letsencrypt/renewal-hooks/deploy/reload-nginx.sh << 'EOF'
#!/bin/bash
DOMAIN="ai.buddhakorea.com"
cp /etc/letsencrypt/live/$DOMAIN/fullchain.pem /opt/buddha-korea/ssl/
cp /etc/letsencrypt/live/$DOMAIN/privkey.pem /opt/buddha-korea/ssl/
chmod 644 /opt/buddha-korea/ssl/fullchain.pem
chmod 600 /opt/buddha-korea/ssl/privkey.pem
docker compose -f /opt/buddha-korea/docker-compose.yml exec -T nginx nginx -s reload 2>/dev/null || \
    docker compose -f /opt/buddha-korea/docker-compose.yml restart nginx
echo "[$(date)] SSL renewed and Nginx reloaded"
EOF
sudo chmod +x /etc/letsencrypt/renewal-hooks/deploy/reload-nginx.sh

# 자동 갱신 타이머 활성화
sudo systemctl enable certbot.timer

# 자동 갱신 테스트 (dry-run)
sudo certbot renew --dry-run
```

### 6.4 Step 4: Docker 빌드 및 실행

```bash
cd /opt/buddha-korea

# 이미지 빌드
docker compose build --no-cache

# 컨테이너 시작
docker compose up -d

# 로그 확인
docker compose logs -f

# 상태 확인
docker compose ps
docker stats
```

### 6.5 Step 5: 검증

```bash
# Health check
curl http://localhost:8000/api/health
curl https://ai.buddhakorea.com/api/health

# 세션 테스트 (Redis 확인)
docker exec buddhakorea-redis redis-cli -a 'your-password' INFO keyspace

# 쿼리 테스트
curl -X POST https://ai.buddhakorea.com/api/chat \
  -H "Content-Type: application/json" \
  -d '{"query": "사성제란 무엇인가?"}'
```

---

## 7. 배포 후 검증

### 7.1 필수 검증 항목

```bash
#!/bin/bash
# verify_deployment.sh

echo "=== Buddha Korea Deployment Verification ==="

# 1. 컨테이너 상태
echo -e "\n[1/7] Container Status:"
docker compose ps

# 2. Health check
echo -e "\n[2/7] Health Check:"
curl -s https://ai.buddhakorea.com/api/health | jq .

# 3. Redis 연결
echo -e "\n[3/7] Redis Connection:"
docker exec buddhakorea-redis redis-cli -a "$REDIS_PASSWORD" PING

# 4. 세션 테스트
echo -e "\n[4/7] Session Test:"
docker exec buddhakorea-backend python -c "
from redis_session import get_session_manager
mgr = get_session_manager()
print(mgr.get_stats())
"

# 5. 메모리 사용량
echo -e "\n[5/7] Memory Usage:"
docker stats --no-stream --format "table {{.Name}}\t{{.MemUsage}}\t{{.MemPerc}}"

# 6. 디스크 사용량
echo -e "\n[6/7] Disk Usage:"
df -h /opt/buddha-korea

# 7. SSL 인증서
echo -e "\n[7/7] SSL Certificate:"
echo | openssl s_client -servername ai.buddhakorea.com -connect ai.buddhakorea.com:443 2>/dev/null | openssl x509 -noout -dates

echo -e "\n=== Verification Complete ==="
```

### 7.2 기능 테스트

| 테스트 | 예상 결과 | 확인 |
|--------|----------|------|
| `/api/health` | `{"status": "healthy"}` | ⬜ |
| `/api/chat` (첫 질문) | 응답 + session_id | ⬜ |
| `/api/chat` (후속 질문) | 이전 컨텍스트 유지 | ⬜ |
| 서버 재시작 후 세션 | 세션 유지됨 | ⬜ |
| `/api/sources` | 경전 목록 반환 | ⬜ |
| Rate limiting | 429 응답 (초과 시) | ⬜ |

---

## 8. 롤백 절차

### 8.1 빠른 롤백 (컨테이너 레벨)

```bash
# 이전 이미지로 롤백
docker compose down
docker tag buddhakorea-backend:latest buddhakorea-backend:broken
docker pull buddhakorea-backend:previous  # 또는 이전 빌드
docker compose up -d
```

### 8.2 전체 롤백 (GCP VM으로)

```bash
# 1. Hetzner nginx 중지
ssh prod "docker compose stop nginx"

# 2. DNS를 GCP VM IP로 변경
# ai.buddhakorea.com → [GCP VM IP]

# 3. GCP VM 서비스 재시작
gcloud compute ssh buddhakorea-rag-server --zone=us-central1-a \
  --command="cd /opt/buddha-korea && docker compose up -d"
```

---

## 9. 모니터링 및 유지보수

### 9.1 로그 확인

```bash
# 전체 로그
docker compose logs -f

# 특정 서비스
docker compose logs -f backend
docker compose logs -f nginx
docker compose logs -f redis

# 최근 100줄
docker compose logs --tail=100 backend
```

### 9.2 리소스 모니터링

```bash
# 실시간 리소스
docker stats

# 디스크 사용량
du -sh /opt/buddha-korea/chroma_db
du -sh /opt/buddha-korea/redis-data
du -sh /opt/buddha-korea/logs

# 시스템 전체
htop
```

### 9.3 백업 (로컬 + GCS 오프사이트)

> **3-2-1 백업 원칙**:
> - **3개 복사본**: 원본 + 로컬 백업 + GCS 오프사이트
> - **2가지 미디어**: 로컬 SSD + 클라우드 스토리지
> - **1개 오프사이트**: 디스크 장애 시에도 복구 가능
>
> **Redis 백업 방식**: `BGSAVE` + `sleep` 대신 **호스트 볼륨 전체 백업**
> - `redis-data/` 폴더에 `dump.rdb` + `appendonly.aof` 모두 포함
> - 데이터 크기와 관계없이 안전

#### GCS 버킷 사전 설정

```bash
# 1. 버킷 생성 (최초 1회)
gcloud storage buckets create gs://buddhakorea-backups \
    --location=asia-northeast3 \
    --uniform-bucket-level-access

# 2. 수명 주기 정책 (7일 후 자동 삭제)
cat > /tmp/lifecycle.json << 'EOF'
{
  "rule": [
    {
      "action": {"type": "Delete"},
      "condition": {"age": 7}
    }
  ]
}
EOF

gcloud storage buckets update gs://buddhakorea-backups \
    --lifecycle-file=/tmp/lifecycle.json

# 3. 서비스 계정 권한 (Hetzner VM에서 접근용)
# VM에 gcloud CLI 설치 및 인증 필요
```

#### 백업 스크립트

```bash
# /opt/buddha-korea/scripts/backup.sh
#!/bin/bash
set -e

APP_DIR="/opt/buddha-korea"
BACKUP_DIR="/opt/backups"
GCS_BUCKET="gs://buddhakorea-backups"
DATE=$(date +%Y%m%d_%H%M%S)
DATE_PATH=$(date +%Y/%m/%d)

mkdir -p $BACKUP_DIR

echo "[$(date)] 🚀 백업 시작..."

# ChromaDB 백업 (~3GB)
tar -czf $BACKUP_DIR/chroma_db_$DATE.tar.gz -C $APP_DIR chroma_db

# Redis 백업 (전체 폴더 - RDB + AOF 포함)
tar -czf $BACKUP_DIR/redis_data_$DATE.tar.gz -C $APP_DIR redis-data

# 환경 설정 백업
tar -czf $BACKUP_DIR/config_$DATE.tar.gz -C $APP_DIR \
    docker-compose.yml .env nginx.conf redis.conf 2>/dev/null || true

# GCS 오프사이트 업로드
echo "[$(date)] ☁️ GCS로 전송 중..."
if gcloud storage cp $BACKUP_DIR/*_$DATE.tar.gz "$GCS_BUCKET/$DATE_PATH/"; then
    # GCS 업로드 성공 시에만 로컬 정리 (3일 이상)
    find $BACKUP_DIR -name "*.tar.gz" -mtime +3 -delete
    echo "[$(date)] ✅ 백업 완료! (로컬: 3일, GCS: 7일 보관)"
else
    echo "[$(date)] ❌ GCS 업로드 실패 - 로컬 백업 유지"
    exit 1
fi
```

```bash
# 스크립트 권한 설정
chmod +x /opt/buddha-korea/scripts/backup.sh

# 크론 설정 (매일 새벽 3시)
sudo crontab -e
# 추가:
0 3 * * * /opt/buddha-korea/scripts/backup.sh >> /var/log/buddha-backup.log 2>&1
```

#### 복구 방법

```bash
# 로컬 백업에서 복구 (빠름)
cd /opt/buddha-korea && docker compose down
tar -xzf /opt/backups/chroma_db_YYYYMMDD.tar.gz -C /opt/buddha-korea/
tar -xzf /opt/backups/redis_data_YYYYMMDD.tar.gz -C /opt/buddha-korea/
docker compose up -d

# GCS에서 복구 (로컬 손실 시)
gcloud storage cp "gs://buddhakorea-backups/2025/01/15/*" /opt/backups/
tar -xzf /opt/backups/chroma_db_*.tar.gz -C /opt/buddha-korea/
tar -xzf /opt/backups/redis_data_*.tar.gz -C /opt/buddha-korea/
docker compose up -d
```

### 9.4 SSL 인증서 갱신 (Critical - 90일 자동화)

> **⚠️ 주의**: Certbot은 `/etc/letsencrypt/`에 인증서를 갱신하지만,
> Nginx 컨테이너는 `/opt/buddha-korea/ssl/`을 바라봅니다.
> **deploy-hook 없이는 90일 후 HTTPS 에러가 발생합니다!**

#### 자동 갱신 설정 (필수)

```bash
# 1. deploy-hook 스크립트 생성
sudo mkdir -p /etc/letsencrypt/renewal-hooks/deploy
sudo tee /etc/letsencrypt/renewal-hooks/deploy/reload-nginx.sh << 'EOF'
#!/bin/bash
# Let's Encrypt 갱신 후 자동 실행되는 스크립트
# 인증서를 앱 디렉토리로 복사하고 Nginx 재시작

DOMAIN="ai.buddhakorea.com"
APP_SSL_DIR="/opt/buddha-korea/ssl"
COMPOSE_FILE="/opt/buddha-korea/docker-compose.yml"

echo "[$(date)] SSL certificate renewed for $DOMAIN"

# 인증서 복사
cp /etc/letsencrypt/live/$DOMAIN/fullchain.pem $APP_SSL_DIR/
cp /etc/letsencrypt/live/$DOMAIN/privkey.pem $APP_SSL_DIR/

# 권한 설정
chmod 644 $APP_SSL_DIR/fullchain.pem
chmod 600 $APP_SSL_DIR/privkey.pem

# Nginx 재시작 (graceful reload)
docker compose -f $COMPOSE_FILE exec -T nginx nginx -s reload 2>/dev/null || \
    docker compose -f $COMPOSE_FILE restart nginx

echo "[$(date)] Nginx reloaded with new certificate"
EOF

# 2. 실행 권한 부여
sudo chmod +x /etc/letsencrypt/renewal-hooks/deploy/reload-nginx.sh

# 3. 자동 갱신 테스트 (실제 갱신 없이 시뮬레이션)
sudo certbot renew --dry-run
```

#### 수동 갱신 (필요 시)

```bash
# 인증서 수동 갱신
sudo certbot renew

# deploy-hook이 자동 실행되지만, 수동으로 해야 한다면:
sudo /etc/letsencrypt/renewal-hooks/deploy/reload-nginx.sh
```

#### 갱신 상태 확인

```bash
# 인증서 만료일 확인
sudo certbot certificates

# 또는 OpenSSL로 직접 확인
echo | openssl s_client -servername ai.buddhakorea.com -connect ai.buddhakorea.com:443 2>/dev/null | openssl x509 -noout -dates

# 갱신 타이머 상태 (Ubuntu)
sudo systemctl status certbot.timer
```

#### 트러블슈팅

```bash
# 갱신 로그 확인
sudo tail -f /var/log/letsencrypt/letsencrypt.log

# deploy-hook 수동 테스트
sudo /etc/letsencrypt/renewal-hooks/deploy/reload-nginx.sh
```

---

## 부록: 명령어 치트시트

```bash
# ═══════════════════════════════════════════════════════════
# 자주 쓰는 명령어
# ═══════════════════════════════════════════════════════════

# 접속
ssh prod

# 서비스 시작/중지
cd /opt/buddha-korea
docker compose up -d      # 시작
docker compose down       # 중지
docker compose restart    # 재시작

# 로그
docker compose logs -f              # 전체
docker compose logs -f backend      # 백엔드만

# 상태
docker compose ps
docker stats

# 빌드 (코드 변경 후)
docker compose build backend
docker compose up -d backend

# Redis CLI
docker exec -it buddhakorea-redis redis-cli -a 'password'

# 컨테이너 쉘 접속
docker exec -it buddhakorea-backend /bin/bash

# 디스크 정리
docker system prune -af
```

---

> **문서 작성**: Claude Code
> **버전**: 1.0
> **다음 단계**: Fix 1, Fix 2 적용 후 배포 진행

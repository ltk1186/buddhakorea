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
            logger.info(f"Redis connected: {self.host}:{self.port}")
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

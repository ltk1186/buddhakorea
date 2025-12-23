"""
Authentication Module
=====================
OAuth 2.0 + JWT authentication for Buddha Korea

Features:
- Google, Naver, Kakao OAuth providers
- Short-lived access tokens (15 min) + refresh tokens (7 days)
- CSRF protection via state parameter
"""

import secrets
from authlib.integrations.starlette_client import OAuth
from datetime import datetime, timedelta, timezone
import jwt
from typing import Optional, Dict, Tuple
import logging

logger = logging.getLogger(__name__)

# OAuth client instance
oauth = OAuth()

# Configuration (set via setup_auth)
SECRET_KEY = "default-insecure-secret"
REFRESH_SECRET_KEY = "default-refresh-secret"  # Separate key for refresh tokens
ALGORITHM = "HS256"

# Token expiration settings
ACCESS_TOKEN_EXPIRE_MINUTES = 15  # Short-lived for security
REFRESH_TOKEN_EXPIRE_DAYS = 7     # Longer for convenience

# Redis client reference (set via setup_auth)
_redis_client = None


def setup_auth(config, redis_client=None):
    """
    Initialize Auth system with config.

    Args:
        config: AppConfig with secret keys and OAuth credentials
        redis_client: Redis client for CSRF state storage
    """
    global SECRET_KEY, REFRESH_SECRET_KEY, ACCESS_TOKEN_EXPIRE_MINUTES, REFRESH_TOKEN_EXPIRE_DAYS, _redis_client

    SECRET_KEY = config.secret_key
    REFRESH_SECRET_KEY = getattr(config, 'refresh_secret_key', config.secret_key + '-refresh')
    ACCESS_TOKEN_EXPIRE_MINUTES = getattr(config, 'access_token_expire_minutes', 15)
    REFRESH_TOKEN_EXPIRE_DAYS = getattr(config, 'refresh_token_expire_days', 7)
    _redis_client = redis_client

    # Register OAuth providers
    if config.google_client_id and config.google_client_secret:
        oauth.register(
            name='google',
            client_id=config.google_client_id,
            client_secret=config.google_client_secret,
            server_metadata_url='https://accounts.google.com/.well-known/openid-configuration',
            client_kwargs={'scope': 'openid email profile'}
        )
        logger.info("Registered Google OAuth")

    if config.naver_client_id and config.naver_client_secret:
        oauth.register(
            name='naver',
            client_id=config.naver_client_id,
            client_secret=config.naver_client_secret,
            api_base_url='https://openapi.naver.com/v1/nid/me',
            request_token_url=None,
            access_token_url='https://nid.naver.com/oauth2.0/token',
            authorize_url='https://nid.naver.com/oauth2.0/authorize',
            client_kwargs={}
        )
        logger.info("Registered Naver OAuth")

    if config.kakao_client_id and config.kakao_client_secret:
        oauth.register(
            name='kakao',
            client_id=config.kakao_client_id,
            client_secret=config.kakao_client_secret,
            api_base_url='https://kapi.kakao.com/v2/user/me',
            request_token_url=None,
            access_token_url='https://kauth.kakao.com/oauth/token',
            authorize_url='https://kauth.kakao.com/oauth/authorize',
            client_kwargs={'scope': 'profile_nickname'},
            token_endpoint_auth_method='client_secret_post'
        )
        logger.info("Registered Kakao OAuth")


# ============================================================================
# CSRF State Management
# ============================================================================

def generate_oauth_state() -> str:
    """
    Generate a random state parameter for CSRF protection.

    The state is stored in Redis with a 10-minute TTL.
    Returns the state string to be passed to the OAuth provider.
    """
    state = secrets.token_urlsafe(32)

    if _redis_client:
        try:
            _redis_client.setex(f"oauth_state:{state}", 600, "valid")  # 10 min TTL
        except Exception as e:
            logger.warning(f"Failed to store OAuth state in Redis: {e}")

    return state


def validate_oauth_state(state: str) -> bool:
    """
    Validate and consume a state parameter.

    Returns True if state is valid, False otherwise.
    Valid states are deleted after use (one-time use).
    """
    if not state:
        return False

    if _redis_client:
        try:
            key = f"oauth_state:{state}"
            result = _redis_client.get(key)
            if result:
                _redis_client.delete(key)  # Consume the state
                return True
            return False
        except Exception as e:
            logger.warning(f"Failed to validate OAuth state in Redis: {e}")
            return True  # Allow if Redis fails (graceful degradation)

    # If no Redis, skip state validation (not recommended for production)
    return True


# ============================================================================
# Token Creation
# ============================================================================

def create_access_token(data: dict, expires_delta: Optional[timedelta] = None) -> str:
    """
    Create a short-lived JWT access token.

    Args:
        data: Payload data (should include user_id, email)
        expires_delta: Optional custom expiration (defaults to ACCESS_TOKEN_EXPIRE_MINUTES)

    Returns:
        Encoded JWT string
    """
    to_encode = data.copy()
    to_encode["type"] = "access"

    if expires_delta:
        expire = datetime.now(timezone.utc) + expires_delta
    else:
        expire = datetime.now(timezone.utc) + timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)

    to_encode["exp"] = expire
    to_encode["iat"] = datetime.now(timezone.utc)

    return jwt.encode(to_encode, SECRET_KEY, algorithm=ALGORITHM)


def create_refresh_token(data: dict, expires_delta: Optional[timedelta] = None) -> str:
    """
    Create a long-lived JWT refresh token.

    Args:
        data: Payload data (should include user_id)
        expires_delta: Optional custom expiration (defaults to REFRESH_TOKEN_EXPIRE_DAYS)

    Returns:
        Encoded JWT string
    """
    to_encode = {"user_id": data.get("user_id"), "type": "refresh"}

    if expires_delta:
        expire = datetime.now(timezone.utc) + expires_delta
    else:
        expire = datetime.now(timezone.utc) + timedelta(days=REFRESH_TOKEN_EXPIRE_DAYS)

    to_encode["exp"] = expire
    to_encode["iat"] = datetime.now(timezone.utc)

    return jwt.encode(to_encode, REFRESH_SECRET_KEY, algorithm=ALGORITHM)


def create_token_pair(user_id: int, email: str) -> Tuple[str, str]:
    """
    Create both access and refresh tokens.

    Args:
        user_id: User's database ID
        email: User's email

    Returns:
        Tuple of (access_token, refresh_token)
    """
    access_data = {"user_id": user_id, "sub": email}
    refresh_data = {"user_id": user_id}

    access_token = create_access_token(access_data)
    refresh_token = create_refresh_token(refresh_data)

    return access_token, refresh_token


# ============================================================================
# Token Verification
# ============================================================================

def decode_access_token(token: str) -> Optional[Dict]:
    """
    Verify and decode a JWT access token.

    Returns:
        Decoded payload dict if valid, None otherwise
    """
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])

        # Verify it's an access token
        if payload.get("type") != "access":
            # Allow legacy tokens without type field
            if "type" in payload:
                return None

        return payload
    except jwt.ExpiredSignatureError:
        logger.debug("Access token expired")
        return None
    except jwt.InvalidTokenError as e:
        logger.debug(f"Invalid access token: {e}")
        return None


def decode_refresh_token(token: str) -> Optional[Dict]:
    """
    Verify and decode a JWT refresh token.

    Returns:
        Decoded payload dict if valid, None otherwise
    """
    try:
        payload = jwt.decode(token, REFRESH_SECRET_KEY, algorithms=[ALGORITHM])

        # Verify it's a refresh token
        if payload.get("type") != "refresh":
            return None

        return payload
    except jwt.ExpiredSignatureError:
        logger.debug("Refresh token expired")
        return None
    except jwt.InvalidTokenError as e:
        logger.debug(f"Invalid refresh token: {e}")
        return None


def refresh_access_token(refresh_token: str) -> Optional[Tuple[str, Dict]]:
    """
    Use a refresh token to generate a new access token.

    Args:
        refresh_token: Valid refresh token

    Returns:
        Tuple of (new_access_token, payload) if valid, None otherwise
    """
    payload = decode_refresh_token(refresh_token)
    if not payload:
        return None

    user_id = payload.get("user_id")
    if not user_id:
        return None

    # Create new access token (email will be fetched from DB in endpoint)
    new_access_token = create_access_token({"user_id": user_id, "sub": ""})

    return new_access_token, payload

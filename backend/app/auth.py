from authlib.integrations.starlette_client import OAuth
from datetime import datetime, timedelta, timezone
import jwt
from typing import Optional, Dict
import logging

logger = logging.getLogger(__name__)

oauth = OAuth()
SECRET_KEY = "default-insecure-secret"
ALGORITHM = "HS256"

def setup_auth(config):
    """Initialize Auth system with config."""
    global SECRET_KEY
    SECRET_KEY = config.secret_key
    
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
            client_kwargs={'scope': 'account_email profile_nickname'}
        )
        logger.info("Registered Kakao OAuth")

def create_access_token(data: dict, expires_delta: Optional[timedelta] = None) -> str:
    """Create a JWT access token."""
    to_encode = data.copy()
    if expires_delta:
        expire = datetime.now(timezone.utc) + expires_delta
    else:
        expire = datetime.now(timezone.utc) + timedelta(minutes=60*24) # 24 hours default
    to_encode.update({"exp": expire})
    encoded_jwt = jwt.encode(to_encode, SECRET_KEY, algorithm=ALGORITHM)
    return encoded_jwt

def decode_access_token(token: str) -> Optional[Dict]:
    """Verify and decode a JWT access token."""
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        return payload
    except jwt.InvalidTokenError:
        return None

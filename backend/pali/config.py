"""
Configuration management for Pali Translator API.
Loads settings from environment variables with sensible defaults.
"""
import os
from pathlib import Path
from typing import Optional
from pydantic_settings import BaseSettings
from functools import lru_cache

# Dynamic path resolution for DPD database
def get_default_dpd_path() -> str:
    """Get default DPD database path relative to this config file."""
    # backend/pali/config.py -> backend/data/dpd/dpd.db
    config_dir = Path(__file__).parent
    dpd_path = config_dir.parent / "data" / "dpd" / "dpd.db"
    return str(dpd_path)


class Settings(BaseSettings):
    """Application settings loaded from environment variables."""

    # Application
    APP_NAME: str = "Pali Translator API"
    APP_VERSION: str = "1.0.0"
    ENVIRONMENT: str = "development"
    DEBUG: bool = False

    # Database
    DATABASE_URL: str = "postgresql://pali:password@localhost:5432/pali_translator"

    # Redis
    REDIS_URL: str = "redis://localhost:6379/1"

    # Google Cloud / Vertex AI
    GCP_PROJECT_ID: Optional[str] = None
    GOOGLE_APPLICATION_CREDENTIALS: Optional[str] = None
    GEMINI_MODEL: str = "gemini-2.5-pro"

    # For development with google-generativeai (non-Vertex)
    GEMINI_API_KEY: Optional[str] = None

    # DPD Dictionary Database
    DPD_DATABASE_PATH: str = get_default_dpd_path()

    # Sentry
    SENTRY_DSN: Optional[str] = None

    # Admin
    ADMIN_TOKEN: Optional[str] = None

    # CORS
    CORS_ORIGINS: list[str] = [
        "https://ai.buddhakorea.com",
        "http://localhost:5173",
        "http://localhost:3000",
    ]

    # Translation settings
    MAX_CHUNK_SIZE: int = 2000
    TEMPERATURE: float = 0.1
    MAX_RETRIES: int = 3
    RETRY_BASE_DELAY: float = 2.0

    # DPD Hint settings
    HINT_ENABLED: bool = True
    HINT_MAX_TOKENS_PER_SEGMENT: int = 160
    HINT_MAX_TOKENS_PER_BATCH: int = 800
    HINT_MAX_WORDS_PER_SEGMENT: int = 100

    # Batch translation settings
    BATCH_MAX_SEGMENTS: int = 3  # Reduced to prevent token overflow
    TRANSLATION_MAX_RETRIES: int = 2  # Increased for reliability
    EXPLANATION_MAX_SENTENCES: int = 3

    class Config:
        env_file = ".env"
        case_sensitive = True


@lru_cache()
def get_settings() -> Settings:
    """Get cached settings instance."""
    return Settings()


settings = get_settings()

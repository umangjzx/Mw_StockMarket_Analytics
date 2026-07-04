"""
Application configuration — all settings are sourced from environment variables or a .env
file via Pydantic Settings. Never hardcode secrets.
"""

from functools import lru_cache
from typing import Literal

from pydantic import Field, PostgresDsn, RedisDsn
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    # ── Application ──────────────────────────────────────────────────────
    APP_ENV: Literal["development", "staging", "production"] = "development"
    APP_DEBUG: bool = False
    APP_NAME: str = "MW StockMarket Analytics"
    SECRET_KEY: str = Field(..., description="Secret key for JWT signing")

    # ── Database ─────────────────────────────────────────────────────────
    DATABASE_URL: str = Field(
        "postgresql+asyncpg://mw_user:mw_pass@localhost:5432/mw_stockmarket",
        description="Async SQLAlchemy DSN (asyncpg driver)",
    )
    DATABASE_URL_SYNC: str = Field(
        "postgresql://mw_user:mw_pass@localhost:5432/mw_stockmarket",
        description="Sync DSN used by Alembic migrations",
    )
    DATABASE_POOL_SIZE: int = 10
    DATABASE_MAX_OVERFLOW: int = 20

    # ── Redis ─────────────────────────────────────────────────────────────
    REDIS_URL: str = "redis://localhost:6379/0"
    CELERY_BROKER_URL: str = "redis://localhost:6379/0"
    CELERY_RESULT_BACKEND: str = "redis://localhost:6379/1"

    # ── YouTube Data API ──────────────────────────────────────────────────
    YOUTUBE_API_KEY: str = Field("", description="YouTube Data API v3 key")
    YOUTUBE_DAILY_QUOTA_LIMIT: int = 10_000

    # ── OpenAI ────────────────────────────────────────────────────────────
    OPENAI_API_KEY: str = Field("", description="OpenAI API key")
    OPENAI_LLM_MODEL: str = "gpt-4o-mini"
    OPENAI_EMBEDDING_MODEL: str = "text-embedding-3-small"
    OPENAI_MAX_TOKENS: int = 4096
    OPENAI_DAILY_SPEND_LIMIT: float = 10.00

    # ── Ollama (local FREE models) ─────────────────────────────────────────
    LLM_PROVIDER: str = "ollama"                               # "openai" | "ollama"
    OLLAMA_BASE_URL: str = "http://host.docker.internal:11434" # reaches host Ollama from Docker
    OLLAMA_LLM_MODEL: str = "mistral:latest"
    OLLAMA_EMBEDDING_MODEL: str = "nomic-embed-text:latest"

    # ── Transcription ─────────────────────────────────────────────────────
    WHISPER_MODE: Literal["local", "openai_api", "groq"] = "groq"  # groq is FREE and fast!
    WHISPER_MODEL_SIZE: Literal["tiny", "base", "small", "medium", "large-v2"] = "base"
    WHISPER_DEVICE: Literal["cpu", "cuda"] = "cpu"
    GROQ_API_KEY: str = Field("", description="Groq API key for ultra-fast FREE Whisper")

    # ── JWT Auth ──────────────────────────────────────────────────────────
    JWT_ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 60
    REFRESH_TOKEN_EXPIRE_DAYS: int = 7

    # ── Admin ─────────────────────────────────────────────────────────────
    ADMIN_API_KEY: str = Field("changeme-admin-key", description="Static API key for admin endpoints")

    # ── Object Storage ────────────────────────────────────────────────────
    STORAGE_BACKEND: Literal["local", "s3"] = "local"
    MEDIA_CACHE_DIR: str = "/tmp/mw_media_cache"
    MEDIA_RETENTION_HOURS: int = 24

    AWS_ACCESS_KEY_ID: str = ""
    AWS_SECRET_ACCESS_KEY: str = ""
    AWS_S3_BUCKET: str = ""
    AWS_S3_REGION: str = "us-east-1"

    # ── Observability ─────────────────────────────────────────────────────
    SENTRY_DSN: str = ""
    LOG_LEVEL: str = "INFO"
    PROMETHEUS_ENABLED: bool = True

    # ── Celery / Workers ─────────────────────────────────────────────────
    CELERY_TASK_ALWAYS_EAGER: bool = False
    MAX_PIPELINE_RETRIES: int = 5
    PIPELINE_RETRY_BACKOFF_MAX: int = 600

    # ── Market Data (Company Intelligence) ─────────────────────────────────
    TWELVE_DATA_API_KEY: str = Field(
        "", description="Twelve Data API key — fallback market data provider. Empty disables it."
    )
    MARKET_QUOTE_CACHE_TTL_SECONDS: int = 30
    MARKET_WATCHED_REFRESH_MINUTES: int = 5

    @property
    def is_production(self) -> bool:
        return self.APP_ENV == "production"

    @property
    def is_development(self) -> bool:
        return self.APP_ENV == "development"


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    """Return the cached Settings singleton. Call this wherever settings are needed."""
    return Settings()


# Module-level convenience alias — import `settings` directly from this module.
settings = get_settings()

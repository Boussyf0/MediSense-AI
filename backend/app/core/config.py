"""
Application configuration — reads from environment variables / .env file.

Why pydantic-settings?
  - Type-safe: APP_PORT="abc" raises a validation error at startup
  - Automatic .env loading: no manual os.getenv() calls scattered everywhere
  - Single source of truth: every setting lives here, imported where needed
"""
from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict
from functools import lru_cache


class Settings(BaseSettings):
    # App
    APP_ENV: str = "development"
    APP_HOST: str = "0.0.0.0"
    APP_PORT: int = 8000
    API_V1_PREFIX: str = "/api/v1"
    CORS_ORIGINS: list[str] = ["https://localhost", "http://localhost:3000"]

    # PostgreSQL
    POSTGRES_HOST: str = "postgres"
    POSTGRES_PORT: int = 5432
    POSTGRES_DB: str = "medisense_db"
    POSTGRES_USER: str = "medisense_user"
    POSTGRES_PASSWORD: str

    # Redis
    REDIS_HOST: str = "redis"
    REDIS_PORT: int = 6379
    REDIS_PASSWORD: str = ""

    # JWT
    JWT_SECRET_KEY: str
    JWT_ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 15
    REFRESH_TOKEN_EXPIRE_DAYS: int = 7

    # RGPD
    PGCRYPTO_KEY: str   # AES-256 key for identity encryption — never logged

    # Qdrant (used Sprint 3)
    QDRANT_HOST: str = "qdrant"
    QDRANT_PORT: int = 6333

    # LLM provider — "ollama" (local) or "groq" (cloud, fast demo)
    LLM_PROVIDER: str = "ollama"

    # Ollama — local inference (Docker service or native on host with Metal GPU)
    # Native Mac M1: set OLLAMA_HOST=host.docker.internal + run `ollama serve` on host
    OLLAMA_HOST: str = "ollama"
    OLLAMA_PORT: int = 11434
    OLLAMA_MODEL: str = "llama3.1:8b"

    # Groq — cloud inference, ~300 tok/s, free tier (console.groq.com)
    # Set LLM_PROVIDER=groq and GROQ_API_KEY=gsk_... in .env
    GROQ_API_KEY: str = ""
    GROQ_MODEL: str = "llama-3.1-8b-instant"

    # SMS reminders (Sprint 5)
    # If SMS_WEBHOOK_URL is empty, reminders are sent in mock mode (dev/demo).
    SMS_WEBHOOK_URL: str = ""
    SMS_WEBHOOK_TOKEN: str = ""
    SMS_PROVIDER_TIMEOUT_SECONDS: float = Field(default=3.0, gt=0)
    SMS_REMINDER_THRESHOLD: float = Field(default=0.30, ge=0.0, le=1.0)
    SMS_REMINDER_MAX_COUNT: int = Field(default=2, ge=1, le=2)

    # Salesforce CRM (Sprint 6 — US-24)
    # If SALESFORCE_WEBHOOK_URL is empty, CRM sync is skipped (dev/demo mode).
    SALESFORCE_WEBHOOK_URL: str = ""
    SALESFORCE_TOKEN: str = ""
    SALESFORCE_TIMEOUT_SECONDS: float = Field(default=3.0, gt=0)
    SALESFORCE_MAX_RETRIES: int = Field(default=3, ge=1, le=5)
    SALESFORCE_RETRY_DELAY_SECONDS: float = Field(default=2.0, gt=0)

    # MLflow Model Registry (Sprint 6 — US-33)
    MLFLOW_MODEL_NAME: str = "noshow-risk-model"
    MLFLOW_PROMOTION_F1_THRESHOLD: float = Field(default=0.80, ge=0.0, le=1.0)
    MLFLOW_PROMOTION_AUC_THRESHOLD: float = Field(default=0.87, ge=0.0, le=1.0)

    @property
    def DATABASE_URL(self) -> str:
        """Async URL for SQLAlchemy (asyncpg driver)."""
        return (
            f"postgresql+asyncpg://{self.POSTGRES_USER}:{self.POSTGRES_PASSWORD}"
            f"@{self.POSTGRES_HOST}:{self.POSTGRES_PORT}/{self.POSTGRES_DB}"
        )

    @property
    def DATABASE_URL_SYNC(self) -> str:
        """Sync URL for Alembic migrations (psycopg2 driver)."""
        return (
            f"postgresql+psycopg2://{self.POSTGRES_USER}:{self.POSTGRES_PASSWORD}"
            f"@{self.POSTGRES_HOST}:{self.POSTGRES_PORT}/{self.POSTGRES_DB}"
        )

    @property
    def REDIS_URL(self) -> str:
        if self.REDIS_PASSWORD:
            return f"redis://:{self.REDIS_PASSWORD}@{self.REDIS_HOST}:{self.REDIS_PORT}/0"
        return f"redis://{self.REDIS_HOST}:{self.REDIS_PORT}/0"

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=True,
    )


@lru_cache()
def get_settings() -> Settings:
    """
    Return cached Settings instance.

    Why lru_cache?
      - Settings reads from disk/env on every instantiation
      - lru_cache means it's read ONCE and reused across the entire app lifetime
      - In tests, you can override by clearing the cache: get_settings.cache_clear()
    """
    return Settings()

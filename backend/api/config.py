"""V1 API configuration (Postgres + Redis)."""

from __future__ import annotations

from functools import lru_cache

from pydantic import field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


def _normalize_database_url(url: str) -> str:
    """Railway/Heroku often set postgres:// — SQLAlchemy needs a driver."""
    if url.startswith("postgres://"):
        return url.replace("postgres://", "postgresql+psycopg2://", 1)
    if url.startswith("postgresql://") and "+psycopg2" not in url:
        return url.replace("postgresql://", "postgresql+psycopg2://", 1)
    return url


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    database_url: str = "postgresql+psycopg2://soapboxx:soapboxx@127.0.0.1:5432/soapboxx_v1"
    redis_url: str = "redis://127.0.0.1:6379/0"

    # pydantic-settings: DATABASE_URL, REDIS_URL env vars
    api_host: str = "127.0.0.1"
    api_port: int = 8000

    # Comma-separated origins for Lovable / local dev (SOAPBOXX_CORS_ORIGINS)
    cors_origins: str = (
        "https://soapboxx.lovable.app,"
        "http://localhost:5173,"
        "http://127.0.0.1:5173"
    )
    auto_process_on_ingest: bool = True
    # Celery beat: drain episodes missing translation (0 = disabled)
    pipeline_drain_minutes: int = 5
    pipeline_batch_size: int = 2
    # After RSS sync / cron — also drain backlog (sync if no worker)
    pipeline_sync_batch_size: int = 5
    # Layer 2 downloads full audio — keep off on Railway HTTP unless a worker runs it
    auto_audio_motion_on_process: bool = False
    # On API boot (Railway): dispatch N pending episodes to Celery (0 = off)
    pipeline_boot_dispatch_limit: int = 0
    rss_sync_minutes: int = 180

    @field_validator("database_url", mode="before")
    @classmethod
    def _db_url(cls, value: object) -> object:
        if isinstance(value, str):
            return _normalize_database_url(value)
        return value


@lru_cache
def get_settings() -> Settings:
    return Settings()

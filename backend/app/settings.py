from __future__ import annotations

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=None, extra="ignore")

    database_url: str = Field(default="", alias="DATABASE_URL")
    alembic_database_url: str = Field(default="", alias="ALEMBIC_DATABASE_URL")

    cors_origins: str = Field(default="", alias="CORS_ORIGINS")
    cors_origin_regex: str = Field(default="", alias="CORS_ORIGIN_REGEX")
    log_level: str = Field(default="info", alias="LOG_LEVEL")

    promo_limits_enabled: bool = Field(default=True, alias="PROMO_LIMITS_ENABLED")

    telegram_bot_token: str = Field(default="", alias="TELEGRAM_BOT_TOKEN")

    outbox_batch_size: int = Field(default=10, alias="OUTBOX_BATCH_SIZE")
    outbox_poll_interval_seconds: float = Field(default=2.0, alias="OUTBOX_POLL_INTERVAL_SECONDS")
    outbox_processing_timeout_seconds: float = Field(
        default=300.0, alias="OUTBOX_PROCESSING_TIMEOUT_SECONDS"
    )


def get_settings() -> Settings:
    s = Settings()
    if not s.database_url:
        raise RuntimeError("DATABASE_URL is required")
    if not s.alembic_database_url:
        raise RuntimeError("ALEMBIC_DATABASE_URL is required")
    return s

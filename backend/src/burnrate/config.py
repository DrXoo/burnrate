from __future__ import annotations

from functools import lru_cache

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    app_env: str = Field(default="development", alias="APP_ENV")
    app_host: str = Field(default="0.0.0.0", alias="APP_HOST")
    app_port: int = Field(default=8000, alias="APP_PORT")
    app_cors_origins: str = Field(default="http://localhost:3000", alias="APP_CORS_ORIGINS")
    database_url: str = Field(
        default="postgresql+psycopg://burnrate:burnrate@postgres:5432/burnrate",
        alias="DATABASE_URL",
    )
    enable_banking_app_id: str = Field(default="replace-me", alias="ENABLE_BANKING_APP_ID")
    enable_banking_private_key: str = Field(default="replace-me", alias="ENABLE_BANKING_PRIVATE_KEY")
    enable_banking_redirect_url: str = Field(
        default="http://localhost:8000/api/v1/integrations/enable-banking/callback",
        alias="ENABLE_BANKING_REDIRECT_URL",
    )
    enable_banking_environment: str = Field(default="production", alias="ENABLE_BANKING_ENVIRONMENT")
    sync_cron: str = Field(default="*/30 * * * *", alias="SYNC_CRON")

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    @property
    def cors_origins(self) -> list[str]:
        return [origin.strip() for origin in self.app_cors_origins.split(",") if origin.strip()]


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    return Settings()


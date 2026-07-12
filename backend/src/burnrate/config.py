from __future__ import annotations

from functools import lru_cache
from pathlib import Path

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    app_env: str = Field(default="development", alias="APP_ENV")
    log_level: str = Field(default="INFO", alias="LOG_LEVEL")
    app_host: str = Field(default="0.0.0.0", alias="APP_HOST")
    app_port: int = Field(default=8000, alias="APP_PORT")
    app_cors_origins: str = Field(default="http://localhost:3000", alias="APP_CORS_ORIGINS")
    app_web_base_url: str = Field(default="http://localhost:3000", alias="WEB_BASE_URL")
    database_url: str = Field(
        default="postgresql+psycopg://burnrate:burnrate@postgres:5432/burnrate",
        alias="DATABASE_URL",
    )
    enable_banking_app_id: str = Field(default="replace-me", alias="ENABLE_BANKING_APP_ID")
    enable_banking_private_key: str = Field(default="replace-me", alias="ENABLE_BANKING_PRIVATE_KEY")
    enable_banking_private_key_path: str | None = Field(
        default=None,
        alias="ENABLE_BANKING_PRIVATE_KEY_PATH",
    )
    enable_banking_redirect_url: str = Field(
        default="http://localhost:8000/api/v1/integrations/enable-banking/callback",
        alias="ENABLE_BANKING_REDIRECT_URL",
    )
    enable_banking_environment: str = Field(default="production", alias="ENABLE_BANKING_ENVIRONMENT")
    enable_banking_api_base_url: str = Field(
        default="https://api.enablebanking.com",
        alias="ENABLE_BANKING_API_BASE_URL",
    )
    enable_banking_timeout_seconds: float = Field(
        default=30.0,
        alias="ENABLE_BANKING_TIMEOUT_SECONDS",
    )
    enable_banking_max_retries: int = Field(
        default=3,
        ge=0,
        alias="ENABLE_BANKING_MAX_RETRIES",
    )
    enable_banking_retry_backoff_seconds: float = Field(
        default=0.5,
        ge=0.0,
        alias="ENABLE_BANKING_RETRY_BACKOFF_SECONDS",
    )
    auth_password_hash: str = Field(default="", alias="AUTH_PASSWORD_HASH")
    auth_secret_key: str = Field(default="", alias="AUTH_SECRET_KEY")
    auth_cookie_name: str = Field(default="burnrate_session", alias="AUTH_COOKIE_NAME")
    auth_session_max_age_seconds: int = Field(default=7 * 24 * 3600, ge=60, alias="AUTH_SESSION_MAX_AGE")
    auth_cookie_secure: bool = Field(default=True, alias="AUTH_COOKIE_SECURE")
    auth_login_max_attempts: int = Field(default=5, ge=1, alias="AUTH_LOGIN_MAX_ATTEMPTS")
    auth_login_lockout_seconds: int = Field(default=300, ge=0, alias="AUTH_LOGIN_LOCKOUT_SECONDS")
    bank_rate_limit_max_requests: int = Field(default=20, ge=1, alias="BANK_RATE_LIMIT_MAX_REQUESTS")
    bank_rate_limit_window_seconds: int = Field(default=60, ge=1, alias="BANK_RATE_LIMIT_WINDOW_SECONDS")
    bank_token_encryption_key: str = Field(default="", alias="BANK_TOKEN_ENCRYPTION_KEY")
    sync_cron: str = Field(default="*/30 * * * *", alias="SYNC_CRON")
    telegram_bot_token: str = Field(default="", alias="TELEGRAM_BOT_TOKEN")
    telegram_allowed_chat_ids: str = Field(default="", alias="TELEGRAM_ALLOWED_CHAT_IDS")
    telegram_api_base_url: str = Field(default="https://api.telegram.org", alias="TELEGRAM_API_BASE_URL")
    telegram_poll_timeout_seconds: int = Field(default=30, ge=0, alias="TELEGRAM_POLL_TIMEOUT_SECONDS")
    telegram_notify_on_sync: bool = Field(default=True, alias="TELEGRAM_NOTIFY_ON_SYNC")
    connection_expiry_warning_days: int = Field(default=7, ge=0, alias="CONNECTION_EXPIRY_WARNING_DAYS")

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    @property
    def auth_configured(self) -> bool:
        return bool(self.auth_password_hash) and bool(self.auth_secret_key)

    @property
    def is_development(self) -> bool:
        return self.app_env.strip().lower() == "development"

    @property
    def cors_origins(self) -> list[str]:
        return [origin.strip() for origin in self.app_cors_origins.split(",") if origin.strip()]

    @property
    def telegram_allowed_chat_id_set(self) -> set[int]:
        ids: set[int] = set()
        for raw in self.telegram_allowed_chat_ids.split(","):
            candidate = raw.strip()
            if candidate:
                ids.add(int(candidate))
        return ids

    @property
    def enable_banking_private_key_value(self) -> str:
        if self.enable_banking_private_key_path:
            return Path(self.enable_banking_private_key_path).read_text(encoding="utf-8")
        return self.enable_banking_private_key


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    return Settings()

"""
Application configuration loaded from environment variables.
Uses pydantic-settings for type-safe, validated config with .env support.
"""

import logging
import sys

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Central configuration. Values are read from environment variables or .env file."""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    # -- Server --
    APP_HOST: str = "0.0.0.0"
    APP_PORT: int = 8000
    DEBUG: bool = False
    APP_BASE_URL: str = "http://localhost:8000"

    # -- Logging --
    LOG_LEVEL: str = "INFO"
    SQL_ECHO: bool = False   # set True to see full SQL statements (very verbose)

    # -- Database --
    DATABASE_URL: str = "postgresql+asyncpg://postgres:postgres@localhost:5432/mehfilcart"

    # -- Redis --
    REDIS_URL: str = "redis://localhost:6379/0"

    # -- JWT --
    JWT_SECRET_KEY: str = "dev-secret-key-change-in-production"
    JWT_ALGORITHM: str = "HS256"
    JWT_ACCESS_TOKEN_EXPIRY_MINUTES: int = 30
    JWT_REFRESH_TOKEN_EXPIRY_DAYS: int = 7

    # -- OTP --
    # "console" for dev (prints to log), "msg91" or "twilio" for prod
    OTP_PROVIDER: str = "console"
    OTP_API_KEY: str = ""
    OTP_EXPIRY_SECONDS: int = 300
    OTP_MAX_ATTEMPTS: int = 3
    OTP_RATE_LIMIT_WINDOW_MINUTES: int = 15
    OTP_RATE_LIMIT_MAX: int = 3
    OTP_LENGTH: int = 6

    # -- Session Defaults --
    DEFAULT_SESSION_TIMEOUT_MINUTES: int = 45
    DEFAULT_MAX_GUESTS_PER_SESSION: int = 8
    SESSION_REOPEN_WINDOW_MINUTES: int = 15
    IDLE_TIMEOUT_MINUTES: int = 15

    # -- CORS --
    # Must be explicit origins (not "*") because the API sends credentials
    # (cookies / Authorization headers). Browsers reject "*" with credentials.
    CORS_ALLOWED_ORIGINS: list[str] = [
        "http://localhost:3000",
        "http://127.0.0.1:3000",
    ]

    # -- Super Admin Seed --
    # Seeded on first startup if no super admin exists
    SUPER_ADMIN_PHONE: str = "+919829778167"

    # -- Geocoding / Maps --
    # Provider used for address search + reverse geocoding. Swappable without
    # touching call sites -- see app/services/geocoding/. Supported: "maptiler".
    GEOCODING_PROVIDER: str = "maptiler"
    # Server-side key for the geocoding provider. Kept on the backend so it is
    # never exposed to the browser; the frontend calls our /admin/geocode proxy.
    MAPTILER_API_KEY: str = ""


settings = Settings()


# ── Logging setup ──────────────────────────────────────────────
def _setup_logging() -> None:
    """Configure a concise, human-friendly log format for the whole app."""
    log_fmt = "[%(levelname)s] %(asctime)s (%(name)s): %(message)s"
    date_fmt = "%H:%M:%S"

    logging.basicConfig(
        level=getattr(logging, settings.LOG_LEVEL.upper(), logging.INFO),
        format=log_fmt,
        datefmt=date_fmt,
        stream=sys.stdout,
        force=True,
    )

    # Quiet noisy third-party loggers
    logging.getLogger("asyncpg").setLevel(logging.WARNING)
    logging.getLogger("uvicorn.access").setLevel(logging.WARNING)


_setup_logging()

# Backend-only settings, loaded from environment variables and the backend .env.
# Development defaults are placeholders; never expose these secrets as VITE_* variables.
from pathlib import Path

from pydantic import model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


# Resolve configuration relative to this file so it works regardless of the
# directory from which Uvicorn is started.
REPOSITORY_ROOT = Path(__file__).resolve().parents[3]


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=REPOSITORY_ROOT / ".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    APP_NAME: str = "Smart Peer Companion"
    APP_VERSION: str = "1.0.0"

    API_V1_PREFIX: str = "/api/v1"

    DEBUG: bool = True

    DATABASE_URL: str = (
        "postgresql://postgres:password@localhost:5432/spc"
    )

    SECRET_KEY: str = "CHANGE_ME"

    # Algorithm used to sign and validate access tokens
    JWT_ALGORITHM: str = "HS256"

    # Access tokens expire after 30 minutes
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 30

    # WebSocket tickets are intentionally short-lived and single-use.
    WEBSOCKET_TICKET_EXPIRE_SECONDS: int = 60

    REDIS_URL: str = "redis://localhost:6379/0"
    CELERY_BROKER_URL: str = "redis://localhost:6379/0"
    CELERY_RESULT_BACKEND: str = "redis://localhost:6379/1"

    # The Hetzner CPX server hosts the application stack. Model inference is
    # configured separately because this server does not provide a GPU.
    INFERENCE_API_URL: str = ""
    INFERENCE_API_KEY: str = ""

    @model_validator(mode="after")
    def reject_insecure_production_secret(self):
        """Prevent staging/production from using a known placeholder secret."""

        insecure_secrets = {
            "CHANGE_ME",
            "local-development-only-change-me",
            "replace_with_a_long_random_local_secret",
            "replace_with_at_least_32_random_bytes",
        }

        if not self.DEBUG and (
            self.SECRET_KEY in insecure_secrets
            or len(self.SECRET_KEY.encode("utf-8")) < 32
        ):
            raise ValueError(
                "SECRET_KEY must contain at least 32 bytes and must not use "
                "a placeholder value when DEBUG is false."
            )

        return self

settings = Settings()

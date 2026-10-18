"""Load backend-only configuration from environment variables and ``.env``.

Development defaults are placeholders. Private values from this module must
never be exposed through frontend ``VITE_*`` variables.
"""

from pathlib import Path

from pydantic import model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


# Resolve configuration relative to this file so it works regardless of the
# directory from which Uvicorn is started.
REPOSITORY_ROOT = Path(__file__).resolve().parents[3]


class Settings(BaseSettings):
    """Validated runtime configuration for the SPC backend."""

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
        "postgresql+psycopg://postgres:password@localhost:5432/spc"
    )

    SECRET_KEY: str = "CHANGE_ME"

    # Algorithm used to sign and validate access tokens
    JWT_ALGORITHM: str = "HS256"

    # Access tokens are deliberately short-lived. Active browser sessions use
    # the opaque refresh-session cookie below to obtain replacement tokens.
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 15

    # An authenticated browser session ends after this much inactivity even
    # when its cookie has not reached the absolute lifetime.
    SESSION_IDLE_TIMEOUT_MINUTES: int = 30

    # Bound the lifetime of a single login even when the user remains active.
    SESSION_ABSOLUTE_TIMEOUT_HOURS: int = 12

    # The cookie contains only a random opaque secret. Session state is held in
    # Redis and the cookie is never readable by browser JavaScript.
    REFRESH_SESSION_COOKIE_NAME: str = "spc_refresh_session"
    REFRESH_SESSION_COOKIE_SECURE: bool | None = None
    REFRESH_SESSION_COOKIE_SAMESITE: str = "lax"

    # WebSocket tickets are intentionally short-lived and single-use.
    WEBSOCKET_TICKET_EXPIRE_SECONDS: int = 60

    # Private location for original uploaded learning materials.
    NOTE_STORAGE_DIRECTORY: Path = REPOSITORY_ROOT / "storage" / "notes"

    # Current sprint accepts PDF files up to 10 MiB.
    MAX_NOTE_UPLOAD_SIZE_BYTES: int = 10 * 1024 * 1024

    # Personal questions are synchronous for the current demonstration.
    MAX_CHAT_QUESTION_LENGTH: int = 4000

    REDIS_URL: str = "redis://localhost:6379/0"
    CELERY_BROKER_URL: str = "redis://localhost:6379/0"
    CELERY_RESULT_BACKEND: str = "redis://localhost:6379/1"

    # The Hetzner CPX server hosts the application stack. Model inference is
    # configured separately because this server does not provide a GPU.
    INFERENCE_API_URL: str = ""
    INFERENCE_API_KEY: str = ""
    # Turn on only after the attachment-scoped PostgreSQL graph repository and
    # migration are deployed. Knowledge graphs are optional derived data and
    # must not prevent ordinary note processing.
    ENABLE_KNOWLEDGE_GRAPH_GENERATION: bool = False

    # PostgreSQL performs authorized HNSW cosine ranking by default. Set this
    # false only to use the legacy authorized-list and Python-ranking fallback.
    ENABLE_DATABASE_SEMANTIC_SEARCH: bool = True
    RAG_SEMANTIC_SEARCH_TOP_K: int = 5

    # A user is online when a presence heartbeat was received recently.
    # Presence heartbeats never extend the authentication idle session.
    PRESENCE_TTL_SECONDS: int = 90

    @model_validator(mode="after")
    def reject_insecure_production_secret(self) -> "Settings":
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

        if self.RAG_SEMANTIC_SEARCH_TOP_K <= 0:
            raise ValueError("RAG_SEMANTIC_SEARCH_TOP_K must be positive")

        if self.PRESENCE_TTL_SECONDS <= 0:
            raise ValueError("PRESENCE_TTL_SECONDS must be positive")

        if self.ACCESS_TOKEN_EXPIRE_MINUTES <= 0:
            raise ValueError("ACCESS_TOKEN_EXPIRE_MINUTES must be positive")

        if self.SESSION_IDLE_TIMEOUT_MINUTES <= 0:
            raise ValueError("SESSION_IDLE_TIMEOUT_MINUTES must be positive")

        if self.SESSION_ABSOLUTE_TIMEOUT_HOURS <= 0:
            raise ValueError("SESSION_ABSOLUTE_TIMEOUT_HOURS must be positive")

        if self.REFRESH_SESSION_COOKIE_SAMESITE not in {"lax", "strict"}:
            raise ValueError(
                "REFRESH_SESSION_COOKIE_SAMESITE must be 'lax' or 'strict'"
            )

        return self

    @property
    def refresh_cookie_secure(self) -> bool:
        """Use secure cookies by default outside local debug mode."""

        if self.REFRESH_SESSION_COOKIE_SECURE is not None:
            return self.REFRESH_SESSION_COOKIE_SECURE
        return not self.DEBUG

settings = Settings()

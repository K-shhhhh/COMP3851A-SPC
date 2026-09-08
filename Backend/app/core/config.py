# Backend-only settings, loaded from environment variables and the backend .env.
# Development defaults are placeholders; never expose these secrets as VITE_* variables.
from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    APP_NAME: str = "Smart Peer Companion"
    APP_VERSION: str = "1.0.0"

    API_V1_PREFIX: str = "/api/v1"

    DEBUG: bool = True

    DATABASE_URL: str = (
        "postgresql://postgres:password@localhost:5432/spc"
    )

    SECRET_KEY: str = "CHANGE_ME"

    ACCESS_TOKEN_EXPIRE_MINUTES: int = 30

    REDIS_URL: str = "redis://localhost:6379/0"
    CELERY_BROKER_URL: str = "redis://localhost:6379/0"
    CELERY_RESULT_BACKEND: str = "redis://localhost:6379/1"

    # The Hetzner CPX server hosts the application stack. Model inference is
    # configured separately because this server does not provide a GPU.
    INFERENCE_API_URL: str = ""
    INFERENCE_API_KEY: str = ""

    class Config:
        env_file = ".env"


settings = Settings()

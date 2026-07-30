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

    class Config:
        env_file = ".env"


settings = Settings()
from typing import List

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env", env_file_encoding="utf-8", extra="ignore"
    )

    ENVIRONMENT: str = "development"
    LOG_LEVEL: str = "info"

    DATABASE_URL: str = "postgresql://postgres:postgres@localhost:5432/patient_data"
    REDIS_URL: str = "redis://localhost:6379/0"

    SECRET_KEY: str = "change-me-in-production"
    JWT_ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 60

    OPENAI_API_KEY: str = ""

    CORS_ORIGINS: List[str] = ["http://localhost:5173"]

    DEFAULT_USER_EMAIL: str = "doctor@example.com"
    DEFAULT_USER_PASSWORD: str = "password123"


settings = Settings()

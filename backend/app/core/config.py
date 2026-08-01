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

    # --- Bóc tách bệnh án (OCR ảnh/PDF scan & đọc file digital) ---
    OPENAI_API_KEY: str = ""
    OPENAI_BASE_URL: str = "https://api.openai.com/v1"

    # "openai" dùng API thật, "stub" trả dữ liệu giả để chạy/dev không tốn tiền.
    # Khi team có model OCR riêng thì thêm provider mới vào extractor/factory.py.
    OCR_PROVIDER: str = "openai"
    OCR_MODEL: str = "gpt-4o"
    DOC_PARSER_PROVIDER: str = "openai"
    DOC_PARSER_MODEL: str = "gpt-4o-mini"

    EXTRACTION_MAX_PAGES: int = 10
    EXTRACTION_TIMEOUT_SECONDS: int = 180
    EXTRACTION_MAX_FILE_MB: int = 20
    # DPI khi render trang PDF thành ảnh cho vision model. Cao hơn thì đọc chữ
    # viết tay tốt hơn nhưng tốn token ảnh hơn.
    EXTRACTION_PDF_DPI: int = 200

    CORS_ORIGINS: List[str] = ["http://localhost:5173"]

    DEFAULT_USER_EMAIL: str = "doctor@example.com"
    DEFAULT_USER_PASSWORD: str = "password123"


settings = Settings()

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
    OCR_MODEL: str = "gpt-5.6-luna"
    DOC_PARSER_PROVIDER: str = "openai"
    DOC_PARSER_MODEL: str = "gpt-5.6-luna"
    # none | low | medium | high | xhigh — chỉ dòng model suy luận (GPT-5 trở lên)
    # nhận tham số này. Để trống khi dùng model cũ như gpt-4o.
    EXTRACTION_REASONING_EFFORT: str = "low"

    EXTRACTION_MAX_PAGES: int = 10
    # File nhiều phiếu của một người (tự tách theo mẫu): bộ quân nhân ~17 trang có
    # nội dung, thanh niên ~9. Vượt ngưỡng gần như chắc là file của nhiều người.
    EXTRACTION_BUNDLE_MAX_PAGES: int = 30
    # Số phiếu đọc song song khi tách file nhiều phiếu.
    EXTRACTION_CONCURRENCY: int = 4
    EXTRACTION_TIMEOUT_SECONDS: int = 180
    EXTRACTION_MAX_FILE_MB: int = 40
    # DPI khi render trang PDF thành ảnh cho vision model. Cao hơn thì đọc chữ
    # viết tay tốt hơn nhưng tốn token ảnh hơn.
    EXTRACTION_PDF_DPI: int = 200

    # --- Trợ lý dữ liệu (hỏi đáp bằng LLM + function calling) ---
    # Để trống thì dùng OCR_MODEL.
    ASSISTANT_MODEL: str = ""
    ASSISTANT_REASONING_EFFORT: str = "low"
    # Số lượt gọi LLM tối đa cho một câu hỏi (mỗi lượt có thể gọi nhiều công cụ).
    ASSISTANT_MAX_STEPS: int = 6
    # Số câu hỏi tối đa mỗi người dùng trong một phút.
    ASSISTANT_RATE_PER_MINUTE: int = 12

    CORS_ORIGINS: List[str] = ["http://localhost:5173"]

    ALLOW_PUBLIC_REGISTRATION: bool = False
    DEFAULT_USER_EMAIL: str = "doctor@example.com"
    DEFAULT_USER_PASSWORD: str = "password123"


settings = Settings()

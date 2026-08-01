"""Chọn bộ bóc tách theo cấu hình.

Thêm nhà cung cấp mới (ví dụ model OCR do team tự huấn luyện) = viết một lớp con
của ``ExamExtractor`` rồi khai báo thêm một nhánh ở đây.
"""

from __future__ import annotations

from app.core.config import settings
from app.modules.documents.extractor.base import ExamExtractor
from app.modules.documents.extractor.openai_extractor import OpenAIExamExtractor
from app.modules.documents.extractor.stub import StubExamExtractor

# Hai chế độ trên giao diện.
MODE_OCR = "ocr"  # ảnh chụp / PDF scan
MODE_UPLOAD = "upload"  # docx / PDF có sẵn lớp văn bản

MODES = (MODE_OCR, MODE_UPLOAD)


def resolve_provider(mode: str) -> str:
    provider = settings.OCR_PROVIDER if mode == MODE_OCR else settings.DOC_PARSER_PROVIDER
    provider = (provider or "").strip().lower()
    # Không có key mà lỡ để "openai" thì tự lùi về stub, tránh dựng cả luồng lên
    # rồi mới báo lỗi ở bước cuối.
    if provider == "openai" and not settings.OPENAI_API_KEY:
        return "stub"
    return provider or "stub"


def get_extractor(mode: str, *, vision: bool) -> ExamExtractor:
    """``vision`` bám theo nội dung file thật, không bám theo nút người dùng bấm."""
    provider = resolve_provider(mode)
    if provider == "stub":
        return StubExamExtractor()
    if provider == "openai":
        return OpenAIExamExtractor(vision=vision)
    raise ValueError(f"Chưa hỗ trợ nhà cung cấp “{provider}”.")

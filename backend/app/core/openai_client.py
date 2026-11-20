"""Client OpenAI dùng chung cho các luồng bóc tách (phiếu khám, phiếu khảo sát)."""

from __future__ import annotations

from typing import Any

from app.core.config import settings


def openai_client():
    """Tạo client theo cấu hình hiện tại.

    Import muộn để môi trường chỉ chạy stub (test, dev không có key) không cần
    nạp thư viện ``openai``.
    """
    if not settings.OPENAI_API_KEY:
        raise RuntimeError(
            "Chưa cấu hình OPENAI_API_KEY. Đặt biến này trong .env, hoặc chuyển "
            "OCR_PROVIDER/DOC_PARSER_PROVIDER sang 'stub' để chạy thử."
        )
    from openai import OpenAI

    return OpenAI(
        api_key=settings.OPENAI_API_KEY,
        base_url=settings.OPENAI_BASE_URL or None,
        timeout=settings.EXTRACTION_TIMEOUT_SECONDS,
        max_retries=2,
    )


def reasoning_options() -> dict[str, Any]:
    """Tham số suy luận cho ``chat.completions.create``.

    Dòng GPT-5 trở lên không nhận ``temperature`` khác mặc định nhưng nhận
    ``reasoning_effort``; model cũ (gpt-4o) thì ngược lại. Vì vậy không bao giờ
    gửi ``temperature`` và chỉ gửi ``reasoning_effort`` khi đã cấu hình.
    """
    effort = settings.EXTRACTION_REASONING_EFFORT.strip().lower()
    return {"reasoning_effort": effort} if effort else {}

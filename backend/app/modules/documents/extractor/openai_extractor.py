"""Bóc tách bằng OpenAI — dùng chung cho cả ảnh (vision) và văn bản.

Chỉ khác nhau ở cách đóng gói nội dung gửi đi; prompt, ràng buộc và hậu xử lý
là một. Model được ép trả JSON qua ``response_format={"type": "json_object"}``
thay vì JSON Schema strict, vì bệnh án có hơn 130 trường — vượt giới hạn của
structured output, và strict mode bắt model phải xuất mọi trường kể cả trường
không có trên giấy, dễ dẫn tới bịa dữ liệu. Ràng buộc thật nằm ở
``schema_spec.coerce_extraction``, nơi mọi giá trị lạ bị loại bỏ.
"""

from __future__ import annotations

import json
import logging

from app.core.config import settings
from app.modules.documents.extractor.base import (
    SYSTEM_PROMPT,
    ExamExtractor,
    ExtractionOutcome,
    build_user_prompt,
)
from app.modules.documents.extractor.file_reader import DocumentContent
from app.modules.documents.extractor.schema_spec import FieldSpec, render_spec_for_prompt

logger = logging.getLogger(__name__)

# Text quá dài thì cắt bớt — bệnh án đầy đủ chỉ khoảng 6-8 nghìn ký tự.
MAX_TEXT_CHARS = 60_000


class OpenAIExamExtractor(ExamExtractor):
    def __init__(self, model: str | None = None, *, vision: bool):
        self.vision = vision
        self.model = model or (settings.OCR_MODEL if vision else settings.DOC_PARSER_MODEL)

    def _client(self):
        from openai import OpenAI

        if not settings.OPENAI_API_KEY:
            raise RuntimeError(
                "Chưa cấu hình OPENAI_API_KEY. Đặt biến này trong .env, hoặc chuyển "
                "OCR_PROVIDER/DOC_PARSER_PROVIDER sang 'stub' để chạy thử."
            )
        return OpenAI(
            api_key=settings.OPENAI_API_KEY,
            base_url=settings.OPENAI_BASE_URL or None,
            timeout=settings.EXTRACTION_TIMEOUT_SECONDS,
        )

    def extract(
        self, content: DocumentContent, specs: list[FieldSpec], disease_label: str
    ) -> ExtractionOutcome:
        spec_text = render_spec_for_prompt(specs)
        document_text = content.text[:MAX_TEXT_CHARS] if content.kind == "text" else None
        user_prompt = build_user_prompt(disease_label, spec_text, document_text)

        parts: list[dict] = [{"type": "text", "text": user_prompt}]
        for image in content.images:
            parts.append(
                {
                    "type": "image_url",
                    "image_url": {
                        "url": f"data:image/png;base64,{image}",
                        "detail": "high",  # chữ viết tay cần độ phân giải cao
                    },
                }
            )

        response = self._client().chat.completions.create(
            model=self.model,
            messages=[
                {"role": "system", "content": SYSTEM_PROMPT},
                {"role": "user", "content": parts},
            ],
            response_format={"type": "json_object"},
            temperature=0,
        )

        raw_text = response.choices[0].message.content or "{}"
        try:
            raw_result = json.loads(raw_text)
        except json.JSONDecodeError:
            logger.warning("Model trả về JSON không hợp lệ: %s", raw_text[:500])
            raw_result = {}

        usage = {}
        if response.usage:
            usage = {
                "prompt_tokens": response.usage.prompt_tokens,
                "completion_tokens": response.usage.completion_tokens,
                "total_tokens": response.usage.total_tokens,
            }

        return ExtractionOutcome(
            raw_result=raw_result if isinstance(raw_result, dict) else {},
            provider="openai",
            model=self.model,
            usage=usage,
        )

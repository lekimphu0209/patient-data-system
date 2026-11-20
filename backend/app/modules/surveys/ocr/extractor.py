"""Gọi model thị giác đọc phiếu khảo sát.

``OpenAISurveyExtractor`` dùng structured output (JSON schema strict) để model chỉ
trả về phương án có trong biểu mẫu. ``StubSurveyExtractor`` trả kết quả cố định,
không gọi ra ngoài — dùng cho test và khi chưa cấu hình API key.
"""

from __future__ import annotations

import base64
import json
import logging
from dataclasses import dataclass, field
from typing import Any, Protocol

from app.core.config import settings
from app.core.openai_client import openai_client, reasoning_options
from app.modules.documents.extractor.factory import MODE_OCR, resolve_provider
from app.modules.surveys.ocr.pages import PageSet
from app.modules.surveys.ocr.schema import SUBJECT_FIELDS, SYSTEM_PROMPT, form_prompt, response_schema

logger = logging.getLogger(__name__)

# Lớp văn bản PDF chỉ là gợi ý; cắt bớt để không lấn át phần ảnh.
MAX_TEXT_LAYER = 20_000
MAX_OUTPUT_TOKENS = 16_000


class ModelResponseError(RuntimeError):
    """Model không trả về kết quả dùng được (bị cắt, từ chối, JSON hỏng)."""


@dataclass
class ModelOutput:
    raw: dict[str, Any]
    provider: str
    model: str
    usage: dict[str, Any] = field(default_factory=dict)


class SurveyExtractor(Protocol):
    def extract(self, form: dict[str, Any], pages: PageSet) -> ModelOutput: ...


class OpenAISurveyExtractor:
    def __init__(self, model: str | None = None):
        self.model = model or settings.OCR_MODEL

    def _content(self, form: dict[str, Any], pages: PageSet) -> list[dict[str, Any]]:
        parts: list[dict[str, Any]] = [{"type": "text", "text": form_prompt(form)}]
        for page in pages.pages:
            parts.append({"type": "text", "text": f"Ảnh trang {page.number}:"})
            encoded = base64.b64encode(page.jpeg).decode("ascii")
            parts.append({
                "type": "image_url",
                # Dấu chọn trên phiếu rất nhỏ — bắt buộc độ phân giải cao.
                "image_url": {"url": f"data:image/jpeg;base64,{encoded}", "detail": "high"},
            })
        text_layer = pages.text_layer
        if text_layer:
            parts.append({
                "type": "text",
                "text": "Lớp văn bản có sẵn trong file PDF — chỉ dùng để đọc chính xác chữ in/chữ gõ; "
                "dấu chọn và chữ viết tay phải xác định từ ảnh:\n" + text_layer[:MAX_TEXT_LAYER],
            })
        return parts

    def extract(self, form: dict[str, Any], pages: PageSet) -> ModelOutput:
        response = openai_client().chat.completions.create(
            model=self.model,
            messages=[
                {"role": "system", "content": SYSTEM_PROMPT},
                {"role": "user", "content": self._content(form, pages)},
            ],
            response_format={
                "type": "json_schema",
                "json_schema": {"name": "survey_extraction", "strict": True, "schema": response_schema(form)},
            },
            max_completion_tokens=MAX_OUTPUT_TOKENS,
            **reasoning_options(),
        )
        choice = response.choices[0]
        if getattr(choice.message, "refusal", None):
            raise ModelResponseError(f"Model từ chối xử lý: {choice.message.refusal}")
        if choice.finish_reason == "length":
            raise ModelResponseError("Kết quả của model bị cắt giữa chừng.")
        try:
            raw = json.loads(choice.message.content or "")
        except json.JSONDecodeError as exc:
            logger.warning("Model trả JSON không hợp lệ: %s", (choice.message.content or "")[:500])
            raise ModelResponseError("Model trả về dữ liệu không đọc được.") from exc

        usage = response.usage.model_dump() if response.usage else {}
        return ModelOutput(raw=raw, provider="openai", model=response.model or self.model, usage=usage)


class StubSurveyExtractor:
    """Kết quả giả lập ổn định: chọn phương án đầu cho câu lẻ, bỏ trống câu chẵn."""

    def extract(self, form: dict[str, Any], pages: PageSet) -> ModelOutput:
        answers: dict[str, Any] = {}
        for index, question in enumerate(form["questions"]):
            options = question["options"]
            if index % 2:
                answers[question["id"]] = [] if question["multi"] else None
            elif not options:
                answers[question["id"]] = "Dữ liệu giả lập"
            else:
                answers[question["id"]] = [options[0]] if question["multi"] else options[0]
        subject = dict.fromkeys(SUBJECT_FIELDS)
        subject.update(code="STUB-001", full_name="Nguyễn Văn Giả Lập")
        return ModelOutput(
            raw={
                "form_check": {"is_expected_form": True, "observed_title": form["title"]},
                "subject": subject,
                "answers": answers,
                "uncertain": [],
                "notes": "Kết quả giả lập (stub) — không đọc nội dung file thật.",
            },
            provider="stub",
            model="stub",
        )


def get_survey_extractor() -> SurveyExtractor:
    provider = resolve_provider(MODE_OCR)
    if provider == "stub":
        return StubSurveyExtractor()
    if provider == "openai":
        return OpenAISurveyExtractor()
    raise ValueError(f"Chưa hỗ trợ nhà cung cấp “{provider}”.")

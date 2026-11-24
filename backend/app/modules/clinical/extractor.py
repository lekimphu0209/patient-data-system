"""Đọc ảnh/PDF bệnh án bằng model thị giác (structured output chặt theo biểu mẫu)."""

from __future__ import annotations

import base64
import json
from typing import Any, Protocol

from app.core.config import settings
from app.core.openai_client import openai_client, reasoning_options
from app.modules.surveys.ocr.extractor import ModelOutput, ModelResponseError
from app.modules.surveys.ocr.pages import PageSet

from .schema import EXTRA_IDENTITY, FIELDS, FORMS

MAX_OUTPUT_TOKENS = 16_000
MAX_TEXT_LAYER = 20_000

SYSTEM_PROMPT = """Bạn là trợ lý số hoá bệnh án nghiên cứu tâm thần của Bệnh viện Quân y 103.
Nhiệm vụ: đọc ảnh các trang bệnh án (in sẵn, điền tay hoặc đánh máy) và điền vào cấu trúc JSON đã cho.

Quy tắc:
- Chỉ điền trường đọc được rõ trên ảnh. Không đọc được, để trống hoặc không có thì trả null (danh sách: []).
- Ô đánh dấu/khoanh tròn: chỉ chọn các phương án được đánh dấu rõ. Dấu bị gạch xoá hoặc khoanh để huỷ thì bỏ.
- Trường lựa chọn: dùng đúng chữ của một phương án trong danh sách cho phép.
- Ngày: định dạng YYYY-MM-DD. Số: chỉ chữ số (dấu chấm thập phân nếu có).
- Chép nguyên văn phần chẩn đoán, kết luận đã viết trên bệnh án; TUYỆT ĐỐI không tự suy ra chẩn đoán từ triệu chứng.
- Chữ viết tay khó đọc hoặc không chắc: vẫn ghi cách đọc tốt nhất và đưa mã trường vào "uncertain".
- form_check.is_expected_form = false nếu tài liệu không phải bệnh án của loại bệnh được yêu cầu.
- notes: ghi ngắn gọn (tiếng Việt) những điểm cần cán bộ đối soát."""


def _nullable(schema: dict[str, Any]) -> dict[str, Any]:
    result = dict(schema)
    result["type"] = [schema["type"], "null"]
    if "enum" in result:
        result["enum"] = [*result["enum"], None]
    return result


def _field_schema(field: dict[str, Any]) -> dict[str, Any]:
    kind = field["kind"]
    if kind == "multi":
        return {"type": "array", "items": {"type": "string", "enum": field["options"]}, "description": field["label"]}
    if kind == "select":
        return _nullable({"type": "string", "enum": field["options"], "description": field["label"]})
    description = field["label"] + {"date": " (YYYY-MM-DD)", "number": " (chỉ số)"}.get(kind, "")
    return _nullable({"type": "string", "description": description})


def _object(properties: dict[str, Any]) -> dict[str, Any]:
    return {"type": "object", "additionalProperties": False, "required": list(properties), "properties": properties}


def response_schema(type_: str) -> dict[str, Any]:
    keys = [field["key"] for field in FIELDS[type_]]
    identity = {
        "code": _nullable({"type": "string", "description": "Mã bệnh nhân / mã nghiên cứu ghi trên bệnh án"}),
        "fullName": _nullable({"type": "string", "description": "Họ và tên bệnh nhân"}),
        "age": _nullable({"type": "string", "description": "Tuổi (chỉ số)"}),
        "sex": _nullable({"type": "string", "enum": ["Nam", "Nữ"]}),
        **{field["key"]: _field_schema(field) for field in EXTRA_IDENTITY},
    }
    return _object({
        "form_check": _object({"is_expected_form": {"type": "boolean"},
                               "observed_title": _nullable({"type": "string"})}),
        "patient": _object(identity),
        "visit_date": _nullable({"type": "string", "description": "Ngày khám (YYYY-MM-DD) nếu ghi trên bệnh án"}),
        "fields": _object({field["key"]: _field_schema(field) for field in FIELDS[type_]}),
        "uncertain": {"type": "array", "items": {"type": "string", "enum": [*keys, "code", "fullName", "age", "sex"]}},
        "notes": {"type": "string"},
    })


def form_prompt(type_: str) -> str:
    form = FORMS[type_]
    lines = [f"Loại bệnh án: {form['title']} ({type_}). Các phần của bệnh án:"]
    for section in form["sections"]:
        lines.append(f"- {section['title']}: " + "; ".join(field["label"] for field in section["fields"]))
    return "\n".join(lines)


class ClinicalExtractor(Protocol):
    def extract(self, type_: str, pages: PageSet) -> ModelOutput: ...


class OpenAIClinicalExtractor:
    def __init__(self, model: str | None = None):
        self.model = model or settings.OCR_MODEL

    def extract(self, type_: str, pages: PageSet) -> ModelOutput:
        content: list[dict[str, Any]] = [{"type": "text", "text": form_prompt(type_)}]
        for page in pages.pages:
            encoded = base64.b64encode(page.jpeg).decode("ascii")
            content.append({"type": "text", "text": f"Ảnh trang {page.number}:"})
            content.append({"type": "image_url",
                            "image_url": {"url": f"data:image/jpeg;base64,{encoded}", "detail": "high"}})
        if pages.text_layer:
            content.append({"type": "text", "text": "Lớp văn bản có sẵn trong PDF (chỉ để đọc chính xác chữ in/gõ):\n"
                            + pages.text_layer[:MAX_TEXT_LAYER]})
        response = openai_client().chat.completions.create(
            model=self.model,
            messages=[{"role": "system", "content": SYSTEM_PROMPT}, {"role": "user", "content": content}],
            response_format={"type": "json_schema", "json_schema": {
                "name": f"clinical_{type_.lower()}", "strict": True, "schema": response_schema(type_)}},
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
        except json.JSONDecodeError as error:
            raise ModelResponseError("Model trả về dữ liệu không đọc được.") from error
        usage = response.usage.model_dump() if response.usage else {}
        return ModelOutput(raw=raw, provider="openai", model=response.model or self.model, usage=usage)


class StubClinicalExtractor:
    """Kết quả giả lập ổn định — dùng khi chưa cấu hình khoá (dev/test), không gọi ra ngoài."""

    def extract(self, type_: str, pages: PageSet) -> ModelOutput:
        return ModelOutput(raw={
            "form_check": {"is_expected_form": True, "observed_title": FORMS[type_]["title"]},
            "patient": {"code": None, "fullName": "Bệnh nhân giả lập", "age": "30", "sex": "Nam"},
            "visit_date": None, "fields": {"diagnosis": "Kết quả giả lập (stub)"}, "uncertain": [],
            "notes": "Kết quả giả lập (stub) — không đọc nội dung file thật.",
        }, provider="stub", model="stub")


def get_clinical_extractor() -> ClinicalExtractor:
    from app.modules.documents.extractor.factory import MODE_OCR, resolve_provider

    provider = resolve_provider(MODE_OCR)
    if provider == "stub":
        return StubClinicalExtractor()
    return OpenAIClinicalExtractor()

"""Giao diện chung cho mọi bộ bóc tách bệnh án.

Thêm model OCR tự huấn luyện sau này = viết một lớp con ở đây rồi khai báo trong
``factory.py``; toàn bộ phần còn lại của hệ thống không phải sửa gì.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Any

from app.modules.documents.extractor.file_reader import DocumentContent
from app.modules.documents.extractor.schema_spec import FieldSpec


@dataclass
class ExtractionOutcome:
    """Kết quả thô của model, trước khi kiểm và ép kiểu."""

    raw_result: dict[str, Any]
    provider: str
    model: str
    usage: dict[str, Any] = field(default_factory=dict)


class ExamExtractor(ABC):
    """Đọc nội dung một phiếu khám và trả về giá trị theo đường dẫn của schema."""

    @abstractmethod
    def extract(
        self, content: DocumentContent, specs: list[FieldSpec], disease_label: str
    ) -> ExtractionOutcome:
        raise NotImplementedError


SYSTEM_PROMPT = """\
Bạn là trợ lý số hoá bệnh án nghiên cứu của bệnh viện, đọc phiếu khám bệnh tiếng Việt.

Nhiệm vụ: đọc tài liệu được cung cấp và trích xuất dữ liệu của PHẦN 3 (KHÁM BỆNH)
đến PHẦN 7 (ĐIỀU TRỊ). BỎ QUA phần 1 (thủ tục hành chính) và phần 2 (hỏi bệnh) —
những phần đó đã có sẵn trong hệ thống.

Quy tắc bắt buộc:
1. Trả về DUY NHẤT một object JSON. Khoá là đường dẫn trong bảng đặc tả bên dưới
   (giữ nguyên dấu chấm), giá trị là dữ liệu đọc được.
2. CHỈ đưa vào những trường thực sự đọc được trên tài liệu. Trường nào không có,
   không nhìn rõ, hoặc bỏ trống thì BỎ HẲN khỏi JSON — tuyệt đối không đoán,
   không bịa, không điền giá trị mặc định.
3. Với trường "chọn 1" hoặc "chọn nhiều": trả về đúng phần MÃ nằm bên trái dấu "="
   (ví dụ trả `limited`, không phải `Hợp tác hạn chế`). "chọn nhiều" trả mảng.
4. Với các bảng triệu chứng có cột Có/Không: chỉ ghi nhận dòng nào được đánh dấu
   rõ ràng, trả `yes` hoặc `no` tương ứng. Dòng để trống thì bỏ qua.
5. Với trường số: trả về số thuần, không kèm đơn vị.
6. Với trường ngày: định dạng YYYY-MM-DD.
7. Giữ nguyên tiếng Việt có dấu cho các trường chữ.

Ô đánh dấu có thể xuất hiện dưới nhiều dạng: ☑, ☒, [x], khoanh tròn, gạch chân,
tô đậm, hoặc viết tay. Ô trống là ☐, [ ], hoặc để trắng.
"""


def build_user_prompt(disease_label: str, spec_text: str, document_text: str | None) -> str:
    parts = [
        f"Bệnh nhân thuộc nhóm: {disease_label}.",
        "",
        "BẢNG ĐẶC TẢ TRƯỜNG (định dạng: đường_dẫn | nhãn | kiểu):",
        spec_text,
        "",
    ]
    if document_text:
        parts += [
            "NỘI DUNG TÀI LIỆU:",
            "-----",
            document_text,
            "-----",
            "",
        ]
    else:
        parts.append("Tài liệu được gửi kèm dưới dạng ảnh các trang.\n")
    parts.append("Trả về JSON theo đúng quy tắc đã nêu.")
    return "\n".join(parts)

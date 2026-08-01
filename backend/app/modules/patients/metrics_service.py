"""Chuỗi số liệu theo thời gian của một bệnh nhân, phục vụ biểu đồ diễn biến.

Danh sách chỉ số suy ra từ chính ``form_schema.json`` — mọi node ``type: "number"``
trong khối KHÁM BỆNH — nên thêm/bớt mục trong template là biểu đồ tự có/mất chỉ
số tương ứng, không nơi nào hard-code tên field.

Vì sao cần endpoint riêng thay vì để client tự lọc từ danh sách lần khám: một
bản ghi lần khám nặng khoảng 5,5 KB JSON (gần như toàn bộ là chữ — chẩn đoán,
điều trị, khám tâm thần...) trong khi phần thật sự dùng để vẽ chưa tới 0,3 KB.
Trả sẵn chuỗi số giảm khoảng 10–20 lần dữ liệu truyền và gộp nhiều lượt gọi
phân trang thành một.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from datetime import date
from typing import Any, Iterable

from sqlalchemy.orm import Session

from app.modules.patients.form_service import FormService
from app.modules.patients.repository import ExaminationRepository, PatientRepository
from app.shared.exceptions import NotFoundException

EXAMINATION_BLOCK = "examination"

# Trần an toàn cho hồ sơ bất thường: chuỗi số trả về thì nhẹ, nhưng đọc bản ghi
# lên bộ nhớ vẫn tốn. Hồ sơ thực tế chỉ vài chục lần khám nên trần này không
# bao giờ chạm tới; nếu chạm thì cắt phần cũ nhất và báo bằng cờ ``truncated``.
MAX_EXAMS = 1000

# Nhãn trong template có đánh số ("3.1. Toàn thân", "PHẦN 4. CẬN LÂM SÀNG CHUNG").
# Số thứ tự hữu ích trong bệnh án giấy nhưng chỉ làm nhiễu tiêu đề biểu đồ.
_ORDINAL_PREFIX = re.compile(r"^(phần\s+)?\d+(\.\d+)*\.?\s*", re.IGNORECASE)

# Chuỗi chỉ được nhận khi nguyên vẹn là một con số. Cố tình *không* bóc số ra
# khỏi câu chữ: "120/80" hay "sốt 39 độ" mà lấy bừa con số đầu tiên thì biểu đồ sai.
_NUMERIC_TEXT = re.compile(r"^-?\d+(?:[.,]\d+)?$")


def pretty_label(raw: str | None) -> str:
    stripped = _ORDINAL_PREFIX.sub("", (raw or "").strip()).strip()
    return stripped or (raw or "").strip()


def pretty_group_label(raw: str | None) -> str:
    """Nhãn nhóm còn phải hạ chữ in hoa.

    "PHẦN 7. ĐIỀU TRỊ" đứng cạnh "Toàn thân" trong cùng một hàng chip nhìn rất
    lệch. Chỉ hạ khi nhãn có nhiều từ — nhãn một từ viết hoa thường là từ viết
    tắt (SGOT, EEG) và phải giữ nguyên.
    """
    stripped = pretty_label(raw)
    if stripped != stripped.upper() or " " not in stripped:
        return stripped
    lowered = stripped.lower()
    return lowered[:1].upper() + lowered[1:]


def parse_numeric(value: Any) -> int | float | None:
    """Chỉ nhận giá trị thật sự là số; chuỗi số do OCR trả về vẫn được chấp nhận."""
    # bool là lớp con của int trong Python — "có/không" không phải chỉ số.
    if isinstance(value, bool):
        return None
    if isinstance(value, (int, float)):
        return value
    if isinstance(value, str):
        text = value.strip()
        if not _NUMERIC_TEXT.match(text):
            return None
        text = text.replace(",", ".")
        return float(text) if "." in text else int(text)
    return None


def _value_at_path(data: Any, path: tuple[str, ...]) -> Any:
    current = data
    for segment in path:
        if not isinstance(current, dict):
            return None
        current = current.get(segment)
    return current


@dataclass(frozen=True)
class NumericField:
    path: tuple[str, ...]
    key: str
    label: str
    unit: str | None
    group_key: str
    group_label: str


def collect_numeric_fields(block: dict[str, Any] | None) -> list[NumericField]:
    """Mọi field ``number`` trong một khối, kèm nhóm gần nhất chứa nó."""
    if not block:
        return []

    fields: list[NumericField] = []

    def walk(node: dict[str, Any], path: tuple[str, ...], group: tuple[str, str]) -> None:
        for child in node.get("children") or []:
            child_path = path + (child["id"],)

            if child.get("type") == "number":
                fields.append(
                    NumericField(
                        path=child_path,
                        key=".".join(child_path),
                        label=pretty_label(child.get("label")),
                        unit=child.get("unit"),
                        group_key=group[0],
                        group_label=group[1],
                    )
                )
            elif child.get("type") in ("group", "block"):
                walk(
                    child,
                    child_path,
                    (".".join(child_path), pretty_group_label(child.get("label"))),
                )

    walk(block, (), (block["id"], pretty_group_label(block.get("label"))))
    return fields


class ExaminationMetricsService:
    """Dựng chuỗi số liệu của các chỉ số dạng số theo trục thời gian khám."""

    def __init__(self, db: Session):
        self.repo = ExaminationRepository(db)
        self.patient_repo = PatientRepository(db)
        self.form_service = FormService()

    def build_series(self, patient_id: int) -> dict[str, Any]:
        patient = self.patient_repo.get_by_id(patient_id)
        if not patient:
            raise NotFoundException("Patient not found")

        disease_code = self.form_service.resolve_disease_code(
            patient.diagnosis, patient.disease_type
        )
        block = self.form_service.get_block(disease_code, EXAMINATION_BLOCK)
        fields = collect_numeric_fields(block)

        exam_count = self.repo.count_by_patient(patient_id)
        rows = self.repo.get_metric_rows_by_patient(patient_id, limit=MAX_EXAMS)

        return {
            "exam_count": exam_count,
            "truncated": exam_count > len(rows),
            "series": _build(fields, rows),
        }


def _build(
    fields: Iterable[NumericField],
    rows: Iterable[tuple[int, date, dict[str, Any] | None]],
) -> list[dict[str, Any]]:
    """Chỉ số nào bệnh nhân chưa từng được ghi giá trị thì không trả về series."""
    rows = list(rows)
    series: list[dict[str, Any]] = []

    for field in fields:
        points = []
        for exam_id, exam_date, data in rows:
            value = parse_numeric(_value_at_path(data, field.path))
            if value is not None:
                points.append({"exam_id": exam_id, "date": exam_date, "value": value})

        if points:
            series.append(
                {
                    "key": field.key,
                    "label": field.label,
                    "unit": field.unit,
                    "group_key": field.group_key,
                    "group_label": field.group_label,
                    "points": points,
                }
            )

    return series

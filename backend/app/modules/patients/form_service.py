"""Form schema service.

Nguồn sự thật duy nhất cho cấu trúc bệnh án là ``form_schema.json`` — file này mô
tả đầy đủ 3 khối (hành chính, hỏi bệnh, khám bệnh) theo template F20/F32, kèm
kiểu nhập liệu (text/number/date/radio/checkbox_group/matrix) và điều kiện hiển
thị theo loại bệnh.

Service chịu trách nhiệm:
- nạp schema,
- lọc theo mã bệnh (``f20`` / ``f32`` / ``normal``),
- suy ra mã bệnh từ bản ghi bệnh nhân.
"""

import json
from functools import lru_cache
from pathlib import Path
from typing import Any

SCHEMA_PATH = Path(__file__).parent / "form_schema.json"

DEFAULT_DISEASE = "normal"


@lru_cache(maxsize=1)
def _load_raw_schema() -> dict[str, Any]:
    with SCHEMA_PATH.open("r", encoding="utf-8") as fh:
        return json.load(fh)


def _applies(node: dict[str, Any], disease_code: str) -> bool:
    """Node không khai báo ``applies_to`` thì áp dụng cho mọi loại bệnh."""
    applies_to = node.get("applies_to")
    if not applies_to:
        return True
    return disease_code in applies_to


def _filter_node(node: dict[str, Any], disease_code: str) -> dict[str, Any] | None:
    if not _applies(node, disease_code):
        return None

    result = {k: v for k, v in node.items() if k not in ("children", "options", "applies_to")}

    if "options" in node:
        options = [opt for opt in node["options"] if _applies(opt, disease_code)]
        result["options"] = [
            {k: v for k, v in opt.items() if k != "applies_to"} for opt in options
        ]

    if "children" in node:
        children = []
        for child in node["children"]:
            filtered = _filter_node(child, disease_code)
            if filtered is not None:
                children.append(filtered)
        # Một group mà mọi con đều bị loại thì bản thân group cũng không còn ý nghĩa.
        if not children:
            return None
        result["children"] = children

    return result


class FormService:
    """Truy xuất schema bệnh án đã lọc theo loại bệnh."""

    def list_diseases(self) -> list[dict[str, Any]]:
        return _load_raw_schema().get("diseases", [])

    def resolve_disease_code(self, *values: str | None) -> str:
        """Suy ra mã bệnh (f20/f32/normal) từ chẩn đoán, loại bệnh... của bệnh nhân."""
        haystack = " ".join(v for v in values if v).lower()
        if not haystack.strip():
            return DEFAULT_DISEASE

        for disease in self.list_diseases():
            if disease["code"] == DEFAULT_DISEASE:
                continue
            for alias in disease.get("aliases", []):
                if alias.lower() in haystack:
                    return disease["code"]
        return DEFAULT_DISEASE

    def get_schema(self, disease_code: str) -> dict[str, Any]:
        """Toàn bộ schema (cả 3 khối) đã lọc theo loại bệnh."""
        raw = _load_raw_schema()
        blocks = []
        for block in raw.get("blocks", []):
            filtered = _filter_node(block, disease_code)
            if filtered is not None:
                blocks.append(filtered)

        disease = next(
            (d for d in raw.get("diseases", []) if d["code"] == disease_code), None
        )
        return {
            "version": raw.get("version"),
            "disease_code": disease_code,
            "disease_label": disease["label"] if disease else disease_code,
            "exam_table_columns": raw.get("exam_table_columns", []),
            "blocks": blocks,
        }

    def get_block(self, disease_code: str, block_id: str) -> dict[str, Any] | None:
        """Một khối cụ thể (``administrative`` / ``medical_history`` / ``examination``)."""
        for block in self.get_schema(disease_code)["blocks"]:
            if block["id"] == block_id:
                return block
        return None

    def is_valid_disease(self, disease_code: str) -> bool:
        return any(d["code"] == disease_code for d in self.list_diseases())

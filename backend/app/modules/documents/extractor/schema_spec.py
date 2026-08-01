"""Cầu nối giữa `form_schema.json` và model bóc tách.

Hai chiều:

- **Đi ra**: biến khối "KHÁM BỆNH" thành một bản đặc tả phẳng (đường dẫn có dấu
  chấm + nhãn tiếng Việt + kiểu + danh sách lựa chọn) để nhét vào prompt.
- **Đi vào**: nhận JSON model trả về, kiểm tra và ép về đúng kiểu, rồi dựng lại
  cấu trúc lồng đúng như form.

Không phụ thuộc nhà cung cấp nào: thay OpenAI bằng model tự huấn luyện sau này
vẫn dùng lại nguyên hai chiều này.
"""

from __future__ import annotations

import re
import unicodedata
from dataclasses import dataclass, field
from datetime import date
from typing import Any

# Kiểu trường sau khi rút gọn cho model đọc.
KIND_TEXT = "text"
KIND_NUMBER = "number"
KIND_DATE = "date"
KIND_ONE_OF = "one_of"
KIND_MANY_OF = "many_of"


@dataclass
class FieldSpec:
    path: str
    label: str
    kind: str
    section: str
    unit: str | None = None
    options: list[tuple[str, str]] = field(default_factory=list)

    @property
    def option_values(self) -> list[str]:
        return [value for value, _ in self.options]


# ==================== Đi ra: schema -> đặc tả cho prompt ====================


def build_field_specs(block: dict[str, Any]) -> list[FieldSpec]:
    """Duyệt khối examination, trả về danh sách trường phẳng theo đường dẫn."""
    specs: list[FieldSpec] = []

    def walk(node: dict[str, Any], path: list[str], labels: list[str]) -> None:
        node_type = node.get("type")
        node_path = [*path, node["id"]]
        node_labels = [*labels, node["label"]]

        if node_type in ("group", "block"):
            for child in node.get("children", []):
                walk(child, node_path, node_labels)
            return

        section = " › ".join(node_labels[:-1]) or "Chung"
        dotted = ".".join(node_path)

        if node_type == "matrix":
            columns = [(c["value"], c["label"]) for c in node.get("columns", [])]
            for row in node.get("rows", []):
                specs.append(
                    FieldSpec(
                        path=f"{dotted}.{row['id']}",
                        label=row["label"],
                        kind=KIND_ONE_OF,
                        section=f"{section} › {node['label']}",
                        options=columns,
                    )
                )
            return

        kind = {
            "number": KIND_NUMBER,
            "date": KIND_DATE,
            "radio": KIND_ONE_OF,
            "checkbox_group": KIND_MANY_OF,
        }.get(node_type, KIND_TEXT)

        specs.append(
            FieldSpec(
                path=dotted,
                label=node["label"],
                kind=kind,
                section=section,
                unit=node.get("unit"),
                options=[(o["value"], o["label"]) for o in node.get("options", [])],
            )
        )

    for child in block.get("children", []):
        walk(child, [], [])
    return specs


def render_spec_for_prompt(specs: list[FieldSpec]) -> str:
    """Bản đặc tả dạng text, nhóm theo mục để model dễ bám theo bố cục bệnh án."""
    lines: list[str] = []
    current_section = None
    for spec in specs:
        if spec.section != current_section:
            current_section = spec.section
            lines.append(f"\n### {current_section}")

        parts = [spec.path, spec.label]
        if spec.kind == KIND_NUMBER:
            parts.append(f"số{f' ({spec.unit})' if spec.unit else ''}")
        elif spec.kind == KIND_DATE:
            parts.append("ngày YYYY-MM-DD")
        elif spec.kind in (KIND_ONE_OF, KIND_MANY_OF):
            choices = ", ".join(f"{value}={label}" for value, label in spec.options)
            prefix = "chọn 1" if spec.kind == KIND_ONE_OF else "chọn nhiều"
            parts.append(f"{prefix} [{choices}]")
        else:
            parts.append("chữ")
        lines.append(" | ".join(parts))
    return "\n".join(lines).strip()


# ==================== Đi vào: JSON model -> giá trị hợp lệ ====================


def _normalise(text: str) -> str:
    """Bỏ dấu, hạ chữ thường — để khớp cả khi model trả nhãn không dấu."""
    stripped = unicodedata.normalize("NFD", str(text))
    stripped = "".join(ch for ch in stripped if unicodedata.category(ch) != "Mn")
    return re.sub(r"\s+", " ", stripped).strip().lower()


def _flatten(value: Any, prefix: str = "") -> dict[str, Any]:
    """Model có thể trả phẳng hoặc lồng — quy về một dạng phẳng duy nhất."""
    flat: dict[str, Any] = {}
    if isinstance(value, dict):
        for key, child in value.items():
            path = f"{prefix}.{key}" if prefix else str(key)
            if isinstance(child, dict):
                flat.update(_flatten(child, path))
            else:
                flat[path] = child
    return flat


def _coerce_number(raw: Any) -> float | int | None:
    if isinstance(raw, (int, float)) and not isinstance(raw, bool):
        return raw
    text = str(raw).replace(",", ".")
    match = re.search(r"-?\d+(?:\.\d+)?", text)
    if not match:
        return None
    number = float(match.group())
    return int(number) if number.is_integer() else number


_DATE_PATTERNS = (
    (re.compile(r"^(\d{4})-(\d{1,2})-(\d{1,2})"), (1, 2, 3)),
    (re.compile(r"^(\d{1,2})/(\d{1,2})/(\d{4})"), (3, 2, 1)),
    (re.compile(r"^(\d{1,2})-(\d{1,2})-(\d{4})"), (3, 2, 1)),
)


def _coerce_date(raw: Any) -> str | None:
    text = str(raw).strip()
    for pattern, (y, m, d) in _DATE_PATTERNS:
        match = pattern.match(text)
        if not match:
            continue
        try:
            return date(
                int(match.group(y)), int(match.group(m)), int(match.group(d))
            ).isoformat()
        except ValueError:
            return None
    return None


# Từ phủ định: nếu một bên có mà bên kia không thì tuyệt đối không được coi là
# khớp — "không bình thường" mà khớp vào "Bình thường" là đảo ngược bệnh án.
_NEGATION = re.compile(r"\b(khong|chua|phu dinh)\b")


def _match_option(raw: Any, spec: FieldSpec) -> str | None:
    """Chấp nhận cả mã (`limited`) lẫn nhãn tiếng Việt (`Hợp tác hạn chế`)."""
    needle = _normalise(raw)
    if not needle:
        return None

    for value, label in spec.options:
        if needle in (_normalise(value), _normalise(label)):
            return value

    # Model hay rút gọn nhãn ("Gọn gàng" thay vì "Gọn gàng, sạch sẽ") hoặc thêm
    # chữ thừa. Cho phép khớp một phía, nhưng chỉ khi duy nhất và cùng sắc thái
    # khẳng định/phủ định.
    needle_negated = bool(_NEGATION.search(needle))
    partial = [
        value
        for value, label in spec.options
        if (needle in _normalise(label) or _normalise(label) in needle)
        and bool(_NEGATION.search(_normalise(label))) == needle_negated
    ]
    return partial[0] if len(partial) == 1 else None


def _split_multi(raw: Any) -> list[Any]:
    if isinstance(raw, (list, tuple, set)):
        return list(raw)
    if raw is None:
        return []
    return [part for part in re.split(r"[;,|]", str(raw)) if part.strip()]


def coerce_extraction(
    raw_result: Any, specs: list[FieldSpec]
) -> tuple[dict[str, Any], list[str]]:
    """Lọc & ép kiểu kết quả model, trả về (dữ liệu lồng, danh sách cảnh báo).

    Nguyên tắc: **thà bỏ trống còn hơn ghi bậy**. Giá trị không khớp lựa chọn nào
    trong template thì loại bỏ và ghi cảnh báo để bác sĩ tự điền ở màn hình soát.
    """
    by_path = {spec.path: spec for spec in specs}
    flat = _flatten(raw_result if isinstance(raw_result, dict) else {})
    warnings: list[str] = []
    cleaned: dict[str, Any] = {}

    for path, raw in flat.items():
        if raw is None or (isinstance(raw, str) and not raw.strip()):
            continue

        spec = by_path.get(path)
        if spec is None:
            warnings.append(f"Bỏ qua trường không có trong biểu mẫu: {path}")
            continue

        if spec.kind == KIND_NUMBER:
            value = _coerce_number(raw)
            if value is None:
                warnings.append(f"{spec.label}: không đọc được số từ “{raw}”")
                continue
        elif spec.kind == KIND_DATE:
            value = _coerce_date(raw)
            if value is None:
                warnings.append(f"{spec.label}: không đọc được ngày từ “{raw}”")
                continue
        elif spec.kind == KIND_ONE_OF:
            value = _match_option(raw, spec)
            if value is None:
                warnings.append(f"{spec.label}: “{raw}” không thuộc danh sách lựa chọn")
                continue
        elif spec.kind == KIND_MANY_OF:
            matched = []
            for item in _split_multi(raw):
                option = _match_option(item, spec)
                if option is None:
                    warnings.append(
                        f"{spec.label}: “{str(item).strip()}” không thuộc danh sách lựa chọn"
                    )
                elif option not in matched:
                    matched.append(option)
            if not matched:
                continue
            value = matched
        else:
            value = str(raw).strip()
            if not value:
                continue

        cleaned[path] = value

    return _nest(cleaned), warnings


def _nest(flat: dict[str, Any]) -> dict[str, Any]:
    nested: dict[str, Any] = {}
    for path, value in flat.items():
        parts = path.split(".")
        cursor = nested
        for part in parts[:-1]:
            cursor = cursor.setdefault(part, {})
        cursor[parts[-1]] = value
    return nested


def count_filled(values: dict[str, Any]) -> int:
    """Số ô thực sự có dữ liệu — dùng để báo cho người soát biết đọc được bao nhiêu."""
    total = 0
    for value in values.values():
        if isinstance(value, dict):
            total += count_filled(value)
        elif value not in (None, "", [], {}):
            total += 1
    return total

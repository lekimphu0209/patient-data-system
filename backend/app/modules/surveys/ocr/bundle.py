"""Tách một file chứa nhiều phiếu của MỘT người thành từng phiếu.

    trang có nội dung -> model nhận diện mẫu của từng trang (chỉ gửi phần đầu trang)
    -> gom các trang liên tiếp cùng mẫu -> mỗi mẫu đọc riêng như một phiếu đơn

Nguyên tắc một lượt một người: cùng một mẫu xuất hiện hai lần (hai trang tiêu đề,
hoặc bị một mẫu khác chen giữa rồi lặp lại) nghĩa là file chứa phiếu của nhiều
người. Khi đó từ chối cả file thay vì đoán trang nào của ai.
"""

from __future__ import annotations

import io
from dataclasses import dataclass, field
from typing import Any

OTHER = "other"
BLANK = "blank"
# Phần đầu trang đủ chứa mã mẫu in ở góc phải, tiêu đề phiếu và vài câu đầu, mà
# chỉ tốn khoảng một phần ba số token so với gửi cả trang.
HEADER_FRACTION = 0.32
HEADER_WIDTH = 1400

CLASSIFY_PROMPT = """\
Bạn phân loại các trang của một file scan chứa phiếu khảo sát sức khỏe tâm thần (giấy, tiếng Việt)
của MỘT người. Mỗi ảnh là phần đầu (khoảng một phần ba phía trên) của một trang. Với từng trang, cho
biết trang thuộc biểu mẫu nào trong danh sách được cung cấp.

Căn cứ, theo thứ tự ưu tiên:
1. Mã mẫu in ở góc trên bên phải mỗi trang (ví dụ "KCB-TT.02- Mẫu 01"). Phải khớp CẢ số sau "TT."
   VÀ số mẫu: "KCB-TT.01- Mẫu 02" và "KCB-TT.05- Mẫu 02" là hai mẫu khác nhau.
2. Tiêu đề phiếu (chỉ in ở trang đầu của mỗi phiếu).
3. Nội dung câu hỏi/mục in trên trang (với trang tiếp theo của một phiếu).

Kết quả cho mỗi trang:
- form: mã biểu mẫu trong danh sách; "other" nếu trang thuộc một mẫu KHÔNG có trong danh sách;
  "blank" nếu trang không có nội dung phiếu (trang trắng, chỉ có số trang hoặc vết bẩn).
- starts_form: true chỉ khi trang có in tiêu đề phiếu, tức là trang đầu tiên của một phiếu.
- printed_code: mã mẫu in trên trang, null nếu không thấy.
- subject_code: mã đối tượng VIẾT TAY trên trang, null nếu không có. Thường viết sau tiền tố in sẵn ở
  mục "Mã số"/"Mã phiếu" (in "KCB-TT.01" rồi viết tay "QK1.01" thì là "QK1.01"), hoặc viết riêng ở lề/góc
  trên trang đầu (ví dụ "PT.CK 001"). Chép đúng từng chữ, từng chữ số như nét viết; không lấy tiền tố
  hay mã mẫu in sẵn; bỏ qua chữ bị ngược do thấm/in từ mặt sau tờ giấy.
Trả về đúng một mục cho mỗi trang được gửi, dùng đúng số trang ghi trước mỗi ảnh. Không suy đoán:
không chắc trang thuộc mẫu nào trong danh sách thì trả "other".
"""


class MultipleCopiesError(ValueError):
    """Cùng một mẫu xuất hiện hơn một lần — file có phiếu của nhiều người."""


@dataclass
class FormPart:
    form: dict[str, Any]
    pages: list[int] = field(default_factory=list)


@dataclass
class SkippedPages:
    pages: list[int]
    reason: str


@dataclass
class BundlePlan:
    parts: list[FormPart]
    skipped: list[SkippedPages]
    # Mã đối tượng viết tay đọc được ở trang đầu các phiếu: (số trang, mã như đã chép).
    written_codes: list[tuple[int, str]] = field(default_factory=list)


def classify_prompt(forms: list[dict[str, Any]]) -> str:
    lines = ["Các biểu mẫu có trong hệ thống (chỉ phân loại vào các mẫu này):"]
    for form in forms:
        first, last = form["questions"][0]["label"], form["questions"][-1]["label"]
        lines.append(
            f"- {form['id']}: mã in “{form['code']}” — tiêu đề “{form['title']}” — "
            f"câu đầu “{first[:90]}” — câu cuối “{last[:90]}”"
        )
    return "\n".join(lines)


def classify_schema(forms: list[dict[str, Any]]) -> dict[str, Any]:
    page = {
        "type": "object",
        "properties": {
            "page": {"type": "integer"},
            "form": {"type": "string", "enum": [form["id"] for form in forms] + [OTHER, BLANK]},
            "starts_form": {"type": "boolean"},
            "printed_code": {"type": ["string", "null"]},
            "subject_code": {"type": ["string", "null"]},
        },
        "required": ["page", "form", "starts_form", "printed_code", "subject_code"],
        "additionalProperties": False,
    }
    return {
        "type": "object",
        "properties": {"pages": {"type": "array", "items": page}},
        "required": ["pages"],
        "additionalProperties": False,
    }


def header_strip(jpeg: bytes) -> bytes:
    """Cắt phần đầu trang (đã render JPEG) để nhận diện mẫu."""
    from PIL import Image

    with Image.open(io.BytesIO(jpeg)) as image:
        width, height = image.size
        strip = image.crop((0, 0, width, max(1, round(height * HEADER_FRACTION))))
        if strip.width > HEADER_WIDTH:
            strip = strip.resize((HEADER_WIDTH, round(strip.height * HEADER_WIDTH / strip.width)))
        buffer = io.BytesIO()
        strip.convert("RGB").save(buffer, format="JPEG", quality=85)
        return buffer.getvalue()


def page_ranges(pages: list[int]) -> str:
    """[1, 2, 3, 5] -> "1–3, 5"."""
    ranges: list[str] = []
    start = previous = None
    for number in sorted(pages):
        if previous is not None and number == previous + 1:
            previous = number
            continue
        if start is not None:
            ranges.append(f"{start}–{previous}" if previous != start else str(start))
        start = previous = number
    if start is not None:
        ranges.append(f"{start}–{previous}" if previous != start else str(start))
    return ", ".join(ranges)


def plan_bundle(forms: list[dict[str, Any]], page_numbers: list[int], raw: dict[str, Any]) -> BundlePlan:
    """Gom trang theo kết quả nhận diện; lỗi ``MultipleCopiesError`` nếu một mẫu lặp lại."""
    by_id = {form["id"]: form for form in forms}
    labels: dict[int, dict[str, Any]] = {}
    for item in (raw or {}).get("pages") or []:
        if isinstance(item, dict) and isinstance(item.get("page"), int):
            labels.setdefault(item["page"], item)

    parts: list[FormPart] = []
    latest: dict[str, FormPart] = {}
    last_form: str | None = None
    blank: list[int] = []
    other: list[int] = []
    other_codes: list[str] = []
    written_codes: list[tuple[int, str]] = []
    for number in page_numbers:
        item = labels.get(number, {})
        written = item.get("subject_code")
        # Mã chỉ viết ở trang đầu phiếu; trang sau thường chỉ có chữ thấm ngược từ mặt sau.
        if item.get("starts_form") is True and isinstance(written, str) and written.strip():
            written_codes.append((number, written.strip()))
        form_id = item.get("form")
        if form_id not in by_id:
            if form_id == BLANK:
                blank.append(number)
            else:
                other.append(number)
                code = item.get("printed_code")
                if isinstance(code, str) and code.strip() and code.strip() not in other_codes:
                    other_codes.append(code.strip())
            continue
        part = latest.get(form_id)
        # Trang "khác"/trắng chen giữa không làm đứt một phiếu (model có thể nhận sai
        # một trang), nhưng một mẫu đã biết chen giữa hoặc thêm trang tiêu đề thì có.
        if part is not None and (item.get("starts_form") is True or last_form != form_id):
            raise MultipleCopiesError(
                f"File có hơn một phiếu “{part.form['title']}” (trang {page_ranges(part.pages)} và "
                f"trang {number}). Mỗi lượt chỉ tải các phiếu của một người — hãy tách file theo "
                "từng người rồi tải lại."
            )
        if part is None:
            part = latest[form_id] = FormPart(by_id[form_id])
            parts.append(part)
        part.pages.append(number)
        last_form = form_id

    skipped: list[SkippedPages] = []
    if other:
        printed = f" (mã in: {', '.join(other_codes)})" if other_codes else ""
        skipped.append(SkippedPages(other, f"không thuộc mẫu nào của nhóm này{printed}"))
    if blank:
        skipped.append(SkippedPages(blank, "trang không có nội dung phiếu"))
    return BundlePlan(parts=parts, skipped=skipped, written_codes=written_codes)

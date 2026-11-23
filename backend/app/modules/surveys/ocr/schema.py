"""Từ định nghĩa biểu mẫu (forms.json) sinh prompt, JSON schema và bộ chuẩn hoá kết quả.

Schema gửi model ở chế độ strict: mỗi câu một lựa chọn bị ràng buộc bằng ``enum``
đúng chuỗi phương án của biểu mẫu (cộng ``null`` khi để trống), nên model không
thể trả về đáp án ngoài danh sách. ``normalize`` vẫn kiểm lại toàn bộ — dữ liệu
từ bên ngoài không bao giờ được tin tuyệt đối.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from datetime import date, datetime
from typing import Any
from zoneinfo import ZoneInfo

SUBJECT_FIELDS = ("code", "full_name", "birth_year", "birth_date", "hometown", "unit", "survey_date")
MAX_TEXT = 20000
MAX_SHORT = 255
MAX_CODE = 120
NO_EVENT = "Không gặp sự kiện đáng kể"

SYSTEM_PROMPT = """\
Bạn là chuyên viên nhập liệu phiếu khảo sát sức khỏe tâm thần của Bệnh viện Quân y 103.
Bạn nhận ảnh chụp/scan một phiếu giấy tiếng Việt đã được người trả lời điền tay, cùng danh
sách câu hỏi của biểu mẫu. Hãy chép lại chính xác những gì ĐƯỢC ĐÁNH DẤU hoặc VIẾT trên phiếu.

Quy tắc đọc dấu chọn:
- Dấu chọn hợp lệ: X, ✓, dấu tích, gạch chéo hoặc tô kín trong ô vuông/ô của bảng ứng với một phương án.
- Dấu bị khoanh tròn, gạch xoá, tô đè hoặc viết đè lên là dấu ĐÃ HUỶ, không tính. Người trả lời
  sửa phiếu bằng cách khoanh tròn dấu cũ rồi đánh dấu sang ô khác.
- Câu có dấu đã huỷ: VẪN PHẢI trả về phương án của dấu hợp lệ còn lại (không trả null chỉ vì có dấu
  huỷ), đồng thời ghi mã câu vào "uncertain" để người soát đối chiếu. Chỉ trả null khi không còn dấu
  hợp lệ nào.
- Câu một lựa chọn mà sau khi bỏ dấu huỷ vẫn còn hơn một dấu hợp lệ, hoặc không phân biệt được
  dấu nằm ở ô nào: trả về null và ghi mã câu vào "uncertain".
- Bảng câu hỏi kéo sang trang sau thường KHÔNG in lại tiêu đề cột. Khi đó thứ tự cột vẫn giữ
  nguyên như trang trước và đúng thứ tự phương án đã liệt kê; căn hàng theo số thứ tự (STT) in trên phiếu.
- Một số ô của bảng để trống không có phương án; luôn căn theo chữ in trong ô hoặc tiêu đề cột.
- Câu cho phép nhiều lựa chọn: trả về mảng mọi phương án được đánh dấu hợp lệ (mảng rỗng nếu không chọn gì).

Quy tắc chung:
- Chỉ dùng đúng chuỗi phương án đã cho; không tự tạo phương án mới.
- Câu bỏ trống, bị che, mờ hoặc không đọc được: trả về null. TUYỆT ĐỐI không suy đoán, không điền
  theo đáp án "hợp lý", không suy ra năm sinh từ tuổi hay ngược lại.

Quy tắc đọc chữ viết tay (câu văn bản tự do và thông tin định danh):
- Chép theo đúng nét chữ thực tế, giữ dấu tiếng Việt và chữ số; bỏ dấu chấm lửng in sẵn. KHÔNG thay
  bằng câu trả lời thường gặp của câu hỏi đó (ví dụ mục tôn giáo viết "Khg" thì là "Không", không phải
  một tôn giáo nào khác).
- Viết tắt thông dụng: "k", "ko", "kg", "khg", "kh" nghĩa là "Không".
- Đọc được phần lớn nhưng còn chữ chưa chắc: chép cách đọc tốt nhất VÀ ghi mã vào "uncertain".
  Chỉ trả về null khi hoàn toàn không đọc được.
- Chữ số viết tay dễ nhầm (1/4/7/9, 3/8, 2/5, 0/6): nếu một chữ số có thể đọc thành chữ số khác thì
  ghi mã vào "uncertain".
- Mỗi mã trong "uncertain" phải là mã câu (Qxxx) hoặc tên trường định danh mà bạn không chắc chắn.

Thông tin định danh (subject) chỉ lấy khi được viết trên phiếu, không có thì null:
- code: mã đối tượng viết tay. Thường viết sau tiền tố in sẵn ở mục "Mã số"/"Mã phiếu" (ví dụ in
  "KCB-TT.01" rồi viết tay "QK1.01" thì code là "QK1.01"), hoặc viết tay riêng ở lề/góc trên của trang
  đầu khi mục "Mã số" để trống (ví dụ "PT.CK 001", "PT.TL 143"). Chép đúng chữ và số như viết, giữ dấu
  chấm/khoảng trắng phân cách. Không lấy tiền tố in sẵn, mã mẫu in sẵn ("KCB-TT.02- Mẫu 01") hay số trang.
- full_name: chỉ lấy từ mục "Họ và tên"; KHÔNG lấy từ chữ ký hay tên ký ở cuối phiếu.
- birth_year (4 chữ số), birth_date (YYYY-MM-DD, chỉ khi có đủ ngày tháng năm),
  hometown (chỉ mục "Quê quán"; KHÔNG lấy "Địa chỉ"), unit (chỉ mục "Đơn vị"/"Địa bàn" ghi rõ),
  survey_date (YYYY-MM-DD, ví dụ mục "Ngày điều tra"/"Ngày khảo sát").

form_check: đối chiếu tiêu đề và mã mẫu in trên phiếu với biểu mẫu được yêu cầu. Đặt
is_expected_form = false CHỈ khi phiếu rõ ràng là một mẫu khác; observed_title là tiêu đề in trên phiếu.
notes: ghi ngắn gọn (tiếng Việt) các vấn đề người soát cần biết, ví dụ phiếu thiếu trang, dấu sửa
khó đọc; null nếu không có gì đáng chú ý.
"""


@dataclass
class Extraction:
    """Kết quả đã chuẩn hoá, sẵn sàng tạo bản ghi khảo sát."""

    answers: dict[str, str | list[str]]
    subject: dict[str, str | None]
    uncertain: list[str]
    notes: str
    is_expected_form: bool
    observed_title: str

    @property
    def is_empty(self) -> bool:
        return not self.answers and not any(self.subject.values())


def _question_kind(question: dict[str, Any]) -> str:
    if not question["options"]:
        return "văn bản tự do"
    return "nhiều lựa chọn" if question["multi"] else "một lựa chọn"


def form_prompt(form: dict[str, Any]) -> str:
    lines = [
        f"Biểu mẫu được yêu cầu: {form['title']} (mã in trên phiếu: {form['code']}).",
        f"Nhóm đối tượng: {'Quân nhân' if form['group'] == 'military' else 'Thanh niên'}.",
        f"Phiếu có {len(form['questions'])} câu, theo đúng thứ tự in trên giấy:",
        "",
    ]
    if form.get("ocrHint"):
        lines[2:2] = [f"Lưu ý riêng của mẫu này: {form['ocrHint']}"]
    for index, question in enumerate(form["questions"], start=1):
        lines.append(f"{question['id']} — câu thứ {index} — {_question_kind(question)}: {question['label']}")
        if question["options"]:
            options = "; ".join(f"[{number}] {option}" for number, option in enumerate(question["options"], 1))
            lines.append(f"    Phương án theo thứ tự cột/ô: {options}")
    return "\n".join(lines)


def response_schema(form: dict[str, Any]) -> dict[str, Any]:
    nullable_text = {"type": ["string", "null"]}
    answers: dict[str, Any] = {}
    for question in form["questions"]:
        if not question["options"]:
            answers[question["id"]] = nullable_text
        elif question["multi"]:
            answers[question["id"]] = {"type": "array", "items": {"type": "string", "enum": question["options"]}}
        else:
            answers[question["id"]] = {"type": ["string", "null"], "enum": [*question["options"], None]}

    def strict_object(properties: dict[str, Any]) -> dict[str, Any]:
        return {
            "type": "object",
            "properties": properties,
            "required": list(properties),
            "additionalProperties": False,
        }

    uncertain_keys = [question["id"] for question in form["questions"]] + list(SUBJECT_FIELDS)
    return strict_object({
        "form_check": strict_object({
            "is_expected_form": {"type": "boolean"},
            "observed_title": nullable_text,
        }),
        "subject": strict_object({name: nullable_text for name in SUBJECT_FIELDS}),
        "answers": strict_object(answers),
        "uncertain": {"type": "array", "items": {"type": "string", "enum": uncertain_keys}},
        "notes": nullable_text,
    })


def _clean(value: Any, limit: int) -> str:
    if not isinstance(value, str):
        return ""
    return re.sub(r"\s+", " ", value).strip(" .…_- ")[:limit].strip()


def _today() -> date:
    return datetime.now(ZoneInfo("Asia/Ho_Chi_Minh")).date()


def _iso_date(value: Any, *, earliest: int) -> str | None:
    text = _clean(value, 20)
    match = re.fullmatch(r"(\d{4})-(\d{1,2})-(\d{1,2})", text)
    if match:
        year, month, day = (int(part) for part in match.groups())
    else:
        match = re.fullmatch(r"(\d{1,2})[/.-](\d{1,2})[/.-](\d{4})", text)
        if not match:
            return None
        day, month, year = (int(part) for part in match.groups())
    try:
        parsed = date(year, month, day)
    except ValueError:
        return None
    return parsed.isoformat() if earliest <= parsed.year and parsed <= _today() else None


# Tiền tố in sẵn của đề tài ("KCB-TT.01", "KCB.TT", "KCB-TT.02- Mẫu 01") mà model đôi khi chép theo.
PRINTED_PREFIX = re.compile(r"^KCB[\s.\-]*TT(?:[\s.\-]*\d+)?(?:[\s.\-]*M[ẪẫAa]U[\s.]*\d+)?[\s.:\-]*", re.I)
CODE_SEPARATOR = re.compile(r"[\s._\-–—·:]+")


def canonical_code(value: Any) -> str | None:
    """Mã đối tượng dạng thống nhất: chữ in hoa, các phần ngăn cách bằng một dấu chấm.

    Người điền viết cùng một mã theo nhiều kiểu ("PT.CK 001", "PT.Ck.001", "PT. CK-001");
    gom về một dạng ("PT.CK.001", "QK1.02") để các phiếu của cùng một người khớp mã.
    Giữ nguyên chữ số (kể cả số 0 đứng đầu) như trên phiếu.
    """
    text = PRINTED_PREFIX.sub("", _clean(value, 200))
    parts = [part for part in CODE_SEPARATOR.split(text.upper()) if part]
    return ".".join(parts)[:MAX_CODE] or None


def code_key(value: Any) -> str | None:
    """Khoá so khớp mã: như ``canonical_code`` nhưng bỏ số 0 đứng đầu ("PT.CK.001" ~ "PT.CK.1")."""
    code = canonical_code(value)
    if not code:
        return None
    return ".".join(str(int(part)) if part.isdigit() else part for part in code.split("."))


def _subject(raw: dict[str, Any]) -> dict[str, str | None]:
    year = _clean(raw.get("birth_year"), 10)
    birth_year = year if re.fullmatch(r"(19|20)\d{2}", year) and int(year) <= _today().year else None
    birth_date = _iso_date(raw.get("birth_date"), earliest=1900)
    if birth_date and birth_year and birth_date[:4] != birth_year:
        birth_date = None
    return {
        "code": canonical_code(raw.get("code")),
        "full_name": _clean(raw.get("full_name"), MAX_SHORT) or None,
        "birth_year": birth_year or (birth_date[:4] if birth_date else None),
        "birth_date": birth_date,
        "hometown": _clean(raw.get("hometown"), MAX_SHORT) or None,
        "unit": _clean(raw.get("unit"), MAX_SHORT) or None,
        "survey_date": _iso_date(raw.get("survey_date"), earliest=2000),
    }


def normalize(form: dict[str, Any], raw: dict[str, Any]) -> Extraction:
    raw = raw if isinstance(raw, dict) else {}
    raw_answers = raw.get("answers") if isinstance(raw.get("answers"), dict) else {}
    uncertain = {key for key in raw.get("uncertain") or [] if isinstance(key, str)}
    answers: dict[str, str | list[str]] = {}

    for question in form["questions"]:
        key, options = question["id"], question["options"]
        value = raw_answers.get(key)
        if value is None or value == []:
            continue
        if not options:
            text = _clean(value, MAX_TEXT)
            if text:
                answers[key] = text
            continue
        if question["multi"]:
            values = value if isinstance(value, list) else [value]
            chosen = list(dict.fromkeys(item for item in values if item in options))
            too_many = "tối đa 2" in question["label"] and len(chosen) > 2
            conflicting = len(chosen) > 1 and any(NO_EVENT in item for item in chosen)
            if len(chosen) != len(values) or too_many or conflicting:
                uncertain.add(key)
            if chosen and not too_many and not conflicting:
                answers[key] = chosen
        elif isinstance(value, str) and value in options:
            answers[key] = value
        else:
            uncertain.add(key)

    subject = _subject(raw.get("subject") if isinstance(raw.get("subject"), dict) else {})
    # Phiếu có ô họ tên / năm sinh: giữ hồ sơ đối tượng và câu trả lời khớp nhau.
    for question in form["questions"]:
        value = answers.get(question["id"])
        if not isinstance(value, str):
            continue
        if re.match(r"^(\d+\.\s*)?Họ và tên", question["label"]) and not subject["full_name"]:
            subject["full_name"] = value[:MAX_SHORT]
        if question["label"] == "Năm sinh" and not subject["birth_year"]:
            if re.fullmatch(r"(19|20)\d{2}", value) and int(value) <= _today().year:
                subject["birth_year"] = value

    check = raw.get("form_check") if isinstance(raw.get("form_check"), dict) else {}
    order = [question["id"] for question in form["questions"]] + list(SUBJECT_FIELDS)
    return Extraction(
        answers=answers,
        subject=subject,
        uncertain=[key for key in order if key in uncertain],
        notes=_clean(raw.get("notes"), 2000),
        is_expected_form=check.get("is_expected_form") is not False,
        observed_title=_clean(check.get("observed_title"), MAX_SHORT),
    )

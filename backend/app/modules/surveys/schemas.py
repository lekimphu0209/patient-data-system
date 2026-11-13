import json
import re
from datetime import date, datetime
from pathlib import Path
from typing import Annotated, Literal
from zoneinfo import ZoneInfo

from pydantic import BaseModel, Field, StringConstraints, field_validator, model_validator

FORMS = json.loads(Path(__file__).with_name("forms.json").read_text(encoding="utf-8"))
FORM_BY_ID = {form["id"]: form for form in FORMS}
Group = Literal["youth", "military"]
Status = Literal["draft", "review", "complete"]
Code = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=120)]
ShortText = Annotated[str, StringConstraints(max_length=255)]
LongText = Annotated[str, StringConstraints(max_length=20000)]
Answer = LongText | Annotated[list[LongText], Field(max_length=50)]


class SubjectInput(BaseModel):
    fullName: ShortText = ""
    birthDate: date | Literal[""] = ""
    birthYear: str = ""
    hometown: ShortText = ""

    @model_validator(mode="after")
    def check_dates(self):
        today = datetime.now(ZoneInfo("Asia/Ho_Chi_Minh")).date()
        if self.birthDate and self.birthDate > today:
            raise ValueError("Ngày sinh không hợp lệ.")
        if self.birthYear and (
            not re.fullmatch(r"[0-9]{4}", self.birthYear)
            or not 1900 <= int(self.birthYear) <= today.year
        ):
            raise ValueError("Năm sinh không hợp lệ.")
        if self.birthDate and self.birthYear and self.birthDate.year != int(self.birthYear):
            raise ValueError("Ngày sinh không khớp năm sinh.")
        return self


class RecordInput(BaseModel):
    id: Code
    person: Code
    group: Group
    form: str
    patient: SubjectInput
    unit: ShortText = ""
    date: date
    source: Literal["Thủ công", "Excel", "OCR"]
    status: Status
    conclusion: LongText = ""
    answers: dict[str, Answer] = Field(default_factory=dict)
    note: LongText = ""
    ocr: Annotated[str, StringConstraints(max_length=200000)] | None = None
    ocrImage: Annotated[str, StringConstraints(max_length=5000000)] | None = None
    updatedAt: datetime | None = None

    @field_validator("id")
    @classmethod
    def reserve_sample_ids(cls, value: str) -> str:
        if value.upper().startswith(("MAU-TN-", "MAU-QN-")):
            raise ValueError("Mã này dành cho dữ liệu mẫu.")
        return value

    @field_validator("ocrImage")
    @classmethod
    def check_image(cls, value: str | None) -> str | None:
        if value and not re.fullmatch(r"data:image/jpeg;base64,[A-Za-z0-9+/]+={0,2}", value):
            raise ValueError("Ảnh phiếu không hợp lệ.")
        return value

    @model_validator(mode="after")
    def check_answers(self):
        form = FORM_BY_ID.get(self.form)
        if not form or form["group"] != self.group:
            raise ValueError("Mã biểu mẫu không thuộc nhóm đối tượng.")
        if self.form == "F01":
            skip_rules = {
                "Q013": ("Chưa bao giờ", ("Q014", "Q015", "Q016", "Q017")),
                "Q018": ("Không gặp sự kiện đáng kể", ("Q019",)),
                "Q020": ("Không có", ("Q021", "Q022", "Q023", "Q024", "Q025", "Q026", "Q027")),
                "Q028": ("Không có ai", ("Q029", "Q030")),
            }
            skipped = {
                question
                for control, (prefix, questions) in skip_rules.items()
                if any(
                    answer.startswith(prefix)
                    for answer in (
                        self.answers.get(control, [])
                        if isinstance(self.answers.get(control), list)
                        else [self.answers.get(control, "")]
                    )
                )
                for question in questions
            }
            self.answers = {key: value for key, value in self.answers.items() if key not in skipped}
        else:
            skipped = set()
        questions = {question["id"]: question for question in form["questions"]}
        for key, value in self.answers.items():
            question = questions.get(key)
            if not question or question["multi"] != isinstance(value, list):
                raise ValueError(f"{key}: đáp án không hợp lệ.")
            choices = value if isinstance(value, list) else [value]
            if question["options"] and any(choice not in question["options"] for choice in choices):
                raise ValueError(f"{key}: đáp án không hợp lệ.")
            if "tối đa 2" in question["label"] and len(choices) > 2:
                raise ValueError(f"{key}: chỉ chọn tối đa 2 đáp án.")
            if len(choices) > 1 and any("Không gặp sự kiện đáng kể" in choice for choice in choices):
                raise ValueError(f"{key}: không chọn đồng thời với sự kiện khác.")
        if self.status == "complete":
            missing = sum(not self.answers.get(key) for key in questions.keys() - skipped)
            if missing:
                raise ValueError(f"Còn {missing} mục thiếu. Hãy bổ sung hoặc lưu bản nháp.")
        return self


class RecordBatch(BaseModel):
    records: list[RecordInput] = Field(min_length=1, max_length=2000)


class DeleteBatch(BaseModel):
    ids: list[Code] = Field(min_length=1)

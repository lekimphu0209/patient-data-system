"""Ảnh chụp dữ liệu khảo sát trong SQLite bộ nhớ cho trợ lý truy vấn.

Bảng (đơn giản, phẳng, dễ cho LLM viết truy vấn):

- ``questions``: danh mục câu hỏi của 9 mẫu.
- ``subjects``: mỗi đối tượng một dòng, kèm giới tính/tuổi suy ra từ câu trả lời.
- ``records``: mỗi phiếu một dòng.
- ``answers``: mỗi đáp án đã chọn một dòng (câu nhiều lựa chọn tách thành nhiều dòng).
  Câu định danh (họ tên, địa chỉ) không có trong bảng này.

Truy vấn chỉ được đọc: ``PRAGMA query_only``, authorizer chỉ cho SELECT/đọc và một danh
sách hàm an toàn, giới hạn thời gian chạy và số dòng.
"""

from __future__ import annotations

import re
import sqlite3
import threading
import time
import unicodedata
from dataclasses import dataclass
from typing import Any, Iterable

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.modules.clinical.models import ClinicalPatient
from app.modules.clinical.schema import FIELDS as CLINICAL_FIELDS, FORMS as CLINICAL_FORMS, SECTION_OF
from app.modules.surveys.models import SurveyRecord, SurveySubject
from app.modules.surveys.schemas import FORMS, skipped_questions

GROUP_LABEL = {"youth": "Thanh niên", "military": "Quân nhân"}
STATUS_LABEL = {"complete": "Đã hoàn tất", "review": "Chờ đối soát", "draft": "Bản nháp"}
STATUS_ORDER = ("complete", "review", "draft")
EXPECTED_FORMS = {group: [form["id"] for form in FORMS if form["group"] == group] for group in GROUP_LABEL}
AGE_GROUPS = ("Dưới 20", "20–24", "25–29", "30 trở lên")
UNKNOWN = "Chưa rõ"

REFRESH_SECONDS = 120
QUERY_SECONDS = 3.0
MAX_ROWS = 500

SCHEMA_SQL = """
CREATE TABLE questions (
  form TEXT, question TEXT, grp TEXT, form_title TEXT, position INTEGER,
  label TEXT, kind TEXT, options TEXT, PRIMARY KEY (form, question)
);
CREATE TABLE subjects (
  grp TEXT, person TEXT, code_prefix TEXT, full_name TEXT, birth_date TEXT, birth_year INTEGER,
  hometown TEXT, gender TEXT, age INTEGER, age_group TEXT, PRIMARY KEY (grp, person)
);
CREATE TABLE records (
  record_id TEXT PRIMARY KEY, grp TEXT, form TEXT, person TEXT, code_prefix TEXT, status TEXT,
  survey_date TEXT, source TEXT, answered INTEGER, applicable INTEGER, has_conclusion INTEGER
);
CREATE TABLE answers (
  record_id TEXT, grp TEXT, form TEXT, person TEXT, status TEXT, question TEXT, value TEXT
);
CREATE INDEX answers_question ON answers (form, question);
CREATE INDEX answers_person ON answers (grp, person);
CREATE INDEX records_person ON records (grp, person);
CREATE TABLE clinical_patients (
  patient_id TEXT PRIMARY KEY, type TEXT, code TEXT, full_name TEXT, age INTEGER, age_group TEXT, sex TEXT,
  source TEXT, visits INTEGER, first_visit TEXT, latest_visit TEXT, latest_diagnosis TEXT
);
CREATE TABLE clinical_fields (
  patient_id TEXT, type TEXT, visit_id TEXT, visit_date TEXT, visit_no INTEGER, is_latest INTEGER,
  section TEXT, field TEXT, label TEXT, kind TEXT, value TEXT
);
CREATE INDEX clinical_fields_field ON clinical_fields (type, field);
"""

# Mô tả cho LLM khi phải tự viết truy vấn (công cụ "truy vấn nâng cao").
SCHEMA_DOC = """Cơ sở dữ liệu SQLite (chỉ đọc). Phiếu khảo sát gồm 4 bảng:
- questions(form, question, grp, form_title, position, label, kind, options): danh mục câu hỏi. kind: 'single' | 'multi' | 'text' | 'identity'. options: các đáp án nối bằng ' | '.
- subjects(grp, person, code_prefix, full_name, birth_date, birth_year, hometown, gender, age, age_group): mỗi đối tượng một dòng. grp: 'youth' (thanh niên) | 'military' (quân nhân). person: mã đối tượng (VD 'PT.CK.001', 'QK1.01'). code_prefix: phần đầu mã ('PT.CK', 'PT.TL', 'QK1'). gender: 'Nam' | 'Nữ' | NULL. age: tuổi (số) hoặc NULL. age_group: 'Dưới 20' | '20–24' | '25–29' | '30 trở lên' | 'Chưa rõ'.
- records(record_id, grp, form, person, code_prefix, status, survey_date, source, answered, applicable, has_conclusion): mỗi phiếu một dòng. form: 'F01'..'F09'. status: 'complete' (Đã hoàn tất) | 'review' (Chờ đối soát) | 'draft' (Bản nháp). survey_date: 'YYYY-MM-DD'. answered/applicable: số câu đã trả lời / số câu áp dụng.
- answers(record_id, grp, form, person, status, question, value): mỗi đáp án đã chọn một dòng; câu nhiều lựa chọn có nhiều dòng; value là đúng chữ của đáp án. Câu bị chuyển qua hoặc bỏ trống thì không có dòng.
Khoá nối: answers.record_id = records.record_id; (grp, person) nối records/answers/subjects.
Đếm người dùng COUNT(DISTINCT grp || '|' || person).
Bệnh án nghiên cứu (tách riêng với phiếu khảo sát, không có mã nối với subjects):
- clinical_patients(patient_id, type, code, full_name, age, age_group, sex, source, visits, first_visit, latest_visit, latest_diagnosis): mỗi bệnh nhân một dòng. type: 'F20' (tâm thần phân liệt) | 'F32' (trầm cảm). source: 'Thủ công' | 'OCR'.
- clinical_fields(patient_id, type, visit_id, visit_date, visit_no, is_latest, section, field, label, kind, value): mỗi giá trị đã nhập của mỗi lần khám một dòng (trường nhiều lựa chọn tách nhiều dòng). visit_no: 1 = khám lần đầu. is_latest = 1 cho lần khám gần nhất. Không có dòng cho trường để trống."""

SAFE_FUNCTIONS = {
    "count", "sum", "avg", "min", "max", "total", "group_concat", "round", "abs", "lower", "upper",
    "length", "substr", "substring", "trim", "ltrim", "rtrim", "replace", "instr", "coalesce", "ifnull",
    "nullif", "iif", "date", "time", "datetime", "strftime", "julianday", "printf", "format", "like",
    "glob", "typeof", "row_number", "rank", "dense_rank", "ntile", "lag", "lead", "first_value",
    "last_value", "percent_rank", "cume_dist", "unicode", "char", "cast", "sign", "unlikely", "likely",
}
_ALLOWED_ACTIONS = {sqlite3.SQLITE_SELECT, sqlite3.SQLITE_READ, getattr(sqlite3, "SQLITE_RECURSIVE", 33)}


class QueryError(Exception):
    """Truy vấn không được phép hoặc chạy lỗi (thông điệp dùng để LLM tự sửa)."""


def fold(text: Any) -> str:
    """Chuẩn hoá để so khớp không dấu, không phân biệt hoa thường."""
    value = unicodedata.normalize("NFD", str(text or "")).replace("đ", "d").replace("Đ", "D")
    return re.sub(r"\s+", " ", "".join(ch for ch in value if unicodedata.category(ch) != "Mn")).strip().lower()


def code_prefix(person: str) -> str:
    parts = [part for part in re.split(r"[.\s]+", person or "") if part]
    while parts and parts[-1].isdigit():
        parts.pop()
    return ".".join(parts) or person


def code_key(value: str) -> str:
    """Khoá so khớp mã đối tượng: bỏ dấu ngăn cách lạ và số 0 đứng đầu ('qk1. 02' ~ 'QK1.2')."""
    parts = [part for part in re.split(r"[\s._\-–—·:]+", (value or "").upper()) if part]
    return ".".join(str(int(part)) if part.isdigit() else part for part in parts)


def question_kind(question: dict[str, Any]) -> str:
    label = question["label"]
    if re.match(r"^(\d+\.\s*)?Họ và tên", label) or label.strip() == "Địa chỉ":
        return "identity"
    if not question["options"]:
        return "text"
    return "multi" if question["multi"] else "single"


QUESTIONS = {
    (form["id"], question["id"]): {
        "form": form["id"], "question": question["id"], "grp": form["group"], "form_title": form["title"],
        "position": position, "label": question["label"], "kind": question_kind(question),
        "options": list(question["options"]),
    }
    for form in FORMS for position, question in enumerate(form["questions"], 1)
}
FORM_TITLES = {form["id"]: form["title"] for form in FORMS}
FORM_GROUP = {form["id"]: form["group"] for form in FORMS}
GENDER_QUESTIONS = {key for key, item in QUESTIONS.items() if fold(item["label"]).endswith("gioi tinh:")
                    or fold(item["label"]).endswith("gioi tinh")}
AGE_QUESTIONS = {key for key, item in QUESTIONS.items() if item["kind"] == "text" and "tuoi" in fold(item["label"])}
BIRTH_YEAR_QUESTIONS = {key for key, item in QUESTIONS.items() if item["kind"] == "text" and fold(item["label"]) == "nam sinh"}


def age_group(age: int | None) -> str:
    if age is None:
        return UNKNOWN
    if age < 20:
        return AGE_GROUPS[0]
    if age < 25:
        return AGE_GROUPS[1]
    if age < 30:
        return AGE_GROUPS[2]
    return AGE_GROUPS[3]


def _number(value: Any) -> int | None:
    match = re.search(r"\d{1,4}", str(value or ""))
    return int(match.group()) if match else None


def _values(answer: Any) -> list[str]:
    values = answer if isinstance(answer, list) else [answer]
    return [str(value).strip() for value in values if isinstance(value, (str, int, float)) and str(value).strip()]


SENSITIVE = {("subjects", "full_name"), ("subjects", "birth_date"), ("subjects", "hometown"),
             ("clinical_patients", "full_name")}
DATE = re.compile(r"\b\d{4}-\d{2}-\d{2}\b")


@dataclass
class Result:
    columns: list[str]
    rows: list[tuple]
    truncated: bool
    sensitive: bool = False  # truy vấn có đọc họ tên / ngày sinh / quê quán


class Snapshot:
    def __init__(self) -> None:
        self._lock = threading.RLock()
        self._connection: sqlite3.Connection | None = None
        self._signature: tuple | None = None
        self._built_at = 0.0
        self.names: set[str] = set()  # họ tên, quê quán thật — để lọc khỏi dữ liệu gửi LLM
        self._names_pattern: re.Pattern[str] | None = None

    # ---------- dựng ảnh chụp ----------

    @staticmethod
    def signature(db: Session) -> tuple:
        records = db.execute(select(func.count(SurveyRecord.id), func.max(SurveyRecord.updated_at))).one()
        subjects = db.scalar(select(func.count()).select_from(SurveySubject))
        clinical = db.execute(select(func.count(ClinicalPatient.id), func.max(ClinicalPatient.updated_at))).one()
        return (records[0], str(records[1]), subjects, clinical[0], str(clinical[1]))

    def ensure(self, db: Session) -> "Snapshot":
        """Dựng lại khi dữ liệu đổi (số phiếu, lần sửa cuối, số đối tượng) hoặc quá ``REFRESH_SECONDS``."""
        with self._lock:
            signature = self.signature(db)
            stale = time.monotonic() - self._built_at >= REFRESH_SECONDS
            if self._connection is None or signature != self._signature or stale:
                self._build(db)
                self._signature = signature
                self._built_at = time.monotonic()
            return self

    def _build(self, db: Session) -> None:
        connection = sqlite3.connect(":memory:", check_same_thread=False)
        connection.executescript(SCHEMA_SQL)
        connection.executemany(
            "INSERT INTO questions VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
            [(item["form"], item["question"], item["grp"], item["form_title"], item["position"], item["label"],
              item["kind"], " | ".join(item["options"])) for item in QUESTIONS.values()],
        )
        forms = {form["id"]: form for form in FORMS}
        rows = db.execute(select(
            SurveyRecord.id, SurveyRecord.group, SurveyRecord.form, SurveyRecord.person, SurveyRecord.status,
            SurveyRecord.date, SurveyRecord.source, SurveyRecord.answers, SurveyRecord.conclusion,
        )).all()
        derived: dict[tuple[str, str], dict[str, Any]] = {}
        record_rows, answer_rows = [], []
        for record_id, group, form_id, person, status, survey_date, source, answers, conclusion in rows:
            answers = answers or {}
            form = forms.get(form_id)
            skipped = skipped_questions(form, answers) if form else set()
            applicable = [q for q in (form or {}).get("questions", []) if q["id"] not in skipped]
            answered = sum(1 for q in applicable if _values(answers.get(q["id"])))
            prefix = code_prefix(person)
            record_rows.append((record_id, group, form_id, person, prefix, status,
                                survey_date.isoformat() if survey_date else None, source, answered,
                                len(applicable), int(bool((conclusion or "").strip()))))
            info = derived.setdefault((group, person), {})
            for question_id, answer in answers.items():
                key = (form_id, question_id)
                meta = QUESTIONS.get(key)
                if meta is None or meta["kind"] == "identity":
                    continue
                values = _values(answer)
                for value in values:
                    answer_rows.append((record_id, group, form_id, person, status, question_id, value))
                if values and key in GENDER_QUESTIONS and values[0] in ("Nam", "Nữ"):
                    info.setdefault("gender", values[0])
                if values and key in AGE_QUESTIONS:
                    age = _number(values[0])
                    if age and 10 <= age <= 90:
                        info.setdefault("age", age)
                if values and key in BIRTH_YEAR_QUESTIONS:
                    year = _number(values[0])
                    if year and 1900 <= year <= 2100 and survey_date:
                        info.setdefault("age_from_year", survey_date.year - year)
        connection.executemany("INSERT INTO records VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)", record_rows)
        connection.executemany("INSERT INTO answers VALUES (?, ?, ?, ?, ?, ?, ?)", answer_rows)

        names: set[str] = set()
        subject_rows = []
        latest_year = max((row[5].year for row in rows if row[5]), default=None)
        for subject in db.scalars(select(SurveySubject)):
            info = derived.get((subject.group, subject.person), {})
            birth_year = _number(subject.birth_year) if subject.birth_year else None
            if subject.birth_date:
                birth_year = subject.birth_date.year
            age = info.get("age") or info.get("age_from_year")
            if age is None and birth_year and latest_year:
                age = latest_year - birth_year
            for value in (subject.full_name, subject.hometown):
                # Chỉ chuỗi nhiều từ: tránh che nhầm từ thường như "Nam" (giới tính).
                if value and len(value.split()) >= 2:
                    names.add(" ".join(value.split()))
            subject_rows.append((
                subject.group, subject.person, code_prefix(subject.person), subject.full_name or None,
                subject.birth_date.isoformat() if subject.birth_date else None, birth_year,
                subject.hometown or None, info.get("gender"), age, age_group(age),
            ))
        connection.executemany("INSERT INTO subjects VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)", subject_rows)
        self._build_clinical(db, connection, names)
        connection.commit()
        connection.execute("PRAGMA query_only = ON")
        old, self._connection, self.names = self._connection, connection, names
        self._names_pattern = re.compile(
            "|".join(r"\s+".join(map(re.escape, name.split())) for name in sorted(names, key=len, reverse=True)),
            re.IGNORECASE) if names else None
        if old is not None:
            old.close()

    @staticmethod
    def _build_clinical(db: Session, connection: sqlite3.Connection, names: set[str]) -> None:
        """Bệnh án: một dòng mỗi bệnh nhân + một dòng mỗi giá trị đã nhập của từng lần khám.

        Không đưa vào: nơi thường trú, quê quán (định danh) và người làm bệnh án.
        """
        patients, values = [], []
        labels = {type_: {field["key"]: field for field in fields} for type_, fields in CLINICAL_FIELDS.items()}
        for patient in db.scalars(select(ClinicalPatient)):
            if patient.type not in CLINICAL_FORMS:
                continue
            for value in (patient.full_name, (patient.identity or {}).get("hometown"), (patient.identity or {}).get("address")):
                if isinstance(value, str) and len(value.split()) >= 2:
                    names.add(" ".join(value.split()))
            ordered = sorted(patient.visits, key=lambda visit: (visit.date, visit.created_at))
            latest = ordered[-1] if ordered else None
            patients.append((
                patient.id, patient.type, patient.code, patient.full_name or None, patient.age, age_group(patient.age),
                patient.sex or None, patient.source, len(ordered), ordered[0].date.isoformat() if ordered else None,
                latest.date.isoformat() if latest else None,
                ((latest.fields or {}).get("diagnosis") if latest else None) or None,
            ))
            for number, visit in enumerate(ordered, 1):
                for key, value in (visit.fields or {}).items():
                    field = labels[patient.type].get(key)
                    if field is None or key == "author":
                        continue
                    for item in value if isinstance(value, list) else [value]:
                        if str(item).strip():
                            values.append((patient.id, patient.type, visit.id, visit.date.isoformat(), number,
                                           int(visit is latest), SECTION_OF[patient.type][key], key, field["label"],
                                           field["kind"], str(item)))
        connection.executemany("INSERT INTO clinical_patients VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)", patients)
        connection.executemany("INSERT INTO clinical_fields VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)", values)

    # ---------- truy vấn ----------

    def query(self, sql: str, params: Iterable[Any] = (), limit: int = MAX_ROWS) -> Result:
        """Chạy MỘT câu SELECT với các giới hạn an toàn."""
        statement = sql.strip().rstrip(";").strip()
        if not statement:
            raise QueryError("Truy vấn rỗng.")
        if not re.match(r"^(select|with)\b", statement, re.IGNORECASE):
            raise QueryError("Chỉ được dùng một câu SELECT (có thể bắt đầu bằng WITH).")
        with self._lock:
            if self._connection is None:
                raise QueryError("Dữ liệu chưa sẵn sàng.")
            connection = self._connection
            deadline = time.monotonic() + QUERY_SECONDS
            reads: set[tuple[str, str]] = set()

            def authorize(action, first, second, database, trigger):
                if action == sqlite3.SQLITE_READ:
                    reads.add(((first or "").lower(), (second or "").lower()))
                    return sqlite3.SQLITE_OK
                if action in _ALLOWED_ACTIONS:
                    return sqlite3.SQLITE_OK
                if action == sqlite3.SQLITE_FUNCTION and (second or "").lower() in SAFE_FUNCTIONS:
                    return sqlite3.SQLITE_OK
                return sqlite3.SQLITE_DENY

            connection.set_authorizer(authorize)
            connection.set_progress_handler(lambda: int(time.monotonic() > deadline), 10_000)
            try:
                cursor = connection.execute(statement, tuple(params))
                rows = cursor.fetchmany(limit + 1)
                columns = [item[0] for item in cursor.description or []]
            except (sqlite3.Warning, sqlite3.DatabaseError) as error:
                message = str(error)
                if "one statement" in message:
                    message = "Chỉ được chạy một câu lệnh mỗi lần."
                elif "interrupted" in message:
                    message = f"Truy vấn chạy quá {QUERY_SECONDS:g} giây."
                elif "not authorized" in message:
                    message = "Truy vấn dùng thao tác hoặc hàm không được phép (chỉ được đọc dữ liệu)."
                raise QueryError(message) from error
            finally:
                connection.set_authorizer(None)
                connection.set_progress_handler(None, 0)
        return Result(columns=columns, rows=[tuple(row) for row in rows[:limit]], truncated=len(rows) > limit,
                      sensitive=bool(reads & SENSITIVE))

    def redact(self, value: Any, sensitive: bool = False) -> Any:
        """Che họ tên/quê quán thật (cả khi nằm trong chuỗi ghép) trước khi gửi cho LLM.

        ``sensitive``: truy vấn đã đọc cột định danh — che thêm mọi chuỗi dạng ngày (ngày sinh).
        """
        if not isinstance(value, str):
            return value
        if self._names_pattern is not None:
            value = self._names_pattern.sub("[ẩn]", value)
        if sensitive:
            value = DATE.sub("[ẩn]", value)
        return value


_snapshot = Snapshot()


def get_snapshot(db: Session) -> Snapshot:
    return _snapshot.ensure(db)

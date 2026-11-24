"""Biểu mẫu bệnh án (forms.json), kiểm tra dữ liệu gửi lên và chuyển bản ghi thành JSON cho giao diện."""

from __future__ import annotations

import json
import math
import re
from datetime import date, datetime, timezone
from pathlib import Path
from typing import Any

from .models import ClinicalPatient, ClinicalVisit

_SPEC = json.loads(Path(__file__).with_name("forms.json").read_text(encoding="utf-8"))
IDENTITY: list[dict[str, Any]] = _SPEC["identity"]
FORMS: dict[str, dict[str, Any]] = _SPEC["forms"]
TYPES = tuple(FORMS)
FIELDS: dict[str, list[dict[str, Any]]] = {
    type_: [field for section in form["sections"] for field in section["fields"]] for type_, form in FORMS.items()
}
FIELD_BY_KEY = {type_: {field["key"]: field for field in fields} for type_, fields in FIELDS.items()}
SECTION_OF = {type_: {field["key"]: section["title"] for section in form["sections"] for field in section["fields"]}
              for type_, form in FORMS.items()}
CORE_KEYS = ("code", "fullName", "age", "sex")
EXTRA_IDENTITY = [field for field in IDENTITY if field["key"] not in CORE_KEYS]
SOURCES = ("Thủ công", "OCR")
MAX_VISITS = 100
VISIT_ID = re.compile(r"^[\w-]{1,64}$")
DATE = re.compile(r"^\d{4}-\d{2}-\d{2}$")
TEXT_LIMIT = {"text": 1000, "textarea": 20000}


class ClinicalError(ValueError):
    """Dữ liệu bệnh án không hợp lệ (thông điệp hiển thị cho người dùng)."""


def code_key(code: str) -> str:
    return " ".join(code.split()).casefold()


def valid_date(value: Any) -> bool:
    if not isinstance(value, str) or not DATE.fullmatch(value):
        return False
    try:
        date.fromisoformat(value)
    except ValueError:
        return False
    return True


def _text(value: Any, limit: int, label: str) -> str:
    if value is None:
        return ""
    if isinstance(value, (int, float)) and not isinstance(value, bool):
        value = str(value)
    if not isinstance(value, str):
        raise ClinicalError(f"{label}: giá trị không hợp lệ.")
    value = value.strip()
    if len(value) > limit:
        raise ClinicalError(f"{label}: tối đa {limit} ký tự.")
    return value


def clean_value(field: dict[str, Any], value: Any) -> Any:
    """Giá trị đã chuẩn hoá của một trường; chuỗi rỗng / danh sách rỗng nghĩa là chưa nhập."""
    kind, label = field["kind"], field["label"]
    if kind == "multi":
        if value in (None, ""):
            return []
        if not isinstance(value, list) or not all(isinstance(item, str) for item in value):
            raise ClinicalError(f"{label}: giá trị không hợp lệ.")
        unknown = [item for item in value if item not in field["options"]]
        if unknown:
            raise ClinicalError(f"{label}: “{unknown[0]}” không có trong danh sách lựa chọn.")
        return [option for option in field["options"] if option in value]
    if kind == "select":
        text = _text(value, 200, label)
        if text and text not in field["options"]:
            raise ClinicalError(f"{label}: “{text}” không có trong danh sách lựa chọn.")
        return text
    if kind == "number":
        text = _text(value, 40, label).replace(",", ".")
        if text:
            try:
                number = float(text)
            except ValueError:
                raise ClinicalError(f"{label}: phải là số.") from None
            if not math.isfinite(number) or number < 0:
                raise ClinicalError(f"{label}: giá trị phải từ 0 trở lên.")
        return text
    if kind == "date":
        text = _text(value, 10, label)
        if text and not valid_date(text):
            raise ClinicalError(f"{label}: ngày không hợp lệ.")
        return text
    return _text(value, TEXT_LIMIT.get(kind, 1000), label)


def clean_fields(type_: str, values: Any) -> dict[str, Any]:
    if values is None:
        return {}
    if not isinstance(values, dict):
        raise ClinicalError("Nội dung bệnh án không hợp lệ.")
    cleaned = {}
    for key, value in values.items():
        field = FIELD_BY_KEY[type_].get(key)
        if field is None:
            continue  # trường lạ (phiên bản biểu mẫu cũ/mới) — bỏ qua
        value = clean_value(field, value)
        if value not in ("", []):
            cleaned[key] = value
    return cleaned


def clean_patient(data: Any, *, require_identity: bool) -> dict[str, Any]:
    """Kiểm tra và chuẩn hoá bệnh án gửi từ giao diện. Ném ``ClinicalError`` nếu sai."""
    if not isinstance(data, dict):
        raise ClinicalError("Dữ liệu bệnh án không hợp lệ.")
    type_ = data.get("type")
    if type_ not in FORMS:
        raise ClinicalError("Loại bệnh án không hợp lệ.")
    patient_id = data.get("id")
    if not isinstance(patient_id, str) or not VISIT_ID.fullmatch(patient_id):
        raise ClinicalError("Mã hồ sơ không hợp lệ.")
    code = _text(data.get("code"), 80, "Mã bệnh nhân")
    full_name = _text(data.get("fullName"), 200, "Họ và tên")
    age_text = _text(data.get("age"), 10, "Tuổi")
    sex = _text(data.get("sex"), 10, "Giới tính")
    if not code:
        raise ClinicalError("Vui lòng nhập mã bệnh nhân.")
    if require_identity and (not full_name or not age_text or not sex):
        raise ClinicalError("Vui lòng nhập mã bệnh nhân, họ tên, tuổi và giới tính.")
    age = None
    if age_text:
        if not re.fullmatch(r"\d{1,3}", age_text) or int(age_text) > 150:
            raise ClinicalError("Tuổi phải là số nguyên từ 0 đến 150.")
        age = int(age_text)
    if sex and sex not in ("Nam", "Nữ"):
        raise ClinicalError("Giới tính không hợp lệ.")
    identity = {}
    for field in EXTRA_IDENTITY:
        value = clean_value(field, data.get(field["key"]))
        if value not in ("", []):
            identity[field["key"]] = value

    visits_in = data.get("visits")
    if not isinstance(visits_in, list) or not visits_in:
        raise ClinicalError("Bệnh án cần ít nhất một lần khám.")
    if len(visits_in) > MAX_VISITS:
        raise ClinicalError(f"Tối đa {MAX_VISITS} lần khám cho một bệnh nhân.")
    visits, seen = [], set()
    for position, visit in enumerate(visits_in):
        if not isinstance(visit, dict):
            raise ClinicalError("Lần khám không hợp lệ.")
        visit_id = visit.get("id")
        if not isinstance(visit_id, str) or not VISIT_ID.fullmatch(visit_id) or visit_id in seen:
            raise ClinicalError("Mã lần khám không hợp lệ.")
        seen.add(visit_id)
        if not valid_date(visit.get("date")):
            raise ClinicalError("Vui lòng nhập ngày khám cho từng lần khám.")
        created = visit.get("createdAt")
        if not isinstance(created, str) or not created or len(created) > 40:
            created = datetime.now(timezone.utc).isoformat(timespec="seconds")
        visits.append({"id": visit_id, "position": position, "date": visit["date"], "createdAt": created,
                       "fields": clean_fields(type_, visit.get("fields"))})
    revision = data.get("revision")
    return {
        "id": patient_id, "type": type_, "code": code, "fullName": full_name, "age": age, "sex": sex,
        "identity": identity, "visits": visits,
        "revision": revision if isinstance(revision, int) and not isinstance(revision, bool) else 0,
    }


def _iso(value: datetime | None) -> str | None:
    if value is None:
        return None
    if value.tzinfo is None:
        value = value.replace(tzinfo=timezone.utc)
    return value.isoformat()


def serialize(patient: ClinicalPatient, original_type: str | None = None) -> dict[str, Any]:
    """Bản ghi theo đúng dạng giao diện dùng (giống bản thiết kế)."""
    data: dict[str, Any] = {
        "id": patient.id, "type": patient.type, "code": patient.code, "fullName": patient.full_name or "",
        "age": "" if patient.age is None else str(patient.age), "sex": patient.sex or "",
    }
    for field in EXTRA_IDENTITY:
        data[field["key"]] = (patient.identity or {}).get(field["key"], [] if field["kind"] == "multi" else "")
    data["visits"] = [visit_json(visit) for visit in sorted(patient.visits, key=lambda item: item.position)]
    data.update(
        revision=patient.revision, source=patient.source, needsReview=bool(patient.needs_review),
        createdAt=_iso(patient.created_at), updatedAt=_iso(patient.updated_at),
        hasOriginal=patient.document_id is not None, originalType=original_type, ocr=patient.ocr or None,
    )
    return data


def visit_json(visit: ClinicalVisit) -> dict[str, Any]:
    return {"id": visit.id, "date": visit.date.isoformat(), "createdAt": visit.created_at, "fields": visit.fields or {}}


def latest_visit(patient: ClinicalPatient) -> ClinicalVisit | None:
    visits = sorted(patient.visits, key=lambda item: (item.date, item.created_at), reverse=True)
    return visits[0] if visits else None

"""Lưu, xoá bệnh án và tạo bệnh án mới từ ảnh/PDF (model thị giác)."""

from __future__ import annotations

import hashlib
import logging
import time
import uuid
from datetime import date, datetime, timezone
from pathlib import Path
from typing import Any
from zoneinfo import ZoneInfo

from fastapi import UploadFile
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.core.config import settings
from app.modules.documents.models import Document, OcrExtraction
from app.modules.surveys.ocr.extractor import ModelResponseError
from app.modules.surveys.ocr.pages import SUPPORTED_SUFFIXES, UnreadableFileError, load_pages, media_type

from .extractor import get_clinical_extractor
from .models import ClinicalPatient, ClinicalVisit
from .schema import (
    EXTRA_IDENTITY, FIELD_BY_KEY, FORMS, ClinicalError, clean_value, code_key, valid_date,
)

logger = logging.getLogger(__name__)

STORAGE_DIR = Path("storage/clinical")
# Bệnh án scan nhiều trang (màu, 300 dpi) thường 4–12 MB; dùng chung giới hạn với tải phiếu khảo sát.
MAX_UPLOAD_MB = settings.EXTRACTION_MAX_FILE_MB
CHUNK_SIZE = 1 << 20


class ConflictError(ClinicalError):
    """Dữ liệu đã thay đổi hoặc trùng mã (HTTP 409)."""


class ExtractionUnavailable(RuntimeError):
    """Dịch vụ đọc ảnh lỗi/quá tải (HTTP 502)."""


def _now() -> datetime:
    return datetime.now(timezone.utc)


def today() -> str:
    return datetime.now(ZoneInfo("Asia/Ho_Chi_Minh")).date().isoformat()


def _ensure_unique_code(db: Session, key: str, patient_id: str) -> None:
    owner = db.scalar(select(ClinicalPatient.id).where(ClinicalPatient.code_key == key))
    if owner is not None and owner != patient_id:
        raise ConflictError("Mã bệnh nhân đã tồn tại. Vui lòng dùng mã khác.")


def save_patient(db: Session, data: dict[str, Any], create_only: bool) -> ClinicalPatient:
    """Tạo mới (``create_only``) hoặc cập nhật theo revision (khoá lạc quan). ``data`` đã qua ``clean_patient``."""
    existing = db.get(ClinicalPatient, data["id"])
    key = code_key(data["code"])
    if create_only:
        if existing is not None:
            raise ConflictError("Hồ sơ đã tồn tại. Hãy tải lại danh sách.")
        _ensure_unique_code(db, key, data["id"])
        patient = ClinicalPatient(id=data["id"], type=data["type"], revision=0, source="Thủ công",
                                  needs_review=False, created_at=_now())
        db.add(patient)
    else:
        if existing is None or existing.revision != data["revision"]:
            raise ConflictError("Hồ sơ đã thay đổi. Hãy tải lại trước khi lưu.")
        if existing.type != data["type"]:
            raise ClinicalError("Không đổi được loại bệnh án của bệnh nhân.")
        _ensure_unique_code(db, key, data["id"])
        patient = existing

    patient.code, patient.code_key = data["code"], key
    patient.full_name, patient.age, patient.sex = data["fullName"], data["age"], data["sex"]
    patient.identity = data["identity"]
    current = {visit.id: visit for visit in patient.visits}
    owned_elsewhere = set(db.scalars(select(ClinicalVisit.id).where(
        ClinicalVisit.id.in_([visit["id"] for visit in data["visits"]]), ClinicalVisit.patient_id != patient.id)))
    if owned_elsewhere:
        raise ConflictError("Mã lần khám bị trùng. Hãy tải lại trang.")
    visits = []
    for item in data["visits"]:
        visit = current.get(item["id"]) or ClinicalVisit(id=item["id"])
        visit.position, visit.date = item["position"], date.fromisoformat(item["date"])
        visit.created_at, visit.fields = item["createdAt"], item["fields"]
        visits.append(visit)
    patient.visits = visits
    patient.revision = (patient.revision or 0) + 1
    patient.updated_at = _now()
    try:
        db.commit()
    except IntegrityError as error:
        db.rollback()
        raise ConflictError("Mã bệnh nhân đã tồn tại. Vui lòng dùng mã khác.") from error
    db.refresh(patient)
    return patient


def delete_patient(db: Session, patient_id: str, revision: int) -> None:
    patient = db.get(ClinicalPatient, patient_id)
    if patient is None or patient.revision != revision:
        raise ConflictError("Hồ sơ đã thay đổi. Hãy tải lại danh sách.")
    path = None
    if patient.document_id is not None:
        document = db.get(Document, patient.document_id)
        patient.document_id = None
        db.flush()
        if document is not None:
            path = Path(document.relative_path)
            db.query(OcrExtraction).filter(OcrExtraction.document_id == document.id).delete()
            db.delete(document)
    db.delete(patient)
    db.commit()
    if path is not None:
        path.unlink(missing_ok=True)


# ---------- tải bệnh án từ ảnh/PDF ----------


def _save_upload(upload: UploadFile) -> tuple[Path, str, str]:
    name = Path(upload.filename or "").name
    suffix = Path(name).suffix.lower()
    if suffix not in SUPPORTED_SUFFIXES:
        raise ClinicalError("Vui lòng chọn ảnh JPG, PNG, WebP hoặc file PDF.")
    STORAGE_DIR.mkdir(parents=True, exist_ok=True)
    destination = STORAGE_DIR / f"{uuid.uuid4().hex}{suffix}"
    digest, size = hashlib.sha256(), 0
    try:
        with destination.open("wb") as output:
            while chunk := upload.file.read(CHUNK_SIZE):
                size += len(chunk)
                if size > MAX_UPLOAD_MB * 1024 * 1024:
                    raise ClinicalError(f"File vượt quá {MAX_UPLOAD_MB} MB.")
                digest.update(chunk)
                output.write(chunk)
        if size == 0:
            raise ClinicalError("File rỗng.")
    except BaseException:
        destination.unlink(missing_ok=True)
        raise
    return destination, name[:255] or destination.name, digest.hexdigest()


def _lenient(field: dict[str, Any], value: Any) -> Any:
    """Giá trị model đọc ra: sai định dạng thì bỏ (để trống cho người đối soát), không báo lỗi.

    Trường nhiều lựa chọn chỉ bỏ các giá trị không có trong danh sách, giữ các giá trị hợp lệ.
    """
    if field["kind"] == "multi" and isinstance(value, list):
        value = [item for item in value if item in field["options"]]
    try:
        return clean_value(field, value)
    except ClinicalError:
        return [] if field["kind"] == "multi" else ""


def build_from_extraction(type_: str, raw: dict[str, Any]) -> tuple[dict[str, Any], int, list[str], bool]:
    """(dữ liệu bệnh nhân, số trường đọc được, mục cần đối soát, ngày khám có phải suy ra không)."""
    patient_raw = raw.get("patient") or {}
    fields: dict[str, Any] = {}
    for key, value in (raw.get("fields") or {}).items():
        field = FIELD_BY_KEY[type_].get(key)
        if field is None:
            continue
        value = _lenient(field, value)
        if value not in ("", []):
            fields[key] = value
    identity = {}
    for field in EXTRA_IDENTITY:
        value = _lenient(field, patient_raw.get(field["key"]))
        if value not in ("", []):
            identity[field["key"]] = value
    code = " ".join(str(patient_raw.get("code") or "").split())[:80]
    full_name = " ".join(str(patient_raw.get("fullName") or "").split())[:200]
    age_text = "".join(ch for ch in str(patient_raw.get("age") or "") if ch.isdigit())[:3]
    age = int(age_text) if age_text and int(age_text) <= 150 else None
    sex = patient_raw.get("sex") if patient_raw.get("sex") in ("Nam", "Nữ") else ""
    count = len(fields) + len(identity) + sum(bool(value) for value in (code, full_name, age is not None, sex))
    visit_date = raw.get("visit_date")
    inferred = False
    if not valid_date(visit_date):
        visit_date = fields.get("admissionDate") if valid_date(fields.get("admissionDate")) else None
    if visit_date is None:
        visit_date, inferred = today(), True
    labels = {**{key: field["label"] for key, field in FIELD_BY_KEY[type_].items()},
              "code": "Mã bệnh nhân", "fullName": "Họ và tên", "age": "Tuổi", "sex": "Giới tính"}
    uncertain = [labels[key] for key in dict.fromkeys(raw.get("uncertain") or []) if key in labels]
    data = {"code": code, "fullName": full_name, "age": age, "sex": sex, "identity": identity,
            "visit": {"date": visit_date, "fields": fields}}
    return data, count, uncertain, inferred


def extract_patient(db: Session, type_: str, upload: UploadFile) -> ClinicalPatient:
    """Đọc ảnh/PDF bệnh án, lưu thành MỘT bệnh nhân mới (nguồn OCR, cần đối soát)."""
    if type_ not in FORMS:
        raise ClinicalError("Loại bệnh án không hợp lệ.")
    path, name, checksum = _save_upload(upload)
    try:
        try:
            pages = load_pages(path, dpi=settings.EXTRACTION_PDF_DPI, max_pages=settings.EXTRACTION_BUNDLE_MAX_PAGES)
            output = get_clinical_extractor().extract(type_, pages)
        except UnreadableFileError as error:
            raise ClinicalError(str(error)) from error
        except ClinicalError:
            raise
        except Exception as error:  # noqa: BLE001 - lỗi mạng/API/model
            logger.exception("Đọc bệnh án %s thất bại", type_)
            reason = str(error) if isinstance(error, ModelResponseError) else "dịch vụ đọc ảnh đang lỗi hoặc quá tải"
            raise ExtractionUnavailable(f"Chưa đọc được bệnh án: {reason}. Hãy thử lại sau.") from error
        raw = output.raw or {}
        check = raw.get("form_check") or {}
        if check.get("is_expected_form") is False:
            seen = f"“{check['observed_title']}”" if check.get("observed_title") else "một tài liệu khác"
            raise ClinicalError(f"File tải lên có vẻ là {seen}, không phải bệnh án {FORMS[type_]['title'].lower()}.")
        data, count, uncertain, inferred = build_from_extraction(type_, raw)
        if not count:
            raise ClinicalError("Chưa nhận dạng được trường thông tin nào. Hãy chụp rõ nhãn và nội dung bệnh án.")
        code = data["code"] or "OCR-" + format(int(time.time() * 1000), "x").upper()
        key = code_key(code)
        if db.scalar(select(ClinicalPatient.id).where(ClinicalPatient.code_key == key)) is not None:
            raise ConflictError(f"Mã bệnh nhân {code} đã có trong hệ thống. Bệnh án từ ảnh không được tạo thành hồ sơ "
                                "khác hoặc ghi đè hồ sơ có sẵn.")
        document = Document(patient_id=None, file_name=name, relative_path=str(path), mime_type=media_type(path),
                            file_type=path.suffix.lower().lstrip("."), checksum=checksum)
        db.add(document)
        db.flush()
        db.add(OcrExtraction(document_id=document.id, provider=output.provider, model=output.model, status="pending",
                             raw_result={"clinical": type_, "values": raw, "usage": output.usage}))
        now = _now()
        patient = ClinicalPatient(
            id=uuid.uuid4().hex, type=type_, code=code, code_key=key, full_name=data["fullName"], age=data["age"],
            sex=data["sex"], identity=data["identity"], source="OCR", needs_review=True, document_id=document.id,
            ocr={"sourceFile": name, "pages": pages.total_pages, "extractedCount": count, "uncertain": uncertain,
                 "notes": str(raw.get("notes") or "")[:4000], "dateInferred": inferred, "model": output.model},
            revision=1, created_at=now, updated_at=now,
        )
        patient.visits = [ClinicalVisit(id=uuid.uuid4().hex, position=0, date=date.fromisoformat(data["visit"]["date"]),
                                        created_at=now.isoformat(timespec="seconds"), fields=data["visit"]["fields"])]
        db.add(patient)
        db.commit()
    except IntegrityError as error:
        db.rollback()
        path.unlink(missing_ok=True)
        raise ConflictError("Mã bệnh nhân đã tồn tại. Vui lòng thử lại.") from error
    except BaseException:
        db.rollback()
        path.unlink(missing_ok=True)
        raise
    db.refresh(patient)
    return patient


def original_path(db: Session, patient: ClinicalPatient) -> tuple[Path, Document] | None:
    if patient.document_id is None:
        return None
    document = db.get(Document, patient.document_id)
    if document is None or not Path(document.relative_path).is_file():
        return None
    return Path(document.relative_path), document

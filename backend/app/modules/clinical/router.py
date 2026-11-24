"""API bệnh án: ``/api/v1/clinical`` (cần đăng nhập)."""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Depends, File, Form, HTTPException, Query, UploadFile
from fastapi.responses import FileResponse
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.deps import get_current_active_user
from app.modules.documents.models import Document

from .models import ClinicalPatient
from .schema import FORMS, IDENTITY, ClinicalError, clean_patient, serialize
from .service import ConflictError, ExtractionUnavailable, delete_patient, extract_patient, original_path, save_patient

router = APIRouter(dependencies=[Depends(get_current_active_user)])


class SaveRequest(BaseModel):
    patient: dict[str, Any]
    createOnly: bool = False


class DeleteRequest(BaseModel):
    id: str
    revision: int


def _original_type(mime: str | None) -> str | None:
    if not mime:
        return None
    return "pdf" if mime == "application/pdf" else "image"


def _serialize_all(db: Session, patients: list[ClinicalPatient]) -> list[dict[str, Any]]:
    ids = [patient.document_id for patient in patients if patient.document_id is not None]
    mimes = dict(db.execute(select(Document.id, Document.mime_type).where(Document.id.in_(ids))).all()) if ids else {}
    return [serialize(patient, _original_type(mimes.get(patient.document_id))) for patient in patients]


def _http(error: ClinicalError) -> HTTPException:
    return HTTPException(409 if isinstance(error, ConflictError) else 422, str(error))


@router.get("/forms")
def get_forms():
    return {"identity": IDENTITY, "forms": FORMS}


@router.get("/patients")
def list_patients(type: str | None = Query(None, max_length=3), db: Session = Depends(get_db)):
    statement = select(ClinicalPatient).order_by(ClinicalPatient.updated_at.desc())
    if type:
        if type not in FORMS:
            raise HTTPException(422, "Loại bệnh án không hợp lệ.")
        statement = statement.where(ClinicalPatient.type == type)
    return {"patients": _serialize_all(db, list(db.scalars(statement)))}


@router.get("/patient")
def get_patient(id: str = Query(max_length=64), db: Session = Depends(get_db)):
    patient = db.get(ClinicalPatient, id)
    if patient is None:
        raise HTTPException(404, "Không tìm thấy bệnh nhân.")
    return {"patient": _serialize_all(db, [patient])[0]}


@router.post("/save")
def save(body: SaveRequest, db: Session = Depends(get_db)):
    try:
        data = clean_patient(body.patient, require_identity=True)
        patient = save_patient(db, data, body.createOnly)
    except ClinicalError as error:
        raise _http(error) from error
    return {"patient": _serialize_all(db, [patient])[0]}


@router.post("/delete")
def delete(body: DeleteRequest, db: Session = Depends(get_db)):
    try:
        delete_patient(db, body.id, body.revision)
    except ClinicalError as error:
        raise _http(error) from error
    return {"ok": True}


@router.post("/extract")
def extract(type: str = Form(max_length=3), file: UploadFile = File(...), db: Session = Depends(get_db)):
    """Tải ảnh/PDF bệnh án: đọc bằng model thị giác và lưu thành một bệnh nhân mới cần đối soát."""
    try:
        patient = extract_patient(db, type, file)
    except ClinicalError as error:
        raise _http(error) from error
    except ExtractionUnavailable as error:
        raise HTTPException(502, str(error)) from error
    return {"patient": _serialize_all(db, [patient])[0]}


@router.get("/original")
def get_original(id: str = Query(max_length=64), db: Session = Depends(get_db)):
    patient = db.get(ClinicalPatient, id)
    found = original_path(db, patient) if patient is not None else None
    if found is None:
        raise HTTPException(404, "Không có file bệnh án gốc.")
    path, document = found
    return FileResponse(path, media_type=document.mime_type, filename=document.file_name,
                        content_disposition_type="inline")

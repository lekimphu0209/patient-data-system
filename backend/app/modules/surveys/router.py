from datetime import datetime, timezone

from fastapi import APIRouter, Depends, File, HTTPException, Query, UploadFile
from fastapi.responses import FileResponse, Response
from sqlalchemy import delete, select
from sqlalchemy.dialects.postgresql import insert as postgres_insert
from sqlalchemy.dialects.sqlite import insert as sqlite_insert
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session, lazyload

from app.core.database import get_db
from app.core.deps import get_current_active_user
from app.modules.documents.models import Document
from app.modules.surveys.models import SurveyRecord, SurveySubject
from app.modules.surveys.ocr.service import (
    ExtractionUnavailableError,
    SurveyExtractionError,
    discard_unsaved,
    extract_bundle,
    extract_survey,
    original_file,
    release_documents,
)
from app.modules.surveys.schemas import FORM_BY_ID, DeleteBatch, DocumentBatch, FORMS, Group, RecordBatch, RecordInput

router = APIRouter(dependencies=[Depends(get_current_active_user)])


@router.get("/forms")
def get_forms():
    return FORMS


def original_type(mime_type: str | None, has_legacy_image: bool) -> str | None:
    if mime_type:
        return "pdf" if mime_type == "application/pdf" else "image"
    return "image" if has_legacy_image else None


def serialize(record: SurveyRecord, has_ocr: bool, original: str | None, include_ocr: bool = False):
    subject = record.subject
    data = {
        "id": record.id,
        "person": record.person,
        "group": record.group,
        "form": record.form,
        "patient": {
            "fullName": subject.full_name,
            "birthDate": subject.birth_date or "",
            "birthYear": subject.birth_year,
            "hometown": subject.hometown,
        },
        "unit": record.unit,
        "date": record.date,
        "source": record.source,
        "status": record.status,
        "conclusion": record.conclusion,
        "answers": record.answers,
        "note": record.note,
        "updatedAt": record.updated_at.replace(tzinfo=timezone.utc),
        "hasOCR": has_ocr,
        "hasOriginal": original is not None,
        "originalType": original,
    }
    if include_ocr:
        data["ocr"] = record.ocr
    return data


def record_rows(db: Session, *conditions):
    """Bản ghi kèm cờ OCR và loại file gốc, không phải nạp các cột văn bản/ảnh nặng."""
    statement = (
        select(
            SurveyRecord,
            SurveyRecord.ocr.is_not(None),
            SurveyRecord.ocr_image.is_not(None),
            Document.mime_type,
        )
        .outerjoin(Document, SurveyRecord.document_id == Document.id)
        .where(*conditions)
    )
    return db.execute(statement)


@router.get("/records")
def list_records(db: Session = Depends(get_db)):
    return [
        serialize(record, has_ocr, original_type(mime, legacy))
        for record, has_ocr, legacy, mime in record_rows(db)
    ]


@router.get("/record")
def get_record(id: str = Query(max_length=120), db: Session = Depends(get_db)):
    row = record_rows(db, SurveyRecord.id == id).first()
    if row is None:
        raise HTTPException(404, "Phiếu khảo sát không còn tồn tại.")
    record, has_ocr, legacy, mime = row
    return serialize(record, has_ocr, original_type(mime, legacy), include_ocr=True)


@router.post("/extract")
def extract(
    form: str = Query(max_length=3),
    file: UploadFile = File(...),
    db: Session = Depends(get_db),
):
    """Bóc tách một phiếu đã điền (ảnh/PDF) thành bản nháp; chưa tạo bản ghi."""
    definition = FORM_BY_ID.get(form)
    if definition is None:
        raise HTTPException(422, "Mã biểu mẫu không hợp lệ.")
    try:
        return extract_survey(db, definition, file).to_dict()
    except SurveyExtractionError as error:
        raise HTTPException(422, str(error)) from error
    except ExtractionUnavailableError as error:
        raise HTTPException(502, str(error)) from error


@router.post("/extract-bundle")
def extract_bundle_file(
    group: Group = Query(),
    file: UploadFile = File(...),
    db: Session = Depends(get_db),
):
    """Tách một file chứa nhiều phiếu của MỘT người thành từng phiếu rồi bóc tách; chưa tạo bản ghi."""
    forms = [form for form in FORMS if form["group"] == group]
    try:
        return extract_bundle(db, group, forms, file).to_dict()
    except SurveyExtractionError as error:
        raise HTTPException(422, str(error)) from error
    except ExtractionUnavailableError as error:
        raise HTTPException(502, str(error)) from error


@router.post("/discard-documents")
def discard_documents(batch: DocumentBatch, db: Session = Depends(get_db)):
    """Xoá file đã bóc tách mà người dùng không lưu thành phiếu."""
    files = discard_unsaved(db, set(batch.ids))
    db.commit()
    for path in files:
        path.unlink(missing_ok=True)
    return {"count": len(files)}


@router.get("/original")
def get_original(id: str = Query(max_length=120), db: Session = Depends(get_db)):
    record = db.get(SurveyRecord, id)
    if record is None:
        raise HTTPException(404, "Phiếu khảo sát không còn tồn tại.")
    original = original_file(db, record)
    if original is None:
        raise HTTPException(404, "Phiếu này không có file gốc hoặc file đã bị xoá khỏi máy chủ.")
    if original.path:
        return FileResponse(
            original.path,
            media_type=original.media_type,
            filename=original.file_name,
            content_disposition_type="inline",
        )
    return Response(original.content, media_type=original.media_type)


def save_subjects(db: Session, records: list[RecordInput], *, merge: bool) -> None:
    subjects = {(record.group, record.person): record.patient for record in records}
    insert = sqlite_insert if db.bind.dialect.name == "sqlite" else postgres_insert
    for (group, person), patient in sorted(subjects.items()):
        values = {
            "full_name": patient.fullName,
            "birth_date": patient.birthDate or None,
            "birth_year": patient.birthYear,
            "hometown": patient.hometown,
        }
        statement = insert(SurveySubject.__table__).values(subject_group=group, person=person, **values)
        changes = {name: value for name, value in values.items() if value or not merge}
        if changes:
            statement = statement.on_conflict_do_update(
                index_elements=["subject_group", "person"], set_=changes
            )
        else:
            statement = statement.on_conflict_do_nothing(index_elements=["subject_group", "person"])
        db.execute(statement)


def write_record(row: SurveyRecord, data: RecordInput) -> None:
    for name in ("unit", "date", "status", "conclusion", "answers", "note"):
        setattr(row, name, getattr(data, name))
    row.updated_at = datetime.now(timezone.utc)


@router.post("/records", status_code=201)
def create_records(batch: RecordBatch, db: Session = Depends(get_db)):
    if len({record.id for record in batch.records}) != len(batch.records):
        raise HTTPException(409, "Mã phiếu bị trùng trong dữ liệu nhập.")
    documents = {record.documentId for record in batch.records if record.documentId}
    if documents and len(set(db.scalars(select(Document.id).where(Document.id.in_(documents))))) != len(documents):
        raise HTTPException(422, "File gốc của phiếu không còn trên máy chủ. Hãy tải file lên lại.")
    try:
        save_subjects(db, batch.records, merge=True)
        for data in batch.records:
            row = SurveyRecord(
                id=data.id, person=data.person, group=data.group, form=data.form,
                source=data.source, ocr=data.ocr, ocr_image=data.ocrImage, document_id=data.documentId,
            )
            write_record(row, data)
            db.add(row)
        db.commit()
    except IntegrityError as error:
        db.rollback()
        raise HTTPException(409, "Mã phiếu đã tồn tại. Hãy kiểm tra dữ liệu nhập.") from error
    return {"count": len(batch.records)}


@router.put("/record")
def update_record(data: RecordInput, db: Session = Depends(get_db)):
    row = db.scalar(
        select(SurveyRecord).options(lazyload(SurveyRecord.subject))
        .where(SurveyRecord.id == data.id).with_for_update()
    )
    if row is None:
        raise HTTPException(404, "Phiếu khảo sát không còn tồn tại.")
    if (data.group, data.person, data.form) != (row.group, row.person, row.form):
        raise HTTPException(422, "Mã đối tượng và loại biểu mẫu của phiếu đã được cố định.")
    if data.updatedAt != row.updated_at.replace(tzinfo=timezone.utc):
        raise HTTPException(409, "Phiếu đã thay đổi. Hãy mở lại phiếu để sửa tiếp.")
    save_subjects(db, [data], merge=False)
    write_record(row, data)
    db.commit()
    return {"count": 1}


@router.post("/delete")
def delete_records(batch: DeleteBatch, db: Session = Depends(get_db)):
    documents = set(db.scalars(
        select(SurveyRecord.document_id)
        .where(SurveyRecord.id.in_(batch.ids), SurveyRecord.document_id.is_not(None))
    ))
    result = db.execute(delete(SurveyRecord).where(SurveyRecord.id.in_(batch.ids)))
    files = release_documents(db, documents)
    db.commit()
    for path in files:
        path.unlink(missing_ok=True)
    return {"count": result.rowcount}

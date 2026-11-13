from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import delete, select
from sqlalchemy.dialects.postgresql import insert as postgres_insert
from sqlalchemy.dialects.sqlite import insert as sqlite_insert
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session, lazyload

from app.core.database import get_db
from app.core.deps import get_current_active_user
from app.modules.surveys.models import SurveyRecord, SurveySubject
from app.modules.surveys.schemas import DeleteBatch, FORMS, RecordBatch, RecordInput

router = APIRouter(dependencies=[Depends(get_current_active_user)])


@router.get("/forms")
def get_forms():
    return FORMS


def serialize(record: SurveyRecord, has_ocr: bool, include_ocr: bool = False):
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
    }
    if include_ocr:
        data.update(ocr=record.ocr, ocrImage=record.ocr_image)
    return data


@router.get("/records")
def list_records(db: Session = Depends(get_db)):
    records = db.execute(select(SurveyRecord, SurveyRecord.ocr.is_not(None)))
    return [serialize(record, has_ocr) for record, has_ocr in records]


@router.get("/record")
def get_record(id: str = Query(max_length=120), db: Session = Depends(get_db)):
    record = db.get(SurveyRecord, id)
    if record is None:
        raise HTTPException(404, "Phiếu khảo sát không còn tồn tại.")
    return serialize(record, bool(record.ocr), include_ocr=True)


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
    try:
        save_subjects(db, batch.records, merge=True)
        for data in batch.records:
            row = SurveyRecord(
                id=data.id, person=data.person, group=data.group, form=data.form,
                source=data.source, ocr=data.ocr, ocr_image=data.ocrImage,
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
    result = db.execute(delete(SurveyRecord).where(SurveyRecord.id.in_(batch.ids)))
    db.commit()
    return {"count": result.rowcount}

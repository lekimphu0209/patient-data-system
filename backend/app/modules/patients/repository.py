from datetime import date
from typing import Any

from sqlalchemy import or_
from sqlalchemy.orm import Session

from app.modules.patients.models import Patient, Examination, MedicalHistory
from app.modules.patients.schemas import (
    PatientCreate,
    PatientUpdate,
    ExaminationCreate,
    ExaminationUpdate,
    MedicalHistoryCreate,
    MedicalHistoryUpdate,
)


class PatientRepository:
    def __init__(self, db: Session):
        self.db = db

    def get_by_id(self, patient_id: int) -> Patient | None:
        return (
            self.db.query(Patient)
            .filter(Patient.id == patient_id, Patient.deleted_at.is_(None))
            .first()
        )

    def get_by_patient_code(self, patient_code: str) -> Patient | None:
        return (
            self.db.query(Patient)
            .filter(Patient.patient_code == patient_code, Patient.deleted_at.is_(None))
            .first()
        )

    def _apply_filters(
        self,
        query,
        search: str | None = None,
        diagnosis: str | None = None,
        disease_type: str | None = None,
        birth_date_from: date | None = None,
        birth_date_to: date | None = None,
    ):
        if search:
            like = f"%{search}%"
            query = query.filter(
                or_(
                    Patient.full_name.ilike(like),
                    Patient.patient_code.ilike(like),
                    Patient.diagnosis.ilike(like),
                )
            )
        if diagnosis:
            query = query.filter(Patient.diagnosis.ilike(f"%{diagnosis}%"))
        if disease_type:
            query = query.filter(Patient.disease_type.ilike(f"%{disease_type}%"))
        if birth_date_from:
            query = query.filter(Patient.birth_date >= birth_date_from)
        if birth_date_to:
            query = query.filter(Patient.birth_date <= birth_date_to)
        return query

    def get_list(
        self,
        page: int,
        limit: int,
        search: str | None = None,
        diagnosis: str | None = None,
        disease_type: str | None = None,
        birth_date_from: date | None = None,
        birth_date_to: date | None = None,
    ) -> tuple[list[Patient], int]:
        query = self._apply_filters(
            self.db.query(Patient).filter(Patient.deleted_at.is_(None)),
            search=search,
            diagnosis=diagnosis,
            disease_type=disease_type,
            birth_date_from=birth_date_from,
            birth_date_to=birth_date_to,
        )
        total = query.count()
        # Deterministic ordering: without it, OFFSET/LIMIT paging can repeat or
        # skip rows between requests.
        items = (
            query.order_by(Patient.created_at.desc(), Patient.id.desc())
            .offset((page - 1) * limit)
            .limit(limit)
            .all()
        )
        return items, total

    def get_all(
        self,
        search: str | None = None,
        diagnosis: str | None = None,
        disease_type: str | None = None,
        birth_date_from: date | None = None,
        birth_date_to: date | None = None,
    ) -> list[Patient]:
        query = self._apply_filters(
            self.db.query(Patient).filter(Patient.deleted_at.is_(None)),
            search=search,
            diagnosis=diagnosis,
            disease_type=disease_type,
            birth_date_from=birth_date_from,
            birth_date_to=birth_date_to,
        )
        return query.order_by(Patient.created_at.desc(), Patient.id.desc()).all()

    def _to_model_kwargs(self, data: dict[str, Any]) -> dict[str, Any]:
        kwargs = dict(data)
        if "metadata" in kwargs:
            kwargs["patient_metadata"] = kwargs.pop("metadata")
        return kwargs

    def create(self, data: PatientCreate) -> Patient:
        patient = Patient(**self._to_model_kwargs(data.model_dump(exclude_unset=True)))
        self.db.add(patient)
        self.db.commit()
        self.db.refresh(patient)
        return patient

    def update(self, patient: Patient, data: PatientUpdate) -> Patient:
        update_data = self._to_model_kwargs(data.model_dump(exclude_unset=True))
        for field, value in update_data.items():
            setattr(patient, field, value)
        self.db.commit()
        self.db.refresh(patient)
        return patient

    def delete(self, patient: Patient, hard: bool = False) -> None:
        if hard:
            self.db.delete(patient)
        else:
            from datetime import datetime, timezone
            patient.deleted_at = datetime.now(timezone.utc)
            self.db.add(patient)
        self.db.commit()

    def bulk_delete_by_patient_codes(self, patient_codes: list[str], hard: bool = False) -> int:
        patients = (
            self.db.query(Patient)
            .filter(Patient.patient_code.in_(patient_codes), Patient.deleted_at.is_(None))
            .all()
        )
        if hard:
            for p in patients:
                self.db.delete(p)
        else:
            from datetime import datetime, timezone
            for p in patients:
                p.deleted_at = datetime.now(timezone.utc)
        self.db.commit()
        return len(patients)


class ExaminationRepository:
    def __init__(self, db: Session):
        self.db = db

    def get_by_id(self, exam_id: int) -> Examination | None:
        return self.db.query(Examination).filter(Examination.id == exam_id).first()

    def get_list_by_patient(
        self, patient_id: int, page: int, limit: int
    ) -> tuple[list[Examination], int]:
        query = self.db.query(Examination).filter(Examination.patient_id == patient_id)
        total = query.count()
        items = (
            query.order_by(Examination.exam_date.desc(), Examination.id.desc())
            .offset((page - 1) * limit)
            .limit(limit)
            .all()
        )
        return items, total

    def count_by_patient(self, patient_id: int) -> int:
        return (
            self.db.query(Examination).filter(Examination.patient_id == patient_id).count()
        )

    def get_metric_rows_by_patient(self, patient_id: int, limit: int):
        """Chỉ 3 cột cần cho biểu đồ diễn biến, sắp xếp tăng dần theo thời gian.

        Khi hồ sơ vượt trần thì lấy các lần khám *mới nhất* rồi mới đảo lại thứ
        tự — phần đáng cắt của một hồ sơ quá dài là các lần khám cũ.
        """
        rows = (
            self.db.query(Examination.id, Examination.exam_date, Examination.data)
            .filter(Examination.patient_id == patient_id)
            .order_by(Examination.exam_date.desc(), Examination.id.desc())
            .limit(limit)
            .all()
        )
        return [(row.id, row.exam_date, row.data) for row in reversed(rows)]

    def get_latest_by_patient(self, patient_id: int) -> Examination | None:
        return (
            self.db.query(Examination)
            .filter(Examination.patient_id == patient_id)
            .order_by(Examination.exam_date.desc(), Examination.id.desc())
            .first()
        )

    def create(self, patient_id: int, data: ExaminationCreate) -> Examination:
        # Schema có field phụ không phải cột (extraction_id) nên lọc theo cột thật.
        columns = {column.name for column in Examination.__table__.columns}
        payload = {
            key: value
            for key, value in data.model_dump(exclude_unset=True).items()
            if key in columns
        }
        exam = Examination(patient_id=patient_id, **payload)
        self.db.add(exam)
        self.db.commit()
        self.db.refresh(exam)
        return exam

    def update(self, exam: Examination, data: ExaminationUpdate) -> Examination:
        for field, value in data.model_dump(exclude_unset=True).items():
            setattr(exam, field, value)
        self.db.commit()
        self.db.refresh(exam)
        return exam

    def delete(self, exam: Examination) -> None:
        self.db.delete(exam)
        self.db.commit()


class MedicalHistoryRepository:
    def __init__(self, db: Session):
        self.db = db

    def get_by_patient_id(self, patient_id: int) -> MedicalHistory | None:
        return self.db.query(MedicalHistory).filter(MedicalHistory.patient_id == patient_id).first()

    def create(self, patient_id: int, data: MedicalHistoryCreate) -> MedicalHistory:
        history = MedicalHistory(patient_id=patient_id, **data.model_dump(exclude_unset=True))
        self.db.add(history)
        self.db.commit()
        self.db.refresh(history)
        return history

    def update(self, history: MedicalHistory, data: MedicalHistoryUpdate) -> MedicalHistory:
        for field, value in data.model_dump(exclude_unset=True).items():
            setattr(history, field, value)
        self.db.commit()
        self.db.refresh(history)
        return history

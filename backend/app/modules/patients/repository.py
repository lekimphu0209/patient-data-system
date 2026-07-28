from sqlalchemy import or_
from sqlalchemy.orm import Session

from app.modules.patients.models import Patient
from app.modules.patients.schemas import PatientCreate, PatientUpdate


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

    def get_list(
        self, page: int, limit: int, search: str | None = None
    ) -> tuple[list[Patient], int]:
        query = self.db.query(Patient).filter(Patient.deleted_at.is_(None))
        if search:
            like = f"%{search}%"
            query = query.filter(
                or_(Patient.full_name.ilike(like), Patient.patient_code.ilike(like))
            )
        total = query.count()
        items = query.offset((page - 1) * limit).limit(limit).all()
        return items, total

    def create(self, data: PatientCreate) -> Patient:
        patient = Patient(**data.model_dump(exclude_unset=True))
        self.db.add(patient)
        self.db.commit()
        self.db.refresh(patient)
        return patient

    def update(self, patient: Patient, data: PatientUpdate) -> Patient:
        update_data = data.model_dump(exclude_unset=True)
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

    def bulk_delete_by_ids(self, ids: list[int], hard: bool = False) -> int:
        patients = (
            self.db.query(Patient).filter(Patient.id.in_(ids), Patient.deleted_at.is_(None)).all()
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

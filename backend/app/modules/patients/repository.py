from datetime import date
from typing import Any

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

from datetime import date

from sqlalchemy.orm import Session

from app.modules.patients.models import Patient
from app.modules.patients.repository import PatientRepository
from app.modules.patients.schemas import PatientCreate, PatientUpdate
from app.shared.exceptions import ConflictException, NotFoundException


def _compute_age(birth_date: date | None) -> int | None:
    if not birth_date:
        return None
    today = date.today()
    return today.year - birth_date.year - ((today.month, today.day) < (birth_date.month, birth_date.day))


class PatientService:
    def __init__(self, db: Session):
        self.repo = PatientRepository(db)

    def list_patients(
        self,
        page: int,
        limit: int,
        search: str | None = None,
        diagnosis: str | None = None,
        disease_type: str | None = None,
        birth_date_from: date | None = None,
        birth_date_to: date | None = None,
    ):
        return self.repo.get_list(
            page=page,
            limit=limit,
            search=search,
            diagnosis=diagnosis,
            disease_type=disease_type,
            birth_date_from=birth_date_from,
            birth_date_to=birth_date_to,
        )

    def get_patient(self, patient_id: int) -> Patient:
        patient = self.repo.get_by_id(patient_id)
        if not patient:
            raise NotFoundException("Patient not found")
        return patient

    def create_patient(self, data: PatientCreate) -> Patient:
        existing = self.repo.get_by_patient_code(data.patient_code)
        if existing:
            raise ConflictException("Patient code already exists")
        create_payload = data.model_dump(exclude_unset=True)
        if create_payload.get("age") is None and create_payload.get("birth_date"):
            create_payload["age"] = _compute_age(create_payload["birth_date"])
        return self.repo.create(PatientCreate(**create_payload))

    def update_patient(self, patient_id: int, data: PatientUpdate) -> Patient:
        patient = self.repo.get_by_id(patient_id)
        if not patient:
            raise NotFoundException("Patient not found")
        if data.patient_code:
            existing = self.repo.get_by_patient_code(data.patient_code)
            if existing and existing.id != patient_id:
                raise ConflictException("Patient code already exists")
        return self.repo.update(patient, data)

    def delete_patient(self, patient_id: int, hard: bool = False) -> None:
        patient = self.repo.get_by_id(patient_id)
        if not patient:
            raise NotFoundException("Patient not found")
        self.repo.delete(patient, hard=hard)

    def bulk_delete_patients(self, patient_codes: list[str], hard: bool = False) -> int:
        return self.repo.bulk_delete_by_patient_codes(patient_codes, hard=hard)

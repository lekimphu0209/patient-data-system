from datetime import date

from sqlalchemy.orm import Session

from app.modules.patients.models import Patient, Examination, MedicalHistory
from app.modules.patients.repository import (
    PatientRepository,
    ExaminationRepository,
    MedicalHistoryRepository,
)
from app.modules.patients.schemas import (
    PatientCreate,
    PatientUpdate,
    ExaminationCreate,
    ExaminationUpdate,
    MedicalHistoryCreate,
    MedicalHistoryUpdate,
)
from app.shared.exceptions import ConflictException, NotFoundException


def _resolve_exam_date(data: ExaminationCreate | ExaminationUpdate) -> date | None:
    """Ngày khám nằm trong ``data.exam_info.exam_date`` của form động; cột
    ``exam_date`` vẫn được ghi để còn sắp xếp/lọc bằng SQL."""
    if data.exam_date:
        return data.exam_date
    raw = ((data.data or {}).get("exam_info") or {}).get("exam_date")
    if not raw:
        return None
    if isinstance(raw, date):
        return raw
    try:
        return date.fromisoformat(str(raw)[:10])
    except ValueError:
        return None


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


class ExaminationService:
    def __init__(self, db: Session):
        self.repo = ExaminationRepository(db)
        self.patient_repo = PatientRepository(db)

    def list_examinations(self, patient_id: int, page: int, limit: int):
        patient = self.patient_repo.get_by_id(patient_id)
        if not patient:
            raise NotFoundException("Patient not found")
        return self.repo.get_list_by_patient(patient_id, page, limit)

    def get_examination(self, exam_id: int) -> Examination:
        exam = self.repo.get_by_id(exam_id)
        if not exam:
            raise NotFoundException("Examination not found")
        return exam

    def get_latest_examination(self, patient_id: int) -> Examination | None:
        patient = self.patient_repo.get_by_id(patient_id)
        if not patient:
            raise NotFoundException("Patient not found")
        return self.repo.get_latest_by_patient(patient_id)

    def create_examination(self, patient_id: int, data: ExaminationCreate) -> Examination:
        patient = self.patient_repo.get_by_id(patient_id)
        if not patient:
            raise NotFoundException("Patient not found")
        data.exam_date = _resolve_exam_date(data) or date.today()
        exam = self.repo.create(patient_id, data)

        # Lần khám tạo từ bản nháp OCR/upload: ghi lại bản đã được bác sĩ soát.
        if data.extraction_id:
            from app.modules.documents.exam_extraction_service import ExamExtractionService

            ExamExtractionService(self.repo.db).mark_reviewed(
                data.extraction_id, data.data or {}
            )
        return exam

    def update_examination(self, exam_id: int, data: ExaminationUpdate) -> Examination:
        exam = self.repo.get_by_id(exam_id)
        if not exam:
            raise NotFoundException("Examination not found")
        resolved = _resolve_exam_date(data)
        if resolved:
            data.exam_date = resolved
        return self.repo.update(exam, data)

    def delete_examination(self, exam_id: int) -> None:
        exam = self.repo.get_by_id(exam_id)
        if not exam:
            raise NotFoundException("Examination not found")
        self.repo.delete(exam)


class MedicalHistoryService:
    def __init__(self, db: Session):
        self.repo = MedicalHistoryRepository(db)
        self.patient_repo = PatientRepository(db)

    def get_medical_history(self, patient_id: int) -> MedicalHistory | None:
        patient = self.patient_repo.get_by_id(patient_id)
        if not patient:
            raise NotFoundException("Patient not found")
        return self.repo.get_by_patient_id(patient_id)

    def create_medical_history(self, patient_id: int, data: MedicalHistoryCreate) -> MedicalHistory:
        patient = self.patient_repo.get_by_id(patient_id)
        if not patient:
            raise NotFoundException("Patient not found")
        existing = self.repo.get_by_patient_id(patient_id)
        if existing:
            return self.repo.update(existing, data)
        return self.repo.create(patient_id, data)

    def update_medical_history(
        self, patient_id: int, data: MedicalHistoryUpdate
    ) -> MedicalHistory:
        history = self.repo.get_by_patient_id(patient_id)
        if not history:
            history = self.repo.create(patient_id, MedicalHistoryCreate(**data.model_dump(exclude_unset=True)))
        else:
            history = self.repo.update(history, data)
        return history

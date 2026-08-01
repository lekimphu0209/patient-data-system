from datetime import date, datetime
from typing import Any, Optional

from pydantic import AliasChoices, BaseModel, ConfigDict, Field


class PatientBase(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    patient_code: str = Field(..., min_length=1, max_length=50)
    full_name: str = Field(..., min_length=1, max_length=255)
    birth_date: Optional[date] = None
    age: Optional[int] = None
    disease_type: Optional[str] = None
    diagnosis: Optional[str] = None
    hometown: Optional[str] = None
    status: str = "active"
    contact_info: Optional[dict[str, Any]] = None
    # Tên field khớp với cột model để request và response dùng chung một khóa;
    # vẫn chấp nhận "metadata" cho client cũ.
    patient_metadata: Optional[dict[str, Any]] = Field(
        default=None, validation_alias=AliasChoices("patient_metadata", "metadata")
    )


class PatientCreate(PatientBase):
    pass


class PatientUpdate(BaseModel):
    patient_code: Optional[str] = Field(default=None, min_length=1, max_length=50)
    full_name: Optional[str] = Field(default=None, min_length=1, max_length=255)
    birth_date: Optional[date] = None
    age: Optional[int] = None
    disease_type: Optional[str] = None
    diagnosis: Optional[str] = None
    hometown: Optional[str] = None
    status: Optional[str] = None
    contact_info: Optional[dict[str, Any]] = None
    patient_metadata: Optional[dict[str, Any]] = Field(
        default=None, validation_alias=AliasChoices("patient_metadata", "metadata")
    )


class PatientResponse(PatientBase):
    model_config = ConfigDict(from_attributes=True, populate_by_name=True)

    id: int
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None


class PatientBulkDeleteRequest(BaseModel):
    patient_codes: list[str]


class MedicalHistoryBase(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    presenting_symptoms: Optional[dict[str, Any]] = None
    onset_age: Optional[int] = None
    disease_duration_years: Optional[int] = None
    disease_duration_months: Optional[int] = None
    previous_diagnoses: Optional[list[str]] = None
    disease_progression: Optional[str] = None
    relapse_count: Optional[int] = None
    previous_inpatient_treatments: Optional[int] = None
    medications_before_admission: Optional[dict[str, Any]] = None
    reinforcement_status: Optional[str] = None
    circumstances_of_onset: Optional[str] = None
    personal_history: Optional[dict[str, Any]] = None
    family_history: Optional[dict[str, Any]] = None
    data: Optional[dict[str, Any]] = None


class MedicalHistoryCreate(MedicalHistoryBase):
    pass


class MedicalHistoryUpdate(BaseModel):
    presenting_symptoms: Optional[dict[str, Any]] = None
    onset_age: Optional[int] = None
    disease_duration_years: Optional[int] = None
    disease_duration_months: Optional[int] = None
    previous_diagnoses: Optional[list[str]] = None
    disease_progression: Optional[str] = None
    relapse_count: Optional[int] = None
    previous_inpatient_treatments: Optional[int] = None
    medications_before_admission: Optional[dict[str, Any]] = None
    reinforcement_status: Optional[str] = None
    circumstances_of_onset: Optional[str] = None
    personal_history: Optional[dict[str, Any]] = None
    family_history: Optional[dict[str, Any]] = None
    data: Optional[dict[str, Any]] = None


class MedicalHistoryResponse(MedicalHistoryBase):
    model_config = ConfigDict(from_attributes=True)

    id: int
    patient_id: int
    created_at: datetime
    updated_at: datetime


class ExaminationBase(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    exam_date: date
    general_condition: Optional[str] = None
    cardiovascular: Optional[str] = None
    respiratory: Optional[str] = None
    digestive: Optional[str] = None
    urinary: Optional[str] = None
    neurological: Optional[str] = None
    other_body_parts: Optional[str] = None
    mental_exam: Optional[dict[str, Any]] = None
    general_clinical_tests: Optional[dict[str, Any]] = None
    other_clinical_tests: Optional[dict[str, Any]] = None
    diagnosis: Optional[str] = None
    treatment: Optional[str] = None
    data: Optional[dict[str, Any]] = None
    source: str = "manual"
    document_id: Optional[int] = None


class ExaminationCreate(ExaminationBase):
    exam_date: Optional[date] = None
    # Chỉ dùng để đánh dấu bản nháp đã được soát; không phải cột của bảng.
    extraction_id: Optional[int] = None


class ExaminationUpdate(BaseModel):
    exam_date: Optional[date] = None
    general_condition: Optional[str] = None
    cardiovascular: Optional[str] = None
    respiratory: Optional[str] = None
    digestive: Optional[str] = None
    urinary: Optional[str] = None
    neurological: Optional[str] = None
    other_body_parts: Optional[str] = None
    mental_exam: Optional[dict[str, Any]] = None
    general_clinical_tests: Optional[dict[str, Any]] = None
    other_clinical_tests: Optional[dict[str, Any]] = None
    diagnosis: Optional[str] = None
    treatment: Optional[str] = None
    data: Optional[dict[str, Any]] = None


class ExaminationResponse(ExaminationBase):
    model_config = ConfigDict(from_attributes=True)

    id: int
    patient_id: int
    created_at: datetime
    updated_at: datetime

from datetime import date, datetime
from typing import Any, Optional

from pydantic import BaseModel, ConfigDict, Field


class PatientBase(BaseModel):
    patient_code: str = Field(..., min_length=1, max_length=50)
    full_name: str = Field(..., min_length=1, max_length=255)
    birth_date: Optional[date] = None
    age: Optional[int] = None
    disease_type: Optional[str] = None
    diagnosis: Optional[str] = None
    status: str = "active"
    contact_info: Optional[dict[str, Any]] = None
    metadata: Optional[dict[str, Any]] = None


class PatientCreate(PatientBase):
    pass


class PatientUpdate(BaseModel):
    patient_code: Optional[str] = Field(default=None, min_length=1, max_length=50)
    full_name: Optional[str] = Field(default=None, min_length=1, max_length=255)
    birth_date: Optional[date] = None
    age: Optional[int] = None
    disease_type: Optional[str] = None
    diagnosis: Optional[str] = None
    status: Optional[str] = None
    contact_info: Optional[dict[str, Any]] = None
    metadata: Optional[dict[str, Any]] = None


class PatientResponse(PatientBase):
    model_config = ConfigDict(from_attributes=True)

    id: int
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None

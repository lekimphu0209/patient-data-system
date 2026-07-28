from datetime import date, datetime
from typing import Any, Optional

from pydantic import BaseModel, ConfigDict, Field


class EncounterBase(BaseModel):
    visit_date: date
    source_type: str = "manual"
    summary: Optional[str] = None
    form_data: Optional[dict[str, Any]] = None
    status: str = "draft"


class EncounterCreate(EncounterBase):
    patient_id: int = Field(..., gt=0)


class EncounterUpdate(BaseModel):
    visit_date: Optional[date] = None
    source_type: Optional[str] = None
    summary: Optional[str] = None
    form_data: Optional[dict[str, Any]] = None
    status: Optional[str] = None


class EncounterResponse(EncounterBase):
    model_config = ConfigDict(from_attributes=True)

    id: int
    patient_id: int
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None

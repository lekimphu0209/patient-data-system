from typing import Any

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.deps import get_current_active_user
from app.modules.auth.models import User
from app.modules.patients.schemas import (
    PatientCreate,
    PatientResponse,
    PatientUpdate,
)
from app.modules.patients.service import PatientService
from app.shared.responses import ApiResponse, PaginatedResponse, PaginationMeta

router = APIRouter()


@router.get("", response_model=PaginatedResponse)
def list_patients(
    page: int = Query(1, ge=1),
    limit: int = Query(20, ge=1, le=100),
    q: str | None = Query(None, description="Search by name or patient code"),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
):
    service = PatientService(db)
    items, total = service.list_patients(page=page, limit=limit, search=q)
    meta = PaginationMeta(
        page=page, limit=limit, total=total, total_pages=(total + limit - 1) // limit
    )
    return PaginatedResponse(
        data=[PatientResponse.model_validate(item) for item in items],
        pagination=meta,
    )


@router.post("", response_model=ApiResponse[PatientResponse], status_code=201)
def create_patient(
    data: PatientCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
):
    service = PatientService(db)
    patient = service.create_patient(data)
    return ApiResponse(data=PatientResponse.model_validate(patient))


@router.get("/{patient_id}", response_model=ApiResponse[PatientResponse])
def get_patient(
    patient_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
):
    service = PatientService(db)
    patient = service.get_patient(patient_id)
    return ApiResponse(data=PatientResponse.model_validate(patient))


@router.patch("/{patient_id}", response_model=ApiResponse[PatientResponse])
def update_patient(
    patient_id: int,
    data: PatientUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
):
    service = PatientService(db)
    patient = service.update_patient(patient_id, data)
    return ApiResponse(data=PatientResponse.model_validate(patient))


@router.delete("/{patient_id}")
def delete_patient(
    patient_id: int,
    hard: bool = Query(False),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
):
    service = PatientService(db)
    service.delete_patient(patient_id, hard=hard)
    return {"message": "Patient deleted"}


@router.post("/bulk-delete")
def bulk_delete_patients(
    payload: dict[str, Any],
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
):
    ids = payload.get("ids", [])
    service = PatientService(db)
    count = service.bulk_delete_patients(ids)
    return {"message": f"Deleted {count} patients"}

from datetime import date
from pathlib import Path
from typing import Any

from fastapi import APIRouter, Depends, File, Query, UploadFile
from fastapi.responses import FileResponse
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.deps import get_current_active_user
from app.modules.auth.models import User
from app.modules.import_export.schemas import ExportRequest
from app.modules.import_export.service import ImportExportService
from app.modules.patients.schemas import (
    PatientBulkDeleteRequest,
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
    q: str | None = Query(None, description="Search by name, code or diagnosis"),
    diagnosis: str | None = Query(None, description="Filter by diagnosis"),
    disease_type: str | None = Query(None, description="Filter by disease type"),
    birth_date_from: date | None = Query(None, description="Filter from birth date"),
    birth_date_to: date | None = Query(None, description="Filter to birth date"),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
):
    service = PatientService(db)
    items, total = service.list_patients(
        page=page,
        limit=limit,
        search=q,
        diagnosis=diagnosis,
        disease_type=disease_type,
        birth_date_from=birth_date_from,
        birth_date_to=birth_date_to,
    )
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


@router.delete("")
def bulk_delete_patients(
    request: PatientBulkDeleteRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
):
    service = PatientService(db)
    count = service.bulk_delete_patients(request.patient_codes)
    return {"message": f"Deleted {count} patients"}


@router.post("/export")
def export_patients(
    request: ExportRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
):
    service = ImportExportService(db)
    filepath = service.export_patients(
        current_user=current_user,
        ids=request.ids,
        format=request.format,
        q=request.q,
        diagnosis=request.diagnosis,
        disease_type=request.disease_type,
        birth_date_from=request.birth_date_from,
        birth_date_to=request.birth_date_to,
    )
    filename = Path(filepath).name
    return {
        "download_url": f"/api/v1/patients/export/download?path={filepath}",
        "filename": filename,
    }


@router.get("/export/download")
def download_export(
    path: str = Query(...),
    current_user: User = Depends(get_current_active_user),
):
    filename = Path(path).name
    if filename.endswith(".xlsx"):
        media_type = "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
    elif filename.endswith(".csv"):
        media_type = "text/csv"
    else:
        media_type = "application/octet-stream"
    return FileResponse(path, filename=filename, media_type=media_type)


@router.post("/import")
def import_patients_preview(
    file: UploadFile = File(...),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
):
    service = ImportExportService(db)
    return service.preview_import_patients(file)


@router.post("/import/commit")
def import_patients_commit(
    payload: dict[str, Any],
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
):
    service = ImportExportService(db)
    rows = payload.get("rows", [])
    return service.commit_import_patients(rows)


@router.get("/import/template")
def download_import_template(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
):
    service = ImportExportService(db)
    filepath = service.get_template()
    filename = Path(filepath).name
    return FileResponse(filepath, filename=filename)

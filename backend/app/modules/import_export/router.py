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

router = APIRouter()


@router.post("/imports/patients")
def import_patients_preview(
    file: UploadFile = File(...),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
):
    service = ImportExportService(db)
    return service.preview_import_patients(file)


@router.post("/imports/{import_id}/commit")
def import_patients_commit(
    import_id: str,
    payload: dict[str, Any],
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
):
    service = ImportExportService(db)
    rows = payload.get("rows", [])
    return service.commit_import_patients(rows)


@router.get("/imports/template")
def download_import_template(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
):
    service = ImportExportService(db)
    filepath = service.get_template()
    return FileResponse(filepath, filename="patients_import_template.xlsx")


@router.post("/exports/patients")
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
        "download_url": f"/api/v1/exports/download?path={filepath}",
        "filename": filename,
    }


@router.get("/exports/download")
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

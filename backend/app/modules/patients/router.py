from dataclasses import asdict
from datetime import date, datetime
from pathlib import Path
from typing import Any

from fastapi import APIRouter, Depends, File, HTTPException, Query, UploadFile
from fastapi.responses import FileResponse, StreamingResponse
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.deps import get_current_active_user
from app.modules.auth.models import User
from app.modules.documents.exam_extraction_service import (
    ExamExtractionService,
    ExtractionError,
)
from app.modules.import_export.schemas import ExportRequest
from app.modules.import_export.service import EXPORT_DIR, ImportExportService
from app.modules.patients.schemas import (
    PatientBulkDeleteRequest,
    PatientCreate,
    PatientResponse,
    PatientUpdate,
    ExaminationCreate,
    ExaminationMetricsResponse,
    ExaminationResponse,
    ExaminationUpdate,
    MedicalHistoryCreate,
    MedicalHistoryResponse,
    MedicalHistoryUpdate,
)
from app.modules.patients.service import PatientService, ExaminationService, MedicalHistoryService
from app.modules.patients.form_service import FormService
from app.modules.patients.export_service import ExaminationExportService
from app.modules.patients.metrics_service import ExaminationMetricsService
from app.shared.responses import ApiResponse, PaginatedResponse, PaginationMeta

router = APIRouter()

XLSX_MEDIA_TYPE = "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"


# ==================== Form Schema Endpoints ====================


@router.get("/forms/{disease_code}", response_model=ApiResponse[Any])
def get_form_schema_by_disease(
    disease_code: str,
    current_user: User = Depends(get_current_active_user),
):
    """Schema bệnh án (cả 3 khối) đã lọc theo mã bệnh: f20 / f32 / normal."""
    form_service = FormService()
    if not form_service.is_valid_disease(disease_code):
        raise HTTPException(status_code=400, detail="Unknown disease code")
    return ApiResponse(data=form_service.get_schema(disease_code))


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


@router.get("/{patient_id}/form-schema", response_model=ApiResponse[Any])
def get_patient_form_schema(
    patient_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
):
    """Schema bệnh án ứng với chẩn đoán của chính bệnh nhân này."""
    patient = PatientService(db).get_patient(patient_id)
    form_service = FormService()
    disease_code = form_service.resolve_disease_code(
        patient.diagnosis, patient.disease_type
    )
    return ApiResponse(data=form_service.get_schema(disease_code))


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


# ==================== Examination Endpoints ====================


@router.get("/{patient_id}/exams", response_model=PaginatedResponse)
def list_examinations(
    patient_id: int,
    page: int = Query(1, ge=1),
    limit: int = Query(10, ge=1, le=100),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
):
    service = ExaminationService(db)
    items, total = service.list_examinations(patient_id, page, limit)
    meta = PaginationMeta(
        page=page, limit=limit, total=total, total_pages=(total + limit - 1) // limit
    )
    return PaginatedResponse(
        data=[ExaminationResponse.model_validate(item) for item in items],
        pagination=meta,
    )


# --- Bóc tách phiếu khám (OCR ảnh/scan & đọc file digital) ---
# Ba route dưới phải đứng trước "/{patient_id}/exams/{exam_id}", nếu không
# "extract"/"extractions" sẽ bị khớp nhầm vào exam_id và trả 422.


@router.post("/{patient_id}/exams/extract", response_model=ApiResponse[Any])
def extract_exam_document(
    patient_id: int,
    mode: str = Query(..., pattern="^(ocr|upload)$"),
    file: UploadFile = File(...),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
):
    """Upload phiếu khám và bóc tách thành bản nháp chờ bác sĩ soát.

    Chưa tạo lần khám nào ở bước này — chỉ tạo sau khi người dùng bấm Lưu.
    """
    service = ExamExtractionService(db)
    try:
        draft = service.extract(patient_id, file, mode)
    except ExtractionError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    return ApiResponse(data=asdict(draft))


@router.get("/{patient_id}/exams/extractions/{extraction_id}", response_model=ApiResponse[Any])
def get_exam_extraction(
    patient_id: int,
    extraction_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
):
    """Đọc lại bản nháp — để màn hình soát tải lại được sau khi refresh."""
    service = ExamExtractionService(db)
    try:
        draft = service.get_draft(patient_id, extraction_id)
    except ExtractionError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    return ApiResponse(data=asdict(draft))


@router.get("/{patient_id}/documents/{document_id}/file")
def get_patient_document_file(
    patient_id: int,
    document_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
):
    """Trả file gốc để hiển thị ở khung xem trước của màn hình soát."""
    path, document = ExamExtractionService(db).document_path(patient_id, document_id)
    return FileResponse(
        path,
        media_type=document.mime_type or "application/octet-stream",
        filename=document.file_name,
        content_disposition_type="inline",
    )


@router.get("/{patient_id}/exams/export")
def export_examinations(
    patient_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
):
    """Xuất toàn bộ lần khám của bệnh nhân ra Excel (2 sheet: bảng + chi tiết)."""
    patient = PatientService(db).get_patient(patient_id)
    exams, _ = ExaminationService(db).list_examinations(patient_id, page=1, limit=10_000)

    exported_by = getattr(current_user, "full_name", None) or current_user.email
    stream = ExaminationExportService().build_workbook(patient, exams, exported_by)

    stamp = datetime.now().strftime("%Y%m%d_%H%M")
    filename = f"kham_benh_{patient.patient_code}_{stamp}.xlsx"
    return StreamingResponse(
        stream,
        media_type=XLSX_MEDIA_TYPE,
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )


@router.get(
    "/{patient_id}/exams/metrics", response_model=ApiResponse[ExaminationMetricsResponse]
)
def get_examination_metrics(
    patient_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
):
    """Chuỗi số liệu của các chỉ số dạng số theo trục thời gian khám.

    Chỉ trả về những chỉ số bệnh nhân thật sự có dữ liệu, dạng gọn (nhãn + đơn vị
    + các cặp ngày/giá trị) để client vẽ biểu đồ mà không phải tải toàn bộ bản
    ghi lần khám.
    """
    return ApiResponse(data=ExaminationMetricsService(db).build_series(patient_id))


@router.get("/{patient_id}/exams/latest", response_model=ApiResponse[ExaminationResponse | None])
def get_latest_examination(
    patient_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
):
    service = ExaminationService(db)
    exam = service.get_latest_examination(patient_id)
    return ApiResponse(data=ExaminationResponse.model_validate(exam) if exam else None)


@router.get("/{patient_id}/exams/{exam_id}", response_model=ApiResponse[ExaminationResponse])
def get_examination(
    patient_id: int,
    exam_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
):
    service = ExaminationService(db)
    exam = service.get_examination(exam_id)
    if exam.patient_id != patient_id:
        raise HTTPException(status_code=404, detail="Examination not found")
    return ApiResponse(data=ExaminationResponse.model_validate(exam))


@router.post("/{patient_id}/exams", response_model=ApiResponse[ExaminationResponse], status_code=201)
def create_examination(
    patient_id: int,
    data: ExaminationCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
):
    service = ExaminationService(db)
    exam = service.create_examination(patient_id, data)
    return ApiResponse(data=ExaminationResponse.model_validate(exam))


@router.patch("/{patient_id}/exams/{exam_id}", response_model=ApiResponse[ExaminationResponse])
def update_examination(
    patient_id: int,
    exam_id: int,
    data: ExaminationUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
):
    service = ExaminationService(db)
    exam = service.update_examination(exam_id, data)
    if exam.patient_id != patient_id:
        raise HTTPException(status_code=404, detail="Examination not found")
    return ApiResponse(data=ExaminationResponse.model_validate(exam))


@router.delete("/{patient_id}/exams/{exam_id}")
def delete_examination(
    patient_id: int,
    exam_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
):
    service = ExaminationService(db)
    exam = service.get_examination(exam_id)
    if exam.patient_id != patient_id:
        raise HTTPException(status_code=404, detail="Examination not found")
    service.delete_examination(exam_id)
    return {"message": "Examination deleted"}


# ==================== Medical History Endpoints ====================


@router.get("/{patient_id}/medical-history", response_model=ApiResponse[MedicalHistoryResponse | None])
def get_medical_history(
    patient_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
):
    service = MedicalHistoryService(db)
    history = service.get_medical_history(patient_id)
    return ApiResponse(
        data=MedicalHistoryResponse.model_validate(history) if history else None
    )


@router.post("/{patient_id}/medical-history", response_model=ApiResponse[MedicalHistoryResponse], status_code=201)
def create_or_update_medical_history(
    patient_id: int,
    data: MedicalHistoryCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
):
    service = MedicalHistoryService(db)
    history = service.create_medical_history(patient_id, data)
    return ApiResponse(data=MedicalHistoryResponse.model_validate(history))


@router.patch("/{patient_id}/medical-history", response_model=ApiResponse[MedicalHistoryResponse])
def update_medical_history(
    patient_id: int,
    data: MedicalHistoryUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
):
    service = MedicalHistoryService(db)
    history = service.update_medical_history(patient_id, data)
    return ApiResponse(data=MedicalHistoryResponse.model_validate(history))


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
    # `path` comes back from the client, so confine it to the export directory
    # instead of serving any file the API process can read.
    export_dir = EXPORT_DIR.resolve()
    requested = Path(path).resolve()
    if not requested.is_relative_to(export_dir) or not requested.is_file():
        raise HTTPException(status_code=404, detail="Không tìm thấy file cần tải.")

    filename = requested.name
    if filename.endswith(".xlsx"):
        media_type = XLSX_MEDIA_TYPE
    elif filename.endswith(".csv"):
        media_type = "text/csv"
    else:
        media_type = "application/octet-stream"
    return FileResponse(requested, filename=filename, media_type=media_type)


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
    return FileResponse(
        filepath, filename=Path(filepath).name, media_type=XLSX_MEDIA_TYPE
    )

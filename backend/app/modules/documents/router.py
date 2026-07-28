from fastapi import APIRouter, Depends, File, UploadFile
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.deps import get_current_active_user
from app.modules.auth.models import User
from app.modules.documents.schemas import DocumentUploadResponse, ExtractionResult
from app.modules.documents.service import DocumentService

router = APIRouter()


@router.post("/upload", response_model=DocumentUploadResponse)
def upload_document(
    patient_id: int | None = None,
    file: UploadFile = File(...),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
):
    service = DocumentService(db)
    return service.save_upload(patient_id=patient_id, file=file)


@router.post("/{document_id}/extract", response_model=ExtractionResult)
def extract_document(
    document_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
):
    service = DocumentService(db)
    result = service.extract_stub(document_id)
    return ExtractionResult(
        document_id=document_id,
        provider="stub",
        raw_result=result,
    )

import os
import shutil
import uuid
from pathlib import Path

from fastapi import UploadFile
from sqlalchemy.orm import Session

from app.modules.documents.extractor.stub import StubExtractor
from app.modules.documents.models import Document
from app.modules.documents.repository import DocumentRepository
from app.modules.documents.schemas import DocumentUploadResponse

STORAGE_DIR = Path("storage/patients")


class DocumentService:
    def __init__(self, db: Session):
        self.repo = DocumentRepository(db)

    def save_upload(
        self, patient_id: int | None, file: UploadFile
    ) -> DocumentUploadResponse:
        STORAGE_DIR.mkdir(parents=True, exist_ok=True)
        ext = Path(file.filename or "unknown").suffix
        unique_name = f"{uuid.uuid4().hex}{ext}"
        dest_path = STORAGE_DIR / unique_name

        with dest_path.open("wb") as buffer:
            shutil.copyfileobj(file.file, buffer)

        doc = self.repo.create(
            patient_id=patient_id,
            file_name=file.filename or unique_name,
            relative_path=str(dest_path),
            mime_type=file.content_type or "application/octet-stream",
        )
        return DocumentUploadResponse.model_validate(doc)

    def extract_stub(self, document_id: int) -> dict:
        doc = self.repo.get_by_id(document_id)
        if not doc:
            raise ValueError("Document not found")
        extractor = StubExtractor()
        result = extractor.extract(doc.relative_path)
        self.repo.create_extraction(
            document_id=document_id,
            provider="stub",
            raw_result=result,
        )
        return result

from sqlalchemy.orm import Session

from app.modules.documents.models import Document, OcrExtraction


class DocumentRepository:
    def __init__(self, db: Session):
        self.db = db

    def create(self, patient_id: int | None, file_name: str, relative_path: str, mime_type: str) -> Document:
        doc = Document(
            patient_id=patient_id,
            file_name=file_name,
            relative_path=relative_path,
            mime_type=mime_type,
        )
        self.db.add(doc)
        self.db.commit()
        self.db.refresh(doc)
        return doc

    def get_by_id(self, document_id: int) -> Document | None:
        return self.db.query(Document).filter(Document.id == document_id).first()

    def create_extraction(self, document_id: int, provider: str, raw_result: dict) -> OcrExtraction:
        extraction = OcrExtraction(
            document_id=document_id,
            provider=provider,
            raw_result=raw_result,
        )
        self.db.add(extraction)
        self.db.commit()
        self.db.refresh(extraction)
        return extraction

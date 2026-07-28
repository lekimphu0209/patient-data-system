from app.modules.documents.extractor.interface import DocumentExtractor


class StubExtractor(DocumentExtractor):
    def extract(self, file_path: str, template_version: str | None = None) -> dict:
        return {
            "patient_code": "STUB-001",
            "full_name": "Nguyễn Văn A",
            "birth_date": "1990-01-01",
            "diagnosis": "Stub diagnosis",
            "note": "This is stub OCR output for local development.",
        }

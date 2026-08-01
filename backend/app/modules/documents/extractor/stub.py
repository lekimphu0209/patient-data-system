from datetime import date

from app.modules.documents.extractor.base import ExamExtractor, ExtractionOutcome
from app.modules.documents.extractor.file_reader import DocumentContent
from app.modules.documents.extractor.interface import DocumentExtractor
from app.modules.documents.extractor.schema_spec import (
    KIND_DATE,
    KIND_MANY_OF,
    KIND_NUMBER,
    KIND_ONE_OF,
    FieldSpec,
)


class StubExtractor(DocumentExtractor):
    def extract(self, file_path: str, template_version: str | None = None) -> dict:
        return {
            "patient_code": "STUB-001",
            "full_name": "Nguyễn Văn A",
            "birth_date": "1990-01-01",
            "diagnosis": "Stub diagnosis",
            "note": "This is stub OCR output for local development.",
        }


class StubExamExtractor(ExamExtractor):
    """Bộ bóc tách giả lập — chạy trọn luồng khi chưa có API key.

    Điền khoảng một nửa số trường theo quy tắc cố định (không random) nên kết quả
    ổn định giữa các lần chạy: tiện cho test tự động và cho việc thử giao diện.
    """

    FILL_EVERY = 2

    def extract(
        self, content: DocumentContent, specs: list[FieldSpec], disease_label: str
    ) -> ExtractionOutcome:
        raw: dict[str, object] = {}
        for index, spec in enumerate(specs):
            if index % self.FILL_EVERY:
                continue

            if spec.kind == KIND_NUMBER:
                raw[spec.path] = 10 + index % 50
            elif spec.kind == KIND_DATE:
                raw[spec.path] = date.today().isoformat()
            elif spec.kind == KIND_ONE_OF and spec.options:
                raw[spec.path] = spec.options[index % len(spec.options)][0]
            elif spec.kind == KIND_MANY_OF and spec.options:
                raw[spec.path] = [spec.options[0][0]]
            else:
                raw[spec.path] = f"[stub] {spec.label}"

        return ExtractionOutcome(raw_result=raw, provider="stub", model="stub")

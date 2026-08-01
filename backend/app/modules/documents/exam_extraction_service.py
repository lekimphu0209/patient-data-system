"""Điều phối luồng bóc tách phiếu khám.

    upload file  ->  đọc nội dung  ->  model bóc tách  ->  kiểm & ép kiểu  ->  bản nháp chờ soát

Bản nháp được lưu vào ``ocr_extractions`` (``raw_result`` = model trả về,
``reviewed_result`` = sau khi bác sĩ sửa). Chưa tạo lần khám nào cho tới khi
người dùng bấm Lưu ở màn hình soát — nên upload nhầm file cũng không làm bẩn dữ liệu.
"""

from __future__ import annotations

import logging
import shutil
import uuid
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from fastapi import UploadFile
from sqlalchemy.orm import Session

from app.core.config import settings
from app.modules.documents.extractor.factory import MODES, get_extractor, resolve_provider
from app.modules.documents.extractor.file_reader import (
    SUPPORTED_SUFFIXES,
    UnsupportedFileError,
    read_document,
)
from app.modules.documents.extractor.schema_spec import (
    build_field_specs,
    coerce_extraction,
    count_filled,
)
from app.modules.documents.models import Document, OcrExtraction
from app.modules.patients.form_service import FormService
from app.modules.patients.models import Patient
from app.shared.exceptions import NotFoundException

logger = logging.getLogger(__name__)

STORAGE_DIR = Path("storage/uploads")

STATUS_PENDING = "pending"
STATUS_REVIEWED = "reviewed"


class ExtractionError(ValueError):
    """Lỗi người dùng sửa được: sai định dạng, file rỗng, quá nặng..."""


@dataclass
class ExtractionDraft:
    extraction_id: int
    document_id: int
    file_name: str
    mime_type: str
    mode: str
    provider: str
    model: str
    page_count: int
    filled_count: int
    total_fields: int
    data: dict[str, Any]
    warnings: list[str] = field(default_factory=list)
    note: str = ""


class ExamExtractionService:
    def __init__(self, db: Session):
        self.db = db
        self.form_service = FormService()

    # ---------- helper ----------

    def _patient(self, patient_id: int) -> Patient:
        patient = self.db.query(Patient).filter(Patient.id == patient_id).first()
        if not patient:
            raise NotFoundException("Patient not found")
        return patient

    def _exam_block(self, patient: Patient) -> tuple[dict[str, Any], str]:
        code = self.form_service.resolve_disease_code(patient.diagnosis, patient.disease_type)
        schema = self.form_service.get_schema(code)
        block = next((b for b in schema["blocks"] if b["id"] == "examination"), None)
        if block is None:
            raise ExtractionError("Không tìm thấy biểu mẫu khám bệnh cho bệnh nhân này.")
        return block, schema["disease_label"]

    def _save_file(self, patient_id: int, file: UploadFile) -> Document:
        suffix = Path(file.filename or "").suffix.lower()
        if suffix not in SUPPORTED_SUFFIXES:
            supported = ", ".join(sorted(SUPPORTED_SUFFIXES))
            raise ExtractionError(
                f"Không hỗ trợ định dạng “{suffix or file.filename}”. Chấp nhận: {supported}."
            )

        STORAGE_DIR.mkdir(parents=True, exist_ok=True)
        dest = STORAGE_DIR / f"{uuid.uuid4().hex}{suffix}"
        with dest.open("wb") as buffer:
            shutil.copyfileobj(file.file, buffer)

        size_mb = dest.stat().st_size / (1024 * 1024)
        if size_mb > settings.EXTRACTION_MAX_FILE_MB:
            dest.unlink(missing_ok=True)
            raise ExtractionError(
                f"File nặng {size_mb:.1f}MB, vượt giới hạn {settings.EXTRACTION_MAX_FILE_MB}MB."
            )
        if dest.stat().st_size == 0:
            dest.unlink(missing_ok=True)
            raise ExtractionError("File rỗng.")

        document = Document(
            patient_id=patient_id,
            file_name=file.filename or dest.name,
            relative_path=str(dest),
            mime_type=file.content_type or "application/octet-stream",
            file_type=suffix.lstrip("."),
        )
        self.db.add(document)
        self.db.commit()
        self.db.refresh(document)
        return document

    # ---------- luồng chính ----------

    def extract(self, patient_id: int, file: UploadFile, mode: str) -> ExtractionDraft:
        if mode not in MODES:
            raise ExtractionError(f"Chế độ “{mode}” không hợp lệ.")

        patient = self._patient(patient_id)
        block, disease_label = self._exam_block(patient)
        specs = build_field_specs(block)

        document = self._save_file(patient_id, file)

        try:
            content = read_document(
                document.relative_path,
                prefer="images" if mode == "ocr" else "text",
                dpi=settings.EXTRACTION_PDF_DPI,
                max_pages=settings.EXTRACTION_MAX_PAGES,
            )
        except UnsupportedFileError as exc:
            raise ExtractionError(str(exc)) from exc

        if content.is_empty:
            raise ExtractionError(
                "Không đọc được nội dung nào từ file. Nếu đây là bản scan, hãy dùng nút OCR."
            )

        extractor = get_extractor(mode, vision=content.kind == "images")
        try:
            outcome = extractor.extract(content, specs, disease_label)
        except Exception as exc:  # noqa: BLE001 - báo lại cho người dùng, có log đầy đủ
            logger.exception("Bóc tách thất bại cho document %s", document.id)
            raise ExtractionError(f"Bóc tách thất bại: {exc}") from exc

        data, warnings = coerce_extraction(outcome.raw_result, specs)

        extraction = OcrExtraction(
            document_id=document.id,
            provider=outcome.provider,
            model=outcome.model,
            raw_result={
                "mode": mode,
                "content_kind": content.kind,
                "page_count": content.page_count,
                "usage": outcome.usage,
                "values": outcome.raw_result,
                "warnings": warnings,
            },
            status=STATUS_PENDING,
        )
        self.db.add(extraction)
        self.db.commit()
        self.db.refresh(extraction)

        return ExtractionDraft(
            extraction_id=extraction.id,
            document_id=document.id,
            file_name=document.file_name,
            mime_type=document.mime_type,
            mode=mode,
            provider=outcome.provider,
            model=outcome.model,
            page_count=content.page_count,
            filled_count=count_filled(data),
            total_fields=len(specs),
            data=data,
            warnings=warnings,
            note=content.note,
        )

    def get_draft(self, patient_id: int, extraction_id: int) -> ExtractionDraft:
        """Đọc lại bản nháp — để màn hình soát tải lại được sau khi F5."""
        patient = self._patient(patient_id)
        extraction = (
            self.db.query(OcrExtraction).filter(OcrExtraction.id == extraction_id).first()
        )
        if not extraction:
            raise NotFoundException("Extraction not found")

        document = (
            self.db.query(Document).filter(Document.id == extraction.document_id).first()
        )
        if not document or document.patient_id != patient.id:
            raise NotFoundException("Extraction not found")

        block, _ = self._exam_block(patient)
        specs = build_field_specs(block)
        raw = extraction.raw_result or {}

        # Đã soát rồi thì hiện lại bản đã sửa, chưa thì hiện bản model đọc.
        if extraction.reviewed_result:
            data, warnings = extraction.reviewed_result, []
        else:
            data, warnings = coerce_extraction(raw.get("values", {}), specs)

        return ExtractionDraft(
            extraction_id=extraction.id,
            document_id=document.id,
            file_name=document.file_name,
            mime_type=document.mime_type,
            mode=raw.get("mode", "ocr"),
            provider=extraction.provider or "",
            model=extraction.model or "",
            page_count=raw.get("page_count", 1),
            filled_count=count_filled(data),
            total_fields=len(specs),
            data=data,
            warnings=raw.get("warnings", warnings),
        )

    def mark_reviewed(self, extraction_id: int, reviewed: dict[str, Any]) -> None:
        extraction = (
            self.db.query(OcrExtraction).filter(OcrExtraction.id == extraction_id).first()
        )
        if not extraction:
            return
        extraction.reviewed_result = reviewed
        extraction.status = STATUS_REVIEWED
        self.db.commit()

    def document_path(self, patient_id: int, document_id: int) -> tuple[Path, Document]:
        document = self.db.query(Document).filter(Document.id == document_id).first()
        if not document or document.patient_id != patient_id:
            raise NotFoundException("Document not found")
        path = Path(document.relative_path)
        if not path.is_file():
            raise NotFoundException("File không còn trên máy chủ.")
        return path, document

    @staticmethod
    def provider_for(mode: str) -> str:
        return resolve_provider(mode)

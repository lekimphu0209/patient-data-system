"""Điều phối bóc tách một phiếu khảo sát và quản lý file gốc.

    lưu file -> render trang -> model đọc -> chuẩn hoá -> bản nháp trả về giao diện

Bước này chưa tạo bản ghi khảo sát: giao diện nhận bản nháp, ghép mã đối tượng
rồi tạo bản ghi kèm ``documentId``. Bóc tách lỗi thì file vừa lưu bị xoá ngay
để không để lại rác.
"""

from __future__ import annotations

import base64
import binascii
import hashlib
import logging
import re
import uuid
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any

from fastapi import UploadFile
from sqlalchemy import delete, select
from sqlalchemy.orm import Session

from app.core.config import settings
from app.modules.documents.models import Document, OcrExtraction
from app.modules.surveys.models import SurveyRecord
from app.modules.surveys.ocr.extractor import ModelResponseError, get_survey_extractor
from app.modules.surveys.ocr.pages import (
    SUPPORTED_SUFFIXES,
    PageSet,
    UnreadableFileError,
    load_pages,
    media_type,
)
from app.modules.surveys.ocr.schema import Extraction, normalize

logger = logging.getLogger(__name__)

STORAGE_DIR = Path("storage/surveys")
CHUNK_SIZE = 1 << 20
LEGACY_IMAGE = re.compile(r"data:(image/jpeg);base64,([A-Za-z0-9+/]+={0,2})")


class SurveyExtractionError(ValueError):
    """Lỗi người dùng tự sửa được: sai định dạng, file hỏng, nhầm mẫu phiếu..."""


class ExtractionUnavailableError(RuntimeError):
    """Dịch vụ bóc tách lỗi hoặc quá tải — người dùng chỉ có thể thử lại sau."""


@dataclass
class SurveyDraft:
    documentId: int
    fileName: str
    pageCount: int
    pagesRead: list[int]
    model: str
    subject: dict[str, str | None]
    answers: dict[str, str | list[str]]
    uncertain: list[str]
    notes: str
    warnings: list[str] = field(default_factory=list)
    summary: str = ""

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


def extract_survey(db: Session, form: dict[str, Any], upload: UploadFile) -> SurveyDraft:
    document = _store(db, upload)
    try:
        pages = load_pages(
            document.relative_path,
            dpi=settings.EXTRACTION_PDF_DPI,
            max_pages=settings.EXTRACTION_MAX_PAGES,
        )
        output = get_survey_extractor().extract(form, pages)
        result = normalize(form, output.raw)
        if not result.is_expected_form:
            seen = f"“{result.observed_title}”" if result.observed_title else "một mẫu khác"
            raise SurveyExtractionError(
                f"File tải lên có vẻ là {seen}, không phải mẫu “{form['title']}”. "
                "Hãy chọn đúng loại phiếu rồi tải lại."
            )
        if result.is_empty:
            raise SurveyExtractionError(
                "Không đọc được câu trả lời nào trên phiếu. Hãy kiểm tra file đúng là phiếu "
                "đã điền và đủ rõ nét."
            )
    except UnreadableFileError as exc:
        _discard(db, document)
        raise SurveyExtractionError(str(exc)) from exc
    except SurveyExtractionError:
        _discard(db, document)
        raise
    except Exception as exc:  # noqa: BLE001 - lỗi mạng/API/model: log đầy đủ, báo gọn
        _discard(db, document)
        logger.exception("Bóc tách phiếu %s thất bại", form["id"])
        reason = str(exc) if isinstance(exc, ModelResponseError) else "dịch vụ bóc tách đang lỗi hoặc quá tải"
        raise ExtractionUnavailableError(f"Chưa bóc tách được phiếu: {reason}. Hãy thử lại sau.") from exc

    warnings = _warnings(pages)
    db.add(OcrExtraction(
        document_id=document.id,
        provider=output.provider,
        model=output.model,
        raw_result={"form": form["id"], "values": output.raw, "usage": output.usage, "warnings": warnings},
        status="pending",
    ))
    db.commit()
    return SurveyDraft(
        documentId=document.id,
        fileName=document.file_name,
        pageCount=pages.total_pages,
        pagesRead=[page.number for page in pages.pages],
        model=output.model,
        subject=result.subject,
        answers=result.answers,
        uncertain=result.uncertain,
        notes=result.notes,
        warnings=warnings,
        summary=_summary(form, document, pages, output.model, result, warnings),
    )


def _store(db: Session, upload: UploadFile) -> Document:
    name = Path(upload.filename or "").name
    suffix = Path(name).suffix.lower()
    if suffix not in SUPPORTED_SUFFIXES:
        raise SurveyExtractionError("Chỉ hỗ trợ ảnh JPG, PNG, WebP hoặc file PDF.")

    STORAGE_DIR.mkdir(parents=True, exist_ok=True)
    destination = STORAGE_DIR / f"{uuid.uuid4().hex}{suffix}"
    limit = settings.EXTRACTION_MAX_FILE_MB * 1024 * 1024
    digest = hashlib.sha256()
    size = 0
    try:
        with destination.open("wb") as output:
            while chunk := upload.file.read(CHUNK_SIZE):
                size += len(chunk)
                if size > limit:
                    raise SurveyExtractionError(f"File vượt giới hạn {settings.EXTRACTION_MAX_FILE_MB} MB.")
                digest.update(chunk)
                output.write(chunk)
        if size == 0:
            raise SurveyExtractionError("File rỗng.")
    except BaseException:
        destination.unlink(missing_ok=True)
        raise

    document = Document(
        patient_id=None,
        file_name=name[:255] or destination.name,
        relative_path=str(destination),
        mime_type=media_type(destination),
        file_type=suffix.lstrip("."),
        checksum=digest.hexdigest(),
    )
    db.add(document)
    db.commit()
    db.refresh(document)
    return document


def _discard(db: Session, document: Document) -> None:
    db.rollback()
    path = Path(document.relative_path)
    db.execute(delete(OcrExtraction).where(OcrExtraction.document_id == document.id))
    db.execute(delete(Document).where(Document.id == document.id))
    db.commit()
    path.unlink(missing_ok=True)


def _warnings(pages: PageSet) -> list[str]:
    warnings = []
    if pages.truncated:
        warnings.append(
            f"File có {pages.total_pages} trang, chỉ đọc {len(pages.pages)} trang có nội dung đầu tiên."
        )
    if pages.skipped_blank:
        warnings.append("Bỏ qua trang trắng: " + ", ".join(map(str, pages.skipped_blank)) + ".")
    return warnings


def _summary(
    form: dict[str, Any],
    document: Document,
    pages: PageSet,
    model: str,
    result: Extraction,
    warnings: list[str],
) -> str:
    labels = {question["id"]: question["label"] for question in form["questions"]}
    read = ", ".join(str(page.number) for page in pages.pages)
    lines = [
        f"Trích xuất tự động từ file “{document.file_name}” ({pages.total_pages} trang, đã đọc trang {read}).",
        f"Mô hình: {model}.",
    ]
    if result.uncertain:
        lines.append("Cần đối soát với phiếu gốc:")
        lines += [f"- {key}: {_shorten(labels.get(key, 'thông tin định danh'))}" for key in result.uncertain]
    if result.notes:
        lines.append(f"Ghi chú khi đọc phiếu: {result.notes}")
    lines += warnings
    return "\n".join(lines)


def _shorten(text: str, limit: int = 90) -> str:
    if len(text) <= limit:
        return text
    return text[:limit].rsplit(" ", 1)[0].rstrip(" ,.;:") + "…"


def release_documents(db: Session, document_ids: set[int]) -> list[Path]:
    """Xoá bản ghi file của các phiếu vừa bị xoá; trả về đường dẫn để xoá sau khi commit.

    Chỉ xoá file không còn phiếu nào dùng.
    """
    if not document_ids:
        return []
    still_used = set(db.scalars(
        select(SurveyRecord.document_id).where(SurveyRecord.document_id.in_(document_ids))
    ))
    unused = document_ids - still_used
    if not unused:
        return []
    paths = [Path(path) for path in db.scalars(select(Document.relative_path).where(Document.id.in_(unused)))]
    db.execute(delete(OcrExtraction).where(OcrExtraction.document_id.in_(unused)))
    db.execute(delete(Document).where(Document.id.in_(unused)))
    return paths


@dataclass
class OriginalFile:
    media_type: str
    file_name: str
    path: Path | None = None
    content: bytes | None = None


def original_file(db: Session, record: SurveyRecord) -> OriginalFile | None:
    """File gốc của phiếu: file đã upload, hoặc ảnh base64 của luồng OCR cũ."""
    if record.document_id:
        document = db.get(Document, record.document_id)
        if document and Path(document.relative_path).is_file():
            return OriginalFile(
                media_type=document.mime_type,
                file_name=document.file_name,
                path=Path(document.relative_path),
            )
        return None
    match = LEGACY_IMAGE.fullmatch(record.ocr_image or "")
    if not match:
        return None
    try:
        content = base64.b64decode(match.group(2), validate=True)
    except binascii.Error:
        return None
    return OriginalFile(media_type=match.group(1), file_name=f"{record.id}.jpg", content=content)

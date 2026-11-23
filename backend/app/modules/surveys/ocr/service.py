"""Điều phối bóc tách phiếu khảo sát và quản lý file gốc.

Một phiếu:   lưu file -> render trang -> model đọc -> chuẩn hoá -> bản nháp
Nhiều phiếu: lưu file -> render trang -> model nhận diện mẫu từng trang -> tách
             thành từng phiếu -> đọc song song -> mỗi phiếu một file gốc riêng

Bước này chưa tạo bản ghi khảo sát: giao diện nhận bản nháp, ghép mã đối tượng
rồi tạo bản ghi kèm ``documentId``. File và bản ghi ``Document`` chỉ được giữ lại
khi đọc thành công; lỗi ở bất kỳ bước nào thì xoá sạch để không để lại rác.
"""

from __future__ import annotations

import base64
import binascii
import hashlib
import logging
import re
import unicodedata
import uuid
from concurrent.futures import ThreadPoolExecutor
from contextlib import contextmanager
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any

from fastapi import UploadFile
from sqlalchemy import delete, select
from sqlalchemy.orm import Session

from app.core.config import settings
from app.modules.documents.models import Document, OcrExtraction
from app.modules.surveys.models import SurveyRecord
from app.modules.surveys.ocr.bundle import FormPart, MultipleCopiesError, page_ranges, plan_bundle
from app.modules.surveys.ocr.extractor import ModelOutput, ModelResponseError, get_survey_extractor
from app.modules.surveys.ocr.pages import (
    SUPPORTED_SUFFIXES,
    PageSet,
    UnreadableFileError,
    load_pages,
    media_type,
)
from app.modules.surveys.ocr.schema import SUBJECT_FIELDS, Extraction, canonical_code, code_key, normalize

logger = logging.getLogger(__name__)

STORAGE_DIR = Path("storage/surveys")
CHUNK_SIZE = 1 << 20
LEGACY_IMAGE = re.compile(r"data:(image/jpeg);base64,([A-Za-z0-9+/]+={0,2})")
GROUP_LABEL = {"youth": "Thanh niên", "military": "Quân nhân"}


class SurveyExtractionError(ValueError):
    """Lỗi người dùng tự sửa được: sai định dạng, file hỏng, nhầm mẫu phiếu..."""


class ExtractionUnavailableError(RuntimeError):
    """Dịch vụ bóc tách lỗi hoặc quá tải — người dùng chỉ có thể thử lại sau."""


@dataclass
class SurveyDraft:
    form: str
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


@dataclass
class BundleResult:
    """Kết quả tách một file nhiều phiếu của một người."""

    fileName: str
    pageCount: int
    model: str
    subject: dict[str, str | None]
    # Các cách đọc mã đối tượng khác nhau (đã chuẩn hoá), để người dùng chọn khi cần xác nhận.
    codeCandidates: list[str]
    drafts: list[SurveyDraft]
    skipped: list[dict[str, Any]]
    warnings: list[str]

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass
class _Upload:
    path: Path
    name: str
    checksum: str


def extract_survey(db: Session, form: dict[str, Any], upload: UploadFile) -> SurveyDraft:
    """Đọc một file chứa đúng một phiếu của mẫu ``form``."""
    saved = _save_upload(upload)
    try:
        with _extraction_errors(form["id"]):
            pages = load_pages(saved.path, dpi=settings.EXTRACTION_PDF_DPI, max_pages=settings.EXTRACTION_MAX_PAGES)
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
            warnings = _page_warnings(pages)
            document = _register(db, saved.path, saved.name, saved.checksum)
            _audit(db, document, form, output, warnings)
            db.commit()
    except BaseException:
        db.rollback()
        saved.path.unlink(missing_ok=True)
        raise

    read = ", ".join(str(page.number) for page in pages.pages)
    source = f"Trích xuất tự động từ file “{saved.name}” ({pages.total_pages} trang, đã đọc trang {read})."
    return _draft(form, document, pages.total_pages, [page.number for page in pages.pages],
                  output, result, warnings, source)


def extract_bundle(db: Session, group: str, forms: list[dict[str, Any]], upload: UploadFile) -> BundleResult:
    """Đọc một file chứa nhiều phiếu (nhiều mẫu khác nhau) của MỘT người thuộc nhóm ``group``."""
    saved = _save_upload(upload)
    created: list[Path] = []
    try:
        with _extraction_errors(f"nhiều phiếu ({group})"):
            pages = load_pages(
                saved.path, dpi=settings.EXTRACTION_PDF_DPI, max_pages=settings.EXTRACTION_BUNDLE_MAX_PAGES,
            )
            if pages.truncated:
                raise SurveyExtractionError(
                    f"File có hơn {settings.EXTRACTION_BUNDLE_MAX_PAGES} trang có nội dung. Mỗi lượt chỉ tải "
                    "các phiếu của một người — hãy kiểm tra lại file."
                )
            extractor = get_survey_extractor()
            classified = extractor.classify(forms, pages)
            try:
                plan = plan_bundle(forms, [page.number for page in pages.pages], classified.raw)
            except MultipleCopiesError as error:
                raise SurveyExtractionError(str(error)) from error
            if not plan.parts:
                raise SurveyExtractionError(
                    f"Không nhận ra phiếu nào thuộc nhóm {GROUP_LABEL[group]} trong file. Hãy kiểm tra "
                    "đúng nhóm đối tượng và file đủ rõ nét."
                )

            by_number = {page.number: page for page in pages.pages}
            subsets = [
                PageSet(pages=[by_number[number] for number in part.pages], total_pages=pages.total_pages)
                for part in plan.parts
            ]
            workers = max(1, min(len(plan.parts), settings.EXTRACTION_CONCURRENCY))
            with ThreadPoolExecutor(max_workers=workers) as pool:
                outputs = list(pool.map(extractor.extract, [part.form for part in plan.parts], subsets))

            skipped = [{"pages": item.pages, "reason": item.reason} for item in plan.skipped]
            if pages.skipped_blank:
                skipped.append({"pages": pages.skipped_blank, "reason": "trang trắng"})
            accepted: list[tuple[FormPart, ModelOutput, Extraction]] = []
            for part, output in zip(plan.parts, outputs):
                result = normalize(part.form, output.raw)
                if result.is_expected_form and not result.is_empty:
                    accepted.append((part, output, result))
                else:
                    skipped.append({
                        "pages": part.pages,
                        "reason": f"nhận là mẫu {part.form['id']} nhưng không đọc được nội dung phiếu",
                    })
            if not accepted:
                raise SurveyExtractionError(
                    "Không đọc được phiếu nào trong file. Hãy kiểm tra file đúng là phiếu đã điền và đủ rõ nét."
                )

            warnings, candidates = _check_identity(accepted, plan.written_codes)
            drafts: list[SurveyDraft] = []
            for part, output, result in accepted:
                path, name = _write_part(saved, part.form["id"], part.pages, single=len(plan.parts) == 1)
                created.append(path)
                document = _register(db, path, name, _sha256(path))
                _audit(db, document, part.form, output, warnings, bundle={
                    "file": saved.name,
                    "checksum": saved.checksum,
                    "pages": part.pages,
                    "classification": {"pages": classified.raw.get("pages"), "usage": classified.usage},
                })
                source = (
                    f"Tự tách từ file “{saved.name}” ({pages.total_pages} trang): "
                    f"phiếu này ở trang {page_ranges(part.pages)}."
                )
                drafts.append(_draft(part.form, document, pages.total_pages, part.pages,
                                     output, result, warnings, source))
            db.commit()
    except BaseException:
        db.rollback()
        for path in created:
            path.unlink(missing_ok=True)
        saved.path.unlink(missing_ok=True)
        raise
    if saved.path not in created:
        saved.path.unlink(missing_ok=True)

    skipped.sort(key=lambda item: item["pages"][0])
    return BundleResult(
        fileName=saved.name,
        pageCount=pages.total_pages,
        model=drafts[0].model,
        subject=_merge_subjects([draft.subject for draft in drafts]),
        codeCandidates=candidates,
        drafts=drafts,
        skipped=skipped,
        warnings=warnings,
    )


@contextmanager
def _extraction_errors(label: str):
    """Quy lỗi về hai loại: người dùng tự sửa được (422) hoặc dịch vụ bóc tách lỗi (502)."""
    try:
        yield
    except (SurveyExtractionError, ExtractionUnavailableError):
        raise
    except UnreadableFileError as error:
        raise SurveyExtractionError(str(error)) from error
    except Exception as error:  # noqa: BLE001 - lỗi mạng/API/model: log đầy đủ, báo gọn
        logger.exception("Bóc tách phiếu %s thất bại", label)
        reason = str(error) if isinstance(error, ModelResponseError) else "dịch vụ bóc tách đang lỗi hoặc quá tải"
        raise ExtractionUnavailableError(f"Chưa bóc tách được phiếu: {reason}. Hãy thử lại sau.") from error


def _save_upload(upload: UploadFile) -> _Upload:
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
    return _Upload(path=destination, name=name[:255] or destination.name, checksum=digest.hexdigest())


def _write_part(saved: _Upload, form_id: str, pages: list[int], *, single: bool) -> tuple[Path, str]:
    """File gốc của một phiếu trong file nhiều phiếu: chỉ gồm các trang của phiếu đó.

    Ảnh chỉ có một trang nên dùng luôn file đã tải lên.
    """
    if saved.path.suffix.lower() != ".pdf":
        return saved.path, saved.name
    import fitz  # PyMuPDF

    stem = Path(saved.name).stem
    suffix = "" if single else f"_{form_id}_trang-{page_ranges(pages).replace('–', '-').replace(', ', '_')}"
    name = f"{stem}{suffix}.pdf"[-255:]
    destination = STORAGE_DIR / f"{uuid.uuid4().hex}.pdf"
    with fitz.open(saved.path) as source, fitz.open() as output:
        for number in pages:
            output.insert_pdf(source, from_page=number - 1, to_page=number - 1)
        output.save(destination, garbage=3, deflate=True)
    return destination, name


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as source:
        while chunk := source.read(CHUNK_SIZE):
            digest.update(chunk)
    return digest.hexdigest()


def _register(db: Session, path: Path, name: str, checksum: str) -> Document:
    document = Document(
        patient_id=None,
        file_name=name,
        relative_path=str(path),
        mime_type=media_type(path),
        file_type=path.suffix.lower().lstrip("."),
        checksum=checksum,
    )
    db.add(document)
    db.flush()
    return document


def _audit(
    db: Session,
    document: Document,
    form: dict[str, Any],
    output: ModelOutput,
    warnings: list[str],
    bundle: dict[str, Any] | None = None,
) -> None:
    raw_result = {"form": form["id"], "values": output.raw, "usage": output.usage, "warnings": warnings}
    if bundle:
        raw_result["bundle"] = bundle
    db.add(OcrExtraction(
        document_id=document.id,
        provider=output.provider,
        model=output.model,
        raw_result=raw_result,
        status="pending",
    ))


def _draft(
    form: dict[str, Any],
    document: Document,
    page_count: int,
    pages_read: list[int],
    output: ModelOutput,
    result: Extraction,
    warnings: list[str],
    source: str,
) -> SurveyDraft:
    return SurveyDraft(
        form=form["id"],
        documentId=document.id,
        fileName=document.file_name,
        pageCount=page_count,
        pagesRead=pages_read,
        model=output.model,
        subject=result.subject,
        answers=result.answers,
        uncertain=result.uncertain,
        notes=result.notes,
        warnings=warnings,
        summary=_summary(form, source, output.model, result, warnings),
    )


def _page_warnings(pages: PageSet) -> list[str]:
    warnings = []
    if pages.truncated:
        warnings.append(
            f"File có {pages.total_pages} trang, chỉ đọc {len(pages.pages)} trang có nội dung đầu tiên."
        )
    if pages.skipped_blank:
        warnings.append("Bỏ qua trang trắng: " + ", ".join(map(str, pages.skipped_blank)) + ".")
    return warnings


def _name_key(name: str) -> str:
    text = unicodedata.normalize("NFD", name.replace("đ", "d").replace("Đ", "D"))
    text = "".join(char for char in text if unicodedata.category(char) != "Mn")
    return " ".join(text.casefold().split())


def _check_identity(
    accepted: list[tuple[FormPart, ModelOutput, Extraction]], written_codes: list[tuple[int, str]],
) -> tuple[list[str], list[str]]:
    """Các phiếu trong file phải là của cùng một người; trả về (cảnh báo, các mã đọc được).

    Mã đối tượng được đọc hai lần độc lập: khi đọc từng phiếu và khi nhận diện phần đầu
    trang. Hai lần lệch nhau (thường do chữ số viết tay khó đọc) thì mã bị đánh dấu cần
    đối soát ở mọi phiếu. Không phiếu nào đọc được mã thì dùng mã đọc ở phần đầu trang,
    cũng đánh dấu cần đối soát.
    """
    results = [result for _, _, result in accepted]
    sources = [(f"phiếu {part.form['id']}", result.subject["code"]) for part, _, result in accepted]
    sources += [(f"đầu trang {page}", canonical_code(code)) for page, code in written_codes]
    sources = [(where, code) for where, code in sources if code]
    by_key: dict[str, str] = {}
    for _, code in sources:
        by_key.setdefault(code_key(code), code)
    candidates = list(by_key.values())
    warnings = []
    doubtful = False
    if len(candidates) > 1:
        detail = "; ".join(f"{code} ({where})" for where, code in sources)
        warnings.append(f"Mã đối tượng đọc được không khớp nhau: {detail}. Đối chiếu mã trên phiếu gốc.")
        doubtful = True
    if candidates and not any(result.subject["code"] for result in results):
        results[0].subject["code"] = candidates[0]
        warnings.append(f"Mã đối tượng {candidates[0]} chỉ đọc được ở phần đầu trang — cần đối chiếu với phiếu gốc.")
        doubtful = True
    if doubtful:
        for result in results:
            if "code" not in result.uncertain:
                result.uncertain.append("code")

    names = list(dict.fromkeys(result.subject["full_name"] for result in results if result.subject["full_name"]))
    if len({_name_key(name) for name in names}) > 1:
        warnings.append(
            f"Họ tên đọc được ở các phiếu khác nhau ({', '.join(names)}). "
            "Kiểm tra lại file có đúng là phiếu của một người."
        )
    return warnings, candidates


def _merge_subjects(subjects: list[dict[str, str | None]]) -> dict[str, str | None]:
    """Thông tin định danh chung: lấy giá trị đầu tiên đọc được theo thứ tự trang."""
    return {
        name: next((subject[name] for subject in subjects if subject.get(name)), None)
        for name in SUBJECT_FIELDS
    }


def _summary(form: dict[str, Any], source: str, model: str, result: Extraction, warnings: list[str]) -> str:
    labels = {question["id"]: question["label"] for question in form["questions"]}
    lines = [source, f"Mô hình: {model}."]
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


def discard_unsaved(db: Session, document_ids: set[int]) -> list[Path]:
    """File đã bóc tách nhưng người dùng không lưu thành phiếu (đóng hộp thoại giữa chừng).

    Chỉ áp dụng cho file phiếu khảo sát và chỉ xoá file chưa phiếu nào dùng.
    """
    owned = set(db.scalars(
        select(Document.id).where(
            Document.id.in_(document_ids),
            Document.patient_id.is_(None),
            Document.relative_path.startswith(f"{STORAGE_DIR}/"),
        )
    ))
    return release_documents(db, owned)


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

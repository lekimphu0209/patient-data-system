"""Đọc file upload thành thứ model dùng được: ảnh (cho vision) hoặc text.

Điểm quan trọng: **PDF không tự nói nó là scan hay digital**. Cùng đuôi .pdf
nhưng một file có thể là ảnh chụp, file kia là văn bản thật. Ở đây ta dò lượng
text trích được để quyết định, thay vì tin vào đuôi file hay lựa chọn của người
dùng.
"""

from __future__ import annotations

import base64
import re
from dataclasses import dataclass, field
from pathlib import Path

IMAGE_SUFFIXES = {".jpg", ".jpeg", ".png", ".webp", ".bmp", ".tif", ".tiff"}
DOCX_SUFFIXES = {".docx"}
PDF_SUFFIXES = {".pdf"}
DOC_SUFFIXES = {".doc"}

SUPPORTED_SUFFIXES = IMAGE_SUFFIXES | DOCX_SUFFIXES | PDF_SUFFIXES

# Dưới ngưỡng này coi như PDF không có lớp text dùng được -> phải OCR bằng ảnh.
MIN_TEXT_CHARS_PER_PAGE = 120


class UnsupportedFileError(ValueError):
    """File không thuộc định dạng hệ thống đọc được."""


@dataclass
class DocumentContent:
    """Nội dung đã chuẩn hoá của một file upload."""

    kind: str  # "images" | "text"
    page_count: int
    text: str = ""
    images: list[str] = field(default_factory=list)  # PNG base64
    note: str = ""

    @property
    def is_empty(self) -> bool:
        return not self.text.strip() and not self.images


def _encode_png(data: bytes) -> str:
    return base64.b64encode(data).decode("ascii")


def read_image(path: Path) -> DocumentContent:
    return DocumentContent(kind="images", page_count=1, images=[_encode_png(path.read_bytes())])


def read_docx_text(path: Path) -> DocumentContent:
    """Lấy cả đoạn văn lẫn ô trong bảng — phần lớn nội dung bệnh án nằm trong bảng."""
    from docx import Document
    from docx.document import Document as DocxDocument
    from docx.oxml.table import CT_Tbl
    from docx.oxml.text.paragraph import CT_P
    from docx.table import Table
    from docx.text.paragraph import Paragraph

    document = Document(str(path))
    lines: list[str] = []

    def walk(parent) -> None:
        element = parent.element.body if isinstance(parent, DocxDocument) else parent._tc
        for child in element.iterchildren():
            if isinstance(child, CT_P):
                text = Paragraph(child, parent).text.strip()
                if text:
                    lines.append(text)
            elif isinstance(child, CT_Tbl):
                for row in Table(child, parent).rows:
                    cells = [cell.text.strip().replace("\n", " ") for cell in row.cells]
                    # Ô gộp lặp lại nội dung -> bỏ trùng liền kề cho gọn.
                    deduped: list[str] = []
                    for cell in cells:
                        if not deduped or deduped[-1] != cell:
                            deduped.append(cell)
                    if any(deduped):
                        lines.append(" | ".join(deduped))

    walk(document)
    return DocumentContent(kind="text", page_count=1, text="\n".join(lines))


def read_pdf_text(path: Path) -> tuple[str, int]:
    from pypdf import PdfReader

    reader = PdfReader(str(path))
    pages = [page.extract_text() or "" for page in reader.pages]
    return "\n".join(pages), len(reader.pages)


def render_pdf_images(path: Path, dpi: int, max_pages: int) -> tuple[list[str], int]:
    import fitz  # PyMuPDF

    images: list[str] = []
    with fitz.open(str(path)) as document:
        total = document.page_count
        for index in range(min(total, max_pages)):
            pixmap = document.load_page(index).get_pixmap(dpi=dpi)
            images.append(_encode_png(pixmap.tobytes("png")))
    return images, total


def read_document(
    path: Path | str,
    *,
    prefer: str = "auto",
    dpi: int = 200,
    max_pages: int = 10,
) -> DocumentContent:
    """Chuẩn hoá file thành ảnh hoặc text.

    ``prefer``:
      - ``"images"``  : ép dùng vision (chế độ OCR)
      - ``"text"``    : ép dùng lớp text (chế độ phiếu digital)
      - ``"auto"``    : tự chọn theo nội dung file
    """
    path = Path(path)
    suffix = path.suffix.lower()

    if suffix in IMAGE_SUFFIXES:
        return read_image(path)

    if suffix in DOCX_SUFFIXES:
        return read_docx_text(path)

    if suffix in DOC_SUFFIXES:
        raise UnsupportedFileError(
            "Định dạng .doc (Word 97-2003) chưa hỗ trợ — hãy lưu lại thành .docx hoặc PDF."
        )

    if suffix not in PDF_SUFFIXES:
        raise UnsupportedFileError(f"Không hỗ trợ định dạng “{suffix or path.name}”.")

    text, page_count = read_pdf_text(path)
    has_text_layer = len(re.sub(r"\s", "", text)) >= MIN_TEXT_CHARS_PER_PAGE * max(page_count, 1)

    if prefer == "text" and has_text_layer:
        return DocumentContent(kind="text", page_count=page_count, text=text)

    if prefer == "text" and not has_text_layer:
        # Người dùng chọn "phiếu digital" nhưng file thật ra là bản scan.
        images, total = render_pdf_images(path, dpi, max_pages)
        return DocumentContent(
            kind="images",
            page_count=total,
            images=images,
            note="File PDF này không có lớp văn bản (bản scan) nên đã tự chuyển sang chế độ OCR.",
        )

    if prefer == "images" and has_text_layer:
        # Ngược lại: chọn OCR nhưng file có sẵn text -> đọc text vừa chính xác
        # hơn vừa rẻ hơn nhiều so với gửi ảnh.
        return DocumentContent(
            kind="text",
            page_count=page_count,
            text=text,
            note="File PDF này có sẵn lớp văn bản nên đã đọc trực tiếp thay vì OCR ảnh.",
        )

    images, total = render_pdf_images(path, dpi, max_pages)
    content = DocumentContent(kind="images", page_count=total, images=images)
    if total > max_pages:
        content.note = f"File có {total} trang, chỉ xử lý {max_pages} trang đầu."
    return content

"""Đọc trang PDF thành ảnh — chạy trong tiến trình con để dùng nhiều nhân CPU.

Ảnh trang được tạo y hệt luồng tải file trên giao diện (cùng DPI, chất lượng JPEG,
cùng cách nhận trang trắng) để VLM nhận đúng loại ảnh đã được kiểm chứng.
"""

from __future__ import annotations

from app.modules.surveys.ocr.pages import JPEG_QUALITY, PageImage, _is_blank

_OPEN: dict[str, object] = {}


def _document(path: str):
    import fitz  # PyMuPDF

    document = _OPEN.get(path)
    if document is None:
        # Mỗi tiến trình giữ file mở để không phải mở lại file vài trăm MB cho từng trang.
        if len(_OPEN) > 4:
            for old in _OPEN.values():
                old.close()
            _OPEN.clear()
        document = _OPEN[path] = fitz.open(path)
    return document


def page_count(path: str) -> int:
    import fitz

    with fitz.open(path) as document:
        if document.needs_pass:
            raise ValueError("File PDF có mật khẩu.")
        return document.page_count


def blank_pages(path: str, numbers: list[int]) -> list[int]:
    """Các trang (đếm từ 1) trong ``numbers`` là trang trắng."""
    document = _document(path)
    return [number for number in numbers if _is_blank(document.load_page(number - 1))]


def render_pages(path: str, numbers: list[int], dpi: int) -> list[PageImage]:
    import fitz

    document = _document(path)
    pages = []
    for number in numbers:
        page = document.load_page(number - 1)
        pixmap = page.get_pixmap(dpi=dpi, colorspace=fitz.csRGB, alpha=False)
        pages.append(PageImage(
            number=number,
            jpeg=pixmap.tobytes("jpeg", jpg_quality=JPEG_QUALITY),
            text=page.get_text("text") or "",
        ))
    return pages

"""Chuẩn hoá file upload thành các trang ảnh JPEG cho model thị giác.

PDF luôn được render thành ảnh, kể cả khi có lớp văn bản: dấu X/✓ viết tay, chú
thích vẽ đè hay lớp OCR do máy scan tự thêm đều không chứa dấu chọn, nên chỉ đọc
text sẽ mất toàn bộ câu trả lời. Lớp văn bản (nếu có) chỉ đi kèm làm gợi ý để
đọc chính xác chữ in/chữ gõ.
"""

from __future__ import annotations

import io
from dataclasses import dataclass, field
from pathlib import Path

MEDIA_TYPES = {
    ".pdf": "application/pdf",
    ".jpg": "image/jpeg",
    ".jpeg": "image/jpeg",
    ".png": "image/png",
    ".webp": "image/webp",
}
SUPPORTED_SUFFIXES = frozenset(MEDIA_TYPES)

# Ảnh lớn hơn mức này không giúp model đọc rõ hơn (model tự thu nhỏ) mà chỉ làm
# request nặng thêm.
MAX_IMAGE_SIDE = 2400
JPEG_QUALITY = 88
# Trang có tỷ lệ điểm tối dưới ngưỡng này coi là trang trắng (mặt sau để trống,
# chỉ có số trang/tiêu đề góc). Đo trên bản scan thật: trang trắng ~0.0000-0.0001,
# trang ít chữ nhất (nửa bảng câu hỏi) ~0.0035 — ngưỡng đặt xa cả hai phía.
BLANK_INK_RATIO = 0.0005


class UnreadableFileError(ValueError):
    """File sai định dạng, hỏng hoặc không có trang nào đọc được."""


@dataclass
class PageImage:
    number: int  # số thứ tự trang trong file gốc, đếm từ 1
    jpeg: bytes
    text: str = ""


@dataclass
class PageSet:
    pages: list[PageImage]
    total_pages: int
    skipped_blank: list[int] = field(default_factory=list)
    truncated: bool = False

    @property
    def text_layer(self) -> str:
        return "\n\n".join(
            f"[Trang {page.number}]\n{page.text.strip()}" for page in self.pages if page.text.strip()
        )


def media_type(path: Path | str) -> str:
    return MEDIA_TYPES[Path(path).suffix.lower()]


def load_pages(path: Path | str, *, dpi: int, max_pages: int) -> PageSet:
    path = Path(path)
    suffix = path.suffix.lower()
    if suffix not in SUPPORTED_SUFFIXES:
        raise UnreadableFileError(f"Không hỗ trợ định dạng “{suffix or path.name}”.")
    if suffix == ".pdf":
        return _load_pdf(path, dpi=dpi, max_pages=max_pages)
    return PageSet(pages=[PageImage(number=1, jpeg=_load_image(path))], total_pages=1)


def _load_image(path: Path) -> bytes:
    from PIL import Image, ImageOps, UnidentifiedImageError

    try:
        with Image.open(path) as source:
            # Ảnh chụp điện thoại thường lưu hướng xoay trong EXIF chứ không xoay
            # điểm ảnh; bỏ qua bước này thì model nhận phiếu nằm ngang/lộn ngược.
            image = ImageOps.exif_transpose(source)
            image = _flatten(image)
            image.thumbnail((MAX_IMAGE_SIDE, MAX_IMAGE_SIDE))
            buffer = io.BytesIO()
            image.save(buffer, format="JPEG", quality=JPEG_QUALITY)
            return buffer.getvalue()
    except (UnidentifiedImageError, OSError, Image.DecompressionBombError) as exc:
        raise UnreadableFileError("Không mở được ảnh. File có thể bị hỏng hoặc không phải ảnh.") from exc


def _flatten(image):
    """Đưa về RGB nền trắng — ảnh PNG/WebP trong suốt sẽ thành nền đen nếu convert thẳng."""
    from PIL import Image

    if image.mode in ("RGBA", "LA") or (image.mode == "P" and "transparency" in image.info):
        rgba = image.convert("RGBA")
        background = Image.new("RGB", rgba.size, "white")
        background.paste(rgba, mask=rgba.getchannel("A"))
        return background
    return image.convert("RGB")


def _load_pdf(path: Path, *, dpi: int, max_pages: int) -> PageSet:
    import fitz  # PyMuPDF

    try:
        document = fitz.open(path)
    except Exception as exc:  # noqa: BLE001 - PyMuPDF ném nhiều loại lỗi khác nhau
        raise UnreadableFileError("Không mở được file PDF. File có thể bị hỏng.") from exc

    with document:
        if document.needs_pass:
            raise UnreadableFileError("File PDF có mật khẩu. Hãy gỡ mật khẩu rồi tải lại.")
        total = document.page_count
        if total == 0:
            raise UnreadableFileError("File PDF không có trang nào.")

        pages: list[PageImage] = []
        skipped: list[int] = []
        truncated = False
        for index in range(total):
            if len(pages) == max_pages:
                truncated = True
                break
            page = document.load_page(index)
            if _is_blank(page):
                skipped.append(index + 1)
                continue
            pixmap = page.get_pixmap(dpi=dpi, colorspace=fitz.csRGB, alpha=False)
            pages.append(
                PageImage(
                    number=index + 1,
                    jpeg=pixmap.tobytes("jpeg", jpg_quality=JPEG_QUALITY),
                    text=page.get_text("text") or "",
                )
            )

    if not pages:
        raise UnreadableFileError("Các trang trong file PDF đều trống.")
    return PageSet(pages=pages, total_pages=total, skipped_blank=skipped, truncated=truncated)


def _is_blank(page) -> bool:
    import fitz

    pixmap = page.get_pixmap(dpi=24, colorspace=fitz.csGRAY, alpha=False)
    samples = pixmap.samples
    if not samples:
        return True
    dark = sum(1 for value in samples if value < 140)
    return dark / len(samples) < BLANK_INK_RATIO

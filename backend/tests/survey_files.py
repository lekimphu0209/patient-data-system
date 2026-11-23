"""File phiếu giả dùng chung cho các test bóc tách phiếu khảo sát."""

import io

import fitz
from PIL import Image

BASE = "/api/v1/surveys"


def make_pdf(pages=("PHIEU SANG LOC TRAM CAM", None, "Trang 3")) -> bytes:
    """PDF nhiều trang; ``None`` là trang trắng."""
    document = fitz.open()
    for text in pages:
        page = document.new_page()
        if text is not None:
            page.insert_text((72, 72), text, fontsize=20)
            for row in range(12):  # kẻ bảng như phiếu thật để trang có đủ "mực"
                page.draw_rect(fitz.Rect(60, 100 + row * 40, 540, 140 + row * 40), width=4)
    data = document.tobytes()
    document.close()
    return data


def make_image(size=(40, 20), mode="RGB", fmt="JPEG", orientation=None) -> bytes:
    image = Image.new(mode, size, (200, 30, 30, 0) if mode == "RGBA" else (200, 30, 30))
    buffer = io.BytesIO()
    if orientation:
        exif = Image.Exif()
        exif[0x0112] = orientation
        image.save(buffer, format=fmt, exif=exif)
    else:
        image.save(buffer, format=fmt)
    return buffer.getvalue()


def pdf_page_texts(content: bytes) -> list[str]:
    with fitz.open(stream=content, filetype="pdf") as document:
        return [page.get_text().strip() for page in document]

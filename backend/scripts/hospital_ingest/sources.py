"""Tìm file scan của bệnh viện và các thao tác chỉ cần máy (không gọi VLM)."""

from __future__ import annotations

import hashlib
import re
import unicodedata
from dataclasses import dataclass
from pathlib import Path

from app.modules.surveys.ocr.schema import canonical_code

# Thư mục dữ liệu bệnh viện -> nhóm đối tượng. Thư mục khác (bản trùng, ocr-samples) bỏ qua.
GROUP_FOLDERS = {
    "đối tượng thanh niên": "youth",
    "đối tượng nhập ngũ": "military",
}
RANGE = re.compile(r"(\d+)\s*-\s*(\d+)")
CHUNK = 1 << 20


def fold(text: str) -> str:
    """So khớp tên thư mục/file: NFC, chữ thường, gộp khoảng trắng (tên có thể thừa dấu cách cuối)."""
    return " ".join(unicodedata.normalize("NFC", text).casefold().split())


def _plain(text: str) -> str:
    text = unicodedata.normalize("NFD", fold(text).replace("đ", "d"))
    return "".join(char for char in text if unicodedata.category(char) != "Mn")


@dataclass
class SourceFile:
    group: str
    path: Path
    label: str  # đường dẫn tương đối, để báo cáo
    start: int | None  # dải mã ghi trên tên file
    end: int | None
    digits: int | None  # số chữ số của số đầu dải ("01" -> 2)
    hint: str | None  # tiền tố mã theo tên file/thư mục ("PT.CK", "QK1")

    @property
    def expected(self) -> int | None:
        return None if self.start is None or self.end is None else self.end - self.start + 1


def group_of(folder: str) -> str | None:
    return GROUP_FOLDERS.get(fold(folder))


def code_hint(text: str) -> str | None:
    """Phần trước dải số trên tên: "PT.CK " -> "PT.CK", "QK1. " -> "QK1", "phieu " -> None."""
    code = canonical_code(text)
    if not code or not re.search(r"[^\W\d_]", code) or _plain(code) in {"phieu", "phieu khao sat"}:
        return None
    return code


def describe(group: str, root: Path, path: Path) -> SourceFile:
    start = end = digits = None
    match = RANGE.search(path.stem)
    if match and int(match.group(1)) <= int(match.group(2)):
        start, end, digits = int(match.group(1)), int(match.group(2)), len(match.group(1))
    hint = code_hint(path.stem[:match.start()] if match else "")
    # Thư mục con giữa thư mục nhóm và file ("QK1. 01 - 180"); không lấy tên thư mục nhóm.
    for folder in list(path.relative_to(root).parents)[:-2]:
        if hint:
            break
        found = RANGE.search(folder.name)
        hint = code_hint(folder.name[:found.start()] if found else folder.name)
    return SourceFile(
        group=group, path=path, label=str(path.relative_to(root)),
        start=start, end=end, digits=digits, hint=hint,
    )


def discover(root: Path) -> list[SourceFile]:
    """Các file PDF trong thư mục nhóm đối tượng, xếp theo nhóm rồi theo dải mã."""
    files: list[SourceFile] = []
    for folder in sorted(root.iterdir()):
        group = group_of(folder.name) if folder.is_dir() else None
        if group is None:
            continue
        for path in folder.rglob("*"):
            if path.is_file() and path.suffix.lower() == ".pdf":
                files.append(describe(group, root, path))
    order = {"youth": 0, "military": 1}
    return sorted(files, key=lambda item: (order[item.group], item.hint or "", item.start or 0, item.label))


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as source:
        while chunk := source.read(CHUNK):
            digest.update(chunk)
    return digest.hexdigest()

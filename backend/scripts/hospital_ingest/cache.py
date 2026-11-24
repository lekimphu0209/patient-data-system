"""Lưu kết quả từng lần gọi VLM ra đĩa để chạy lại không phải gọi lại.

Mỗi kết quả là một file JSON, khoá theo checksum file nguồn + loại việc + các trang.
Kèm "dấu vân tay" của prompt/model/độ phân giải: đổi prompt hay model thì kết quả cũ
không còn đúng và sẽ được đọc lại; giữ nguyên thì không bao giờ gọi lại.
"""

from __future__ import annotations

import hashlib
import json
import os
from pathlib import Path
from typing import Any


def fingerprint(*parts: Any) -> str:
    text = json.dumps(parts, ensure_ascii=False, sort_keys=True, default=str)
    return hashlib.sha256(text.encode("utf-8")).hexdigest()[:12]


class Cache:
    def __init__(self, root: Path):
        self.root = root

    def path(self, checksum: str, name: str) -> Path:
        return self.root / checksum[:16] / f"{name}.json"

    def get(self, checksum: str, name: str, fingerprint: str | None = None) -> dict[str, Any] | None:
        path = self.path(checksum, name)
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
        except FileNotFoundError:
            return None
        except (OSError, json.JSONDecodeError):
            # File dở dang không thể xảy ra (ghi nguyên tử) nhưng hỏng đĩa thì coi như chưa có.
            return None
        if fingerprint is not None and data.get("fingerprint") != fingerprint:
            return None
        return data

    def put(self, checksum: str, name: str, data: dict[str, Any]) -> None:
        path = self.path(checksum, name)
        path.parent.mkdir(parents=True, exist_ok=True)
        temporary = path.with_name(f".{path.name}.{os.getpid()}.tmp")
        temporary.write_text(json.dumps(data, ensure_ascii=False), encoding="utf-8")
        os.replace(temporary, path)

    def drop_failures(self) -> int:
        """Xoá các kết quả lỗi đã lưu (model từ chối, JSON hỏng) để lần chạy sau đọc lại."""
        dropped = 0
        for path in self.root.glob("*/*.json"):
            try:
                failed = "error" in json.loads(path.read_text(encoding="utf-8"))
            except (OSError, json.JSONDecodeError):
                failed = True
            if failed:
                path.unlink(missing_ok=True)
                dropped += 1
        return dropped

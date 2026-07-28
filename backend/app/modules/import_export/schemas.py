from typing import Any

from pydantic import BaseModel


class ImportPreviewItem(BaseModel):
    row: int
    valid: bool
    data: dict[str, Any]
    errors: list[str]


class ImportPreviewResponse(BaseModel):
    valid_count: int
    invalid_count: int
    rows: list[ImportPreviewItem]


class ImportCommitResponse(BaseModel):
    created: int
    errors: list[dict[str, Any]]


class ExportRequest(BaseModel):
    ids: list[int] | None = None
    format: str = "xlsx"  # xlsx or csv

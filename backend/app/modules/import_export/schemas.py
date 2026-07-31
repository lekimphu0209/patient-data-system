from datetime import date
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
    q: str | None = None
    diagnosis: str | None = None
    disease_type: str | None = None
    birth_date_from: date | None = None
    birth_date_to: date | None = None

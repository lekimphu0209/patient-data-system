from datetime import datetime
from typing import Any, Optional

from pydantic import BaseModel, ConfigDict


class DocumentUploadResponse(BaseModel):
    id: int
    file_name: str
    relative_path: str
    mime_type: str
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)


class ExtractionResult(BaseModel):
    document_id: int
    provider: str
    raw_result: dict[str, Any]

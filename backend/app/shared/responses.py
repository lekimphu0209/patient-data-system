from typing import Any, Generic, Optional, TypeVar

from pydantic import BaseModel

T = TypeVar("T")


class PaginationParams(BaseModel):
    page: int = 1
    limit: int = 20


class PaginationMeta(BaseModel):
    page: int
    limit: int
    total: int
    total_pages: int


class ApiResponse(BaseModel, Generic[T]):
    data: T
    message: Optional[str] = None


class PaginatedResponse(BaseModel, Generic[T]):
    data: list[Any]
    pagination: PaginationMeta

from datetime import datetime, timezone
from typing import Any

from sqlalchemy import JSON, DateTime, ForeignKey, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base


class AssistantLog(Base):
    """Nhật ký hỏi đáp của trợ lý dữ liệu: ai hỏi, công cụ/SQL đã chạy, câu trả lời (chỉ máy chủ xem)."""

    __tablename__ = "assistant_logs"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    user_id: Mapped[int | None] = mapped_column(Integer, ForeignKey("users.id"), nullable=True, index=True)
    question: Mapped[str] = mapped_column(Text)
    answer: Mapped[str] = mapped_column(Text, default="")
    calls: Mapped[list[dict[str, Any]]] = mapped_column(JSON, default=list)
    usage: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict)
    model: Mapped[str] = mapped_column(String(100), default="")
    error: Mapped[str | None] = mapped_column(Text, nullable=True)
    duration_ms: Mapped[int] = mapped_column(Integer, default=0)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))

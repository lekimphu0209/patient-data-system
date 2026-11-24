import datetime as dt
from datetime import datetime, timezone
from typing import Any

from sqlalchemy import JSON, Boolean, Date, DateTime, ForeignKey, Integer, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base


def _now() -> datetime:
    return datetime.now(timezone.utc)


class ClinicalPatient(Base):
    """Bệnh nhân của một nhóm bệnh án (F20 hoặc F32)."""

    __tablename__ = "clinical_patients"

    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    type: Mapped[str] = mapped_column(String(3), index=True)
    code: Mapped[str] = mapped_column(String(80))
    # Mã chuẩn hoá (chữ thường, bỏ khoảng trắng thừa) — duy nhất trên toàn bộ bệnh án.
    code_key: Mapped[str] = mapped_column(String(80), unique=True, index=True)
    full_name: Mapped[str] = mapped_column(String(200), default="")
    age: Mapped[int | None] = mapped_column(Integer, nullable=True)
    sex: Mapped[str] = mapped_column(String(10), default="")
    # Các trường hành chính còn lại: quê quán, dân tộc, học vấn, nghề nghiệp, nơi ở, hôn nhân.
    identity: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict)
    source: Mapped[str] = mapped_column(String(20), default="Thủ công")
    needs_review: Mapped[bool] = mapped_column(Boolean, default=False)
    document_id: Mapped[int | None] = mapped_column(Integer, ForeignKey("documents.id"), nullable=True)
    # Tóm tắt lần đọc ảnh bệnh án (tên file, số trường đọc được, mục cần đối soát, ghi chú của model).
    ocr: Mapped[dict[str, Any] | None] = mapped_column(JSON, nullable=True)
    revision: Mapped[int] = mapped_column(Integer, default=1)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_now)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_now)

    visits: Mapped[list["ClinicalVisit"]] = relationship(
        back_populates="patient", cascade="all, delete-orphan", lazy="selectin",
        order_by="ClinicalVisit.position",
    )


class ClinicalVisit(Base):
    """Một lần khám: bản bệnh án theo biểu mẫu của nhóm."""

    __tablename__ = "clinical_visits"

    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    patient_id: Mapped[str] = mapped_column(String(64), ForeignKey("clinical_patients.id", ondelete="CASCADE"), index=True)
    position: Mapped[int] = mapped_column(Integer, default=0)  # thứ tự tạo (0 = khám lần đầu)
    date: Mapped[dt.date] = mapped_column(Date)
    created_at: Mapped[str] = mapped_column(String(40))
    fields: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict)

    patient: Mapped[ClinicalPatient] = relationship(back_populates="visits")

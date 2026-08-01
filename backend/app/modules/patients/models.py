from datetime import date, datetime, timezone
from typing import Any, Optional

from sqlalchemy import JSON, Date, DateTime, Integer, String, ForeignKey, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base


class Patient(Base):
    __tablename__ = "patients"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    patient_code: Mapped[str] = mapped_column(
        String(50), unique=True, index=True, nullable=False
    )
    full_name: Mapped[str] = mapped_column(String(255), nullable=False)
    birth_date: Mapped[Optional[date]] = mapped_column(Date, nullable=True)
    age: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    disease_type: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
    diagnosis: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    hometown: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    status: Mapped[str] = mapped_column(String(50), default="active")
    contact_info: Mapped[Optional[dict[str, Any]]] = mapped_column(JSON, nullable=True)
    patient_metadata: Mapped[Optional[dict[str, Any]]] = mapped_column("metadata", JSON, nullable=True)
    deleted_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(timezone.utc)
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        onupdate=lambda: datetime.now(timezone.utc),
    )
    exams: Mapped[list["Examination"]] = relationship("Examination", back_populates="patient")
    medical_history: Mapped[Optional["MedicalHistory"]] = relationship(
        "MedicalHistory", back_populates="patient", uselist=False
    )


class MedicalHistory(Base):
    __tablename__ = "medical_histories"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    patient_id: Mapped[int] = mapped_column(Integer, ForeignKey("patients.id"), nullable=False)

    # Triệu chứng/Reason for visit (khác nhau tùy loại bệnh)
    presenting_symptoms: Mapped[Optional[dict[str, Any]]] = mapped_column(JSON, nullable=True)

    # Bệnh sử (chung cho cả 2 loại)
    onset_age: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    disease_duration_years: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    disease_duration_months: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    previous_diagnoses: Mapped[Optional[list[str]]] = mapped_column(JSON, nullable=True)
    disease_progression: Mapped[Optional[str]] = mapped_column(String(50), nullable=True)  # Liên tục/Từng giai đoạn
    relapse_count: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    previous_inpatient_treatments: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    medications_before_admission: Mapped[Optional[dict[str, Any]]] = mapped_column(JSON, nullable=True)
    reinforcement_status: Mapped[Optional[str]] = mapped_column(String(50), nullable=True)  # Đều/Không đều/Không
    circumstances_of_onset: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)

    # Tiền sử (Personal & Family history)
    personal_history: Mapped[Optional[dict[str, Any]]] = mapped_column(JSON, nullable=True)
    family_history: Mapped[Optional[dict[str, Any]]] = mapped_column(JSON, nullable=True)

    # Toàn bộ khối "HỎI BỆNH" lưu phân cấp theo form_schema.json:
    # {"<group_id>": {"<field_id>": value}}. Các cột rời phía trên chỉ còn giữ
    # cho dữ liệu cũ; dữ liệu mới đọc/ghi qua đây.
    data: Mapped[Optional[dict[str, Any]]] = mapped_column(JSON, nullable=True)

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(timezone.utc)
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        onupdate=lambda: datetime.now(timezone.utc),
    )

    patient: Mapped["Patient"] = relationship("Patient", back_populates="medical_history")


class Examination(Base):
    __tablename__ = "examinations"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    patient_id: Mapped[int] = mapped_column(Integer, ForeignKey("patients.id"), nullable=False)

    # 3.1 Khám thực thể (Physical examination)
    exam_date: Mapped[date] = mapped_column(Date, nullable=False, index=True)
    general_condition: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    cardiovascular: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    respiratory: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    digestive: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    urinary: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    neurological: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    other_body_parts: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)

    # 3.2 Khám tâm thần (Mental examination)
    mental_exam: Mapped[Optional[dict[str, Any]]] = mapped_column(JSON, nullable=True)

    # 3.3 Cận lâm sàng chung (General clinical tests)
    general_clinical_tests: Mapped[Optional[dict[str, Any]]] = mapped_column(JSON, nullable=True)

    # 3.4 Cận lâm sàng khác (Other clinical tests)
    other_clinical_tests: Mapped[Optional[dict[str, Any]]] = mapped_column(JSON, nullable=True)

    # 3.5 Chẩn đoán (Diagnosis)
    diagnosis: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)

    # 3.6 Điều trị (Treatment)
    treatment: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)

    # Toàn bộ khối "KHÁM BỆNH" (PHẦN 3 → PHẦN 7) lưu phân cấp theo
    # form_schema.json: {"<group_id>": {"<field_id>": value}}. Các cột rời phía
    # trên chỉ còn giữ cho dữ liệu cũ; dữ liệu mới đọc/ghi qua đây.
    data: Mapped[Optional[dict[str, Any]]] = mapped_column(JSON, nullable=True)

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(timezone.utc)
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        onupdate=lambda: datetime.now(timezone.utc),
    )

    patient: Mapped["Patient"] = relationship("Patient", back_populates="exams")

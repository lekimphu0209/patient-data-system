from datetime import date, datetime

from sqlalchemy import JSON, Date, DateTime, ForeignKeyConstraint, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base


class SurveySubject(Base):
    __tablename__ = "survey_subjects"

    group: Mapped[str] = mapped_column("subject_group", String(10), primary_key=True)
    person: Mapped[str] = mapped_column(String(120), primary_key=True)
    full_name: Mapped[str] = mapped_column(String(255))
    birth_date: Mapped[date | None] = mapped_column(Date)
    birth_year: Mapped[str] = mapped_column(String(4))
    hometown: Mapped[str] = mapped_column(String(255))


class SurveyRecord(Base):
    __tablename__ = "survey_records"
    __table_args__ = (
        ForeignKeyConstraint(
            ["subject_group", "person"],
            ["survey_subjects.subject_group", "survey_subjects.person"],
        ),
    )

    id: Mapped[str] = mapped_column(String(120), primary_key=True)
    group: Mapped[str] = mapped_column("subject_group", String(10))
    person: Mapped[str] = mapped_column(String(120))
    form: Mapped[str] = mapped_column(String(3))
    unit: Mapped[str] = mapped_column(String(255))
    date: Mapped[date] = mapped_column(Date)
    source: Mapped[str] = mapped_column(String(20))
    status: Mapped[str] = mapped_column(String(10))
    conclusion: Mapped[str] = mapped_column(Text)
    answers: Mapped[dict[str, str | list[str]]] = mapped_column(JSON)
    note: Mapped[str] = mapped_column(Text)
    ocr: Mapped[str | None] = mapped_column(Text, deferred=True)
    ocr_image: Mapped[str | None] = mapped_column(Text, deferred=True)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))

    subject: Mapped[SurveySubject] = relationship(lazy="joined")

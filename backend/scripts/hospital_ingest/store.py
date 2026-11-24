"""Ghi kết quả vào database/storage, dọn dữ liệu cũ.

Bản ghi được dựng theo đúng quy tắc của luồng tải file trên giao diện
(``buildRecords`` ở frontend): điền họ tên/năm sinh từ thông tin đối tượng, bỏ câu
được chuyển qua, bỏ đáp án không hợp lệ, đủ câu và không còn mục nghi vấn thì "Chờ đối
soát", ngược lại là "Bản nháp". Mỗi phiếu có file gốc riêng chỉ gồm các trang của nó.
"""

from __future__ import annotations

import json
import os
import re
import shutil
import unicodedata
import uuid
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any
from zoneinfo import ZoneInfo

from pydantic import ValidationError
from sqlalchemy import delete, func, or_, select, tuple_
from sqlalchemy.orm import Session

from app.modules.clinical.models import ClinicalPatient, ClinicalVisit
from app.modules.documents.models import Document, OcrExtraction
from app.modules.encounters.models import Encounter
from app.modules.patients.models import Examination, MedicalHistory, Patient
from app.modules.surveys.models import SurveyRecord, SurveySubject
from app.modules.surveys.ocr.bundle import page_ranges
from app.modules.surveys.ocr.extractor import ModelOutput
from app.modules.surveys.ocr.schema import Extraction
from app.modules.surveys.ocr.service import (
    _audit, _merge_subjects, _name_key, _register, _sha256, _summary, release_documents,
)
from app.modules.surveys.router import save_subjects, write_record
from app.modules.surveys.schemas import RecordInput, SubjectInput

from .segment import Part, Segment
from .sources import SourceFile

FILE_PREFIX = "ingest-"
NAME_LABEL = re.compile(r"^(Họ và tên|1\. Họ và tên)")
NO_EVENT = "Không gặp sự kiện đáng kể"
# Dữ liệu bệnh nhân bị xoá trước khi nạp; tài khoản và file mẫu (storage/templates) giữ nguyên.
WIPE_MODELS = (SurveyRecord, SurveySubject, ClinicalVisit, ClinicalPatient, OcrExtraction, Examination, MedicalHistory,
               Document, Encounter, Patient)
WIPE_FOLDERS = ("surveys", "clinical", "uploads", "exports", "imports")
# Phiếu sửa sau khi nạp quá khoảng này thì coi là người dùng đã chỉnh, không cho gỡ.
EDIT_GRACE = timedelta(minutes=2)


def today() -> str:
    return datetime.now(ZoneInfo("Asia/Ho_Chi_Minh")).date().isoformat()


# ---------- Dựng câu trả lời giống giao diện ----------


def has_answer(value: Any) -> bool:
    if isinstance(value, list):
        return bool(value)
    return isinstance(value, str) and bool(value.strip())


def _skipped(answers: dict[str, Any], question: dict[str, Any]) -> bool:
    rule = question.get("skipIf")
    if not rule:
        return False
    value = answers.get(rule["question"])
    return rule["answer"] in value if isinstance(value, list) else value == rule["answer"]


def _dropped_by_skip(answers: dict[str, Any], question: dict[str, Any]) -> bool:
    return _skipped(answers, question) and not question["skipIf"].get("keepAnswer")


def prepare_answers(form: dict[str, Any], answers: dict[str, Any], patient: dict[str, str]) -> dict[str, Any]:
    """Cổng của ``prepareAnswers`` (frontend/src/features/surveys/model.ts)."""
    result = dict(answers)
    for question in form["questions"]:
        key, label = question["id"], question["label"]
        if NAME_LABEL.match(label) and patient["fullName"]:
            result[key] = patient["fullName"]
        if label == "Năm sinh" and (patient["birthDate"] or patient["birthYear"]):
            result[key] = (patient["birthDate"] or patient["birthYear"])[:4]
        if label == "Địa chỉ" and patient["hometown"] and not result.get(key):
            result[key] = patient["hometown"]
        if isinstance(result.get(key), str):
            result[key] = result[key].strip()
        if not has_answer(result.get(key)) or _dropped_by_skip(result, question):
            result.pop(key, None)
    return result


def invalid_answers(form: dict[str, Any], answers: dict[str, Any]) -> set[str]:
    """Cổng của ``validateAnswers``: các câu có đáp án không hợp lệ (bị bỏ khi lưu)."""
    invalid = set()
    for question in form["questions"]:
        value = answers.get(question["id"])
        if not has_answer(value) or _dropped_by_skip(answers, question):
            continue
        values = value if isinstance(value, list) else [value]
        if question["options"] and any(item not in question["options"] for item in values):
            invalid.add(question["id"])
        if "tối đa 2" in question["label"] and len(values) > 2:
            invalid.add(question["id"])
        if len(values) > 1 and any(NO_EVENT in item for item in values):
            invalid.add(question["id"])
    return invalid


def progress(form: dict[str, Any], answers: dict[str, Any]) -> tuple[int, int]:
    applicable = [question for question in form["questions"] if not _skipped(answers, question)]
    return sum(has_answer(answers.get(question["id"])) for question in applicable), len(applicable)


# ---------- Một người ----------


@dataclass
class FormResult:
    part: Part
    output: ModelOutput | None = None
    result: Extraction | None = None
    problem: str | None = None  # lý do phiếu này không nạp được


@dataclass
class Person:
    source: SourceFile
    checksum: str
    total_pages: int
    index: int  # thứ tự người trong file, đếm từ 0
    count: int  # số người tách được trong file
    segment: Segment
    forms: list[FormResult]
    labels: list[dict[str, Any]] = field(default_factory=list)
    reads: list[str] = field(default_factory=list)
    code: str | None = None
    code_note: str = ""
    code_doubtful: bool = False
    problem: str | None = None  # lý do cả người này phải nạp tay
    created: list[str] = field(default_factory=list)
    existing: list[str] = field(default_factory=list)

    @property
    def accepted(self) -> list[FormResult]:
        return [item for item in self.forms if item.result is not None and item.problem is None]


def record_id(code: str, form_id: str) -> str:
    return f"OCR-{code}-{form_id}"


def _patient(subject: dict[str, str | None]) -> dict[str, str]:
    patient = {
        "fullName": subject.get("full_name") or "",
        "birthDate": subject.get("birth_date") or "",
        "birthYear": subject.get("birth_year") or "",
        "hometown": subject.get("hometown") or "",
    }
    try:
        SubjectInput(**patient)
    except ValidationError:
        # Như giao diện: ngày/năm sinh đọc ra mâu thuẫn thì bỏ để người soát nhập lại.
        patient["birthDate"] = patient["birthYear"] = ""
    return patient


def _name_warnings(person: Person) -> list[str]:
    names = list(dict.fromkeys(
        item.result.subject["full_name"] for item in person.accepted if item.result.subject["full_name"]
    ))
    if len({_name_key(name) for name in names}) > 1:
        return [f"Họ tên đọc được ở các phiếu khác nhau ({', '.join(names)}) — kiểm tra lại phiếu gốc."]
    return []


def build_record(person: Person, item: FormResult, patient: dict[str, str], merged: dict[str, Any],
                 warnings: list[str]) -> RecordInput:
    form, result = item.part.form, item.result
    answers = prepare_answers(form, result.answers, patient)
    for key in invalid_answers(form, answers):
        answers.pop(key, None)
    count, total = progress(form, answers)
    uncertain = [key for key in result.uncertain if key != "code"]
    if person.code_doubtful:
        uncertain.append("code")
    survey_date = result.subject.get("survey_date") or merged.get("survey_date")
    note = " ".join(part for part in [
        f"Nạp hàng loạt từ file {person.source.label}, trang {page_ranges(item.part.pages)}.",
        person.code_note,
        f"Cần đối soát {len(uncertain)} mục: {', '.join(uncertain)}." if uncertain
        else "Đối chiếu với phiếu gốc trước khi hoàn tất.",
        "" if survey_date else "Ngày khảo sát tạm dùng ngày nhập, cần xác nhận.",
        *warnings,
    ] if part)
    source = (
        f"Nạp hàng loạt từ file “{person.source.label}” ({person.total_pages} trang): "
        f"phiếu này ở trang {page_ranges(item.part.pages)}."
    )
    summary_warnings = [*([person.code_note] if person.code_doubtful else []), *warnings]
    return RecordInput(
        id=record_id(person.code, form["id"]),
        person=person.code,
        group=person.source.group,
        form=form["id"],
        patient=patient,
        unit=result.subject.get("unit") or merged.get("unit") or "",
        date=survey_date or today(),
        source="OCR",
        status="review" if count == total and not uncertain else "draft",
        conclusion="",
        answers=answers,
        note=note,
        ocr=_summary(form, source, item.output.model, result, summary_warnings),
    )


def split_pdf(source_document, pages: list[int], storage_dir: Path) -> Path:
    import fitz

    storage_dir.mkdir(parents=True, exist_ok=True)
    destination = storage_dir / f"{FILE_PREFIX}{uuid.uuid4().hex}.pdf"
    with fitz.open() as output:
        for number in pages:
            output.insert_pdf(source_document, from_page=number - 1, to_page=number - 1)
        output.save(destination, garbage=3, deflate=True)
    return destination


def write_person(db: Session, person: Person, source_document, storage_dir: Path, skip_ids: set[str]) -> None:
    """Ghi các phiếu chưa có của một người trong một transaction (hỏng giữa chừng thì không ghi gì)."""
    merged = _merge_subjects([item.result.subject for item in person.accepted])
    patient = _patient(merged)
    warnings = _name_warnings(person)
    wanted = {record_id(person.code, item.part.form["id"]): item for item in person.accepted}
    present = set(db.scalars(select(SurveyRecord.id).where(SurveyRecord.id.in_(wanted))))
    person.existing = sorted(present | (skip_ids & wanted.keys()))
    todo = [(key, item) for key, item in wanted.items() if key not in person.existing]
    if not todo:
        return

    files: list[Path] = []
    records: list[RecordInput] = []
    try:
        for key, item in todo:
            try:
                record = build_record(person, item, patient, merged, warnings)
            except ValidationError as error:
                item.problem = f"dữ liệu đọc ra không hợp lệ: {error.errors()[0].get('msg', error)}"
                continue
            path = split_pdf(source_document, item.part.pages, storage_dir)
            files.append(path)
            name = f"{person.code}_{item.part.form['id']}_trang-{page_ranges(item.part.pages).replace('–', '-').replace(', ', '_')}.pdf"
            document = _register(db, path, name, _sha256(path))
            _audit(db, document, item.part.form, item.output, warnings, bundle={
                "file": person.source.label,
                "checksum": person.checksum,
                "pages": item.part.pages,
                "classification": {"pages": person.labels},
                "ingest": {
                    "person": person.index + 1, "people": person.count, "code": person.code,
                    "codeNote": person.code_note, "reads": person.reads,
                },
            })
            record.documentId = document.id
            records.append(record)
        if records:
            save_subjects(db, records, merge=True)
            for data in records:
                row = SurveyRecord(
                    id=data.id, person=data.person, group=data.group, form=data.form,
                    source=data.source, ocr=data.ocr, ocr_image=None, document_id=data.documentId,
                )
                write_record(row, data)
                db.add(row)
        db.commit()
    except BaseException:
        db.rollback()
        for path in files:
            path.unlink(missing_ok=True)
        raise
    person.created = [record.id for record in records]


# ---------- Dọn dẹp, kiểm tra ----------


def sweep_orphans(db: Session, storage_dir: Path) -> int:
    """Xoá file đã tách nhưng chưa kịp ghi bản ghi (tiến trình bị ngắt giữa chừng)."""
    known = set(db.scalars(select(Document.relative_path).where(Document.relative_path.contains(FILE_PREFIX))))
    removed = 0
    for path in storage_dir.glob(f"{FILE_PREFIX}*.pdf"):
        if str(path) not in known:
            path.unlink(missing_ok=True)
            removed += 1
    return removed


def foreign_records(db: Session) -> int:
    """Số phiếu khảo sát KHÔNG do script này nạp (dữ liệu cũ chưa xoá)."""
    statement = (
        select(func.count(SurveyRecord.id))
        .outerjoin(Document, SurveyRecord.document_id == Document.id)
        .where(or_(Document.id.is_(None), ~Document.relative_path.contains(FILE_PREFIX)))
    )
    return db.scalar(statement) or 0


def wipe(db: Session, storage_root: Path) -> dict[str, int]:
    """Xoá toàn bộ dữ liệu bệnh nhân (bảng + file). Giữ tài khoản và storage/templates."""
    counts: dict[str, int] = {}
    for model in WIPE_MODELS:
        counts[model.__tablename__] = db.execute(delete(model)).rowcount or 0
    db.commit()
    removed = 0
    for folder in WIPE_FOLDERS:
        for path in sorted((storage_root / folder).rglob("*"), reverse=True):
            if path.is_file() or path.is_symlink():
                path.unlink()
                removed += 1
    counts["files"] = removed
    return counts


class PurgeRefused(Exception):
    pass


def _utc(value: datetime) -> datetime:
    return value.replace(tzinfo=timezone.utc) if value.tzinfo is None else value.astimezone(timezone.utc)


def ingested_from(db: Session, name: str) -> tuple[str, list[str]]:
    """Các phiếu đã nạp từ đúng một file nguồn có tên chứa ``name``: (tên file, mã phiếu).

    Từ chối khi không khớp file nào, khớp nhiều file, hoặc có phiếu người dùng đã sửa
    sau khi nạp (gỡ đi sẽ mất chỉnh sửa).
    """
    wanted = unicodedata.normalize("NFC", name)
    rows = db.execute(
        select(SurveyRecord.id, SurveyRecord.updated_at, OcrExtraction.created_at, OcrExtraction.raw_result)
        .join(Document, Document.id == SurveyRecord.document_id)
        .join(OcrExtraction, OcrExtraction.document_id == Document.id)
        .where(Document.relative_path.contains(FILE_PREFIX))
    ).all()
    matched: dict[str, list[tuple[str, datetime, datetime]]] = {}
    for record_id_, updated, created, raw in rows:
        label = unicodedata.normalize("NFC", str(((raw or {}).get("bundle") or {}).get("file") or ""))
        if wanted and wanted in label:
            matched.setdefault(label, []).append((record_id_, updated, created))
    if not matched:
        raise PurgeRefused(f"không có phiếu nào đã nạp từ file có tên chứa “{name}”")
    if len(matched) > 1:
        raise PurgeRefused("tên khớp nhiều file, ghi rõ hơn: " + "; ".join(sorted(matched)))
    (label, items), = matched.items()
    edited = sorted(key for key, updated, created in items if _utc(updated) - _utc(created) > EDIT_GRACE)
    if edited:
        raise PurgeRefused(f"{len(edited)} phiếu đã được sửa sau khi nạp ({', '.join(edited[:10])}"
                           f"{'…' if len(edited) > 10 else ''}); gỡ đi sẽ mất chỉnh sửa")
    return label, sorted(key for key, _, _ in items)


def purge(db: Session, ids: list[str], ledger: Ledger) -> dict[str, int]:
    """Gỡ các phiếu đã nạp (kèm file gốc, bản ghi OCR, đối tượng không còn phiếu nào) để nạp lại.

    Ledger được sửa trước: bị ngắt giữa chừng thì phiếu vẫn còn và chạy lại lệnh gỡ là xong,
    không có trường hợp phiếu đã gỡ mà ledger vẫn chặn nạp lại.
    """
    persons = set(db.execute(select(SurveyRecord.group, SurveyRecord.person).where(SurveyRecord.id.in_(ids))).all())
    documents = set(db.scalars(select(SurveyRecord.document_id).where(
        SurveyRecord.id.in_(ids), SurveyRecord.document_id.is_not(None))))
    ledger.forget(ids)
    removed = db.execute(delete(SurveyRecord).where(SurveyRecord.id.in_(ids))).rowcount or 0
    files = release_documents(db, documents)
    remaining = set(db.execute(select(SurveyRecord.group, SurveyRecord.person).where(
        tuple_(SurveyRecord.group, SurveyRecord.person).in_(persons))).all()) if persons else set()
    subjects = 0
    for group, person in persons - remaining:
        subjects += db.execute(delete(SurveySubject).where(
            SurveySubject.group == group, SurveySubject.person == person)).rowcount or 0
    db.commit()
    for path in files:
        path.unlink(missing_ok=True)
    return {"phiếu": removed, "đối tượng": subjects, "file gốc": len(files)}


class Ledger:
    """Các phiếu đã nạp. Chạy lại không tạo lại phiếu người dùng đã chủ động xoá sau khi nạp."""

    def __init__(self, path: Path):
        self.path = path
        self.ids: set[str] = set()
        if path.exists():
            for line in path.read_text(encoding="utf-8").splitlines():
                if line.strip():
                    self.ids.add(json.loads(line)["id"])

    def add(self, ids: list[str]) -> None:
        if not ids:
            return
        self.path.parent.mkdir(parents=True, exist_ok=True)
        with self.path.open("a", encoding="utf-8") as output:
            for key in ids:
                output.write(json.dumps({"id": key, "at": datetime.now().isoformat(timespec="seconds")}) + "\n")
        self.ids.update(ids)

    def forget(self, ids: list[str]) -> None:
        """Bỏ các phiếu khỏi ledger (sau khi gỡ để nạp lại). Ghi đè nguyên tử, giữ bản cũ bên cạnh."""
        drop = set(ids)
        self.ids -= drop
        if not drop or not self.path.exists():
            return
        lines = self.path.read_text(encoding="utf-8").splitlines()
        kept = [line for line in lines if line.strip() and json.loads(line)["id"] not in drop]
        shutil.copy2(self.path, self.path.with_name(f"{self.path.stem}-truoc-khi-go-{datetime.now():%Y%m%d-%H%M%S}.jsonl"))
        temporary = self.path.with_suffix(".tmp")
        temporary.write_text("".join(f"{line}\n" for line in kept), encoding="utf-8")
        os.replace(temporary, self.path)

    def reset(self) -> None:
        if self.path.exists():
            self.path.rename(self.path.with_name(f"{self.path.stem}-{datetime.now():%Y%m%d-%H%M%S}.jsonl"))
        self.ids.clear()

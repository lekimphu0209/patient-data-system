#!/usr/bin/env python3
"""Nạp dữ liệu mẫu từ CSV vào database.

Chạy:
    python scripts/load_mock_data.py             # thêm mới / cập nhật theo mã hồ sơ
    python scripts/load_mock_data.py --replace   # xoá sạch bệnh nhân trong CSV rồi nạp lại
    python scripts/load_mock_data.py --dir /path/to/csv

Tên cột trong CSV là đường dẫn trong form_schema.json (``examination.general.weight``),
nên script chỉ cần tách theo dấu chấm để dựng lại cấu trúc phân cấp. Kiểu dữ liệu
(số / nhiều lựa chọn / bảng) được ép theo đúng khai báo của schema, không đoán mò.
"""

from __future__ import annotations

import argparse
import csv
import sys
from collections import defaultdict
from datetime import date
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.core.database import Base, SessionLocal, engine  # noqa: E402
from app.modules.patients.form_service import FormService  # noqa: E402
from app.modules.patients.models import (  # noqa: E402
    Examination,
    MedicalHistory,
    Patient,
)

DEFAULT_DIR = Path(__file__).parent / "mock_data"
MULTI_SEPARATOR = "|"
METADATA_PREFIX = "patient.metadata."


# ==================== Tra cứu kiểu từ schema ====================


def build_type_index(service: FormService) -> dict[str, str]:
    """path -> type. Gộp schema của mọi loại bệnh để phủ hết cột trong CSV."""
    index: dict[str, str] = {}

    def walk(prefix: str, nodes: list[dict]) -> None:
        for node in nodes:
            path = f"{prefix}.{node['id']}" if prefix else node["id"]
            if node["type"] == "group":
                walk(path, node["children"])
            elif node["type"] == "matrix":
                for row in node.get("rows", []):
                    index[f"{path}.{row['id']}"] = "matrix_cell"
            else:
                index[path] = node["type"]

    for disease in ("f20", "f32", "normal"):
        for block in service.get_schema(disease)["blocks"]:
            walk(block["id"], block["children"])
    return index


def build_source_index(service: FormService) -> dict[str, str]:
    """Khối hành chính ghi thẳng vào bảng patients, mỗi field khai `source`."""
    sources: dict[str, str] = {}
    for block in service.get_schema("f20")["blocks"]:
        if block["id"] != "administrative":
            continue
        for node in block["children"]:
            if node.get("source"):
                sources[node["id"]] = node["source"]
    return sources


def coerce(raw: str, node_type: str | None):
    if raw is None or raw == "":
        return None
    if node_type == "checkbox_group":
        return [part for part in raw.split(MULTI_SEPARATOR) if part]
    if node_type == "number":
        try:
            return int(raw) if float(raw).is_integer() else float(raw)
        except ValueError:
            return None
    return raw


def nest(row: dict[str, str], prefix: str, types: dict[str, str]) -> dict:
    """Dựng lại dict lồng từ các cột dạng `a.b.c` có tiền tố `prefix`."""
    result: dict = {}
    for column, raw in row.items():
        if not column.startswith(f"{prefix}."):
            continue
        value = coerce(raw, types.get(column))
        if value is None:
            continue
        cursor = result
        parts = column.split(".")[1:]  # bỏ tiền tố block
        for part in parts[:-1]:
            cursor = cursor.setdefault(part, {})
        cursor[parts[-1]] = value
    return result


# ==================== Nạp dữ liệu ====================


def apply_admin(patient: Patient, values: dict, sources: dict[str, str]) -> None:
    metadata = dict(patient.patient_metadata or {})
    for field_id, source in sources.items():
        if field_id not in values:
            continue
        value = values[field_id]
        if source.startswith(METADATA_PREFIX):
            metadata[source[len(METADATA_PREFIX):]] = value
        else:
            setattr(patient, source.replace("patient.", ""), value)
    patient.patient_metadata = metadata


def parse_date(raw: object) -> date:
    if isinstance(raw, date):
        return raw
    try:
        return date.fromisoformat(str(raw)[:10])
    except (TypeError, ValueError):
        return date.today()


def main() -> None:
    parser = argparse.ArgumentParser(description="Nạp dữ liệu mẫu vào database")
    parser.add_argument("--dir", type=Path, default=DEFAULT_DIR, help="Thư mục chứa CSV")
    parser.add_argument(
        "--replace",
        action="store_true",
        help="Xoá hẳn bệnh nhân trùng mã trong CSV (kèm lần khám, hỏi bệnh) rồi nạp lại",
    )
    args = parser.parse_args()

    patients_csv = args.dir / "patients.csv"
    exams_csv = args.dir / "examinations.csv"
    for path in (patients_csv, exams_csv):
        if not path.exists():
            parser.error(f"Không tìm thấy {path}. Chạy scripts/generate_mock_csv.py trước.")

    Base.metadata.create_all(bind=engine)

    service = FormService()
    types = build_type_index(service)
    sources = build_source_index(service)

    with patients_csv.open(encoding="utf-8") as fh:
        patient_rows = list(csv.DictReader(fh))
    with exams_csv.open(encoding="utf-8") as fh:
        exam_rows = list(csv.DictReader(fh))

    exams_by_code: dict[str, list[dict]] = defaultdict(list)
    for row in exam_rows:
        exams_by_code[row["patient_code"]].append(row)

    db = SessionLocal()
    created = updated = exam_count = 0
    try:
        codes = [row["patient_code"] for row in patient_rows]

        if args.replace:
            existing = db.query(Patient).filter(Patient.patient_code.in_(codes)).all()
            for patient in existing:
                db.query(Examination).filter(Examination.patient_id == patient.id).delete()
                db.query(MedicalHistory).filter(
                    MedicalHistory.patient_id == patient.id
                ).delete()
                db.delete(patient)
            db.commit()
            print(f"Đã xoá {len(existing)} bệnh nhân trùng mã.")

        for row in patient_rows:
            code = row["patient_code"]
            patient = db.query(Patient).filter(Patient.patient_code == code).first()
            if patient:
                updated += 1
            else:
                patient = Patient(patient_code=code, full_name=row["patient_code"])
                db.add(patient)
                created += 1

            patient.diagnosis = row.get("diagnosis") or None
            patient.disease_type = row.get("disease_type") or None
            if row.get("birth_date"):
                patient.birth_date = parse_date(row["birth_date"])
            patient.status = "active"
            patient.deleted_at = None
            apply_admin(patient, nest(row, "administrative", types), sources)
            db.flush()

            # Khối 2 — hỏi bệnh (bệnh nhân bình thường không có khối này).
            history_data = nest(row, "medical_history", types)
            history = (
                db.query(MedicalHistory)
                .filter(MedicalHistory.patient_id == patient.id)
                .first()
            )
            if history_data:
                if not history:
                    history = MedicalHistory(patient_id=patient.id)
                    db.add(history)
                history.data = history_data
            elif history:
                history.data = {}

            # Khối 3 — các lần khám.
            db.query(Examination).filter(Examination.patient_id == patient.id).delete()
            for exam_row in exams_by_code.get(code, []):
                exam_data = nest(exam_row, "examination", types)
                db.add(
                    Examination(
                        patient_id=patient.id,
                        exam_date=parse_date(exam_data.get("exam_info", {}).get("exam_date")),
                        data=exam_data,
                    )
                )
                exam_count += 1

        db.commit()
    except Exception:
        db.rollback()
        raise
    finally:
        db.close()

    print(f"Bệnh nhân : {created} tạo mới, {updated} cập nhật")
    print(f"Lần khám  : {exam_count}")


if __name__ == "__main__":
    main()

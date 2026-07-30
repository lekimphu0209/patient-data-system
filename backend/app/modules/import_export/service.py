import csv
import io
import uuid
from datetime import date, datetime
from pathlib import Path


import pandas as pd
from fastapi import UploadFile
from openpyxl import Workbook
from openpyxl.styles import Alignment, Border, Font, PatternFill, Side
from openpyxl.utils import get_column_letter
from sqlalchemy.orm import Session

from app.modules.patients.models import Patient
from app.modules.patients.repository import PatientRepository
from app.modules.patients.schemas import PatientCreate
from app.modules.patients.service import PatientService

REQUIRED_COLUMNS = ["patient_code", "full_name"]
OPTIONAL_COLUMNS = [
    "birth_date",
    "age",
    "gender",
    "hometown",
    "disease_type",
    "diagnosis",
    "status",
    "phone",
    "contact_person",
    "notes",
]

EXPORT_DIR = Path("storage/exports")
IMPORT_DIR = Path("storage/imports")


def _parse_date(value):
    if pd.isna(value):
        return None
    if isinstance(value, date):
        return value
    try:
        return pd.to_datetime(value, dayfirst=True).date()
    except Exception:
        return None


def _safe_int(value):
    if pd.isna(value):
        return None
    try:
        return int(value)
    except (ValueError, TypeError):
        return None


def _build_import_patient_data(raw: dict) -> dict:
    data = {
        "patient_code": raw.get("patient_code"),
        "full_name": raw.get("full_name"),
        "birth_date": raw.get("birth_date"),
        "age": raw.get("age"),
        "hometown": raw.get("hometown"),
        "disease_type": raw.get("disease_type"),
        "diagnosis": raw.get("diagnosis"),
        "status": raw.get("status") or "active",
    }
    contact_info = {}
    if raw.get("phone"):
        contact_info["phone"] = raw["phone"]
    if raw.get("contact_person"):
        contact_info["contact_person"] = raw["contact_person"]
    if contact_info:
        data["contact_info"] = contact_info

    patient_metadata = {}
    if raw.get("gender"):
        patient_metadata["gender"] = raw["gender"]
    if raw.get("notes"):
        patient_metadata["notes"] = raw["notes"]
    if patient_metadata:
        data["patient_metadata"] = patient_metadata
    return data


def _gender_label(value: str | None) -> str:
    if not value:
        return ""
    mapping = {"male": "Nam", "female": "Nữ", "other": "Khác"}
    return mapping.get(value, value)


def _write_csv_export(patients: list[Patient], filepath: Path) -> None:
    headers = [
        "STT",
        "Mã bệnh nhân",
        "Họ và tên",
        "Ngày sinh",
        "Giới tính",
        "Quê quán",
        "Số điện thoại",
        "Người liên hệ",
        "Chẩn đoán",
        "Ghi chú",
    ]
    with open(filepath, "w", encoding="utf-8-sig", newline="") as f:
        writer = csv.writer(f)
        writer.writerow(headers)
        for idx, p in enumerate(patients, 1):
            writer.writerow(
                [
                    idx,
                    p.patient_code,
                    p.full_name,
                    p.birth_date.isoformat() if p.birth_date else "",
                    _gender_label(p.patient_metadata.get("gender") if p.patient_metadata else None),
                    p.hometown or "",
                    p.contact_info.get("phone", "") if p.contact_info else "",
                    p.contact_info.get("contact_person", "") if p.contact_info else "",
                    p.diagnosis or "",
                    p.patient_metadata.get("notes", "") if p.patient_metadata else "",
                ]
            )


def _write_xlsx_export(patients: list[Patient], filepath: Path, current_user) -> None:
    wb = Workbook()
    ws = wb.active
    ws.title = "Danh sách bệnh nhân"

    ws.merge_cells("A1:J1")
    title_cell = ws["A1"]
    title_cell.value = "Danh sách bệnh nhân"
    title_cell.font = Font(name="Arial", size=16, bold=True)
    title_cell.alignment = Alignment(horizontal="center", vertical="center")
    ws.row_dimensions[1].height = 30

    export_time = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    exported_by = (
        current_user.full_name
        if current_user and getattr(current_user, "full_name", None)
        else (
            current_user.email
            if current_user and getattr(current_user, "email", None)
            else "Unknown"
        )
    )
    ws["A3"] = f"Export Time: {export_time}"
    ws["A4"] = f"Exported By: {exported_by}"
    ws["A3"].font = Font(name="Arial", size=11)
    ws["A4"].font = Font(name="Arial", size=11)

    headers = [
        "STT",
        "Mã bệnh nhân",
        "Họ và tên",
        "Ngày sinh",
        "Giới tính",
        "Quê quán",
        "Số điện thoại",
        "Người liên hệ",
        "Chẩn đoán",
        "Ghi chú",
    ]
    header_row = 6
    header_font = Font(name="Arial", bold=True, size=11, color="FFFFFF")
    header_fill = PatternFill(start_color="4472C4", end_color="4472C4", fill_type="solid")
    thin_border = Border(
        left=Side(style="thin"),
        right=Side(style="thin"),
        top=Side(style="thin"),
        bottom=Side(style="thin"),
    )

    for col, header in enumerate(headers, 1):
        cell = ws.cell(row=header_row, column=col, value=header)
        cell.font = header_font
        cell.fill = header_fill
        cell.alignment = Alignment(horizontal="center", vertical="center")
        cell.border = thin_border

    for idx, p in enumerate(patients, 1):
        row = header_row + idx
        values = [
            idx,
            p.patient_code,
            p.full_name,
            p.birth_date,
            _gender_label(p.patient_metadata.get("gender") if p.patient_metadata else None),
            p.hometown,
            p.contact_info.get("phone") if p.contact_info else None,
            p.contact_info.get("contact_person") if p.contact_info else None,
            p.diagnosis,
            p.patient_metadata.get("notes") if p.patient_metadata else None,
        ]
        for col, value in enumerate(values, 1):
            cell = ws.cell(row=row, column=col, value=value)
            cell.font = Font(name="Arial", size=11)
            cell.border = thin_border
            if col in (1, 4):
                cell.alignment = Alignment(horizontal="center", vertical="center")
            if col == 4 and value:
                cell.number_format = "yyyy-mm-dd"

    for col in range(1, len(headers) + 1):
        max_len = 0
        column_letter = get_column_letter(col)
        for row in range(1, header_row + len(patients) + 1):
            cell = ws.cell(row=row, column=col)
            if cell.value is not None:
                max_len = max(max_len, len(str(cell.value)))
        ws.column_dimensions[column_letter].width = min(max_len + 2, 50)

    wb.save(filepath)


class ImportExportService:
    def __init__(self, db: Session):
        self.db = db
        self.patient_repo = PatientRepository(db)
        self.patient_service = PatientService(db)

    def preview_import_patients(self, file: UploadFile) -> dict:
        IMPORT_DIR.mkdir(parents=True, exist_ok=True)
        contents = file.file.read()
        buffer = io.BytesIO(contents)
        if file.filename and file.filename.endswith(".xlsx"):
            df = pd.read_excel(buffer)
        else:
            df = pd.read_csv(buffer)
        df.columns = [c.strip() for c in df.columns]

        rows = []
        valid_count = 0
        invalid_count = 0
        seen_patient_codes: set[str] = set()

        for idx, row in df.iterrows():
            data = {"row": idx + 2}
            errors = []

            for col in REQUIRED_COLUMNS:
                if col not in df.columns or pd.isna(row.get(col)):
                    errors.append(f"Missing required field: {col}")

            if not errors:
                patient_code = str(row.get("patient_code", "")).strip()
                if patient_code in seen_patient_codes:
                    errors.append(f"Patient code '{patient_code}' is duplicated in file")
                elif self.patient_repo.get_by_patient_code(patient_code):
                    errors.append(f"Patient code '{patient_code}' already exists")
                else:
                    seen_patient_codes.add(patient_code)

            raw = {}
            for col in REQUIRED_COLUMNS + OPTIONAL_COLUMNS:
                if col in df.columns:
                    value = row.get(col)
                    if col == "birth_date":
                        raw[col] = _parse_date(value)
                        if pd.notna(value) and raw[col] is None:
                            errors.append(f"Invalid birth_date format: {value}")
                    elif col == "age":
                        raw[col] = _safe_int(value)
                        if pd.notna(value) and raw[col] is None:
                            errors.append(f"Invalid age value: {value}")
                    else:
                        raw[col] = str(value).strip() if pd.notna(value) else None

            data["data"] = _build_import_patient_data(raw)
            data["valid"] = len(errors) == 0
            data["errors"] = errors

            if data["valid"]:
                valid_count += 1
            else:
                invalid_count += 1

            rows.append(data)

        return {
            "valid_count": valid_count,
            "invalid_count": invalid_count,
            "rows": rows,
        }

    def commit_import_patients(self, rows: list[dict]) -> dict:
        created = 0
        errors = []
        for row in rows:
            if not row.get("valid"):
                continue
            try:
                data = row["data"]
                self.patient_service.create_patient(PatientCreate(**data))
                created += 1
            except Exception as e:
                errors.append({"row": row.get("row"), "error": str(e)})
        return {"created": created, "errors": errors}

    def export_patients(
        self,
        *,
        current_user,
        ids: list[int] | None = None,
        format: str = "xlsx",
        q: str | None = None,
        diagnosis: str | None = None,
        disease_type: str | None = None,
        birth_date_from: date | None = None,
        birth_date_to: date | None = None,
    ) -> str:
        EXPORT_DIR.mkdir(parents=True, exist_ok=True)

        if ids:
            patients = (
                self.db.query(Patient)
                .filter(Patient.id.in_(ids), Patient.deleted_at.is_(None))
                .all()
            )
        else:
            patients = self.patient_repo.get_all(
                search=q,
                diagnosis=diagnosis,
                disease_type=disease_type,
                birth_date_from=birth_date_from,
                birth_date_to=birth_date_to,
            )

        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        filename = f"patients_{timestamp}.{format}"
        filepath = EXPORT_DIR / filename

        if format == "csv":
            _write_csv_export(patients, filepath)
        else:
            _write_xlsx_export(patients, filepath, current_user)

        return str(filepath)

    def get_template(self) -> str:
        EXPORT_DIR.mkdir(parents=True, exist_ok=True)
        df = pd.DataFrame(columns=REQUIRED_COLUMNS + OPTIONAL_COLUMNS)
        filepath = EXPORT_DIR / "patients_import_template.xlsx"
        df.to_excel(filepath, index=False)
        return str(filepath)

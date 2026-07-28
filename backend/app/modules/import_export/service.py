import io
import uuid
from datetime import date
from pathlib import Path

import pandas as pd
from fastapi import UploadFile
from sqlalchemy.orm import Session

from app.modules.patients.models import Patient
from app.modules.patients.repository import PatientRepository
from app.modules.patients.schemas import PatientCreate
from app.modules.patients.service import PatientService

REQUIRED_COLUMNS = ["patient_code", "full_name"]
OPTIONAL_COLUMNS = [
    "birth_date",
    "age",
    "disease_type",
    "diagnosis",
    "status",
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


class ImportExportService:
    def __init__(self, db: Session):
        self.db = db
        self.patient_repo = PatientRepository(db)
        self.patient_service = PatientService(db)

    def preview_import_patients(self, file: UploadFile) -> dict:
        IMPORT_DIR.mkdir(parents=True, exist_ok=True)
        df = pd.read_excel(file.file) if file.filename and file.filename.endswith(".xlsx") else pd.read_csv(file.file)
        df.columns = [c.strip() for c in df.columns]

        rows = []
        valid_count = 0
        invalid_count = 0

        for idx, row in df.iterrows():
            data = {"row": idx + 2}
            errors = []

            for col in REQUIRED_COLUMNS:
                if col not in df.columns or pd.isna(row.get(col)):
                    errors.append(f"Missing required field: {col}")

            if not errors:
                patient_code = str(row.get("patient_code", "")).strip()
                if self.patient_repo.get_by_patient_code(patient_code):
                    errors.append(f"Patient code '{patient_code}' already exists")

            parsed = {}
            for col in REQUIRED_COLUMNS + OPTIONAL_COLUMNS:
                if col in df.columns:
                    value = row.get(col)
                    if col == "birth_date":
                        parsed[col] = _parse_date(value)
                    elif col == "age":
                        parsed[col] = int(value) if pd.notna(value) else None
                    else:
                        parsed[col] = str(value).strip() if pd.notna(value) else None

            data["data"] = parsed
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

    def export_patients(self, ids: list[int] | None = None) -> str:
        EXPORT_DIR.mkdir(parents=True, exist_ok=True)
        query = self.db.query(Patient).filter(Patient.deleted_at.is_(None))
        if ids:
            query = query.filter(Patient.id.in_(ids))
        patients = query.all()

        records = []
        for p in patients:
            records.append({
                "id": p.id,
                "patient_code": p.patient_code,
                "full_name": p.full_name,
                "birth_date": p.birth_date.isoformat() if p.birth_date else None,
                "age": p.age,
                "disease_type": p.disease_type,
                "diagnosis": p.diagnosis,
                "status": p.status,
                "created_at": p.created_at.isoformat() if p.created_at else None,
            })

        df = pd.DataFrame(records)
        filename = f"patients_export_{uuid.uuid4().hex}.xlsx"
        filepath = EXPORT_DIR / filename
        df.to_excel(filepath, index=False)
        return str(filepath)

    def get_template(self) -> str:
        EXPORT_DIR.mkdir(parents=True, exist_ok=True)
        df = pd.DataFrame(columns=REQUIRED_COLUMNS + OPTIONAL_COLUMNS)
        filepath = EXPORT_DIR / "patients_import_template.xlsx"
        df.to_excel(filepath, index=False)
        return str(filepath)

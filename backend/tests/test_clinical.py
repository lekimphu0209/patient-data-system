"""Bệnh án F20/F32: kiểm tra dữ liệu, lưu theo revision, xoá, tải bệnh án từ ảnh, trợ lý dữ liệu.

Mọi bản ghi test dùng mã riêng và được xoá sau mỗi test; file tải lên ghi vào thư mục tạm.
"""

from __future__ import annotations

import json
import random
import string
import uuid
from datetime import date

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, delete, select
from sqlalchemy.orm import sessionmaker

from app.core.config import settings
from app.core.database import Base, SessionLocal
from app.main import app
from app.modules.assistant.snapshot import Snapshot
from app.modules.assistant.tools import TOOLS, ToolError
from app.modules.clinical import service
from app.modules.clinical.models import ClinicalPatient, ClinicalVisit
from app.modules.clinical.schema import FIELDS, FORMS, ClinicalError, clean_patient
from app.modules.documents.models import Document, OcrExtraction
from app.modules.surveys.ocr.extractor import ModelOutput
from tests.survey_files import make_pdf

BASE = "/api/v1/clinical"


def visit(day="2026-11-01", **fields):
    return {"id": uuid.uuid4().hex, "date": day, "createdAt": f"{day}T08:00:00Z", "fields": fields}


def patient(prefix, type_="F20", code="001", **overrides):
    data = {"id": uuid.uuid4().hex, "type": type_, "code": f"{prefix}-{code}", "fullName": "Nguyễn Văn Bệnh",
            "age": "30", "sex": "Nam", "hometown": "Phú Thọ", "residence": ["Nông thôn"], "marital": "Chưa kết hôn",
            "visits": [visit(diagnosis="Tâm thần phân liệt thể paranoid")], "revision": 0}
    data.update(overrides)
    return data


@pytest.fixture
def client():
    with TestClient(app) as test_client:
        login = test_client.post("/api/v1/auth/login", json={
            "email": settings.DEFAULT_USER_EMAIL, "password": settings.DEFAULT_USER_PASSWORD})
        test_client.headers["Authorization"] = f"Bearer {login.json()['access_token']}"
        yield test_client


@pytest.fixture
def prefix(tmp_path, monkeypatch):
    """Mã bệnh nhân riêng của test; xoá mọi bệnh án + file test sau khi xong."""
    value = "T" + "".join(random.choices(string.ascii_uppercase, k=6))
    monkeypatch.setattr(service, "STORAGE_DIR", tmp_path / "clinical")
    yield value
    with SessionLocal() as db:
        patients = list(db.scalars(select(ClinicalPatient).where(ClinicalPatient.code.startswith(value))))
        ocr_codes = list(db.scalars(select(ClinicalPatient).where(ClinicalPatient.code.startswith("OCR-"),
                                                                  ClinicalPatient.full_name == value)))
        for item in patients + ocr_codes:
            document_id = item.document_id
            db.delete(item)
            db.flush()
            if document_id:
                db.execute(delete(OcrExtraction).where(OcrExtraction.document_id == document_id))
                db.execute(delete(Document).where(Document.id == document_id))
        db.commit()


def save(client, data, create=True):
    return client.post(f"{BASE}/save", json={"patient": data, "createOnly": create})


# ---------- biểu mẫu & kiểm tra dữ liệu ----------


def test_forms_match_design(client):
    body = client.get(f"{BASE}/forms").json()
    assert [field["key"] for field in body["identity"]][:4] == ["code", "fullName", "age", "sex"]
    assert len(body["identity"]) == 11
    assert {type_: form["title"] for type_, form in body["forms"].items()} == {
        "F20": "Tâm thần phân liệt", "F32": "Trầm cảm"}
    assert (len(FIELDS["F20"]), len(FIELDS["F32"])) == (107, 160)
    assert len(FORMS["F32"]["sections"]) == 16 and FORMS["F20"]["sections"][0]["key"] == "admin"
    assert TestClient(app).get(f"{BASE}/forms").status_code == 401


@pytest.mark.parametrize("change, message", [
    ({"code": "  "}, "mã bệnh nhân"),
    ({"fullName": ""}, "họ tên, tuổi và giới tính"),
    ({"age": "151"}, "Tuổi phải là số nguyên"),
    ({"age": "2.5"}, "Tuổi phải là số nguyên"),
    ({"sex": "Khác"}, "Giới tính không hợp lệ"),
    ({"type": "F99"}, "Loại bệnh án"),
    ({"marital": "Độc thân"}, "không có trong danh sách"),
    ({"residence": ["Sao Hoả"]}, "không có trong danh sách"),
    ({"visits": []}, "ít nhất một lần khám"),
    ({"visits": [visit(day="2026-02-30")]}, "ngày khám"),
    ({"visits": [visit(weight="-3")]}, "từ 0 trở lên"),
    ({"visits": [visit(weight="nặng")]}, "phải là số"),
    ({"visits": [visit(admissionDate="31/12/2026")]}, "ngày không hợp lệ"),
    ({"visits": [visit(previousDiagnoses=["Cảm cúm"])]}, "không có trong danh sách"),
    ({"visits": [visit(diagnosis="x" * 20001)]}, "tối đa 20000"),
])
def test_validation_rejects_bad_data(change, message):
    with pytest.raises(ClinicalError, match=message):
        clean_patient({**patient("X"), **change}, require_identity=True)


def test_clean_drops_unknown_and_empty_fields():
    data = clean_patient(patient("X", visits=[visit(diagnosis="  Trầm cảm  ", unknownField="x", weight="",
                                                     previousDiagnoses=["Khác", "Trầm cảm"])]), require_identity=True)
    assert data["visits"][0]["fields"] == {"diagnosis": "Trầm cảm", "previousDiagnoses": ["Trầm cảm", "Khác"]}
    assert data["identity"] == {"hometown": "Phú Thọ", "residence": ["Nông thôn"], "marital": "Chưa kết hôn"}
    assert data["age"] == 30


# ---------- lưu / sửa / xoá ----------


def test_create_update_and_concurrency(client, prefix):
    created = save(client, patient(prefix))
    assert created.status_code == 200, created.text
    record = created.json()["patient"]
    assert (record["revision"], record["source"], record["age"], record["residence"]) == (1, "Thủ công", "30", ["Nông thôn"])
    assert record["visits"][0]["fields"]["diagnosis"] == "Tâm thần phân liệt thể paranoid"
    # Tạo lại cùng id hoặc cùng mã (khác hoa thường, khác loại bệnh án) đều bị chặn.
    assert save(client, {**patient(prefix), "id": record["id"]}).status_code == 409
    duplicate = save(client, patient(prefix, type_="F32", code="001".lower(), visits=[visit()]))
    assert duplicate.status_code == 409 and "Mã bệnh nhân đã tồn tại" in duplicate.json()["detail"]
    assert save(client, patient(prefix.lower(), type_="F32")).status_code == 409

    # Thêm lần khám, sửa thông tin: revision tăng; lưu bằng revision cũ bị từ chối.
    second = visit(day="2026-11-20", diagnosis="Ổn định")
    updated = save(client, {**record, "fullName": "Tên mới", "visits": record["visits"] + [second]}, create=False)
    assert updated.status_code == 200
    newer = updated.json()["patient"]
    assert newer["revision"] == 2 and len(newer["visits"]) == 2 and newer["fullName"] == "Tên mới"
    stale = save(client, {**record, "fullName": "Ghi đè"}, create=False)
    assert stale.status_code == 409 and "đã thay đổi" in stale.json()["detail"]
    assert save(client, {**newer, "type": "F32"}, create=False).status_code == 422
    # Bỏ một lần khám khỏi danh sách thì lần khám đó bị xoá.
    trimmed = save(client, {**newer, "visits": newer["visits"][1:]}, create=False).json()["patient"]
    assert [item["id"] for item in trimmed["visits"]] == [second["id"]]
    with SessionLocal() as db:
        assert db.get(ClinicalVisit, record["visits"][0]["id"]) is None

    listed = client.get(f"{BASE}/patients", params={"type": "F20"}).json()["patients"]
    assert any(item["id"] == record["id"] for item in listed)
    assert not any(item["id"] == record["id"] for item in client.get(f"{BASE}/patients", params={"type": "F32"}).json()["patients"])
    assert client.get(f"{BASE}/patient", params={"id": record["id"]}).json()["patient"]["revision"] == 3
    assert client.get(f"{BASE}/patient", params={"id": "khong-co"}).status_code == 404

    assert client.post(f"{BASE}/delete", json={"id": record["id"], "revision": 1}).status_code == 409
    assert client.post(f"{BASE}/delete", json={"id": record["id"], "revision": 3}).json() == {"ok": True}
    with SessionLocal() as db:
        assert db.get(ClinicalPatient, record["id"]) is None
        assert db.scalar(select(ClinicalVisit).where(ClinicalVisit.patient_id == record["id"])) is None


def test_visit_ids_cannot_be_stolen_from_another_patient(client, prefix):
    first = save(client, patient(prefix, code="A")).json()["patient"]
    stolen = patient(prefix, code="B", visits=[{**first["visits"][0]}])
    response = save(client, stolen)
    assert response.status_code == 409


# ---------- tải bệnh án từ ảnh ----------


class FakeExtractor:
    def __init__(self, raw):
        self.raw = raw
        self.calls = 0

    def extract(self, type_, pages):
        self.calls += 1
        return ModelOutput(raw=self.raw, provider="test", model="test-model", usage={"prompt_tokens": 10})


def raw_result(code=None, name="Bệnh nhân ảnh", **fields):
    return {"form_check": {"is_expected_form": True, "observed_title": "Bệnh án"},
            "patient": {"code": code, "fullName": name, "age": "41 tuổi", "sex": "Nữ", "marital": "Đã kết hôn",
                        "education": "Không có", "residence": ["Thành thị", "Sao Hoả"]},
            "visit_date": None, "fields": fields, "uncertain": ["fullName", "diagnosis", "khong-co"],
            "notes": "Chữ viết tay mờ ở phần chẩn đoán."}


def upload(client, type_="F32", name="benh-an.pdf", content=None):
    content = content if content is not None else make_pdf(("Bệnh án trầm cảm",))
    return client.post(f"{BASE}/extract", data={"type": type_},
                       files={"file": (name, content, "application/pdf")})


def test_extract_creates_patient_for_review(client, prefix, monkeypatch, tmp_path):
    fake = FakeExtractor(raw_result(code=f"{prefix}-OCR1", admissionDate="2026-10-05", diagnosis="Trầm cảm nặng",
                                    weight="-5", mood0="Có", mood1="Không rõ"))
    monkeypatch.setattr(service, "get_clinical_extractor", lambda: fake)
    response = upload(client)
    assert response.status_code == 200, response.text
    record = response.json()["patient"]
    assert (record["source"], record["needsReview"], record["code"], record["sex"], record["age"]) == (
        "OCR", True, f"{prefix}-OCR1", "Nữ", "41")
    assert record["marital"] == "Đã kết hôn" and record["education"] == "" and record["residence"] == ["Thành thị"]
    visit_ = record["visits"][0]
    assert visit_["date"] == "2026-10-05"  # không có ngày khám: dùng ngày vào viện
    assert visit_["fields"] == {"admissionDate": "2026-10-05", "diagnosis": "Trầm cảm nặng", "mood0": "Có"}
    assert record["ocr"]["uncertain"] == ["Họ và tên", "Chẩn đoán xác định"]
    assert record["ocr"]["extractedCount"] == 9 and record["ocr"]["dateInferred"] is False
    assert record["hasOriginal"] and record["originalType"] == "pdf"
    original = client.get(f"{BASE}/original", params={"id": record["id"]})
    assert original.status_code == 200 and original.content.startswith(b"%PDF")
    stored = list((tmp_path / "clinical").iterdir())
    assert len(stored) == 1

    # Cùng mã: không tạo hồ sơ khác, không ghi đè; file vừa tải bị xoá.
    again = upload(client)
    assert again.status_code == 409 and "đã có trong hệ thống" in again.json()["detail"]
    assert list((tmp_path / "clinical").iterdir()) == stored

    # Xoá bệnh nhân thì xoá luôn file gốc.
    assert client.post(f"{BASE}/delete", json={"id": record["id"], "revision": record["revision"]}).status_code == 200
    assert list((tmp_path / "clinical").iterdir()) == []


def test_extract_without_code_or_date_generates_them(client, prefix, monkeypatch):
    monkeypatch.setattr(service, "get_clinical_extractor", lambda: FakeExtractor(raw_result(name=prefix)))
    response = upload(client, type_="F20", name="anh.png", content=make_png())
    assert response.status_code == 200, response.text
    record = response.json()["patient"]
    assert record["code"].startswith("OCR-") and record["type"] == "F20" and record["originalType"] == "image"
    assert record["ocr"]["dateInferred"] is True and record["visits"][0]["date"] == service.today()


@pytest.mark.parametrize("raw, status, message", [
    ({**raw_result(), "form_check": {"is_expected_form": False, "observed_title": "Giấy ra viện"}}, 422, "Giấy ra viện"),
    ({"form_check": {"is_expected_form": True}, "patient": {}, "fields": {}, "uncertain": [], "notes": ""}, 422,
     "Chưa nhận dạng được"),
])
def test_extract_rejects_wrong_or_empty_documents(client, prefix, monkeypatch, tmp_path, raw, status, message):
    monkeypatch.setattr(service, "get_clinical_extractor", lambda: FakeExtractor(raw))
    response = upload(client)
    assert response.status_code == status and message in response.json()["detail"]
    assert list((tmp_path / "clinical").iterdir()) == []


def test_extract_validates_upload(client, prefix, monkeypatch, tmp_path):
    fake = FakeExtractor(raw_result())
    monkeypatch.setattr(service, "get_clinical_extractor", lambda: fake)
    assert "JPG, PNG, WebP" in upload(client, name="benh-an.docx").json()["detail"]
    assert upload(client, type_="F99").status_code == 422
    big = upload(client, content=b"%PDF" + b"0" * (service.MAX_UPLOAD_MB * 1024 * 1024 + 1))
    assert big.status_code == 422 and f"{service.MAX_UPLOAD_MB} MB" in big.json()["detail"]
    assert upload(client, content=b"not a pdf").status_code == 422
    assert fake.calls == 0
    assert list((tmp_path / "clinical").iterdir()) == []


def test_extract_reports_model_failure(client, prefix, monkeypatch, tmp_path):
    class Broken:
        def extract(self, type_, pages):
            raise RuntimeError("mất kết nối")

    monkeypatch.setattr(service, "get_clinical_extractor", lambda: Broken())
    response = upload(client)
    assert response.status_code == 502 and "thử lại" in response.json()["detail"]
    assert list((tmp_path / "clinical").iterdir()) == []


def make_png() -> bytes:
    import fitz

    with fitz.open() as document:
        page = document.new_page(width=200, height=200)
        page.insert_text((20, 100), "Benh an")
        return page.get_pixmap(dpi=40).tobytes("png")


# ---------- trợ lý dữ liệu ----------


@pytest.fixture
def snapshot(tmp_path):
    engine = create_engine(f"sqlite:///{tmp_path / 'clinical.db'}")
    Base.metadata.create_all(engine)
    with sessionmaker(bind=engine)() as db:
        def add(code, type_, name, age, sex, visits):
            item = ClinicalPatient(id=uuid.uuid4().hex, type=type_, code=code, code_key=code.lower(), full_name=name,
                                   age=age, sex=sex, identity={"address": "Số 1 Đường Lê Lợi, Hà Nội"}, source="Thủ công")
            item.visits = [ClinicalVisit(id=uuid.uuid4().hex, position=index, date=date.fromisoformat(day),
                                         created_at=f"{day}T08:00:00", fields=fields)
                           for index, (day, fields) in enumerate(visits)]
            db.add(item)
        add("BA-01", "F32", "Trần Thị Thử", 25, "Nữ", [
            ("2026-10-01", {"previousDiagnoses": ["Trầm cảm"], "diagnosis": "Trầm cảm vừa", "author": "BS Nguyễn Văn Ký"}),
            ("2026-11-01", {"previousDiagnoses": ["Trầm cảm", "Khác"], "diagnosis": "Trầm cảm nhẹ"})])
        add("BA-02", "F32", "Lê Văn Mẫu", 31, "Nam", [("2026-11-02", {"previousDiagnoses": ["Hưng cảm"]})])
        add("BA-03", "F20", "Phạm Văn Kiểm", 40, "Nam", [("2026-11-03", {"diagnosis": "Tâm thần phân liệt"})])
        db.commit()
        yield Snapshot().ensure(db)


def test_assistant_clinical_tools(snapshot):
    summary = TOOLS["clinical_summary"].run(snapshot, {"type": None, "field": None})
    assert summary.llm["patients"] == 3 and [row["patients"] for row in summary.llm["by_type"]] == [1, 2]
    dist = TOOLS["clinical_summary"].run(snapshot, {"type": "F32", "field": "previousDiagnoses"})
    assert {item["value"]: item["patients"] for item in dist.llm["distribution"]}["Trầm cảm"] == 1  # chỉ lần gần nhất
    assert dist.llm["answered"] == 2 and "lần khám gần nhất" in dist.method
    with pytest.raises(ToolError, match="find_clinical_fields"):
        TOOLS["clinical_summary"].run(snapshot, {"type": "F32", "field": "khongco"})
    with pytest.raises(ToolError, match="người làm bệnh án"):
        TOOLS["clinical_summary"].run(snapshot, {"type": "F32", "field": "author"})

    found = TOOLS["find_clinical_patients"].run(snapshot, {
        "type": "F32", "conditions": [{"field": "previousDiagnoses", "values": ["tram cam"]}], "match": "all",
        "latest_only": False})
    assert found.llm["matched_patients"] == 1
    block = found.blocks[0]
    assert block["rows"][0]["name"] == "Trần Thị Thử" and block["recordKey"] == "id"
    assert block["rows"][0]["clinicalType"] == "F32"
    text = TOOLS["find_clinical_patients"].run(snapshot, {
        "type": "F32", "conditions": [{"field": "diagnosis", "values": ["nhẹ"]}], "match": "all", "latest_only": True})
    assert text.llm["matched_patients"] == 1
    payload = json.dumps([summary.llm, dist.llm, found.llm], ensure_ascii=False)
    assert "Trần Thị Thử" not in payload and "BA-01" not in payload

    fields = TOOLS["find_clinical_fields"].run(snapshot, {"keyword": "chan doan truoc", "type": "F32"})
    assert fields.llm["matches"][0]["field"] == "previousDiagnoses"

    sql = TOOLS["run_sql"].run(snapshot, {"sql": "SELECT patient_id, type, code, full_name, latest_diagnosis "
                                                 "FROM clinical_patients ORDER BY code", "purpose": "Danh sách"})
    assert "Phạm Văn Kiểm" not in json.dumps(sql.llm, ensure_ascii=False)
    assert sql.blocks[0]["recordKey"] == "id" and sql.blocks[0]["rows"][0]["clinicalType"] in ("F20", "F32")
    assert snapshot.query("SELECT COUNT(*) FROM clinical_fields WHERE field = 'author'").rows == [(0,)]
    assert "Lê Lợi" not in json.dumps(snapshot.query("SELECT * FROM clinical_patients").rows, ensure_ascii=False)

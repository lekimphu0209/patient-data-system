"""Tải một file chứa nhiều phiếu của một người: nhận diện, tách, đọc từng phiếu.

Không gọi API trả phí: bộ bóc tách được thay bằng bản giả đọc nhãn chữ in trên
trang PDF thử ("F08 START", "F09", "KHAC"...).
"""

import io
import re
from uuid import uuid4

import pytest
from PIL import Image
from sqlalchemy import func

from app.core.config import settings
from app.core.database import SessionLocal
from app.modules.documents.models import Document, OcrExtraction
from app.modules.surveys.ocr import extractor as extractor_module
from app.modules.surveys.ocr import service as service_module
from app.modules.surveys.ocr.bundle import (
    BLANK,
    OTHER,
    MultipleCopiesError,
    classify_schema,
    header_strip,
    page_ranges,
    plan_bundle,
)
from app.modules.surveys.ocr.extractor import ModelOutput
from app.modules.surveys.ocr.pages import load_pages
from app.modules.surveys.schemas import FORM_BY_ID, FORMS
from tests.survey_files import BASE, make_image, make_pdf, pdf_page_texts

YOUTH = [form for form in FORMS if form["group"] == "youth"]
MILITARY = [form for form in FORMS if form["group"] == "military"]


def labels(*items):
    """("F08", True) -> mục nhận diện của trang 1, 2, ..."""
    return {"pages": [
        {"page": number, "form": form, "starts_form": starts, "printed_code": code}
        for number, (form, starts, code) in enumerate(items, 1)
    ]}


# ---------- gom trang ----------


def test_plan_splits_youth_packet_into_two_forms():
    raw = labels(("F08", True, None), ("F08", False, None), ("F08", False, None), ("F08", False, None),
                 ("F09", True, None), ("F09", False, None), ("F09", False, None))
    plan = plan_bundle(YOUTH, [1, 2, 3, 4, 5, 6, 7], raw)
    assert [(part.form["id"], part.pages) for part in plan.parts] == [("F08", [1, 2, 3, 4]), ("F09", [5, 6, 7])]
    assert plan.skipped == []


def test_plan_keeps_form_together_across_unrecognised_page():
    raw = labels(("F02", True, None), ("other", True, "KCB-TT.01- Mẫu 02"), ("other", False, "KCB-TT.01- Mẫu 02"),
                 ("F03", True, None), (BLANK, False, None), ("F03", False, None), ("F01", True, None))
    plan = plan_bundle(MILITARY, [1, 2, 3, 4, 6, 7, 9], raw | {"pages": [
        {**item, "page": number} for item, number in zip(raw["pages"], [1, 2, 3, 4, 6, 7, 9])
    ]})
    assert [(part.form["id"], part.pages) for part in plan.parts] == [("F02", [1]), ("F03", [4, 7]), ("F01", [9])]
    assert [(item.pages, item.reason) for item in plan.skipped] == [
        ([2, 3], "không thuộc mẫu nào của nhóm này (mã in: KCB-TT.01- Mẫu 02)"),
        ([6], "trang không có nội dung phiếu"),
    ]


def test_plan_treats_missing_or_invalid_labels_as_other():
    raw = {"pages": [{"page": 1, "form": "F08", "starts_form": True, "printed_code": None},
                     {"page": 2, "form": "F99"}, "rác", {"page": "3"}]}
    plan = plan_bundle(YOUTH, [1, 2, 3], raw)
    assert [part.pages for part in plan.parts] == [[1]]
    assert plan.skipped[0].pages == [2, 3]
    assert plan_bundle(YOUTH, [1], None).parts == []


@pytest.mark.parametrize("items, message", [
    ((("F08", True, None), ("F08", False, None), ("F08", True, None)), "trang 1–2 và trang 3"),
    ((("F08", True, None), ("F09", True, None), ("F08", False, None)), "trang 1 và trang 3"),
])
def test_plan_rejects_more_than_one_copy_of_a_form(items, message):
    with pytest.raises(MultipleCopiesError, match=message):
        plan_bundle(YOUTH, list(range(1, len(items) + 1)), labels(*items))


def test_page_ranges():
    assert page_ranges([5, 1, 2, 3, 7]) == "1–3, 5, 7"
    assert page_ranges([4]) == "4" and page_ranges([]) == ""


def test_classify_schema_is_strict_and_limited_to_group():
    item = classify_schema(YOUTH)["properties"]["pages"]["items"]
    assert item["properties"]["form"]["enum"] == ["F08", "F09", OTHER, BLANK]
    assert item["additionalProperties"] is False and item["required"] == list(item["properties"])


def test_header_strip_keeps_top_of_page_only():
    page = Image.new("RGB", (2000, 2800), "white")
    buffer = io.BytesIO()
    page.save(buffer, format="JPEG")
    strip = Image.open(io.BytesIO(header_strip(buffer.getvalue())))
    assert strip.width == 1400 and abs(strip.height - round(2800 * 0.32 * 1400 / 2000)) <= 1


def test_openai_classify_sends_header_strips(monkeypatch, tmp_path):
    captured = {}

    class Completions:
        def create(self, **kwargs):
            captured.update(kwargs)
            message = type("Message", (), {"refusal": None, "content": '{"pages": []}'})()
            choice = type("Choice", (), {"message": message, "finish_reason": "stop"})()
            return type("Response", (), {"choices": [choice], "usage": None, "model": "gpt-5.6-luna"})()

    client = type("Client", (), {"chat": type("Chat", (), {"completions": Completions()})()})()
    monkeypatch.setattr(extractor_module, "openai_client", lambda: client)
    path = tmp_path / "bo-phieu.pdf"
    path.write_bytes(make_pdf(("F08 START", "F09 START", "F09")))
    output = extractor_module.OpenAISurveyExtractor("gpt-5.6-luna").classify(YOUTH, load_pages(path, dpi=60, max_pages=5))
    assert output.raw == {"pages": []}
    assert captured["response_format"]["json_schema"]["name"] == "page_forms"
    content = captured["messages"][1]["content"]
    assert "F08" in content[0]["text"] and "KCB-TT.02 · Mẫu 02" in content[0]["text"]
    assert [part["text"] for part in content if part["type"] == "text"][1:] == ["Trang 1:", "Trang 2:", "Trang 3:"]
    assert sum(part["type"] == "image_url" for part in content) == 3


# ---------- API ----------


class FakeExtractor:
    """Nhận diện theo nhãn in trên trang thử; đọc phiếu trả phương án đầu của 2 câu đầu."""

    def __init__(self, codes=None, empty=(), failing=()):
        self.codes = codes or {}
        self.empty = set(empty)
        self.failing = set(failing)
        self.calls = []

    def classify(self, forms, pages):
        items = []
        for page in pages.pages:
            found = re.search(r"\bF\d\d\b", page.text)
            form = found.group(0) if found and found.group(0) in {f["id"] for f in forms} else OTHER
            code = "KCB-TT.01- Mẫu 02" if "KHAC" in page.text else None
            written = re.search(r"MA=(\S+)", page.text)
            items.append({"page": page.number, "form": form, "starts_form": "START" in page.text,
                          "printed_code": code, "subject_code": written and written.group(1)})
        return ModelOutput(raw={"pages": items}, provider="test", model="test", usage={"prompt_tokens": 10})

    def extract(self, form, pages):
        self.calls.append((form["id"], [page.number for page in pages.pages]))
        if form["id"] in self.failing:
            raise TimeoutError("hết thời gian")
        if form["id"] in self.empty:
            return ModelOutput(raw={"answers": {}, "subject": {}}, provider="test", model="test")
        choices = [question for question in form["questions"] if question["options"]][:2]
        answers = {
            question["id"]: [question["options"][0]] if question["multi"] else question["options"][0]
            for question in choices
        }
        subject = {"code": self.codes.get(form["id"]), "full_name": None, "survey_date": None}
        if form["id"] == "F09":
            subject["survey_date"] = "2026-10-21"
        return ModelOutput(raw={"answers": answers, "subject": subject, "uncertain": []}, provider="test", model="test")


@pytest.fixture
def fake(monkeypatch):
    def install(**options):
        extractor = FakeExtractor(**options)
        monkeypatch.setattr(service_module, "get_survey_extractor", lambda: extractor)
        return extractor
    return install


def upload_bundle(api, content, group="youth", name="PT.CK001.pdf"):
    return api.post(f"{BASE}/extract-bundle", params={"group": group},
                    files={"file": (name, content, "application/pdf")})


@pytest.fixture
def new_documents():
    """Bản ghi ``Document`` tạo ra trong test (CSDL test dùng chung giữa các lần chạy)."""
    with SessionLocal() as db:
        start = db.query(func.max(Document.id)).scalar() or 0

    def created():
        with SessionLocal() as db:
            return db.query(Document).filter(Document.id > start).all()
    return created


PACKET = ("F08 START PT.CK 001", "F08", None, "F09 START", "F09", "KHAC", None)


def test_bundle_splits_file_into_one_original_per_form(api, storage, fake, new_documents):
    extractor = fake(codes={"F08": "PT.CK 001"})
    response = upload_bundle(api, make_pdf(PACKET))
    assert response.status_code == 200, response.text
    result = response.json()

    assert [draft["form"] for draft in result["drafts"]] == ["F08", "F09"]
    assert sorted(extractor.calls) == [("F08", [1, 2]), ("F09", [4, 5])]
    assert result["fileName"] == "PT.CK001.pdf" and result["pageCount"] == 7
    assert result["subject"]["code"] == "PT.CK.001" and result["subject"]["survey_date"] == "2026-10-21"
    assert result["skipped"] == [
        {"pages": [3, 7], "reason": "trang trắng"},
        {"pages": [6], "reason": "không thuộc mẫu nào của nhóm này (mã in: KCB-TT.01- Mẫu 02)"},
    ]
    f08, f09 = result["drafts"]
    assert f08["pagesRead"] == [1, 2] and f09["pagesRead"] == [4, 5]
    assert f08["fileName"] == "PT.CK001_F08_trang-1-2.pdf" and f09["fileName"] == "PT.CK001_F09_trang-4-5.pdf"
    assert "Tự tách từ file “PT.CK001.pdf” (7 trang): phiếu này ở trang 1–2." in f08["summary"]
    assert f08["answers"] and f09["answers"]

    # File gốc tải lên được thay bằng file riêng của từng phiếu, chỉ gồm trang của phiếu đó.
    documents = {document.id: document for document in new_documents()}
    assert set(documents) == {f08["documentId"], f09["documentId"]}
    assert len(list(storage.iterdir())) == 2
    for draft, expected in ((f08, ["F08 START PT.CK 001", "F08"]), (f09, ["F09 START", "F09"])):
        document = documents[draft["documentId"]]
        assert document.file_name == draft["fileName"] and document.mime_type == "application/pdf"
        with open(document.relative_path, "rb") as file:
            assert [text.splitlines()[0] for text in pdf_page_texts(file.read())] == expected
    with SessionLocal() as db:
        audit = db.query(OcrExtraction).filter_by(document_id=f09["documentId"]).one()
        assert audit.raw_result["bundle"]["pages"] == [4, 5]
        assert audit.raw_result["bundle"]["file"] == "PT.CK001.pdf"
        assert len(audit.raw_result["bundle"]["classification"]["pages"]) == 5


def test_bundle_records_keep_their_own_original(api, storage, fake):
    fake()
    result = upload_bundle(api, make_pdf(PACKET)).json()
    person = f"PT.CK.{uuid4().hex[:6]}"
    ids = []
    for draft in result["drafts"]:
        id = f"OCR-{uuid4().hex}"
        ids.append(id)
        assert api.post(f"{BASE}/records", json={"records": [{
            "id": id, "person": person, "group": "youth", "form": draft["form"], "patient": {},
            "date": "2026-11-20", "status": "draft", "source": "OCR", "answers": draft["answers"],
            "ocr": draft["summary"], "documentId": draft["documentId"],
        }]}).status_code == 201
    original = api.get(f"{BASE}/original", params={"id": ids[1]})
    assert original.status_code == 200 and original.headers["content-type"] == "application/pdf"
    assert pdf_page_texts(original.content)[0].startswith("F09 START")

    assert api.post(f"{BASE}/delete", json={"ids": [ids[0]]}).json() == {"count": 1}
    assert len(list(storage.iterdir())) == 1  # chỉ xoá file của phiếu đã xoá
    assert api.get(f"{BASE}/original", params={"id": ids[1]}).status_code == 200
    api.post(f"{BASE}/delete", json={"ids": [ids[1]]})
    assert not list(storage.iterdir())


def test_bundle_with_single_form_keeps_original_name(api, storage, fake):
    fake()
    result = upload_bundle(api, make_pdf(("F09 START", "F09", None)), name="phieu.pdf").json()
    assert [draft["fileName"] for draft in result["drafts"]] == ["phieu.pdf"]
    assert result["skipped"] == [{"pages": [3], "reason": "trang trắng"}]


def test_bundle_image_uses_uploaded_file(api, storage, fake, monkeypatch):
    def single(forms, pages):
        return ModelOutput(raw={"pages": [{"page": 1, "form": "F08", "starts_form": True, "printed_code": None}]},
                           provider="test", model="test")

    extractor = fake()
    monkeypatch.setattr(extractor, "classify", single)
    content = make_image()
    response = api.post(f"{BASE}/extract-bundle", params={"group": "youth"},
                        files={"file": ("chup.jpg", content, "image/jpeg")})
    assert response.status_code == 200, response.text
    (draft,) = response.json()["drafts"]
    files = list(storage.iterdir())
    assert len(files) == 1 and files[0].read_bytes() == content and draft["fileName"] == "chup.jpg"


def test_bundle_warns_when_forms_disagree_on_identity(api, storage, fake):
    fake(codes={"F08": "PT.CK 001", "F09": "PT.TL 143"})
    result = upload_bundle(api, make_pdf(PACKET)).json()
    assert "PT.CK.001 (phiếu F08); PT.TL.143 (phiếu F09)" in result["warnings"][0]
    assert result["codeCandidates"] == ["PT.CK.001", "PT.TL.143"]
    assert all(result["warnings"][0] in draft["summary"] for draft in result["drafts"])

    fake(codes={"F08": "PT.CK 001", "F09": "pt-ck-1"})
    assert upload_bundle(api, make_pdf(PACKET)).json()["warnings"] == []


def test_bundle_skips_form_that_reads_empty(api, storage, fake):
    fake(empty={"F08"})
    result = upload_bundle(api, make_pdf(PACKET)).json()
    assert [draft["form"] for draft in result["drafts"]] == ["F09"]
    assert {"pages": [1, 2], "reason": "nhận là mẫu F08 nhưng không đọc được nội dung phiếu"} in result["skipped"]
    assert len(list(storage.iterdir())) == 1


@pytest.mark.parametrize("pages, options, message", [
    (("F08 START", "F08", "F09 START", "F08 START"), {}, "hơn một phiếu"),
    (("KHAC", "KHAC"), {}, "Không nhận ra phiếu nào thuộc nhóm Thanh niên"),
    (("F08 START", "F09 START"), {"empty": {"F08", "F09"}}, "Không đọc được phiếu nào"),
])
def test_bundle_rejects_without_leaving_files(api, storage, fake, new_documents, pages, options, message):
    fake(**options)
    response = upload_bundle(api, make_pdf(pages))
    assert response.status_code == 422 and message in response.json()["detail"]
    assert not list(storage.iterdir()) and not new_documents()


def test_bundle_rejects_file_with_too_many_pages(api, storage, fake, monkeypatch):
    fake()
    monkeypatch.setattr(settings, "EXTRACTION_BUNDLE_MAX_PAGES", 2)
    response = upload_bundle(api, make_pdf(("F08 START", "F08", "F09 START")))
    assert response.status_code == 422 and "hơn 2 trang" in response.json()["detail"]
    assert not list(storage.iterdir())


def test_bundle_reports_provider_failure_and_cleans_up(api, storage, fake, new_documents):
    fake(failing={"F09"})
    response = upload_bundle(api, make_pdf(PACKET))
    assert response.status_code == 502 and "thử lại" in response.json()["detail"]
    assert not list(storage.iterdir()) and not new_documents()


def test_bundle_validates_group_and_file_type(api, storage, fake):
    fake()
    assert api.post(f"{BASE}/extract-bundle", params={"group": "staff"},
                    files={"file": ("a.pdf", make_pdf(), "application/pdf")}).status_code == 422
    response = api.post(f"{BASE}/extract-bundle", params={"group": "youth"},
                        files={"file": ("a.docx", b"PK", "application/octet-stream")})
    assert response.status_code == 422 and "Chỉ hỗ trợ" in response.json()["detail"]
    assert not list(storage.iterdir())


def test_stub_classifies_every_page_as_first_form(api, storage):
    result = upload_bundle(api, make_pdf(("Trang 1", "Trang 2")), group="military").json()
    assert [(draft["form"], draft["pagesRead"]) for draft in result["drafts"]] == [(MILITARY[0]["id"], [1, 2])]
    assert result["model"] == "stub" and FORM_BY_ID[MILITARY[0]["id"]]["group"] == "military"


def test_bundle_cross_checks_code_read_twice(api, storage, fake):
    fake(codes={"F08": "PT.CK 021"})
    result = upload_bundle(api, make_pdf(("F08 START MA=PT.CK.081", "F08 MA=180.10.19", "F09 START"))).json()
    assert result["codeCandidates"] == ["PT.CK.021", "PT.CK.081"]
    assert result["subject"]["code"] == "PT.CK.021"
    assert "PT.CK.021 (phiếu F08); PT.CK.081 (đầu trang 1)" in result["warnings"][0]
    assert all("code" in draft["uncertain"] for draft in result["drafts"])

    fake(codes={"F08": "PT.CK 081"})
    result = upload_bundle(api, make_pdf(("F08 START MA=pt.ck.81", "F08", "F09 START"))).json()
    assert result["codeCandidates"] == ["PT.CK.081"] and result["warnings"] == []
    assert not any("code" in draft["uncertain"] for draft in result["drafts"])


def test_bundle_falls_back_to_code_read_from_page_header(api, storage, fake):
    fake()
    result = upload_bundle(api, make_pdf(("F09 START MA=PT.TL.143", "F09"))).json()
    assert result["subject"]["code"] == "PT.TL.143" and result["codeCandidates"] == ["PT.TL.143"]
    assert "chỉ đọc được ở phần đầu trang" in result["warnings"][0]
    assert result["drafts"][0]["uncertain"] == ["code"]


def test_unsaved_extractions_can_be_discarded(api, storage, fake):
    fake()
    drafts = upload_bundle(api, make_pdf(PACKET)).json()["drafts"]
    kept, dropped = drafts[0]["documentId"], drafts[1]["documentId"]
    id = f"OCR-{uuid4().hex}"
    assert api.post(f"{BASE}/records", json={"records": [{
        "id": id, "person": id, "group": "youth", "form": "F08", "patient": {}, "date": "2026-11-20",
        "status": "draft", "source": "OCR", "answers": drafts[0]["answers"], "documentId": kept,
    }]}).status_code == 201

    response = api.post(f"{BASE}/discard-documents", json={"ids": [kept, dropped, 987654321]})
    assert response.json() == {"count": 1}
    assert len(list(storage.iterdir())) == 1  # file của phiếu đã lưu vẫn còn
    with SessionLocal() as db:
        assert db.get(Document, dropped) is None and db.get(Document, kept) is not None
    assert api.post(f"{BASE}/discard-documents", json={"ids": []}).status_code == 422
    api.post(f"{BASE}/delete", json={"ids": [id]})
    assert not list(storage.iterdir())


def test_discard_never_touches_files_outside_survey_storage(api, storage):
    with SessionLocal() as db:
        document = Document(patient_id=None, file_name="khac.pdf", relative_path="storage/uploads/khac.pdf",
                            mime_type="application/pdf", file_type="pdf", checksum="0" * 64)
        db.add(document)
        db.commit()
        document_id = document.id
    try:
        assert api.post(f"{BASE}/discard-documents", json={"ids": [document_id]}).json() == {"count": 0}
        with SessionLocal() as db:
            assert db.get(Document, document_id) is not None
    finally:
        with SessionLocal() as db:
            db.query(Document).filter_by(id=document_id).delete()
            db.commit()

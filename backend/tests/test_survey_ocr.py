"""Bóc tách phiếu khảo sát từ ảnh/PDF và quản lý file gốc.

Mọi test chạy với bộ bóc tách giả lập hoặc bộ thay thế — không gọi API trả phí.
"""

import io
from uuid import uuid4

import pytest
from PIL import Image

from app.core.config import settings
from app.core.database import SessionLocal
from app.modules.documents.models import Document, OcrExtraction
from app.modules.surveys.ocr import extractor as extractor_module
from app.modules.surveys.ocr import service as service_module
from app.modules.surveys.ocr.extractor import ModelOutput
from app.modules.surveys.ocr.pages import UnreadableFileError, load_pages
from app.modules.surveys.ocr.schema import NO_EVENT, form_prompt, normalize, response_schema
from app.modules.surveys.schemas import FORM_BY_ID
from tests.survey_files import BASE, make_image, make_pdf


def use_extractor(monkeypatch, extract):
    class Replacement:
        def extract(self, form, pages):
            return extract(form, pages)

    monkeypatch.setattr(service_module, "get_survey_extractor", lambda: Replacement())


def upload(api, form="F03", content=None, name="phieu.pdf"):
    content = make_pdf() if content is None else content
    return api.post(f"{BASE}/extract", params={"form": form}, files={"file": (name, content, "application/octet-stream")})


# ---------- prompt & schema ----------


def walk(schema):
    yield schema
    for child in schema.get("properties", {}).values():
        yield from walk(child)
    if "items" in schema:
        yield from walk(schema["items"])


@pytest.mark.parametrize("form_id", sorted(FORM_BY_ID))
def test_schema_is_strict_and_covers_every_question(form_id):
    form = FORM_BY_ID[form_id]
    schema = response_schema(form)
    for node in walk(schema):
        if node.get("type") == "object":
            assert node["additionalProperties"] is False
            assert node["required"] == list(node["properties"])
    answers = schema["properties"]["answers"]["properties"]
    assert list(answers) == [question["id"] for question in form["questions"]]
    for question in form["questions"]:
        spec = answers[question["id"]]
        if not question["options"]:
            assert spec == {"type": ["string", "null"]}
        elif question["multi"]:
            assert spec["items"]["enum"] == question["options"]
        else:
            assert spec["enum"] == [*question["options"], None]


def test_prompt_lists_questions_and_options_in_paper_order():
    form = FORM_BY_ID["F06"]
    prompt = form_prompt(form)
    assert form["code"] in prompt
    positions = [prompt.index(f"{question['id']} — câu thứ {index}") for index, question in enumerate(form["questions"], 1)]
    assert positions == sorted(positions)
    assert "[1] 1-2; [2] 3-4; [3] 5-6; [4] 7-9; [5] Từ 10 trở lên" in prompt


def test_templates_match_paper_forms():
    f02 = {question["id"]: question for question in FORM_BY_ID["F02"]["questions"]}
    assert f02["Q008"]["options"] == ["Kết hôn", "Ly thân", "Ly hôn", "Độc thân", "Góa vợ/chồng"]
    assert f02["Q009"]["options"] == ["Sĩ quan", "Quân nhân chuyên nghiệp", "Học viên", "Hạ sĩ quan/chiến sĩ"]
    f06 = FORM_BY_ID["F06"]["questions"]
    assert all(question["options"] and "Phương án trả lời" not in question["options"] for question in f06)
    assert f06[12]["options"] == ["Không", "Có nhưng không phải trong 12 tháng qua", "Có, trong 12 tháng qua"]
    assert {FORM_BY_ID[f"F0{number}"]["code"][-6:] for number in range(3, 8)} == {f"Mẫu 0{n}" for n in range(3, 8)}


# ---------- chuẩn hoá kết quả model ----------


def test_normalize_keeps_only_valid_options_and_flags_the_rest():
    form = FORM_BY_ID["F03"]
    result = normalize(form, {
        "answers": {"Q001": "Không bao giờ", "Q002": "Hiếm khi", "Q003": None, "Q004": "Liên tục"},
        "uncertain": ["Q004", "Q999", 5],
        "subject": {},
    })
    assert result.answers == {"Q001": "Không bao giờ", "Q004": "Liên tục"}
    assert result.uncertain == ["Q002", "Q004"]
    assert result.is_expected_form


def test_normalize_enforces_multi_choice_rules():
    form = FORM_BY_ID["F01"]
    q015, q017, q018 = (FORM_BY_ID["F01"]["questions"][index] for index in (14, 16, 17))
    result = normalize(form, {"answers": {
        "Q015": [q015["options"][0], q015["options"][0], "Bịa ra"],
        "Q017": q017["options"][:3],
        "Q018": [q018["options"][0], NO_EVENT],
    }})
    assert result.answers == {"Q015": [q015["options"][0]]}
    assert result.uncertain == ["Q015", "Q017", "Q018"]


def test_normalize_cleans_subject_fields():
    form = FORM_BY_ID["F02"]
    result = normalize(form, {
        "subject": {
            "code": "KCB-TT.01 QK1. 01", "full_name": "  Hà   Anh Tuấn ", "birth_year": "2099",
            "birth_date": "1981-02-30", "hometown": None, "unit": "....", "survey_date": "05/11/2026",
        },
        "answers": {"Q002": "1981", "Q006": "Hữu Lũng, Lạng Sơn......"},
    })
    assert result.subject == {
        "code": "QK1.01", "full_name": "Hà Anh Tuấn", "birth_year": "1981", "birth_date": None,
        "hometown": None, "unit": None, "survey_date": "2026-11-05",
    }
    assert result.answers["Q006"] == "Hữu Lũng, Lạng Sơn"


def test_normalize_fills_subject_from_answers_and_rejects_bad_dates():
    form = FORM_BY_ID["F02"]
    result = normalize(form, {
        "subject": {"birth_date": "1990-05-04", "birth_year": "1991", "survey_date": "2999-01-01"},
        "answers": {"Q001": "Nguyễn Văn A", "Q002": "1991"},
    })
    assert result.subject["full_name"] == "Nguyễn Văn A"
    assert result.subject["birth_year"] == "1991"
    assert result.subject["birth_date"] is None  # lệch năm sinh -> bỏ
    assert result.subject["survey_date"] is None  # ngày tương lai -> bỏ


def test_normalize_detects_wrong_form_and_empty_result():
    form = FORM_BY_ID["F03"]
    wrong = normalize(form, {"form_check": {"is_expected_form": False, "observed_title": "PHIẾU LO ÂU"}})
    assert not wrong.is_expected_form and wrong.observed_title == "PHIẾU LO ÂU"
    assert normalize(form, {"answers": {"Q001": None}}).is_empty
    assert normalize(form, "không phải JSON object").is_empty


# ---------- đọc file ----------


def test_pdf_pages_skip_blank_and_respect_page_limit(tmp_path):
    path = tmp_path / "phieu.pdf"
    path.write_bytes(make_pdf(("Trang 1", None, "Trang 3", "Trang 4")))
    pages = load_pages(path, dpi=60, max_pages=2)
    assert [page.number for page in pages.pages] == [1, 3]
    assert pages.skipped_blank == [2]
    assert pages.truncated and pages.total_pages == 4
    assert pages.pages[0].jpeg[:3] == b"\xff\xd8\xff"
    assert "Trang 1" in pages.text_layer


def test_image_is_rotated_by_exif_and_flattened(tmp_path):
    rotated = tmp_path / "chup.jpg"
    rotated.write_bytes(make_image(orientation=6))
    image = Image.open(io.BytesIO(load_pages(rotated, dpi=60, max_pages=5).pages[0].jpeg))
    assert image.size == (20, 40)

    transparent = tmp_path / "trong.png"
    transparent.write_bytes(make_image(mode="RGBA", fmt="PNG"))
    image = Image.open(io.BytesIO(load_pages(transparent, dpi=60, max_pages=5).pages[0].jpeg))
    assert image.mode == "RGB" and image.getpixel((5, 5))[0] > 240  # nền trắng, không đen


@pytest.mark.parametrize("name, content, message", [
    ("hong.pdf", b"%PDF-1.4 rac", "PDF"),
    ("hong.png", b"khong phai anh", "ảnh"),
    ("trang.pdf", make_pdf((None, None)), "trống"),
    ("van-ban.docx", b"PK", "định dạng"),
])
def test_unreadable_files_are_rejected(tmp_path, name, content, message):
    path = tmp_path / name
    path.write_bytes(content)
    with pytest.raises(UnreadableFileError, match=message):
        load_pages(path, dpi=60, max_pages=5)


# ---------- API ----------


def test_extract_returns_draft_and_keeps_original(api, storage):
    response = upload(api)
    assert response.status_code == 200, response.text
    draft = response.json()
    assert draft["model"] == "stub" and draft["pageCount"] == 3 and draft["pagesRead"] == [1, 3]
    assert draft["subject"]["code"] == "STUB.001" and draft["form"] == "F03"
    assert draft["answers"]["Q001"] == "Không bao giờ" and "Q002" not in draft["answers"]
    assert "Bỏ qua trang trắng: 2." in draft["warnings"]
    assert "phieu.pdf" in draft["summary"]

    with SessionLocal() as db:
        document = db.get(Document, draft["documentId"])
        assert document.mime_type == "application/pdf" and document.patient_id is None
        assert len(document.checksum) == 64
        assert db.query(OcrExtraction).filter_by(document_id=document.id).count() == 1
    assert len(list(storage.iterdir())) == 1


def test_extracted_record_serves_original_until_deleted(api, storage):
    content = make_pdf()
    draft = upload(api, content=content).json()
    id = f"OCR-{uuid4().hex}"
    record = {
        "id": id, "person": id, "group": "military", "form": "F03", "patient": {"fullName": "Thử nghiệm"},
        "date": "2026-11-20", "status": "draft", "source": "OCR", "answers": draft["answers"],
        "ocr": draft["summary"], "documentId": draft["documentId"],
    }
    assert api.post(f"{BASE}/records", json={"records": [record]}).status_code == 201

    listed = next(row for row in api.get(f"{BASE}/records").json() if row["id"] == id)
    assert listed["hasOriginal"] and listed["originalType"] == "pdf" and listed["hasOCR"]
    original = api.get(f"{BASE}/original", params={"id": id})
    assert original.status_code == 200 and original.content == content
    assert original.headers["content-type"] == "application/pdf"
    assert original.headers["content-disposition"].startswith("inline")

    assert api.post(f"{BASE}/delete", json={"ids": [id]}).json() == {"count": 1}
    assert not list(storage.iterdir())
    with SessionLocal() as db:
        assert db.get(Document, draft["documentId"]) is None
    assert api.get(f"{BASE}/original", params={"id": id}).status_code == 404


def test_record_without_original(api):
    id = f"TC-{uuid4().hex}"
    record = {
        "id": id, "person": id, "group": "military", "form": "F03", "patient": {},
        "date": "2026-11-20", "status": "draft", "source": "Thủ công",
    }
    assert api.post(f"{BASE}/records", json={"records": [{**record, "documentId": 987654321}]}).status_code == 422
    assert api.post(f"{BASE}/records", json={"records": [record]}).status_code == 201
    listed = next(row for row in api.get(f"{BASE}/records").json() if row["id"] == id)
    assert not listed["hasOriginal"] and listed["originalType"] is None
    assert api.get(f"{BASE}/original", params={"id": id}).status_code == 404
    api.post(f"{BASE}/delete", json={"ids": [id]})


@pytest.mark.parametrize("params, name, content, status, message", [
    ({"form": "F99"}, "phieu.pdf", None, 422, "biểu mẫu"),
    ({"form": "F03"}, "phieu.docx", b"PK", 422, "Chỉ hỗ trợ"),
    ({"form": "F03"}, "phieu.pdf", b"", 422, "rỗng"),
    ({"form": "F03"}, "phieu.pdf", b"%PDF-1.4 rac", 422, "PDF"),
])
def test_extract_rejects_bad_input_without_leaving_files(api, storage, params, name, content, status, message):
    content = make_pdf() if content is None else content
    response = api.post(f"{BASE}/extract", params=params, files={"file": (name, content, "application/pdf")})
    assert response.status_code == status
    assert message in response.json()["detail"]
    assert not list(storage.iterdir())


def test_extract_rejects_oversized_file(api, storage, monkeypatch):
    monkeypatch.setattr(settings, "EXTRACTION_MAX_FILE_MB", 0)
    response = upload(api)
    assert response.status_code == 422 and "giới hạn" in response.json()["detail"]
    assert not list(storage.iterdir())


def test_extract_rejects_wrong_form_and_empty_result(api, storage, monkeypatch):
    def wrong_form(form, pages):
        return ModelOutput(raw={"form_check": {"is_expected_form": False, "observed_title": "PHIẾU LO ÂU"},
                                "answers": {"Q001": "Không bao giờ"}}, provider="test", model="test")

    use_extractor(monkeypatch, wrong_form)
    response = upload(api)
    assert response.status_code == 422 and "PHIẾU LO ÂU" in response.json()["detail"]

    use_extractor(monkeypatch, lambda form, pages: ModelOutput(raw={}, provider="test", model="test"))
    response = upload(api)
    assert response.status_code == 422 and "Không đọc được" in response.json()["detail"]
    assert not list(storage.iterdir())
    with SessionLocal() as db:
        assert db.query(Document).filter(Document.relative_path.like(f"{storage}%")).count() == 0


def test_extract_reports_provider_failure(api, storage, monkeypatch):
    def failing(form, pages):
        raise TimeoutError("hết thời gian")

    use_extractor(monkeypatch, failing)
    response = upload(api)
    assert response.status_code == 502 and "thử lại" in response.json()["detail"]
    assert not list(storage.iterdir())


def test_openai_extractor_sends_strict_schema_and_images(monkeypatch, tmp_path):
    """Kiểm tra request gửi đi mà không gọi mạng."""
    captured = {}

    class Completions:
        def create(self, **kwargs):
            captured.update(kwargs)
            message = type("Message", (), {"refusal": None, "content": '{"answers": {}}'})()
            choice = type("Choice", (), {"message": message, "finish_reason": "stop"})()
            return type("Response", (), {"choices": [choice], "usage": None, "model": "gpt-5.6-luna"})()

    client = type("Client", (), {"chat": type("Chat", (), {"completions": Completions()})()})()
    monkeypatch.setattr(extractor_module, "openai_client", lambda: client)
    monkeypatch.setattr(settings, "EXTRACTION_REASONING_EFFORT", "low")
    path = tmp_path / "phieu.pdf"
    path.write_bytes(make_pdf(("Trang 1", "Trang 2")))

    output = extractor_module.OpenAISurveyExtractor("gpt-5.6-luna").extract(
        FORM_BY_ID["F03"], load_pages(path, dpi=60, max_pages=5)
    )
    assert output.raw == {"answers": {}} and output.model == "gpt-5.6-luna"
    assert captured["reasoning_effort"] == "low" and "temperature" not in captured
    assert captured["response_format"]["json_schema"]["strict"] is True
    content = captured["messages"][1]["content"]
    images = [part for part in content if part["type"] == "image_url"]
    assert len(images) == 2 and all(part["image_url"]["detail"] == "high" for part in images)
    assert "Trang 2" in content[-1]["text"]  # lớp văn bản PDF đi kèm làm gợi ý

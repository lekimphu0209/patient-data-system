"""Nạp hàng loạt phiếu scan của bệnh viện (scripts/hospital_ingest).

Không gọi API trả phí: VLM được thay bằng bản giả đọc nhãn chữ in trên trang PDF thử
("F08 START MA=...", "KHAC"...). Mỗi test dùng một tiền tố mã riêng để không đụng dữ
liệu của test khác trong CSDL test dùng chung.
"""

import json
import random
import string
import threading
import unicodedata
from collections import Counter
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

import pytest
from sqlalchemy import create_engine, delete, func, select
from sqlalchemy.orm import sessionmaker

from app.core.database import Base, SessionLocal
from app.modules.auth.models import User
from app.modules.documents.models import Document, OcrExtraction
from app.modules.patients.models import Patient
from app.modules.surveys.models import SurveyRecord, SurveySubject
from app.modules.surveys.ocr.bundle import OTHER
from app.modules.surveys.ocr.extractor import ModelOutput, ModelResponseError
from app.modules.surveys.schemas import FORM_BY_ID, FORMS
from scripts.hospital_ingest import store
from scripts.hospital_ingest.__main__ import main as cli
from scripts.hospital_ingest.pipeline import Options, Runner
from scripts.hospital_ingest.segment import (
    assign_numbers, choose_prefix, choose_width, lead_form, numbers_read, segment_pages, split_code,
)
from scripts.hospital_ingest.sources import code_hint, discover
from tests.survey_files import make_pdf, pdf_page_texts

YOUTH = [form for form in FORMS if form["group"] == "youth"]
MILITARY = [form for form in FORMS if form["group"] == "military"]
YOUTH_DIR = "Đối tượng thanh niên"
MILITARY_DIR = "Đối tượng nhập ngũ "  # tên thật có dấu cách cuối


# ---------- dữ liệu thử ----------


def youth_person(prefix, number, read=None):
    code = f"MA={prefix}.{read if read is not None else f'{number:03d}'}"
    return [f"F08 START {code}", "F08", f"F09 START {code}", "F09", None]


def military_person(prefix, number):
    code = f"MA={prefix}.{number:02d}"
    return [f"F02 START {code}", None, "KHAC", "KHAC", f"F03 START {code}", "F03", None]


def write_pdf(path: Path, pages) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(make_pdf(tuple(pages)))
    return path


class FakeVLM:
    """Đọc nhãn trên trang thử. Đếm lượt gọi; có thể giả lập lỗi."""

    def __init__(self, *, fail_after=None, model_error_forms=(), classify_error_pages=(), tokens=1000):
        self.calls = []
        self.fail_after = fail_after
        self.model_error_forms = set(model_error_forms)
        self.classify_error_pages = set(classify_error_pages)
        self.tokens = tokens
        self._lock = threading.Lock()

    def _count(self, what, pages):
        with self._lock:
            self.calls.append((what, [page.number for page in pages.pages]))
            if self.fail_after is not None and len(self.calls) > self.fail_after:
                raise ConnectionError("mất mạng")

    def classify(self, forms, pages):
        self._count("classify", pages)
        if self.classify_error_pages & {page.number for page in pages.pages}:
            raise ModelResponseError("Model trả về dữ liệu không đọc được.")
        items = []
        for page in pages.pages:
            words = page.text.split()
            form = next((word for word in words if word in {item["id"] for item in forms}), OTHER)
            written = next((word[3:] for word in words if word.startswith("MA=")), None)
            items.append({"page": page.number, "form": form, "starts_form": "START" in words,
                          "printed_code": "KCB-TT.01- Mẫu 02" if "KHAC" in words else None,
                          "subject_code": written})
        return ModelOutput(raw={"pages": items}, provider="test", model="test",
                           usage={"prompt_tokens": self.tokens, "completion_tokens": 10})

    def extract(self, form, pages):
        self._count(form["id"], pages)
        if form["id"] in self.model_error_forms:
            raise ModelResponseError("Kết quả của model bị cắt giữa chừng.")
        answers = {}
        for question in form["questions"]:
            if question["options"]:
                answers[question["id"]] = [question["options"][0]] if question["multi"] else question["options"][0]
            else:
                answers[question["id"]] = "Văn bản"
        words = " ".join(page.text for page in pages.pages).split()
        code = next((word[3:] for word in words if word.startswith("MA=")), None)
        subject = {"code": code, "full_name": f"Người {code}", "birth_year": "2004", "survey_date": "2026-10-21"}
        return ModelOutput(raw={"form_check": {"is_expected_form": True}, "answers": answers, "subject": subject,
                                "uncertain": []},
                           provider="test", model="test", usage={"prompt_tokens": self.tokens, "completion_tokens": 10})


@pytest.fixture(autouse=True)
def low_resolution(monkeypatch):
    """Trang thử chỉ có nhãn chữ to: render độ phân giải thấp cho test chạy nhanh."""
    from app.core.config import settings

    monkeypatch.setattr(settings, "EXTRACTION_PDF_DPI", 40)


@pytest.fixture
def prefix(api):
    """Tiền tố mã riêng của test (chữ cái), dọn dữ liệu test sau khi xong."""
    value = "T" + "".join(random.choices(string.ascii_uppercase, k=5))
    yield value
    with SessionLocal() as db:
        documents = list(db.scalars(select(SurveyRecord.document_id).where(SurveyRecord.person.startswith(value))))
        db.execute(delete(SurveyRecord).where(SurveyRecord.person.startswith(value)))
        db.execute(delete(SurveySubject).where(SurveySubject.person.startswith(value)))
        db.execute(delete(OcrExtraction).where(OcrExtraction.document_id.in_(documents)))
        db.execute(delete(Document).where(Document.id.in_(documents)))
        db.commit()


@pytest.fixture
def ingest(tmp_path):
    """Chạy script nạp trên thư mục dữ liệu thử; trả về (runner, kết quả)."""
    storage = tmp_path / "storage" / "surveys"

    def run(vlm, **options):
        settings = {"allow_existing": True} | options
        runner = Runner(
            Options(data=tmp_path / "data", work=tmp_path / "work", workers=4, processes=1, **settings),
            extractor=vlm,
            executor_factory=lambda size: ThreadPoolExecutor(1),  # PyMuPDF không an toàn đa luồng
            storage_dir=storage,
            log=logs.append,
            sleep=lambda seconds: None,
        )
        return runner, runner.run()

    logs: list[str] = []
    run.logs = logs
    run.storage = storage
    run.work = tmp_path / "work"
    run.data = tmp_path / "data"
    return run


def records_of(prefix):
    with SessionLocal() as db:
        rows = db.scalars(select(SurveyRecord).where(SurveyRecord.person.startswith(prefix))
                          .order_by(SurveyRecord.id)).all()
        return [(row, db.get(Document, row.document_id)) for row in rows]


# ---------- tìm file ----------


def test_discover_maps_folders_to_groups_and_reads_ranges(tmp_path):
    root = tmp_path / "data"
    write_pdf(root / unicodedata.normalize("NFD", YOUTH_DIR) / "PT.CK 01 - 80-11232026004719.pdf", ["F08"])
    write_pdf(root / YOUTH_DIR / "PT.PL 86 - 165-11222026233534.pdf", ["F08"])
    write_pdf(root / MILITARY_DIR / "QK1 181 - 300" / "Phiếu 181 - 230.pdf", ["F02"])
    write_pdf(root / MILITARY_DIR / "QK1. 01 - 180" / "phieu 01- 41.pdf", ["F02"])
    write_pdf(root / "scan trạm y tế cẩm khê" / "PT.CK 01 - 80.pdf", ["F08"])  # bản trùng: bỏ qua
    write_pdf(root / "ocr-samples" / "x.pdf", ["F08"])
    (root / YOUTH_DIR / "ghi-chu.txt").write_text("không phải PDF")

    found = [(item.group, item.hint, item.start, item.end, item.digits, item.expected) for item in discover(root)]
    assert found == [
        ("youth", "PT.CK", 1, 80, 2, 80),
        ("youth", "PT.PL", 86, 165, 2, 80),
        ("military", "QK1", 1, 41, 2, 41),
        ("military", "QK1", 181, 230, 3, 50),
    ]


def test_code_hint():
    assert code_hint("PT.CK ") == "PT.CK" and code_hint("QK1. ") == "QK1"
    assert code_hint("phieu ") is None and code_hint("Phiếu ") is None and code_hint("") is None
    assert code_hint("12 ") is None


# ---------- tách người ----------


def labels_for(pages):
    """Trang thử -> nhãn nhận diện như VLM giả trả về (bỏ trang trắng)."""
    vlm = FakeVLM()
    from app.modules.surveys.ocr.pages import PageImage, PageSet

    images = [PageImage(number, b"", text) for number, text in enumerate(pages, 1) if text is not None]
    group = MILITARY if any("F02" in (text or "") for text in pages) else YOUTH
    raw = vlm.classify(group, PageSet(images, len(pages))).raw
    return group, [image.number for image in images], {item["page"]: item for item in raw["pages"]}


def test_segment_splits_people_when_a_form_repeats():
    group, numbers, labels = labels_for(youth_person("PT.CK", 1) + youth_person("PT.CK", 2) + youth_person("PT.CK", 3))
    segments = segment_pages(group, numbers, labels)
    assert [[(part.form["id"], part.pages) for part in segment.parts] for segment in segments] == [
        [("F08", [1, 2]), ("F09", [3, 4])],
        [("F08", [6, 7]), ("F09", [8, 9])],
        [("F08", [11, 12]), ("F09", [13, 14])],
    ]
    assert segments[1].written == [(6, "PT.CK.002"), (8, "PT.CK.002")]


def test_segment_without_title_page_or_with_missing_form():
    pages = youth_person("A", 1) + ["F08", "F08", "F09 START MA=A.002", "F09", None] + ["F09 START MA=A.003", "F09"]
    group, numbers, labels = labels_for(pages)
    segments = segment_pages(group, numbers, labels)
    # Người 2 mất trang tiêu đề F08 vẫn tách đúng; người 3 thiếu hẳn F08.
    assert [[part.pages for part in segment.parts] for segment in segments] == [
        [[1, 2], [3, 4]], [[6, 7], [8, 9]], [[11, 12]],
    ]


def test_segment_keeps_unknown_pages_with_the_current_person():
    group, numbers, labels = labels_for(["KHAC"] + military_person("QK1", 1) + military_person("QK1", 2))
    segments = segment_pages(group, numbers, labels)
    assert [(segment.pages, segment.other) for segment in segments] == [
        ([1, 2, 4, 5, 6, 7], [1, 4, 5]),
        ([9, 11, 12, 13, 14], [11, 12]),
    ]
    assert segment_pages(group, [1], {1: {"form": OTHER}}) == []


def pack_labels(*people):
    """Nhãn trang như VLM trả về cho bộ phiếu quân nhân thật: mã viết tay chỉ ở trang đầu F02.

    Mỗi người là danh sách (mẫu, là trang đầu mẫu, mã viết tay).
    """
    sequence = [page for person in people for page in person]
    return {number: {"page": number, "form": form, "starts_form": starts, "subject_code": code}
            for number, (form, starts, code) in enumerate(sequence, 1)}


def pack(code, f05_second_page=("F05", False)):
    return [("F02", True, code), (OTHER, True, None), (OTHER, False, None), ("F03", True, None), ("F03", False, None),
            ("F04", True, None), ("F04", False, None), ("F05", True, None), (*f05_second_page, None)]


def test_lead_form_is_the_form_carrying_the_handwritten_code():
    ids = {form["id"] for form in MILITARY}
    assert lead_form(ids, pack_labels(pack("Q.01"), pack("Q.02"))) == "F02"
    assert lead_form(ids, pack_labels(pack("Q.01"))) is None  # một trang thì chưa đủ chắc
    _, _, youth_labels = labels_for(youth_person("PT.CK", 1) + youth_person("PT.CK", 2))
    assert lead_form({form["id"] for form in YOUTH}, youth_labels) is None  # mã ở cả F08 và F09: không rõ


def test_misread_continuation_page_does_not_shift_later_people():
    # Trang 2 của F05 người 1 bị đọc thành "F03". Cách tách cũ mở người mới ở đó và mọi ranh
    # giới phía sau lệch nửa người (lỗi thật ở file "Phiếu 181 - 230", trang 334).
    labels = pack_labels(pack("Q.01", ("F03", False)), pack("Q.02"), pack("Q.03"))
    segments = segment_pages(MILITARY, sorted(labels), labels)
    assert [segment.pages[0] for segment in segments] == [1, 10, 19]
    assert [(part.form["id"], part.pages) for part in segments[0].parts] == [
        ("F02", [1]), ("F03", [4, 5]), ("F04", [6, 7]), ("F05", [8, 9])]
    assert [segment.written for segment in segments] == [[(1, "Q.01")], [(10, "Q.02")], [(19, "Q.03")]]


def test_title_page_realigns_people_after_a_wrong_split():
    # Trang đọc nhầm thành trang ĐẦU của một mẫu đã có thì vẫn tách (có thể là người mất trang
    # tiêu đề), nhưng trang tiêu đề kế tiếp đưa ranh giới về đúng chỗ.
    labels = pack_labels(pack("Q.01", ("F03", True)), pack("Q.02"), pack("Q.03"))
    segments = segment_pages(MILITARY, sorted(labels), labels)
    assert [segment.pages for segment in segments][1:] == [[9], list(range(10, 19)), list(range(19, 28))]
    assert segments[1].written == []


# ---------- gán mã ----------


def test_split_code_and_numbers_read():
    assert split_code("PT.TL 085") == ("PT.TL", "085")
    assert split_code("QK1.41") == ("QK1", "41") and split_code("QK1.02") == ("QK1", "02")
    assert split_code("085") == ("", "085") and split_code("PT.TL") is None and split_code(None) is None
    assert numbers_read(["PT.TL.085", "PT.TL 85", "QH1.02", "rác"]) == Counter({85: 2, 2: 1})


def test_choose_prefix_prefers_what_is_written_on_the_forms():
    assert choose_prefix("PT.PL", [["PT.TL.001", "PT.TL 001"], ["PT.TL.002"], ["PT.TI.003"]])[0] == "PT.TL"
    # Mực đỏ đọc ra lộn xộn: tên file vẫn được 1/5 số người xác nhận thì giữ tên file.
    reads = [["QK1.01"], ["QH1.02"], ["QCH.03"], ["QĐL.04"], ["QK1.05"]]
    assert choose_prefix("QK1", reads)[0] == "QK1"
    assert choose_prefix("QK1", [[], []])[0] == "QK1"
    assert choose_prefix(None, [["A.1"], ["B.2"], ["C.3"]]) == (None, "không xác định được tiền tố mã")


def test_choose_width_follows_handwriting():
    assert choose_width([["PT.CK 001"], ["PT.CK.002", "PT.CK.02"], ["PT.CK.150"]], 2) == 3
    assert choose_width([["QK1.01"], ["QK1.41"]], 3) == 2
    assert choose_width([["QK1.181"]], 3) == 3 and choose_width([], None) == 2


def reads(*values):
    return [Counter({value: 2}) if isinstance(value, int) else Counter(value or {}) for value in values]


def test_numbers_follow_file_order_when_count_matches():
    result = assign_numbers(1, 4, reads(1, None, 9, 4))  # một mã đọc nhầm không làm lệch thứ tự
    assert (result.mode, result.numbers, result.problems) == ("order", [1, 2, 3, 4], {})


def test_numbers_use_handwritten_codes_when_order_is_shifted():
    # Đủ số người nhưng một người bị tách đôi và hai người bị gộp: mã đọc được lệch dần.
    result = assign_numbers(1, 6, reads(1, 2, 2, 3, 4, 5))
    assert result.mode == "anchors"
    # Hai nửa của người bị tách đôi cùng đọc ra số 2: không gán, chuyển nạp tay.
    assert result.numbers == [1, None, None, 3, 4, 5]
    assert set(result.problems) == {1, 2}


def test_numbers_skip_a_missing_person():
    result = assign_numbers(1, 6, reads(1, 2, 4, 5, 6))
    assert (result.mode, result.numbers, result.problems) == ("anchors", [1, 2, 4, 5, 6], {})


def test_numbers_leave_the_ambiguous_person_unassigned():
    result = assign_numbers(1, 4, reads(1, 2, None, 3, 4))  # người 2 bị tách làm hai
    assert result.numbers == [1, 2, None, 3, 4]
    assert "lệch nhau" in result.problems[2]


def test_numbers_ignore_a_misread_anchor():
    result = assign_numbers(1, 6, reads(1, 2, 9, 4, 5))
    assert result.numbers == [1, 2, 3, 4, 5]


def test_numbers_reject_out_of_range_and_duplicates():
    result = assign_numbers(81, 83, reads(81, 82, 82, 83))
    assert result.numbers == [81, None, None, 83] and "trùng số thứ tự 82" in result.problems[1]
    assert assign_numbers(1, 3, reads(1, 2, 3, None)).problems == {3: "số thứ tự suy ra (4) nằm ngoài dải mã của file"}
    assert assign_numbers(None, None, reads(None, None)).problems == {
        0: "không đọc chắc được mã nào trong file để xác định thứ tự",
        1: "không đọc chắc được mã nào trong file để xác định thứ tự",
    }
    single = assign_numbers(1, 3, [Counter({2: 1}), Counter(), Counter()])  # một lần đọc chưa đủ làm điểm neo
    assert single.mode == "order" and single.numbers == [1, 2, 3]


# ---------- dựng bản ghi giống giao diện ----------


def test_prepare_answers_matches_interface_rules():
    f09 = FORM_BY_ID["F09"]
    answers = {"Q012": "Không", "Q013": "Có", "Q001": "  "}
    prepared = store.prepare_answers(f09, answers, {"fullName": "", "birthDate": "", "birthYear": "", "hometown": ""})
    assert prepared == {"Q012": "Không", "Q013": "Có"}  # F09: câu được chuyển qua vẫn giữ câu trả lời
    empty = {"fullName": "", "birthDate": "", "birthYear": "", "hometown": ""}
    assert "Q014" not in store.prepare_answers(FORM_BY_ID["F01"], {"Q013": "Chưa bao giờ (1)", "Q014": "x"}, empty)
    filled = store.prepare_answers(FORM_BY_ID["F02"], {"Q006": "Hà Nội"},
                                   {"fullName": "Lê Văn B", "birthDate": "", "birthYear": "2003", "hometown": "Nam Định"})
    assert (filled["Q001"], filled["Q002"], filled["Q006"]) == ("Lê Văn B", "2003", "Hà Nội")
    assert store.invalid_answers(FORM_BY_ID["F08"], {"Q007": "Khác: ......"}) == {"Q007"}


# ---------- chạy cả luồng ----------


def make_dataset(data: Path, prefix: str, *, youth=3, military=2, youth_range=None, youth_people=None):
    people = youth_people or [youth_person(f"{prefix}.XX", n) for n in range(1, youth + 1)]
    write_pdf(data / YOUTH_DIR / f"{prefix}.XX {youth_range or f'01 - {youth:02d}'}-11232026004719.pdf",
              [page for person in people for page in person])
    write_pdf(data / MILITARY_DIR / f"{prefix}Q 01 - {military:02d}" / f"phieu 01- {military:02d}.pdf",
              [page for n in range(1, military + 1) for page in military_person(f"{prefix}Q", n)])


def test_run_ingests_each_person_with_original_files(ingest, prefix):
    make_dataset(ingest.data, prefix)
    (ingest.data / MILITARY_DIR / f"{prefix}Q 01 - 02" / "phieu 03 - 04.pdf").write_bytes(b"\0" * 4096)  # file hỏng
    write_pdf(ingest.data / "scan trạm y tế" / "PT.CK 01 - 80.pdf", youth_person("PT.CK", 1))
    vlm = FakeVLM()
    runner, states = ingest(vlm)

    rows = records_of(prefix)
    assert [row.id for row, _ in rows] == [
        f"OCR-{prefix}.XX.001-F08", f"OCR-{prefix}.XX.001-F09", f"OCR-{prefix}.XX.002-F08",
        f"OCR-{prefix}.XX.002-F09", f"OCR-{prefix}.XX.003-F08", f"OCR-{prefix}.XX.003-F09",
        f"OCR-{prefix}Q.01-F02", f"OCR-{prefix}Q.01-F03", f"OCR-{prefix}Q.02-F02", f"OCR-{prefix}Q.02-F03",
    ]
    record, document = rows[2]
    assert (record.person, record.group, record.source, record.status) == (f"{prefix}.XX.002", "youth", "OCR", "review")
    assert record.subject.full_name == f"Người {prefix}.XX.002" and record.subject.birth_year == "2004"
    assert str(record.date) == "2026-10-21"
    assert "khớp mã viết tay" in record.note and "trang 6–7" in record.note
    assert document.file_name == f"{prefix}.XX.002_F08_trang-6-7.pdf"
    assert pdf_page_texts(Path(document.relative_path).read_bytes()) == [f"F08 START MA={prefix}.XX.002", "F08"]
    military, military_document = rows[7]
    assert military.person == f"{prefix}Q.01" and military.group == "military"
    assert pdf_page_texts(Path(military_document.relative_path).read_bytes()) == [f"F03 START MA={prefix}Q.01", "F03"]
    with SessionLocal() as db:
        audit = db.scalar(select(OcrExtraction).where(OcrExtraction.document_id == document.id))
    assert audit.raw_result["bundle"]["ingest"]["code"] == f"{prefix}.XX.002"
    assert audit.raw_result["bundle"]["pages"] == [6, 7]

    broken = next(state for state in states if state.source.label.endswith("phieu 03 - 04.pdf"))
    assert "không mở được file PDF" in broken.error
    assert not any("scan trạm" in state.source.label for state in states)
    assert {kind for kind, _ in vlm.calls} == {"classify", "F08", "F09", "F02", "F03"}
    assert json.loads((ingest.work / "decisions.json").read_text()) == {"width": {"youth": 3, "military": 2}}
    report = (ingest.work / "report" / "nguoi.csv").read_text(encoding="utf-8-sig")
    assert f"{prefix}.XX.003" in report
    assert len(store.Ledger(ingest.work / "ledger.jsonl").ids) == 10


def test_rerun_calls_no_vlm_and_creates_nothing_twice(ingest, prefix):
    make_dataset(ingest.data, prefix, military=1)
    ingest(FakeVLM())
    again = FakeVLM()
    runner, states = ingest(again)
    assert again.calls == []
    assert len(records_of(prefix)) == 8
    assert sum(len(person.existing) for state in states for person in state.persons) == 8
    assert sum(len(person.created) for state in states for person in state.persons) == 0


def test_interrupted_run_resumes_without_repeating_vlm_calls(ingest, prefix):
    make_dataset(ingest.data, prefix)
    clean = FakeVLM()
    ingest(clean)  # để đếm tổng số lượt gọi cần thiết
    total = len(clean.calls)
    # Chạy lại từ đầu ở thư mục mới, bị "mất mạng" sau 7 lượt gọi.
    import shutil

    shutil.rmtree(ingest.work)
    with SessionLocal() as db:
        db.execute(delete(SurveyRecord).where(SurveyRecord.person.startswith(prefix)))
        db.commit()
    broken = FakeVLM(fail_after=7)
    runner, states = ingest(broken)
    assert any("mất mạng" in message for message in runner.failures.values())
    assert any(state.status.startswith("chưa") for state in states)
    resumed = FakeVLM()
    runner, states = ingest(resumed)
    assert len(resumed.calls) == total - 7
    assert not set(map(str, resumed.calls)) & set(map(str, broken.calls[:7]))
    assert len(records_of(prefix)) == 10


def test_failed_write_leaves_no_files_and_sweeps_orphans(ingest, prefix, monkeypatch):
    make_dataset(ingest.data, prefix, youth=2, military=1)
    original = store.write_record
    seen = []

    def flaky(row, data):
        seen.append(data.id)
        if data.person.endswith(".002"):
            raise RuntimeError("ổ đĩa đầy")
        original(row, data)

    monkeypatch.setattr(store, "write_record", flaky)
    runner, states = ingest(FakeVLM())
    person = states[0].persons[1]
    assert person.problem.startswith("lỗi khi ghi") and person.created == []
    assert len(records_of(prefix)) == 4
    with SessionLocal() as db:
        known = set(db.scalars(select(Document.relative_path).where(Document.relative_path.startswith(str(ingest.storage)))))
    assert {str(path) for path in ingest.storage.glob("*.pdf")} == known  # không còn file mồ côi

    stray = ingest.storage / "ingest-mo-coi.pdf"
    stray.write_bytes(b"%PDF")
    monkeypatch.setattr(store, "write_record", original)
    runner, states = ingest(FakeVLM())
    assert not stray.exists()
    assert len(records_of(prefix)) == 6


def test_filename_prefix_is_corrected_by_handwriting(ingest, prefix):
    people = [youth_person(f"{prefix}.TL", n) for n in range(1, 4)]
    write_pdf(ingest.data / YOUTH_DIR / f"{prefix}.PL 01 - 03-1.pdf", [page for person in people for page in person])
    ingest(FakeVLM())
    assert [row.person for row, _ in records_of(prefix)][::2] == [f"{prefix}.TL.001", f"{prefix}.TL.002", f"{prefix}.TL.003"]


def test_code_that_disagrees_with_file_order_is_flagged(ingest, prefix):
    people = [youth_person(f"{prefix}.XX", 1), youth_person(f"{prefix}.XX", 2, read="009"),
              youth_person(f"{prefix}.XX", 3)]
    make_dataset(ingest.data, prefix, military=1, youth_people=people)
    ingest(FakeVLM())
    rows = {row.id: row for row, _ in records_of(prefix)}
    flagged = rows[f"OCR-{prefix}.XX.002-F08"]
    assert flagged.status == "draft"
    assert "mã viết tay đọc được là" in flagged.note and "code" in flagged.note
    assert rows[f"OCR-{prefix}.XX.003-F08"].status == "review"


def test_missing_person_uses_handwritten_codes_and_ambiguous_people_go_to_manual(ingest, prefix):
    # Dải 01–04 nhưng thiếu người 03: neo theo mã đọc được, các mã đều cần đối chiếu.
    people = [youth_person(f"{prefix}.XX", n) for n in (1, 2, 4)]
    make_dataset(ingest.data, prefix, military=1, youth_people=people, youth_range="01 - 04")
    runner, states = ingest(FakeVLM())
    rows = {row.person: row for row, _ in records_of(prefix) if row.group == "youth"}
    assert sorted(rows) == [f"{prefix}.XX.001", f"{prefix}.XX.002", f"{prefix}.XX.004"]
    assert all(row.status == "draft" and "suy ra từ mã viết tay" in row.note for row in rows.values())

    # Người không có mã nào đọc được nằm giữa hai đoạn lệch nhau: không đoán, xuất PDF nạp tay.
    other = "U" + prefix[1:]
    people = [youth_person(f"{other}.XX", 1), youth_person(f"{other}.XX", 2),
              [text.replace(f"MA={other}.XX.003", "") if text else text for text in youth_person(f"{other}.XX", 3)],
              youth_person(f"{other}.XX", 2)]
    write_pdf(ingest.data / YOUTH_DIR / f"{other}.XX 01 - 03-1.pdf", [page for person in people for page in person])
    try:
        runner, states = ingest(FakeVLM(), only=[f"{other}.XX"])
        persons = states[0].persons
        assert [person.problem is not None for person in persons] == [False, True, True, True]
        folder = ingest.work / "manual" / "youth" / f"{other}.XX 01 - 03-1"
        assert sorted(path.name for path in folder.iterdir()) == [
            "nguoi-002_trang-6-9.pdf", "nguoi-003_trang-11-14.pdf", "nguoi-004_trang-16-19.pdf"]
        assert pdf_page_texts((folder / "nguoi-002_trang-6-9.pdf").read_bytes())[0] == f"F08 START MA={other}.XX.002"
    finally:
        with SessionLocal() as db:
            db.execute(delete(SurveyRecord).where(SurveyRecord.person.startswith(other)))
            db.execute(delete(SurveySubject).where(SurveySubject.person.startswith(other)))
            db.commit()


def test_form_the_model_cannot_read_is_cached_and_exported_for_manual_upload(ingest, prefix):
    make_dataset(ingest.data, prefix, youth=2, military=1)
    failing = FakeVLM(model_error_forms={"F09"})
    runner, states = ingest(failing)
    assert sorted(row.form for row, _ in records_of(prefix) if row.group == "youth") == ["F08", "F08"]
    assert len([call for call in failing.calls if call[0] == "F09"]) == 2 * 3  # thử lại 3 lần mỗi phiếu
    folder = ingest.work / "manual" / "youth" / f"{prefix}.XX 01 - 02-11232026004719"
    assert sorted(path.name for path in folder.iterdir()) == [
        f"{prefix}.XX.001_F09_trang-3-4.pdf", f"{prefix}.XX.002_F09_trang-8-9.pdf"]

    again = FakeVLM()
    ingest(again)
    assert again.calls == []  # lỗi đã lưu: không gọi lại nếu không yêu cầu
    retry = FakeVLM()
    ingest(retry, retry_failed=True)
    assert [call[0] for call in retry.calls] == ["F09", "F09"]
    assert sorted(row.form for row, _ in records_of(prefix) if row.group == "youth") == ["F08", "F08", "F09", "F09"]
    assert not folder.exists()  # đã nạp được: bỏ PDF nạp tay cũ


def test_unclassifiable_pages_send_nearby_people_to_manual(ingest, prefix):
    people = [youth_person(f"{prefix}.XX", n) for n in range(1, 8)]
    make_dataset(ingest.data, prefix, military=1, youth_people=people, youth_range="01 - 07")
    # Lô nhận diện thứ hai (trang 13–24: cuối người 3 tới hết người 5) lỗi mãi.
    runner, states = ingest(FakeVLM(classify_error_pages={21}))
    youth = states[0]
    assert [person.problem is not None for person in youth.persons] == [False, True, True, True, False]
    assert "không nhận diện được" in youth.persons[2].problem
    assert sorted({row.person for row, _ in records_of(prefix) if row.group == "youth"}) == [
        f"{prefix}.XX.001", f"{prefix}.XX.007"]


def test_budget_limit_stops_new_calls(ingest, prefix):
    make_dataset(ingest.data, prefix)
    vlm = FakeVLM(tokens=5_000_000)  # mỗi lượt ~$1
    runner, states = ingest(vlm, max_cost=2.5)
    assert [kind for kind, _ in vlm.calls] == ["classify"] * 3  # hết ngân sách trước khi đọc phiếu
    assert any("[DỪNG]" in line for line in ingest.logs)
    assert records_of(prefix) == []


def test_dry_run_and_pilot_write_nothing(ingest, prefix):
    make_dataset(ingest.data, prefix, youth=4)
    runner, states = ingest(FakeVLM(), dry_run=True, max_pages=12)
    youth = states[0]
    assert youth.truncated and [person.code for person in youth.persons] == [f"{prefix}.XX.001", f"{prefix}.XX.002"]
    assert records_of(prefix) == [] and not ingest.storage.exists()
    assert not (ingest.work / "decisions.json").exists()


def test_refuses_to_run_over_existing_data(ingest, prefix):
    make_dataset(ingest.data, prefix)
    with SessionLocal() as db:
        db.add(SurveySubject(group="youth", person=f"{prefix}.CU", full_name="", birth_date=None, birth_year="",
                             hometown=""))
        db.flush()
        from datetime import date, datetime, timezone

        db.add(SurveyRecord(id=f"{prefix}-CU", group="youth", person=f"{prefix}.CU", form="F08", unit="",
                            date=date.today(), source="Thủ công", status="draft", conclusion="", answers={}, note="",
                            updated_at=datetime.now(timezone.utc)))
        db.commit()
    with pytest.raises(SystemExit, match="không do script này nạp"):
        ingest(FakeVLM(), allow_existing=False)


def test_deleted_records_are_not_recreated_on_rerun(ingest, prefix):
    make_dataset(ingest.data, prefix, youth=1, military=1)
    ingest(FakeVLM())
    with SessionLocal() as db:
        db.execute(delete(SurveyRecord).where(SurveyRecord.id == f"OCR-{prefix}.XX.001-F09"))
        db.commit()
    ingest(FakeVLM())
    assert f"OCR-{prefix}.XX.001-F09" not in {row.id for row, _ in records_of(prefix)}


def test_run_keeps_people_aligned_when_a_continuation_page_is_misread(ingest, prefix):
    def person(number, misread=False):
        code = f"MA={prefix}Q.{number:02d}"
        return [f"F02 START {code}", None, "KHAC", "KHAC", "F03 START", "F03", "F04 START",
                "F03" if misread else "F04", None]

    pages = person(1, misread=True) + person(2) + person(3)
    write_pdf(ingest.data / MILITARY_DIR / f"{prefix}Q 01 - 03" / "phieu 01- 03.pdf", pages)
    runner, states = ingest(FakeVLM())
    assert states[0].mode == "order"
    rows = records_of(prefix)
    assert [row.id for row, _ in rows] == [f"OCR-{prefix}Q.0{n}-F0{f}" for n in (1, 2, 3) for f in (2, 3, 4)]
    first_f04 = next(document for row, document in rows if row.id == f"OCR-{prefix}Q.01-F04")
    assert pdf_page_texts(Path(first_f04.relative_path).read_bytes()) == ["F04 START", "F03"]
    assert all("code" not in row.note for row, _ in rows) and all("khớp mã viết tay" in row.note for row, _ in rows)


def test_purge_one_file_then_rerun_reloads_it_from_cache(ingest, prefix):
    make_dataset(ingest.data, prefix, youth=2, military=2)
    ingest(FakeVLM())
    before = {row.id: document.relative_path for row, document in records_of(prefix)}
    military_files = [Path(document.relative_path) for row, document in records_of(prefix) if row.group == "military"]

    with SessionLocal() as db:
        label, ids = store.ingested_from(db, f"{prefix}Q 01 - 02")
        assert label.endswith(f"{prefix}Q 01 - 02/phieu 01- 02.pdf")
        assert ids == sorted(key for key in before if f"{prefix}Q." in key)
        ledger = store.Ledger(ingest.work / "ledger.jsonl")
        counts = store.purge(db, ids, ledger)
    assert counts == {"phiếu": 4, "đối tượng": 2, "file gốc": 4}
    assert not any(path.exists() for path in military_files)
    assert {row.id for row, _ in records_of(prefix)} == {key for key in before if f"{prefix}Q." not in key}
    with SessionLocal() as db:
        assert db.get(SurveySubject, ("military", f"{prefix}Q.01")) is None
        assert db.scalar(select(func.count(Document.id)).where(Document.relative_path.in_(
            [str(path) for path in military_files]))) == 0
    assert not set(ids) & store.Ledger(ingest.work / "ledger.jsonl").ids
    assert list(ingest.work.glob("ledger-truoc-khi-go-*.jsonl"))

    again = FakeVLM()
    ingest(again)
    assert again.calls == []
    after = {row.id: document.relative_path for row, document in records_of(prefix)}
    assert after.keys() == before.keys()
    assert all(after[key] == before[key] for key in before if key not in ids)  # file khác không bị đụng tới
    assert all(after[key] != before[key] for key in ids)
    assert set(ids) <= store.Ledger(ingest.work / "ledger.jsonl").ids


def test_purge_refuses_edited_unknown_or_ambiguous_files(ingest, prefix):
    make_dataset(ingest.data, prefix, youth=1, military=1)
    ingest(FakeVLM())
    with SessionLocal() as db:
        with pytest.raises(store.PurgeRefused, match="không có phiếu nào"):
            store.ingested_from(db, f"{prefix}-khong-co")
        with pytest.raises(store.PurgeRefused, match="khớp nhiều file"):
            store.ingested_from(db, prefix)
        row = db.get(SurveyRecord, f"OCR-{prefix}Q.01-F03")
        row.updated_at = row.updated_at + store.EDIT_GRACE * 3
        db.commit()
        with pytest.raises(store.PurgeRefused, match=f"1 phiếu đã được sửa sau khi nạp \\(OCR-{prefix}Q.01-F03\\)"):
            store.ingested_from(db, f"{prefix}Q 01 - 01")
    assert len(records_of(prefix)) == 4


def test_purge_command_requires_confirmation(tmp_path, capsys):
    assert cli(["--work", str(tmp_path / "work"), "purge", "--file", "Phiếu 181 - 230", "--confirm", "co"]) == 1
    assert "GO-PHIEU-DA-NAP" in capsys.readouterr().err


def test_wipe_keeps_accounts_and_templates(tmp_path):
    engine = create_engine(f"sqlite:///{tmp_path / 'wipe.db'}")
    Base.metadata.create_all(engine)
    root = tmp_path / "storage"
    for name in ("surveys/a.pdf", "uploads/b.png", "exports/c.xlsx", "templates/mau_nhap_benh_nhan.xlsx",
                 "ingest/cache/x.json"):
        (root / name).parent.mkdir(parents=True, exist_ok=True)
        (root / name).write_text("x")
    with sessionmaker(bind=engine)() as db:
        db.add(User(email="bs@example.com", password_hash="x", full_name="Bác sĩ"))
        db.add(Patient(patient_code="BN001", full_name="Bệnh nhân"))
        db.add(SurveySubject(group="youth", person="PT.CK.001", full_name="", birth_date=None, birth_year="",
                             hometown=""))
        db.commit()
        counts = store.wipe(db, root)
        assert counts["patients"] == 1 and counts["survey_subjects"] == 1 and counts["files"] == 3
        assert db.scalar(select(User.email)) == "bs@example.com"
        assert db.scalar(select(Patient.id)) is None
    assert sorted(str(path.relative_to(root)) for path in root.rglob("*") if path.is_file()) == [
        "ingest/cache/x.json", "templates/mau_nhap_benh_nhan.xlsx"]


def test_wipe_command_requires_backup_and_confirmation(tmp_path, capsys):
    backup = tmp_path / "backup"
    backup.mkdir()
    assert cli(["--work", str(tmp_path / "work"), "wipe", "--backup", str(backup), "--confirm", "co"]) == 1
    assert cli(["--work", str(tmp_path / "work"), "wipe", "--backup", str(backup),
                "--confirm", "XOA-DU-LIEU-BENH-NHAN"]) == 1
    assert "chưa thấy bản sao lưu" in capsys.readouterr().err


def test_scan_command_reports_pages_and_broken_files(tmp_path, capsys, monkeypatch):
    data = tmp_path / "data"
    write_pdf(data / YOUTH_DIR / "PT.CK 01 - 02-1.pdf", youth_person("PT.CK", 1) + youth_person("PT.CK", 2))
    (data / YOUTH_DIR / "PT.CK 03 - 04-1.pdf").write_bytes(b"\0" * 100)
    monkeypatch.setattr(Runner, "_process_pool", staticmethod(lambda size: ThreadPoolExecutor(1)))
    assert cli(["--data", str(data), "--work", str(tmp_path / "work"), "scan"]) == 0
    output = capsys.readouterr().out
    assert "PT.CK 01 - 02-1.pdf: 10 trang, 2 trắng, 8 có nội dung" in output
    assert "[HỎNG]" in output and "PT.CK 03 - 04-1.pdf" in output


def test_refuses_to_ingest_with_stub_extractor(tmp_path):
    write_pdf(tmp_path / "data" / YOUTH_DIR / "PT.CK 01 - 01-1.pdf", youth_person("PT.CK", 1))
    runner = Runner(Options(data=tmp_path / "data", work=tmp_path / "work", dry_run=True),
                    executor_factory=lambda size: ThreadPoolExecutor(1), log=lambda message: None)
    with pytest.raises(SystemExit, match="stub"):
        runner.run()

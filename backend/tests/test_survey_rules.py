"""Biểu mẫu khớp phiếu giấy, chỉ dẫn chuyển câu, mã đối tượng và dữ liệu cũ."""

from datetime import datetime, timezone
from uuid import uuid4

import pytest
from pydantic import ValidationError

from app.core.database import SessionLocal
from app.modules.surveys.legacy import rename_legacy_options
from app.modules.surveys.models import SurveyRecord, SurveySubject
from app.modules.surveys.ocr.schema import canonical_code, code_key, form_prompt, normalize
from app.modules.surveys.schemas import FORM_BY_ID, FORMS, RecordInput, skipped_questions


def full_answers(form_id: str) -> dict:
    """Trả lời mọi câu bằng phương án đầu tiên (câu tự do: một chuỗi)."""
    return {
        question["id"]: ([question["options"][0]] if question["multi"] else question["options"][0])
        if question["options"] else "Trả lời"
        for question in FORM_BY_ID[form_id]["questions"]
    }


def record(form_id: str, answers: dict, status: str = "complete") -> RecordInput:
    form = FORM_BY_ID[form_id]
    return RecordInput(
        id=f"T-{uuid4().hex}", person="PT.CK.001", group=form["group"], form=form_id, patient={},
        date="2026-11-20", source="OCR", status=status, answers=answers,
    )


# ---------- biểu mẫu ----------


def test_youth_templates_match_paper_forms():
    f08 = {question["id"]: question for question in FORM_BY_ID["F08"]["questions"]}
    f09 = {question["id"]: question for question in FORM_BY_ID["F09"]["questions"]}
    assert f08["Q007"]["options"] == ["Thành thị", "Nông thôn", "Miền núi hoặc vùng sâu, vùng xa", "Khác"]
    assert f09["Q012"]["label"].startswith("D0. Trong cuộc đời")
    assert f09["Q013"]["label"].startswith("D1. Trong giai đoạn đó")
    assert [label for label in (q["label"] for q in f09.values()) if label.startswith("D1.")] == [f09["Q013"]["label"]]
    blocks = [block["text"] for block in FORM_BY_ID["F09"]["blocks"] if "text" in block]
    assert any(text.startswith("D0. Trong cuộc đời") for text in blocks)


def test_youth_options_have_no_fill_in_dots():
    for form in (FORM_BY_ID["F08"], FORM_BY_ID["F09"]):
        for question in form["questions"]:
            assert not any("...." in option for option in question["options"]), (form["id"], question["id"])


def test_skip_rules_point_back_to_real_options():
    for form in FORMS:
        order = [question["id"] for question in form["questions"]]
        questions = dict(zip(order, form["questions"]))
        for question in form["questions"]:
            rule = question.get("skipIf")
            if not rule:
                continue
            control = questions[rule["question"]]
            assert order.index(control["id"]) < order.index(question["id"])
            assert rule["answer"] in control["options"]
            assert set(rule) <= {"question", "answer", "keepAnswer"}


def test_prompt_carries_form_specific_hint():
    prompt = form_prompt(FORM_BY_ID["F09"])
    assert "in nhầm nhãn “D1”" in prompt
    assert "Lưu ý riêng" not in form_prompt(FORM_BY_ID["F08"])


# ---------- chuyển câu ----------


def test_f09_d0_no_makes_d1_to_d4_optional_but_keeps_given_answers():
    answers = full_answers("F09")
    answers["Q012"] = "Không"
    for key in ("Q013", "Q014", "Q015", "Q016"):
        answers.pop(key)
    assert skipped_questions(FORM_BY_ID["F09"], answers) == {"Q013", "Q014", "Q015", "Q016"}
    assert record("F09", answers).status == "complete"

    answered = {**answers, "Q013": "Có"}
    assert record("F09", answered).answers["Q013"] == "Có"  # không xoá câu người trả lời đã đánh

    with pytest.raises(ValidationError, match="Còn 4 mục thiếu"):
        record("F09", {**answers, "Q012": "Có"})
    with pytest.raises(ValidationError, match="Q014: đáp án không hợp lệ"):
        record("F09", {**answers, "Q014": "Bịa ra"}, status="draft")


def test_f01_skip_rules_still_clear_skipped_answers():
    answers = full_answers("F01")
    assert answers["Q013"] == "Chưa bao giờ (1)" and answers["Q020"] == "Không có (1)"
    saved = record("F01", answers)
    assert not {"Q014", "Q015", "Q016", "Q017", "Q021", "Q027"} & saved.answers.keys()
    assert {"Q019", "Q029"} <= saved.answers.keys()

    for key in ("Q014", "Q015", "Q016", "Q017", "Q019"):
        answers.pop(key)
    answers["Q018"] = ["Không gặp sự kiện đáng kể"]
    assert "Q019" in skipped_questions(FORM_BY_ID["F01"], answers)
    assert record("F01", answers).status == "complete"

    answers["Q013"] = "1 lần (2)"
    with pytest.raises(ValidationError, match="Còn 4 mục thiếu"):
        record("F01", answers)


# ---------- mã đối tượng ----------


@pytest.mark.parametrize("written, expected", [
    ("PT.CK 001", "PT.CK.001"),
    ("PT.Ck.081", "PT.CK.081"),
    ("pt. tl - 143", "PT.TL.143"),
    ("PT.TL.143 ", "PT.TL.143"),
    ("KCB-TT.02- Mẫu 01 PT.CK 001", "PT.CK.001"),
    ("KCB-TT.01 QK1. 01", "QK1.01"),
    ("QK1.02", "QK1.02"),
    ("TN_0005", "TN.0005"),
    ("K.2/16", "K.2/16"),
    ("....", None),
    (None, None),
])
def test_canonical_code(written, expected):
    assert canonical_code(written) == expected


def test_code_key_ignores_separators_case_and_leading_zeros():
    assert code_key("PT.CK 001") == code_key("pt-ck-1") == "PT.CK.1"
    assert code_key("QK1.01") != code_key("QK10.1")
    assert code_key("") is None


def test_ocr_code_is_canonical():
    result = normalize(FORM_BY_ID["F08"], {"subject": {"code": "PT. Ck 081"}, "answers": {}})
    assert result.subject["code"] == "PT.CK.081"


# ---------- dữ liệu cũ ----------


def test_legacy_option_names_are_renamed_once(api):  # api: dựng bảng như lúc ứng dụng khởi động
    ids = [f"LEGACY-{uuid4().hex}" for _ in range(3)]
    with SessionLocal() as db:
        person = f"LEGACY-{uuid4().hex}"
        db.add(SurveySubject(group="youth", person=person, full_name="", birth_date=None, birth_year="", hometown=""))
        values = [{"Q007": "Khác: ................", "Q008": "Bạn bè"}, {"Q007": "Nông thôn"}, {}]
        for id, answers in zip(ids, values):
            db.add(SurveyRecord(
                id=id, group="youth", person=person, form="F08", unit="", date=datetime(2026, 11, 20).date(),
                source="Thủ công", status="draft", conclusion="", answers=answers, note="",
                updated_at=datetime.now(timezone.utc),
            ))
        db.commit()
        try:
            assert rename_legacy_options(db) >= 1
            assert rename_legacy_options(db) == 0
            stored = {row.id: row.answers for row in db.query(SurveyRecord).filter(SurveyRecord.id.in_(ids))}
            assert stored[ids[0]] == {"Q007": "Khác", "Q008": "Bạn bè"}
            assert stored[ids[1]] == {"Q007": "Nông thôn"} and stored[ids[2]] == {}
        finally:
            db.query(SurveyRecord).filter(SurveyRecord.id.in_(ids)).delete()
            db.query(SurveySubject).filter_by(person=person).delete()
            db.commit()

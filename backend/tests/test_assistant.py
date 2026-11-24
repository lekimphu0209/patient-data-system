"""Trợ lý dữ liệu: ảnh chụp dữ liệu, công cụ phân tích, chặn truy vấn nguy hiểm, lọc định danh, vòng agent, API.

Không gọi LLM thật: ``FakeLLM`` trả các lượt gọi công cụ soạn sẵn.
"""

from __future__ import annotations

import json
import random
import string
from datetime import date, datetime, timezone

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, delete, select
from sqlalchemy.orm import sessionmaker

from app.core.config import settings
from app.core.database import Base, SessionLocal
from app.main import app
from app.modules.assistant import agent
from app.modules.assistant.models import AssistantLog
from app.modules.assistant.router import limiter, llm_dependency
from app.modules.assistant.snapshot import QueryError, Snapshot
from app.modules.assistant.tools import TOOLS, ToolError
from app.modules.surveys.models import SurveyRecord, SurveySubject

NO_FILTER = {"group": None, "forms": None, "statuses": None, "code_prefix": None, "date_from": None, "date_to": None}
NAMES = {"PT.CK.001": "Nguyễn Văn Thử", "PT.CK.002": "Trần Thị Mẫu", "PT.TL.001": "Lê Hoàng Kiểm",
         "QK1.01": "Phạm Quốc Định", "QK1.02": "Đỗ Minh Chứng"}


# ---------- dữ liệu mẫu ----------


def seed(db, prefix: str = "") -> dict[str, str]:
    """3 thanh niên (PT.CK x2, PT.TL x1) và 2 quân nhân (QK1). Trả về {mã: họ tên}."""
    names = {}
    now = datetime.now(timezone.utc)

    def subject(group, code, name, hometown, birth_year="", birth_date=None):
        names[prefix + code] = name
        db.add(SurveySubject(group=group, person=prefix + code, full_name=name, birth_date=birth_date,
                             birth_year=birth_year, hometown=hometown))

    def record(group, code, form, status, answers, day="2026-10-21"):
        db.add(SurveyRecord(id=f"{prefix}{code}-{form}", group=group, person=prefix + code, form=form, unit="",
                            date=date.fromisoformat(day), source="OCR", status=status, conclusion="", answers=answers,
                            note="", updated_at=now))

    subject("youth", "PT.CK.001", NAMES["PT.CK.001"], "Xã Tân Lập, Phú Thọ")
    subject("youth", "PT.CK.002", NAMES["PT.CK.002"], "Xã Đồng Tâm, Phú Thọ")
    subject("youth", "PT.TL.001", NAMES["PT.TL.001"], "Xã Minh Khai, Phú Thọ")
    subject("military", "QK1.01", NAMES["QK1.01"], "Xã Quang Trung, Hà Nội", birth_year="2004")
    subject("military", "QK1.02", NAMES["QK1.02"], "Xã Tiền Phong, Hà Nội", birth_date=date(2001, 5, 12),
            birth_year="2001")
    db.flush()
    record("youth", "PT.CK.001", "F08", "complete",
           {"Q001": NAMES["PT.CK.001"], "Q002": "19", "Q003": "Nam", "Q006": "Xã Tân Lập, Phú Thọ",
            "Q040": "Không sử dụng"})
    record("youth", "PT.CK.001", "F09", "review", {"Q042": "Có", "Q045": "Không"})
    record("youth", "PT.CK.002", "F08", "draft",
           {"Q001": NAMES["PT.CK.002"], "Q002": "23", "Q003": "Nữ", "Q040": "1-3 lần/tháng"}, day="2026-11-02")
    record("youth", "PT.CK.002", "F09", "complete", {"Q042": "Không", "Q045": "Có"}, day="2026-11-02")
    record("youth", "PT.TL.001", "F08", "review", {"Q002": "21", "Q003": "Nam", "Q040": "1-3 lần/tháng"})
    record("youth", "PT.TL.001", "F09", "draft", {"Q042": "Có", "Q045": "Có"})
    record("military", "QK1.01", "F01", "draft",
           {"Q001": "22", "Q002": "Nam", "Q013": "1 lần (2)", "Q015": ["Uống thuốc quá liều", "Treo cổ, thắt cổ"]})
    record("military", "QK1.01", "F02", "review", {"Q001": NAMES["QK1.01"], "Q002": "2004", "Q003": "Nam"})
    record("military", "QK1.02", "F01", "complete", {"Q002": "Nam", "Q013": "Chưa bao giờ (1)"})
    db.commit()
    return names


@pytest.fixture
def snapshot(tmp_path):
    engine = create_engine(f"sqlite:///{tmp_path / 'assistant.db'}")
    Base.metadata.create_all(engine)
    with sessionmaker(bind=engine)() as db:
        seed(db)
        yield Snapshot().ensure(db)


def run(snapshot, name, **arguments):
    return TOOLS[name].run(snapshot, arguments)


def blob(value) -> str:
    return json.dumps(value, ensure_ascii=False, default=str)


# ---------- ảnh chụp dữ liệu ----------


def test_snapshot_flattens_answers_and_derives_age_gender(snapshot):
    assert snapshot.query("SELECT COUNT(*) FROM records").rows == [(9,)]
    multi = snapshot.query("SELECT value FROM answers WHERE record_id = 'QK1.01-F01' AND question = 'Q015' ORDER BY value")
    assert multi.rows == [("Treo cổ, thắt cổ",), ("Uống thuốc quá liều",)]
    # Câu định danh (họ tên, địa chỉ) không vào bảng answers.
    identity = snapshot.query("SELECT COUNT(*) FROM answers WHERE (form IN ('F02','F08') AND question IN ('Q001','Q006'))")
    assert identity.rows == [(0,)]
    subjects = dict((row[0], row[1:]) for row in snapshot.query(
        "SELECT person, code_prefix, gender, age, age_group FROM subjects").rows)
    assert subjects["PT.CK.001"] == ("PT.CK", "Nam", 19, "Dưới 20")
    assert subjects["PT.CK.002"] == ("PT.CK", "Nữ", 23, "20–24")
    assert subjects["QK1.01"] == ("QK1", "Nam", 22, "20–24")  # tuổi từ F01 Q001
    assert subjects["QK1.02"][3] in ("20–24", "25–29")  # tuổi suy từ ngày sinh
    progress = dict(snapshot.query("SELECT record_id, answered || '/' || applicable FROM records").rows)
    assert progress["PT.CK.001-F09"].startswith("2/")


def test_snapshot_rebuilds_when_data_changes(tmp_path):
    engine = create_engine(f"sqlite:///{tmp_path / 'a.db'}")
    Base.metadata.create_all(engine)
    with sessionmaker(bind=engine)() as db:
        seed(db)
        snap = Snapshot().ensure(db)
        first = snap._connection
        assert snap.ensure(db)._connection is first  # không đổi gì: dùng lại
        row = db.get(SurveyRecord, "QK1.02-F01")
        row.status, row.updated_at = "review", datetime.now(timezone.utc)
        db.commit()
        assert snap.ensure(db)._connection is not first
        assert snap.query("SELECT status FROM records WHERE record_id = 'QK1.02-F01'").rows == [("review",)]


@pytest.mark.parametrize("sql, message", [
    ("DELETE FROM records", "Chỉ được dùng một câu SELECT"),
    ("SELECT 1; DROP TABLE records", "một câu lệnh"),
    ("PRAGMA table_info(records)", "Chỉ được dùng một câu SELECT"),
    ("ATTACH DATABASE ':memory:' AS other", "Chỉ được dùng một câu SELECT"),
    ("WITH x AS (SELECT 1) DELETE FROM records", "không được phép"),
    ("SELECT zeroblob(1000000000)", "không được phép"),
    ("SELECT load_extension('x')", "không được phép"),
    ("WITH RECURSIVE c(x) AS (SELECT 1 UNION ALL SELECT x + 1 FROM c) SELECT COUNT(*) FROM c", "quá"),
    ("SELECT * FROM bang_khong_co", "no such table"),
])
def test_queries_are_read_only_and_bounded(snapshot, sql, message):
    with pytest.raises(QueryError, match=message):
        snapshot.query(sql)
    assert snapshot.query("SELECT COUNT(*) FROM records").rows == [(9,)]  # dữ liệu còn nguyên


def test_query_row_limit(snapshot):
    result = snapshot.query("SELECT * FROM answers", limit=3)
    assert len(result.rows) == 3 and result.truncated


# ---------- công cụ ----------


def test_find_questions_matches_without_accents(snapshot):
    result = run(snapshot, "find_questions", keyword="nghi den tu sat thang qua", form=None)
    assert result.llm["matches"][0]["form"] == "F09" and result.llm["matches"][0]["question"] == "Q042"
    assert result.blocks == []


def test_overview_counts_and_method(snapshot):
    result = run(snapshot, "overview", filters=NO_FILTER)
    assert result.llm["total_records"] == 9 and result.llm["total_persons"] == 5
    assert result.llm["by_status"] == {"Đã hoàn tất": 3, "Chờ đối soát": 3, "Bản nháp": 3}
    assert result.blocks[0]["type"] == "stats" and result.blocks[1]["type"] == "table"
    assert result.method == "Tính trên 9 phiếu · mọi trạng thái (Đã hoàn tất 3, Chờ đối soát 3, Bản nháp 3); đếm theo phiếu."
    youth = run(snapshot, "overview", filters={**NO_FILTER, "group": "youth", "statuses": ["complete"]})
    assert youth.llm["total_records"] == 2
    assert "Thanh niên" in youth.method and "chỉ Đã hoàn tất" in youth.method


def test_answer_distribution(snapshot):
    result = run(snapshot, "answer_distribution", form="F09", question="q42", filters=NO_FILTER)
    assert result.llm["question"] == "Q042" and result.llm["answered"] == 3
    assert {item["answer"]: (item["count"], item["percent_of_answered"]) for item in result.llm["distribution"]} == {
        "Không": (1, 33.3), "Có": (2, 66.7)}
    assert result.blocks[0]["type"] == "bars"
    multi = run(snapshot, "answer_distribution", form="F01", question="Q015", filters=NO_FILTER)
    assert "vượt 100%" in multi.blocks[0]["note"] and "1 phiếu chưa trả lời" in multi.blocks[0]["note"]
    ages = run(snapshot, "answer_distribution", form="F08", question="Q002", filters=NO_FILTER)
    assert [item["answer"] for item in ages.llm["distribution"]] == ["19", "21", "23"]
    with pytest.raises(ToolError, match="định danh"):
        run(snapshot, "answer_distribution", form="F08", question="Q001", filters=NO_FILTER)
    with pytest.raises(ToolError, match="find_questions"):
        run(snapshot, "answer_distribution", form="F08", question="Q999", filters=NO_FILTER)


def test_cross_tab_counts_people_across_forms(snapshot):
    result = run(snapshot, "cross_tab",
                 row={"kind": "question", "form": "F08", "question": "Q003"},
                 column={"kind": "question", "form": "F09", "question": "Q042"}, filters=NO_FILTER)
    table = {item["row"]: {cell["column"]: cell["count"] for cell in item["cells"]} for item in result.llm["table"]}
    assert table == {"Nam": {"Không": 0, "Có": 2}, "Nữ": {"Không": 1, "Có": 0}}
    assert result.llm["persons"] == 3 and "đếm theo đối tượng" in result.method
    by_age = run(snapshot, "cross_tab", row={"kind": "age_group", "form": None, "question": None},
                 column={"kind": "question", "form": "F08", "question": "Q040"},
                 filters={**NO_FILTER, "group": "youth"})
    assert [item["row"] for item in by_age.llm["table"]] == ["Dưới 20", "20–24"]
    rows = by_age.blocks[0]["rows"]
    assert rows[1]["row"] == "20–24" and rows[1]["total"] == 2 and "100,0%" in rows[1]["c1"]


def test_find_subjects_lists_names_for_user_but_not_for_llm(snapshot):
    result = run(snapshot, "find_subjects", conditions=[{"form": "F09", "question": "Q042", "values": ["co"]}],
                 match="all", filters=NO_FILTER)
    assert result.llm["matched_persons"] == 2 and result.llm["by_code_prefix"] == {"PT.CK": 1, "PT.TL": 1}
    table = result.blocks[0]
    assert [row["person"] for row in table["rows"]] == ["PT.CK.001", "PT.TL.001"]
    assert table["rows"][0]["name"] == NAMES["PT.CK.001"] and table["personKey"] == "person"
    assert not any(name in blob(result.llm) for name in NAMES.values())
    assert "PT.CK.001" not in blob(result.llm)
    both = run(snapshot, "find_subjects", match="all", filters=NO_FILTER, conditions=[
        {"form": "F09", "question": "Q042", "values": ["Có"]}, {"form": "F09", "question": "Q045", "values": ["Có"]}])
    either = run(snapshot, "find_subjects", match="any", filters=NO_FILTER, conditions=[
        {"form": "F09", "question": "Q042", "values": ["Có"]}, {"form": "F09", "question": "Q045", "values": ["Có"]}])
    assert both.llm["matched_persons"] == 1 and either.llm["matched_persons"] == 3
    with pytest.raises(ToolError, match="Các đáp án: Không \\| Có"):
        run(snapshot, "find_subjects", conditions=[{"form": "F09", "question": "Q042", "values": ["Có thể"]}],
            match="all", filters=NO_FILTER)


def test_subject_profile(snapshot):
    result = run(snapshot, "subject_profile", person="qk1. 1", forms=["F01"])
    assert result.llm["person"] == "QK1.01" and result.llm["missing_forms"] == ["F03", "F04", "F05", "F06", "F07"]
    assert result.llm["answers"]["F01"][0]["answer"] == "22"
    info = {row["field"]: row["value"] for row in result.blocks[0]["rows"]}
    assert info["Họ và tên"] == NAMES["QK1.01"]
    assert NAMES["QK1.01"] not in blob(result.llm) and "Hà Nội" not in blob(result.llm)
    with pytest.raises(ToolError, match="Không tìm thấy"):
        run(snapshot, "subject_profile", person="QK1.99", forms=None)


def test_review_progress(snapshot):
    result = run(snapshot, "review_progress", by="group", filters=NO_FILTER)
    rows = {row["key"]: row for row in result.llm["rows"]}
    assert rows["Thanh niên"]["total"] == 6 and rows["Quân nhân"]["Đã hoàn tất"] == 1
    assert result.llm["persons_missing_forms"] == 2  # hai quân nhân chưa đủ F01–F07
    assert result.blocks[-1]["title"] == "Đối tượng còn thiếu phiếu (2)"
    by_prefix = run(snapshot, "review_progress", by="code_prefix", filters={**NO_FILTER, "code_prefix": "pt ck"})
    assert [row["key"] for row in by_prefix.llm["rows"]] == ["PT.CK"]


def test_trend_by_month(snapshot):
    result = run(snapshot, "trend", period="month", split="none", filters=NO_FILTER)
    assert result.llm["series"] == [{"bucket": "2026-10", "records": 7}, {"bucket": "2026-11", "records": 2}]
    split = run(snapshot, "trend", period="month", split="group", filters=NO_FILTER)
    assert split.llm["series"][0] == {"bucket": "2026-10", "Quân nhân": 3, "Thanh niên": 4}
    with pytest.raises(ToolError, match="YYYY-MM-DD"):
        run(snapshot, "trend", period="day", split="none", filters={**NO_FILTER, "date_from": "21/10/2026"})


def test_run_sql_hides_identity_from_llm_but_shows_user(snapshot):
    result = run(snapshot, "run_sql", purpose="Danh sách theo nhóm tuổi",
                 sql="SELECT age_group, group_concat(upper(full_name)) AS ten, group_concat(birth_date) AS ns, "
                     "MAX(hometown) AS qq FROM subjects GROUP BY age_group")
    payload = blob(result.llm)
    assert not any(name.lower() in payload.lower() for name in NAMES.values())
    assert "2001-05-12" not in payload and "Hà Nội" not in payload
    # Người dùng vẫn thấy (upper() của SQLite chỉ đổi chữ ASCII nên so không phân biệt hoa thường).
    assert any(NAMES["QK1.02"].lower() in str(row).lower() for row in result.blocks[0]["rows"])
    assert result.method == "Danh sách theo nhóm tuổi" and "SELECT" in result.audit["sql"]
    labelled = run(snapshot, "run_sql", purpose="x", sql="SELECT grp, person, status FROM records LIMIT 2")
    assert labelled.blocks[0]["columns"][0]["label"] == "Nhóm" and labelled.blocks[0]["personKey"] == "person"
    assert labelled.blocks[0]["rows"][0]["c0"] in ("Thanh niên", "Quân nhân")
    with pytest.raises(ToolError, match="Truy vấn lỗi"):
        run(snapshot, "run_sql", sql="DROP TABLE records", purpose="x")


# ---------- vòng agent ----------


class FakeLLM:
    """Trả lần lượt các lượt soạn sẵn; ghi lại mọi message đã nhận."""

    def __init__(self, *replies):
        self.replies = list(replies)
        self.seen: list[list[dict]] = []
        self.tools_given: list[bool] = []

    def complete(self, messages, tools):
        self.seen.append(json.loads(json.dumps(messages, default=str)))
        self.tools_given.append(tools is not None)
        reply = self.replies.pop(0) if self.replies else agent.LLMReply("Xong.", [])
        return reply


def call(name, **arguments):
    return agent.LLMReply(None, [agent.ToolCall(f"call-{name}", name, json.dumps(arguments, ensure_ascii=False))],
                          usage={"prompt_tokens": 100, "completion_tokens": 10})


def test_agent_runs_tools_and_never_sends_names_to_llm(snapshot):
    llm = FakeLLM(
        call("find_subjects", conditions=[{"form": "F09", "question": "Q042", "values": ["Có"]}], match="all",
             filters=NO_FILTER),
        call("subject_profile", person="PT.CK.001", forms=["F08", "F09"]),
        call("run_sql", sql="SELECT full_name, person FROM subjects", purpose="Danh sách đối tượng"),
        agent.LLMReply("Có **2 thanh niên** trả lời có. Xem bảng bên dưới.", [], usage={"prompt_tokens": 50}),
    )
    answer = agent.run(llm, snapshot, "Thanh niên nào nghĩ đến tự sát?", [{"role": "user", "content": "Chào"},
                                                                          {"role": "assistant", "content": "Chào bạn"}])
    assert answer.text.startswith("Có **2 thanh niên**")
    assert answer.tools == ["Tìm đối tượng theo câu trả lời", "Hồ sơ một đối tượng", "Truy vấn nâng cao"]
    assert answer.usage["prompt_tokens"] == 350
    assert [block["type"] for block in answer.blocks].count("table") >= 3
    assert answer.calls[2]["sql"] == "SELECT full_name, person FROM subjects"
    everything = blob(llm.seen)
    assert not any(name in everything for name in NAMES.values())
    assert "Xã Tân Lập" not in everything
    assert llm.seen[0][1] == {"role": "user", "content": "Chào"}  # lịch sử hội thoại được gửi kèm


def test_agent_feeds_errors_back_and_stops_after_max_steps(snapshot):
    llm = FakeLLM(
        agent.LLMReply(None, [agent.ToolCall("a", "khong_co", "{}"), agent.ToolCall("b", "overview", "{not json"),
                              agent.ToolCall("c", "answer_distribution",
                                             json.dumps({"form": "F09", "question": "Q999", "filters": NO_FILTER}))]),
        call("overview", filters=NO_FILTER),
        call("overview", filters=NO_FILTER),
        agent.LLMReply("Tổng cộng 9 phiếu.", []),
    )
    answer = agent.run(llm, snapshot, "Tổng quan?", [], max_steps=3)
    tool_messages = [m for m in llm.seen[1] if m["role"] == "tool"]
    assert [json.loads(m["content"])["error"][:20] for m in tool_messages] == [
        "Không có công cụ kho", "Tham số không phải J", "Không có câu Q999 tr"]
    assert llm.tools_given == [True, True, False]  # lượt cuối buộc trả lời, không cho gọi thêm công cụ
    # Lượt cuối (không còn công cụ) vẫn trả lượt gọi công cụ, không có chữ: dùng câu trả lời dự phòng.
    assert "chưa tìm được" in answer.text
    assert [c.get("error") is not None for c in answer.calls][:3] == [True, True, True]


def test_agent_fallback_text_when_model_returns_nothing(snapshot):
    answer = agent.run(FakeLLM(agent.LLMReply("", [])), snapshot, "?", [])
    assert "chưa tìm được" in answer.text


def test_openai_input_conversion_replays_reasoning_items():
    messages = [
        {"role": "system", "content": "SYS"},
        {"role": "user", "content": "Hỏi"},
        {"role": "assistant", "content": None, "items": [{"type": "reasoning", "encrypted_content": "x"},
                                                         {"type": "function_call", "call_id": "1", "name": "overview",
                                                          "arguments": "{}"}],
         "tool_calls": [{"id": "1", "type": "function", "function": {"name": "overview", "arguments": "{}"}}]},
        {"role": "tool", "tool_call_id": "1", "content": "{\"total\": 1}"},
    ]
    instructions, items = agent.OpenAIAssistantLLM._input(messages)
    assert instructions == "SYS"
    assert items == [{"role": "user", "content": "Hỏi"}, {"type": "reasoning", "encrypted_content": "x"},
                     {"type": "function_call", "call_id": "1", "name": "overview", "arguments": "{}"},
                     {"type": "function_call_output", "call_id": "1", "output": "{\"total\": 1}"}]


def test_tool_schemas_are_strict():
    def check(schema, path):
        if schema.get("type") == "object" or schema.get("type") == ["object", "null"]:
            assert schema.get("additionalProperties") is False, path
            assert set(schema["required"]) == set(schema["properties"]), path
            for key, child in schema["properties"].items():
                check(child, f"{path}.{key}")
        if "items" in schema:
            check(schema["items"], path + "[]")

    for tool in TOOLS.values():
        check(tool.parameters, tool.name)
    assert "SELECT" not in json.dumps([t.title for t in TOOLS.values()])


# ---------- API ----------


@pytest.fixture
def client():
    with TestClient(app) as test_client:
        login = test_client.post("/api/v1/auth/login", json={
            "email": settings.DEFAULT_USER_EMAIL, "password": settings.DEFAULT_USER_PASSWORD})
        test_client.headers["Authorization"] = f"Bearer {login.json()['access_token']}"
        yield test_client
    app.dependency_overrides.clear()


@pytest.fixture
def shared_data():
    """Dữ liệu mẫu trong database dùng chung của bộ test, mã riêng cho từng test."""
    prefix = "Z" + "".join(random.choices(string.ascii_uppercase, k=4)) + "."
    with SessionLocal() as db:
        names = seed(db, prefix)
    yield prefix, names
    with SessionLocal() as db:
        db.execute(delete(SurveyRecord).where(SurveyRecord.person.startswith(prefix)))
        db.execute(delete(SurveySubject).where(SurveySubject.person.startswith(prefix)))
        db.commit()


def test_api_requires_login_and_configured_llm(client):
    assert TestClient(app).post("/api/v1/assistant/chat", json={"message": "hi"}).status_code == 401
    # Bộ test chạy chế độ giả lập (không có khoá): báo chưa cấu hình, không gọi ra ngoài.
    response = client.post("/api/v1/assistant/chat", json={"message": "Tổng quan"})
    assert response.status_code == 503 and "chưa được cấu hình" in response.json()["detail"]
    suggestions = client.get("/api/v1/assistant/suggestions").json()["tools"]
    assert [item["title"] for item in suggestions] == [
        "Tổng quan số liệu", "Phân bố câu trả lời", "So sánh theo nhóm", "Tìm đối tượng theo câu trả lời",
        "Hồ sơ một đối tượng", "Tiến độ đối soát", "Xu hướng theo thời gian"]
    assert all(item["examples"] and item["description"] for item in suggestions)


def test_api_chat_returns_answer_without_sql_and_logs_it(client, shared_data):
    prefix, names = shared_data
    sql = f"SELECT person, full_name FROM subjects WHERE person LIKE '{prefix}%'"
    llm = FakeLLM(
        call("overview", filters={**NO_FILTER, "code_prefix": prefix + "PT.CK"}),
        call("run_sql", sql=sql, purpose="Danh sách đối tượng mẫu"),
        agent.LLMReply("Có **4 phiếu**.", []),
    )
    app.dependency_overrides[llm_dependency] = lambda: llm
    response = client.post("/api/v1/assistant/chat", json={
        "message": "Tổng quan PT.CK?", "history": [{"role": "user", "content": "Chào"}]})
    assert response.status_code == 200
    body = response.json()
    assert set(body) == {"answer", "blocks", "methods", "tools"}
    assert body["answer"] == "Có **4 phiếu**." and body["tools"] == ["Tổng quan số liệu", "Truy vấn nâng cao"]
    assert body["blocks"][0]["items"][0] == {"label": "Phiếu khảo sát", "value": 4, "tone": "navy"}
    assert "SELECT" not in json.dumps(body) and "sql" not in json.dumps(body).lower()
    assert body["methods"][1] == "Danh sách đối tượng mẫu"
    assert {row["c1"] for row in body["blocks"][-1]["rows"]} == set(names.values())
    with SessionLocal() as db:
        log = db.scalars(select(AssistantLog).order_by(AssistantLog.id.desc())).first()
        assert log.question == "Tổng quan PT.CK?" and log.answer == "Có **4 phiếu**."
        assert log.calls[1]["sql"] == sql and log.usage["prompt_tokens"] == 200
        db.delete(log)
        db.commit()


def test_api_rate_limit_and_validation(client, monkeypatch):
    app.dependency_overrides[llm_dependency] = lambda: FakeLLM(agent.LLMReply("Ok.", []))
    monkeypatch.setattr(settings, "ASSISTANT_RATE_PER_MINUTE", 2)
    limiter._hits.clear()
    assert client.post("/api/v1/assistant/chat", json={"message": "   "}).status_code == 422
    assert client.post("/api/v1/assistant/chat", json={"message": "x" * 1001}).status_code == 422
    codes = [client.post("/api/v1/assistant/chat", json={"message": "Hỏi"}).status_code for _ in range(3)]
    assert codes == [200, 200, 429]
    limiter._hits.clear()
    with SessionLocal() as db:
        db.execute(delete(AssistantLog).where(AssistantLog.question == "Hỏi"))
        db.commit()


def test_api_reports_llm_failure_politely(client):
    class Broken:
        def complete(self, messages, tools):
            raise RuntimeError("mất kết nối")

    app.dependency_overrides[llm_dependency] = lambda: Broken()
    limiter._hits.clear()
    response = client.post("/api/v1/assistant/chat", json={"message": "Tổng quan lỗi"})
    assert response.status_code == 502 and "thử lại" in response.json()["detail"]
    with SessionLocal() as db:
        log = db.scalars(select(AssistantLog).where(AssistantLog.question == "Tổng quan lỗi")).one()
        assert "mất kết nối" in log.error
        db.delete(log)
        db.commit()

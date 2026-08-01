"""Kiểm thử chuỗi số liệu phục vụ biểu đồ diễn biến chỉ số.

Trọng tâm là hai điều dễ sai: chỉ lấy đúng field ``number`` có dữ liệu (không
lấy nhầm chữ, không trả về chỉ số rỗng), và giữ nguyên thứ tự thời gian tăng dần
kể cả khi lần khám được tạo lộn xộn.
"""

from __future__ import annotations

import uuid

import pytest
from fastapi.testclient import TestClient

from app.main import app
from app.modules.patients.metrics_service import (
    collect_numeric_fields,
    parse_numeric,
    pretty_group_label,
    pretty_label,
)


@pytest.fixture(scope="module")
def client():
    with TestClient(app) as test_client:
        yield test_client


@pytest.fixture(scope="module")
def auth(client):
    response = client.post(
        "/api/v1/auth/register",
        json={
            "email": f"metrics-{uuid.uuid4().hex[:8]}@example.com",
            "password": "password123",
            "full_name": "Bác sĩ Biểu đồ",
            "role": "doctor",
        },
    )
    assert response.status_code == 201
    return {"Authorization": f"Bearer {response.json()['access_token']}"}


@pytest.fixture(scope="module")
def patient_id(client, auth):
    response = client.post(
        "/api/v1/patients",
        headers=auth,
        json={
            "patient_code": f"MTR{uuid.uuid4().hex[:8]}",
            "full_name": "Bệnh nhân biểu đồ",
            "diagnosis": "Trầm cảm",
        },
    )
    assert response.status_code == 201
    return response.json()["data"]["id"]


# ==================== Hàm thuần ====================


def test_parse_numeric_accepts_numbers_and_numeric_strings():
    assert parse_numeric(56) == 56
    assert parse_numeric(36.8) == 36.8
    assert parse_numeric("36,8") == 36.8
    assert parse_numeric(" 120 ") == 120
    assert parse_numeric(0) == 0


def test_parse_numeric_rejects_text_and_booleans():
    # Không bóc số ra khỏi câu chữ: "120/80" mà lấy 120 thì biểu đồ sai hẳn.
    assert parse_numeric("120/80") is None
    assert parse_numeric("sốt 39 độ") is None
    assert parse_numeric("Bình thường") is None
    assert parse_numeric(None) is None
    # bool là lớp con của int trong Python — "có/không" không phải chỉ số.
    assert parse_numeric(True) is None


def test_labels_drop_numbering_but_keep_acronyms():
    assert pretty_label("7.2. Thời gian điều trị nội trú") == "Thời gian điều trị nội trú"
    assert pretty_label("SGOT") == "SGOT"
    assert pretty_group_label("PHẦN 7. ĐIỀU TRỊ") == "Điều trị"
    assert pretty_group_label("4.1. Xét nghiệm công thức máu") == "Xét nghiệm công thức máu"
    assert pretty_group_label("SGOT") == "SGOT"


def test_collect_numeric_fields_walks_nested_groups():
    block = {
        "id": "examination",
        "label": "KHÁM BỆNH",
        "type": "block",
        "children": [
            {
                "id": "general",
                "label": "3.1. Toàn thân",
                "type": "group",
                "children": [
                    {"id": "weight", "label": "Cân nặng", "type": "number", "unit": "kg"},
                    {"id": "skin", "label": "Da niêm mạc", "type": "text"},
                ],
            },
            {
                "id": "lab",
                "label": "PHẦN 4. CẬN LÂM SÀNG",
                "type": "group",
                "children": [
                    {
                        "id": "blood",
                        "label": "4.1. Công thức máu",
                        "type": "group",
                        "children": [
                            {"id": "hgb", "label": "Huyết sắc tố", "type": "number", "unit": "g/l"}
                        ],
                    }
                ],
            },
        ],
    }

    fields = {f.key: f for f in collect_numeric_fields(block)}
    assert set(fields) == {"general.weight", "lab.blood.hgb"}
    assert fields["general.weight"].group_label == "Toàn thân"
    assert fields["lab.blood.hgb"].path == ("lab", "blood", "hgb")
    # Nhóm là group gần nhất chứa field, không phải khối cha ngoài cùng.
    assert fields["lab.blood.hgb"].group_label == "Công thức máu"


# ==================== Endpoint ====================


def test_metrics_empty_for_patient_without_exams(client, auth, patient_id):
    response = client.get(f"/api/v1/patients/{patient_id}/exams/metrics", headers=auth)
    assert response.status_code == 200
    data = response.json()["data"]
    assert data["exam_count"] == 0
    assert data["series"] == []
    assert data["truncated"] is False


def test_metrics_builds_series_in_time_order(client, auth, patient_id):
    # Tạo ngược thứ tự thời gian để chắc chắn endpoint tự sắp xếp lại.
    for exam_date, weight, hgb in (
        ("2026-03-01", 58, 140),
        ("2025-01-15", 60.5, None),
    ):
        payload = {
            "exam_date": exam_date,
            "data": {
                "general": {"weight": weight, "skin_mucosa": "Bình thường"},
                "general_lab": {"blood_count": {"hgb": hgb} if hgb else {}},
                "diagnosis": {"definitive": "F32.1"},
            },
        }
        response = client.post(
            f"/api/v1/patients/{patient_id}/exams", headers=auth, json=payload
        )
        assert response.status_code == 201

    response = client.get(f"/api/v1/patients/{patient_id}/exams/metrics", headers=auth)
    assert response.status_code == 200
    data = response.json()["data"]

    assert data["exam_count"] == 2
    series = {item["key"]: item for item in data["series"]}

    weight = series["general.weight"]
    assert weight["label"] == "Cân nặng"
    assert weight["unit"] == "kg"
    assert weight["group_label"] == "Toàn thân"
    assert [p["date"] for p in weight["points"]] == ["2025-01-15", "2026-03-01"]
    assert [p["value"] for p in weight["points"]] == [60.5, 58]

    # Chỉ số chỉ có một lần đo vẫn được trả về, nhưng đúng một điểm.
    assert len(series["general_lab.blood_count.hgb"]["points"]) == 1

    # Trường chữ không bao giờ trở thành chỉ số.
    assert not any("skin_mucosa" in key or "diagnosis" in key for key in series)


def test_metrics_omits_fields_never_recorded(client, auth, patient_id):
    response = client.get(f"/api/v1/patients/{patient_id}/exams/metrics", headers=auth)
    keys = {item["key"] for item in response.json()["data"]["series"]}
    # "Mạch" có trong template nhưng bệnh nhân này chưa từng được đo.
    assert "general.pulse" not in keys


def test_metrics_rejects_unknown_patient(client, auth):
    response = client.get("/api/v1/patients/99999999/exams/metrics", headers=auth)
    assert response.status_code == 404

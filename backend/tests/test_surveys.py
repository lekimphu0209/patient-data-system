from uuid import uuid4

from fastapi.testclient import TestClient

from app.core.config import settings
from app.main import app


def test_survey_batch_is_atomic_and_subject_is_shared():
    prefix = uuid4().hex
    first_id, second_id, extra_id = (f"{prefix}-{index}" for index in range(3))
    record = {
        "id": first_id, "person": prefix, "group": "youth", "form": "F08",
        "patient": {"fullName": "Đối tượng khảo sát"}, "date": "2026-11-13",
        "status": "draft", "source": "Thủ công", "answers": {},
    }
    second = {**record, "id": second_id, "form": "F09"}
    base = "/api/v1/surveys"

    with TestClient(app) as client:
        assert client.get(f"{base}/records").status_code == 401
        login = client.post("/api/v1/auth/login", json={
            "email": settings.DEFAULT_USER_EMAIL, "password": settings.DEFAULT_USER_PASSWORD,
        })
        headers = {"Authorization": f"Bearer {login.json()['access_token']}"}
        forms = client.get(f"{base}/forms", headers=headers).json()
        assert [sum(form["group"] == group for form in forms) for group in ("youth", "military")] == [2, 7]

        def create(*records):
            return client.post(f"{base}/records", json={"records": list(records)}, headers=headers)

        def detail(id):
            return client.get(f"{base}/record", params={"id": id}, headers=headers)

        assert create({**record, "status": "complete"}).status_code == 422
        assert create({**record, "form": "F01"}).status_code == 422
        assert create({**record, "id": "MAU-TN-123-F08"}).status_code == 422
        assert create(record, second).status_code == 201

        subject = {"fullName": "Hồ sơ dùng chung", "hometown": "Hà Nội"}
        assert create({**record, "id": extra_id, "patient": subject}, second).status_code == 409
        assert detail(extra_id).status_code == 404
        original = detail(first_id).json()
        assert original["patient"]["fullName"] == record["patient"]["fullName"]
        updated = {**original, "patient": subject}
        assert client.put(f"{base}/record", json=updated, headers=headers).status_code == 200
        assert client.put(f"{base}/record", json=updated, headers=headers).status_code == 409
        assert detail(second_id).json()["patient"]["fullName"] == subject["fullName"]

        response = client.post(f"{base}/delete", json={"ids": [first_id]}, headers=headers)
        assert response.json() == {"count": 1}
        assert detail(first_id).status_code == 404
        assert detail(second_id).status_code == 200
        client.post(f"{base}/delete", json={"ids": [second_id]}, headers=headers)


def test_ocr_attachment_is_only_in_detail():
    id = f"OCR-{uuid4().hex}"
    base = "/api/v1/surveys"
    with TestClient(app) as client:
        login = client.post("/api/v1/auth/login", json={
            "email": settings.DEFAULT_USER_EMAIL, "password": settings.DEFAULT_USER_PASSWORD,
        })
        headers = {"Authorization": f"Bearer {login.json()['access_token']}"}
        row = {
            "id": id, "person": id, "group": "military", "form": "F01", "patient": {},
            "date": "2026-11-13", "status": "draft", "source": "OCR",
            "ocr": "Văn bản khảo sát", "ocrImage": "data:image/jpeg;base64,YQ==",
        }
        assert client.post(f"{base}/records", json={"records": [row]}, headers=headers).status_code == 201
        records = client.get(f"{base}/records", headers=headers).json()
        listed = next(record for record in records if record["id"] == id)
        assert listed["hasOCR"] and "ocr" not in listed and "ocrImage" not in listed
        detail = client.get(f"{base}/record", params={"id": id}, headers=headers).json()
        assert detail["ocr"] == row["ocr"]
        assert detail["ocrImage"] == row["ocrImage"]
        client.post(f"{base}/delete", json={"ids": [id]}, headers=headers)

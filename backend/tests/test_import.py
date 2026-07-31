import io
import uuid

from fastapi.testclient import TestClient

from app.main import app


def _get_auth_header(client: TestClient) -> dict[str, str]:
    response = client.post(
        "/api/v1/auth/login",
        json={"email": "doctor@example.com", "password": "password123"},
    )
    assert response.status_code == 200
    data = response.json()
    return {"Authorization": f"Bearer {data['access_token']}"}


def test_import_preview_and_commit():
    code = f"PT-IMP-{uuid.uuid4().hex[:8]}"
    with TestClient(app) as client:
        headers = _get_auth_header(client)
        csv_content = (
            "patient_code,full_name,birth_date,age,gender,hometown,"
            "disease_type,diagnosis,status,phone,contact_person,notes\n"
            f"{code},Nguyễn Văn Import,1990-01-01,30,male,Hà Nội,"
            "Tiểu đường,Type 2,active,0909000000,Nguyễn Văn Liên hệ,Test import\n"
        )
        file = io.BytesIO(csv_content.encode())
        preview = client.post(
            "/api/v1/patients/import",
            files={"file": ("patients.csv", file, "text/csv")},
            headers=headers,
        )
    assert preview.status_code == 200
    data = preview.json()
    assert data["valid_count"] == 1
    assert data["invalid_count"] == 0
    assert len(data["rows"]) == 1
    assert data["rows"][0]["data"]["patient_code"] == code

    with TestClient(app) as client:
        headers = _get_auth_header(client)
        commit = client.post(
            "/api/v1/patients/import/commit",
            json={"rows": data["rows"]},
            headers=headers,
        )
    assert commit.status_code == 200
    commit_data = commit.json()
    assert commit_data["created"] == 1
    assert len(commit_data["errors"]) == 0

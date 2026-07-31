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


def test_create_patient():
    with TestClient(app) as client:
        headers = _get_auth_header(client)
        code = f"PT-{uuid.uuid4().hex[:8]}"
        response = client.post(
            "/api/v1/patients",
            json={
                "patient_code": code,
                "full_name": "Nguyễn Văn A",
                "birth_date": "1990-05-15",
                "age": 34,
                "hometown": "Hà Nội",
                "disease_type": "Tiểu đường",
                "diagnosis": "Type 2",
                "status": "active",
                "contact_info": {"phone": "0909000000", "contact_person": "Nguyễn Văn B"},
                "patient_metadata": {"gender": "male", "notes": "Test patient"},
            },
            headers=headers,
        )
    assert response.status_code == 201
    data = response.json()
    assert data["data"]["patient_code"] == code
    assert data["data"]["full_name"] == "Nguyễn Văn A"


def test_list_patients():
    with TestClient(app) as client:
        headers = _get_auth_header(client)
        response = client.get("/api/v1/patients", headers=headers)
    assert response.status_code == 200
    data = response.json()
    assert "data" in data
    assert "pagination" in data
    assert data["pagination"]["page"] == 1


def test_get_patient():
    with TestClient(app) as client:
        headers = _get_auth_header(client)
        code = f"PT-{uuid.uuid4().hex[:8]}"
        create = client.post(
            "/api/v1/patients",
            json={
                "patient_code": code,
                "full_name": "Trần Thị B",
                "status": "active",
            },
            headers=headers,
        )
        patient_id = create.json()["data"]["id"]
        response = client.get(f"/api/v1/patients/{patient_id}", headers=headers)
    assert response.status_code == 200
    assert response.json()["data"]["patient_code"] == code


def test_delete_patient():
    with TestClient(app) as client:
        headers = _get_auth_header(client)
        code = f"PT-{uuid.uuid4().hex[:8]}"
        create = client.post(
            "/api/v1/patients",
            json={
                "patient_code": code,
                "full_name": "Lê Văn C",
                "status": "active",
            },
            headers=headers,
        )
        patient_id = create.json()["data"]["id"]
        response = client.delete(f"/api/v1/patients/{patient_id}", headers=headers)
    assert response.status_code == 200

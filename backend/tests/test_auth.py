import uuid

from fastapi.testclient import TestClient

from app.main import app


def test_register():
    with TestClient(app) as client:
        email = f"new-{uuid.uuid4().hex[:8]}@example.com"
        response = client.post(
            "/api/v1/auth/register",
            json={
                "email": email,
                "password": "password123",
                "full_name": "Bác sĩ mới",
                "role": "doctor",
            },
        )
    assert response.status_code == 201
    data = response.json()
    assert "access_token" in data
    assert data["user"]["email"] == email


def test_health_check():
    with TestClient(app) as client:
        response = client.get("/api/health")
    assert response.status_code == 200
    assert response.json() == {"status": "ok"}


def test_login_success():
    with TestClient(app) as client:
        response = client.post(
            "/api/v1/auth/login",
            json={"email": "doctor@example.com", "password": "password123"},
        )
    assert response.status_code == 200
    data = response.json()
    assert "access_token" in data
    assert data["token_type"] == "bearer"


def test_login_failure():
    with TestClient(app) as client:
        response = client.post(
            "/api/v1/auth/login",
            json={"email": "doctor@example.com", "password": "wrongpassword"},
        )
    assert response.status_code == 401


def test_get_me():
    with TestClient(app) as client:
        login = client.post(
            "/api/v1/auth/login",
            json={"email": "doctor@example.com", "password": "password123"},
        )
        token = login.json()["access_token"]
        response = client.get(
            "/api/v1/auth/me",
            headers={"Authorization": f"Bearer {token}"},
        )
    assert response.status_code == 200
    data = response.json()
    assert data["email"] == "doctor@example.com"


def test_logout():
    with TestClient(app) as client:
        login = client.post(
            "/api/v1/auth/login",
            json={"email": "doctor@example.com", "password": "password123"},
        )
        token = login.json()["access_token"]
        response = client.post(
            "/api/v1/auth/logout",
            headers={"Authorization": f"Bearer {token}"},
        )
    assert response.status_code == 200

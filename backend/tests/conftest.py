import os

os.environ["DATABASE_URL"] = "sqlite:///./test.db"
os.environ["SECRET_KEY"] = "test-secret"
os.environ["ALLOW_PUBLIC_REGISTRATION"] = "true"

import pytest


@pytest.fixture(autouse=True, scope="session")
def never_call_paid_apis():
    """Chặn cứng mọi lời gọi ra nhà cung cấp AI khi chạy test.

    ``settings`` là singleton dựng lúc import module đầu tiên, nên đặt biến môi
    trường trong từng file test là quá muộn — nếu máy có OPENAI_API_KEY thật thì
    bộ test sẽ gọi API thật, vừa tốn tiền vừa cho kết quả không ổn định. Ghi đè
    thẳng vào settings sau khi nó đã được dựng mới chắc chắn.
    """
    from app.core.config import settings

    original = {
        "OCR_PROVIDER": settings.OCR_PROVIDER,
        "DOC_PARSER_PROVIDER": settings.DOC_PARSER_PROVIDER,
        "OPENAI_API_KEY": settings.OPENAI_API_KEY,
    }
    settings.OCR_PROVIDER = "stub"
    settings.DOC_PARSER_PROVIDER = "stub"
    settings.OPENAI_API_KEY = ""

    yield

    for key, value in original.items():
        setattr(settings, key, value)


@pytest.fixture
def storage(tmp_path, monkeypatch):
    """Thư mục lưu file phiếu khảo sát riêng cho từng test."""
    from app.modules.surveys.ocr import service

    monkeypatch.setattr(service, "STORAGE_DIR", tmp_path)
    return tmp_path


@pytest.fixture
def api():
    """Client đã đăng nhập bằng tài khoản mặc định."""
    from fastapi.testclient import TestClient

    from app.core.config import settings
    from app.main import app

    with TestClient(app) as client:
        login = client.post("/api/v1/auth/login", json={
            "email": settings.DEFAULT_USER_EMAIL, "password": settings.DEFAULT_USER_PASSWORD,
        })
        client.headers["Authorization"] = f"Bearer {login.json()['access_token']}"
        yield client

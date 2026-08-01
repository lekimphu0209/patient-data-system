import os

os.environ["DATABASE_URL"] = "sqlite:///./test.db"
os.environ["SECRET_KEY"] = "test-secret"

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

import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.core.config import settings
from app.core.database import Base, SessionLocal, engine

# Import all models first so Base.metadata contains every table.
from app.modules.auth import models as auth_models  # noqa: F401
from app.modules.encounters import models as encounter_models  # noqa: F401
from app.modules.patients import models as patient_models  # noqa: F401
from app.modules.documents import models as document_models  # noqa: F401

from app.modules.auth.router import router as auth_router
from app.modules.documents.router import router as documents_router
from app.modules.patients.router import router as patients_router


logger = logging.getLogger(__name__)


def _add_missing_columns() -> None:
    """Bổ sung cột mới vào bảng đã tồn tại.

    ``create_all`` chỉ tạo bảng thiếu chứ không thêm cột thiếu, nên các cột mới
    (ví dụ ``data`` của examinations / medical_histories) sẽ không xuất hiện trên
    database đã chạy từ trước. Chỉ ADD COLUMN, không bao giờ sửa hay xoá.
    """
    from sqlalchemy import inspect, text
    from sqlalchemy.schema import CreateColumn

    inspector = inspect(engine)
    existing_tables = set(inspector.get_table_names())
    for table in Base.metadata.sorted_tables:
        if table.name not in existing_tables:
            continue
        present = {c["name"] for c in inspector.get_columns(table.name)}
        for column in table.columns:
            if column.name in present:
                continue
            ddl = str(CreateColumn(column).compile(dialect=engine.dialect))
            statement = f'ALTER TABLE "{table.name}" ADD COLUMN {ddl}'
            # Mỗi cột một transaction riêng: một cột hỏng không kéo theo cả loạt.
            try:
                with engine.begin() as conn:
                    conn.execute(text(statement))
            except Exception:
                # Thêm cột NOT NULL không có default vào bảng đã có dữ liệu thì
                # Postgres từ chối. Hạ xuống nullable để ứng dụng vẫn khởi động
                # được; giá trị mới vẫn do default phía model đảm bảo.
                relaxed = ddl.replace(" NOT NULL", "")
                if relaxed == ddl:
                    logger.exception("Không thêm được cột %s.%s", table.name, column.name)
                    continue
                try:
                    with engine.begin() as conn:
                        conn.execute(text(f'ALTER TABLE "{table.name}" ADD COLUMN {relaxed}'))
                    logger.warning(
                        "Đã thêm cột %s.%s dưới dạng nullable (bảng đã có dữ liệu sẵn).",
                        table.name,
                        column.name,
                    )
                except Exception:
                    logger.exception("Không thêm được cột %s.%s", table.name, column.name)


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Create tables for development convenience.
    # In production, rely on Alembic migrations.
    Base.metadata.create_all(bind=engine)
    _add_missing_columns()
    db = SessionLocal()
    try:
        from app.modules.auth.service import AuthService
        service = AuthService(db)
        service.seed_default_user(
            email=settings.DEFAULT_USER_EMAIL,
            password=settings.DEFAULT_USER_PASSWORD,
            full_name="Bác sĩ A",
        )
    finally:
        db.close()
    yield


app = FastAPI(
    title="Patient Data System API",
    version="0.1.0",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.CORS_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(auth_router, prefix="/api/v1/auth", tags=["auth"])
app.include_router(patients_router, prefix="/api/v1/patients", tags=["patients"])
app.include_router(documents_router, prefix="/api/v1/documents", tags=["documents"])


@app.get("/api/health", tags=["health"])
def health_check():
    return {"status": "ok"}

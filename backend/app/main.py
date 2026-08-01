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
    with engine.begin() as conn:
        for table in Base.metadata.sorted_tables:
            if table.name not in existing_tables:
                continue
            present = {c["name"] for c in inspector.get_columns(table.name)}
            for column in table.columns:
                if column.name in present:
                    continue
                ddl = CreateColumn(column).compile(dialect=engine.dialect)
                conn.execute(text(f'ALTER TABLE "{table.name}" ADD COLUMN {ddl}'))


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

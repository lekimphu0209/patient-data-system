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
from app.modules.import_export.router import router as import_export_router
from app.modules.patients.router import router as patients_router


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Create tables for development convenience.
    # In production, rely on Alembic migrations.
    Base.metadata.create_all(bind=engine)
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
app.include_router(import_export_router, prefix="/api/v1", tags=["import-export"])


@app.get("/api/health", tags=["health"])
def health_check():
    return {"status": "ok"}

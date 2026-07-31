from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.deps import get_current_active_user
from app.modules.auth.models import User
from app.modules.auth.schemas import (
    ChangePasswordRequest,
    LoginRequest,
    LoginResponse,
    RegisterRequest,
    UpdateProfileRequest,
    UserResponse,
)
from app.modules.auth.service import AuthService

router = APIRouter()


@router.post("/login", response_model=LoginResponse)
def login(data: LoginRequest, db: Session = Depends(get_db)):
    service = AuthService(db)
    return service.login(data)


@router.post("/register", response_model=LoginResponse, status_code=201)
def register(data: RegisterRequest, db: Session = Depends(get_db)):
    service = AuthService(db)
    return service.register(data)


@router.get("/me", response_model=UserResponse)
def get_me(current_user: User = Depends(get_current_active_user)):
    return UserResponse.model_validate(current_user)


@router.patch("/me", response_model=UserResponse)
def update_me(
    request: UpdateProfileRequest,
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db),
):
    service = AuthService(db)
    return service.update_profile(current_user.id, request.full_name)


@router.post("/logout")
def logout():
    # Stateless JWT; client removes token.
    return {"message": "Logged out"}


@router.patch("/password")
def change_password(
    request: ChangePasswordRequest,
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db),
):
    service = AuthService(db)
    service.change_password(
        current_user.id,
        request.current_password,
        request.new_password,
        request.confirm_password,
    )
    return {"message": "Password changed successfully"}

from fastapi import HTTPException, status
from sqlalchemy.orm import Session

from app.core.security import create_access_token, get_password_hash, verify_password
from app.modules.auth.repository import AuthRepository
from app.modules.auth.schemas import LoginRequest, LoginResponse, RegisterRequest, UserResponse


class AuthService:
    def __init__(self, db: Session):
        self.repo = AuthRepository(db)

    def login(self, data: LoginRequest) -> LoginResponse:
        user = self.repo.get_by_email(data.email)
        if not user or not verify_password(data.password, user.password_hash):
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Incorrect email or password",
            )
        access_token = create_access_token(data={"sub": str(user.id)})
        return LoginResponse(
            access_token=access_token,
            user=UserResponse.model_validate(user),
        )

    def register(self, data: RegisterRequest) -> LoginResponse:
        existing = self.repo.get_by_email(data.email)
        if existing:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="Email already registered",
            )
        user = self.repo.create(
            email=data.email,
            password_hash=get_password_hash(data.password),
            full_name=data.full_name,
            role=data.role,
        )
        access_token = create_access_token(data={"sub": str(user.id)})
        return LoginResponse(
            access_token=access_token,
            user=UserResponse.model_validate(user),
        )

    def change_password(
        self,
        user_id: int,
        current_password: str,
        new_password: str,
        confirm_password: str,
    ) -> None:
        if new_password != confirm_password:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="New password and confirmation do not match",
            )
        user = self.repo.get_by_id(user_id)
        if not user:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND, detail="User not found"
            )
        if not verify_password(current_password, user.password_hash):
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Incorrect current password",
            )
        self.repo.update_password_hash(user_id, get_password_hash(new_password))

    def update_profile(self, user_id: int, full_name: str) -> UserResponse:
        user = self.repo.update_profile(user_id, full_name.strip())
        if not user:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND, detail="User not found"
            )
        return UserResponse.model_validate(user)

    def get_me(self, user_id: int) -> UserResponse:
        user = self.repo.get_by_id(user_id)
        if not user:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND, detail="User not found"
            )
        return UserResponse.model_validate(user)

    def seed_default_user(self, email: str, password: str, full_name: str):
        existing = self.repo.get_by_email(email)
        if existing:
            return existing
        return self.repo.create(
            email=email,
            password_hash=get_password_hash(password),
            full_name=full_name,
        )

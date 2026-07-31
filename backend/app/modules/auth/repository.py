from sqlalchemy.orm import Session

from app.modules.auth.models import User


class AuthRepository:
    def __init__(self, db: Session):
        self.db = db

    def get_by_id(self, user_id: int) -> User | None:
        return self.db.query(User).filter(User.id == user_id).first()

    def get_by_email(self, email: str) -> User | None:
        return self.db.query(User).filter(User.email == email).first()

    def create(
        self, email: str, password_hash: str, full_name: str, role: str = "doctor"
    ) -> User:
        user = User(email=email, password_hash=password_hash, full_name=full_name, role=role)
        self.db.add(user)
        self.db.commit()
        self.db.refresh(user)
        return user

    def update_password_hash(self, user_id: int, password_hash: str) -> User | None:
        user = self.get_by_id(user_id)
        if not user:
            return None
        user.password_hash = password_hash
        self.db.commit()
        return user

    def update_profile(self, user_id: int, full_name: str) -> User | None:
        user = self.get_by_id(user_id)
        if not user:
            return None
        user.full_name = full_name
        self.db.commit()
        self.db.refresh(user)
        return user

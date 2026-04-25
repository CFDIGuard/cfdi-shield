from datetime import datetime

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.config import settings
from app.models.user import User


class UserRepository:
    def __init__(self, db: Session):
        self.db = db

    def create(self, username: str, password_hash: str) -> User:
        user = User(
            username=username,
            password_hash=password_hash,
            use_sat_validation=settings.enable_sat_validation,
        )
        self.db.add(user)
        self.db.commit()
        self.db.refresh(user)
        return user

    def get_by_id(self, user_id: int) -> User | None:
        return self.db.get(User, user_id)

    def get_by_username(self, username: str) -> User | None:
        statement = select(User).where(User.username == username)
        return self.db.execute(statement).scalar_one_or_none()

    def get_by_password_reset_token_hash(self, token_hash: str) -> User | None:
        statement = select(User).where(User.password_reset_token_hash == token_hash)
        return self.db.execute(statement).scalar_one_or_none()

    def save(self, user: User) -> User:
        self.db.add(user)
        self.db.commit()
        self.db.refresh(user)
        return user

    def update_password(self, user: User, password_hash: str) -> User:
        user.password_hash = password_hash
        user.password_reset_token_hash = None
        user.password_reset_expires_at = None
        user.two_factor_code_hash = None
        user.two_factor_expires_at = None
        return self.save(user)

    def set_password_reset(self, user: User, token_hash: str, expires_at: datetime) -> User:
        user.password_reset_token_hash = token_hash
        user.password_reset_expires_at = expires_at
        return self.save(user)

    def clear_password_reset(self, user: User) -> User:
        user.password_reset_token_hash = None
        user.password_reset_expires_at = None
        return self.save(user)

    def set_two_factor_enabled(self, user: User, enabled: bool) -> User:
        user.two_factor_enabled = enabled
        if not enabled:
            user.two_factor_code_hash = None
            user.two_factor_expires_at = None
        return self.save(user)

    def set_use_sat_validation(self, user: User, enabled: bool) -> User:
        user.use_sat_validation = enabled
        return self.save(user)

    def set_two_factor_code(self, user: User, code_hash: str, expires_at: datetime) -> User:
        user.two_factor_code_hash = code_hash
        user.two_factor_expires_at = expires_at
        return self.save(user)

    def clear_two_factor_code(self, user: User) -> User:
        user.two_factor_code_hash = None
        user.two_factor_expires_at = None
        return self.save(user)

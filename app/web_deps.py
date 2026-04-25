from fastapi import Depends, Request, status
from fastapi.responses import RedirectResponse

from app.core.config import settings
from app.db.init_db import ensure_db_initialized
from app.db.session import SessionLocal
from app.models.user import User
from app.repositories.user_repository import UserRepository
from app.services.auth_service import verify_pending_two_factor_token, verify_session_token


def get_current_user(request: Request) -> User | None:
    user_id = verify_session_token(request.cookies.get(settings.session_cookie_name))
    if user_id is None:
        return None

    ensure_db_initialized()
    with SessionLocal() as db:
        user = UserRepository(db).get_by_id(user_id)

    if user is None or not user.is_active:
        return None
    return user


def require_user(current_user: User | None = Depends(get_current_user)) -> User | RedirectResponse:
    if current_user is None:
        return RedirectResponse(url="/login", status_code=status.HTTP_303_SEE_OTHER)
    return current_user


def get_pending_two_factor_user(request: Request) -> User | None:
    user_id = verify_pending_two_factor_token(request.cookies.get(settings.pending_two_factor_cookie_name))
    if user_id is None:
        return None

    ensure_db_initialized()
    with SessionLocal() as db:
        user = UserRepository(db).get_by_id(user_id)

    if user is None or not user.is_active:
        return None
    return user

from fastapi import Depends, Request, status
from fastapi.responses import RedirectResponse
from sqlalchemy.orm import Session

from app.core.config import settings
from app.db.session import get_db
from app.models.user import User
from app.repositories.user_repository import UserRepository
from app.services.auth_service import verify_pending_two_factor_token
from app.services.session_service import get_user_from_session_token


def get_current_user(
    request: Request,
    db: Session = Depends(get_db),
) -> User | None:
    raw_token = request.cookies.get(settings.session_cookie_name)
    if not raw_token:
        return None

    user = get_user_from_session_token(db, raw_token)
    if user is None or not user.is_active:
        return None
    return user


def require_user(current_user: User | None = Depends(get_current_user)) -> User | RedirectResponse:
    if current_user is None:
        return RedirectResponse(url="/login", status_code=status.HTTP_303_SEE_OTHER)
    return current_user


def get_pending_two_factor_user(
    request: Request,
    db: Session = Depends(get_db),
) -> User | None:
    user_id = verify_pending_two_factor_token(request.cookies.get(settings.pending_two_factor_cookie_name))
    if user_id is None:
        return None

    user = UserRepository(db).get_by_id(user_id)
    if user is None or not user.is_active:
        return None
    return user

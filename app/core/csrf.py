import os
import secrets
from collections.abc import Callable

from fastapi import HTTPException, Request, status

CSRF_SESSION_KEY = "csrf_token"
APP_SECRET_KEY = os.getenv("APP_SECRET_KEY")

if not APP_SECRET_KEY:
    # fallback only for local/dev environments
    APP_SECRET_KEY = secrets.token_urlsafe(48)


def get_csrf_token(request: Request) -> str:
    session = getattr(request, "session", None)
    if session is None:
        raise RuntimeError("SessionMiddleware is required for CSRF protection.")

    token = session.get(CSRF_SESSION_KEY)
    if not token:
        token = secrets.token_urlsafe(32)
        session[CSRF_SESSION_KEY] = token
    return token


def validate_csrf_token(request: Request, form_token: str | None) -> bool:
    session = getattr(request, "session", None)
    if session is None:
        return False

    session_token = session.get(CSRF_SESSION_KEY)
    if not session_token or not form_token:
        return False
    return secrets.compare_digest(session_token, form_token)


def csrf_context_processor(request: Request) -> dict[str, Callable[[], str]]:
    return {"csrf_token": lambda: get_csrf_token(request)}


async def require_csrf(request: Request) -> None:
    if request.method.upper() in ("GET", "HEAD", "OPTIONS", "TRACE"):
        return

    form = await request.form()
    form_token = form.get("csrf_token")
    if not isinstance(form_token, str) or not validate_csrf_token(request, form_token):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="CSRF validation failed",
        )

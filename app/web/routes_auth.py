import logging
from datetime import datetime

from fastapi import APIRouter, Depends, Form, Request, status
from fastapi.responses import HTMLResponse, RedirectResponse
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.core.config import settings
from app.db.session import get_db
from app.models.user import User
from app.repositories.user_repository import UserRepository
from app.services.auth_service import (
    create_password_reset_expiration,
    create_password_reset_token,
    create_pending_two_factor_token,
    create_session_token,
    create_two_factor_code,
    create_two_factor_expiration,
    hash_password,
    hash_token,
    verify_password,
)
from app.services.notification_service import (
    send_password_reset_email,
    send_two_factor_email,
    smtp_is_configured,
    smtp_ready_for_delivery,
)
from app.templates import templates
from app.web.utils import web_url
from app.web_deps import get_current_user, get_pending_two_factor_user


logger = logging.getLogger(__name__)
router = APIRouter(tags=["auth"])


def _enable_registration() -> bool:
    return bool(getattr(settings, "enable_registration", True))


def _enable_beta_mode() -> bool:
    return bool(getattr(settings, "enable_beta_mode", False))


def _beta_access_code() -> str:
    return str(getattr(settings, "beta_access_code", "") or "")


def _beta_allowed_emails() -> set[str]:
    value = getattr(settings, "beta_allowed_emails", set())
    return value if isinstance(value, set) else set()


def _two_factor_available() -> bool:
    return bool(settings.enable_two_factor)


def _two_factor_can_be_enabled() -> bool:
    return _two_factor_available() and smtp_ready_for_delivery()


def _set_session_cookie(response: RedirectResponse, user_id: int) -> None:
    response.set_cookie(
        key=settings.session_cookie_name,
        value=create_session_token(user_id),
        max_age=settings.session_max_age_seconds,
        httponly=True,
        samesite="lax",
    )


def _set_pending_two_factor_cookie(response: RedirectResponse, user_id: int) -> None:
    response.set_cookie(
        key=settings.pending_two_factor_cookie_name,
        value=create_pending_two_factor_token(user_id),
        max_age=settings.pending_two_factor_max_age_seconds,
        httponly=True,
        samesite="lax",
    )


def _clear_auth_cookies(response: RedirectResponse) -> None:
    response.delete_cookie(settings.session_cookie_name)
    response.delete_cookie(settings.pending_two_factor_cookie_name)


def _registration_error_for(username: str, access_code: str | None) -> str | None:
    if not _enable_registration():
        return "El registro publico esta desactivado en este entorno."
    if not _enable_beta_mode():
        return None

    normalized_username = username.strip().lower()
    normalized_access_code = (access_code or "").strip()
    configured_code = _beta_access_code()
    if normalized_access_code and configured_code and normalized_access_code == configured_code:
        return None
    if normalized_username in _beta_allowed_emails():
        return None
    return "El registro beta requiere un codigo de acceso valido o un correo autorizado."


@router.get("/login", response_class=HTMLResponse, response_model=None)
def login_page(
    request: Request,
    message: str | None = None,
    error: str | None = None,
    current_user: User | None = Depends(get_current_user),
    pending_user: User | None = Depends(get_pending_two_factor_user),
):
    if current_user is not None:
        return RedirectResponse(url="/dashboard-web", status_code=status.HTTP_303_SEE_OTHER)
    if pending_user is not None:
        return RedirectResponse(url="/verify-2fa", status_code=status.HTTP_303_SEE_OTHER)

    return templates.TemplateResponse(
        request,
        "login.html",
        {
            "message": message,
            "error": error,
            "enable_registration": _enable_registration(),
        },
    )


@router.post("/login", response_model=None)
def login(
    username: str = Form(...),
    password: str = Form(...),
    db: Session = Depends(get_db),
):
    normalized_username = username.strip().lower()
    repository = UserRepository(db)
    user = repository.get_by_username(normalized_username)

    if user is None or not verify_password(password, user.password_hash) or not user.is_active:
        logger.warning("Failed login attempt for username=%s", normalized_username)
        return RedirectResponse(
            url=web_url("/login", error="Usuario o contrasena incorrectos."),
            status_code=status.HTTP_303_SEE_OTHER,
        )

    if settings.enable_two_factor and user.two_factor_enabled:
        code = create_two_factor_code()
        repository.set_two_factor_code(
            user,
            code_hash=hash_token(code),
            expires_at=create_two_factor_expiration(),
        )

        delivered = send_two_factor_email(to_email=user.username, code=code)
        if not delivered:
            if smtp_is_configured():
                repository.clear_two_factor_code(user)
                logger.warning("2FA delivery unavailable for username=%s", user.username)
                return RedirectResponse(
                    url=web_url(
                        "/login",
                        error="No fue posible enviar el codigo de verificacion. Revisa la configuracion de correo.",
                    ),
                    status_code=status.HTTP_303_SEE_OTHER,
                )
            else:
                repository.clear_two_factor_code(user)
                logger.warning("2FA delivery unavailable for username=%s", user.username)
                return RedirectResponse(
                    url=web_url(
                        "/login",
                        error="No fue posible enviar el codigo de verificacion. Revisa la configuracion de correo.",
                    ),
                    status_code=status.HTTP_303_SEE_OTHER,
                )

        response = RedirectResponse(
            url=web_url("/verify-2fa", message="Introduce tu codigo de verificacion."),
            status_code=status.HTTP_303_SEE_OTHER,
        )
        _clear_auth_cookies(response)
        _set_pending_two_factor_cookie(response, user.id)
        logger.info("2FA challenge started for %s", user.username)
        return response

    response = RedirectResponse(
        url=web_url("/dashboard-web", message="Sesion iniciada correctamente."),
        status_code=status.HTTP_303_SEE_OTHER,
    )
    _clear_auth_cookies(response)
    _set_session_cookie(response, user.id)
    logger.info("User logged in: %s", user.username)
    return response


@router.get("/verify-2fa", response_class=HTMLResponse, response_model=None)
def verify_two_factor_page(
    request: Request,
    message: str | None = None,
    error: str | None = None,
    pending_user: User | None = Depends(get_pending_two_factor_user),
    current_user: User | None = Depends(get_current_user),
):
    if current_user is not None:
        return RedirectResponse(url="/dashboard-web", status_code=status.HTTP_303_SEE_OTHER)
    if pending_user is None:
        return RedirectResponse(url="/login", status_code=status.HTTP_303_SEE_OTHER)

    return templates.TemplateResponse(
        request,
        "verify_2fa.html",
        {
            "message": message,
            "error": error,
            "pending_user": pending_user,
        },
    )


@router.post("/verify-2fa", response_model=None)
def verify_two_factor(
    code: str = Form(...),
    db: Session = Depends(get_db),
    pending_user: User | None = Depends(get_pending_two_factor_user),
):
    if pending_user is None:
        return RedirectResponse(url="/login", status_code=status.HTTP_303_SEE_OTHER)

    user = UserRepository(db).get_by_id(pending_user.id)
    if user is None:
        return RedirectResponse(url="/login", status_code=status.HTTP_303_SEE_OTHER)

    now = datetime.utcnow()
    is_valid = (
        user.two_factor_code_hash is not None
        and user.two_factor_expires_at is not None
        and user.two_factor_expires_at >= now
        and user.two_factor_code_hash == hash_token(code.strip())
    )
    if not is_valid:
        return RedirectResponse(
            url=web_url("/verify-2fa", error="Codigo invalido o expirado."),
            status_code=status.HTTP_303_SEE_OTHER,
        )

    UserRepository(db).clear_two_factor_code(user)
    response = RedirectResponse(
        url=web_url("/dashboard-web", message="Sesion iniciada correctamente."),
        status_code=status.HTTP_303_SEE_OTHER,
    )
    _clear_auth_cookies(response)
    _set_session_cookie(response, user.id)
    logger.info("2FA verification completed for %s", user.username)
    return response


@router.get("/forgot-password", response_class=HTMLResponse, response_model=None)
def forgot_password_page(
    request: Request,
    message: str | None = None,
    error: str | None = None,
):
    return templates.TemplateResponse(
        request,
        "forgot_password.html",
        {
            "message": message,
            "error": error,
        },
    )


@router.post("/forgot-password", response_model=None)
def forgot_password(
    username: str = Form(...),
    db: Session = Depends(get_db),
):
    normalized_username = username.strip().lower()
    repository = UserRepository(db)
    user = repository.get_by_username(normalized_username)

    if user is not None and user.is_active:
        raw_token = create_password_reset_token()
        expires_at = create_password_reset_expiration()
        repository.set_password_reset(
            user,
            token_hash=hash_token(raw_token),
            expires_at=expires_at,
        )
        delivered = send_password_reset_email(to_email=user.username, reset_token=raw_token)
        if not delivered:
            repository.clear_password_reset(user)
            logger.warning("Password reset delivery unavailable for username=%s", user.username)

    return RedirectResponse(
        url=web_url(
            "/forgot-password",
            message="Si la cuenta existe, enviamos un enlace de recuperacion. Revisa tu correo.",
        ),
        status_code=status.HTTP_303_SEE_OTHER,
    )


@router.get("/reset-password", response_class=HTMLResponse, response_model=None)
def reset_password_page(
    request: Request,
    token: str | None = None,
    message: str | None = None,
    error: str | None = None,
):
    if not token:
        return RedirectResponse(
            url=web_url("/forgot-password", error="El enlace de recuperacion no es valido."),
            status_code=status.HTTP_303_SEE_OTHER,
        )

    return templates.TemplateResponse(
        request,
        "reset_password.html",
        {
            "token": token,
            "message": message,
            "error": error,
        },
    )


@router.post("/reset-password", response_model=None)
def reset_password(
    token: str = Form(...),
    password: str = Form(...),
    password_confirm: str = Form(...),
    db: Session = Depends(get_db),
):
    if len(password) < 8:
        return RedirectResponse(
            url=web_url("/reset-password", token=token, error="La contrasena debe tener al menos 8 caracteres."),
            status_code=status.HTTP_303_SEE_OTHER,
        )
    if password != password_confirm:
        return RedirectResponse(
            url=web_url("/reset-password", token=token, error="Las contrasenas no coinciden."),
            status_code=status.HTTP_303_SEE_OTHER,
        )

    repository = UserRepository(db)
    user = repository.get_by_password_reset_token_hash(hash_token(token))
    now = datetime.utcnow()
    if (
        user is None
        or user.password_reset_expires_at is None
        or user.password_reset_expires_at < now
    ):
        return RedirectResponse(
            url=web_url("/forgot-password", error="El enlace de recuperacion es invalido o expiro."),
            status_code=status.HTTP_303_SEE_OTHER,
        )

    repository.update_password(user, hash_password(password))
    logger.info("Password reset completed for %s", user.username)
    return RedirectResponse(
        url=web_url("/login", message="Contrasena actualizada correctamente."),
        status_code=status.HTTP_303_SEE_OTHER,
    )


@router.get("/register", response_class=HTMLResponse, response_model=None)
def register_page(
    request: Request,
    message: str | None = None,
    error: str | None = None,
    current_user: User | None = Depends(get_current_user),
):
    if current_user is not None:
        return RedirectResponse(url="/dashboard-web", status_code=status.HTTP_303_SEE_OTHER)
    if not _enable_registration():
        return RedirectResponse(
            url=web_url("/login", error="El registro publico esta desactivado en este entorno."),
            status_code=status.HTTP_303_SEE_OTHER,
        )

    return templates.TemplateResponse(
        request,
        "register.html",
        {
            "message": message,
            "error": error,
            "enable_beta_mode": _enable_beta_mode(),
            "beta_access_code_required": bool(_beta_access_code()),
        },
    )


@router.post("/register", response_model=None)
def register(
    username: str = Form(...),
    password: str = Form(...),
    password_confirm: str = Form(...),
    access_code: str | None = Form(default=None),
    db: Session = Depends(get_db),
):
    normalized_username = username.strip().lower()
    registration_error = _registration_error_for(normalized_username, access_code)
    if registration_error is not None:
        return RedirectResponse(
            url=web_url("/register", error=registration_error),
            status_code=status.HTTP_303_SEE_OTHER,
        )
    if len(normalized_username) < 3:
        return RedirectResponse(
            url=web_url("/register", error="El usuario debe tener al menos 3 caracteres."),
            status_code=status.HTTP_303_SEE_OTHER,
        )
    if len(password) < 8:
        return RedirectResponse(
            url=web_url("/register", error="La contrasena debe tener al menos 8 caracteres."),
            status_code=status.HTTP_303_SEE_OTHER,
        )
    if password != password_confirm:
        return RedirectResponse(
            url=web_url("/register", error="Las contrasenas no coinciden."),
            status_code=status.HTTP_303_SEE_OTHER,
        )

    repository = UserRepository(db)
    if repository.get_by_username(normalized_username) is not None:
        return RedirectResponse(
            url=web_url("/register", error="Ese usuario ya existe."),
            status_code=status.HTTP_303_SEE_OTHER,
        )

    try:
        user = repository.create(username=normalized_username, password_hash=hash_password(password))
    except IntegrityError:
        db.rollback()
        return RedirectResponse(
            url=web_url("/register", error="Ese usuario ya existe."),
            status_code=status.HTTP_303_SEE_OTHER,
        )

    response = RedirectResponse(
        url=web_url("/dashboard-web", message="Cuenta creada correctamente."),
        status_code=status.HTTP_303_SEE_OTHER,
    )
    _clear_auth_cookies(response)
    _set_session_cookie(response, user.id)
    logger.info("User registered: %s", user.username)
    return response

@router.post("/two-factor/toggle", response_model=None)
def toggle_two_factor(
    current_user: User | None = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    if current_user is None:
        return RedirectResponse(url="/login", status_code=status.HTTP_303_SEE_OTHER)

    if not _two_factor_available():
        return RedirectResponse(
            url=web_url("/dashboard-web", error="La verificacion en dos pasos esta desactivada en este entorno."),
            status_code=status.HTTP_303_SEE_OTHER,
        )

    repository = UserRepository(db)
    user = repository.get_by_id(current_user.id)
    if user is None:
        return RedirectResponse(url="/login", status_code=status.HTTP_303_SEE_OTHER)

    if not user.two_factor_enabled and not _two_factor_can_be_enabled():
        return RedirectResponse(
            url=web_url("/dashboard-web", error="2FA requiere configuracion SMTP."),
            status_code=status.HTTP_303_SEE_OTHER,
        )

    repository.set_two_factor_enabled(user, not user.two_factor_enabled)
    status_message = "2FA activado correctamente." if user.two_factor_enabled else "2FA desactivado correctamente."
    return RedirectResponse(
        url=web_url("/dashboard-web", message=status_message),
        status_code=status.HTTP_303_SEE_OTHER,
    )


@router.post("/logout", response_model=None)
def logout():
    response = RedirectResponse(
        url=web_url("/login", message="Sesion cerrada correctamente."),
        status_code=status.HTTP_303_SEE_OTHER,
    )
    _clear_auth_cookies(response)
    return response

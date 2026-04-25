from __future__ import annotations

import logging
import re
import smtplib
from email.message import EmailMessage
from typing import Any
from urllib.parse import quote

from app.core.config import settings


logger = logging.getLogger(__name__)
EMAIL_REGEX = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")


def looks_like_email(value: str | None) -> bool:
    return bool(value and EMAIL_REGEX.match(value.strip()))


def smtp_is_configured() -> bool:
    return bool(settings.smtp_host and settings.smtp_port and settings.smtp_from_email)


def smtp_diagnostics() -> dict[str, Any]:
    return {
        "smtp_host": bool(settings.smtp_host),
        "smtp_port": settings.smtp_port,
        "smtp_user": bool(settings.smtp_user),
        "smtp_use_tls": settings.smtp_use_tls,
        "smtp_use_ssl": settings.smtp_use_ssl,
        "smtp_from_email": bool(settings.smtp_from_email),
    }


def log_smtp_configuration() -> None:
    logger.info(
        "SMTP config host=%s port=%s user=%s tls=%s ssl=%s from_email=%s",
        bool(settings.smtp_host),
        settings.smtp_port,
        bool(settings.smtp_user),
        settings.smtp_use_tls,
        settings.smtp_use_ssl,
        bool(settings.smtp_from_email),
    )


def smtp_ready_for_delivery() -> bool:
    return bool(
        settings.smtp_host
        and settings.smtp_port
        and settings.smtp_user
        and settings.smtp_password
        and settings.smtp_from_email
    )


def smtp_probe() -> tuple[bool, str]:
    if not smtp_ready_for_delivery():
        return False, "SMTP incompleto: faltan host, puerto, usuario, password o remitente."

    try:
        if settings.smtp_use_ssl:
            with smtplib.SMTP_SSL(settings.smtp_host, settings.smtp_port, timeout=15) as client:
                client.login(settings.smtp_user, settings.smtp_password)
        else:
            with smtplib.SMTP(settings.smtp_host, settings.smtp_port, timeout=15) as client:
                if settings.smtp_use_tls:
                    client.starttls()
                client.login(settings.smtp_user, settings.smtp_password)
    except smtplib.SMTPAuthenticationError:
        return False, (
            "Autenticacion SMTP rechazada. Gmail requiere App Password y 2FA habilitado en la cuenta."
        )
    except smtplib.SMTPException as exc:
        return False, f"SMTP error: {exc}"
    except OSError as exc:
        return False, f"SMTP connection error: {exc}"

    return True, "Conexion SMTP autenticada correctamente."


def send_email(*, to_email: str, subject: str, body: str) -> bool:
    if not smtp_is_configured() or not looks_like_email(to_email):
        logger.warning("SMTP delivery skipped for recipient=%s due to missing config or invalid email", _mask_email(to_email))
        return False

    message = EmailMessage()
    message["Subject"] = subject
    message["From"] = settings.smtp_from_email
    message["To"] = to_email.strip()
    message.set_content(body)

    try:
        logger.info("Intentando enviar correo a %s", _mask_email(to_email))
        if settings.smtp_use_ssl:
            with smtplib.SMTP_SSL(settings.smtp_host, settings.smtp_port, timeout=15) as client:
                if settings.smtp_user:
                    client.login(settings.smtp_user, settings.smtp_password)
                client.send_message(message)
        else:
            with smtplib.SMTP(settings.smtp_host, settings.smtp_port, timeout=15) as client:
                if settings.smtp_use_tls:
                    client.starttls()
                if settings.smtp_user:
                    client.login(settings.smtp_user, settings.smtp_password)
                client.send_message(message)
    except smtplib.SMTPAuthenticationError:
        logger.warning(
            "SMTP error: autenticacion rechazada para user_configured=%s. Gmail requiere App Password y 2FA habilitado.",
            bool(settings.smtp_user),
        )
        return False
    except smtplib.SMTPException as exc:
        logger.warning("SMTP error: %s", exc)
        return False
    except OSError as exc:
        logger.warning("SMTP error: %s", exc)
        return False
    except Exception as exc:
        logger.warning("SMTP error: %s", exc)
        return False

    logger.info("Correo enviado correctamente a %s", _mask_email(to_email))
    return True


def send_password_reset_email(*, to_email: str, reset_token: str) -> bool:
    reset_link = f"{settings.base_url.rstrip('/')}/reset-password?token={quote(reset_token)}"
    body = (
        "Recibimos una solicitud para restablecer tu contrasena.\n\n"
        "Usa el siguiente enlace para continuar:\n\n"
        f"{reset_link}\n\n"
        "Si no solicitaste este cambio, puedes ignorar este mensaje.\n"
    )
    return send_email(
        to_email=to_email,
        subject="Recuperacion de contrasena - CFDI Shield",
        body=body,
    )


def send_two_factor_email(*, to_email: str, code: str) -> bool:
    body = (
        "Tu codigo de verificacion para CFDI Shield es:\n\n"
        f"{code}\n\n"
        "El codigo expira pronto. Si no iniciaste sesion, ignora este mensaje.\n"
    )
    return send_email(
        to_email=to_email,
        subject="Codigo de verificacion - CFDI Shield",
        body=body,
    )


def _mask_email(email: str) -> str:
    if not looks_like_email(email):
        return "***"
    local, domain = email.split("@", 1)
    if len(local) <= 2:
        masked_local = local[0] + "*"
    else:
        masked_local = local[:2] + "***"
    return f"{masked_local}@{domain}"

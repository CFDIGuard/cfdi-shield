import hashlib
import hmac
import os
import secrets
from datetime import datetime, timedelta

from app.core.csrf import APP_SECRET_KEY
from app.core.config import settings


PBKDF2_ITERATIONS = 390000
TOKEN_HASH_ALGORITHM = "sha256"


def _get_secret_key() -> str:
    return APP_SECRET_KEY


def hash_password(password: str) -> str:
    salt = os.urandom(16)
    digest = hashlib.pbkdf2_hmac("sha256", password.encode("utf-8"), salt, PBKDF2_ITERATIONS)
    return f"pbkdf2_sha256${PBKDF2_ITERATIONS}${salt.hex()}${digest.hex()}"


def verify_password(password: str, password_hash: str) -> bool:
    try:
        algorithm, iterations, salt_hex, digest_hex = password_hash.split("$", 3)
        if algorithm != "pbkdf2_sha256":
            return False
        digest = hashlib.pbkdf2_hmac(
            "sha256",
            password.encode("utf-8"),
            bytes.fromhex(salt_hex),
            int(iterations),
        )
        return hmac.compare_digest(digest.hex(), digest_hex)
    except (ValueError, TypeError):
        return False


def create_session_token(user_id: int) -> str:
    payload = str(user_id)
    signature = hmac.new(
        _get_secret_key().encode("utf-8"),
        payload.encode("utf-8"),
        hashlib.sha256,
    ).hexdigest()
    return f"{payload}:{signature}"


def create_pending_two_factor_token(user_id: int) -> str:
    payload = f"2fa:{user_id}"
    signature = hmac.new(
        _get_secret_key().encode("utf-8"),
        payload.encode("utf-8"),
        hashlib.sha256,
    ).hexdigest()
    return f"{payload}:{signature}"


def verify_session_token(token: str | None) -> int | None:
    if not token or ":" not in token:
        return None

    payload, signature = token.split(":", 1)
    expected_signature = hmac.new(
        _get_secret_key().encode("utf-8"),
        payload.encode("utf-8"),
        hashlib.sha256,
    ).hexdigest()
    if not hmac.compare_digest(signature, expected_signature):
        return None

    try:
        return int(payload)
    except ValueError:
        return None


def verify_pending_two_factor_token(token: str | None) -> int | None:
    if not token or ":" not in token:
        return None

    payload, signature = token.rsplit(":", 1)
    expected_signature = hmac.new(
        _get_secret_key().encode("utf-8"),
        payload.encode("utf-8"),
        hashlib.sha256,
    ).hexdigest()
    if not hmac.compare_digest(signature, expected_signature):
        return None
    if not payload.startswith("2fa:"):
        return None

    try:
        return int(payload.split(":", 1)[1])
    except ValueError:
        return None


def hash_token(token: str) -> str:
    return hashlib.new(TOKEN_HASH_ALGORITHM, token.encode("utf-8")).hexdigest()


def create_password_reset_token() -> str:
    return secrets.token_urlsafe(32)


def create_password_reset_expiration() -> datetime:
    return datetime.utcnow() + timedelta(minutes=settings.password_reset_token_ttl_minutes)


def create_two_factor_code() -> str:
    return f"{secrets.randbelow(1000000):06d}"


def create_two_factor_expiration() -> datetime:
    return datetime.utcnow() + timedelta(minutes=settings.two_factor_code_ttl_minutes)

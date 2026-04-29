from __future__ import annotations

import hashlib
import hmac
import logging
import secrets
from datetime import datetime, timedelta, timezone

from sqlalchemy import select, update
from sqlalchemy.orm import Session

from app.core.csrf import APP_SECRET_KEY
from app.core.config import settings
from app.models.user import User
from app.models.user_session import UserSession
from app.services.security_utils import mask_username


logger = logging.getLogger(__name__)


def _utc_now() -> datetime:
    return datetime.now(timezone.utc)


def _to_utc(value: datetime | None) -> datetime | None:
    if value is None:
        return None
    if value.tzinfo is None:
        return value.replace(tzinfo=timezone.utc)
    return value.astimezone(timezone.utc)


def _log_security_event(
    event: str,
    *,
    user: User | None = None,
    user_id: int | None = None,
    session_id: str | None = None,
    result: str = "ok",
    reason: str | None = None,
) -> None:
    username = user.username if user is not None else None
    effective_user_id = user.id if user is not None else user_id
    logger.info(
        "security_event=%s result=%s user=%s user_id=%s org=%s session_id=%s reason=%s",
        event,
        result,
        mask_username(username) if username else "-",
        effective_user_id if effective_user_id is not None else "-",
        "-",
        session_id or "-",
        reason or "-",
    )


def _hash_with_secret(value: str | None) -> str | None:
    if not value:
        return None
    return hmac.new(
        APP_SECRET_KEY.encode("utf-8"),
        value.encode("utf-8"),
        hashlib.sha256,
    ).hexdigest()


def _session_lifetime_delta() -> timedelta:
    return timedelta(hours=settings.session_max_age_hours)


def _session_idle_delta() -> timedelta:
    return timedelta(minutes=settings.session_idle_timeout_minutes)


def _should_touch_last_seen(session: UserSession, now: datetime) -> bool:
    interval = max(int(settings.session_update_last_seen_interval_seconds or 0), 0)
    if interval == 0:
        return True
    last_seen = _to_utc(session.last_seen_at) or now
    return (now - last_seen).total_seconds() >= interval


def _revoke_session_object(db: Session, session: UserSession, reason: str) -> None:
    if session.revoked_at is None:
        session.revoked_at = _utc_now()
        session.revoked_reason = reason
        db.add(session)


def create_user_session(
    db: Session,
    user_id: int,
    ip: str | None = None,
    user_agent: str | None = None,
) -> str:
    raw_token = secrets.token_urlsafe(32)
    now = _utc_now()
    session = UserSession(
        user_id=user_id,
        token_hash=_hash_with_secret(raw_token),
        created_at=now,
        last_seen_at=now,
        expires_at=now + _session_lifetime_delta(),
        ip_hash=_hash_with_secret(ip),
        user_agent_hash=_hash_with_secret(user_agent),
    )
    db.add(session)
    db.commit()
    db.refresh(session)
    _log_security_event("session_created", user_id=user_id, session_id=session.id, result="success")
    return raw_token


def get_session_by_token_hash(db: Session, token_hash: str) -> UserSession | None:
    statement = select(UserSession).where(UserSession.token_hash == token_hash)
    return db.execute(statement).scalar_one_or_none()


def get_user_from_session_token(
    db: Session,
    raw_token: str | None,
) -> User | None:
    if not raw_token:
        return None

    now = _utc_now()
    token_hash = _hash_with_secret(raw_token)
    if not token_hash:
        return None

    session = get_session_by_token_hash(db, token_hash)
    if session is None:
        _log_security_event("session_invalid", result="missing")
        return None

    expires_at = _to_utc(session.expires_at)
    last_seen_at = _to_utc(session.last_seen_at)
    revoked_at = _to_utc(session.revoked_at)

    if revoked_at is not None:
        _log_security_event("session_invalid", user_id=session.user_id, session_id=session.id, result="revoked")
        return None

    if expires_at is not None and expires_at <= now:
        _revoke_session_object(db, session, "expired")
        db.commit()
        _log_security_event("session_expired", user_id=session.user_id, session_id=session.id, result="expired")
        return None

    if last_seen_at is not None and now - last_seen_at > _session_idle_delta():
        _revoke_session_object(db, session, "idle_timeout")
        db.commit()
        _log_security_event("session_expired", user_id=session.user_id, session_id=session.id, result="idle_timeout")
        return None

    user = db.execute(select(User).where(User.id == session.user_id)).scalar_one_or_none()
    if user is None or not user.is_active:
        _revoke_session_object(db, session, "user_inactive")
        db.commit()
        _log_security_event("session_invalid", user_id=session.user_id, session_id=session.id, result="user_inactive")
        return None

    if _should_touch_last_seen(session, now):
        session.last_seen_at = now
        db.add(session)
        db.commit()

    return user


def revoke_session(db: Session, raw_token: str | None, reason: str = "logout") -> bool:
    if not raw_token:
        return False
    token_hash = _hash_with_secret(raw_token)
    if not token_hash:
        return False
    session = get_session_by_token_hash(db, token_hash)
    if session is None:
        _log_security_event("session_invalid", result="missing", reason=reason)
        return False
    _revoke_session_object(db, session, reason)
    db.commit()
    _log_security_event("session_revoked", user_id=session.user_id, session_id=session.id, result="success", reason=reason)
    return True


def revoke_all_user_sessions(db: Session, user_id: int, reason: str = "global_logout") -> int:
    now = _utc_now()
    result = db.execute(
        update(UserSession)
        .where(
            UserSession.user_id == user_id,
            UserSession.revoked_at.is_(None),
        )
        .values(revoked_at=now, revoked_reason=reason)
    )
    db.commit()
    affected = int(result.rowcount or 0)
    if affected > 0:
        _log_security_event("global_logout", user_id=user_id, result="success", reason=reason)
    return affected


def cleanup_expired_sessions(db: Session) -> int:
    now = _utc_now()
    result = db.execute(
        update(UserSession)
        .where(
            UserSession.revoked_at.is_(None),
            UserSession.expires_at <= now,
        )
        .values(revoked_at=now, revoked_reason="expired")
    )
    db.commit()
    return int(result.rowcount or 0)

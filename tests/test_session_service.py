from __future__ import annotations

from datetime import timedelta, timezone, datetime

from sqlalchemy import create_engine, select
from sqlalchemy.orm import sessionmaker

from app.db.base import Base
from app.models.user import User
from app.models.user_session import UserSession
from app.services.auth_service import hash_password
from app.services.session_service import (
    create_user_session,
    get_user_from_session_token,
    revoke_all_user_sessions,
    revoke_session,
)


def _utc_now() -> datetime:
    return datetime.now(timezone.utc)


def _make_db(tmp_path):
    db_path = tmp_path / "session_service.db"
    engine = create_engine(f"sqlite:///{db_path}", connect_args={"check_same_thread": False})
    session_local = sessionmaker(bind=engine, autoflush=False, autocommit=False)
    Base.metadata.drop_all(bind=engine)
    Base.metadata.create_all(bind=engine)
    return engine, session_local


def test_create_user_session_generates_non_deterministic_tokens(tmp_path, monkeypatch):
    _, session_local = _make_db(tmp_path)
    monkeypatch.setattr("app.services.session_service.settings.session_max_age_hours", 24)

    with session_local() as db:
        user = User(username="demo@example.com", password_hash=hash_password("password123"), is_active=True)
        db.add(user)
        db.commit()
        db.refresh(user)

        token_a = create_user_session(db, user.id, ip="127.0.0.1", user_agent="UA-1")
        token_b = create_user_session(db, user.id, ip="127.0.0.1", user_agent="UA-1")

        assert token_a != token_b
        sessions = list(db.execute(select(UserSession).where(UserSession.user_id == user.id)).scalars().all())
        assert len(sessions) == 2
        assert all(session.token_hash != token_a for session in sessions)
        assert all(session.token_hash != token_b for session in sessions)


def test_revoked_session_fails_validation(tmp_path):
    _, session_local = _make_db(tmp_path)

    with session_local() as db:
        user = User(username="revoked@example.com", password_hash=hash_password("password123"), is_active=True)
        db.add(user)
        db.commit()
        db.refresh(user)

        token = create_user_session(db, user.id)
        assert get_user_from_session_token(db, token) is not None

        revoked = revoke_session(db, token, reason="logout")
        assert revoked is True
        assert get_user_from_session_token(db, token) is None


def test_expired_session_fails_validation(tmp_path):
    _, session_local = _make_db(tmp_path)

    with session_local() as db:
        user = User(username="expired@example.com", password_hash=hash_password("password123"), is_active=True)
        db.add(user)
        db.commit()
        db.refresh(user)

        token = create_user_session(db, user.id)
        session = db.execute(select(UserSession).where(UserSession.user_id == user.id)).scalar_one()
        session.expires_at = _utc_now() - timedelta(minutes=1)
        db.add(session)
        db.commit()

        assert get_user_from_session_token(db, token) is None


def test_idle_timeout_fails_validation(tmp_path, monkeypatch):
    _, session_local = _make_db(tmp_path)
    monkeypatch.setattr("app.services.session_service.settings.session_idle_timeout_minutes", 1)

    with session_local() as db:
        user = User(username="idle@example.com", password_hash=hash_password("password123"), is_active=True)
        db.add(user)
        db.commit()
        db.refresh(user)

        token = create_user_session(db, user.id)
        session = db.execute(select(UserSession).where(UserSession.user_id == user.id)).scalar_one()
        session.last_seen_at = _utc_now() - timedelta(minutes=5)
        db.add(session)
        db.commit()

        assert get_user_from_session_token(db, token) is None


def test_revoke_all_user_sessions_revokes_every_active_session(tmp_path):
    _, session_local = _make_db(tmp_path)

    with session_local() as db:
        user = User(username="global@example.com", password_hash=hash_password("password123"), is_active=True)
        db.add(user)
        db.commit()
        db.refresh(user)

        token_a = create_user_session(db, user.id)
        token_b = create_user_session(db, user.id)

        revoked_count = revoke_all_user_sessions(db, user.id)
        assert revoked_count == 2
        assert get_user_from_session_token(db, token_a) is None
        assert get_user_from_session_token(db, token_b) is None

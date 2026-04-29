from __future__ import annotations

import re

from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

import app.web_deps as web_deps_module
from app.core.config import settings
from app.db import init_db as init_db_module
from app.db import session as session_module
from app.db.base import Base
from app.main import app
from app.repositories.user_repository import UserRepository
from app.services import rate_limit_service
from app.services.auth_service import hash_password
from app.services.session_service import create_user_session


def _extract_csrf_token(html: str) -> str:
    match = re.search(r'name="csrf_token"\s+value="([^"]+)"', html)
    assert match is not None
    return match.group(1)


def test_security_headers_present(monkeypatch):
    client = TestClient(app, base_url="https://testserver")
    monkeypatch.setattr(settings, "cookie_secure", True)

    response = client.get("/login")

    assert response.status_code == 200
    assert response.headers["x-frame-options"] == "DENY"
    assert response.headers["x-content-type-options"] == "nosniff"
    assert response.headers["referrer-policy"] == "strict-origin-when-cross-origin"
    assert "default-src 'self'" in response.headers["content-security-policy"]
    assert response.headers["strict-transport-security"] == "max-age=31536000; includeSubDomains"


def test_login_cookie_flags_hardened(tmp_path, monkeypatch):
    db_path = tmp_path / "security.db"
    engine = create_engine(f"sqlite:///{db_path}", connect_args={"check_same_thread": False})
    testing_session_local = sessionmaker(bind=engine, autoflush=False, autocommit=False)

    monkeypatch.setattr(session_module, "engine", engine)
    monkeypatch.setattr(session_module, "SessionLocal", testing_session_local)
    monkeypatch.setattr(init_db_module, "engine", engine)
    monkeypatch.setattr(init_db_module, "_initialized", False)
    monkeypatch.setattr(web_deps_module, "SessionLocal", testing_session_local)
    monkeypatch.setattr(settings, "cookie_secure", True)

    Base.metadata.create_all(bind=engine)
    init_db_module.ensure_db_initialized()

    with testing_session_local() as db:
        UserRepository(db).create("hardening@example.com", hash_password("password123"))

    client = TestClient(app, base_url="https://testserver")
    login_page = client.get("/login")
    csrf_token = _extract_csrf_token(login_page.text)

    response = client.post(
        "/login",
        data={
            "username": "hardening@example.com",
            "password": "password123",
            "csrf_token": csrf_token,
        },
        follow_redirects=False,
    )

    assert response.status_code == 303
    set_cookie_header = response.headers.get("set-cookie", "")
    assert f"{settings.session_cookie_name}=" in set_cookie_header
    assert "HttpOnly" in set_cookie_header
    assert "SameSite=lax" in set_cookie_header
    assert "Secure" in set_cookie_header


def test_logout_revokes_server_side_session(tmp_path, monkeypatch):
    db_path = tmp_path / "logout_revoke.db"
    engine = create_engine(f"sqlite:///{db_path}", connect_args={"check_same_thread": False})
    testing_session_local = sessionmaker(bind=engine, autoflush=False, autocommit=False)

    monkeypatch.setattr(session_module, "engine", engine)
    monkeypatch.setattr(session_module, "SessionLocal", testing_session_local)
    monkeypatch.setattr(init_db_module, "engine", engine)
    monkeypatch.setattr(init_db_module, "_initialized", False)
    monkeypatch.setattr(web_deps_module, "SessionLocal", testing_session_local)
    monkeypatch.setattr(settings, "cookie_secure", False)

    Base.metadata.create_all(bind=engine)
    init_db_module.ensure_db_initialized()

    with testing_session_local() as db:
        user = UserRepository(db).create("logout@example.com", hash_password("password123"))
        raw_token = create_user_session(db, user.id, ip="127.0.0.1", user_agent="pytest")

    client = TestClient(app)
    cookie_name = settings.session_cookie_name
    auth_cookies = {cookie_name: raw_token}
    dashboard_page = client.get("/dashboard-web", cookies=auth_cookies)
    assert dashboard_page.status_code == 200
    csrf_token = _extract_csrf_token(dashboard_page.text)
    session_cookie = dashboard_page.cookies.get("cfdi_shield_web_session") or client.cookies.get("cfdi_shield_web_session")
    assert session_cookie is not None

    logout_response = client.post(
        "/logout",
        cookies={cookie_name: raw_token, "cfdi_shield_web_session": session_cookie},
        data={"csrf_token": csrf_token},
        follow_redirects=False,
    )
    assert logout_response.status_code == 303

    reused = client.get("/dashboard-web", cookies=auth_cookies, follow_redirects=False)
    assert reused.status_code == 303
    assert reused.headers["location"].startswith("/login")


def test_rate_limit_still_blocks(monkeypatch):
    monkeypatch.setattr(settings, "auth_rate_limit_window_seconds", 60)
    monkeypatch.setattr(settings, "auth_rate_limit_ip_max_attempts", 2)
    monkeypatch.setattr(settings, "auth_rate_limit_user_max_attempts", 2)
    rate_limit_service._rate_limit_store.clear()

    assert rate_limit_service.is_rate_limited("login", "127.0.0.1", "demo@example.com") is False
    rate_limit_service.record_rate_limit_failure("login", "127.0.0.1", "demo@example.com")
    assert rate_limit_service.is_rate_limited("login", "127.0.0.1", "demo@example.com") is False
    rate_limit_service.record_rate_limit_failure("login", "127.0.0.1", "demo@example.com")
    assert rate_limit_service.is_rate_limited("login", "127.0.0.1", "demo@example.com") is True

import logging
import os
import time
from pathlib import Path
from urllib.parse import urlparse

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse
from fastapi.staticfiles import StaticFiles
from sqlalchemy import text
from starlette.middleware.sessions import SessionMiddleware

from app.api.router import api_router
from app.core.config import settings
from app.core.csrf import APP_SECRET_KEY
from app.db.init_db import ensure_db_initialized
from app.db.session import SessionLocal
from app.resource_paths import resource_path
from app.services.notification_service import log_smtp_configuration
from app.web.routes_auth import router as auth_router
from app.web.routes_pages import router as web_router

Path("logs").mkdir(exist_ok=True)

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s [%(name)s] %(message)s",
    handlers=[
        logging.StreamHandler(),
        logging.FileHandler(Path("logs") / "cfdi_shield.log", encoding="utf-8"),
    ],
)
logger = logging.getLogger(__name__)


def _database_log_details() -> tuple[str, str]:
    if settings.sqlite_database_path is not None:
        return "sqlite", str(settings.sqlite_database_path)

    parsed = urlparse(settings.database_url)
    engine = parsed.scheme.split("+", 1)[0] if parsed.scheme else "unknown"
    host = parsed.hostname or "unknown-host"
    database = parsed.path.lstrip("/") or "unknown-db"
    return engine, f"{host}/{database}"


def _content_security_policy() -> str:
    # TODO(v1.2): retirar 'unsafe-inline' moviendo CSS/JS inline a archivos estaticos
    # o usando nonces/hashes. Se mantiene por compatibilidad con plantillas actuales.
    return (
        "default-src 'self'; "
        "base-uri 'self'; "
        "frame-ancestors 'none'; "
        "object-src 'none'; "
        "form-action 'self'; "
        "img-src 'self' data:; "
        "font-src 'self' data:; "
        "style-src 'self' 'unsafe-inline'; "
        "script-src 'self' 'unsafe-inline'; "
        "connect-src 'self'"
    )


def create_app() -> FastAPI:
    app = FastAPI(
        title=settings.app_name,
        version=settings.app_version,
        docs_url="/docs" if settings.debug else None,
        redoc_url="/redoc" if settings.debug else None,
        openapi_url="/openapi.json" if settings.debug else None,
    )
    app.add_middleware(
        SessionMiddleware,
        secret_key=APP_SECRET_KEY,
        session_cookie="cfdi_shield_web_session",
        same_site="lax",
        https_only=settings.use_secure_cookies,
        max_age=settings.auth_session_max_age_seconds,
    )
    app.mount("/static", StaticFiles(directory=str(resource_path("static"))), name="static")
    app.include_router(api_router, prefix=settings.api_v1_prefix)
    app.include_router(auth_router)
    app.include_router(web_router)

    @app.on_event("startup")
    def startup_log() -> None:
        db_engine, db_target = _database_log_details()
        logger.info("Starting %s v%s", settings.app_name, settings.app_version)
        logger.info(
            "Runtime config debug=%s local_mode=%s sat_validation=%s port=%s",
            settings.debug,
            settings.local_mode,
            settings.enable_sat_validation,
            settings.port,
        )
        logger.info("Database engine=%s target=%s", db_engine, db_target)
        logger.info("Current working directory=%s", os.getcwd())
        if settings.sqlite_database_path is not None:
            logger.info("SQLite database path=%s", settings.sqlite_database_path)
        log_smtp_configuration()

    @app.middleware("http")
    async def security_headers(request: Request, call_next):
        response = await call_next(request)
        if settings.security_headers_enabled:
            response.headers.setdefault("X-Frame-Options", "DENY")
            response.headers.setdefault("X-Content-Type-Options", "nosniff")
            response.headers.setdefault("Referrer-Policy", "strict-origin-when-cross-origin")
            response.headers.setdefault("Content-Security-Policy", _content_security_policy())
            if settings.use_secure_cookies:
                hsts_value = "max-age=31536000; includeSubDomains"
                if settings.app_env.strip().lower() == "production":
                    hsts_value += "; preload"
                response.headers.setdefault(
                    "Strict-Transport-Security",
                    hsts_value,
                )
        return response

    @app.middleware("http")
    async def log_requests(request: Request, call_next):
        start = time.perf_counter()
        response = await call_next(request)
        duration_ms = (time.perf_counter() - start) * 1000
        if response.status_code >= 500:
            logger.error(
                "Request failed %s %s status=%s duration_ms=%.2f",
                request.method,
                request.url.path,
                response.status_code,
                duration_ms,
            )
        elif duration_ms >= 3000:
            logger.warning(
                "Slow request %s %s status=%s duration_ms=%.2f",
                request.method,
                request.url.path,
                response.status_code,
                duration_ms,
            )
        return response

    @app.exception_handler(Exception)
    async def unhandled_exception_handler(request: Request, exc: Exception):
        logger.exception("Unhandled error on %s %s", request.method, request.url.path)
        return JSONResponse(
            status_code=500,
            content={"detail": "Internal server error", "path": request.url.path},
        )

    @app.get("/ping", tags=["health"], response_model=None)
    def ping():
        return {"status": "ok"}

    @app.get("/health", tags=["health"], response_model=None)
    def health():
        return {"status": "ok"}

    @app.get("/ready", tags=["health"], response_model=None)
    def ready():
        ensure_db_initialized()
        with SessionLocal() as db:
            db.execute(text("SELECT 1"))
        return {"status": "ready"}

    @app.on_event("shutdown")
    def shutdown_log() -> None:
        logger.info("Stopping %s v%s", settings.app_name, settings.app_version)

    return app


app = create_app()

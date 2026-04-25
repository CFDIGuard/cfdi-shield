import logging
import threading

from sqlalchemy import text

from app.db.base import Base
from app.db.session import engine
from app.models import Invoice, SatValidationCache, User


logger = logging.getLogger(__name__)
_init_lock = threading.Lock()
_initialized = False


def _column_names(table_name: str) -> set[str]:
    with engine.begin() as connection:
        rows = connection.execute(text(f"PRAGMA table_info({table_name})")).fetchall()
    return {row[1] for row in rows}


def _ensure_user_columns() -> None:
    columns = _column_names("users")
    statements = {
        "two_factor_enabled": "ALTER TABLE users ADD COLUMN two_factor_enabled BOOLEAN DEFAULT 0",
        "use_sat_validation": "ALTER TABLE users ADD COLUMN use_sat_validation BOOLEAN DEFAULT 1",
        "two_factor_code_hash": "ALTER TABLE users ADD COLUMN two_factor_code_hash VARCHAR",
        "two_factor_expires_at": "ALTER TABLE users ADD COLUMN two_factor_expires_at DATETIME",
        "password_reset_token_hash": "ALTER TABLE users ADD COLUMN password_reset_token_hash VARCHAR",
        "password_reset_expires_at": "ALTER TABLE users ADD COLUMN password_reset_expires_at DATETIME",
    }

    with engine.begin() as connection:
        for column_name, statement in statements.items():
            if column_name not in columns:
                connection.execute(text(statement))


def _ensure_invoice_indexes() -> None:
    with engine.begin() as connection:
        connection.execute(
            text("CREATE UNIQUE INDEX IF NOT EXISTS ix_invoices_uuid_unique ON invoices(uuid)")
        )


def _ensure_invoice_columns() -> None:
    columns = _column_names("invoices")
    statements = {
        "archivo": "ALTER TABLE invoices ADD COLUMN archivo VARCHAR",
        "razon_social": "ALTER TABLE invoices ADD COLUMN razon_social VARCHAR",
        "folio": "ALTER TABLE invoices ADD COLUMN folio VARCHAR",
        "fecha_emision": "ALTER TABLE invoices ADD COLUMN fecha_emision VARCHAR",
        "mes": "ALTER TABLE invoices ADD COLUMN mes VARCHAR",
        "subtotal": "ALTER TABLE invoices ADD COLUMN subtotal FLOAT DEFAULT 0",
        "iva_retenido": "ALTER TABLE invoices ADD COLUMN iva_retenido FLOAT DEFAULT 0",
        "isr_retenido": "ALTER TABLE invoices ADD COLUMN isr_retenido FLOAT DEFAULT 0",
        "moneda": "ALTER TABLE invoices ADD COLUMN moneda VARCHAR",
        "metodo_pago": "ALTER TABLE invoices ADD COLUMN metodo_pago VARCHAR",
        "score_proveedor": "ALTER TABLE invoices ADD COLUMN score_proveedor FLOAT DEFAULT 0",
        "detalle_riesgo": "ALTER TABLE invoices ADD COLUMN detalle_riesgo TEXT",
        "sat_validado_at": "ALTER TABLE invoices ADD COLUMN sat_validado_at DATETIME",
    }

    with engine.begin() as connection:
        for column_name, statement in statements.items():
            if column_name not in columns:
                connection.execute(text(statement))


def ensure_db_initialized() -> None:
    global _initialized
    if _initialized:
        return

    with _init_lock:
        if _initialized:
            return
        logger.info("Initializing database schema")
        Base.metadata.create_all(bind=engine)
        _ensure_user_columns()
        _ensure_invoice_columns()
        _ensure_invoice_indexes()
        _initialized = True
        logger.info("Database schema ready")

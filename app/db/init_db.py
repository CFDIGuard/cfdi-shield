import logging
import threading

from sqlalchemy import inspect, text

from app.db.base import Base
from app.db.session import engine
from app.models import Invoice, SatValidationCache, User


logger = logging.getLogger(__name__)
_init_lock = threading.Lock()
_initialized = False


def _database_dialect() -> str:
    return engine.dialect.name


def _column_names(table_name: str) -> set[str]:
    if _database_dialect() == "sqlite":
        with engine.begin() as connection:
            rows = connection.execute(text(f"PRAGMA table_info({table_name})")).fetchall()
        return {row[1] for row in rows}

    inspector = inspect(engine)
    return {column["name"] for column in inspector.get_columns(table_name)}


def _bool_default(value: bool) -> str:
    return "TRUE" if value else "FALSE"


def _datetime_type() -> str:
    return "TIMESTAMP"


def _float_default(value: float) -> str:
    return str(int(value)) if value == int(value) else str(value)


def _add_column_statement(table_name: str, column_name: str, column_type: str, default: str | None = None) -> str:
    statement = f"ALTER TABLE {table_name} ADD COLUMN {column_name} {column_type}"
    if default is not None:
        statement += f" DEFAULT {default}"
    return statement


def _execute_add_column_if_missing(table_name: str, column_name: str, statement: str) -> None:
    columns = _column_names(table_name)
    with engine.begin() as connection:
        if column_name not in columns:
            connection.execute(text(statement))


def _ensure_user_columns() -> None:
    statements = {
        "two_factor_enabled": _add_column_statement(
            "users", "two_factor_enabled", "BOOLEAN", _bool_default(False)
        ),
        "use_sat_validation": _add_column_statement(
            "users", "use_sat_validation", "BOOLEAN", _bool_default(True)
        ),
        "two_factor_code_hash": _add_column_statement("users", "two_factor_code_hash", "VARCHAR"),
        "two_factor_expires_at": _add_column_statement("users", "two_factor_expires_at", _datetime_type()),
        "password_reset_token_hash": _add_column_statement("users", "password_reset_token_hash", "VARCHAR"),
        "password_reset_expires_at": _add_column_statement(
            "users", "password_reset_expires_at", _datetime_type()
        ),
    }

    for column_name, statement in statements.items():
        _execute_add_column_if_missing("users", column_name, statement)


def _ensure_invoice_indexes() -> None:
    with engine.begin() as connection:
        connection.execute(
            text("CREATE UNIQUE INDEX IF NOT EXISTS ix_invoices_uuid_unique ON invoices(uuid)")
        )


def _ensure_invoice_columns() -> None:
    statements = {
        "archivo": _add_column_statement("invoices", "archivo", "VARCHAR"),
        "razon_social": _add_column_statement("invoices", "razon_social", "VARCHAR"),
        "folio": _add_column_statement("invoices", "folio", "VARCHAR"),
        "fecha_emision": _add_column_statement("invoices", "fecha_emision", "VARCHAR"),
        "mes": _add_column_statement("invoices", "mes", "VARCHAR"),
        "subtotal": _add_column_statement("invoices", "subtotal", "FLOAT", _float_default(0)),
        "total_original": _add_column_statement("invoices", "total_original", "FLOAT", _float_default(0)),
        "iva_retenido": _add_column_statement("invoices", "iva_retenido", "FLOAT", _float_default(0)),
        "isr_retenido": _add_column_statement("invoices", "isr_retenido", "FLOAT", _float_default(0)),
        "moneda": _add_column_statement("invoices", "moneda", "VARCHAR"),
        "moneda_original": _add_column_statement("invoices", "moneda_original", "VARCHAR"),
        "tipo_cambio_xml": _add_column_statement("invoices", "tipo_cambio_xml", "FLOAT"),
        "tipo_cambio_usado": _add_column_statement("invoices", "tipo_cambio_usado", "FLOAT"),
        "total_mxn": _add_column_statement("invoices", "total_mxn", "FLOAT"),
        "fuente_tipo_cambio": _add_column_statement("invoices", "fuente_tipo_cambio", "VARCHAR"),
        "fecha_tipo_cambio": _add_column_statement("invoices", "fecha_tipo_cambio", "VARCHAR"),
        "metodo_pago": _add_column_statement("invoices", "metodo_pago", "VARCHAR"),
        "score_proveedor": _add_column_statement(
            "invoices", "score_proveedor", "FLOAT", _float_default(0)
        ),
        "detalle_riesgo": _add_column_statement("invoices", "detalle_riesgo", "TEXT"),
        "sat_validado_at": _add_column_statement("invoices", "sat_validado_at", _datetime_type()),
    }

    for column_name, statement in statements.items():
        _execute_add_column_if_missing("invoices", column_name, statement)


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

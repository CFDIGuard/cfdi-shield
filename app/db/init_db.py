import logging
import threading

from sqlalchemy import inspect, text

from app.db.base import Base
from app.db.session import engine
from app.models import BankTransaction, Invoice, PaymentComplement, SatValidationCache, User


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
        if _database_dialect() == "postgresql":
            connection.execute(text("ALTER TABLE invoices DROP CONSTRAINT IF EXISTS invoices_uuid_key"))
        connection.execute(text("DROP INDEX IF EXISTS ix_invoices_uuid_unique"))
        connection.execute(text("DROP INDEX IF EXISTS ix_invoices_uuid"))
        connection.execute(text("CREATE INDEX IF NOT EXISTS ix_invoices_uuid ON invoices(uuid)"))
        connection.execute(text("CREATE INDEX IF NOT EXISTS ix_invoices_user_id ON invoices(user_id)"))
        connection.execute(
            text(
                "CREATE UNIQUE INDEX IF NOT EXISTS ix_invoices_user_uuid_unique "
                "ON invoices(user_id, uuid)"
            )
        )


def _ensure_invoice_user_ownership_constraints() -> None:
    if _database_dialect() != "postgresql":
        return

    with engine.begin() as connection:
        existing = {
            row[0]
            for row in connection.execute(
                text(
                    "SELECT constraint_name "
                    "FROM information_schema.table_constraints "
                    "WHERE table_name = 'invoices'"
                )
            ).fetchall()
        }
        if "invoices_user_id_fkey" not in existing:
            connection.execute(
                text(
                    "ALTER TABLE invoices "
                    "ADD CONSTRAINT invoices_user_id_fkey "
                    "FOREIGN KEY (user_id) REFERENCES users(id)"
                )
            )
        connection.execute(text("ALTER TABLE invoices ALTER COLUMN user_id SET NOT NULL"))


def _ensure_invoice_columns() -> None:
    statements = {
        "user_id": _add_column_statement("invoices", "user_id", "INTEGER"),
        "archivo": _add_column_statement("invoices", "archivo", "VARCHAR"),
        "tipo_comprobante": _add_column_statement("invoices", "tipo_comprobante", "VARCHAR"),
        "razon_social": _add_column_statement("invoices", "razon_social", "VARCHAR"),
        "folio": _add_column_statement("invoices", "folio", "VARCHAR"),
        "fecha_emision": _add_column_statement("invoices", "fecha_emision", "VARCHAR"),
        "mes": _add_column_statement("invoices", "mes", "VARCHAR"),
        "subtotal": _add_column_statement("invoices", "subtotal", "FLOAT", _float_default(0)),
        "descuento": _add_column_statement("invoices", "descuento", "FLOAT", _float_default(0)),
        "total_original": _add_column_statement("invoices", "total_original", "FLOAT", _float_default(0)),
        "iva_trasladado": _add_column_statement("invoices", "iva_trasladado", "FLOAT", _float_default(0)),
        "iva_retenido": _add_column_statement("invoices", "iva_retenido", "FLOAT", _float_default(0)),
        "isr_retenido": _add_column_statement("invoices", "isr_retenido", "FLOAT", _float_default(0)),
        "ieps_trasladado": _add_column_statement("invoices", "ieps_trasladado", "FLOAT", _float_default(0)),
        "total_impuestos_trasladados": _add_column_statement(
            "invoices", "total_impuestos_trasladados", "FLOAT", _float_default(0)
        ),
        "total_impuestos_retenidos": _add_column_statement(
            "invoices", "total_impuestos_retenidos", "FLOAT", _float_default(0)
        ),
        "moneda": _add_column_statement("invoices", "moneda", "VARCHAR"),
        "moneda_original": _add_column_statement("invoices", "moneda_original", "VARCHAR"),
        "tipo_cambio_xml": _add_column_statement("invoices", "tipo_cambio_xml", "FLOAT"),
        "tipo_cambio_usado": _add_column_statement("invoices", "tipo_cambio_usado", "FLOAT"),
        "total_mxn": _add_column_statement("invoices", "total_mxn", "FLOAT"),
        "fuente_tipo_cambio": _add_column_statement("invoices", "fuente_tipo_cambio", "VARCHAR"),
        "fecha_tipo_cambio": _add_column_statement("invoices", "fecha_tipo_cambio", "VARCHAR"),
        "metodo_pago": _add_column_statement("invoices", "metodo_pago", "VARCHAR"),
        "total_pagado": _add_column_statement("invoices", "total_pagado", "FLOAT", _float_default(0)),
        "saldo_pendiente": _add_column_statement("invoices", "saldo_pendiente", "FLOAT"),
        "estado_pago": _add_column_statement("invoices", "estado_pago", "VARCHAR", "'SIN_RELACION'"),
        "score_proveedor": _add_column_statement(
            "invoices", "score_proveedor", "FLOAT", _float_default(0)
        ),
        "detalle_riesgo": _add_column_statement("invoices", "detalle_riesgo", "TEXT"),
        "sat_validado_at": _add_column_statement("invoices", "sat_validado_at", _datetime_type()),
    }

    for column_name, statement in statements.items():
        _execute_add_column_if_missing("invoices", column_name, statement)

    columns = _column_names("invoices")
    if {"iva", "iva_trasladado"}.issubset(columns):
        with engine.begin() as connection:
            connection.execute(
                text(
                    "UPDATE invoices "
                    "SET iva_trasladado = COALESCE(iva_trasladado, 0) + 0 "
                    "WHERE iva_trasladado IS NULL"
                )
            )
            connection.execute(
                text(
                    "UPDATE invoices "
                    "SET iva_trasladado = iva "
                    "WHERE COALESCE(iva_trasladado, 0) = 0 AND COALESCE(iva, 0) <> 0"
                )
            )
            if "tipo_comprobante" in columns:
                connection.execute(
                    text(
                        "UPDATE invoices "
                        "SET tipo_comprobante = 'I' "
                        "WHERE tipo_comprobante IS NULL OR tipo_comprobante = ''"
                    )
                )
            if {"estado_pago", "metodo_pago"}.issubset(columns):
                connection.execute(
                    text(
                        "UPDATE invoices "
                        "SET estado_pago = CASE "
                        "WHEN tipo_comprobante = 'P' THEN 'SIN_RELACION' "
                        "WHEN UPPER(COALESCE(metodo_pago, '')) = 'PPD' THEN 'PENDIENTE' "
                        "ELSE 'SIN_RELACION' "
                        "END "
                        "WHERE estado_pago IS NULL OR estado_pago = ''"
                    )
                )
            if "total_pagado" in columns:
                connection.execute(
                    text(
                        "UPDATE invoices "
                        "SET total_pagado = 0 "
                        "WHERE total_pagado IS NULL"
                    )
                )
            if {"saldo_pendiente", "total_original", "total"}.issubset(columns):
                connection.execute(
                    text(
                        "UPDATE invoices "
                        "SET saldo_pendiente = COALESCE(total_original, total, 0) "
                        "WHERE saldo_pendiente IS NULL AND COALESCE(tipo_comprobante, '') <> 'P'"
                    )
                )


def _ensure_bank_transaction_columns() -> None:
    if "bank_transactions" not in inspect(engine).get_table_names():
        return

    statements = {
        "origen": _add_column_statement(
            "bank_transactions",
            "origen",
            "VARCHAR",
            "'AUTOMATICO'",
        ),
    }
    for column_name, statement in statements.items():
        _execute_add_column_if_missing("bank_transactions", column_name, statement)


def _first_user_id() -> int | None:
    with engine.begin() as connection:
        row = connection.execute(
            text(
                "SELECT id FROM users "
                "ORDER BY CASE WHEN username = 'admin' THEN 0 ELSE 1 END, id ASC "
                "LIMIT 1"
            )
        ).first()
    if row is None:
        return None
    return int(row[0])


def _backfill_invoice_user_id() -> None:
    columns = _column_names("invoices")
    if "user_id" not in columns:
        return

    owner_user_id = _first_user_id()
    if owner_user_id is None:
        return

    with engine.begin() as connection:
        connection.execute(
            text("UPDATE invoices SET user_id = :user_id WHERE user_id IS NULL"),
            {"user_id": owner_user_id},
        )


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
        _ensure_bank_transaction_columns()
        _backfill_invoice_user_id()
        _ensure_invoice_user_ownership_constraints()
        _ensure_invoice_indexes()
        _initialized = True
        logger.info("Database schema ready")

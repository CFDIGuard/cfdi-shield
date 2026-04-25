from __future__ import annotations

from sqlalchemy import inspect, text
from sqlalchemy.orm import Session

from app.db.init_db import (
    _backfill_invoice_user_id,
    _ensure_invoice_indexes,
    _ensure_invoice_user_ownership_constraints,
    ensure_db_initialized,
)
from app.db.session import engine
from app.repositories.user_repository import UserRepository
from app.services.security_utils import mask_username


def get_invoice_ownership_diagnostics() -> dict[str, object]:
    ensure_db_initialized()
    inspector = inspect(engine)

    with engine.begin() as connection:
        total_invoices = int(connection.execute(text("SELECT COUNT(*) FROM invoices")).scalar_one())
        null_owner_count = int(
            connection.execute(text("SELECT COUNT(*) FROM invoices WHERE user_id IS NULL")).scalar_one()
        )
        grouped_rows = connection.execute(
            text(
                "SELECT user_id, COUNT(*) AS total "
                "FROM invoices "
                "GROUP BY user_id "
                "ORDER BY user_id"
            )
        ).fetchall()
        users_rows = connection.execute(
            text(
                "SELECT id, username "
                "FROM users "
                "ORDER BY id"
            )
        ).fetchall()

    return {
        "total_invoices": total_invoices,
        "invoices_with_null_user_id": null_owner_count,
        "invoices_by_user_id": [
            {"user_id": row[0], "total": int(row[1])}
            for row in grouped_rows
        ],
        "users": [
            {"id": row[0], "email": mask_username(row[1])}
            for row in users_rows
        ],
        "indexes": [
            {
                "name": index.get("name"),
                "unique": bool(index.get("unique")),
                "columns": index.get("column_names") or [],
            }
            for index in inspector.get_indexes("invoices")
        ],
        "unique_constraints": [
            {
                "name": constraint.get("name"),
                "columns": constraint.get("column_names") or [],
            }
            for constraint in inspector.get_unique_constraints("invoices")
        ],
        "foreign_keys": [
            {
                "name": fk.get("name"),
                "columns": fk.get("constrained_columns") or [],
                "referred_table": fk.get("referred_table"),
                "referred_columns": fk.get("referred_columns") or [],
            }
            for fk in inspector.get_foreign_keys("invoices")
        ],
    }


def assign_invoices_to_user(
    *,
    db: Session,
    email: str,
    assign_all: bool = False,
    apply_changes: bool = True,
) -> dict[str, object]:
    ensure_db_initialized()
    normalized_email = email.strip().lower()
    user = UserRepository(db).get_by_username(normalized_email)
    if user is None:
        raise ValueError(f"Usuario no encontrado: {email}")

    if assign_all:
        count = int(db.execute(text("SELECT COUNT(*) FROM invoices")).scalar_one())
        statement = text("UPDATE invoices SET user_id = :user_id")
    else:
        count = int(
            db.execute(text("SELECT COUNT(*) FROM invoices WHERE user_id IS NULL")).scalar_one()
        )
        statement = text("UPDATE invoices SET user_id = :user_id WHERE user_id IS NULL")

    if apply_changes and count > 0:
        db.execute(statement, {"user_id": user.id})
        db.commit()

    return {
        "target_user_id": user.id,
        "target_email": mask_username(user.username),
        "assign_all": assign_all,
        "affected_invoices": count,
    }


def repair_invoice_constraints() -> dict[str, object]:
    ensure_db_initialized()
    _backfill_invoice_user_id()
    _ensure_invoice_user_ownership_constraints()
    _ensure_invoice_indexes()
    return {
        "status": "ok",
        "message": "Invoice ownership and constraints repaired.",
    }

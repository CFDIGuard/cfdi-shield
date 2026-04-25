from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from sqlalchemy import inspect, text

from app.db.init_db import ensure_db_initialized
from app.db.session import engine
from app.services.security_utils import mask_username


def main() -> None:
    ensure_db_initialized()
    inspector = inspect(engine)

    with engine.begin() as connection:
        diagnostics = {
            "total_invoices": int(connection.execute(text("SELECT COUNT(*) FROM invoices")).scalar_one()),
            "invoices_with_null_user_id": int(
                connection.execute(text("SELECT COUNT(*) FROM invoices WHERE user_id IS NULL")).scalar_one()
            ),
            "invoices_by_user_id": [
                {"user_id": row[0], "total": int(row[1])}
                for row in connection.execute(
                    text(
                        "SELECT user_id, COUNT(*) AS total "
                        "FROM invoices GROUP BY user_id ORDER BY user_id"
                    )
                ).fetchall()
            ],
            "users": [
                {"id": row[0], "email": mask_username(row[1])}
                for row in connection.execute(
                    text("SELECT id, username FROM users ORDER BY id")
                ).fetchall()
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

    print("=== Invoice ownership diagnosis ===")
    print(f"total invoices: {diagnostics['total_invoices']}")
    print(f"invoices con user_id NULL: {diagnostics['invoices_with_null_user_id']}")
    print()
    print("usuarios existentes:")
    for row in diagnostics["users"]:
        print(f"  - id={row['id']} email={row['email']}")
    print()
    print("facturas agrupadas por user_id:")
    for row in diagnostics["invoices_by_user_id"]:
        print(f"  - user_id={row['user_id']} total={row['total']}")
    print()
    print("indices de invoices:")
    for index in diagnostics["indexes"]:
        print(
            f"  - name={index.get('name')} unique={index.get('unique')} columns={index.get('columns')}"
        )
    print()
    print("constraints de invoices:")
    for constraint in diagnostics["unique_constraints"]:
        print(f"  - unique name={constraint.get('name')} columns={constraint.get('columns')}")
    for fk in diagnostics["foreign_keys"]:
        print(
            f"  - foreign key name={fk.get('name')} columns={fk.get('columns')} "
            f"-> {fk.get('referred_table')}({fk.get('referred_columns')})"
        )


if __name__ == "__main__":
    main()

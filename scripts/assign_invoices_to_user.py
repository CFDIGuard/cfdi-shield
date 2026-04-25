from __future__ import annotations

import argparse
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from sqlalchemy import text

from app.db.init_db import ensure_db_initialized
from app.db.session import SessionLocal
from app.repositories.user_repository import UserRepository
from app.services.security_utils import mask_username


def _confirm(message: str) -> bool:
    answer = input(f"{message} [y/N]: ").strip().lower()
    return answer in {"y", "yes", "s", "si"}


def main() -> None:
    parser = argparse.ArgumentParser(description="Assign invoices to a user.")
    parser.add_argument("--email", required=True, help="Target user email/username")
    parser.add_argument(
        "--all",
        action="store_true",
        dest="assign_all",
        help="Assign all invoices to the target user instead of only NULL ownership invoices",
    )
    args = parser.parse_args()

    ensure_db_initialized()
    with SessionLocal() as db:
        normalized_email = args.email.strip().lower()
        user = UserRepository(db).get_by_username(normalized_email)
        if user is None:
            raise SystemExit(f"Usuario no encontrado: {args.email}")

        if args.assign_all:
            count = int(db.execute(text("SELECT COUNT(*) FROM invoices")).scalar_one())
        else:
            count = int(
                db.execute(text("SELECT COUNT(*) FROM invoices WHERE user_id IS NULL")).scalar_one()
            )

        print(
            f"Se reasignaran {count} factura(s) al usuario "
            f"{mask_username(user.username)} (id={user.id})."
        )
        if count == 0:
            print("No hay facturas por reasignar.")
            return

        if not _confirm("Confirma la operacion"):
            print("Operacion cancelada.")
            return

        if args.assign_all:
            db.execute(text("UPDATE invoices SET user_id = :user_id"), {"user_id": user.id})
        else:
            db.execute(
                text("UPDATE invoices SET user_id = :user_id WHERE user_id IS NULL"),
                {"user_id": user.id},
            )
        db.commit()
        print(
            f"Reasignacion completada correctamente. Facturas afectadas: {count}."
        )


if __name__ == "__main__":
    main()

from __future__ import annotations

import argparse
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from app.db.session import SessionLocal
from app.services.invoice_maintenance_service import assign_invoices_to_user


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

    with SessionLocal() as db:
        try:
            preview = assign_invoices_to_user(
                db=db,
                email=args.email,
                assign_all=args.assign_all,
                apply_changes=False,
            )
        except ValueError as exc:
            raise SystemExit(str(exc)) from exc

        print(
            f"Se reasignaran {preview['affected_invoices']} factura(s) al usuario "
            f"{preview['target_email']} (id={preview['target_user_id']})."
        )
        if preview["affected_invoices"] == 0:
            print("No hay facturas por reasignar.")
            return
        db.rollback()

        if not _confirm("Confirma la operacion"):
            print("Operacion cancelada.")
            return

        result = assign_invoices_to_user(
            db=db,
            email=args.email,
            assign_all=args.assign_all,
            apply_changes=True,
        )
        print(
            f"Reasignacion completada correctamente. Facturas afectadas: {result['affected_invoices']}."
        )


if __name__ == "__main__":
    main()

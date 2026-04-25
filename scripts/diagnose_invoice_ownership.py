from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from app.services.invoice_maintenance_service import get_invoice_ownership_diagnostics


def main() -> None:
    diagnostics = get_invoice_ownership_diagnostics()

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

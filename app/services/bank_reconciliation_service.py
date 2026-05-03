from __future__ import annotations

"""Temporary legacy passthrough for Bank Shield reconciliation services.

Deprecated: runtime implementation now lives in
app.modules.bank_shield.services.reconciliation_service.
"""

from app.modules.bank_shield.services.reconciliation_service import (
    ParsedBankTransaction,
    process_bank_statement_upload,
    reconcile_transactions,
    get_reconciliation_rows,
    get_reconciliation_summary,
)

__all__ = [
    "ParsedBankTransaction",
    "process_bank_statement_upload",
    "reconcile_transactions",
    "get_reconciliation_rows",
    "get_reconciliation_summary",
]

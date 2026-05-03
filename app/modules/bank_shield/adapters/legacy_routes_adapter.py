"""Compatibility adapter between legacy shared imports and Bank Shield.

This module keeps transition points explicit while runtime logic is migrated
incrementally into the internal Bank Shield module.
"""

from sqlalchemy.orm import Session

from app.modules.bank_shield.services.statement_parser import (
    ParsedBankTransaction,
    parse_bank_statement as _parse_bank_statement,
)
from app.modules.bank_shield.services.reconciliation_service import (
    get_reconciliation_rows as _get_reconciliation_rows,
    get_reconciliation_summary as _get_reconciliation_summary,
    process_bank_statement_upload as _process_bank_statement_upload,
    reconcile_transactions as _reconcile_transactions,
)
from app.models.invoice import Invoice
from app.schemas.bank_reconciliation import BankReconciliationFilters


def parse_bank_statement(file_bytes: bytes, filename: str) -> list[ParsedBankTransaction]:
    """Delegate bank statement parsing to the module implementation."""
    return _parse_bank_statement(file_bytes, filename)


def reconcile_transactions(
    parsed_transactions: list[ParsedBankTransaction],
    invoices: list[Invoice],
) -> list[dict[str, object]]:
    """Delegate reconciliation matching to the module implementation."""
    return _reconcile_transactions(parsed_transactions, invoices)


def process_bank_statement_upload(
    *,
    db: Session,
    user_id: int,
    file_bytes: bytes,
    filename: str,
) -> dict[str, int]:
    """Delegate bank statement upload processing to the module implementation."""
    return _process_bank_statement_upload(
        db=db,
        user_id=user_id,
        file_bytes=file_bytes,
        filename=filename,
    )


def get_reconciliation_rows(
    db: Session,
    user_id: int,
    limit: int = 150,
    filters: BankReconciliationFilters | None = None,
) -> list[dict[str, object]]:
    """Delegate reconciliation row assembly to the module implementation."""
    return _get_reconciliation_rows(
        db=db,
        user_id=user_id,
        limit=limit,
        filters=filters,
    )


def get_reconciliation_summary(
    db: Session,
    user_id: int,
    filters: BankReconciliationFilters | None = None,
) -> dict[str, int]:
    """Delegate reconciliation summary generation to the module implementation."""
    return _get_reconciliation_summary(
        db=db,
        user_id=user_id,
        filters=filters,
    )

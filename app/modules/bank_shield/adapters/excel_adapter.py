"""Compatibility adapter between Bank Shield data and the shared Excel export pipeline."""

from __future__ import annotations

from sqlalchemy.orm import Session

from app.modules.bank_shield.services.reconciliation_service import get_reconciliation_rows
from app.schemas.bank_reconciliation import BankReconciliationFilters


def build_reconciliation_export_rows(
    db: Session,
    user_id: int,
    filters: BankReconciliationFilters | None = None,
    limit: int = 500,
) -> list[dict[str, object]]:
    """Build reconciliation rows for Excel export without changing the shared workbook contract."""

    return get_reconciliation_rows(
        db,
        user_id,
        limit=limit,
        filters=filters,
    )

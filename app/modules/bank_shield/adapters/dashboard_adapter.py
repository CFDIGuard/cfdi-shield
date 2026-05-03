"""Compatibility adapter between Bank Shield reconciliation data and the shared dashboard layer."""

from __future__ import annotations

from sqlalchemy.orm import Session

from app.modules.bank_shield.services.reconciliation_service import (
    get_reconciliation_rows,
    get_reconciliation_summary,
)
from app.schemas.bank_reconciliation import BankReconciliationFilters


def build_reconciliation_dashboard_payload(
    db: Session,
    user_id: int,
    filters: BankReconciliationFilters | None = None,
) -> dict[str, object]:
    """Build the reconciliation payload consumed by the current web dashboard layer."""

    summary = get_reconciliation_summary(db, user_id, filters=filters)
    rows = get_reconciliation_rows(db, user_id, limit=150, filters=filters)
    return {
        "summary": summary,
        "rows": rows,
    }

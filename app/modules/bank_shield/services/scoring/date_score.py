from __future__ import annotations

from datetime import datetime

from app.core.config import settings


def _extract_date(value: str | None) -> datetime | None:
    if not value:
        return None
    try:
        return datetime.fromisoformat(value[:10])
    except ValueError:
        return None


def _date_match_score(transaction_date: str | None, invoice_date: str | None) -> tuple[int, str | None]:
    tx_date = _extract_date(transaction_date)
    inv_date = _extract_date(invoice_date)
    if tx_date is None or inv_date is None:
        return 0, None
    days_diff = abs((tx_date.date() - inv_date.date()).days)
    if days_diff <= settings.bank_reconciliation_date_window_days:
        return 20, f"Fecha dentro de {days_diff} dias"
    return 0, None

"""Compatibility adapter for asynchronous invoice search in Bank Shield."""

from __future__ import annotations

from sqlalchemy.orm import Session

from app.repositories.invoice_repository import InvoiceRepository


def _invoice_search_option(invoice) -> dict[str, object]:
    total_mxn = invoice.total_mxn if invoice.total_mxn is not None else (invoice.total_original or invoice.total or 0)
    return {
        "id": invoice.id,
        "label": f"{invoice.uuid} | {invoice.razon_social or '-'} | ${float(total_mxn or 0):,.2f}",
    }


def build_invoice_search_results(
    db: Session,
    user_id: int,
    query: str,
    limit: int = 20,
) -> list[dict[str, object]]:
    repository = InvoiceRepository(db, user_id=user_id)
    return [
        _invoice_search_option(invoice)
        for invoice in repository.search_for_reconciliation(query, limit=limit)
    ]

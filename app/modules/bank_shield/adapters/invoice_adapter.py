"""Compatibility adapter between Bank Shield and the shared invoice / CFDI layer."""

from __future__ import annotations

from sqlalchemy.orm import Session

from app.repositories.invoice_repository import InvoiceRepository


def _invoice_option(invoice) -> dict[str, object]:
    total_mxn = invoice.total_mxn if invoice.total_mxn is not None else (invoice.total_original or invoice.total or 0)
    return {
        "id": invoice.id,
        "label": f"{invoice.uuid} | {invoice.razon_social or '-'} | ${float(total_mxn or 0):,.2f}",
    }

def build_invoice_options(
    db: Session,
    user_id: int,
    limit: int | None = None,
) -> list[dict[str, object]]:
    """Build invoice options for reconciliation without changing the current dropdown contract."""

    repository = InvoiceRepository(db, user_id=user_id)
    invoices = repository.list_all()
    if limit is not None:
        invoices = invoices[:limit]
    return [_invoice_option(invoice) for invoice in invoices]

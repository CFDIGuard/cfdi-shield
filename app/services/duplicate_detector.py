from __future__ import annotations

from app.repositories.invoice_repository import InvoiceRepository
from app.schemas.invoice import InvoiceProcessedData


def has_duplicate_uuid(repository: InvoiceRepository, uuid: str) -> bool:
    return repository.get_by_uuid(uuid) is not None


def has_same_rfc_total(repository: InvoiceRepository, invoice: InvoiceProcessedData) -> bool:
    if not invoice.rfc_emisor:
        return False
    return repository.exists_same_rfc_total(invoice.rfc_emisor, invoice.total)

from __future__ import annotations

"""Minimal Bank Shield wrapper for invoice reads used by reconciliation."""

from sqlalchemy.orm import Session

from app.models.invoice import Invoice
from app.repositories.invoice_repository import InvoiceRepository


class InvoiceLookupRepository:
    def __init__(self, db: Session, user_id: int):
        self._repository = InvoiceRepository(db, user_id=user_id)

    def list_all_for_matching(self) -> list[Invoice]:
        return self._repository.list_all()

    def list_by_ids_for_reconciliation(self, invoice_ids: list[int]) -> list[Invoice]:
        return self._repository.list_by_ids(invoice_ids)

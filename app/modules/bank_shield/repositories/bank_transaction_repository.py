from __future__ import annotations

"""Bank Shield v0.1 bank transaction repository.

Current implementation is migrated into the Bank Shield module while legacy
imports remain supported through temporary passthrough adapters.
"""

from sqlalchemy import String, cast, func, or_, select
from sqlalchemy.orm import Session

from app.models.bank_transaction import BankTransaction
from app.models.invoice import Invoice
from app.repositories.scope_utils import apply_owner_scope, resolve_user_organization_id
from app.schemas.bank_reconciliation import BankReconciliationFilters


class BankTransactionRepository:
    def __init__(self, db: Session, user_id: int | None = None, organization_id: int | None = None):
        self.db = db
        self.user_id = user_id
        self.organization_id = organization_id if organization_id is not None else resolve_user_organization_id(db, user_id)

    def _scope_statement(self, statement):
        return apply_owner_scope(
            statement,
            BankTransaction,
            user_id=self.user_id,
            organization_id=self.organization_id,
        )

    def _apply_filters(self, statement, filters: BankReconciliationFilters | None):
        if filters is None:
            return statement

        cleaned = filters.cleaned()
        if not cleaned:
            return statement

        if cleaned.get("estado"):
            statement = statement.where(
                func.upper(func.coalesce(BankTransaction.match_status, "")) == cleaned["estado"].upper()
            )
        if cleaned.get("origen"):
            statement = statement.where(
                func.upper(func.coalesce(BankTransaction.origen, "")) == cleaned["origen"].upper()
            )
        if cleaned.get("busqueda"):
            needle = f"%{cleaned['busqueda'].upper()}%"
            statement = statement.outerjoin(Invoice, BankTransaction.matched_invoice_id == Invoice.id).where(
                or_(
                    func.upper(func.coalesce(cast(BankTransaction.descripcion, String), "")).like(needle),
                    func.upper(func.coalesce(BankTransaction.referencia, "")).like(needle),
                    func.upper(func.coalesce(cast(Invoice.razon_social, String), "")).like(needle),
                    func.upper(func.coalesce(Invoice.uuid, "")).like(needle),
                )
            )
        return statement

    def get_by_raw_hash(self, raw_hash: str) -> BankTransaction | None:
        statement = self._scope_statement(select(BankTransaction)).where(BankTransaction.raw_hash == raw_hash)
        return self.db.execute(statement).scalar_one_or_none()

    def get_by_id(self, transaction_id: int) -> BankTransaction | None:
        statement = self._scope_statement(select(BankTransaction)).where(BankTransaction.id == transaction_id)
        return self.db.execute(statement).scalar_one_or_none()

    def upsert(self, payload: dict[str, object]) -> BankTransaction:
        raw_hash = str(payload["raw_hash"])
        existing = self.get_by_raw_hash(raw_hash)
        if existing is None:
            if self.user_id is not None:
                payload["user_id"] = self.user_id
            if self.organization_id is not None:
                payload["organization_id"] = self.organization_id
            existing = BankTransaction(**payload)
            self.db.add(existing)
        else:
            for key, value in payload.items():
                setattr(existing, key, value)
            if self.user_id is not None:
                existing.user_id = self.user_id
            if self.organization_id is not None:
                existing.organization_id = self.organization_id
        self.db.flush()
        return existing

    def list_recent(self, limit: int = 150, filters: BankReconciliationFilters | None = None) -> list[BankTransaction]:
        statement = self._scope_statement(select(BankTransaction))
        statement = self._apply_filters(statement, filters)
        statement = statement.order_by(
            BankTransaction.created_at.desc(),
            BankTransaction.id.desc(),
        ).limit(limit)
        return list(self.db.execute(statement).scalars().all())

    def list_all(self, filters: BankReconciliationFilters | None = None) -> list[BankTransaction]:
        statement = self._scope_statement(select(BankTransaction))
        statement = self._apply_filters(statement, filters)
        statement = statement.order_by(
            BankTransaction.created_at.desc(),
            BankTransaction.id.desc(),
        )
        return list(self.db.execute(statement).scalars().all())

    def summary(self, filters: BankReconciliationFilters | None = None) -> dict[str, int]:
        rows = self.list_all(filters=filters)
        counts: dict[str, int] = {}
        for row in rows:
            status = str(row.match_status or "PENDIENTE").upper()
            counts[status] = counts.get(status, 0) + 1
        conciliados = counts.get("CONCILIADO", 0)
        posibles = counts.get("POSIBLE", 0)
        pendientes = counts.get("PENDIENTE", 0)
        return {
            "total_movimientos": conciliados + posibles + pendientes,
            "conciliados": conciliados,
            "posibles": posibles,
            "pendientes": pendientes,
        }

    def save(self, transaction: BankTransaction) -> BankTransaction:
        self.db.add(transaction)
        self.db.commit()
        self.db.refresh(transaction)
        return transaction

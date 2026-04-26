from __future__ import annotations

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.models.bank_transaction import BankTransaction


class BankTransactionRepository:
    def __init__(self, db: Session, user_id: int | None = None):
        self.db = db
        self.user_id = user_id

    def _scope_statement(self, statement):
        if self.user_id is None:
            return statement
        return statement.where(BankTransaction.user_id == self.user_id)

    def get_by_raw_hash(self, raw_hash: str) -> BankTransaction | None:
        statement = self._scope_statement(select(BankTransaction)).where(BankTransaction.raw_hash == raw_hash)
        return self.db.execute(statement).scalar_one_or_none()

    def upsert(self, payload: dict[str, object]) -> BankTransaction:
        raw_hash = str(payload["raw_hash"])
        existing = self.get_by_raw_hash(raw_hash)
        if existing is None:
            if self.user_id is not None:
                payload["user_id"] = self.user_id
            existing = BankTransaction(**payload)
            self.db.add(existing)
        else:
            for key, value in payload.items():
                setattr(existing, key, value)
            if self.user_id is not None:
                existing.user_id = self.user_id
        self.db.flush()
        return existing

    def list_recent(self, limit: int = 150) -> list[BankTransaction]:
        statement = self._scope_statement(select(BankTransaction)).order_by(
            BankTransaction.created_at.desc(),
            BankTransaction.id.desc(),
        ).limit(limit)
        return list(self.db.execute(statement).scalars().all())

    def list_all(self) -> list[BankTransaction]:
        statement = self._scope_statement(select(BankTransaction)).order_by(
            BankTransaction.created_at.desc(),
            BankTransaction.id.desc(),
        )
        return list(self.db.execute(statement).scalars().all())

    def summary(self) -> dict[str, int]:
        rows = self.db.execute(
            self._scope_statement(
                select(BankTransaction.match_status, func.count(BankTransaction.id)).group_by(BankTransaction.match_status)
            )
        ).all()
        counts = {str(status or "PENDIENTE").upper(): int(total or 0) for status, total in rows}
        conciliados = counts.get("CONCILIADO", 0)
        posibles = counts.get("POSIBLE", 0)
        pendientes = counts.get("PENDIENTE", 0)
        return {
            "total_movimientos": conciliados + posibles + pendientes,
            "conciliados": conciliados,
            "posibles": posibles,
            "pendientes": pendientes,
        }

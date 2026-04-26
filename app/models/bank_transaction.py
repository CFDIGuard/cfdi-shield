from datetime import datetime, timezone

from sqlalchemy import DateTime, Float, ForeignKey, Index, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


class BankTransaction(Base):
    __tablename__ = "bank_transactions"
    __table_args__ = (
        Index("ix_bank_transactions_user_raw_hash_unique", "user_id", "raw_hash", unique=True),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), index=True, nullable=False)
    organization_id: Mapped[int | None] = mapped_column(ForeignKey("organizations.id"), index=True, nullable=True)
    fecha: Mapped[str | None] = mapped_column(String, index=True, default=None)
    descripcion: Mapped[str | None] = mapped_column(Text, default=None)
    referencia: Mapped[str | None] = mapped_column(String, default=None)
    cargo: Mapped[float] = mapped_column(Float, default=0)
    abono: Mapped[float] = mapped_column(Float, default=0)
    monto: Mapped[float] = mapped_column(Float, default=0)
    tipo_movimiento: Mapped[str | None] = mapped_column(String, default=None)
    moneda: Mapped[str | None] = mapped_column(String, default="MXN")
    raw_hash: Mapped[str] = mapped_column(String, index=True, nullable=False)
    matched_invoice_id: Mapped[int | None] = mapped_column(ForeignKey("invoices.id"), index=True, default=None)
    origen: Mapped[str] = mapped_column(String, default="AUTOMATICO")
    match_status: Mapped[str] = mapped_column(String, default="PENDIENTE")
    match_score: Mapped[float] = mapped_column(Float, default=0)
    match_reason: Mapped[str | None] = mapped_column(Text, default=None)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=lambda: datetime.now(timezone.utc))

from datetime import datetime, timezone

from sqlalchemy import DateTime, Float, ForeignKey, Index, Integer, String
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


class PaymentComplement(Base):
    __tablename__ = "payment_complements"
    __table_args__ = (
        Index("ix_payment_complements_user_related_uuid", "user_id", "related_invoice_uuid"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), index=True, nullable=False)
    organization_id: Mapped[int | None] = mapped_column(ForeignKey("organizations.id"), index=True, nullable=True)
    payment_invoice_id: Mapped[int] = mapped_column(ForeignKey("invoices.id"), index=True, nullable=False)
    related_invoice_uuid: Mapped[str | None] = mapped_column(String, index=True, default=None)
    fecha_pago: Mapped[str | None] = mapped_column(String, default=None)
    moneda_pago: Mapped[str | None] = mapped_column(String, default=None)
    tipo_cambio_pago: Mapped[float | None] = mapped_column(Float, default=None)
    monto_pago: Mapped[float] = mapped_column(Float, default=0)
    parcialidad: Mapped[int | None] = mapped_column(Integer, default=None)
    saldo_anterior: Mapped[float] = mapped_column(Float, default=0)
    importe_pagado: Mapped[float] = mapped_column(Float, default=0)
    saldo_insoluto: Mapped[float] = mapped_column(Float, default=0)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=lambda: datetime.now(timezone.utc))

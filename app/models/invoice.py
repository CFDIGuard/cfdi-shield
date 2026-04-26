from datetime import datetime, timezone

from sqlalchemy import DateTime, Float, ForeignKey, Index, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


class Invoice(Base):
    __tablename__ = "invoices"
    __table_args__ = (
        Index("ix_invoices_user_uuid_unique", "user_id", "uuid", unique=True),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), index=True, nullable=False)
    organization_id: Mapped[int | None] = mapped_column(ForeignKey("organizations.id"), index=True, nullable=True)
    uuid: Mapped[str] = mapped_column(String, index=True, nullable=False)
    archivo: Mapped[str | None] = mapped_column(String, default=None)
    tipo_comprobante: Mapped[str | None] = mapped_column(String, default=None)
    razon_social: Mapped[str | None] = mapped_column(String, default=None)
    rfc_emisor: Mapped[str | None] = mapped_column(String, index=True)
    rfc_receptor: Mapped[str | None] = mapped_column(String, index=True)
    folio: Mapped[str | None] = mapped_column(String, default=None)
    fecha_emision: Mapped[str | None] = mapped_column(String, index=True)
    mes: Mapped[str | None] = mapped_column(String, index=True)
    subtotal: Mapped[float] = mapped_column(Float, default=0)
    descuento: Mapped[float] = mapped_column(Float, default=0)
    total: Mapped[float] = mapped_column(Float, default=0)
    total_original: Mapped[float] = mapped_column(Float, default=0)
    iva: Mapped[float] = mapped_column(Float, default=0)
    iva_trasladado: Mapped[float] = mapped_column(Float, default=0)
    iva_retenido: Mapped[float] = mapped_column(Float, default=0)
    isr_retenido: Mapped[float] = mapped_column(Float, default=0)
    ieps_trasladado: Mapped[float] = mapped_column(Float, default=0)
    total_impuestos_trasladados: Mapped[float] = mapped_column(Float, default=0)
    total_impuestos_retenidos: Mapped[float] = mapped_column(Float, default=0)
    moneda: Mapped[str | None] = mapped_column(String, default=None)
    moneda_original: Mapped[str | None] = mapped_column(String, default=None)
    tipo_cambio_xml: Mapped[float | None] = mapped_column(Float, default=None)
    tipo_cambio_usado: Mapped[float | None] = mapped_column(Float, default=None)
    total_mxn: Mapped[float | None] = mapped_column(Float, default=None)
    fuente_tipo_cambio: Mapped[str | None] = mapped_column(String, default=None)
    fecha_tipo_cambio: Mapped[str | None] = mapped_column(String, default=None)
    metodo_pago: Mapped[str | None] = mapped_column(String, default=None)
    total_pagado: Mapped[float] = mapped_column(Float, default=0)
    saldo_pendiente: Mapped[float | None] = mapped_column(Float, default=None)
    estado_pago: Mapped[str] = mapped_column(String, default="SIN_RELACION")
    estatus_sat: Mapped[str] = mapped_column(String, default="ERROR")
    riesgo: Mapped[str] = mapped_column(String, default="BAJO")
    score_proveedor: Mapped[float] = mapped_column(Float, default=0)
    detalle_riesgo: Mapped[str | None] = mapped_column(Text, default=None)
    sat_validado_at: Mapped[datetime | None] = mapped_column(DateTime, default=None)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=lambda: datetime.now(timezone.utc))

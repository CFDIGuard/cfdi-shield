from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field


class PaymentComplementBase(BaseModel):
    related_invoice_uuid: str | None = None
    fecha_pago: str | None = None
    moneda_pago: str | None = None
    tipo_cambio_pago: float | None = None
    monto_pago: float = 0
    parcialidad: int | None = None
    saldo_anterior: float = 0
    importe_pagado: float = 0
    saldo_insoluto: float = 0


class PaymentComplementCreate(PaymentComplementBase):
    user_id: int
    payment_invoice_id: int


class PaymentComplementResponse(PaymentComplementBase):
    id: int
    user_id: int
    payment_invoice_id: int
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)


class PaymentComplementProcessedData(PaymentComplementBase):
    serie: str | None = None
    folio: str | None = None
    moneda_documento_relacionado: str | None = None
    objeto_impuesto_dr: str | None = None
    impuestos_dr_trasladados: float = 0
    impuestos_dr_retenidos: float = 0


class PaymentComplementReportRow(BaseModel):
    uuid_complemento: str
    uuid_factura_relacionada: str | None = None
    fecha_pago: str | None = None
    monto_pago: float = 0
    moneda_pago: str | None = None
    parcialidad: int | None = None
    saldo_anterior: float = 0
    importe_pagado: float = 0
    saldo_insoluto: float = 0
    estado_relacion: str = Field(default="PENDIENTE")

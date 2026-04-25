from datetime import datetime

from pydantic import BaseModel, ConfigDict


class InvoiceBase(BaseModel):
    uuid: str
    archivo: str | None = None
    razon_social: str | None = None
    rfc_emisor: str | None = None
    rfc_receptor: str | None = None
    folio: str | None = None
    fecha_emision: str | None = None
    mes: str | None = None
    subtotal: float = 0
    total: float = 0
    total_original: float = 0
    iva: float = 0
    iva_retenido: float = 0
    isr_retenido: float = 0
    moneda: str | None = None
    moneda_original: str | None = None
    tipo_cambio_xml: float | None = None
    tipo_cambio_usado: float | None = None
    total_mxn: float | None = None
    fuente_tipo_cambio: str | None = None
    fecha_tipo_cambio: str | None = None
    metodo_pago: str | None = None
    estatus_sat: str = "ERROR"
    riesgo: str = "BAJO"
    score_proveedor: float = 0
    detalle_riesgo: str | None = None
    sat_validado_at: datetime | None = None


class InvoiceCreate(InvoiceBase):
    user_id: int


class InvoiceResponse(InvoiceBase):
    id: int
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)


class InvoiceUploadResponse(BaseModel):
    status: str
    data: InvoiceResponse


class InvoiceProcessedData(InvoiceBase):
    pass


class InvoiceFilters(BaseModel):
    rfc_receptor: str | None = None
    rfc_emisor: str | None = None
    proveedor: str | None = None
    estatus_sat: str | None = None
    riesgo: str | None = None
    moneda: str | None = None
    fecha_desde: str | None = None
    fecha_hasta: str | None = None

    def cleaned(self) -> dict[str, str]:
        return {
            key: str(value).strip()
            for key, value in self.model_dump().items()
            if value not in (None, "")
            and str(value).strip()
        }

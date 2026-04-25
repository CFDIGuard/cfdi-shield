from pydantic import BaseModel


class ProviderSummary(BaseModel):
    rfc_emisor: str
    razon_social: str
    facturas: int
    total_facturado: float
    canceladas: int
    porcentaje_canceladas: float
    iva_total: float
    score_riesgo: float
    nivel_riesgo: str


class RiskSummary(BaseModel):
    uuid: str
    rfc_emisor: str
    razon_social: str
    total: float
    estatus_sat: str
    riesgo: str
    detalle_riesgo: str | None = None
    fecha_emision: str | None = None
    mes: str | None = None


class MonthlySummary(BaseModel):
    mes: str
    facturas: int
    subtotal: float
    iva_trasladado: float
    iva_retenido: float
    isr_retenido: float
    total: float
    vigentes: int
    canceladas: int
    porcentaje_canceladas: float


class ControlRow(BaseModel):
    uuid: str
    archivo: str | None = None
    rfc_emisor: str | None = None
    razon_social: str | None = None
    rfc_receptor: str | None = None
    folio: str | None = None
    fecha_emision: str | None = None
    mes: str | None = None
    subtotal: float
    iva: float
    iva_retenido: float
    isr_retenido: float
    total: float
    moneda: str | None = None
    metodo_pago: str | None = None
    estatus_sat: str
    riesgo: str
    detalle_riesgo: str | None = None
    sat_validado_at: str | None = None
    created_at: str | None = None


class DashboardSummary(BaseModel):
    total_facturado: float
    facturas: int
    vigentes: int
    canceladas: int
    sin_validacion_sat: int
    total_iva: float
    proveedores_unicos: int
    riesgos_altos: int
    riesgo_alto: int
    riesgo_medio: int
    riesgo_bajo: int
    top_proveedores: list[ProviderSummary]
    riesgos: list[RiskSummary]


class ReportsBundle(BaseModel):
    resumen: list[MonthlySummary]
    control: list[ControlRow]
    proveedores: list[ProviderSummary]
    riesgos: list[RiskSummary]

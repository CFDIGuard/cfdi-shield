from pydantic import BaseModel

from app.schemas.payment_complement import PaymentComplementReportRow


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
    total_original: float
    total_mxn: float | None = None
    moneda_original: str
    estatus_sat: str
    riesgo: str
    detalle_riesgo: str | None = None
    fecha_emision: str | None = None
    mes: str | None = None


class FiscalRiskInvoiceRow(BaseModel):
    uuid: str
    rfc_emisor: str
    proveedor: str
    fecha: str | None = None
    moneda: str
    total_original: float
    total_mxn: float | None = None
    estatus_sat: str
    riesgo: str
    motivo: str


class FiscalRiskSupplierRow(BaseModel):
    rfc_emisor: str
    proveedor: str
    facturas: int
    total_mxn: float
    canceladas: int
    porcentaje_canceladas: float
    score_riesgo: float
    monedas_usadas: str
    operaciones_repetidas: int
    riesgo_acumulado: str
    motivo: str
    flag_requiere_contrato: bool


class FiscalRiskMetricRow(BaseModel):
    indicador: str
    valor: int
    detalle: str


class AlertActionRow(BaseModel):
    titulo: str
    valor: int
    nivel: str
    motivo: str
    accion_sugerida: str


class MonthlySummary(BaseModel):
    mes: str
    facturas: int
    subtotal: float
    descuento: float
    iva_trasladado: float
    iva_retenido: float
    isr_retenido: float
    ieps_trasladado: float
    total_impuestos_trasladados: float
    total_impuestos_retenidos: float
    total: float
    total_mxn: float
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
    descuento: float
    iva: float
    iva_trasladado: float
    iva_retenido: float
    isr_retenido: float
    ieps_trasladado: float
    total_impuestos_trasladados: float
    total_impuestos_retenidos: float
    total: float
    moneda: str | None = None
    moneda_original: str | None = None
    total_original: float
    tipo_cambio_usado: float | None = None
    fuente_tipo_cambio: str | None = None
    fecha_tipo_cambio: str | None = None
    total_mxn: float | None = None
    metodo_pago: str | None = None
    total_pagado: float = 0
    saldo_pendiente: float = 0
    estado_pago: str | None = None
    estatus_sat: str
    riesgo: str
    score_riesgo: float = 0
    nivel_riesgo: str | None = None
    detalle_riesgo: str | None = None
    accion_sugerida: str | None = None
    sat_validado_at: str | None = None
    created_at: str | None = None


class DashboardSummary(BaseModel):
    total_facturado: float
    facturas: int
    vigentes: int
    canceladas: int
    sin_validacion_sat: int
    total_iva: float
    total_iva_trasladado: float
    total_iva_retenido: float
    total_isr_retenido: float
    total_impuestos_netos: float
    proveedores_unicos: int
    riesgos_altos: int
    riesgo_alto: int
    riesgo_medio: int
    riesgo_bajo: int
    top_proveedores: list[ProviderSummary]
    riesgos: list[RiskSummary]
    alertas_cfdi_count: int = 0
    analisis_proveedor_count: int = 0
    rr1_count: int = 0
    rr9_count: int = 0
    facturas_pagadas: int = 0
    facturas_parciales: int = 0
    facturas_pendientes: int = 0
    complementos_sin_factura_relacionada: int = 0
    facturas_sin_complemento_pago: int = 0
    transacciones_bancarias_sin_conciliar: int = 0
    analisis_proveedor_alertas: list[FiscalRiskSupplierRow] = []
    rr9_alertas: list[FiscalRiskSupplierRow] = []
    indicadores_riesgo: list[AlertActionRow] = []
    oportunidades_fiscales: list[AlertActionRow] = []


class ReportsBundle(BaseModel):
    resumen: list[MonthlySummary]
    control: list[ControlRow]
    proveedores: list[ProviderSummary]
    riesgos: list[RiskSummary]
    alertas_cfdi: list[FiscalRiskInvoiceRow] = []
    analisis_proveedor: list[FiscalRiskSupplierRow] = []
    rr1: list[FiscalRiskInvoiceRow] = []
    rr9: list[FiscalRiskSupplierRow] = []
    resumen_riesgos: list[FiscalRiskMetricRow] = []
    complementos_pago: list[PaymentComplementReportRow] = []

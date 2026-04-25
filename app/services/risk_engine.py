from __future__ import annotations

from app.schemas.invoice import InvoiceProcessedData


RISK_LEVEL_BY_TYPE = {
    "PROVEEDOR_CANCELACIONES_ALTAS": "ALTO",
    "DUPLICADO_UUID_CONFIRMADO": "ALTO",
    "POTENCIAL_DUPLICADO_RFC_MONTO": "MEDIO",
    "IVA_INCONSISTENTE": "ALTO",
    "FACTURA_ALTA_PROVEEDOR_NUEVO": "MEDIO",
    "FACTURA_CANCELADA_SAT": "MEDIO",
}
RISK_SCORE_BY_TYPE = {
    "PROVEEDOR_CANCELACIONES_ALTAS": 35,
    "DUPLICADO_UUID_CONFIRMADO": 80,
    "POTENCIAL_DUPLICADO_RFC_MONTO": 10,
    "IVA_INCONSISTENTE": 40,
    "FACTURA_ALTA_PROVEEDOR_NUEVO": 15,
    "FACTURA_CANCELADA_SAT": 15,
}


def has_provider_high_cancellation_risk(
    cancelled_count: int,
    invoice_count: int,
) -> bool:
    if cancelled_count >= 5:
        return True
    if invoice_count <= 0:
        return False
    return cancelled_count >= 3 and (cancelled_count / invoice_count) > 0.30


def detect_invoice_risk_types(
    invoice: InvoiceProcessedData,
    estatus_sat: str,
    provider_invoice_count: int = 0,
    provider_cancelled_count: int = 0,
    has_same_rfc_total: bool = False,
    high_amount_threshold: float = 100000.0,
) -> list[str]:
    risk_types: list[str] = []

    normalized_sat = str(estatus_sat or "").strip().upper()
    if normalized_sat == "CANCELADO":
        risk_types.append("FACTURA_CANCELADA_SAT")

    if has_provider_high_cancellation_risk(
        cancelled_count=provider_cancelled_count,
        invoice_count=provider_invoice_count,
    ):
        risk_types.append("PROVEEDOR_CANCELACIONES_ALTAS")

    if has_same_rfc_total:
        risk_types.append("POTENCIAL_DUPLICADO_RFC_MONTO")

    if invoice.subtotal <= 0 and invoice.iva > 0:
        risk_types.append("IVA_INCONSISTENTE")
    elif invoice.subtotal > 0 and invoice.iva > 0:
        ratio = invoice.iva / invoice.subtotal
        if not any(abs(ratio - expected) <= 0.015 for expected in (0.16, 0.08, 0.0)):
            risk_types.append("IVA_INCONSISTENTE")

    if invoice.iva > invoice.total:
        risk_types.append("IVA_INCONSISTENTE")

    if provider_invoice_count <= 2 and invoice.total >= max(high_amount_threshold, 100000.0):
        risk_types.append("FACTURA_ALTA_PROVEEDOR_NUEVO")

    return sorted(set(risk_types))


def build_risk_detail(risk_types: list[str]) -> str | None:
    details = {
        "FACTURA_CANCELADA_SAT": "CFDI cancelado, revisar sustitucion o motivo.",
        "PROVEEDOR_CANCELACIONES_ALTAS": "Proveedor con volumen alto de cancelaciones frente a su historial.",
        "DUPLICADO_UUID_CONFIRMADO": "UUID duplicado confirmado; revisar intento de carga o control documental.",
        "POTENCIAL_DUPLICADO_RFC_MONTO": "Posible duplicado por mismo RFC emisor y mismo monto.",
        "IVA_INCONSISTENTE": "IVA inconsistente frente a la estructura esperada del CFDI.",
        "FACTURA_ALTA_PROVEEDOR_NUEVO": "Proveedor nuevo con monto alto frente al historico.",
    }
    messages = [details[risk_type] for risk_type in risk_types if risk_type in details]
    return " ".join(messages) if messages else None


def calculate_risk_score(risk_types: list[str]) -> float:
    return float(min(100, sum(RISK_SCORE_BY_TYPE.get(risk_type, 0) for risk_type in risk_types)))


def calculate_risk_level(risk_types: list[str], estatus_sat: str, total: float) -> str:
    normalized_sat = str(estatus_sat or "").strip().upper()

    if any(
        risk_type in risk_types
        for risk_type in ("DUPLICADO_UUID_CONFIRMADO", "IVA_INCONSISTENTE", "PROVEEDOR_CANCELACIONES_ALTAS")
    ):
        return "ALTO"

    if any(
        risk_type in risk_types
        for risk_type in ("FACTURA_CANCELADA_SAT", "POTENCIAL_DUPLICADO_RFC_MONTO", "FACTURA_ALTA_PROVEEDOR_NUEVO")
    ):
        return "MEDIO"

    if risk_types:
        return "MEDIO"

    if normalized_sat in {"SIN_VALIDACION", "VIGENTE", "NO_ENCONTRADO", "ERROR", ""} and total >= 0:
        return "BAJO"

    return "BAJO"


def calcular_riesgo(estatus_sat: str, total: float) -> str:
    normalized_sat = str(estatus_sat or "").strip().upper()
    if normalized_sat == "CANCELADO":
        return "MEDIO"
    if normalized_sat == "SIN_VALIDACION":
        return "BAJO"
    return "BAJO"

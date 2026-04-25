from __future__ import annotations

from collections import Counter

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
    iva_trasladado = float(getattr(invoice, "iva_trasladado", None) or getattr(invoice, "iva", 0) or 0)

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

    if invoice.subtotal <= 0 and iva_trasladado > 0:
        risk_types.append("IVA_INCONSISTENTE")
    elif invoice.subtotal > 0 and iva_trasladado > 0:
        ratio = iva_trasladado / invoice.subtotal
        if not any(abs(ratio - expected) <= 0.015 for expected in (0.16, 0.08, 0.0)):
            risk_types.append("IVA_INCONSISTENTE")

    if iva_trasladado > invoice.total:
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


def _rr9_currency(invoice) -> str:
    return str(getattr(invoice, "moneda_original", None) or getattr(invoice, "moneda", None) or "MXN").upper()


def _rr9_total_original(invoice) -> float:
    return float(getattr(invoice, "total_original", None) or getattr(invoice, "total", None) or 0)


def _rr9_total_mxn(invoice) -> float | None:
    total_mxn = getattr(invoice, "total_mxn", None)
    if total_mxn is not None:
        return float(total_mxn)
    if _rr9_currency(invoice) == "MXN":
        return _rr9_total_original(invoice)
    return None


def _rr9_level_from_score(score: float) -> str:
    if score >= 70:
        return "HIGH"
    if score >= 35:
        return "MEDIUM"
    return "LOW"


def calculate_rr9_score(invoices_by_supplier: dict[str, list[object]]) -> dict[str, dict[str, object]]:
    all_totals_mxn = [
        amount
        for supplier_invoices in invoices_by_supplier.values()
        for invoice in supplier_invoices
        if (amount := _rr9_total_mxn(invoice)) is not None and amount > 0
    ]
    overall_total_mxn = float(sum(all_totals_mxn))
    avg_invoice_total_mxn = float(sum(all_totals_mxn) / len(all_totals_mxn)) if all_totals_mxn else 0.0

    results: dict[str, dict[str, object]] = {}

    for rfc_emisor, invoices in invoices_by_supplier.items():
        if not invoices:
            continue

        total_mxn = float(sum(_rr9_total_mxn(invoice) or 0 for invoice in invoices))
        facturas = len(invoices)
        canceladas = sum(1 for invoice in invoices if str(getattr(invoice, "estatus_sat", "") or "").upper() == "CANCELADO")
        concentration_pct = round((total_mxn / overall_total_mxn * 100) if overall_total_mxn else 0.0, 2)
        monthly_counts = Counter(str(getattr(invoice, "mes", None) or "SIN_MES") for invoice in invoices)
        peak_period_volume = max(monthly_counts.values()) if monthly_counts else facturas

        repeated_keys = Counter()
        monedas_usadas = set()
        pending_fx_count = 0
        high_count = 0
        medium_count = 0
        incomplete_count = 0
        max_invoice_total = 0.0
        sum_invoice_totals = 0.0

        for invoice in invoices:
            amount_reference = _rr9_total_mxn(invoice)
            if amount_reference is None:
                amount_reference = _rr9_total_original(invoice)
            repeated_keys[(str(getattr(invoice, "rfc_emisor", "") or ""), round(amount_reference, 2))] += 1
            monedas_usadas.add(_rr9_currency(invoice))
            if _rr9_currency(invoice) != "MXN" and (
                _rr9_total_mxn(invoice) is None or str(getattr(invoice, "fuente_tipo_cambio", "") or "").upper() == "PENDIENTE"
            ):
                pending_fx_count += 1
            invoice_risk = str(getattr(invoice, "riesgo", "") or "").upper()
            if invoice_risk == "ALTO":
                high_count += 1
            elif invoice_risk == "MEDIO":
                medium_count += 1
            if not getattr(invoice, "rfc_emisor", None) or not getattr(invoice, "razon_social", None) or not getattr(invoice, "fecha_emision", None):
                incomplete_count += 1
            max_invoice_total = max(max_invoice_total, amount_reference)
            sum_invoice_totals += amount_reference

        operaciones_repetidas = sum(
            1
            for invoice in invoices
            if repeated_keys[
                (
                    str(getattr(invoice, "rfc_emisor", "") or ""),
                    round((_rr9_total_mxn(invoice) if _rr9_total_mxn(invoice) is not None else _rr9_total_original(invoice)), 2),
                )
            ] > 1
        )
        proveedor_promedio = float(sum_invoice_totals / facturas) if facturas else 0.0
        concentration_score = 25 if concentration_pct > 30 else 0
        volume_score = 15 if (peak_period_volume >= 5 or facturas >= 8) else 0
        repetition_score = 15 if operaciones_repetidas >= 2 else 0
        cancellation_score = 10 if canceladas > 0 else 0
        currency_score = 10 if pending_fx_count > 0 else 0
        incomplete_score = 10 if incomplete_count > 0 else 0
        atypical_score = 15 if (
            (avg_invoice_total_mxn > 0 and max_invoice_total >= max(avg_invoice_total_mxn * 3, 100000.0))
            or (proveedor_promedio > 0 and max_invoice_total >= max(proveedor_promedio * 2.5, 100000.0))
        ) else 0

        rr9_score = float(
            min(
                100,
                concentration_score
                + volume_score
                + repetition_score
                + cancellation_score
                + currency_score
                + incomplete_score
                + atypical_score,
            )
        )
        rr9_score = round(min(100.0, rr9_score + min(10.0, high_count * 4 + medium_count * 2)), 2)

        risk_level = _rr9_level_from_score(rr9_score)
        reasons: list[str] = []
        if concentration_score:
            reasons.append(f"Concentracion de gasto alta ({concentration_pct:.2f}%)")
        if volume_score:
            reasons.append("Volumen alto de CFDI en periodo corto")
        if repetition_score:
            reasons.append("Operaciones repetidas por mismo RFC y monto")
        if cancellation_score:
            reasons.append("Proveedor con CFDI cancelados")
        if currency_score:
            reasons.append("Operaciones en moneda extranjera sin tipo de cambio")
        if incomplete_score:
            reasons.append("Datos CFDI incompletos para analisis")
        if atypical_score:
            reasons.append("Importes atipicos frente al historico")
        if high_count or medium_count:
            reasons.append("Riesgo acumulado por CFDI del proveedor")

        flag_requiere_contrato = bool(
            concentration_score
            or volume_score
            or repetition_score
            or atypical_score
            or total_mxn >= 250000
        )
        if flag_requiere_contrato:
            reasons.append("Operacion que probablemente requiere contrato")

        results[rfc_emisor] = {
            "total_mxn": round(total_mxn, 2),
            "facturas": facturas,
            "canceladas": canceladas,
            "porcentaje_canceladas": round((canceladas / facturas * 100) if facturas else 0.0, 2),
            "score_riesgo": rr9_score,
            "risk_level": risk_level,
            "risk_reason": "; ".join(reasons),
            "flag_requiere_contrato": flag_requiere_contrato,
            "operaciones_repetidas": operaciones_repetidas,
            "monedas_usadas": ", ".join(sorted(monedas_usadas)),
            "concentration_pct": concentration_pct,
            "promedio_historico": round(proveedor_promedio, 2),
            "pending_fx_count": pending_fx_count,
            "incomplete_count": incomplete_count,
        }

    return results

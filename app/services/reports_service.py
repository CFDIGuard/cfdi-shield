from __future__ import annotations

from collections import defaultdict

from app.models.invoice import Invoice
from app.models.payment_complement import PaymentComplement
from app.services.fiscal_risk_reports_service import build_fiscal_risk_reports
from app.services.supplier_score import calculate_supplier_score


def _normalized_text(value: str | None, fallback: str = "-") -> str:
    text = str(value or "").strip()
    return text or fallback


def _iva_trasladado(invoice: Invoice) -> float:
    return float(invoice.iva_trasladado or invoice.iva or 0)


def _mxn_amount(invoice: Invoice) -> float:
    if invoice.total_mxn is not None:
        return float(invoice.total_mxn or 0)
    currency = str(invoice.moneda_original or invoice.moneda or "MXN").upper()
    if currency == "MXN":
        return float(invoice.total_original or invoice.total or 0)
    return 0.0


def _non_payment_invoices(invoices: list[Invoice]) -> list[Invoice]:
    return [invoice for invoice in invoices if str(invoice.tipo_comprobante or "").upper() != "P"]


def _visible_invoices(invoices: list[Invoice]) -> list[Invoice]:
    return _non_payment_invoices(invoices)


def _build_payment_complements_report(
    invoices: list[Invoice],
    payment_complements: list[PaymentComplement],
) -> list[dict[str, object]]:
    invoice_by_id = {invoice.id: invoice for invoice in invoices}
    invoice_by_uuid = {invoice.uuid: invoice for invoice in invoices if invoice.uuid}
    rows: list[dict[str, object]] = []

    for complement in sorted(payment_complements, key=lambda item: (item.fecha_pago or "", item.created_at), reverse=True):
        payment_invoice = invoice_by_id.get(complement.payment_invoice_id)
        related_invoice = invoice_by_uuid.get(str(complement.related_invoice_uuid or "").upper())
        rows.append(
            {
                "uuid_complemento": payment_invoice.uuid if payment_invoice is not None else "-",
                "uuid_factura_relacionada": complement.related_invoice_uuid,
                "fecha_pago": complement.fecha_pago,
                "monto_pago": float(complement.monto_pago or 0),
                "moneda_pago": complement.moneda_pago,
                "parcialidad": complement.parcialidad,
                "saldo_anterior": float(complement.saldo_anterior or 0),
                "importe_pagado": float(complement.importe_pagado or 0),
                "saldo_insoluto": float(complement.saldo_insoluto or 0),
                "estado_relacion": "RELACIONADA" if related_invoice is not None else "PENDIENTE",
            }
        )

    return rows


def _build_provider_report(invoices: list[Invoice]) -> list[dict[str, object]]:
    grouped: dict[str, dict[str, object]] = defaultdict(
        lambda: {
            "rfc_emisor": "",
            "razon_social": "",
            "facturas": 0,
            "total_facturado": 0.0,
            "canceladas": 0,
            "iva_total": 0.0,
            "duplicate_count": 0,
            "iva_inconsistency_count": 0,
            "new_high_amount_count": 0,
        }
    )

    repeated_pairs: dict[tuple[str, float], int] = defaultdict(int)
    for invoice in invoices:
        if invoice.rfc_emisor:
            repeated_pairs[(invoice.rfc_emisor, round(invoice.total or 0, 2))] += 1

    for invoice in invoices:
        if not invoice.rfc_emisor:
            continue

        provider = grouped[invoice.rfc_emisor]
        provider["rfc_emisor"] = invoice.rfc_emisor
        provider["razon_social"] = _normalized_text(invoice.razon_social)
        provider["facturas"] += 1
        provider["total_facturado"] += _mxn_amount(invoice)
        provider["canceladas"] += 1 if str(invoice.estatus_sat or "").upper() == "CANCELADO" else 0
        provider["iva_total"] += _iva_trasladado(invoice)

        detail = str(invoice.detalle_riesgo or "").upper()
        if "MISMO RFC EMISOR Y MISMO MONTO" in detail or repeated_pairs[(invoice.rfc_emisor, round(invoice.total or 0, 2))] > 1:
            provider["duplicate_count"] += 1
        if "IVA" in detail:
            provider["iva_inconsistency_count"] += 1
        if "PROVEEDOR NUEVO CON MONTO ALTO" in detail or "PROVEEDOR NUEVO" in detail:
            provider["new_high_amount_count"] += 1

    providers: list[dict[str, object]] = []
    for provider in grouped.values():
        facturas = int(provider["facturas"])
        canceladas = int(provider["canceladas"])
        porcentaje_canceladas = round((canceladas / facturas * 100) if facturas else 0.0, 2)
        score_riesgo, nivel_riesgo = calculate_supplier_score(
            cancellation_rate=porcentaje_canceladas,
            cancellation_count=canceladas,
            invoice_count=facturas,
            duplicate_count=int(provider["duplicate_count"]),
            iva_inconsistency_count=int(provider["iva_inconsistency_count"]),
            new_high_amount_count=int(provider["new_high_amount_count"]),
        )
        providers.append(
            {
                "rfc_emisor": provider["rfc_emisor"],
                "razon_social": provider["razon_social"],
                "total_facturado": round(float(provider["total_facturado"]), 2),
                "facturas": facturas,
                "canceladas": canceladas,
                "porcentaje_canceladas": porcentaje_canceladas,
                "iva_total": round(float(provider["iva_total"]), 2),
                "score_riesgo": score_riesgo,
                "nivel_riesgo": nivel_riesgo,
            }
        )

    providers.sort(key=lambda item: (-float(item["total_facturado"]), item["rfc_emisor"]))
    return providers


def _build_risk_report(invoices: list[Invoice]) -> list[dict[str, object]]:
    risk_rows = [
        {
            "uuid": invoice.uuid,
            "rfc_emisor": _normalized_text(invoice.rfc_emisor),
            "razon_social": _normalized_text(invoice.razon_social),
            "total": float(invoice.total or 0),
            "total_original": float(invoice.total_original or invoice.total or 0),
            "total_mxn": invoice.total_mxn if invoice.total_mxn is not None else None,
            "moneda_original": _normalized_text(invoice.moneda_original or invoice.moneda),
            "estatus_sat": str(invoice.estatus_sat or "").upper(),
            "riesgo": str(invoice.riesgo or "").upper() or "BAJO",
            "detalle_riesgo": invoice.detalle_riesgo,
            "fecha_emision": invoice.fecha_emision,
            "mes": invoice.mes,
        }
        for invoice in sorted(invoices, key=lambda item: item.created_at, reverse=True)
    ]
    return risk_rows


def _build_control_report(invoices: list[Invoice]) -> list[dict[str, object]]:
    control_rows = [
        {
            "uuid": invoice.uuid,
            "archivo": invoice.archivo,
            "rfc_emisor": invoice.rfc_emisor,
            "razon_social": invoice.razon_social,
            "rfc_receptor": invoice.rfc_receptor,
            "folio": invoice.folio,
            "fecha_emision": invoice.fecha_emision,
            "mes": invoice.mes,
            "subtotal": float(invoice.subtotal or 0),
            "descuento": float(invoice.descuento or 0),
            "iva": float(invoice.iva or 0),
            "iva_trasladado": _iva_trasladado(invoice),
            "iva_retenido": float(invoice.iva_retenido or 0),
            "isr_retenido": float(invoice.isr_retenido or 0),
            "ieps_trasladado": float(invoice.ieps_trasladado or 0),
            "total_impuestos_trasladados": float(invoice.total_impuestos_trasladados or 0),
            "total_impuestos_retenidos": float(invoice.total_impuestos_retenidos or 0),
            "total_impuestos": float(invoice.total_impuestos_trasladados or 0) + float(invoice.total_impuestos_retenidos or 0),
            "total": float(invoice.total or 0),
            "moneda": invoice.moneda,
            "moneda_original": invoice.moneda_original or invoice.moneda,
            "total_original": float(invoice.total_original or invoice.total or 0),
            "tipo_cambio_usado": invoice.tipo_cambio_usado,
            "fuente_tipo_cambio": invoice.fuente_tipo_cambio,
            "fecha_tipo_cambio": invoice.fecha_tipo_cambio,
            "total_mxn": invoice.total_mxn,
            "metodo_pago": invoice.metodo_pago,
            "total_pagado": float(invoice.total_pagado or 0),
            "saldo_pendiente": float(invoice.saldo_pendiente or 0),
            "estado_pago": invoice.estado_pago,
            "estatus_sat": invoice.estatus_sat,
            "riesgo": invoice.riesgo,
            "detalle_riesgo": invoice.detalle_riesgo,
            "sat_validado_at": invoice.sat_validado_at.isoformat() if invoice.sat_validado_at else None,
            "created_at": invoice.created_at.isoformat() if invoice.created_at else None,
        }
        for invoice in sorted(invoices, key=lambda item: (item.fecha_emision or "", item.uuid or ""), reverse=True)
    ]
    return control_rows


def _build_resumen_report(invoices: list[Invoice]) -> list[dict[str, object]]:
    grouped: dict[str, dict[str, object]] = defaultdict(
        lambda: {
            "mes": "SIN_MES",
            "facturas": 0,
            "subtotal": 0.0,
            "descuento": 0.0,
            "iva_trasladado": 0.0,
            "iva_retenido": 0.0,
            "isr_retenido": 0.0,
            "ieps_trasladado": 0.0,
            "total_impuestos_trasladados": 0.0,
            "total_impuestos_retenidos": 0.0,
            "total": 0.0,
            "total_mxn": 0.0,
            "vigentes": 0,
            "canceladas": 0,
        }
    )

    for invoice in invoices:
        mes = _normalized_text(invoice.mes, fallback="SIN_MES")
        bucket = grouped[mes]
        bucket["mes"] = mes
        bucket["facturas"] += 1
        bucket["subtotal"] += float(invoice.subtotal or 0)
        bucket["descuento"] = float(bucket.get("descuento", 0.0)) + float(invoice.descuento or 0)
        bucket["iva_trasladado"] += _iva_trasladado(invoice)
        bucket["iva_retenido"] += float(invoice.iva_retenido or 0)
        bucket["isr_retenido"] += float(invoice.isr_retenido or 0)
        bucket["ieps_trasladado"] = float(bucket.get("ieps_trasladado", 0.0)) + float(invoice.ieps_trasladado or 0)
        bucket["total_impuestos_trasladados"] = float(bucket.get("total_impuestos_trasladados", 0.0)) + float(
            invoice.total_impuestos_trasladados or 0
        )
        bucket["total_impuestos_retenidos"] = float(bucket.get("total_impuestos_retenidos", 0.0)) + float(
            invoice.total_impuestos_retenidos or 0
        )
        bucket["total"] += float(invoice.total or 0)
        bucket["total_mxn"] += _mxn_amount(invoice)
        estatus = str(invoice.estatus_sat or "").upper()
        bucket["vigentes"] += 1 if estatus == "VIGENTE" else 0
        bucket["canceladas"] += 1 if estatus == "CANCELADO" else 0

    resumen = []
    for bucket in grouped.values():
        facturas = int(bucket["facturas"])
        canceladas = int(bucket["canceladas"])
        resumen.append(
            {
                "mes": bucket["mes"],
                "facturas": facturas,
                "subtotal": round(float(bucket["subtotal"]), 2),
                "descuento": round(float(bucket.get("descuento", 0.0)), 2),
                "iva_trasladado": round(float(bucket["iva_trasladado"]), 2),
                "iva_retenido": round(float(bucket["iva_retenido"]), 2),
                "isr_retenido": round(float(bucket["isr_retenido"]), 2),
                "ieps_trasladado": round(float(bucket.get("ieps_trasladado", 0.0)), 2),
                "total_impuestos_trasladados": round(float(bucket.get("total_impuestos_trasladados", 0.0)), 2),
                "total_impuestos_retenidos": round(float(bucket.get("total_impuestos_retenidos", 0.0)), 2),
                "total": round(float(bucket["total"]), 2),
                "total_mxn": round(float(bucket["total_mxn"]), 2),
                "vigentes": int(bucket["vigentes"]),
                "canceladas": canceladas,
                "porcentaje_canceladas": round((canceladas / facturas * 100) if facturas else 0.0, 2),
            }
        )

    resumen.sort(key=lambda item: item["mes"])
    return resumen


def build_reports_bundle(
    invoices: list[Invoice],
    payment_complements: list[PaymentComplement] | None = None,
) -> dict[str, object]:
    payment_complements = payment_complements or []
    visible_invoices = _visible_invoices(invoices)
    payment_status_invoices = _non_payment_invoices(invoices)
    resumen = _build_resumen_report(visible_invoices)
    control = _build_control_report(visible_invoices)
    proveedores = _build_provider_report(visible_invoices)
    riesgos = _build_risk_report(visible_invoices)
    fiscal_risk_reports = build_fiscal_risk_reports(visible_invoices)
    complementos_pago = _build_payment_complements_report(invoices, payment_complements)

    total_facturado = float(sum(_mxn_amount(invoice) for invoice in visible_invoices))
    total_iva = float(sum(_iva_trasladado(invoice) for invoice in visible_invoices))
    total_iva_retenido = float(sum(invoice.iva_retenido or 0 for invoice in visible_invoices))
    total_isr_retenido = float(sum(invoice.isr_retenido or 0 for invoice in visible_invoices))
    total_impuestos_netos = float(sum((invoice.total_impuestos_trasladados or 0) - (invoice.total_impuestos_retenidos or 0) for invoice in visible_invoices))
    facturas = len(visible_invoices)
    vigentes = sum(1 for invoice in visible_invoices if str(invoice.estatus_sat or "").upper() == "VIGENTE")
    canceladas = sum(1 for invoice in visible_invoices if str(invoice.estatus_sat or "").upper() == "CANCELADO")
    sin_validacion_sat = sum(
        1 for invoice in visible_invoices if str(invoice.estatus_sat or "").upper() == "SIN_VALIDACION"
    )
    riesgo_alto = sum(1 for invoice in visible_invoices if str(invoice.riesgo or "").upper() == "ALTO")
    riesgo_medio = sum(1 for invoice in visible_invoices if str(invoice.riesgo or "").upper() == "MEDIO")
    riesgo_bajo = sum(1 for invoice in visible_invoices if str(invoice.riesgo or "").upper() == "BAJO")
    proveedores_unicos = len({invoice.rfc_emisor for invoice in visible_invoices if invoice.rfc_emisor})
    facturas_pagadas = sum(1 for invoice in payment_status_invoices if str(invoice.estado_pago or "").upper() == "PAGADA")
    facturas_parciales = sum(1 for invoice in payment_status_invoices if str(invoice.estado_pago or "").upper() == "PARCIAL")
    facturas_pendientes = sum(1 for invoice in payment_status_invoices if str(invoice.estado_pago or "").upper() == "PENDIENTE")
    complementos_sin_factura_relacionada = sum(
        1 for row in complementos_pago if str(row.get("estado_relacion") or "").upper() != "RELACIONADA"
    )

    return {
        "summary": {
            "total_facturado": round(total_facturado, 2),
            "facturas": facturas,
            "vigentes": vigentes,
            "canceladas": canceladas,
            "sin_validacion_sat": sin_validacion_sat,
            "total_iva": round(total_iva, 2),
            "total_iva_trasladado": round(total_iva, 2),
            "total_iva_retenido": round(total_iva_retenido, 2),
            "total_isr_retenido": round(total_isr_retenido, 2),
            "total_impuestos_netos": round(total_impuestos_netos, 2),
            "proveedores_unicos": proveedores_unicos,
            "riesgos_altos": riesgo_alto,
            "riesgo_alto": riesgo_alto,
            "riesgo_medio": riesgo_medio,
            "riesgo_bajo": riesgo_bajo,
            "top_proveedores": proveedores[:5],
            "riesgos": [row for row in riesgos if row["riesgo"] == "ALTO"][:8],
            "rr1_count": len(fiscal_risk_reports["rr1"]),
            "rr9_count": len(fiscal_risk_reports["rr9"]),
            "facturas_pagadas": facturas_pagadas,
            "facturas_parciales": facturas_parciales,
            "facturas_pendientes": facturas_pendientes,
            "complementos_sin_factura_relacionada": complementos_sin_factura_relacionada,
            "rr9_alertas": [
                row for row in fiscal_risk_reports["rr9"] if str(row.get("riesgo_acumulado", "")).upper() in {"ALTO", "MEDIO"}
            ][:8],
        },
        "reports": {
            "resumen": resumen,
            "control": control,
            "proveedores": proveedores,
            "riesgos": riesgos,
            "rr1": fiscal_risk_reports["rr1"],
            "rr9": fiscal_risk_reports["rr9"],
            "resumen_riesgos": fiscal_risk_reports["resumen_riesgos"],
            "complementos_pago": complementos_pago,
        },
    }


def build_dashboard_summary(
    invoices: list[Invoice],
    payment_complements: list[PaymentComplement] | None = None,
) -> dict[str, object]:
    return build_reports_bundle(invoices, payment_complements)["summary"]

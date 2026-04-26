from __future__ import annotations

from collections import Counter, defaultdict
import re

from app.models.invoice import Invoice
from app.services.risk_engine import calculate_rr9_score


RFC_PATTERN = re.compile(r"^[A-Z&\u00d1]{3,4}\d{6}[A-Z0-9]{3}$")


def _currency(invoice: Invoice) -> str:
    return str(invoice.moneda_original or invoice.moneda or "MXN").upper()


def _total_original(invoice: Invoice) -> float:
    return float(invoice.total_original or invoice.total or 0)


def _total_mxn(invoice: Invoice) -> float | None:
    if invoice.total_mxn is not None:
        return float(invoice.total_mxn)
    if _currency(invoice) == "MXN":
        return _total_original(invoice)
    return None


def _safe_text(value: str | None, fallback: str = "-") -> str:
    text = str(value or "").strip()
    return text or fallback


def _valid_rfc(rfc: str | None) -> bool:
    return bool(RFC_PATTERN.match(str(rfc or "").strip().upper()))


def _duplicate_uuid_counts(invoices: list[Invoice]) -> Counter[str]:
    return Counter(invoice.uuid for invoice in invoices if invoice.uuid)


def _alertas_cfdi_motives(invoice: Invoice, uuid_counts: Counter[str]) -> list[str]:
    motives: list[str] = []
    estatus_sat = str(invoice.estatus_sat or "").upper()
    riesgo = str(invoice.riesgo or "").upper()
    moneda = _currency(invoice)
    detail = str(invoice.detalle_riesgo or "")

    if estatus_sat == "CANCELADO":
        motives.append("CFDI cancelado")
    if estatus_sat == "SIN_VALIDACION":
        motives.append("CFDI sin validacion SAT")
    if invoice.uuid and uuid_counts[invoice.uuid] > 1:
        motives.append("UUID duplicado")
    if "XML" in detail.upper() and ("INVALID" in detail.upper() or "INVALIDO" in detail.upper()):
        motives.append("XML invalido")
    if not _valid_rfc(invoice.rfc_emisor):
        motives.append("RFC emisor faltante o invalido")
    if moneda != "MXN" and invoice.total_mxn is None:
        motives.append("Monto en moneda extranjera sin conversion MXN")
    if moneda != "MXN" and str(invoice.fuente_tipo_cambio or "").upper() == "PENDIENTE":
        motives.append("Tipo de cambio pendiente")
    if riesgo in {"MEDIO", "ALTO"}:
        motives.append(f"Factura con riesgo {riesgo}")
    return motives


def build_fiscal_risk_reports(invoices: list[Invoice]) -> dict[str, list[dict[str, object]]]:
    uuid_counts = _duplicate_uuid_counts(invoices)
    alertas_cfdi_rows: list[dict[str, object]] = []

    for invoice in sorted(invoices, key=lambda item: item.created_at, reverse=True):
        motives = _alertas_cfdi_motives(invoice, uuid_counts)
        if not motives:
            continue
        alertas_cfdi_rows.append(
            {
                "uuid": invoice.uuid,
                "rfc_emisor": _safe_text(invoice.rfc_emisor),
                "proveedor": _safe_text(invoice.razon_social),
                "fecha": invoice.fecha_emision,
                "moneda": _currency(invoice),
                "total_original": _total_original(invoice),
                "total_mxn": _total_mxn(invoice),
                "estatus_sat": str(invoice.estatus_sat or "").upper() or "SIN_ESTATUS",
                "riesgo": str(invoice.riesgo or "").upper() or "BAJO",
                "motivo": "; ".join(motives),
            }
        )

    grouped_by_rfc: dict[str, list[Invoice]] = defaultdict(list)
    for invoice in invoices:
        if invoice.rfc_emisor:
            grouped_by_rfc[invoice.rfc_emisor].append(invoice)

    analisis_proveedor_scores = calculate_rr9_score(grouped_by_rfc)

    analisis_proveedor_rows: list[dict[str, object]] = []
    for rfc_emisor, provider_invoices in grouped_by_rfc.items():
        analisis_proveedor_metrics = analisis_proveedor_scores.get(rfc_emisor)
        if not analisis_proveedor_metrics:
            continue
        provider_name = _safe_text(provider_invoices[0].razon_social)
        if not analisis_proveedor_metrics["risk_reason"]:
            continue

        analisis_proveedor_rows.append(
            {
                "rfc_emisor": rfc_emisor,
                "proveedor": provider_name,
                "facturas": analisis_proveedor_metrics["facturas"],
                "total_mxn": analisis_proveedor_metrics["total_mxn"],
                "canceladas": analisis_proveedor_metrics["canceladas"],
                "porcentaje_canceladas": analisis_proveedor_metrics["porcentaje_canceladas"],
                "score_riesgo": analisis_proveedor_metrics["score_riesgo"],
                "monedas_usadas": analisis_proveedor_metrics["monedas_usadas"],
                "operaciones_repetidas": analisis_proveedor_metrics["operaciones_repetidas"],
                "riesgo_acumulado": str(analisis_proveedor_metrics["risk_level"]).replace("LOW", "BAJO").replace("MEDIUM", "MEDIO").replace("HIGH", "ALTO"),
                "motivo": analisis_proveedor_metrics["risk_reason"],
                "flag_requiere_contrato": analisis_proveedor_metrics["flag_requiere_contrato"],
            }
        )

    analisis_proveedor_rows.sort(key=lambda row: (-float(row["total_mxn"]), str(row["rfc_emisor"])))

    resumen_riesgos = [
        {"indicador": "Alertas por CFDI", "valor": len(alertas_cfdi_rows), "detalle": "Facturas individuales con criterio de riesgo operativo"},
        {"indicador": "Proveedores en analisis", "valor": len(analisis_proveedor_rows), "detalle": "RFC con concentracion, cancelaciones o patrones"},
        {
            "indicador": "Facturas sin validacion SAT",
            "valor": sum(1 for invoice in invoices if str(invoice.estatus_sat or "").upper() == "SIN_VALIDACION"),
            "detalle": "CFDI cargados sin consulta SAT efectiva",
        },
        {
            "indicador": "Facturas canceladas",
            "valor": sum(1 for invoice in invoices if str(invoice.estatus_sat or "").upper() == "CANCELADO"),
            "detalle": "CFDI con estatus cancelado",
        },
        {
            "indicador": "Facturas con tipo de cambio pendiente",
            "valor": sum(
                1
                for invoice in invoices
                if _currency(invoice) != "MXN" and str(invoice.fuente_tipo_cambio or "").upper() == "PENDIENTE"
            ),
            "detalle": "Moneda extranjera sin conversion definitiva a MXN",
        },
    ]

    return {
        "alertas_cfdi": alertas_cfdi_rows,
        "analisis_proveedor": analisis_proveedor_rows,
        "rr1": alertas_cfdi_rows,
        "rr9": analisis_proveedor_rows,
        "resumen_riesgos": resumen_riesgos,
    }

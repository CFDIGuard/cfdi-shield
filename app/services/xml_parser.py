from __future__ import annotations

import re
from datetime import datetime
from decimal import Decimal, InvalidOperation

from defusedxml import ElementTree as ET
from defusedxml.common import DefusedXmlException

from app.schemas.invoice import InvoiceProcessedData
from app.schemas.payment_complement import PaymentComplementProcessedData


CFDI_NS = {
    "cfdi": "http://www.sat.gob.mx/cfd/4",
    "cfdi3": "http://www.sat.gob.mx/cfd/3",
    "tfd": "http://www.sat.gob.mx/TimbreFiscalDigital",
    "pagos20": "http://www.sat.gob.mx/Pagos20",
    "pagos10": "http://www.sat.gob.mx/Pagos",
}
RFC_REGEX = re.compile(r"^[A-Z&]{3,4}[0-9]{6}[A-Z0-9]{3}$")
UUID_REGEX = re.compile(
    r"^[0-9A-F]{8}-[0-9A-F]{4}-[1-5][0-9A-F]{3}-[89AB][0-9A-F]{3}-[0-9A-F]{12}$"
)


def _find_first(root: ET.Element, paths: list[str]) -> ET.Element | None:
    for path in paths:
        element = root.find(path, CFDI_NS)
        if element is not None:
            return element
    return None


def _findall_first(root: ET.Element, paths: list[str]) -> list[ET.Element]:
    for path in paths:
        elements = root.findall(path, CFDI_NS)
        if elements:
            return elements
    return []


def _extract_tax_amounts(
    impuestos: ET.Element | None,
    include_nested: bool = False,
) -> tuple[Decimal, Decimal, Decimal, Decimal, Decimal, Decimal]:
    if impuestos is None:
        zero = Decimal("0")
        return zero, zero, zero, zero, zero, zero

    zero = Decimal("0")
    iva_trasladado = zero
    ieps_trasladado = zero
    iva_retenido = zero
    isr_retenido = zero

    traslado_paths = ["cfdi:Traslados/cfdi:Traslado", "cfdi3:Traslados/cfdi3:Traslado"]
    retencion_paths = ["cfdi:Retenciones/cfdi:Retencion", "cfdi3:Retenciones/cfdi3:Retencion"]
    if include_nested:
        traslado_paths = [".//cfdi:Traslado", ".//cfdi3:Traslado"]
        retencion_paths = [".//cfdi:Retencion", ".//cfdi3:Retencion"]

    for traslado in _findall_first(impuestos, traslado_paths):
        impuesto = traslado.attrib.get("Impuesto")
        importe = _decimal_value(traslado.attrib.get("Importe"))
        if impuesto == "002":
            iva_trasladado += importe
        elif impuesto == "003":
            ieps_trasladado += importe

    for retencion in _findall_first(impuestos, retencion_paths):
        impuesto = retencion.attrib.get("Impuesto")
        importe = _decimal_value(retencion.attrib.get("Importe"))
        if impuesto == "002":
            iva_retenido += importe
        elif impuesto == "001":
            isr_retenido += importe

    total_trasladados = _decimal_value(impuestos.attrib.get("TotalImpuestosTrasladados"))
    total_retenidos = _decimal_value(impuestos.attrib.get("TotalImpuestosRetenidos"))

    if total_trasladados == zero:
        total_trasladados = iva_trasladado + ieps_trasladado
    if total_retenidos == zero:
        total_retenidos = iva_retenido + isr_retenido

    return (
        iva_trasladado,
        ieps_trasladado,
        iva_retenido,
        isr_retenido,
        total_trasladados,
        total_retenidos,
    )


def _extract_payment_docto_tax_amounts(
    impuestos_dr: ET.Element | None,
) -> tuple[Decimal, Decimal]:
    if impuestos_dr is None:
        zero = Decimal("0")
        return zero, zero

    total_trasladados = Decimal("0")
    total_retenidos = Decimal("0")

    for traslado in _findall_first(
        impuestos_dr,
        [
            "pagos20:TrasladosDR/pagos20:TrasladoDR",
            ".//pagos20:TrasladoDR",
        ],
    ):
        total_trasladados += _decimal_value(traslado.attrib.get("ImporteDR"))

    for retencion in _findall_first(
        impuestos_dr,
        [
            "pagos20:RetencionesDR/pagos20:RetencionDR",
            ".//pagos20:RetencionDR",
        ],
    ):
        total_retenidos += _decimal_value(retencion.attrib.get("ImporteDR"))

    return total_trasladados, total_retenidos


def _float_value(value: str | None) -> float:
    return float(_decimal_value(value))


def _decimal_value(value: str | None) -> Decimal:
    if value in (None, ""):
        return Decimal("0")
    try:
        return Decimal(str(value).strip())
    except (InvalidOperation, TypeError, ValueError):
        return Decimal("0")


def _safe_upper(value: str | None) -> str:
    return str(value or "").strip().upper()


def _safe_float(value: str | None) -> float | None:
    if value in (None, ""):
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _safe_int(value: str | None) -> int | None:
    if value in (None, ""):
        return None
    try:
        return int(str(value).strip())
    except (TypeError, ValueError):
        return None


def _build_month(fecha_emision: str | None) -> str | None:
    if not fecha_emision:
        return None
    try:
        return datetime.fromisoformat(fecha_emision.replace("Z", "+00:00")).strftime("%Y-%m")
    except ValueError:
        return fecha_emision[:7] if len(fecha_emision) >= 7 else None


def _validate_required_fields(data: InvoiceProcessedData) -> None:
    if not data.uuid:
        raise ValueError("El XML no contiene UUID de CFDI.")
    if not UUID_REGEX.match(data.uuid):
        raise ValueError("El UUID del CFDI es invalido.")
    if not data.rfc_emisor or not RFC_REGEX.match(data.rfc_emisor):
        raise ValueError("El RFC emisor es invalido.")
    if not data.rfc_receptor or not RFC_REGEX.match(data.rfc_receptor):
        raise ValueError("El RFC receptor es invalido.")
    if str(data.tipo_comprobante or "").upper() == "P":
        if not data.payment_complements:
            raise ValueError("El complemento de pago no contiene documentos relacionados.")
        if not any(float(item.importe_pagado or item.monto_pago or 0) > 0 for item in data.payment_complements):
            raise ValueError("El complemento de pago no contiene montos validos.")
        return
    if data.total <= 0:
        raise ValueError("El total del CFDI debe ser mayor a cero.")


def _payment_nodes(root: ET.Element) -> list[ET.Element]:
    return _findall_first(root, [".//pagos20:Pago", ".//pagos10:Pago"])


def _extract_payment_complements(root: ET.Element) -> list[PaymentComplementProcessedData]:
    complements: list[PaymentComplementProcessedData] = []

    for pago in _payment_nodes(root):
        fecha_pago = pago.attrib.get("FechaPago")
        moneda_pago = _safe_upper(pago.attrib.get("MonedaP")) or None
        tipo_cambio_pago = _safe_float(pago.attrib.get("TipoCambioP"))
        monto_pago_decimal = _decimal_value(pago.attrib.get("Monto"))

        doctos_relacionados = _findall_first(
            pago,
            ["pagos20:DoctoRelacionado", "pagos10:DoctoRelacionado"],
        )
        for docto in doctos_relacionados:
            impuestos_dr = _find_first(
                docto,
                ["pagos20:ImpuestosDR", "pagos10:ImpuestosDR"],
            )
            total_trasladados_dr, total_retenidos_dr = _extract_payment_docto_tax_amounts(impuestos_dr)
            complements.append(
                PaymentComplementProcessedData(
                    related_invoice_uuid=_safe_upper(docto.attrib.get("IdDocumento")) or None,
                    fecha_pago=fecha_pago,
                    moneda_pago=moneda_pago,
                    tipo_cambio_pago=tipo_cambio_pago,
                    monto_pago=float(monto_pago_decimal),
                    parcialidad=_safe_int(docto.attrib.get("NumParcialidad")),
                    saldo_anterior=float(_decimal_value(docto.attrib.get("ImpSaldoAnt"))),
                    importe_pagado=float(_decimal_value(docto.attrib.get("ImpPagado"))),
                    saldo_insoluto=float(_decimal_value(docto.attrib.get("ImpSaldoInsoluto"))),
                    serie=str(docto.attrib.get("Serie", "")).strip() or None,
                    folio=str(docto.attrib.get("Folio", "")).strip() or None,
                    moneda_documento_relacionado=_safe_upper(docto.attrib.get("MonedaDR")) or None,
                    objeto_impuesto_dr=str(docto.attrib.get("ObjetoImpDR", "")).strip() or None,
                    impuestos_dr_trasladados=float(total_trasladados_dr),
                    impuestos_dr_retenidos=float(total_retenidos_dr),
                )
            )

    return complements


def parse_cfdi_xml(file_bytes: bytes, filename: str | None = None) -> InvoiceProcessedData:
    try:
        root = ET.fromstring(file_bytes)
    except (ET.ParseError, DefusedXmlException) as exc:
        raise ValueError("El archivo XML no es valido.") from exc

    emisor = _find_first(root, ["cfdi:Emisor", "cfdi3:Emisor"])
    receptor = _find_first(root, ["cfdi:Receptor", "cfdi3:Receptor"])
    timbre = _find_first(root, [".//tfd:TimbreFiscalDigital"])

    if emisor is None or receptor is None or timbre is None:
        raise ValueError("XML sin Emisor, Receptor o TimbreFiscalDigital.")

    subtotal = _decimal_value(root.attrib.get("SubTotal"))
    descuento = _decimal_value(root.attrib.get("Descuento"))
    total = _decimal_value(root.attrib.get("Total"))
    fecha_emision = root.attrib.get("Fecha")
    tipo_comprobante = _safe_upper(root.attrib.get("TipoDeComprobante")) or None
    moneda_original = _safe_upper(root.attrib.get("Moneda")) or "MXN"
    tipo_cambio_xml = _safe_float(root.attrib.get("TipoCambio"))
    payment_complements = _extract_payment_complements(root)

    impuestos_root = _find_first(root, ["cfdi:Impuestos", "cfdi3:Impuestos"])
    (
        iva_trasladado,
        ieps_trasladado,
        iva_retenido,
        isr_retenido,
        total_impuestos_trasladados,
        total_impuestos_retenidos,
    ) = _extract_tax_amounts(impuestos_root)
    if (
        iva_trasladado == Decimal("0")
        and ieps_trasladado == Decimal("0")
        and iva_retenido == Decimal("0")
        and isr_retenido == Decimal("0")
        and total_impuestos_trasladados == Decimal("0")
        and total_impuestos_retenidos == Decimal("0")
    ):
        (
            iva_trasladado,
            ieps_trasladado,
            iva_retenido,
            isr_retenido,
            total_impuestos_trasladados,
            total_impuestos_retenidos,
        ) = _extract_tax_amounts(impuestos_root, include_nested=True)

    data = InvoiceProcessedData(
        archivo=filename,
        uuid=_safe_upper(timbre.attrib.get("UUID")),
        tipo_comprobante=tipo_comprobante,
        razon_social=str(emisor.attrib.get("Nombre", "")).strip(),
        rfc_emisor=_safe_upper(emisor.attrib.get("Rfc")),
        rfc_receptor=_safe_upper(receptor.attrib.get("Rfc")),
        folio=str(root.attrib.get("Folio", "")).strip() or None,
        fecha_emision=fecha_emision,
        mes=_build_month(fecha_emision),
        subtotal=float(subtotal),
        descuento=float(descuento),
        total=float(total),
        total_original=float(total),
        iva=float(iva_trasladado),
        iva_trasladado=float(iva_trasladado),
        iva_retenido=float(iva_retenido),
        isr_retenido=float(isr_retenido),
        ieps_trasladado=float(ieps_trasladado),
        total_impuestos_trasladados=float(total_impuestos_trasladados),
        total_impuestos_retenidos=float(total_impuestos_retenidos),
        moneda=moneda_original,
        moneda_original=moneda_original,
        tipo_cambio_xml=tipo_cambio_xml,
        metodo_pago=str(root.attrib.get("MetodoPago", "")).strip() or None,
        payment_complements=payment_complements,
    )
    _validate_required_fields(data)
    return data

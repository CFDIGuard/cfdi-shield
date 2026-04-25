from __future__ import annotations

import re
import xml.etree.ElementTree as ET
from datetime import datetime

from app.schemas.invoice import InvoiceProcessedData


CFDI_NS = {
    "cfdi": "http://www.sat.gob.mx/cfd/4",
    "cfdi3": "http://www.sat.gob.mx/cfd/3",
    "tfd": "http://www.sat.gob.mx/TimbreFiscalDigital",
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


def _extract_tax_amounts(impuestos: ET.Element | None, include_nested: bool = False) -> tuple[float, float, float]:
    if impuestos is None:
        return 0.0, 0.0, 0.0

    iva_trasladado = 0.0
    iva_retenido = 0.0
    isr_retenido = 0.0

    traslado_paths = ["cfdi:Traslados/cfdi:Traslado", "cfdi3:Traslados/cfdi3:Traslado"]
    retencion_paths = ["cfdi:Retenciones/cfdi:Retencion", "cfdi3:Retenciones/cfdi3:Retencion"]
    if include_nested:
        traslado_paths = [".//cfdi:Traslado", ".//cfdi3:Traslado"]
        retencion_paths = [".//cfdi:Retencion", ".//cfdi3:Retencion"]

    for traslado in _findall_first(impuestos, traslado_paths):
        if traslado.attrib.get("Impuesto") == "002":
            iva_trasladado += _float_value(traslado.attrib.get("Importe"))

    for retencion in _findall_first(impuestos, retencion_paths):
        impuesto = retencion.attrib.get("Impuesto")
        if impuesto == "002":
            iva_retenido += _float_value(retencion.attrib.get("Importe"))
        elif impuesto == "001":
            isr_retenido += _float_value(retencion.attrib.get("Importe"))

    return iva_trasladado, iva_retenido, isr_retenido


def _float_value(value: str | None) -> float:
    if value in (None, ""):
        return 0.0
    try:
        return float(value)
    except (TypeError, ValueError):
        return 0.0


def _safe_upper(value: str | None) -> str:
    return str(value or "").strip().upper()


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
    if data.total <= 0:
        raise ValueError("El total del CFDI debe ser mayor a cero.")


def parse_cfdi_xml(file_bytes: bytes, filename: str | None = None) -> InvoiceProcessedData:
    try:
        root = ET.fromstring(file_bytes)
    except ET.ParseError as exc:
        raise ValueError("El archivo XML no es valido.") from exc

    emisor = _find_first(root, ["cfdi:Emisor", "cfdi3:Emisor"])
    receptor = _find_first(root, ["cfdi:Receptor", "cfdi3:Receptor"])
    timbre = _find_first(root, [".//tfd:TimbreFiscalDigital"])

    if emisor is None or receptor is None or timbre is None:
        raise ValueError("XML sin Emisor, Receptor o TimbreFiscalDigital.")

    subtotal = _float_value(root.attrib.get("SubTotal"))
    total = _float_value(root.attrib.get("Total"))
    fecha_emision = root.attrib.get("Fecha")

    impuestos_root = _find_first(root, ["cfdi:Impuestos", "cfdi3:Impuestos"])
    iva_trasladado, iva_retenido, isr_retenido = _extract_tax_amounts(impuestos_root)
    if iva_trasladado == 0.0 and iva_retenido == 0.0 and isr_retenido == 0.0:
        iva_trasladado, iva_retenido, isr_retenido = _extract_tax_amounts(impuestos_root, include_nested=True)

    data = InvoiceProcessedData(
        archivo=filename,
        uuid=_safe_upper(timbre.attrib.get("UUID")),
        razon_social=str(emisor.attrib.get("Nombre", "")).strip(),
        rfc_emisor=_safe_upper(emisor.attrib.get("Rfc")),
        rfc_receptor=_safe_upper(receptor.attrib.get("Rfc")),
        folio=str(root.attrib.get("Folio", "")).strip() or None,
        fecha_emision=fecha_emision,
        mes=_build_month(fecha_emision),
        subtotal=subtotal,
        total=total,
        iva=iva_trasladado,
        iva_retenido=iva_retenido,
        isr_retenido=isr_retenido,
        moneda=str(root.attrib.get("Moneda", "")).strip() or None,
        metodo_pago=str(root.attrib.get("MetodoPago", "")).strip() or None,
    )
    _validate_required_fields(data)
    return data

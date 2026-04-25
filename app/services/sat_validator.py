from __future__ import annotations

import logging
import time
import xml.etree.ElementTree as ET
from dataclasses import dataclass

import requests

from app.core.config import settings


logger = logging.getLogger(__name__)
SAT_STATE_NAMESPACE = "http://schemas.datacontract.org/2004/07/Sat.Cfdi.Negocio.ConsultaCfdi.Servicio"
SOAP_ACTION = "http://tempuri.org/IConsultaCFDIService/Consulta"
_sat_cache: dict[str, tuple[float, str]] = {}


@dataclass
class SatValidationResult:
    estatus: str
    validated_at_epoch: float | None


class SatValidator:
    def __init__(self) -> None:
        self.session = requests.Session()

    def validar(
        self,
        uuid: str,
        rfc_emisor: str | None,
        rfc_receptor: str | None,
        total: float,
        force_refresh: bool = False,
    ) -> SatValidationResult:
        if settings.local_mode:
            logger.info("SAT validation skipped: LOCAL_MODE")
            return SatValidationResult(estatus="SIN_VALIDACION", validated_at_epoch=None)

        if not settings.enable_sat_validation:
            logger.info("SAT validation skipped: ENABLE_SAT_VALIDATION=False")
            return SatValidationResult(estatus="SIN_VALIDACION", validated_at_epoch=None)

        if not uuid or not rfc_emisor or not rfc_receptor:
            return SatValidationResult(estatus="ERROR", validated_at_epoch=time.time())

        logger.info("SAT validation enabled")
        now = time.time()
        cached = None if force_refresh else _sat_cache.get(uuid)
        if cached and now - cached[0] <= settings.sat_cache_ttl_seconds:
            return SatValidationResult(estatus=cached[1], validated_at_epoch=cached[0])

        formatted_total = f"{float(total):.6f}"
        soap = self._build_soap(uuid, rfc_emisor, rfc_receptor, formatted_total)

        try:
            response = self.session.post(
                settings.sat_service_url,
                data=soap.encode("utf-8"),
                headers={
                    "Content-Type": "text/xml; charset=utf-8",
                    "SOAPAction": SOAP_ACTION,
                },
                timeout=settings.sat_timeout_seconds,
            )
            response.raise_for_status()
            estatus = self._parse_estado(response.text)
        except requests.RequestException as exc:
            logger.warning("SAT validation failed for UUID=%s: %s", uuid[-8:], exc)
            estatus = "ERROR"
        except ET.ParseError:
            estatus = "ERROR"

        _sat_cache[uuid] = (now, estatus)
        return SatValidationResult(estatus=estatus, validated_at_epoch=now)

    def _build_soap(self, uuid: str, rfc_emisor: str, rfc_receptor: str, total: str) -> str:
        return f"""<?xml version="1.0" encoding="utf-8"?>
<soapenv:Envelope xmlns:soapenv="http://schemas.xmlsoap.org/soap/envelope/" xmlns:tem="http://tempuri.org/">
<soapenv:Body>
<tem:Consulta>
<tem:expresionImpresa>?re={rfc_emisor}&amp;rr={rfc_receptor}&amp;tt={total}&amp;id={uuid}</tem:expresionImpresa>
</tem:Consulta>
</soapenv:Body>
</soapenv:Envelope>"""

    def _parse_estado(self, response_text: str) -> str:
        root = ET.fromstring(response_text)
        estado = root.find(f".//{{{SAT_STATE_NAMESPACE}}}Estado")
        if estado is None or not estado.text:
            return "NO_ENCONTRADO"
        return estado.text.strip().upper()


def get_sat_validator() -> SatValidator:
    return SatValidator()

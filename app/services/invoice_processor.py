from __future__ import annotations

from datetime import datetime
import logging

from app.core.config import settings
from app.repositories.invoice_repository import InvoiceRepository
from app.schemas.invoice import InvoiceCreate
from app.services.duplicate_detector import has_same_rfc_total
from app.services.risk_engine import (
    build_risk_detail,
    calculate_risk_level,
    calculate_risk_score,
    detect_invoice_risk_types,
)
from app.services.sat_validator import SatValidationResult, get_sat_validator
from app.services.xml_parser import parse_cfdi_xml


logger = logging.getLogger(__name__)


def procesar_factura(
    file_bytes: bytes,
    repository: InvoiceRepository,
    filename: str | None = None,
    use_sat_validation: bool | None = None,
) -> InvoiceCreate:
    data = parse_cfdi_xml(file_bytes, filename=filename)
    provider_stats = repository.get_provider_stats(data.rfc_emisor)
    sat_validation_enabled = settings.enable_sat_validation and not settings.local_mode
    if use_sat_validation is not None:
        sat_validation_enabled = sat_validation_enabled and use_sat_validation

    if not sat_validation_enabled:
        logger.info("SAT validation skipped: user toggle disabled")
        sat_result = SatValidationResult(estatus="SIN_VALIDACION", validated_at_epoch=None)
    else:
        cached_sat = repository.get_recent_sat_validation(
            data.uuid,
            max_age_seconds=settings.sat_cache_ttl_seconds,
        )
        if cached_sat is not None:
            logger.info("SAT validation cache hit for UUID=%s", f"...{data.uuid[-8:]}")
            sat_result = SatValidationResult(
                estatus=cached_sat.estatus_sat,
                validated_at_epoch=cached_sat.validated_at.timestamp(),
            )
        else:
            sat_result = get_sat_validator().validar(
                uuid=data.uuid,
                rfc_emisor=data.rfc_emisor,
                rfc_receptor=data.rfc_receptor,
                total=data.total,
            )
            if sat_result.validated_at_epoch is not None:
                repository.save_sat_validation(
                    data.uuid,
                    sat_result.estatus,
                    datetime.utcfromtimestamp(sat_result.validated_at_epoch),
                )

    risk_types = detect_invoice_risk_types(
        invoice=data,
        estatus_sat=sat_result.estatus,
        provider_invoice_count=provider_stats["facturas"],
        provider_cancelled_count=provider_stats["canceladas"],
        has_same_rfc_total=has_same_rfc_total(repository, data),
        high_amount_threshold=repository.get_high_amount_threshold(),
    )
    invoice_data = data.model_dump()
    invoice_data.update(
        {
            "estatus_sat": sat_result.estatus,
            "riesgo": calculate_risk_level(risk_types, sat_result.estatus, data.total),
            "score_proveedor": calculate_risk_score(risk_types),
            "detalle_riesgo": build_risk_detail(risk_types),
            "sat_validado_at": (
                datetime.utcfromtimestamp(sat_result.validated_at_epoch)
                if sat_result.validated_at_epoch is not None
                else None
            ),
        }
    )
    return InvoiceCreate(**invoice_data)

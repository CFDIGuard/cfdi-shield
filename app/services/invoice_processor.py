from __future__ import annotations

from datetime import datetime
import logging

from app.core.config import settings
from app.repositories.invoice_repository import InvoiceRepository
from app.schemas.invoice import InvoiceCreate
from app.services.duplicate_detector import has_same_rfc_total
from app.services.exchange_rate_service import resolve_exchange_rate
from app.services.security_utils import mask_uuid
from app.services.risk_engine import (
    build_risk_detail,
    calculate_risk_level,
    calculate_risk_score,
    detect_invoice_risk_types,
)
from app.services.sat_validator import SatValidationResult, get_sat_validator
from app.services.xml_parser import parse_cfdi_xml


logger = logging.getLogger(__name__)


class InvoiceProcessingError(Exception):
    def __init__(
        self,
        *,
        stage: str,
        message: str,
        filename: str | None = None,
        uuid: str | None = None,
    ) -> None:
        super().__init__(message)
        self.stage = stage
        self.message = message
        self.filename = filename
        self.uuid = uuid


def procesar_factura(
    file_bytes: bytes,
    repository: InvoiceRepository,
    filename: str | None = None,
    use_sat_validation: bool | None = None,
    user_id: int | None = None,
) -> InvoiceCreate:
    data = None
    try:
        data = parse_cfdi_xml(file_bytes, filename=filename)
        if str(data.tipo_comprobante or "").upper() == "P":
            logger.info(
                "Payment invoice detected | payment_invoice_uuid=%s | complements=%s",
                mask_uuid(data.uuid),
                len(data.payment_complements),
            )
            for payment in data.payment_complements:
                logger.info(
                    "Payment complement parsed | payment_invoice_uuid=%s | related_invoice_uuid=%s | importe_pagado=%.2f",
                    mask_uuid(data.uuid),
                    mask_uuid(payment.related_invoice_uuid),
                    float(payment.importe_pagado or 0),
                )
    except Exception as exc:
        logger.exception(
            "Invoice processing failed | stage=parse_xml | filename=%s | uuid=%s | error=%s",
            filename or "sin_nombre",
            None,
            str(exc),
        )
        raise InvoiceProcessingError(
            stage="parse_xml",
            message=str(exc),
            filename=filename,
        ) from exc

    provider_stats = repository.get_provider_stats(data.rfc_emisor)
    exchange_rate_result = resolve_exchange_rate(
        moneda_original=data.moneda_original or data.moneda,
        total_original=data.total_original or data.total,
        tipo_cambio_xml=data.tipo_cambio_xml,
        fecha_emision=data.fecha_emision,
    )
    sat_validation_enabled = settings.enable_sat_validation and not settings.local_mode
    if use_sat_validation is not None:
        sat_validation_enabled = sat_validation_enabled and use_sat_validation

    try:
        if not sat_validation_enabled:
            logger.info("SAT validation skipped: user toggle disabled")
            sat_result = SatValidationResult(
                estatus="SIN_VALIDACION",
                validated_at_epoch=None,
            )
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
                    data.uuid,
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
    except Exception as exc:
        logger.exception(
            "Invoice processing failed | stage=sat_validation | filename=%s | uuid=%s | error=%s",
            filename or "sin_nombre",
            mask_uuid(data.uuid if data is not None else None),
            str(exc),
        )
        raise InvoiceProcessingError(
            stage="sat_validation",
            message=str(exc),
            filename=filename,
            uuid=data.uuid if data is not None else None,
        ) from exc

    try:
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
                "moneda": exchange_rate_result.moneda_original,
                "moneda_original": exchange_rate_result.moneda_original,
                "total_original": data.total_original or data.total,
                "tipo_cambio_usado": exchange_rate_result.tipo_cambio_usado,
                "total_mxn": exchange_rate_result.total_mxn,
                "fuente_tipo_cambio": exchange_rate_result.fuente_tipo_cambio,
                "fecha_tipo_cambio": exchange_rate_result.fecha_tipo_cambio,
                "user_id": user_id,
                "sat_validado_at": (
                    datetime.utcfromtimestamp(sat_result.validated_at_epoch)
                    if sat_result.validated_at_epoch is not None
                    else None
                ),
            }
        )
        return InvoiceCreate(**invoice_data)
    except Exception as exc:
        logger.exception(
            "Invoice processing failed | stage=unknown | filename=%s | uuid=%s | error=%s",
            filename or "sin_nombre",
            mask_uuid(data.uuid if data is not None else None),
            str(exc),
        )
        raise InvoiceProcessingError(
            stage="unknown",
            message=str(exc),
            filename=filename,
            uuid=data.uuid if data is not None else None,
        ) from exc

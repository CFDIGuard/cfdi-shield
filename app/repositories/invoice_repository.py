from __future__ import annotations

from datetime import datetime, timedelta
import logging

from sqlalchemy import Numeric, String, cast, distinct, func, select
from sqlalchemy.orm import Session

from app.models.invoice import Invoice
from app.models.payment_complement import PaymentComplement
from app.models.sat_validation_cache import SatValidationCache
from app.schemas.invoice import InvoiceCreate, InvoiceFilters
from app.schemas.payment_complement import PaymentComplementCreate
from app.services.reports_service import build_dashboard_summary, build_reports_bundle


logger = logging.getLogger(__name__)


class InvoiceRepository:
    def __init__(self, db: Session, user_id: int | None = None):
        self.db = db
        self.user_id = user_id

    def _scope_invoice_statement(self, statement):
        if self.user_id is None:
            return statement
        return statement.where(Invoice.user_id == self.user_id)

    def _apply_filters(self, statement, filters: InvoiceFilters | None):
        if filters is None:
            return statement

        cleaned = filters.cleaned()
        if not cleaned:
            return statement

        if cleaned.get("rfc_receptor"):
            statement = statement.where(
                func.upper(func.coalesce(Invoice.rfc_receptor, "")).like(f"%{cleaned['rfc_receptor'].upper()}%")
            )
        if cleaned.get("rfc_emisor"):
            statement = statement.where(
                func.upper(func.coalesce(Invoice.rfc_emisor, "")).like(f"%{cleaned['rfc_emisor'].upper()}%")
            )
        if cleaned.get("proveedor"):
            statement = statement.where(
                func.upper(func.coalesce(cast(Invoice.razon_social, String), "")).like(f"%{cleaned['proveedor'].upper()}%")
            )
        if cleaned.get("estatus_sat"):
            statement = statement.where(
                func.upper(func.coalesce(Invoice.estatus_sat, "")) == cleaned["estatus_sat"].upper()
            )
        if cleaned.get("riesgo"):
            statement = statement.where(
                func.upper(func.coalesce(Invoice.riesgo, "")) == cleaned["riesgo"].upper()
            )
        if cleaned.get("moneda"):
            statement = statement.where(
                func.upper(func.coalesce(Invoice.moneda_original, Invoice.moneda, "MXN")) == cleaned["moneda"].upper()
            )
        if cleaned.get("fecha_desde"):
            statement = statement.where(func.coalesce(Invoice.fecha_emision, "") >= cleaned["fecha_desde"])
        if cleaned.get("fecha_hasta"):
            statement = statement.where(func.coalesce(Invoice.fecha_emision, "") <= f"{cleaned['fecha_hasta']}T23:59:59")
        return statement

    def _scope_payment_statement(self, statement):
        if self.user_id is None:
            return statement
        return statement.where(PaymentComplement.user_id == self.user_id)

    def _invoice_reference_total(self, invoice: Invoice) -> float:
        if invoice.total_mxn is not None:
            return float(invoice.total_mxn or 0)
        if invoice.total_original:
            return float(invoice.total_original or 0)
        return float(invoice.total or 0)

    def _persist_payment_complements(
        self,
        invoice: Invoice,
        payment_complements: list[dict[str, object]],
    ) -> None:
        if not payment_complements:
            return

        missing_related: list[str] = []
        normalized_rows: list[PaymentComplementCreate] = []
        for row in payment_complements:
            related_invoice_uuid = str(row.get("related_invoice_uuid") or "").strip().upper() or None
            if not related_invoice_uuid:
                missing_related.append("(sin UUID relacionado)")
                continue
            related_invoice = self.get_by_uuid(related_invoice_uuid)
            logger.info(
                "Processing payment complement relation | payment_invoice_uuid=%s | related_invoice_uuid=%s | importe_pagado=%.2f | invoice_found=%s",
                invoice.uuid,
                related_invoice_uuid,
                float(row.get("importe_pagado", 0) or 0),
                "yes" if related_invoice is not None else "no",
            )
            if related_invoice is None:
                missing_related.append(related_invoice_uuid)
                continue
            normalized_rows.append(
                PaymentComplementCreate(
                    user_id=invoice.user_id,
                    payment_invoice_id=invoice.id,
                    related_invoice_uuid=related_invoice_uuid,
                    fecha_pago=row.get("fecha_pago"),
                    moneda_pago=row.get("moneda_pago"),
                    tipo_cambio_pago=row.get("tipo_cambio_pago"),
                    monto_pago=row.get("monto_pago", 0) or 0,
                    parcialidad=row.get("parcialidad"),
                    saldo_anterior=row.get("saldo_anterior", 0) or 0,
                    importe_pagado=row.get("importe_pagado", 0) or 0,
                    saldo_insoluto=row.get("saldo_insoluto", 0) or 0,
                )
            )

        if missing_related:
            missing_joined = ", ".join(sorted(set(missing_related)))
            raise ValueError(
                "No se puede cargar el complemento de pago porque la factura relacionada no existe para este usuario: "
                f"{missing_joined}"
            )

        for item in normalized_rows:
            self.db.add(PaymentComplement(**item.model_dump()))
            logger.info(
                "Payment complement persisted | payment_invoice_uuid=%s | related_invoice_uuid=%s | importe_pagado=%.2f",
                invoice.uuid,
                item.related_invoice_uuid,
                float(item.importe_pagado or 0),
            )

    def recalculate_payment_status(self, invoice_uuid: str, user_id: int | None = None) -> Invoice | None:
        normalized_uuid = str(invoice_uuid or "").strip().upper()
        if not normalized_uuid:
            return None

        scoped_user_id = self.user_id if self.user_id is not None else user_id
        statement = select(Invoice).where(func.upper(Invoice.uuid) == normalized_uuid)
        if scoped_user_id is not None:
            statement = statement.where(Invoice.user_id == scoped_user_id)
        invoice = self.db.execute(statement).scalar_one_or_none()
        if invoice is None:
            logger.info(
                "Payment status recalculation skipped | related_invoice_uuid=%s | invoice_found=no",
                normalized_uuid,
            )
            return None

        if str(invoice.tipo_comprobante or "").upper() == "P":
            invoice.total_pagado = 0
            invoice.saldo_pendiente = 0
            invoice.estado_pago = "SIN_RELACION"
            self.db.flush()
            logger.info(
                "Payment status recalculated | invoice_uuid=%s | total_pagado=0.00 | saldo_pendiente=0.00 | estado_pago=%s",
                invoice.uuid,
                invoice.estado_pago,
            )
            return invoice

        complements = self.list_payment_complements_for_invoice_uuid(invoice.uuid)
        invoice_total = self._invoice_reference_total(invoice)
        if not complements:
            invoice.total_pagado = 0
            invoice.saldo_pendiente = round(invoice_total, 2)
            invoice.estado_pago = "PENDIENTE"
            self.db.flush()
            logger.info(
                "Payment status recalculated | invoice_uuid=%s | total_pagado=0.00 | saldo_pendiente=%.2f | estado_pago=%s",
                invoice.uuid,
                invoice.saldo_pendiente or 0,
                invoice.estado_pago,
            )
            return invoice

        latest_complement = sorted(
            complements,
            key=lambda item: (item.fecha_pago or "", item.created_at),
        )[-1]
        total_pagado = round(sum(float(item.importe_pagado or 0) for item in complements), 2)
        saldo_pendiente = round(float(latest_complement.saldo_insoluto or 0), 2)
        if saldo_pendiente <= 0:
            estado_pago = "PAGADA"
        elif total_pagado > 0:
            estado_pago = "PARCIAL"
        else:
            estado_pago = "PENDIENTE"

        invoice.total_pagado = total_pagado
        invoice.saldo_pendiente = max(saldo_pendiente, 0)
        invoice.estado_pago = estado_pago
        self.db.flush()
        logger.info(
            "Payment status recalculated | invoice_uuid=%s | total_pagado=%.2f | saldo_pendiente=%.2f | estado_pago=%s",
            invoice.uuid,
            invoice.total_pagado or 0,
            invoice.saldo_pendiente or 0,
            invoice.estado_pago,
        )
        return invoice

    def _sync_invoice_payment_status(self, invoice: Invoice) -> None:
        self.recalculate_payment_status(invoice.uuid, user_id=invoice.user_id)

    def list_payment_complements(self) -> list[PaymentComplement]:
        statement = self._scope_payment_statement(select(PaymentComplement)).order_by(
            PaymentComplement.created_at.desc()
        )
        return list(self.db.execute(statement).scalars().all())

    def list_payment_complements_for_invoices(self, invoices: list[Invoice]) -> list[PaymentComplement]:
        if not invoices:
            return []
        invoice_ids = [invoice.id for invoice in invoices]
        invoice_uuids = [str(invoice.uuid).strip().upper() for invoice in invoices if invoice.uuid]
        statement = self._scope_payment_statement(select(PaymentComplement)).where(
            (PaymentComplement.payment_invoice_id.in_(invoice_ids))
            | (func.upper(func.coalesce(PaymentComplement.related_invoice_uuid, "")).in_(invoice_uuids))
        ).order_by(PaymentComplement.created_at.desc())
        return list(self.db.execute(statement).scalars().all())

    def list_payment_complements_for_invoice_uuid(self, related_invoice_uuid: str) -> list[PaymentComplement]:
        normalized_uuid = str(related_invoice_uuid or "").strip().upper()
        statement = self._scope_payment_statement(select(PaymentComplement)).where(
            func.upper(func.coalesce(PaymentComplement.related_invoice_uuid, "")) == normalized_uuid
        )
        return list(self.db.execute(statement).scalars().all())

    def create(self, invoice_data: InvoiceCreate) -> Invoice:
        payload = invoice_data.model_dump()
        payment_complements = payload.pop("payment_complements", [])
        if self.user_id is not None:
            payload["user_id"] = self.user_id
        invoice = Invoice(**payload)
        self.db.add(invoice)
        self.db.flush()
        if str(invoice.tipo_comprobante or "").upper() == "P":
            self._persist_payment_complements(invoice, payment_complements)
            self._sync_invoice_payment_status(invoice)
            for item in payment_complements:
                related_invoice_uuid = str(item.get("related_invoice_uuid") or "").strip().upper()
                if not related_invoice_uuid:
                    continue
                self.recalculate_payment_status(related_invoice_uuid, user_id=invoice.user_id)
        else:
            self._sync_invoice_payment_status(invoice)
        self.db.commit()
        self.db.refresh(invoice)
        return invoice

    def get_by_id(self, invoice_id: int) -> Invoice | None:
        statement = self._scope_invoice_statement(select(Invoice)).where(Invoice.id == invoice_id)
        return self.db.execute(statement).scalar_one_or_none()

    def get_by_uuid(self, uuid: str) -> Invoice | None:
        normalized_uuid = str(uuid or "").strip().upper()
        statement = self._scope_invoice_statement(select(Invoice)).where(func.upper(Invoice.uuid) == normalized_uuid)
        return self.db.execute(statement).scalar_one_or_none()

    def get_recent_sat_validation(self, uuid: str, max_age_seconds: int) -> SatValidationCache | None:
        threshold = datetime.utcnow() - timedelta(seconds=max_age_seconds)
        statement = select(SatValidationCache).where(
            SatValidationCache.uuid == uuid,
            SatValidationCache.validated_at >= threshold,
        )
        return self.db.execute(statement).scalar_one_or_none()

    def save_sat_validation(self, uuid: str, estatus_sat: str, validated_at: datetime) -> SatValidationCache:
        cache_entry = self.db.execute(
            select(SatValidationCache).where(SatValidationCache.uuid == uuid)
        ).scalar_one_or_none()
        if cache_entry is None:
            cache_entry = SatValidationCache(
                uuid=uuid,
                estatus_sat=estatus_sat,
                validated_at=validated_at,
            )
            self.db.add(cache_entry)
        else:
            cache_entry.estatus_sat = estatus_sat
            cache_entry.validated_at = validated_at
        self.db.flush()
        return cache_entry

    def list_filtered(self, filters: InvoiceFilters | None = None, skip: int = 0, limit: int | None = 100) -> list[Invoice]:
        statement = self._scope_invoice_statement(select(Invoice))
        statement = self._apply_filters(statement, filters)
        statement = statement.order_by(Invoice.created_at.desc()).offset(skip)
        if limit is not None:
            statement = statement.limit(limit)
        return list(self.db.execute(statement).scalars().all())

    def list(self, skip: int = 0, limit: int = 100, filters: InvoiceFilters | None = None) -> list[Invoice]:
        return self.list_filtered(filters=filters, skip=skip, limit=limit)

    def list_all(self, filters: InvoiceFilters | None = None) -> list[Invoice]:
        return self.list_filtered(filters=filters, skip=0, limit=None)

    def exists_same_rfc_total(self, rfc_emisor: str, total: float) -> bool:
        statement = self._scope_invoice_statement(select(func.count(Invoice.id))).where(
            Invoice.rfc_emisor == rfc_emisor,
            func.round(cast(Invoice.total, Numeric), 2) == round(total, 2),
        )
        return bool(self.db.execute(statement).scalar_one())

    def get_provider_stats(self, rfc_emisor: str | None) -> dict[str, int]:
        if not rfc_emisor:
            return {"facturas": 0, "canceladas": 0}
        facturas = self.db.execute(
            self._scope_invoice_statement(select(func.count(Invoice.id))).where(
                Invoice.rfc_emisor == rfc_emisor
            )
        ).scalar_one()
        canceladas = self.db.execute(
            self._scope_invoice_statement(select(func.count(Invoice.id))).where(
                Invoice.rfc_emisor == rfc_emisor,
                func.upper(Invoice.estatus_sat) == "CANCELADO",
            )
        ).scalar_one()
        return {"facturas": int(facturas), "canceladas": int(canceladas)}

    def get_high_amount_threshold(self) -> float:
        threshold = self.db.execute(
            self._scope_invoice_statement(select(func.coalesce(func.avg(Invoice.total), 0)))
        ).scalar_one()
        return max(float(threshold or 0) * 2, 100000.0)

    def update_status_and_risk(
        self,
        invoice: Invoice,
        estatus_sat: str,
        riesgo: str,
        detalle_riesgo: str | None = None,
        sat_validado_at: datetime | None = None,
    ) -> Invoice:
        invoice.estatus_sat = estatus_sat
        invoice.riesgo = riesgo
        if detalle_riesgo is not None:
            invoice.detalle_riesgo = detalle_riesgo
        if sat_validado_at is not None:
            invoice.sat_validado_at = sat_validado_at
        self.db.commit()
        self.db.refresh(invoice)
        return invoice

    def delete(self, invoice: Invoice) -> None:
        if str(invoice.tipo_comprobante or "").upper() == "P":
            related_uuids = [
                related_uuid
                for related_uuid in {
                    item.related_invoice_uuid
                    for item in self.list_payment_complements()
                    if item.payment_invoice_id == invoice.id
                }
                if related_uuid
            ]
            statement = self._scope_payment_statement(select(PaymentComplement)).where(
                PaymentComplement.payment_invoice_id == invoice.id
            )
            for item in self.db.execute(statement).scalars().all():
                self.db.delete(item)
            self.db.delete(invoice)
            self.db.flush()
            for related_uuid in related_uuids:
                related_invoice = self.get_by_uuid(related_uuid)
                if related_invoice is not None:
                    self._sync_invoice_payment_status(related_invoice)
            self.db.commit()
            return
        self.db.delete(invoice)
        self.db.commit()

    def summary(self, filters: InvoiceFilters | None = None) -> dict[str, object]:
        invoices = self.list_all(filters=filters)
        return build_dashboard_summary(
            invoices,
            self.list_payment_complements_for_invoices(invoices),
        )

    def reports(self, filters: InvoiceFilters | None = None) -> dict[str, object]:
        invoices = self.list_all(filters=filters)
        return build_reports_bundle(
            invoices,
            self.list_payment_complements_for_invoices(invoices),
        )

    def unique_suppliers_count(self) -> int:
        statement = self._scope_invoice_statement(
            select(func.count(distinct(Invoice.rfc_emisor))).where(Invoice.rfc_emisor.is_not(None))
        )
        return int(self.db.execute(statement).scalar_one())

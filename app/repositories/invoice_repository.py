from __future__ import annotations

from datetime import datetime, timedelta

from sqlalchemy import Numeric, cast, distinct, func, select
from sqlalchemy.orm import Session

from app.models.invoice import Invoice
from app.models.sat_validation_cache import SatValidationCache
from app.schemas.invoice import InvoiceCreate
from app.services.reports_service import build_dashboard_summary, build_reports_bundle


class InvoiceRepository:
    def __init__(self, db: Session):
        self.db = db

    def create(self, invoice_data: InvoiceCreate) -> Invoice:
        invoice = Invoice(**invoice_data.model_dump())
        self.db.add(invoice)
        self.db.commit()
        self.db.refresh(invoice)
        return invoice

    def get_by_id(self, invoice_id: int) -> Invoice | None:
        return self.db.get(Invoice, invoice_id)

    def get_by_uuid(self, uuid: str) -> Invoice | None:
        statement = select(Invoice).where(Invoice.uuid == uuid)
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

    def list(self, skip: int = 0, limit: int = 100) -> list[Invoice]:
        statement = select(Invoice).order_by(Invoice.created_at.desc()).offset(skip).limit(limit)
        return list(self.db.execute(statement).scalars().all())

    def list_all(self) -> list[Invoice]:
        statement = select(Invoice).order_by(Invoice.created_at.desc())
        return list(self.db.execute(statement).scalars().all())

    def exists_same_rfc_total(self, rfc_emisor: str, total: float) -> bool:
        statement = select(func.count(Invoice.id)).where(
            Invoice.rfc_emisor == rfc_emisor,
            func.round(cast(Invoice.total, Numeric), 2) == round(total, 2),
        )
        return bool(self.db.execute(statement).scalar_one())

    def get_provider_stats(self, rfc_emisor: str | None) -> dict[str, int]:
        if not rfc_emisor:
            return {"facturas": 0, "canceladas": 0}
        facturas = self.db.execute(
            select(func.count(Invoice.id)).where(Invoice.rfc_emisor == rfc_emisor)
        ).scalar_one()
        canceladas = self.db.execute(
            select(func.count(Invoice.id)).where(
                Invoice.rfc_emisor == rfc_emisor,
                func.upper(Invoice.estatus_sat) == "CANCELADO",
            )
        ).scalar_one()
        return {"facturas": int(facturas), "canceladas": int(canceladas)}

    def get_high_amount_threshold(self) -> float:
        threshold = self.db.execute(select(func.coalesce(func.avg(Invoice.total), 0))).scalar_one()
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
        self.db.delete(invoice)
        self.db.commit()

    def summary(self) -> dict[str, object]:
        return build_dashboard_summary(self.list_all())

    def reports(self) -> dict[str, object]:
        return build_reports_bundle(self.list_all())

    def unique_suppliers_count(self) -> int:
        statement = select(func.count(distinct(Invoice.rfc_emisor))).where(Invoice.rfc_emisor.is_not(None))
        return int(self.db.execute(statement).scalar_one())

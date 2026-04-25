from datetime import datetime
from io import BytesIO

from fastapi import APIRouter, Depends
from fastapi.responses import StreamingResponse
from sqlalchemy.orm import Session

from app.api.deps import get_api_current_user, get_db
from app.models.user import User
from app.repositories.invoice_repository import InvoiceRepository
from app.schemas.dashboard import (
    ControlRow,
    DashboardSummary,
    FiscalRiskInvoiceRow,
    FiscalRiskMetricRow,
    FiscalRiskSupplierRow,
    MonthlySummary,
    ProviderSummary,
    ReportsBundle,
    RiskSummary,
)
from app.services.excel_exporter import generate_excel_report
from app.schemas.invoice import InvoiceFilters


router = APIRouter(prefix="/dashboard", tags=["dashboard"])


def get_invoice_filters(
    rfc_receptor: str | None = None,
    rfc_emisor: str | None = None,
    proveedor: str | None = None,
    estatus_sat: str | None = None,
    riesgo: str | None = None,
    moneda: str | None = None,
    fecha_desde: str | None = None,
    fecha_hasta: str | None = None,
) -> InvoiceFilters:
    return InvoiceFilters(
        rfc_receptor=rfc_receptor,
        rfc_emisor=rfc_emisor,
        proveedor=proveedor,
        estatus_sat=estatus_sat,
        riesgo=riesgo,
        moneda=moneda,
        fecha_desde=fecha_desde,
        fecha_hasta=fecha_hasta,
    )


@router.get("/summary", response_model=DashboardSummary)
def get_summary(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_api_current_user),
    filters: InvoiceFilters = Depends(get_invoice_filters),
) -> dict[str, float | int]:
    return InvoiceRepository(db, user_id=current_user.id).summary(filters=filters)


@router.get("/reports", response_model=ReportsBundle)
def get_reports(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_api_current_user),
    filters: InvoiceFilters = Depends(get_invoice_filters),
) -> dict[str, object]:
    return InvoiceRepository(db, user_id=current_user.id).reports(filters=filters)["reports"]


@router.get("/reports/resumen", response_model=list[MonthlySummary])
def get_resumen_report(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_api_current_user),
    filters: InvoiceFilters = Depends(get_invoice_filters),
) -> list[dict[str, object]]:
    return InvoiceRepository(db, user_id=current_user.id).reports(filters=filters)["reports"]["resumen"]


@router.get("/reports/control", response_model=list[ControlRow])
def get_control_report(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_api_current_user),
    filters: InvoiceFilters = Depends(get_invoice_filters),
) -> list[dict[str, object]]:
    return InvoiceRepository(db, user_id=current_user.id).reports(filters=filters)["reports"]["control"]


@router.get("/reports/proveedores", response_model=list[ProviderSummary])
def get_proveedores_report(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_api_current_user),
    filters: InvoiceFilters = Depends(get_invoice_filters),
) -> list[dict[str, object]]:
    return InvoiceRepository(db, user_id=current_user.id).reports(filters=filters)["reports"]["proveedores"]


@router.get("/reports/riesgos", response_model=list[RiskSummary])
def get_riesgos_report(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_api_current_user),
    filters: InvoiceFilters = Depends(get_invoice_filters),
) -> list[dict[str, object]]:
    return InvoiceRepository(db, user_id=current_user.id).reports(filters=filters)["reports"]["riesgos"]


@router.get("/reports/rr1", response_model=list[FiscalRiskInvoiceRow])
def get_rr1_report(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_api_current_user),
    filters: InvoiceFilters = Depends(get_invoice_filters),
) -> list[dict[str, object]]:
    return InvoiceRepository(db, user_id=current_user.id).reports(filters=filters)["reports"]["rr1"]


@router.get("/reports/rr9", response_model=list[FiscalRiskSupplierRow])
def get_rr9_report(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_api_current_user),
    filters: InvoiceFilters = Depends(get_invoice_filters),
) -> list[dict[str, object]]:
    return InvoiceRepository(db, user_id=current_user.id).reports(filters=filters)["reports"]["rr9"]


@router.get("/reports/resumen-riesgos", response_model=list[FiscalRiskMetricRow])
def get_resumen_riesgos_report(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_api_current_user),
    filters: InvoiceFilters = Depends(get_invoice_filters),
) -> list[dict[str, object]]:
    return InvoiceRepository(db, user_id=current_user.id).reports(filters=filters)["reports"]["resumen_riesgos"]


@router.get("/export-excel", response_model=None)
def export_excel_report(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_api_current_user),
    filters: InvoiceFilters = Depends(get_invoice_filters),
) -> StreamingResponse:
    reports_bundle = InvoiceRepository(db, user_id=current_user.id).reports(filters=filters)
    workbook_bytes = generate_excel_report(reports_bundle)
    filename = f"facturas_v3_{datetime.now().strftime('%Y%m%d_%H%M%S')}.xlsx"
    return StreamingResponse(
        BytesIO(workbook_bytes),
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        headers={
            "Content-Disposition": f'attachment; filename="{filename}"',
        },
    )


@router.get("/export-rr1-excel", response_model=None)
def export_rr1_excel_report(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_api_current_user),
    filters: InvoiceFilters = Depends(get_invoice_filters),
) -> StreamingResponse:
    reports_bundle = InvoiceRepository(db, user_id=current_user.id).reports(filters=filters)
    workbook_bytes = generate_excel_report(reports_bundle, report_mode="rr1")
    filename = f"cfdi_shield_rr1_{datetime.now().strftime('%Y%m%d_%H%M%S')}.xlsx"
    return StreamingResponse(
        BytesIO(workbook_bytes),
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )


@router.get("/export-rr9-excel", response_model=None)
def export_rr9_excel_report(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_api_current_user),
    filters: InvoiceFilters = Depends(get_invoice_filters),
) -> StreamingResponse:
    reports_bundle = InvoiceRepository(db, user_id=current_user.id).reports(filters=filters)
    workbook_bytes = generate_excel_report(reports_bundle, report_mode="rr9")
    filename = f"cfdi_shield_rr9_{datetime.now().strftime('%Y%m%d_%H%M%S')}.xlsx"
    return StreamingResponse(
        BytesIO(workbook_bytes),
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )

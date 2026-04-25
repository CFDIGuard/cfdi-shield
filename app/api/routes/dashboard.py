from datetime import datetime
from io import BytesIO

from fastapi import APIRouter, Depends
from fastapi.responses import StreamingResponse
from sqlalchemy.orm import Session

from app.api.deps import get_db
from app.repositories.invoice_repository import InvoiceRepository
from app.schemas.dashboard import (
    ControlRow,
    DashboardSummary,
    MonthlySummary,
    ProviderSummary,
    ReportsBundle,
    RiskSummary,
)
from app.services.excel_exporter import generate_excel_report


router = APIRouter(prefix="/dashboard", tags=["dashboard"])


@router.get("/summary", response_model=DashboardSummary)
def get_summary(db: Session = Depends(get_db)) -> dict[str, float | int]:
    return InvoiceRepository(db).summary()


@router.get("/reports", response_model=ReportsBundle)
def get_reports(db: Session = Depends(get_db)) -> dict[str, object]:
    return InvoiceRepository(db).reports()["reports"]


@router.get("/reports/resumen", response_model=list[MonthlySummary])
def get_resumen_report(db: Session = Depends(get_db)) -> list[dict[str, object]]:
    return InvoiceRepository(db).reports()["reports"]["resumen"]


@router.get("/reports/control", response_model=list[ControlRow])
def get_control_report(db: Session = Depends(get_db)) -> list[dict[str, object]]:
    return InvoiceRepository(db).reports()["reports"]["control"]


@router.get("/reports/proveedores", response_model=list[ProviderSummary])
def get_proveedores_report(db: Session = Depends(get_db)) -> list[dict[str, object]]:
    return InvoiceRepository(db).reports()["reports"]["proveedores"]


@router.get("/reports/riesgos", response_model=list[RiskSummary])
def get_riesgos_report(db: Session = Depends(get_db)) -> list[dict[str, object]]:
    return InvoiceRepository(db).reports()["reports"]["riesgos"]


@router.get("/export-excel", response_model=None)
def export_excel_report(db: Session = Depends(get_db)) -> StreamingResponse:
    reports_bundle = InvoiceRepository(db).reports()
    workbook_bytes = generate_excel_report(reports_bundle)
    filename = f"facturas_v3_{datetime.now().strftime('%Y%m%d_%H%M%S')}.xlsx"
    return StreamingResponse(
        BytesIO(workbook_bytes),
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        headers={
            "Content-Disposition": f'attachment; filename="{filename}"',
        },
    )

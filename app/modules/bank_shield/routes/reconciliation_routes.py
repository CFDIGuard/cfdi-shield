from __future__ import annotations

import logging
from io import BytesIO
from urllib.parse import urlencode

from fastapi import APIRouter, Depends, File, Request, UploadFile, status
from fastapi.responses import HTMLResponse, JSONResponse, RedirectResponse, StreamingResponse
from sqlalchemy.orm import Session

from app.core.config import settings
from app.db.session import get_db
from app.modules.bank_shield.adapters.dashboard_adapter import build_reconciliation_dashboard_payload
from app.modules.bank_shield.adapters.excel_adapter import build_reconciliation_export_rows
from app.modules.bank_shield.adapters.invoice_adapter import build_invoice_options
from app.modules.bank_shield.adapters.invoice_search_adapter import build_invoice_search_results
from app.models.bank_transaction import BankTransaction
from app.models.user import User
from app.modules.bank_shield.repositories.bank_transaction_repository import BankTransactionRepository
from app.modules.bank_shield.services.reconciliation_service import (
    process_bank_statement_upload,
)
from app.repositories.invoice_repository import InvoiceRepository
from app.schemas.bank_reconciliation import BankReconciliationFilters
from app.services.excel_exporter import generate_excel_report
from app.services.security_utils import mask_username
from app.templates import templates
from app.web.utils import web_url
from app.web_deps import get_current_user


logger = logging.getLogger(__name__)
router = APIRouter()

MIN_LIMIT = 1
DEFAULT_LIMIT = 20
MAX_LIMIT = 50


def _security_event(
    event: str,
    *,
    current_user: User | None = None,
    filename: str | None = None,
    result: str = "ok",
    detail: str | None = None,
) -> None:
    logger.info(
        "security_event=%s result=%s user=%s org=%s file=%s detail=%s",
        event,
        result,
        mask_username(current_user.username) if current_user is not None else "-",
        "-",
        filename or "-",
        detail or "-",
    )


def _build_reconciliation_filters(
    estado: str | None = None,
    origen: str | None = None,
    busqueda: str | None = None,
) -> BankReconciliationFilters:
    return BankReconciliationFilters(
        estado=estado,
        origen=origen,
        busqueda=busqueda,
    )


def _reconciliation_query_suffix(filters: BankReconciliationFilters) -> str:
    cleaned = filters.cleaned()
    if not cleaned:
        return ""
    return f"?{urlencode(cleaned)}"


def _transaction_payload(transaction: BankTransaction, invoice_repository: InvoiceRepository) -> dict[str, object]:
    matched_invoice = (
        invoice_repository.get_by_id(transaction.matched_invoice_id)
        if transaction.matched_invoice_id is not None
        else None
    )
    return {
        "id": transaction.id,
        "descripcion": transaction.descripcion,
        "referencia": transaction.referencia,
        "match_status": transaction.match_status,
        "match_score": float(transaction.match_score or 0),
        "match_reason": transaction.match_reason,
        "origen": transaction.origen,
        "matched_invoice_id": transaction.matched_invoice_id,
        "matched_invoice_uuid": matched_invoice.uuid if matched_invoice is not None else None,
        "matched_invoice_provider": matched_invoice.razon_social if matched_invoice is not None else None,
    }


@router.post("/reconciliation/upload", response_model=None)
def upload_bank_statement_web(
    file: UploadFile | None = File(default=None),
    db: Session = Depends(get_db),
    current_user: User | None = Depends(get_current_user),
):
    if current_user is None:
        return RedirectResponse(url="/login", status_code=status.HTTP_303_SEE_OTHER)
    if file is None or not file.filename:
        return RedirectResponse(
            url=web_url("/reconciliation", error="Debes seleccionar un archivo CSV o XLSX."),
            status_code=status.HTTP_303_SEE_OTHER,
        )

    filename = file.filename
    if not filename.lower().endswith((".csv", ".xlsx")):
        return RedirectResponse(
            url=web_url("/reconciliation", error="Solo se aceptan estados bancarios CSV o XLSX."),
            status_code=status.HTTP_303_SEE_OTHER,
        )

    file_bytes = file.file.read()
    if len(file_bytes) > settings.max_upload_size_bytes:
        return RedirectResponse(
            url=web_url("/reconciliation", error="El archivo excede el tamano maximo permitido."),
            status_code=status.HTTP_303_SEE_OTHER,
        )

    try:
        summary = process_bank_statement_upload(
            db=db,
            user_id=current_user.id,
            file_bytes=file_bytes,
            filename=filename,
        )
        _security_event(
            "bank_statement_upload",
            current_user=current_user,
            filename=filename,
            result="stored",
            detail="bank_statement_processed",
        )
    except ValueError as exc:
        db.rollback()
        _security_event(
            "bank_statement_upload",
            current_user=current_user,
            filename=filename,
            result="rejected",
            detail="validation_error",
        )
        return RedirectResponse(
            url=web_url("/reconciliation", error=str(exc)),
            status_code=status.HTTP_303_SEE_OTHER,
        )
    except Exception as exc:
        db.rollback()
        logger.exception("Unexpected error processing bank statement %s: %s", filename, exc)
        _security_event(
            "bank_statement_upload",
            current_user=current_user,
            filename=filename,
            result="unexpected_error",
            detail="exception",
        )
        return RedirectResponse(
            url=web_url("/reconciliation", error="No fue posible procesar el estado bancario."),
            status_code=status.HTTP_303_SEE_OTHER,
        )

    return RedirectResponse(
        url=web_url(
            "/reconciliation",
            message=(
                "Estado bancario procesado: "
                f"{summary['conciliados']} conciliados, "
                f"{summary['posibles']} posibles, "
                f"{summary['pendientes']} pendientes."
            ),
        ),
        status_code=status.HTTP_303_SEE_OTHER,
    )


@router.get("/api/reconciliation/invoices/search", response_model=None)
def search_reconciliation_invoices(
    q: str = "",
    limit: int = DEFAULT_LIMIT,
    db: Session = Depends(get_db),
    current_user: User | None = Depends(get_current_user),
):
    if current_user is None:
        return JSONResponse(status_code=401, content={"detail": "Not authenticated"})

    query = str(q or "").strip()
    if len(query) < 2:
        return JSONResponse(status_code=400, content={"detail": "Debes capturar al menos 2 caracteres"})

    safe_limit = max(MIN_LIMIT, min(int(limit or DEFAULT_LIMIT), MAX_LIMIT))
    items = build_invoice_search_results(
        db,
        current_user.id,
        query=query,
        limit=safe_limit,
    )
    return {"items": items}


@router.get("/reconciliation", response_class=HTMLResponse, response_model=None)
def reconciliation_web(
    request: Request,
    message: str | None = None,
    error: str | None = None,
    estado: str | None = None,
    origen: str | None = None,
    busqueda: str | None = None,
    db: Session = Depends(get_db),
    current_user: User | None = Depends(get_current_user),
):
    if current_user is None:
        return RedirectResponse(url="/login", status_code=status.HTTP_303_SEE_OTHER)

    reconciliation_filters = _build_reconciliation_filters(
        estado=estado,
        origen=origen,
        busqueda=busqueda,
    )
    query_suffix = _reconciliation_query_suffix(reconciliation_filters)
    dashboard_payload = build_reconciliation_dashboard_payload(
        db,
        current_user.id,
        filters=reconciliation_filters,
    )
    return templates.TemplateResponse(
        request,
        "reconciliation.html",
        {
            "current_user": current_user,
            "message": message,
            "error": error,
            "summary": dashboard_payload["summary"],
            "rows": dashboard_payload["rows"],
            "invoice_options": build_invoice_options(db, current_user.id),
            "reconciliation_filters": reconciliation_filters,
            "reconciliation_export_url": f"/reconciliation/export-excel{query_suffix}",
        },
    )


@router.get("/reconciliation/export-excel", response_model=None)
def export_reconciliation_excel(
    estado: str | None = None,
    origen: str | None = None,
    busqueda: str | None = None,
    db: Session = Depends(get_db),
    current_user: User | None = Depends(get_current_user),
):
    if current_user is None:
        return RedirectResponse(url="/login", status_code=status.HTTP_303_SEE_OTHER)

    reconciliation_filters = _build_reconciliation_filters(
        estado=estado,
        origen=origen,
        busqueda=busqueda,
    )
    reports_bundle = InvoiceRepository(db, user_id=current_user.id).reports()
    workbook_bytes = generate_excel_report(
        reports_bundle,
        reconciliation_rows=build_reconciliation_export_rows(
            db,
            current_user.id,
            filters=reconciliation_filters,
        ),
    )
    filename = f"cfdi_shield_conciliacion_{current_user.id}.xlsx"
    return StreamingResponse(
        BytesIO(workbook_bytes),
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        headers={"Content-Disposition": f'attachment; filename=\"{filename}\"'},
    )


@router.post("/reconciliation/confirm/{transaction_id}", response_model=None)
def confirm_reconciliation(
    transaction_id: int,
    estado: str | None = None,
    origen: str | None = None,
    busqueda: str | None = None,
    db: Session = Depends(get_db),
    current_user: User | None = Depends(get_current_user),
):
    if current_user is None:
        return JSONResponse(status_code=401, content={"detail": "Not authenticated"})

    bank_repository = BankTransactionRepository(db, user_id=current_user.id)
    invoice_repository = InvoiceRepository(db, user_id=current_user.id)
    transaction = bank_repository.get_by_id(transaction_id)
    if transaction is None:
        return JSONResponse(status_code=404, content={"detail": "Movimiento no encontrado"})
    if transaction.matched_invoice_id is None:
        return JSONResponse(status_code=400, content={"detail": "No hay CFDI sugerido para confirmar"})
    if invoice_repository.get_by_id(transaction.matched_invoice_id) is None:
        return JSONResponse(status_code=404, content={"detail": "El CFDI sugerido ya no esta disponible"})

    transaction.match_status = "CONCILIADO"
    transaction.match_score = max(float(transaction.match_score or 0), 80.0)
    transaction.match_reason = "Confirmado manualmente"
    transaction.origen = "MANUAL"
    bank_repository.save(transaction)
    filters = _build_reconciliation_filters(estado=estado, origen=origen, busqueda=busqueda)
    return JSONResponse(
        content={
            "ok": True,
            "transaction": _transaction_payload(transaction, invoice_repository),
            "summary": bank_repository.summary(filters=filters),
        }
    )


@router.post("/reconciliation/reject/{transaction_id}", response_model=None)
def reject_reconciliation(
    transaction_id: int,
    estado: str | None = None,
    origen: str | None = None,
    busqueda: str | None = None,
    db: Session = Depends(get_db),
    current_user: User | None = Depends(get_current_user),
):
    if current_user is None:
        return JSONResponse(status_code=401, content={"detail": "Not authenticated"})

    bank_repository = BankTransactionRepository(db, user_id=current_user.id)
    invoice_repository = InvoiceRepository(db, user_id=current_user.id)
    transaction = bank_repository.get_by_id(transaction_id)
    if transaction is None:
        return JSONResponse(status_code=404, content={"detail": "Movimiento no encontrado"})

    transaction.match_status = "PENDIENTE"
    transaction.matched_invoice_id = None
    transaction.match_score = 0
    transaction.match_reason = "Marcado como no conciliable"
    transaction.origen = "MANUAL"
    bank_repository.save(transaction)
    filters = _build_reconciliation_filters(estado=estado, origen=origen, busqueda=busqueda)
    return JSONResponse(
        content={
            "ok": True,
            "transaction": _transaction_payload(transaction, invoice_repository),
            "summary": bank_repository.summary(filters=filters),
        }
    )


@router.post("/reconciliation/assign/{transaction_id}", response_model=None)
def assign_reconciliation(
    transaction_id: int,
    invoice_id: int,
    estado: str | None = None,
    origen: str | None = None,
    busqueda: str | None = None,
    db: Session = Depends(get_db),
    current_user: User | None = Depends(get_current_user),
):
    if current_user is None:
        return JSONResponse(status_code=401, content={"detail": "Not authenticated"})

    bank_repository = BankTransactionRepository(db, user_id=current_user.id)
    invoice_repository = InvoiceRepository(db, user_id=current_user.id)
    transaction = bank_repository.get_by_id(transaction_id)
    if transaction is None:
        return JSONResponse(status_code=404, content={"detail": "Movimiento no encontrado"})

    invoice = invoice_repository.get_by_id(invoice_id)
    if invoice is None:
        return JSONResponse(status_code=404, content={"detail": "No puedes asignar un CFDI de otro usuario"})

    transaction.match_status = "CONCILIADO"
    transaction.matched_invoice_id = invoice.id
    transaction.match_score = max(float(transaction.match_score or 0), 80.0)
    transaction.match_reason = "Confirmado manualmente"
    transaction.origen = "MANUAL"
    bank_repository.save(transaction)
    filters = _build_reconciliation_filters(estado=estado, origen=origen, busqueda=busqueda)
    return JSONResponse(
        content={
            "ok": True,
            "transaction": _transaction_payload(transaction, invoice_repository),
            "summary": bank_repository.summary(filters=filters),
        }
    )

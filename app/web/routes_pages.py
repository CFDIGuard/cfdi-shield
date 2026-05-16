import logging
import math
from io import BytesIO
from urllib.parse import urlencode

from fastapi import APIRouter, Depends, File, Form, Request, UploadFile, status
from fastapi.responses import HTMLResponse, JSONResponse, RedirectResponse, StreamingResponse
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.csrf import require_csrf
from app.db.session import get_db
from app.models.user import User
from app.repositories.invoice_repository import InvoiceRepository
from app.repositories.user_repository import UserRepository
from app.modules.bank_shield.routes.reconciliation_routes import router as reconciliation_router
from app.schemas.invoice import InvoiceFilters
from app.services.bank_reconciliation_service import get_reconciliation_summary
from app.services.excel_exporter import generate_excel_report
from app.services.invoice_processor import InvoiceProcessingError, procesar_factura
from app.services.notification_service import email_ready_for_delivery
from app.services.security_utils import mask_username, mask_uuid
from app.templates import templates
from app.services.xml_parser import parse_cfdi_xml
from app.web.utils import web_url
from app.web_deps import get_current_user


logger = logging.getLogger(__name__)
router = APIRouter(tags=["web"], dependencies=[Depends(require_csrf)])
router.include_router(reconciliation_router)


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


def _build_invoice_filters(
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


def _query_suffix(filters: InvoiceFilters) -> str:
    cleaned = filters.cleaned()
    if not cleaned:
        return ""
    return f"?{urlencode(cleaned)}"


def _dashboard_redirect(filters: InvoiceFilters, **params: str) -> str:
    merged = filters.cleaned()
    merged.update({key: value for key, value in params.items() if value is not None})
    if not merged:
        return "/dashboard-web"
    return f"/dashboard-web?{urlencode(merged)}"


def _invoice_list_redirect(filters: InvoiceFilters, page: int = 1, **params: str | int) -> str:
    merged = filters.cleaned()
    if page > 1:
        merged["page"] = str(page)
    merged.update({key: str(value) for key, value in params.items() if value is not None})
    if not merged:
        return "/invoices"
    return f"/invoices?{urlencode(merged)}"


def _invoice_option(invoice) -> dict[str, object]:
    total_mxn = invoice.total_mxn if invoice.total_mxn is not None else (invoice.total_original or invoice.total or 0)
    return {
        "id": invoice.id,
        "label": f"{invoice.uuid} | {invoice.razon_social or '-'} | ${float(total_mxn or 0):,.2f}",
    }


def _collect_uploads(files: list[UploadFile] | None, file: UploadFile | None) -> list[UploadFile]:
    uploads: list[UploadFile] = []
    if files:
        uploads.extend(files)
    if file is not None:
        uploads.append(file)
    return uploads


def _build_upload_summary_message(
    nuevas: int,
    duplicadas: int,
    invalidas: int,
    errores: int,
) -> str:
    return (
        f"Carga completada: {nuevas} nuevas, "
        f"{duplicadas} duplicadas, "
        f"{invalidas} invalidas, "
        f"{errores} errores."
    )


def _format_upload_detail(filename: str, stage: str, reason: str) -> str:
    safe_name = filename or "sin_nombre"
    safe_stage = stage or "unknown"
    safe_reason = reason or "Error no especificado"
    return f"{safe_name} | {safe_stage} | {safe_reason}"


def _is_duplicate_integrity_error(exc: IntegrityError) -> bool:
    message = str(exc).lower()
    duplicate_markers = (
        "duplicate key",
        "unique constraint",
        "unique failed",
        "already exists",
        "ix_invoices_user_uuid_unique",
        "invoices_uuid_key",
        "invoices.uuid",
    )
    return any(marker in message for marker in duplicate_markers)


def _sat_mode_view(current_user: User) -> tuple[bool, str]:
    if settings.local_mode:
        return False, "Desactivado por LOCAL_MODE. Las nuevas cargas usaran estado local."
    if not settings.enable_sat_validation:
        return False, "Desactivado por configuracion global. Las nuevas cargas usaran estado local."
    if not current_user.use_sat_validation:
        return False, "Desactivado para este usuario. Las nuevas cargas usaran estado local sin consultar SAT."
    return True, "Activado para este usuario. Las nuevas cargas consultaran SAT cuando aplique."


def _two_factor_view(current_user: User) -> tuple[bool, str, bool]:
    if not settings.enable_two_factor:
        return False, "2FA desactivado en esta demo.", False
    if not email_ready_for_delivery():
        if current_user.two_factor_enabled:
            return True, "2FA requiere configuracion de correo para volver a activarse por correo.", True
        return False, "2FA requiere configuracion de correo.", False
    if current_user.two_factor_enabled:
        return True, "Proteccion por correo activa para este usuario.", True
    return False, "Disponible para activarse con envio por correo.", True


@router.get("/", response_class=HTMLResponse, response_model=None)
def index(
    request: Request,
    message: str | None = None,
    error: str | None = None,
    current_user: User | None = Depends(get_current_user),
):
    if current_user is None:
        return RedirectResponse(url="/login", status_code=status.HTTP_303_SEE_OTHER)

    return templates.TemplateResponse(
        request,
        "index.html",
        {
            "message": message,
            "error": error,
            "current_user": current_user,
            "demo_mode": settings.demo_mode,
            "allow_real_xml_upload": settings.allow_real_xml_upload,
        },
    )


@router.get("/landing", response_class=HTMLResponse, response_model=None)
def landing(request: Request):
    return templates.TemplateResponse(
        request,
        "landing.html",
        {},
    )


@router.post("/upload", response_model=None)
def upload_xml_web(
    files: list[UploadFile] | None = File(default=None),
    file: UploadFile | None = File(default=None),
    db: Session = Depends(get_db),
    current_user: User | None = Depends(get_current_user),
):
    if current_user is None:
        return RedirectResponse(url="/login", status_code=status.HTTP_303_SEE_OTHER)

    uploads = _collect_uploads(files, file)
    if not uploads:
        return RedirectResponse(
            url=web_url("/", error="Debes seleccionar al menos un archivo XML."),
            status_code=status.HTTP_303_SEE_OTHER,
        )

    if len(uploads) > settings.max_files_per_upload:
        return RedirectResponse(
            url=web_url(
                "/",
                error=f"Solo puedes subir hasta {settings.max_files_per_upload} archivos por carga.",
            ),
            status_code=status.HTTP_303_SEE_OTHER,
        )

    if settings.demo_mode and not settings.allow_real_xml_upload:
        return RedirectResponse(
            url=web_url(
                "/",
                error="La carga de CFDI esta desactivada en esta demo publica.",
            ),
            status_code=status.HTTP_303_SEE_OTHER,
        )

    repository = InvoiceRepository(db, user_id=current_user.id)
    nuevas = 0
    duplicadas = 0
    invalidas = 0
    errores = 0
    detail_lines: list[str] = []

    batch_uuids: set[str] = set()
    for current_file in uploads:
        filename = current_file.filename or ""
        if not filename.lower().endswith(".xml"):
            invalidas += 1
            logger.warning("Rejected non-XML upload: %s", filename or "sin_nombre")
            _security_event(
                "xml_upload",
                current_user=current_user,
                filename=filename,
                result="rejected_extension",
                detail="extension_no_permitida",
            )
            detail_lines.append(
                _format_upload_detail(filename, "parse_xml", "Extension no permitida")
            )
            continue

        content = current_file.file.read()
        if len(content) > settings.max_upload_size_bytes:
            invalidas += 1
            logger.warning("Rejected oversized XML upload: %s", filename)
            _security_event(
                "xml_upload",
                current_user=current_user,
                filename=filename,
                result="rejected_size",
                detail="tamano_excedido",
            )
            detail_lines.append(
                _format_upload_detail(
                    filename,
                    "parse_xml",
                    "Archivo excede el tamano maximo permitido",
                )
            )
            continue

        try:
            parsed_invoice = parse_cfdi_xml(content, filename=filename)
        except ValueError as exc:
            invalidas += 1
            logger.warning("Invalid XML upload: %s", exc)
            _security_event(
                "xml_upload",
                current_user=current_user,
                filename=filename,
                result="parse_failed",
                detail="xml_invalido",
            )
            detail_lines.append(_format_upload_detail(filename, "parse_xml", str(exc)))
            continue

        if parsed_invoice.uuid in batch_uuids:
            duplicadas += 1
            _security_event(
                "xml_upload",
                current_user=current_user,
                filename=filename,
                result="duplicate",
                detail="uuid_duplicado_en_lote",
            )
            detail_lines.append(
                _format_upload_detail(
                    filename,
                    "duplicate_check",
                    f"UUID duplicado dentro de la misma carga (...{parsed_invoice.uuid[-8:]})",
                )
            )
            continue

        existing_invoice = repository.get_by_uuid(parsed_invoice.uuid)
        if existing_invoice is not None:
            duplicadas += 1
            _security_event(
                "xml_upload",
                current_user=current_user,
                filename=filename,
                result="duplicate",
                detail="uuid_ya_existente",
            )
            detail_lines.append(
                _format_upload_detail(
                    filename,
                    "duplicate_check",
                    f"UUID ya existe en base de datos (...{parsed_invoice.uuid[-8:]})",
                )
            )
            continue

        batch_uuids.add(parsed_invoice.uuid)

        try:
            invoice_data = procesar_factura(
                content,
                repository=repository,
                filename=filename,
                use_sat_validation=current_user.use_sat_validation,
                user_id=current_user.id,
            )
            repository.create(invoice_data)
            nuevas += 1
            _security_event(
                "xml_upload",
                current_user=current_user,
                filename=filename,
                result="stored",
                detail="cfdi_procesado",
            )
        except InvoiceProcessingError as exc:
            db.rollback()
            if exc.stage == "parse_xml":
                invalidas += 1
            else:
                errores += 1
            _security_event(
                "xml_upload",
                current_user=current_user,
                filename=filename,
                result="processing_failed",
                detail=exc.stage,
            )
            detail_lines.append(
                _format_upload_detail(
                    exc.filename or filename,
                    exc.stage,
                    exc.message,
                )
            )
        except ValueError as exc:
            db.rollback()
            invalidas += 1
            logger.warning("Business rule rejected XML upload: %s", exc)
            _security_event(
                "xml_upload",
                current_user=current_user,
                filename=filename,
                result="business_rule_rejected",
                detail="payment_relation",
            )
            detail_lines.append(_format_upload_detail(filename, "payment_relation", str(exc)))
        except IntegrityError as exc:
            db.rollback()
            duplicadas += 1
            _security_event(
                "xml_upload",
                current_user=current_user,
                filename=filename,
                result="duplicate",
                detail="database_duplicate",
            )
            if _is_duplicate_integrity_error(exc):
                detail_lines.append(
                    _format_upload_detail(
                        filename,
                        "duplicate_check",
                        "UUID ya existe para este usuario",
                    )
                )
            else:
                detail_lines.append(
                    _format_upload_detail(
                        filename,
                        "database_insert",
                        "Conflicto de base de datos al guardar la factura",
                    )
                )
        except Exception as exc:
            db.rollback()
            errores += 1
            logger.exception("Unexpected error processing XML upload %s: %s", filename, exc)
            _security_event(
                "xml_upload",
                current_user=current_user,
                filename=filename,
                result="unexpected_error",
                detail="exception",
            )
            detail_lines.append(_format_upload_detail(filename, "unknown", str(exc)))

    return RedirectResponse(
        url=web_url(
            "/dashboard-web",
            message=_build_upload_summary_message(nuevas, duplicadas, invalidas, errores),
            details="\n".join(detail_lines[:20]) if detail_lines else None,
        ),
        status_code=status.HTTP_303_SEE_OTHER,
    )


@router.get("/dashboard-web", response_class=HTMLResponse, response_model=None)
def dashboard_web(
    request: Request,
    message: str | None = None,
    error: str | None = None,
    details: str | None = None,
    rfc_receptor: str | None = None,
    rfc_emisor: str | None = None,
    proveedor: str | None = None,
    estatus_sat: str | None = None,
    riesgo: str | None = None,
    moneda: str | None = None,
    fecha_desde: str | None = None,
    fecha_hasta: str | None = None,
    db: Session = Depends(get_db),
    current_user: User | None = Depends(get_current_user),
):
    if current_user is None:
        return RedirectResponse(url="/login", status_code=status.HTTP_303_SEE_OTHER)

    filters = _build_invoice_filters(
        rfc_receptor=rfc_receptor,
        rfc_emisor=rfc_emisor,
        proveedor=proveedor,
        estatus_sat=estatus_sat,
        riesgo=riesgo,
        moneda=moneda,
        fecha_desde=fecha_desde,
        fecha_hasta=fecha_hasta,
    )
    query_suffix = _query_suffix(filters)
    repository = InvoiceRepository(db, user_id=current_user.id)
    reports_bundle = repository.reports(filters=filters)
    summary = reports_bundle["summary"]
    invoices = repository.list(limit=8, filters=filters)
    reconciliation_summary = get_reconciliation_summary(db, current_user.id)
    sat_mode_effective, sat_mode_note = _sat_mode_view(current_user)
    two_factor_effective, two_factor_note, can_toggle_two_factor = _two_factor_view(current_user)

    return templates.TemplateResponse(
        request,
        "dashboard.html",
        {
            "summary": summary,
            "reports": reports_bundle["reports"],
            "invoices": invoices,
            "message": message,
            "error": error,
            "details": details,
            "current_user": current_user,
            "filters": filters,
            "reconciliation_summary": reconciliation_summary,
            "use_sat_validation": current_user.use_sat_validation,
            "sat_mode_effective": sat_mode_effective,
            "sat_mode_note": sat_mode_note,
            "two_factor_effective": two_factor_effective,
            "two_factor_note": two_factor_note,
            "can_toggle_two_factor": can_toggle_two_factor,
            "demo_mode": settings.demo_mode,
            "allow_real_xml_upload": settings.allow_real_xml_upload,
            "dashboard_url": f"/dashboard-web{query_suffix}",
            "all_invoices_url": _invoice_list_redirect(filters),
            "alertas_cfdi_url": f"/reports/alertas-cfdi{query_suffix}",
            "analisis_proveedor_url": f"/reports/analisis-proveedor{query_suffix}",
            "rr1_url": f"/reports/rr1{query_suffix}",
            "rr9_url": f"/reports/rr9{query_suffix}",
            "export_excel_url": f"/api/v1/dashboard/export-excel{query_suffix}",
            "export_alertas_cfdi_url": f"/api/v1/dashboard/export-alertas-cfdi-excel{query_suffix}",
            "export_analisis_proveedor_url": f"/api/v1/dashboard/export-analisis-proveedor-excel{query_suffix}",
            "export_rr1_url": f"/api/v1/dashboard/export-rr1-excel{query_suffix}",
            "export_rr9_url": f"/api/v1/dashboard/export-rr9-excel{query_suffix}",
        },
    )


@router.get("/invoices", response_class=HTMLResponse, response_model=None)
def invoices_web(
    request: Request,
    message: str | None = None,
    error: str | None = None,
    page: int = 1,
    rfc_receptor: str | None = None,
    rfc_emisor: str | None = None,
    proveedor: str | None = None,
    estatus_sat: str | None = None,
    riesgo: str | None = None,
    moneda: str | None = None,
    fecha_desde: str | None = None,
    fecha_hasta: str | None = None,
    db: Session = Depends(get_db),
    current_user: User | None = Depends(get_current_user),
):
    if current_user is None:
        return RedirectResponse(url="/login", status_code=status.HTTP_303_SEE_OTHER)

    page_size = 25
    current_page = max(page, 1)
    filters = _build_invoice_filters(
        rfc_receptor=rfc_receptor,
        rfc_emisor=rfc_emisor,
        proveedor=proveedor,
        estatus_sat=estatus_sat,
        riesgo=riesgo,
        moneda=moneda,
        fecha_desde=fecha_desde,
        fecha_hasta=fecha_hasta,
    )
    repository = InvoiceRepository(db, user_id=current_user.id)
    total_items = repository.count_filtered(filters=filters)
    total_pages = max(1, math.ceil(total_items / page_size)) if total_items else 1
    if current_page > total_pages:
        current_page = total_pages
    skip = (current_page - 1) * page_size
    invoices = repository.list(skip=skip, limit=page_size, filters=filters)

    return templates.TemplateResponse(
        request,
        "invoices_list.html",
        {
            "current_user": current_user,
            "message": message,
            "error": error,
            "filters": filters,
            "invoices": invoices,
            "page": current_page,
            "page_size": page_size,
            "total_items": total_items,
            "total_pages": total_pages,
            "dashboard_url": _dashboard_redirect(filters),
            "all_invoices_url": _invoice_list_redirect(filters, current_page),
            "prev_page_url": _invoice_list_redirect(filters, current_page - 1) if current_page > 1 else None,
            "next_page_url": _invoice_list_redirect(filters, current_page + 1) if current_page < total_pages else None,
        },
    )


def _render_alertas_cfdi_report(
    request: Request,
    rfc_receptor: str | None = None,
    rfc_emisor: str | None = None,
    proveedor: str | None = None,
    estatus_sat: str | None = None,
    riesgo: str | None = None,
    moneda: str | None = None,
    fecha_desde: str | None = None,
    fecha_hasta: str | None = None,
    db: Session = Depends(get_db),
    current_user: User | None = Depends(get_current_user),
):
    if current_user is None:
        return RedirectResponse(url="/login", status_code=status.HTTP_303_SEE_OTHER)

    filters = _build_invoice_filters(
        rfc_receptor=rfc_receptor,
        rfc_emisor=rfc_emisor,
        proveedor=proveedor,
        estatus_sat=estatus_sat,
        riesgo=riesgo,
        moneda=moneda,
        fecha_desde=fecha_desde,
        fecha_hasta=fecha_hasta,
    )
    query_suffix = _query_suffix(filters)
    repository = InvoiceRepository(db, user_id=current_user.id)
    reports_bundle = repository.reports(filters=filters)
    return templates.TemplateResponse(
        request,
        "report_alertas_cfdi.html",
        {
            "current_user": current_user,
            "rows": reports_bundle["reports"]["alertas_cfdi"],
            "summary": reports_bundle["summary"],
            "dashboard_url": f"/dashboard-web{query_suffix}",
            "alertas_cfdi_url": f"/reports/alertas-cfdi{query_suffix}",
            "analisis_proveedor_url": f"/reports/analisis-proveedor{query_suffix}",
            "export_alertas_cfdi_url": f"/api/v1/dashboard/export-alertas-cfdi-excel{query_suffix}",
        },
    )


@router.get("/reports/alertas-cfdi", response_class=HTMLResponse, response_model=None)
@router.get("/reports/rr1", response_class=HTMLResponse, response_model=None)
def report_alertas_cfdi_web(
    request: Request,
    rfc_receptor: str | None = None,
    rfc_emisor: str | None = None,
    proveedor: str | None = None,
    estatus_sat: str | None = None,
    riesgo: str | None = None,
    moneda: str | None = None,
    fecha_desde: str | None = None,
    fecha_hasta: str | None = None,
    db: Session = Depends(get_db),
    current_user: User | None = Depends(get_current_user),
):
    return _render_alertas_cfdi_report(
        request=request,
        rfc_receptor=rfc_receptor,
        rfc_emisor=rfc_emisor,
        proveedor=proveedor,
        estatus_sat=estatus_sat,
        riesgo=riesgo,
        moneda=moneda,
        fecha_desde=fecha_desde,
        fecha_hasta=fecha_hasta,
        db=db,
        current_user=current_user,
    )


def _render_analisis_proveedor_report(
    request: Request,
    rfc_receptor: str | None = None,
    rfc_emisor: str | None = None,
    proveedor: str | None = None,
    estatus_sat: str | None = None,
    riesgo: str | None = None,
    moneda: str | None = None,
    fecha_desde: str | None = None,
    fecha_hasta: str | None = None,
    db: Session = Depends(get_db),
    current_user: User | None = Depends(get_current_user),
):
    if current_user is None:
        return RedirectResponse(url="/login", status_code=status.HTTP_303_SEE_OTHER)

    filters = _build_invoice_filters(
        rfc_receptor=rfc_receptor,
        rfc_emisor=rfc_emisor,
        proveedor=proveedor,
        estatus_sat=estatus_sat,
        riesgo=riesgo,
        moneda=moneda,
        fecha_desde=fecha_desde,
        fecha_hasta=fecha_hasta,
    )
    query_suffix = _query_suffix(filters)
    repository = InvoiceRepository(db, user_id=current_user.id)
    reports_bundle = repository.reports(filters=filters)
    return templates.TemplateResponse(
        request,
        "report_analisis_proveedor.html",
        {
            "current_user": current_user,
            "rows": reports_bundle["reports"]["analisis_proveedor"],
            "summary": reports_bundle["summary"],
            "dashboard_url": f"/dashboard-web{query_suffix}",
            "alertas_cfdi_url": f"/reports/alertas-cfdi{query_suffix}",
            "analisis_proveedor_url": f"/reports/analisis-proveedor{query_suffix}",
            "export_analisis_proveedor_url": f"/api/v1/dashboard/export-analisis-proveedor-excel{query_suffix}",
        },
    )


@router.get("/reports/analisis-proveedor", response_class=HTMLResponse, response_model=None)
@router.get("/reports/rr9", response_class=HTMLResponse, response_model=None)
def report_analisis_proveedor_web(
    request: Request,
    rfc_receptor: str | None = None,
    rfc_emisor: str | None = None,
    proveedor: str | None = None,
    estatus_sat: str | None = None,
    riesgo: str | None = None,
    moneda: str | None = None,
    fecha_desde: str | None = None,
    fecha_hasta: str | None = None,
    db: Session = Depends(get_db),
    current_user: User | None = Depends(get_current_user),
):
    return _render_analisis_proveedor_report(
        request=request,
        rfc_receptor=rfc_receptor,
        rfc_emisor=rfc_emisor,
        proveedor=proveedor,
        estatus_sat=estatus_sat,
        riesgo=riesgo,
        moneda=moneda,
        fecha_desde=fecha_desde,
        fecha_hasta=fecha_hasta,
        db=db,
        current_user=current_user,
    )


@router.post("/sat-validation/toggle", response_model=None)
def toggle_sat_validation(
    current_user: User | None = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    if current_user is None:
        return RedirectResponse(url="/login", status_code=status.HTTP_303_SEE_OTHER)

    repository = UserRepository(db)
    updated_user = repository.set_use_sat_validation(current_user, not current_user.use_sat_validation)
    if updated_user.use_sat_validation:
        message = "Modo SAT activado. Las nuevas cargas consultaran SAT cuando aplique."
    else:
        message = "Modo SAT desactivado. Las nuevas cargas usaran estado local sin consultar SAT."
    return RedirectResponse(
        url=web_url("/dashboard-web", message=message),
        status_code=status.HTTP_303_SEE_OTHER,
    )


@router.post("/invoices/recalculate-payment-statuses", response_model=None)
def recalculate_all_payment_statuses_web(
    rfc_receptor: str | None = None,
    rfc_emisor: str | None = None,
    proveedor: str | None = None,
    estatus_sat: str | None = None,
    riesgo: str | None = None,
    moneda: str | None = None,
    fecha_desde: str | None = None,
    fecha_hasta: str | None = None,
    current_user: User | None = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    if current_user is None:
        return RedirectResponse(url="/login", status_code=status.HTTP_303_SEE_OTHER)

    filters = _build_invoice_filters(
        rfc_receptor=rfc_receptor,
        rfc_emisor=rfc_emisor,
        proveedor=proveedor,
        estatus_sat=estatus_sat,
        riesgo=riesgo,
        moneda=moneda,
        fecha_desde=fecha_desde,
        fecha_hasta=fecha_hasta,
    )
    repository = InvoiceRepository(db, user_id=current_user.id)
    try:
        recalculated = repository.recalculate_all_payment_statuses(user_id=current_user.id)
        db.commit()
    except Exception:
        db.rollback()
        logger.exception(
            "Bulk payment status recalculation failed | user=%s",
            mask_username(current_user.username),
        )
        return RedirectResponse(
            url=_dashboard_redirect(filters, error="No fue posible recalcular los estados de pago."),
            status_code=status.HTTP_303_SEE_OTHER,
        )

    return RedirectResponse(
        url=_dashboard_redirect(
            filters,
            message=f"Estados de pago recalculados correctamente ({recalculated} facturas).",
        ),
        status_code=status.HTTP_303_SEE_OTHER,
    )


@router.post("/invoices/{invoice_id}/recalculate-payment-status", response_model=None)
def recalculate_payment_status_web(
    invoice_id: int,
    rfc_receptor: str | None = None,
    rfc_emisor: str | None = None,
    proveedor: str | None = None,
    estatus_sat: str | None = None,
    riesgo: str | None = None,
    moneda: str | None = None,
    fecha_desde: str | None = None,
    fecha_hasta: str | None = None,
    current_user: User | None = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    if current_user is None:
        return RedirectResponse(url="/login", status_code=status.HTTP_303_SEE_OTHER)

    filters = _build_invoice_filters(
        rfc_receptor=rfc_receptor,
        rfc_emisor=rfc_emisor,
        proveedor=proveedor,
        estatus_sat=estatus_sat,
        riesgo=riesgo,
        moneda=moneda,
        fecha_desde=fecha_desde,
        fecha_hasta=fecha_hasta,
    )
    repository = InvoiceRepository(db, user_id=current_user.id)
    invoice = repository.get_by_id(invoice_id)
    if invoice is None:
        return RedirectResponse(
            url=_dashboard_redirect(filters, error="La factura ya no existe."),
            status_code=status.HTTP_303_SEE_OTHER,
        )

    try:
        repository.recalculate_payment_status(invoice.uuid, current_user.id)
        db.commit()
    except Exception:
        db.rollback()
        logger.exception(
            "Manual payment status recalculation failed | user=%s | invoice_id=%s | uuid=%s",
            mask_username(current_user.username),
            invoice.id,
            mask_uuid(invoice.uuid),
        )
        return RedirectResponse(
            url=_dashboard_redirect(filters, error="No fue posible recalcular el estado de pago."),
            status_code=status.HTTP_303_SEE_OTHER,
        )

    return RedirectResponse(
        url=_dashboard_redirect(filters, message="Estado de pago recalculado correctamente."),
        status_code=status.HTTP_303_SEE_OTHER,
    )


@router.post("/invoices/{invoice_id}/delete", response_model=None)
def delete_invoice(
    invoice_id: int,
    redirect_to: str | None = Form(default=None),
    page: int = Form(default=1),
    rfc_receptor: str | None = Form(default=None),
    rfc_emisor: str | None = Form(default=None),
    proveedor: str | None = Form(default=None),
    estatus_sat: str | None = Form(default=None),
    riesgo: str | None = Form(default=None),
    moneda: str | None = Form(default=None),
    fecha_desde: str | None = Form(default=None),
    fecha_hasta: str | None = Form(default=None),
    current_user: User | None = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    if current_user is None:
        return RedirectResponse(url="/login", status_code=status.HTTP_303_SEE_OTHER)

    filters = _build_invoice_filters(
        rfc_receptor=rfc_receptor,
        rfc_emisor=rfc_emisor,
        proveedor=proveedor,
        estatus_sat=estatus_sat,
        riesgo=riesgo,
        moneda=moneda,
        fecha_desde=fecha_desde,
        fecha_hasta=fecha_hasta,
    )
    if redirect_to == "invoices":
        redirect_builder = lambda **params: _invoice_list_redirect(filters, page=page, **params)
    else:
        redirect_builder = lambda **params: _dashboard_redirect(filters, **params)
    repository = InvoiceRepository(db, user_id=current_user.id)
    invoice = repository.get_by_id(invoice_id)
    if invoice is None:
        return RedirectResponse(
            url=redirect_builder(error="La factura ya no existe."),
            status_code=status.HTTP_303_SEE_OTHER,
        )

    logger.info(
        "Invoice deleted by user=%s invoice_id=%s uuid=%s",
        mask_username(current_user.username),
        invoice.id,
        mask_uuid(invoice.uuid),
    )
    try:
        repository.delete(invoice)
    except ValueError as exc:
        db.rollback()
        logger.warning(
            "Invoice delete blocked | user=%s | invoice_id=%s | uuid=%s | reason=%s",
            mask_username(current_user.username),
            invoice.id,
            mask_uuid(invoice.uuid),
            str(exc),
        )
        return RedirectResponse(
            url=redirect_builder(error=str(exc)),
            status_code=status.HTTP_303_SEE_OTHER,
        )
    except Exception as exc:
        db.rollback()
        logger.exception(
            "Invoice delete failed | user=%s | invoice_id=%s | uuid=%s",
            mask_username(current_user.username),
            invoice.id,
            mask_uuid(invoice.uuid),
        )
        return RedirectResponse(
            url=redirect_builder(error="No fue posible eliminar la factura en este momento."),
            status_code=status.HTTP_303_SEE_OTHER,
        )
    return RedirectResponse(
        url=redirect_builder(message="Factura eliminada correctamente."),
        status_code=status.HTTP_303_SEE_OTHER,
    )

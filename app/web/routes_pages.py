import logging

from fastapi import APIRouter, Depends, File, Request, UploadFile, status
from fastapi.responses import HTMLResponse, RedirectResponse
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.core.config import settings
from app.db.session import get_db
from app.models.user import User
from app.repositories.invoice_repository import InvoiceRepository
from app.repositories.user_repository import UserRepository
from app.services.invoice_processor import InvoiceProcessingError, procesar_factura
from app.templates import templates
from app.services.xml_parser import parse_cfdi_xml
from app.web.utils import web_url
from app.web_deps import get_current_user


logger = logging.getLogger(__name__)
router = APIRouter(tags=["web"])


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


def _sat_mode_view(current_user: User) -> tuple[bool, str]:
    if settings.local_mode:
        return False, "Desactivado por LOCAL_MODE. Las nuevas cargas usaran estado local."
    if not settings.enable_sat_validation:
        return False, "Desactivado por configuracion global. Las nuevas cargas usaran estado local."
    if not current_user.use_sat_validation:
        return False, "Desactivado para este usuario. Las nuevas cargas usaran estado local sin consultar SAT."
    return True, "Activado para este usuario. Las nuevas cargas consultaran SAT cuando aplique."


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

    repository = InvoiceRepository(db)
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
            detail_lines.append(
                _format_upload_detail(filename, "parse_xml", "Extension no permitida")
            )
            continue

        content = current_file.file.read()
        if len(content) > settings.max_upload_size_bytes:
            invalidas += 1
            logger.warning("Rejected oversized XML upload: %s", filename)
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
            detail_lines.append(_format_upload_detail(filename, "parse_xml", str(exc)))
            continue

        if parsed_invoice.uuid in batch_uuids:
            duplicadas += 1
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
            )
            repository.create(invoice_data)
            nuevas += 1
        except InvoiceProcessingError as exc:
            db.rollback()
            if exc.stage == "parse_xml":
                invalidas += 1
            else:
                errores += 1
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
            logger.warning("Invalid XML upload during processing: %s", exc)
            detail_lines.append(_format_upload_detail(filename, "parse_xml", str(exc)))
        except IntegrityError:
            db.rollback()
            duplicadas += 1
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
    db: Session = Depends(get_db),
    current_user: User | None = Depends(get_current_user),
):
    if current_user is None:
        return RedirectResponse(url="/login", status_code=status.HTTP_303_SEE_OTHER)

    repository = InvoiceRepository(db)
    reports_bundle = repository.reports()
    summary = reports_bundle["summary"]
    invoices = repository.list(limit=8)
    sat_mode_effective, sat_mode_note = _sat_mode_view(current_user)

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
            "use_sat_validation": current_user.use_sat_validation,
            "sat_mode_effective": sat_mode_effective,
            "sat_mode_note": sat_mode_note,
        },
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


@router.post("/invoices/{invoice_id}/delete", response_model=None)
def delete_invoice(
    invoice_id: int,
    current_user: User | None = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    if current_user is None:
        return RedirectResponse(url="/login", status_code=status.HTTP_303_SEE_OTHER)

    repository = InvoiceRepository(db)
    invoice = repository.get_by_id(invoice_id)
    if invoice is None:
        return RedirectResponse(
            url=web_url("/dashboard-web", error="La factura ya no existe."),
            status_code=status.HTTP_303_SEE_OTHER,
        )

    logger.info(
        "Invoice deleted by user=%s invoice_id=%s uuid=%s",
        current_user.username,
        invoice.id,
        f"...{invoice.uuid[-8:]}" if invoice.uuid else "",
    )
    repository.delete(invoice)
    return RedirectResponse(
        url=web_url("/dashboard-web", message="Factura eliminada correctamente."),
        status_code=status.HTTP_303_SEE_OTHER,
    )

from datetime import datetime

from fastapi import APIRouter, Depends, File, HTTPException, UploadFile, status
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.api.deps import get_api_current_user, get_db
from app.repositories.invoice_repository import InvoiceRepository
from app.models.user import User
from app.schemas.invoice import InvoiceFilters, InvoiceResponse, InvoiceUploadResponse
from app.services.invoice_processor import procesar_factura
from app.services.risk_engine import build_risk_detail, calculate_risk_level, detect_invoice_risk_types
from app.services.sat_validator import get_sat_validator
from app.services.xml_parser import parse_cfdi_xml


router = APIRouter(prefix="/invoices", tags=["invoices"])


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


@router.post(
    "/upload",
    response_model=InvoiceUploadResponse,
    status_code=status.HTTP_201_CREATED,
)
def upload_xml(
    file: UploadFile = File(...),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_api_current_user),
) -> dict[str, object]:
    if not file.filename or not file.filename.lower().endswith(".xml"):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="El archivo debe ser un XML.",
        )

    content = file.file.read()
    repository = InvoiceRepository(db, user_id=current_user.id)

    try:
        parsed_invoice = parse_cfdi_xml(content, filename=file.filename)
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc

    existing_invoice = repository.get_by_uuid(parsed_invoice.uuid)
    if existing_invoice is not None:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Ya existe una factura con ese UUID.",
        )

    try:
        invoice_data = procesar_factura(
            content,
            repository=repository,
            filename=file.filename,
            use_sat_validation=current_user.use_sat_validation,
            user_id=current_user.id,
        )
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc

    try:
        invoice = repository.create(invoice_data)
    except ValueError as exc:
        db.rollback()
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc
    except IntegrityError as exc:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Ya existe una factura con ese UUID.",
        ) from exc

    return {"status": "ok", "data": invoice}


@router.get("", response_model=list[InvoiceResponse])
def list_invoices(
    skip: int = 0,
    limit: int = 100,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_api_current_user),
    filters: InvoiceFilters = Depends(get_invoice_filters),
) -> list[InvoiceResponse]:
    limit = min(limit, 500)
    return InvoiceRepository(db, user_id=current_user.id).list(skip=skip, limit=limit, filters=filters)


@router.get("/by-uuid/{uuid}", response_model=InvoiceResponse)
def get_invoice_by_uuid(
    uuid: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_api_current_user),
) -> InvoiceResponse:
    invoice = InvoiceRepository(db, user_id=current_user.id).get_by_uuid(uuid)
    if invoice is None or str(invoice.tipo_comprobante or "").upper() == "P":
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Factura no encontrada.")
    return invoice


@router.get("/{invoice_id}", response_model=InvoiceResponse)
def get_invoice(
    invoice_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_api_current_user),
) -> InvoiceResponse:
    invoice = InvoiceRepository(db, user_id=current_user.id).get_by_id(invoice_id)
    if invoice is None or str(invoice.tipo_comprobante or "").upper() == "P":
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Factura no encontrada.")
    return invoice


@router.post("/{invoice_id}/refresh-sat-status", response_model=InvoiceResponse)
def refresh_sat_status(
    invoice_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_api_current_user),
) -> InvoiceResponse:
    repository = InvoiceRepository(db, user_id=current_user.id)
    invoice = repository.get_by_id(invoice_id)
    if invoice is None or str(invoice.tipo_comprobante or "").upper() == "P":
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Factura no encontrada.")

    sat_validator = get_sat_validator()
    sat_result = sat_validator.validar(
        uuid=invoice.uuid,
        rfc_emisor=invoice.rfc_emisor,
        rfc_receptor=invoice.rfc_receptor,
        total=invoice.total,
        force_refresh=True,
    )
    sat_validado_at = (
        datetime.utcfromtimestamp(sat_result.validated_at_epoch)
        if sat_result.validated_at_epoch is not None
        else None
    )
    if sat_validado_at is not None:
        repository.save_sat_validation(invoice.uuid, sat_result.estatus, sat_validado_at)
    provider_stats = repository.get_provider_stats(invoice.rfc_emisor)
    risk_types = detect_invoice_risk_types(
        invoice=invoice,
        estatus_sat=sat_result.estatus,
        provider_invoice_count=provider_stats["facturas"],
        provider_cancelled_count=provider_stats["canceladas"],
        has_same_rfc_total=(
            False
            if str(invoice.tipo_comprobante or "").upper() == "P"
            else repository.exists_same_rfc_total(invoice.rfc_emisor or "", invoice.total)
        ),
        high_amount_threshold=repository.get_high_amount_threshold(),
    )
    riesgo = calculate_risk_level(risk_types, sat_result.estatus, invoice.total)
    return repository.update_status_and_risk(
        invoice,
        estatus_sat=sat_result.estatus,
        riesgo=riesgo,
        detalle_riesgo=build_risk_detail(risk_types),
        sat_validado_at=sat_validado_at,
    )

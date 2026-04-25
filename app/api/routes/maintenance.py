from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session

from app.api.deps import get_db
from app.core.config import settings
from app.services.invoice_maintenance_service import (
    assign_invoices_to_user,
    get_invoice_ownership_diagnostics,
    repair_invoice_constraints,
)


router = APIRouter(prefix="/admin/maintenance", tags=["maintenance"])


def _require_maintenance_token(token: str | None) -> None:
    if not settings.admin_maintenance_token or token != settings.admin_maintenance_token:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Not found.")


@router.get("/invoice-ownership", response_model=None)
def invoice_ownership(
    token: str = Query(...),
):
    _require_maintenance_token(token)
    return get_invoice_ownership_diagnostics()


@router.post("/assign-orphan-invoices", response_model=None)
def assign_orphan_invoices(
    token: str = Query(...),
    email: str = Query(...),
    db: Session = Depends(get_db),
):
    _require_maintenance_token(token)
    try:
        return assign_invoices_to_user(db=db, email=email, assign_all=False)
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc


@router.post("/repair-invoice-constraints", response_model=None)
def repair_constraints(
    token: str = Query(...),
):
    _require_maintenance_token(token)
    return repair_invoice_constraints()

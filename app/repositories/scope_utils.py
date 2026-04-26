from __future__ import annotations

from sqlalchemy import and_, or_, select
from sqlalchemy.orm import Session

from app.models.organization import OrganizationMembership


def resolve_user_organization_id(db: Session, user_id: int | None) -> int | None:
    if user_id is None:
        return None

    statement = (
        select(OrganizationMembership.organization_id)
        .where(OrganizationMembership.user_id == user_id)
        .order_by((OrganizationMembership.role == "OWNER").desc(), OrganizationMembership.id.asc())
        .limit(1)
    )
    return db.execute(statement).scalar_one_or_none()


def apply_owner_scope(statement, model, *, user_id: int | None, organization_id: int | None):
    # Durante la transicion, organization_id es el eje principal cuando existe.
    # Para compatibilidad con datos historicos aun no migrados, si el registro no
    # tiene organization_id se permite fallback por user_id.
    if organization_id is not None and user_id is not None:
        return statement.where(
            or_(
                model.organization_id == organization_id,
                and_(model.organization_id.is_(None), model.user_id == user_id),
            )
        )
    if organization_id is not None:
        return statement.where(model.organization_id == organization_id)
    if user_id is not None:
        return statement.where(model.user_id == user_id)
    return statement

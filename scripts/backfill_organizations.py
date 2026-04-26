from __future__ import annotations

import argparse
import logging
import sys
from dataclasses import dataclass
from pathlib import Path

from sqlalchemy import select, text
from sqlalchemy.orm import Session

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from app.db.init_db import ensure_db_initialized
from app.db.session import SessionLocal
from app.models.organization import Organization, OrganizationMembership
from app.models.user import User


logger = logging.getLogger("backfill_organizations")


@dataclass
class BackfillResult:
    users_processed: int = 0
    organizations_created: int = 0
    memberships_created: int = 0
    invoices_updated: int = 0
    payment_complements_updated: int = 0
    bank_transactions_updated: int = 0


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description=(
            "Crea una organization por usuario existente, genera memberships OWNER "
            "y asigna organization_id en datos historicos."
        )
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Solo muestra lo que haria sin confirmar cambios en la base.",
    )
    parser.add_argument(
        "--user-id",
        type=int,
        help="Limita el backfill a un solo usuario.",
    )
    return parser


def _organization_slug(user: User) -> str:
    return f"org-user-{user.id}"


def _organization_name(user: User) -> str:
    return f"Organizacion de {user.username}"


def _resolve_canonical_organization(db: Session, user: User, result: BackfillResult) -> Organization:
    slug = _organization_slug(user)
    organization = db.execute(
        select(Organization).where(Organization.slug == slug)
    ).scalar_one_or_none()
    if organization is not None:
        return organization

    organization = db.execute(
        select(Organization)
        .join(OrganizationMembership, OrganizationMembership.organization_id == Organization.id)
        .where(
            OrganizationMembership.user_id == user.id,
            OrganizationMembership.role == "OWNER",
        )
        .order_by(OrganizationMembership.id.asc())
    ).scalar_one_or_none()
    if organization is not None:
        return organization

    organization = Organization(name=_organization_name(user), slug=slug)
    db.add(organization)
    db.flush()
    result.organizations_created += 1
    logger.info(
        "Organization creada | user_id=%s | organization_id=%s | slug=%s",
        user.id,
        organization.id,
        organization.slug,
    )
    return organization


def _ensure_owner_membership(
    db: Session,
    user: User,
    organization: Organization,
    result: BackfillResult,
) -> None:
    membership = db.execute(
        select(OrganizationMembership).where(
            OrganizationMembership.organization_id == organization.id,
            OrganizationMembership.user_id == user.id,
        )
    ).scalar_one_or_none()
    if membership is not None:
        return

    db.add(
        OrganizationMembership(
            organization_id=organization.id,
            user_id=user.id,
            role="OWNER",
        )
    )
    db.flush()
    result.memberships_created += 1
    logger.info(
        "Membership OWNER creada | user_id=%s | organization_id=%s",
        user.id,
        organization.id,
    )


def _backfill_user_data(
    db: Session,
    user: User,
    organization: Organization,
    result: BackfillResult,
) -> None:
    invoices_updated = db.execute(
        text(
            "UPDATE invoices "
            "SET organization_id = :organization_id "
            "WHERE user_id = :user_id AND organization_id IS NULL"
        ),
        {"organization_id": organization.id, "user_id": user.id},
    ).rowcount or 0
    payment_complements_updated = db.execute(
        text(
            "UPDATE payment_complements "
            "SET organization_id = :organization_id "
            "WHERE user_id = :user_id AND organization_id IS NULL"
        ),
        {"organization_id": organization.id, "user_id": user.id},
    ).rowcount or 0
    bank_transactions_updated = db.execute(
        text(
            "UPDATE bank_transactions "
            "SET organization_id = :organization_id "
            "WHERE user_id = :user_id AND organization_id IS NULL"
        ),
        {"organization_id": organization.id, "user_id": user.id},
    ).rowcount or 0

    result.invoices_updated += int(invoices_updated)
    result.payment_complements_updated += int(payment_complements_updated)
    result.bank_transactions_updated += int(bank_transactions_updated)

    logger.info(
        (
            "Backfill aplicado | user_id=%s | organization_id=%s | "
            "invoices=%s | payment_complements=%s | bank_transactions=%s"
        ),
        user.id,
        organization.id,
        invoices_updated,
        payment_complements_updated,
        bank_transactions_updated,
    )


def _load_users(db: Session, user_id: int | None) -> list[User]:
    statement = select(User).order_by(User.id.asc())
    if user_id is not None:
        statement = statement.where(User.id == user_id)
    return list(db.execute(statement).scalars().all())


def _run(user_id: int | None, dry_run: bool) -> BackfillResult:
    ensure_db_initialized()
    result = BackfillResult()

    with SessionLocal() as db:
        users = _load_users(db, user_id)
        result.users_processed = len(users)
        logger.info(
            "Inicio de backfill de organizations | usuarios=%s | dry_run=%s",
            len(users),
            dry_run,
        )

        try:
            for user in users:
                organization = _resolve_canonical_organization(db, user, result)
                _ensure_owner_membership(db, user, organization, result)
                _backfill_user_data(db, user, organization, result)

            if dry_run:
                db.rollback()
                logger.info("Dry run completado; todos los cambios fueron revertidos.")
            else:
                db.commit()
                logger.info("Backfill completado y confirmado en base de datos.")
        except Exception:
            db.rollback()
            logger.exception("Backfill de organizations fallido; se hizo rollback completo.")
            raise

    return result


def main() -> int:
    parser = _build_parser()
    args = parser.parse_args()

    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s | %(levelname)s | %(name)s | %(message)s",
    )

    result = _run(user_id=args.user_id, dry_run=args.dry_run)
    print(f"Usuarios procesados: {result.users_processed}")
    print(f"Organizations creadas: {result.organizations_created}")
    print(f"Memberships creadas: {result.memberships_created}")
    print(f"Invoices actualizadas: {result.invoices_updated}")
    print(f"Payment complements actualizados: {result.payment_complements_updated}")
    print(f"Bank transactions actualizadas: {result.bank_transactions_updated}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

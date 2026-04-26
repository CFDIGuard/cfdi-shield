from __future__ import annotations

import argparse
import logging
import sys
from pathlib import Path

from sqlalchemy import func, select

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from app.db.init_db import ensure_db_initialized
from app.db.session import SessionLocal
from app.models.invoice import Invoice
from app.repositories.invoice_repository import InvoiceRepository


logger = logging.getLogger("recalculate_payment_statuses")


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Recalcula total_pagado, saldo_pendiente y estado_pago para facturas historicas."
    )
    target = parser.add_mutually_exclusive_group(required=True)
    target.add_argument("--all", action="store_true", help="Recalcula para todos los usuarios.")
    target.add_argument("--user-id", type=int, help="Recalcula solo para un usuario especifico.")
    return parser


def _preview(db, user_id: int | None) -> list[Invoice]:
    statement = select(Invoice).where(func.upper(func.coalesce(Invoice.tipo_comprobante, "I")) != "P")
    if user_id is not None:
        statement = statement.where(Invoice.user_id == user_id)
    statement = statement.order_by(Invoice.user_id.asc(), Invoice.created_at.asc(), Invoice.id.asc())
    return list(db.execute(statement).scalars().all())


def _run(user_id: int | None) -> int:
    ensure_db_initialized()
    with SessionLocal() as db:
        repository = InvoiceRepository(db, user_id=user_id)
        candidates = _preview(db, user_id)
        scope_label = "todos los usuarios" if user_id is None else f"user_id={user_id}"
        logger.info("Inicio de recalculo historico | alcance=%s | facturas=%s", scope_label, len(candidates))
        for invoice in candidates:
            logger.info("Pendiente de recalculo | invoice_uuid=%s | user_id=%s", invoice.uuid, invoice.user_id)
        try:
            recalculated = repository.recalculate_all_payment_statuses(user_id=user_id)
            db.commit()
        except Exception:
            db.rollback()
            logger.exception("El recalculo historico fallo y se hizo rollback completo | alcance=%s", scope_label)
            raise

        logger.info("Recalculo historico finalizado | alcance=%s | facturas=%s", scope_label, recalculated)
        return recalculated


def main() -> int:
    parser = _build_parser()
    args = parser.parse_args()

    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s | %(levelname)s | %(name)s | %(message)s",
    )

    user_id = None if args.all else args.user_id
    recalculated = _run(user_id=user_id)
    print(f"Facturas recalculadas: {recalculated}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

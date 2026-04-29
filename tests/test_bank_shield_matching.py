from __future__ import annotations

from types import SimpleNamespace

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.db.base import Base
from app.repositories.bank_transaction_repository import BankTransactionRepository
from app.repositories.invoice_repository import InvoiceRepository
from app.repositories.user_repository import UserRepository
from app.schemas.invoice import InvoiceCreate
from app.services.auth_service import hash_password
from app.services.bank_reconciliation_service import process_bank_statement_upload, reconcile_transactions
from app.services.bank_statement_parser import ParsedBankTransaction


def _make_db(tmp_path):
    db_path = tmp_path / "bank_shield_matching.db"
    engine = create_engine(f"sqlite:///{db_path}", connect_args={"check_same_thread": False})
    session_local = sessionmaker(bind=engine, autoflush=False, autocommit=False)
    Base.metadata.drop_all(bind=engine)
    Base.metadata.create_all(bind=engine)
    return engine, session_local


def _invoice_stub(
    *,
    invoice_id: int,
    uuid: str,
    total_mxn: float,
    razon_social: str,
    rfc_emisor: str,
    fecha_emision: str = "2026-04-25T10:00:00",
):
    return SimpleNamespace(
        id=invoice_id,
        uuid=uuid,
        total_mxn=total_mxn,
        total_original=total_mxn,
        total=total_mxn,
        moneda="MXN",
        moneda_original="MXN",
        razon_social=razon_social,
        rfc_emisor=rfc_emisor,
        fecha_emision=fecha_emision,
    )


def _transaction(
    *,
    descripcion: str,
    referencia: str | None,
    monto: float,
    fecha: str = "2026-04-25",
    raw_hash: str = "tx-hash",
):
    return ParsedBankTransaction(
        fecha=fecha,
        descripcion=descripcion,
        referencia=referencia,
        cargo=0.0,
        abono=monto,
        monto=monto,
        tipo_movimiento="ABONO",
        moneda="MXN",
        raw_hash=raw_hash,
    )


def _make_invoice(user_id: int, uuid: str, total: float, razon_social: str) -> InvoiceCreate:
    return InvoiceCreate(
        user_id=user_id,
        uuid=uuid,
        archivo=f"{uuid}.xml",
        razon_social=razon_social,
        rfc_emisor="AAA010101AAA",
        rfc_receptor="BBB010101BBB",
        folio="F-1",
        fecha_emision="2026-04-25T10:00:00",
        mes="2026-04",
        subtotal=total,
        total=total,
        total_original=total,
        iva=0,
        iva_retenido=0,
        isr_retenido=0,
        moneda="MXN",
        moneda_original="MXN",
        tipo_cambio_xml=None,
        tipo_cambio_usado=1,
        total_mxn=total,
        fuente_tipo_cambio="MXN",
        fecha_tipo_cambio="2026-04-25",
        metodo_pago="PUE",
        estatus_sat="VIGENTE",
        riesgo="BAJO",
        score_proveedor=0,
        detalle_riesgo="",
        sat_validado_at=None,
    )


def test_uuid_exact_match_is_conciliado():
    invoice = _invoice_stub(
        invoice_id=1,
        uuid="AAAAAAAA-1111-4111-8111-AAAAAAAAAAAA",
        total_mxn=100.0,
        razon_social="Proveedor A",
        rfc_emisor="AAA010101AAA",
    )
    transaction = _transaction(
        descripcion="Pago Proveedor A AAA010101AAA",
        referencia="AAAAAAAA-1111-4111-8111-AAAAAAAAAAAA",
        monto=100.0,
        raw_hash="uuid-exacto",
    )

    row = reconcile_transactions([transaction], [invoice])[0]

    assert row["match_status"] == "CONCILIADO"
    assert row["matched_invoice_id"] == 1


def test_heuristic_match_without_uuid_is_posible():
    invoice = _invoice_stub(
        invoice_id=2,
        uuid="BBBBBBBB-2222-4222-8222-BBBBBBBBBBBB",
        total_mxn=150.0,
        razon_social="Proveedor A2",
        rfc_emisor="CCC010101CCC",
    )
    transaction = _transaction(
        descripcion="Transferencia Proveedor A2 CCC010101CCC",
        referencia=None,
        monto=150.0,
        raw_hash="heuristica-fuerte",
    )

    row = reconcile_transactions([transaction], [invoice])[0]

    assert row["match_status"] == "POSIBLE"
    assert row["matched_invoice_id"] == 2


def test_missing_match_is_pendiente():
    invoice = _invoice_stub(
        invoice_id=3,
        uuid="CCCCCCCC-3333-4333-8333-CCCCCCCCCCCC",
        total_mxn=100.0,
        razon_social="Proveedor C",
        rfc_emisor="DDD010101DDD",
    )
    transaction = _transaction(
        descripcion="Movimiento sin relacion",
        referencia=None,
        monto=999.0,
        raw_hash="sin-coincidencia",
    )

    row = reconcile_transactions([transaction], [invoice])[0]

    assert row["match_status"] == "PENDIENTE"
    assert row["matched_invoice_id"] is None


def test_process_bank_statement_upload_does_not_cross_user_scope(tmp_path):
    _, session_local = _make_db(tmp_path)

    with session_local() as db:
        user_repo = UserRepository(db)
        user_a = user_repo.create("bank-a@example.com", hash_password("password123"))
        user_b = user_repo.create("bank-b@example.com", hash_password("password123"))

        invoice_b_payload = _make_invoice(
            user_b.id,
            "DDDDDDDD-4444-4444-8444-DDDDDDDDDDDD",
            200.0,
            "Proveedor B",
        )
        invoice_b_payload.rfc_emisor = "BBB010101BBB"
        InvoiceRepository(db, user_id=user_b.id).create(invoice_b_payload)

        csv_bytes = (
            "fecha,descripcion,referencia,monto\n"
            "2026-04-25,Pago Proveedor B BBB010101BBB,DDDDDDDD-4444-4444-8444-DDDDDDDDDDDD,200.00\n"
        ).encode("utf-8")

        summary = process_bank_statement_upload(
            db=db,
            user_id=user_a.id,
            file_bytes=csv_bytes,
            filename="estado.csv",
        )

        rows = BankTransactionRepository(db, user_id=user_a.id).list_all()

        assert summary["conciliados"] == 0
        assert summary["posibles"] == 0
        assert summary["pendientes"] == 1
        assert len(rows) == 1
        assert rows[0].match_status == "PENDIENTE"
        assert rows[0].matched_invoice_id is None

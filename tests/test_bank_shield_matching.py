from __future__ import annotations

from types import SimpleNamespace

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.db.base import Base
from app.modules.bank_shield.services.reconciliation_service import (
    _classify_match,
    _currency_matches,
    _date_match_score,
    _supplier_match_score,
)
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


def test_supplier_name_match_without_uuid_is_posible():
    invoice = _invoice_stub(
        invoice_id=4,
        uuid="EEEEEEEE-1111-4111-8111-EEEEEEEEEEEE",
        total_mxn=875.0,
        razon_social="ALEJANDRO LANDEROS RAMIREZ",
        rfc_emisor="ALR010101AAA",
    )
    transaction = _transaction(
        descripcion="PAGO ALEJANDRO LANDEROS RAMIREZ",
        referencia=None,
        monto=875.0,
        raw_hash="nombre-proveedor-exacto",
    )

    row = reconcile_transactions([transaction], [invoice])[0]

    assert row["match_status"] == "POSIBLE"
    assert row["matched_invoice_id"] == 4
    assert row["match_score"] > 0
    assert "proveedor" in str(row["match_reason"]).lower() or "nombre" in str(row["match_reason"]).lower()


def test_supplier_name_match_with_banking_noise_stays_posible_without_uuid():
    invoice = _invoice_stub(
        invoice_id=5,
        uuid="FFFFFFFF-2222-4222-8222-FFFFFFFFFFFF",
        total_mxn=430.0,
        razon_social="ARMANDO LIMA OROZCO",
        rfc_emisor="ALO010101AAA",
    )
    transaction = _transaction(
        descripcion="TRANSFERENCIA ARMANDO LIMA OROZCO",
        referencia="SPEI BANCA MOVIL",
        monto=430.0,
        raw_hash="nombre-proveedor-ruido",
    )

    row = reconcile_transactions([transaction], [invoice])[0]

    assert row["match_status"] == "POSIBLE"
    assert row["matched_invoice_id"] == 5
    assert row["match_score"] >= 50
    assert row["match_status"] != "CONCILIADO"


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


def test_date_match_score_returns_full_points_for_exact_date():
    score, reason = _date_match_score("2026-04-25", "2026-04-25T10:00:00")

    assert score == 20
    assert reason == "Fecha dentro de 0 dias"


def test_date_match_score_returns_full_points_for_nearby_date_within_window():
    score, reason = _date_match_score("2026-04-25", "2026-04-28T10:00:00")

    assert score == 20
    assert reason == "Fecha dentro de 3 dias"


def test_date_match_score_returns_no_points_for_distant_date():
    score, reason = _date_match_score("2026-04-25", "2026-05-10T10:00:00")

    assert score == 0
    assert reason is None


def test_supplier_match_score_detects_supplier_name_in_transaction_text():
    invoice = _invoice_stub(
        invoice_id=10,
        uuid="11111111-1111-4111-8111-111111111111",
        total_mxn=500.0,
        razon_social="Proveedor Industrial SA de CV",
        rfc_emisor="PIS010101AAA",
    )
    transaction = _transaction(
        descripcion="Transferencia Proveedor Industrial SA de CV",
        referencia=None,
        monto=500.0,
        raw_hash="supplier-name",
    )

    score, reason = _supplier_match_score(transaction, invoice)

    assert score == 25
    assert reason == "Proveedor detectado en descripcion"


def test_supplier_match_score_detects_rfc_in_transaction_text():
    invoice = _invoice_stub(
        invoice_id=11,
        uuid="22222222-2222-4222-8222-222222222222",
        total_mxn=600.0,
        razon_social="Nombre no presente",
        rfc_emisor="RFC010101AAA",
    )
    transaction = _transaction(
        descripcion="Abono RFC010101AAA por servicio",
        referencia=None,
        monto=600.0,
        raw_hash="supplier-rfc",
    )

    score, reason = _supplier_match_score(transaction, invoice)

    assert score == 25
    assert reason == "RFC detectado en descripcion"


def test_supplier_match_score_returns_no_match_for_unrelated_text():
    invoice = _invoice_stub(
        invoice_id=12,
        uuid="33333333-3333-4333-8333-333333333333",
        total_mxn=700.0,
        razon_social="Proveedor Relacionado",
        rfc_emisor="REL010101AAA",
    )
    transaction = _transaction(
        descripcion="Movimiento sin datos relacionados",
        referencia="Operacion interna",
        monto=700.0,
        raw_hash="supplier-none",
    )

    score, reason = _supplier_match_score(transaction, invoice)

    assert score == 0
    assert reason is None


def test_currency_matches_returns_true_for_same_currency():
    invoice = _invoice_stub(
        invoice_id=13,
        uuid="44444444-4444-4444-8444-444444444444",
        total_mxn=800.0,
        razon_social="Proveedor MXN",
        rfc_emisor="MXN010101AAA",
    )
    transaction = _transaction(
        descripcion="Pago en pesos",
        referencia=None,
        monto=800.0,
        raw_hash="currency-same",
    )

    assert _currency_matches(transaction, invoice) is True


def test_currency_matches_returns_false_for_different_currency():
    invoice = _invoice_stub(
        invoice_id=14,
        uuid="55555555-5555-4555-8555-555555555555",
        total_mxn=900.0,
        razon_social="Proveedor USD",
        rfc_emisor="USD010101AAA",
    )
    invoice.moneda_original = "USD"
    transaction = _transaction(
        descripcion="Pago en pesos",
        referencia=None,
        monto=900.0,
        raw_hash="currency-different",
    )

    assert _currency_matches(transaction, invoice) is False


def test_classify_match_returns_conciliado_for_uuid_and_threshold():
    assert _classify_match(80, True) == "CONCILIADO"


def test_classify_match_returns_posible_for_partial_threshold():
    assert _classify_match(50, False) == "POSIBLE"


def test_classify_match_returns_pendiente_below_threshold():
    assert _classify_match(49.99, False) == "PENDIENTE"


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

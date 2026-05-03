from __future__ import annotations

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.db.base import Base
from app.repositories.bank_transaction_repository import BankTransactionRepository
from app.repositories.invoice_repository import InvoiceRepository
from app.repositories.user_repository import UserRepository
from app.schemas.bank_reconciliation import BankReconciliationFilters
from app.schemas.invoice import InvoiceCreate
from app.services.auth_service import hash_password


def _make_db(tmp_path):
    db_path = tmp_path / "bank_shield_repository.db"
    engine = create_engine(f"sqlite:///{db_path}", connect_args={"check_same_thread": False})
    session_local = sessionmaker(bind=engine, autoflush=False, autocommit=False)
    Base.metadata.drop_all(bind=engine)
    Base.metadata.create_all(bind=engine)
    return engine, session_local


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


def _payload(
    *,
    raw_hash: str,
    descripcion: str,
    monto: float,
    match_status: str = "PENDIENTE",
    origen: str = "AUTOMATICO",
    matched_invoice_id: int | None = None,
    referencia: str | None = None,
) -> dict[str, object]:
    return {
        "fecha": "2026-04-25",
        "descripcion": descripcion,
        "referencia": referencia,
        "cargo": 0.0,
        "abono": monto,
        "monto": monto,
        "tipo_movimiento": "ABONO",
        "moneda": "MXN",
        "raw_hash": raw_hash,
        "matched_invoice_id": matched_invoice_id,
        "origen": origen,
        "match_status": match_status,
        "match_score": 0.0,
        "match_reason": "Prueba",
    }


def test_bank_transaction_upsert_updates_existing_row(tmp_path):
    _, session_local = _make_db(tmp_path)

    with session_local() as db:
        user = UserRepository(db).create("repo@example.com", hash_password("password123"))
        repo = BankTransactionRepository(db, user_id=user.id)

        created = repo.upsert(_payload(raw_hash="hash-1", descripcion="Pago inicial", monto=100.0))
        original_id = created.id

        updated = repo.upsert(
            _payload(
                raw_hash="hash-1",
                descripcion="Pago actualizado",
                monto=100.0,
                match_status="POSIBLE",
                origen="MANUAL",
            )
        )

        rows = repo.list_all()

        assert updated.id == original_id
        assert len(rows) == 1
        assert rows[0].descripcion == "Pago actualizado"
        assert rows[0].match_status == "POSIBLE"
        assert rows[0].origen == "MANUAL"


def test_bank_transaction_list_all_is_scoped_by_user(tmp_path):
    _, session_local = _make_db(tmp_path)

    with session_local() as db:
        user_repo = UserRepository(db)
        user_a = user_repo.create("repo-a@example.com", hash_password("password123"))
        user_b = user_repo.create("repo-b@example.com", hash_password("password123"))

        BankTransactionRepository(db, user_id=user_a.id).upsert(
            _payload(raw_hash="hash-a", descripcion="Pago A", monto=100.0)
        )
        BankTransactionRepository(db, user_id=user_b.id).upsert(
            _payload(raw_hash="hash-b", descripcion="Pago B", monto=200.0)
        )

        rows_a = BankTransactionRepository(db, user_id=user_a.id).list_all()
        rows_b = BankTransactionRepository(db, user_id=user_b.id).list_all()

        assert len(rows_a) == 1
        assert rows_a[0].descripcion == "Pago A"
        assert len(rows_b) == 1
        assert rows_b[0].descripcion == "Pago B"


def test_bank_transaction_filters_and_search(tmp_path):
    _, session_local = _make_db(tmp_path)

    with session_local() as db:
        user = UserRepository(db).create("filters@example.com", hash_password("password123"))
        invoice_payload = _make_invoice(
            user.id,
            "EEEEEEEE-5555-4555-8555-EEEEEEEEEEEE",
            150.0,
            "Proveedor Alpha",
        )
        invoice = InvoiceRepository(db, user_id=user.id).create(invoice_payload)

        repo = BankTransactionRepository(db, user_id=user.id)
        repo.upsert(
            _payload(
                raw_hash="hash-conciliado",
                descripcion="Pago Alpha",
                monto=150.0,
                match_status="CONCILIADO",
                origen="AUTOMATICO",
                matched_invoice_id=invoice.id,
                referencia=invoice.uuid,
            )
        )
        repo.upsert(
            _payload(
                raw_hash="hash-posible",
                descripcion="Pago por revisar",
                monto=151.0,
                match_status="POSIBLE",
                origen="AUTOMATICO",
            )
        )
        repo.upsert(
            _payload(
                raw_hash="hash-pendiente",
                descripcion="Ajuste manual",
                monto=50.0,
                match_status="PENDIENTE",
                origen="MANUAL",
            )
        )

        posibles = repo.list_all(filters=BankReconciliationFilters(estado="POSIBLE"))
        manuales = repo.list_all(filters=BankReconciliationFilters(origen="MANUAL"))
        search_provider = repo.list_all(filters=BankReconciliationFilters(busqueda="Alpha"))

        assert len(posibles) == 1
        assert posibles[0].match_status == "POSIBLE"
        assert len(manuales) == 1
        assert manuales[0].origen == "MANUAL"
        assert len(search_provider) == 1
        assert search_provider[0].matched_invoice_id == invoice.id


def test_bank_transaction_summary_counts_statuses(tmp_path):
    _, session_local = _make_db(tmp_path)

    with session_local() as db:
        user = UserRepository(db).create("summary@example.com", hash_password("password123"))
        repo = BankTransactionRepository(db, user_id=user.id)

        repo.upsert(_payload(raw_hash="sum-1", descripcion="Pago 1", monto=100.0, match_status="CONCILIADO"))
        repo.upsert(_payload(raw_hash="sum-2", descripcion="Pago 2", monto=101.0, match_status="POSIBLE"))
        repo.upsert(_payload(raw_hash="sum-3", descripcion="Pago 3", monto=102.0, match_status="PENDIENTE"))

        summary = repo.summary()

        assert summary == {
            "total_movimientos": 3,
            "conciliados": 1,
            "posibles": 1,
            "pendientes": 1,
        }

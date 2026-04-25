from __future__ import annotations

from io import BytesIO

from fastapi.testclient import TestClient
from openpyxl import load_workbook
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.core.config import settings
from app.db.base import Base
from app.db import init_db as init_db_module
from app.db import session as session_module
from app.main import app
from app.models.invoice import Invoice
from app.repositories.invoice_repository import InvoiceRepository
from app.repositories.user_repository import UserRepository
from app.schemas.invoice import InvoiceCreate
from app.services.auth_service import create_session_token, hash_password
import app.web_deps as web_deps_module


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


def test_multiuser_excel_delete_and_get_isolation(tmp_path, monkeypatch):
    db_path = tmp_path / "multiuser.db"
    engine = create_engine(f"sqlite:///{db_path}", connect_args={"check_same_thread": False})
    testing_session_local = sessionmaker(bind=engine, autoflush=False, autocommit=False)

    monkeypatch.setattr(session_module, "engine", engine)
    monkeypatch.setattr(session_module, "SessionLocal", testing_session_local)
    monkeypatch.setattr(init_db_module, "engine", engine)
    monkeypatch.setattr(init_db_module, "_initialized", False)
    monkeypatch.setattr(web_deps_module, "SessionLocal", testing_session_local)

    Base.metadata.create_all(bind=engine)
    init_db_module.ensure_db_initialized()

    with testing_session_local() as db:
        user_repo = UserRepository(db)
        user_a = user_repo.create("a@example.com", hash_password("password123"))
        user_b = user_repo.create("b@example.com", hash_password("password123"))

        repo_a = InvoiceRepository(db, user_id=user_a.id)
        repo_b = InvoiceRepository(db, user_id=user_b.id)
        invoice_a = repo_a.create(_make_invoice(user_a.id, "AAAAAAAA-1111-4111-8111-AAAAAAAAAAAA", 100.0, "Proveedor A"))
        invoice_b = repo_b.create(_make_invoice(user_b.id, "BBBBBBBB-2222-4222-8222-BBBBBBBBBBBB", 200.0, "Proveedor B"))

    client = TestClient(app)
    cookie_name = settings.session_cookie_name
    cookie_a = {cookie_name: create_session_token(user_a.id)}
    cookie_b = {cookie_name: create_session_token(user_b.id)}

    response_a = client.get("/api/v1/dashboard/export-excel", cookies=cookie_a)
    assert response_a.status_code == 200
    workbook_a = load_workbook(filename=BytesIO(response_a.content))
    control_a = workbook_a["CONTROL"]
    values_a = "\n".join("" if cell is None else str(cell) for row in control_a.iter_rows(values_only=True) for cell in row)
    assert "Proveedor A" in values_a
    assert "Proveedor B" not in values_a
    assert "BBBBBBBB-2222-4222-8222-BBBBBBBBBBBB" not in values_a

    response_b = client.get("/api/v1/dashboard/export-excel", cookies=cookie_b)
    assert response_b.status_code == 200
    workbook_b = load_workbook(filename=BytesIO(response_b.content))
    control_b = workbook_b["CONTROL"]
    values_b = "\n".join("" if cell is None else str(cell) for row in control_b.iter_rows(values_only=True) for cell in row)
    assert "Proveedor B" in values_b
    assert "Proveedor A" not in values_b
    assert "AAAAAAAA-1111-4111-8111-AAAAAAAAAAAA" not in values_b

    get_b_as_a = client.get(f"/api/v1/invoices/{invoice_b.id}", cookies=cookie_a)
    assert get_b_as_a.status_code == 404

    delete_b_as_a = client.post(
        f"/invoices/{invoice_b.id}/delete",
        cookies=cookie_a,
        follow_redirects=False,
    )
    assert delete_b_as_a.status_code == 303

    with testing_session_local() as db:
        remaining_b = InvoiceRepository(db, user_id=user_b.id).get_by_id(invoice_b.id)
        assert remaining_b is not None

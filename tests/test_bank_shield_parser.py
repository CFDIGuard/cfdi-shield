from __future__ import annotations

import pytest

from app.services.bank_statement_parser import parse_bank_statement


def test_parse_bank_statement_csv_valid_normalizes_fields():
    csv_bytes = (
        "fecha,descripcion,referencia,abono,moneda\n"
        "2026-04-25,  Pago cliente  , ABC-123 ,100.00,mxn\n"
    ).encode("utf-8")

    transactions = parse_bank_statement(csv_bytes, "estado.csv")

    assert len(transactions) == 1
    transaction = transactions[0]
    assert transaction.fecha == "2026-04-25"
    assert transaction.descripcion == "Pago cliente"
    assert transaction.referencia == "ABC-123"
    assert transaction.abono == 100.0
    assert transaction.cargo == 0.0
    assert transaction.monto == 100.0
    assert transaction.moneda == "MXN"
    assert transaction.tipo_movimiento == "ABONO"


def test_parse_bank_statement_accepts_header_aliases():
    csv_bytes = (
        "fecha_operacion,concepto,uuid,deposito,currency\n"
        "25/04/2026,Abono proveedor,REF-XYZ,250.00,usd\n"
    ).encode("utf-8")

    transactions = parse_bank_statement(csv_bytes, "alias.csv")

    assert len(transactions) == 1
    transaction = transactions[0]
    assert transaction.fecha == "2026-04-25"
    assert transaction.descripcion == "Abono proveedor"
    assert transaction.referencia == "REF-XYZ"
    assert transaction.abono == 250.0
    assert transaction.monto == 250.0
    assert transaction.moneda == "USD"


def test_parse_bank_statement_interprets_positive_and_negative_monto():
    csv_bytes = (
        "fecha,descripcion,monto\n"
        "2026-04-25,Cobro cliente,150.00\n"
        "2026-04-25,Comision bancaria,-45.00\n"
    ).encode("utf-8")

    transactions = parse_bank_statement(csv_bytes, "montos.csv")

    assert len(transactions) == 2

    positive, negative = transactions
    assert positive.abono == 150.0
    assert positive.cargo == 0.0
    assert positive.monto == 150.0
    assert positive.tipo_movimiento == "ABONO"

    assert negative.abono == 0.0
    assert negative.cargo == -45.0
    assert negative.monto == 45.0
    assert negative.tipo_movimiento == "CARGO"


def test_parse_bank_statement_rejects_invalid_structure():
    csv_bytes = (
        "referencia,detalle\n"
        "ABC-123,Pago sin columnas requeridas\n"
    ).encode("utf-8")

    with pytest.raises(ValueError, match="fecha y descripcion"):
        parse_bank_statement(csv_bytes, "invalido.csv")


def test_parse_bank_statement_rejects_invalid_extension():
    with pytest.raises(ValueError, match="CSV o XLSX"):
        parse_bank_statement(b"contenido", "estado.txt")


def test_parse_bank_statement_raw_hash_is_consistent():
    csv_bytes = (
        "fecha,descripcion,referencia,abono\n"
        "2026-04-25,Pago cliente,ABC-123,100.00\n"
    ).encode("utf-8")

    first = parse_bank_statement(csv_bytes, "estado.csv")
    second = parse_bank_statement(csv_bytes, "estado.csv")

    assert len(first) == 1
    assert len(second) == 1
    assert first[0].raw_hash == second[0].raw_hash

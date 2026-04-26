from __future__ import annotations

from datetime import datetime
import re

from sqlalchemy.orm import Session

from app.core.config import settings
from app.models.invoice import Invoice
from app.repositories.bank_transaction_repository import BankTransactionRepository
from app.repositories.invoice_repository import InvoiceRepository
from app.schemas.bank_reconciliation import BankReconciliationFilters
from app.services.bank_statement_parser import ParsedBankTransaction, parse_bank_statement


UUID_PATTERN = re.compile(r"[0-9A-F]{8}-[0-9A-F]{4}-[1-5][0-9A-F]{3}-[89AB][0-9A-F]{3}-[0-9A-F]{12}", re.IGNORECASE)


def _normalized_text(value: str | None) -> str:
    return str(value or "").strip().upper()


def _invoice_total_mxn(invoice: Invoice) -> float | None:
    if invoice.total_mxn is not None:
        return float(invoice.total_mxn)
    if _normalized_text(invoice.moneda_original or invoice.moneda) == "MXN":
        return float(invoice.total_original or invoice.total or 0)
    return None


def _extract_date(value: str | None) -> datetime | None:
    if not value:
        return None
    try:
        return datetime.fromisoformat(value[:10])
    except ValueError:
        return None


def _date_match_score(transaction_date: str | None, invoice_date: str | None) -> tuple[int, str | None]:
    tx_date = _extract_date(transaction_date)
    inv_date = _extract_date(invoice_date)
    if tx_date is None or inv_date is None:
        return 0, None
    days_diff = abs((tx_date.date() - inv_date.date()).days)
    if days_diff <= settings.bank_reconciliation_date_window_days:
        return 20, f"Fecha dentro de {days_diff} dias"
    return 0, None


def _description_has_supplier(transaction: ParsedBankTransaction, invoice: Invoice) -> bool:
    haystack = f"{transaction.descripcion} {transaction.referencia or ''}".upper()
    if invoice.rfc_emisor and invoice.rfc_emisor.upper() in haystack:
        return True
    supplier_name = str(invoice.razon_social or "").strip().upper()
    if supplier_name and len(supplier_name) >= 6 and supplier_name in haystack:
        return True
    return False


def _uuid_detected(transaction: ParsedBankTransaction, invoice: Invoice) -> bool:
    haystack = f"{transaction.descripcion} {transaction.referencia or ''}".upper()
    if invoice.uuid and invoice.uuid.upper() in haystack:
        return True
    matches = UUID_PATTERN.findall(haystack)
    return any(match.upper() == str(invoice.uuid or "").upper() for match in matches)


def _currency_matches(transaction: ParsedBankTransaction, invoice: Invoice) -> bool:
    transaction_currency = _normalized_text(transaction.moneda or "MXN") or "MXN"
    invoice_currency = _normalized_text(invoice.moneda_original or invoice.moneda or "MXN") or "MXN"
    return transaction_currency == invoice_currency


def _score_transaction(transaction: ParsedBankTransaction, invoice: Invoice) -> tuple[float, list[str]]:
    score = 0.0
    reasons: list[str] = []
    invoice_total_mxn = _invoice_total_mxn(invoice)
    if invoice_total_mxn is None:
        return score, reasons

    amount_diff = abs(transaction.monto - invoice_total_mxn)
    if amount_diff <= 0.005:
        score += 50
        reasons.append("Monto exacto")
    elif amount_diff <= settings.bank_reconciliation_amount_tolerance:
        score += 35
        reasons.append(f"Monto dentro de tolerancia (+/- {settings.bank_reconciliation_amount_tolerance:.2f})")
    else:
        return 0.0, []

    date_score, date_reason = _date_match_score(transaction.fecha, invoice.fecha_emision)
    score += date_score
    if date_reason:
        reasons.append(date_reason)

    if _description_has_supplier(transaction, invoice):
        score += 20
        reasons.append("RFC o proveedor detectado en descripcion")

    if _uuid_detected(transaction, invoice):
        score += 30
        reasons.append("UUID detectado en referencia o descripcion")

    if _currency_matches(transaction, invoice):
        score += 10
        reasons.append("Moneda coincide")

    return min(score, 100.0), reasons


def _classify_match(score: float) -> str:
    if score >= 80:
        return "CONCILIADO"
    if score >= 50:
        return "POSIBLE"
    return "PENDIENTE"


def reconcile_transactions(
    parsed_transactions: list[ParsedBankTransaction],
    invoices: list[Invoice],
) -> list[dict[str, object]]:
    results: list[dict[str, object]] = []
    for transaction in parsed_transactions:
        best_invoice: Invoice | None = None
        best_score = 0.0
        best_reasons: list[str] = []

        for invoice in invoices:
            score, reasons = _score_transaction(transaction, invoice)
            if score > best_score:
                best_invoice = invoice
                best_score = score
                best_reasons = reasons

        status = _classify_match(best_score)
        if status == "PENDIENTE":
            best_invoice = None
            best_reasons = ["Sin coincidencia suficiente"]

        results.append(
            {
                "fecha": transaction.fecha,
                "descripcion": transaction.descripcion,
                "referencia": transaction.referencia,
                "cargo": transaction.cargo,
                "abono": transaction.abono,
                "monto": transaction.monto,
                "tipo_movimiento": transaction.tipo_movimiento,
                "moneda": transaction.moneda,
                "raw_hash": transaction.raw_hash,
                "matched_invoice_id": best_invoice.id if best_invoice is not None else None,
                "origen": "AUTOMATICO",
                "match_status": status,
                "match_score": round(best_score, 2),
                "match_reason": "; ".join(best_reasons),
            }
        )
    return results


def process_bank_statement_upload(
    *,
    db: Session,
    user_id: int,
    file_bytes: bytes,
    filename: str,
) -> dict[str, int]:
    parsed_transactions = parse_bank_statement(file_bytes, filename)
    if not parsed_transactions:
        raise ValueError("No se encontraron movimientos validos en el estado bancario.")

    invoice_repository = InvoiceRepository(db, user_id=user_id)
    bank_repository = BankTransactionRepository(db, user_id=user_id)
    invoices = invoice_repository.list_all()
    reconciled_rows = reconcile_transactions(parsed_transactions, invoices)

    for payload in reconciled_rows:
        bank_repository.upsert(payload)
    db.commit()
    return bank_repository.summary()


def get_reconciliation_rows(
    db: Session,
    user_id: int,
    limit: int = 150,
    filters: BankReconciliationFilters | None = None,
) -> list[dict[str, object]]:
    bank_repository = BankTransactionRepository(db, user_id=user_id)
    invoice_repository = InvoiceRepository(db, user_id=user_id)
    invoices_by_id = {invoice.id: invoice for invoice in invoice_repository.list_all()}

    rows: list[dict[str, object]] = []
    for movement in bank_repository.list_recent(limit=limit, filters=filters):
        matched_invoice = invoices_by_id.get(movement.matched_invoice_id)
        rows.append(
            {
                "id": movement.id,
                "fecha": movement.fecha,
                "descripcion": movement.descripcion,
                "referencia": movement.referencia,
                "cargo": float(movement.cargo or 0),
                "abono": float(movement.abono or 0),
                "monto": float(movement.monto or 0),
                "tipo_movimiento": movement.tipo_movimiento,
                "moneda": movement.moneda,
                "origen": movement.origen,
                "matched_invoice_id": movement.matched_invoice_id,
                "match_status": movement.match_status,
                "match_score": float(movement.match_score or 0),
                "match_reason": movement.match_reason,
                "matched_invoice_uuid": matched_invoice.uuid if matched_invoice is not None else None,
                "matched_invoice_provider": matched_invoice.razon_social if matched_invoice is not None else None,
                "matched_invoice_total_mxn": _invoice_total_mxn(matched_invoice) if matched_invoice is not None else None,
            }
        )
    return rows


def get_reconciliation_summary(
    db: Session,
    user_id: int,
    filters: BankReconciliationFilters | None = None,
) -> dict[str, int]:
    return BankTransactionRepository(db, user_id=user_id).summary(filters=filters)

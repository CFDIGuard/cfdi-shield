from __future__ import annotations

"""Bank Shield v0.1 reconciliation service.

Current implementation is migrated into the Bank Shield module while legacy
imports remain supported through temporary passthrough adapters.
"""

from datetime import datetime
import re

from sqlalchemy.orm import Session

from app.core.config import settings
from app.modules.bank_shield.repositories.invoice_lookup_repository import InvoiceLookupRepository
from app.modules.bank_shield.services.normalization import (
    _meaningful_tokens,
    _normalized_text,
    _normalize_search_text,
)
from app.modules.bank_shield.services.statement_parser import ParsedBankTransaction, parse_bank_statement
from app.models.invoice import Invoice
from app.modules.bank_shield.repositories.bank_transaction_repository import BankTransactionRepository
from app.schemas.bank_reconciliation import BankReconciliationFilters


UUID_PATTERN = re.compile(r"[0-9A-F]{8}-[0-9A-F]{4}-[1-5][0-9A-F]{3}-[89AB][0-9A-F]{3}-[0-9A-F]{12}", re.IGNORECASE)
MAX_BREAKDOWN_CHIPS = 6
STRONG_EVIDENCE_MIN_CHIPS = 3
WEAK_EVIDENCE_MAX_CHIPS = 1


def _invoice_total_mxn(invoice: Invoice) -> float | None:
    if invoice.total_mxn is not None:
        return float(invoice.total_mxn)
    if _normalized_text(invoice.moneda_original or invoice.moneda) == "MXN":
        return float(invoice.total_original or invoice.total or 0)
    return None


def invoice_unavailable_for_ui(
    match_reason: str | None,
    *,
    matched_invoice_id: int | None,
    matched_invoice_uuid: str | None,
) -> bool:
    normalized_reason = _normalized_text(match_reason)
    indicates_unavailable = (
        "FACTURA RELACIONADA ELIMINADA" in normalized_reason
        or "FACTURA RELACIONADA NO DISPONIBLE" in normalized_reason
        or "FACTURA NO DISPONIBLE" in normalized_reason
    )
    return (indicates_unavailable or matched_invoice_id is not None) and not matched_invoice_uuid


def _score_breakdown_for_ui(
    *,
    match_reason: str | None,
    invoice_unavailable: bool,
) -> dict[str, object]:
    if invoice_unavailable:
        return {
            "chips": [
                {"key": "invoice_unavailable", "label": "CFDI no disponible", "tone": "warning"},
            ],
            "summary": "La factura sugerida ya no esta disponible para conciliacion.",
            "confidence_hint": "evidence_weak",
        }

    normalized_reason = _normalized_text(match_reason)
    if not normalized_reason or normalized_reason == "SIN COINCIDENCIA SUFICIENTE":
        return {
            "chips": [
                {"key": "insufficient_match", "label": "Sin coincidencia", "tone": "warning"},
            ],
            "summary": "No hay evidencia suficiente para sugerir un CFDI.",
            "confidence_hint": "evidence_weak",
        }

    chips: list[dict[str, str]] = []

    def add_chip(key: str, label: str, tone: str = "positive") -> None:
        if any(existing["key"] == key for existing in chips):
            return
        chips.append({"key": key, "label": label, "tone": tone})

    if "UUID DETECTADO" in normalized_reason:
        add_chip("uuid", "UUID")
    if "MONTO EXACTO" in normalized_reason or "MONTO DENTRO DE TOLERANCIA" in normalized_reason:
        add_chip("amount", "Monto")
    if "FECHA DENTRO DE" in normalized_reason:
        add_chip("date", "Fecha", "neutral")
    if "RFC DETECTADO" in normalized_reason:
        add_chip("rfc", "RFC")
    if "PROVEEDOR DETECTADO" in normalized_reason or "COINCIDENCIA POR PROVEEDOR/NOMBRE" in normalized_reason:
        add_chip("supplier", "Proveedor")
    if "MONEDA COINCIDE" in normalized_reason:
        add_chip("currency", "Moneda", "neutral")

    confidence_hint = "evidence_partial"
    if any(chip["key"] == "uuid" for chip in chips) or len(chips) >= STRONG_EVIDENCE_MIN_CHIPS:
        confidence_hint = "evidence_strong"
    elif len(chips) <= WEAK_EVIDENCE_MAX_CHIPS:
        confidence_hint = "evidence_weak"

    return {
        "chips": chips[:MAX_BREAKDOWN_CHIPS],
        "summary": match_reason or "Revision sugerida",
        "confidence_hint": confidence_hint,
    }


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


def _supplier_match_score(transaction: ParsedBankTransaction, invoice: Invoice) -> tuple[int, str | None]:
    haystack = _normalize_search_text(f"{transaction.descripcion} {transaction.referencia or ''}")

    for rfc_value in (invoice.rfc_emisor, getattr(invoice, "rfc_receptor", None)):
        normalized_rfc = _normalize_search_text(rfc_value)
        if normalized_rfc and normalized_rfc in haystack:
            return 25, "RFC detectado en descripcion"

    supplier_name = _normalize_search_text(invoice.razon_social)
    if supplier_name and len(supplier_name) >= 6 and supplier_name in haystack:
        return 25, "Proveedor detectado en descripcion"

    haystack_tokens = set(_meaningful_tokens(f"{transaction.descripcion} {transaction.referencia or ''}"))
    supplier_tokens = _meaningful_tokens(invoice.razon_social)
    if len(supplier_tokens) >= 2 and haystack_tokens:
        matched_tokens = [token for token in supplier_tokens if token in haystack_tokens]
        if len(matched_tokens) >= 2:
            coverage = len(matched_tokens) / len(supplier_tokens)
            if coverage >= 0.6:
                return 20, "Coincidencia por proveedor/nombre"

    return 0, None


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


def _score_transaction(transaction: ParsedBankTransaction, invoice: Invoice) -> tuple[float, list[str], bool]:
    score = 0.0
    reasons: list[str] = []
    invoice_total_mxn = _invoice_total_mxn(invoice)
    if invoice_total_mxn is None:
        return score, reasons, False

    amount_diff = abs(transaction.monto - invoice_total_mxn)
    if amount_diff <= 0.005:
        score += 50
        reasons.append("Monto exacto")
    elif amount_diff <= settings.bank_reconciliation_amount_tolerance:
        score += 35
        reasons.append(f"Monto dentro de tolerancia (+/- {settings.bank_reconciliation_amount_tolerance:.2f})")
    else:
        return 0.0, [], False

    date_score, date_reason = _date_match_score(transaction.fecha, invoice.fecha_emision)
    score += date_score
    if date_reason:
        reasons.append(date_reason)

    supplier_score, supplier_reason = _supplier_match_score(transaction, invoice)
    score += supplier_score
    if supplier_reason:
        reasons.append(supplier_reason)

    uuid_detected = _uuid_detected(transaction, invoice)
    if uuid_detected:
        score += 30
        reasons.append("UUID detectado en referencia o descripcion")

    if _currency_matches(transaction, invoice):
        score += 10
        reasons.append("Moneda coincide")

    return min(score, 100.0), reasons, uuid_detected


def _classify_match(score: float, uuid_detected: bool) -> str:
    if uuid_detected and score >= 80:
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
        best_uuid_detected = False

        for invoice in invoices:
            score, reasons, uuid_detected = _score_transaction(transaction, invoice)
            if score > best_score:
                best_invoice = invoice
                best_score = score
                best_reasons = reasons
                best_uuid_detected = uuid_detected

        status = _classify_match(best_score, best_uuid_detected)
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

    bank_repository = BankTransactionRepository(db, user_id=user_id)
    invoice_lookup_repository = InvoiceLookupRepository(db, user_id=user_id)
    invoices = invoice_lookup_repository.list_all_for_matching()
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
    invoice_lookup_repository = InvoiceLookupRepository(db, user_id=user_id)
    movements = bank_repository.list_recent(limit=limit, filters=filters)
    matched_invoice_ids = sorted(
        {
            movement.matched_invoice_id
            for movement in movements
            if movement.matched_invoice_id is not None
        }
    )
    invoices_by_id = {
        invoice.id: invoice
        for invoice in invoice_lookup_repository.list_by_ids_for_reconciliation(matched_invoice_ids)
    }

    rows: list[dict[str, object]] = []
    for movement in movements:
        matched_invoice = invoices_by_id.get(movement.matched_invoice_id)
        matched_invoice_uuid = matched_invoice.uuid if matched_invoice is not None else None
        matched_invoice_provider = matched_invoice.razon_social if matched_invoice is not None else None
        invoice_unavailable = invoice_unavailable_for_ui(
            movement.match_reason,
            matched_invoice_id=movement.matched_invoice_id,
            matched_invoice_uuid=matched_invoice_uuid,
        )
        score_breakdown = _score_breakdown_for_ui(
            match_reason=movement.match_reason,
            invoice_unavailable=invoice_unavailable,
        )
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
                "match_status": "PENDIENTE" if invoice_unavailable else movement.match_status,
                "match_score": float(movement.match_score or 0),
                "match_reason": movement.match_reason,
                "matched_invoice_uuid": matched_invoice_uuid,
                "matched_invoice_provider": matched_invoice_provider,
                "matched_invoice_total_mxn": _invoice_total_mxn(matched_invoice) if matched_invoice is not None else None,
                "invoice_unavailable": invoice_unavailable,
                "score_breakdown": score_breakdown,
            }
        )
    return rows


def get_reconciliation_summary(
    db: Session,
    user_id: int,
    filters: BankReconciliationFilters | None = None,
) -> dict[str, int]:
    return BankTransactionRepository(db, user_id=user_id).summary(filters=filters)

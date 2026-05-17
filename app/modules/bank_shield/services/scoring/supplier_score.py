from __future__ import annotations

from app.modules.bank_shield.services.normalization import _meaningful_tokens, _normalize_search_text
from app.modules.bank_shield.services.statement_parser import ParsedBankTransaction
from app.models.invoice import Invoice


def _supplier_match_score(transaction: ParsedBankTransaction, invoice: Invoice) -> tuple[int, str | None]:
    transaction_text = f"{transaction.descripcion} {transaction.referencia or ''}"
    haystack = _normalize_search_text(transaction_text)

    for rfc_value in (invoice.rfc_emisor, getattr(invoice, "rfc_receptor", None)):
        normalized_rfc = _normalize_search_text(rfc_value)
        if normalized_rfc and normalized_rfc in haystack:
            return 25, "RFC detectado en descripcion"

    supplier_name = _normalize_search_text(invoice.razon_social)
    if supplier_name and len(supplier_name) >= 6 and supplier_name in haystack:
        return 25, "Proveedor detectado en descripcion"

    haystack_tokens = set(_meaningful_tokens(transaction_text))
    supplier_tokens = _meaningful_tokens(invoice.razon_social)
    if len(supplier_tokens) >= 2 and haystack_tokens:
        matched_tokens = [token for token in supplier_tokens if token in haystack_tokens]
        if len(matched_tokens) >= 2:
            coverage = len(matched_tokens) / len(supplier_tokens)
            if coverage >= 0.6:
                return 20, "Coincidencia por proveedor/nombre"

    return 0, None

from __future__ import annotations

from app.modules.bank_shield.services.normalization import _normalized_text
from app.modules.bank_shield.services.statement_parser import ParsedBankTransaction
from app.models.invoice import Invoice


def _currency_matches(transaction: ParsedBankTransaction, invoice: Invoice) -> bool:
    transaction_currency = _normalized_text(transaction.moneda or "MXN") or "MXN"
    invoice_currency = _normalized_text(invoice.moneda_original or invoice.moneda or "MXN") or "MXN"
    return transaction_currency == invoice_currency

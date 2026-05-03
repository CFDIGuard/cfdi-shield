from __future__ import annotations

"""Temporary legacy passthrough for Bank Shield statement parsing.

Deprecated: runtime implementation now lives in
app.modules.bank_shield.services.statement_parser.
"""

from app.modules.bank_shield.services.statement_parser import (
    HEADER_ALIASES,
    DATE_FORMATS,
    ParsedBankTransaction,
    parse_bank_statement,
)

__all__ = [
    "HEADER_ALIASES",
    "DATE_FORMATS",
    "ParsedBankTransaction",
    "parse_bank_statement",
]

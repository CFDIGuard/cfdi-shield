"""Compatibility adapter between legacy shared imports and Bank Shield.

This module keeps transition points explicit while runtime logic is migrated
incrementally into the internal Bank Shield module.
"""

from app.modules.bank_shield.services.statement_parser import (
    ParsedBankTransaction,
    parse_bank_statement as _parse_bank_statement,
)


def parse_bank_statement(file_bytes: bytes, filename: str) -> list[ParsedBankTransaction]:
    """Delegate bank statement parsing to the module implementation."""
    return _parse_bank_statement(file_bytes, filename)

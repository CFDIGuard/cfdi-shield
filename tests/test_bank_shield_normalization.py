from app.modules.bank_shield.services.normalization import (
    _meaningful_tokens,
    _normalized_text,
    _normalize_search_text,
)


def test_normalized_text_uppercases_and_strips_spaces():
    assert _normalized_text("  proveedor uno  ") == "PROVEEDOR UNO"


def test_normalized_text_handles_none_as_empty_string():
    assert _normalized_text(None) == ""


def test_normalize_search_text_uppercases_and_removes_accents():
    assert _normalize_search_text("  depósito nómina  ") == "DEPOSITO NOMINA"


def test_normalize_search_text_replaces_special_characters_with_spaces():
    assert _normalize_search_text("Pago#123/ABC-99") == "PAGO 123 ABC 99"


def test_normalize_search_text_preserves_letters_and_numbers_and_collapses_spaces():
    assert _normalize_search_text("  ref...factura   001   proveedor\tuno  ") == "REF FACTURA 001 PROVEEDOR UNO"


def test_meaningful_tokens_removes_banking_noise_words():
    assert _meaningful_tokens("PAGO SPEI TRANSFERENCIA REF PROVEEDOR FACTURA") == ["PROVEEDOR", "FACTURA"]


def test_meaningful_tokens_keeps_useful_tokens_with_length_three_or_more():
    assert _meaningful_tokens("Proveedor Industrial RFC123 ABC") == ["PROVEEDOR", "INDUSTRIAL", "RFC123", "ABC"]


def test_meaningful_tokens_removes_short_tokens():
    assert _meaningful_tokens("AB CD EF GHI JKL") == ["GHI", "JKL"]


def test_meaningful_tokens_handles_none_or_empty_text():
    assert _meaningful_tokens(None) == []
    assert _meaningful_tokens("") == []

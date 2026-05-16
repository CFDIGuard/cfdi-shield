from __future__ import annotations

import re
import unicodedata


BANKING_NOISE_WORDS = {
    "PAGO",
    "TRANSFERENCIA",
    "TRANSF",
    "SPEI",
    "ABONO",
    "CARGO",
    "REF",
    "REFERENCIA",
    "CONCEPTO",
    "PAG",
    "TRASPASO",
    "DEPOSITO",
    "DEPOSITO",
    "COBRO",
}


def _normalized_text(value: str | None) -> str:
    return str(value or "").strip().upper()


def _normalize_search_text(value: str | None) -> str:
    text = str(value or "").strip().upper()
    text = unicodedata.normalize("NFKD", text)
    text = "".join(character for character in text if not unicodedata.combining(character))
    return re.sub(r"[^A-Z0-9]+", " ", text).strip()


def _meaningful_tokens(value: str | None) -> list[str]:
    return [
        token
        for token in _normalize_search_text(value).split()
        if len(token) >= 3 and token not in BANKING_NOISE_WORDS
    ]

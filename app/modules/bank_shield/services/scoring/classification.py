from __future__ import annotations

from app.modules.bank_shield.services.scoring.rules import (
    CONCILIADO_THRESHOLD,
    MATCH_STATUS_CONCILIADO,
    MATCH_STATUS_PENDIENTE,
    MATCH_STATUS_POSIBLE,
    POSIBLE_THRESHOLD,
)


def _classify_match(score: float, uuid_detected: bool) -> str:
    if uuid_detected and score >= CONCILIADO_THRESHOLD:
        return MATCH_STATUS_CONCILIADO
    if score >= POSIBLE_THRESHOLD:
        return MATCH_STATUS_POSIBLE
    return MATCH_STATUS_PENDIENTE

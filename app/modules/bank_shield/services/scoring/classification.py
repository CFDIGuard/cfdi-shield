from __future__ import annotations


def _classify_match(score: float, uuid_detected: bool) -> str:
    if uuid_detected and score >= 80:
        return "CONCILIADO"
    if score >= 50:
        return "POSIBLE"
    return "PENDIENTE"

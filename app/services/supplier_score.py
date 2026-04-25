from __future__ import annotations

from app.services.risk_engine import has_provider_high_cancellation_risk

def calculate_supplier_score(
    cancellation_rate: float,
    cancellation_count: int = 0,
    invoice_count: int = 0,
    duplicate_count: int = 0,
    iva_inconsistency_count: int = 0,
    new_high_amount_count: int = 0,
) -> tuple[float, str]:
    score = (
        (35 if has_provider_high_cancellation_risk(cancellation_count, invoice_count) else 0)
        + duplicate_count * 10
        + iva_inconsistency_count * 12
        + new_high_amount_count * 15
    )
    score = round(min(100.0, score), 2)
    if score >= 70:
        return score, "ALTO"
    if score >= 35:
        return score, "MEDIO"
    return score, "BAJO"

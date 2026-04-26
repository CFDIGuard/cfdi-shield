from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from decimal import Decimal, InvalidOperation, ROUND_HALF_UP
import logging
import threading

import requests

from app.core.config import settings


logger = logging.getLogger(__name__)
_cache_lock = threading.Lock()
_exchange_rate_cache: dict[tuple[str, str], "ExchangeRateResult"] = {}
_MONEY_QUANTIZE = Decimal("0.01")


@dataclass(slots=True)
class ExchangeRateResult:
    moneda_original: str
    tipo_cambio_usado: float | None
    total_mxn: float | None
    fuente_tipo_cambio: str
    fecha_tipo_cambio: str | None


def _normalize_currency(value: str | None) -> str:
    return str(value or "MXN").strip().upper() or "MXN"


def _invoice_date(fecha_emision: str | None) -> str | None:
    if not fecha_emision:
        return None
    return fecha_emision[:10] if len(fecha_emision) >= 10 else None


def _to_decimal(value: float | int | str | None) -> Decimal | None:
    if value in (None, ""):
        return None
    try:
        return Decimal(str(value))
    except (InvalidOperation, TypeError, ValueError):
        return None


def _round_money(value: Decimal) -> float:
    return float(value.quantize(_MONEY_QUANTIZE, rounding=ROUND_HALF_UP))


def _build_result(
    *,
    moneda_original: str,
    total_original: float,
    tipo_cambio_usado: float | None,
    fuente_tipo_cambio: str,
    fecha_tipo_cambio: str | None,
) -> ExchangeRateResult:
    if tipo_cambio_usado is None:
        return ExchangeRateResult(
            moneda_original=moneda_original,
            tipo_cambio_usado=None,
            total_mxn=None,
            fuente_tipo_cambio=fuente_tipo_cambio,
            fecha_tipo_cambio=fecha_tipo_cambio,
        )

    total_decimal = _to_decimal(total_original) or Decimal("0")
    rate_decimal = _to_decimal(tipo_cambio_usado) or Decimal("0")
    total_mxn = _round_money(total_decimal * rate_decimal)
    return ExchangeRateResult(
        moneda_original=moneda_original,
        tipo_cambio_usado=float(rate_decimal),
        total_mxn=total_mxn,
        fuente_tipo_cambio=fuente_tipo_cambio,
        fecha_tipo_cambio=fecha_tipo_cambio,
    )


def _extract_rate(payload: dict[str, object]) -> tuple[float | None, str | None]:
    rates = payload.get("rates")
    if isinstance(rates, dict):
        rate = rates.get("MXN")
        if rate is not None:
            try:
                return float(rate), str(payload.get("date") or "")
            except (TypeError, ValueError):
                return None, None
    return None, None


def _fetch_rate_from_api(moneda_original: str, fecha_tipo_cambio: str | None) -> tuple[float | None, str | None]:
    base_url = settings.exchange_rate_api_url.rstrip("/")
    requests_to_try: list[tuple[str, dict[str, str]]] = []
    current_params = {"base": moneda_original, "quotes": "MXN"}
    if fecha_tipo_cambio:
        current_params["date"] = fecha_tipo_cambio
    requests_to_try.append((f"{base_url}/v2/rates", current_params))

    if fecha_tipo_cambio:
        requests_to_try.append(
            (f"{base_url}/{fecha_tipo_cambio}", {"base": moneda_original, "quotes": "MXN"})
        )
        requests_to_try.append(
            (f"{base_url}/{fecha_tipo_cambio}", {"from": moneda_original, "to": "MXN"})
        )

    requests_to_try.append((f"{base_url}/latest", {"from": moneda_original, "to": "MXN"}))

    for url, params in requests_to_try:
        try:
            response = requests.get(url, params=params, timeout=settings.exchange_rate_timeout_seconds)
            response.raise_for_status()
            rate, resolved_date = _extract_rate(response.json())
            if rate is not None:
                return rate, resolved_date or fecha_tipo_cambio
        except requests.RequestException as exc:
            logger.warning(
                "Exchange rate lookup failed for currency=%s date=%s: %s",
                moneda_original,
                fecha_tipo_cambio or "latest",
                exc,
            )
        except ValueError as exc:
            logger.warning(
                "Exchange rate payload invalid for currency=%s date=%s: %s",
                moneda_original,
                fecha_tipo_cambio or "latest",
                exc,
            )

    return None, None


def resolve_exchange_rate(
    *,
    moneda_original: str | None,
    total_original: float,
    tipo_cambio_xml: float | None,
    fecha_emision: str | None,
) -> ExchangeRateResult:
    normalized_currency = _normalize_currency(moneda_original)
    invoice_date = _invoice_date(fecha_emision)
    total_decimal = _to_decimal(total_original) or Decimal("0")

    if normalized_currency == "MXN":
        return _build_result(
            moneda_original="MXN",
            total_original=total_original,
            tipo_cambio_usado=1.0,
            fuente_tipo_cambio="MXN",
            fecha_tipo_cambio=invoice_date,
        )

    if total_decimal == Decimal("0"):
        if tipo_cambio_xml and tipo_cambio_xml > 0:
            return ExchangeRateResult(
                moneda_original=normalized_currency,
                tipo_cambio_usado=float(tipo_cambio_xml),
                total_mxn=0.0,
                fuente_tipo_cambio="XML",
                fecha_tipo_cambio=invoice_date,
            )
        return ExchangeRateResult(
            moneda_original=normalized_currency,
            tipo_cambio_usado=None,
            total_mxn=0.0,
            fuente_tipo_cambio="SIN_TOTAL",
            fecha_tipo_cambio=invoice_date,
        )

    if tipo_cambio_xml and tipo_cambio_xml > 0:
        return _build_result(
            moneda_original=normalized_currency,
            total_original=total_original,
            tipo_cambio_usado=tipo_cambio_xml,
            fuente_tipo_cambio="XML",
            fecha_tipo_cambio=invoice_date,
        )

    if not settings.enable_exchange_rate_api:
        return _build_result(
            moneda_original=normalized_currency,
            total_original=total_original,
            tipo_cambio_usado=None,
            fuente_tipo_cambio="PENDIENTE",
            fecha_tipo_cambio=invoice_date,
        )

    cache_key = (normalized_currency, invoice_date or "latest")
    with _cache_lock:
        cached = _exchange_rate_cache.get(cache_key)
    if cached is not None:
        return _build_result(
            moneda_original=normalized_currency,
            total_original=total_original,
            tipo_cambio_usado=cached.tipo_cambio_usado,
            fuente_tipo_cambio=cached.fuente_tipo_cambio,
            fecha_tipo_cambio=cached.fecha_tipo_cambio,
        )

    rate, resolved_date = _fetch_rate_from_api(normalized_currency, invoice_date)
    if rate is None:
        return _build_result(
            moneda_original=normalized_currency,
            total_original=total_original,
            tipo_cambio_usado=None,
            fuente_tipo_cambio="PENDIENTE",
            fecha_tipo_cambio=invoice_date,
        )

    cached_result = ExchangeRateResult(
        moneda_original=normalized_currency,
        tipo_cambio_usado=rate,
        total_mxn=None,
        fuente_tipo_cambio="API",
        fecha_tipo_cambio=resolved_date or invoice_date,
    )
    with _cache_lock:
        _exchange_rate_cache[cache_key] = cached_result

    return _build_result(
        moneda_original=normalized_currency,
        total_original=total_original,
        tipo_cambio_usado=rate,
        fuente_tipo_cambio="API",
        fecha_tipo_cambio=resolved_date or invoice_date,
    )

from __future__ import annotations

"""
Rate limiting simple en memoria.

Limitaciones conocidas:
- No persiste entre reinicios del proceso.
- No se comparte entre multiples workers o replicas.
- Debe migrarse a un backend compartido (por ejemplo Redis) para produccion escalada.
"""

from collections import defaultdict, deque
from time import time

from app.core.config import settings


_rate_limit_store: dict[str, deque[float]] = defaultdict(deque)


def _key(action: str, scope: str, value: str) -> str:
    return f"{action}:{scope}:{value.strip().lower()}"


def _prune(bucket: deque[float], now: float, window_seconds: int) -> None:
    threshold = now - window_seconds
    while bucket and bucket[0] < threshold:
        bucket.popleft()


def _get_bucket(action: str, scope: str, value: str, now: float, window_seconds: int) -> deque[float]:
    storage_key = _key(action, scope, value)
    bucket = _rate_limit_store[storage_key]
    _prune(bucket, now, window_seconds)
    if not bucket:
        _rate_limit_store.pop(storage_key, None)
        bucket = _rate_limit_store[storage_key]
    return bucket


def is_rate_limited(action: str, ip_address: str | None, username: str | None) -> bool:
    now = time()
    window = settings.auth_rate_limit_window_seconds

    if ip_address:
        ip_bucket = _get_bucket(action, "ip", ip_address, now, window)
        if len(ip_bucket) >= settings.auth_rate_limit_ip_max_attempts:
            return True

    if username:
        user_bucket = _get_bucket(action, "user", username, now, window)
        if len(user_bucket) >= settings.auth_rate_limit_user_max_attempts:
            return True

    return False


def record_rate_limit_failure(action: str, ip_address: str | None, username: str | None) -> None:
    now = time()
    window = settings.auth_rate_limit_window_seconds

    if ip_address:
        ip_bucket = _get_bucket(action, "ip", ip_address, now, window)
        ip_bucket.append(now)

    if username:
        user_bucket = _get_bucket(action, "user", username, now, window)
        user_bucket.append(now)


def clear_rate_limit(action: str, ip_address: str | None, username: str | None) -> None:
    if ip_address:
        _rate_limit_store.pop(_key(action, "ip", ip_address), None)
    if username:
        _rate_limit_store.pop(_key(action, "user", username), None)

from __future__ import annotations


def mask_uuid(value: str | None) -> str:
    if not value:
        return "***"
    compact = value.strip()
    if len(compact) <= 8:
        return "***"
    return f"...{compact[-8:]}"


def mask_rfc(value: str | None) -> str:
    if not value:
        return "***"
    compact = value.strip().upper()
    if len(compact) <= 4:
        return compact[:1] + "***"
    return f"{compact[:3]}***{compact[-2:]}"


def mask_username(value: str | None) -> str:
    if not value:
        return "***"
    candidate = value.strip()
    if "@" in candidate:
        local, domain = candidate.split("@", 1)
        if len(local) <= 2:
            local_masked = local[:1] + "*"
        else:
            local_masked = local[:2] + "***"
        return f"{local_masked}@{domain}"
    if len(candidate) <= 3:
        return candidate[:1] + "***"
    return candidate[:2] + "***"

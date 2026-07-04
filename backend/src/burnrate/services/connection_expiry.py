from __future__ import annotations

from datetime import UTC, datetime

# Derived status buckets for a bank connection's consent window.
EXPIRY_UNKNOWN = "unknown"
EXPIRY_ACTIVE = "active"
EXPIRY_EXPIRING_SOON = "expiring_soon"
EXPIRY_EXPIRED = "expired"


def as_utc(value: datetime | None) -> datetime | None:
    """Coerce a possibly-naive datetime (e.g. read back from SQLite) to UTC-aware."""
    if value is None:
        return None
    if value.tzinfo is None:
        return value.replace(tzinfo=UTC)
    return value


def expiry_status(
    expires_at: datetime | None,
    *,
    now: datetime,
    warning_days: int,
) -> tuple[str, int | None]:
    """Classify a consent window into a status and whole days remaining.

    Returns ``(status, days_until_expiry)``. ``days_until_expiry`` is ``None`` when
    no expiry is known, negative once past. A connection is "expiring_soon" from
    ``warning_days`` out until it lapses, then "expired".
    """
    expires = as_utc(expires_at)
    if expires is None:
        return EXPIRY_UNKNOWN, None
    days = (expires - now).days
    if expires <= now:
        return EXPIRY_EXPIRED, days
    if days <= warning_days:
        return EXPIRY_EXPIRING_SOON, days
    return EXPIRY_ACTIVE, days

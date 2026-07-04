from __future__ import annotations

from datetime import UTC, datetime, timedelta

from burnrate.services.connection_expiry import (
    EXPIRY_ACTIVE,
    EXPIRY_EXPIRED,
    EXPIRY_EXPIRING_SOON,
    EXPIRY_UNKNOWN,
    as_utc,
    expiry_status,
)

NOW = datetime(2026, 7, 4, tzinfo=UTC)


def test_unknown_when_no_expiry() -> None:
    assert expiry_status(None, now=NOW, warning_days=7) == (EXPIRY_UNKNOWN, None)


def test_active_when_far_out() -> None:
    status, days = expiry_status(NOW + timedelta(days=30), now=NOW, warning_days=7)
    assert status == EXPIRY_ACTIVE
    assert days == 30


def test_expiring_soon_within_window() -> None:
    status, days = expiry_status(NOW + timedelta(days=3), now=NOW, warning_days=7)
    assert status == EXPIRY_EXPIRING_SOON
    assert days == 3


def test_expiring_soon_on_boundary() -> None:
    status, _ = expiry_status(NOW + timedelta(days=7), now=NOW, warning_days=7)
    assert status == EXPIRY_EXPIRING_SOON


def test_expired_when_past() -> None:
    status, days = expiry_status(NOW - timedelta(days=2), now=NOW, warning_days=7)
    assert status == EXPIRY_EXPIRED
    assert days < 0


def test_as_utc_coerces_naive_to_utc() -> None:
    naive = datetime(2026, 7, 4, 12, 0, 0)
    assert as_utc(naive).tzinfo is UTC
    assert as_utc(None) is None

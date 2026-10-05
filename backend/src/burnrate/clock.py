from __future__ import annotations

from datetime import UTC, date, datetime
from zoneinfo import ZoneInfo


def civil_date(*, timezone_name: str, instant: datetime | None = None) -> date:
    """Resolve the calendar day an instant falls on in the given IANA timezone.

    Deriving a civil date straight from UTC reports yesterday to an owner ahead of
    it just after local midnight, and the whole previous month on the 1st. Every
    place BurnRate needs "today" or "this month" resolves it through here, so the
    answer is the same wherever it is asked.
    """
    moment = instant or datetime.now(UTC)
    if moment.tzinfo is None:
        # astimezone() would read a naive value as the host's local time, so the
        # same reading would resolve to a different day on a differently
        # configured container. Fail instead of guessing.
        raise ValueError("civil_date needs an aware instant, got a naive datetime")
    return moment.astimezone(ZoneInfo(timezone_name)).date()

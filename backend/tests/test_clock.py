from __future__ import annotations

from datetime import UTC, date, datetime

import pytest

from burnrate.clock import civil_date
from conftest import AHEAD_OF_UTC, BEHIND_UTC

AHEAD_TZ, AHEAD_INSTANT, _ = AHEAD_OF_UTC
BEHIND_TZ, BEHIND_INSTANT, _ = BEHIND_UTC


# Every civil date in the product resolves through ``civil_date``, so the four
# services and the notifier all inherit whatever this gets wrong. It had no test of
# its own: the zone conversion was covered transitively through those callers, which
# means a regression here surfaced as an unrelated service failing.
#
# timezone, instant, the owner's calendar day, what UTC would have said instead
CIVIL_DAY_EXAMPLES = [
    (AHEAD_TZ, AHEAD_INSTANT, date(2026, 7, 1), date(2026, 6, 30)),
    (BEHIND_TZ, BEHIND_INSTANT, date(2026, 6, 30), date(2026, 7, 1)),
]


@pytest.mark.parametrize(
    ("timezone_name", "instant", "owners_day", "utc_day"),
    CIVIL_DAY_EXAMPLES,
)
def test_civil_date_resolves_the_owners_day_not_utcs(
    timezone_name: str,
    instant: datetime,
    owners_day: date,
    utc_day: date,
) -> None:
    resolved = civil_date(timezone_name=timezone_name, instant=instant)

    assert resolved == owners_day
    # Stated rather than implied: both rows sit on a month boundary, so the day UTC
    # would have reported is in the adjacent month. That difference is the whole
    # reason the helper exists, and asserting only the first line would pass for a
    # function that ignored the timezone in one direction.
    assert instant.date() == utc_day
    assert resolved.month != utc_day.month


def test_civil_date_rejects_a_naive_instant() -> None:
    # astimezone() would read a naive value as the host's local time, so the same
    # reading would resolve to a different day on a differently configured container.
    # Failing closed is what keeps a misconfigured deployment from silently filing
    # charges into the wrong month.
    with pytest.raises(ValueError, match="aware instant"):
        civil_date(timezone_name="Europe/Madrid", instant=datetime(2026, 6, 30, 23, 0))


def test_civil_date_keeps_an_instant_inside_the_day_it_already_belongs_to() -> None:
    # Midday is the uninteresting case, and it is here so the boundary rows above
    # cannot be satisfied by a function that simply shifts every date by one.
    assert civil_date(
        timezone_name="Europe/Madrid",
        instant=datetime(2026, 6, 15, 12, 0, tzinfo=UTC),
    ) == date(2026, 6, 15)


def test_civil_date_requires_an_instant() -> None:
    # The seam only holds if a caller cannot quietly fall back to the wall clock:
    # that fallback is why three of the four call sites went uncovered for six phases.
    with pytest.raises(TypeError):
        civil_date(timezone_name="Europe/Madrid")  # type: ignore[call-arg]

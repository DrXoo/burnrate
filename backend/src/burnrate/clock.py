"""The owner's calendar day, and the one seam for asking what it is.

Every place BurnRate needs "today" or "this month" resolves it through
``civil_date`` below, so the answer is the same wherever it is asked.

**``instant`` is required**, which is the whole point of this module's shape: a
caller cannot fall back to the wall clock by omitting it. That is not a style
preference. Letting ``civil_date`` read the clock itself left freezing the process
clock as the only way to exercise a month-end boundary, which ``AGENTS.md`` rules
out -- and it is why three of the four call sites went uncovered through six
phases. Whoever holds the clock has to say so out loud.

So every caller needs an instant, and there are two shapes for getting one.

**A service takes it as an injectable clock:**

```python
clock: Callable[[], datetime] | None = None,
...
self._clock = clock or (lambda: datetime.now(UTC))
```

Where the zone comes from depends on what the service already holds.
``SummaryService``, ``BudgetService`` and ``TelegramCommandRouter`` take a
``timezone_name: str = "UTC"`` beside the clock; ``EnableBankingService`` already
takes the whole ``Settings`` object and reads ``settings.app_timezone`` instead of
duplicating it. Both are fine -- what matters is the clock, not how the zone is
spelled. A fifth service with no ``Settings`` should copy the first form.

**A plain function takes an optional aware ``now``** and resolves it itself, as
``telegram.notifier.send_sync_notification`` does:

```python
civil_date(timezone_name=settings.app_timezone, instant=now or datetime.now(UTC))
```

Production passes no clock and gets the real one; tests pass the instant that sits
on the boundary. ``tests/conftest.py`` holds the two boundary instants the suite
asserts against, one zone ahead of UTC and one behind.
"""

from __future__ import annotations

from datetime import date, datetime
from zoneinfo import ZoneInfo


def civil_date(*, timezone_name: str, instant: datetime) -> date:
    """Resolve the calendar day an instant falls on in the given IANA timezone.

    Deriving a civil date straight from UTC reports yesterday to an owner ahead of
    it just after local midnight, and the whole previous month on the 1st.

    ``instant`` must be aware. A naive one is rejected rather than assumed to be
    UTC: ``astimezone`` would read it as the host's local time, so the same reading
    would resolve to a different day on a differently configured container.
    """
    if instant.tzinfo is None:
        raise ValueError("civil_date needs an aware instant, got a naive datetime")
    return instant.astimezone(ZoneInfo(timezone_name)).date()

"""Reading which days the bank was actually asked about, for the two callers that ask.

The rule itself is pure and lives in ``burnrate.domain.sync_coverage``. This is the
one place that reads the sync history out of the database for it, because two callers
need the same answer and asking it twice is how two readers come to disagree:

* the **summary**, so the owner opening the app is told a month cannot be trusted --
  which is the only path that catches the failure that actually happened, a worker
  down for 36 days, because a process that is not running cannot report itself;
* the **worker**, so the product says so unprompted when something is lost or about
  to be.

``BaselineService`` reads the same history for its Qualifying Month test and gets it
from here as well, rather than keeping the query it used to own.
"""

from __future__ import annotations

from collections.abc import Callable
from datetime import UTC, date, datetime, timedelta

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from burnrate.clock import civil_date
from burnrate.db.models import SyncSession
from burnrate.domain.sync_coverage import SyncGap, sync_gap
from burnrate.services.connection_expiry import as_utc
from burnrate.services.enable_banking_service import TRANSACTION_WINDOW

SYNC_GAP_LOOKBACK_DAYS = 90
"""How far back a gap is still worth reporting.

Permanent damage never becomes recoverable, so without a bound the product would
report the owner's August 2026 loss on every run for the rest of its life -- and an
alert that cannot stop is an alert that gets muted. Ninety days is wider than the
30-day fetch window by enough that a gap is reported for a good while after it
hardens, and narrow enough to fall silent eventually.
"""


def successful_sync_days(
    *, db: Session, since: date, timezone_name: str
) -> list[date]:
    """The owner's civil days on which a sync actually succeeded, oldest first.

    Only ``success`` counts. ``skipped`` is the status an expired consent writes, once
    per attempt, so it papers over the very gap this exists to find; ``failed`` learned
    nothing and ``running`` has not finished learning.

    Bounded below by ``since`` less a day, for the timezone conversion: a run whose
    window closed before the period opened cannot cover any part of it.
    """
    floor = datetime(since.year, since.month, since.day, tzinfo=UTC) - timedelta(days=1)
    instants = db.scalars(
        select(SyncSession.started_at).where(
            func.lower(SyncSession.status) == "success",
            SyncSession.started_at >= floor,
        )
    ).all()
    return sorted(
        {
            civil_date(timezone_name=timezone_name, instant=as_utc(instant))
            for instant in instants
            if instant is not None
        }
    )


class SyncCoverageService:
    """What the sync history says about whether the figures can be trusted."""

    def __init__(
        self,
        *,
        db: Session,
        timezone_name: str = "UTC",
        clock: Callable[[], datetime] | None = None,
    ) -> None:
        self.db = db
        self._timezone_name = timezone_name
        self._clock = clock or (lambda: datetime.now(UTC))

    def owner_today(self) -> date:
        """The owner's civil day, from the injected clock. See ``burnrate.clock``."""
        return civil_date(timezone_name=self._timezone_name, instant=self._clock())

    def current_gap(self, *, today: date | None = None) -> SyncGap | None:
        """The gap in the recent past, or ``None`` when every day was asked about.

        ``today`` is the owner's civil day and is taken from the injected clock when
        not given, never from the wall clock directly -- the convention
        ``burnrate.clock`` states, so a test can fix the day without freezing the
        process.
        """
        day = today or self.owner_today()
        # One day of slack below the lookback, so the sweep's own clamp has the first
        # coverable day available rather than inferring it from a truncated history.
        since = day - timedelta(days=SYNC_GAP_LOOKBACK_DAYS + TRANSACTION_WINDOW.days)
        return sync_gap(
            today=day,
            successful_sync_days=successful_sync_days(
                db=self.db,
                since=since,
                timezone_name=self._timezone_name,
            ),
            fetch_window_days=TRANSACTION_WINDOW.days,
            lookback_days=SYNC_GAP_LOOKBACK_DAYS,
        )

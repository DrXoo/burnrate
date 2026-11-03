from __future__ import annotations

from datetime import datetime
from zoneinfo import ZoneInfo

import pytest

from burnrate import worker
from burnrate.config import Settings
from burnrate.sync_schedule import next_sync_at


def make_settings(sync_cron: str, app_timezone: str = "UTC") -> Settings:
    return Settings(
        SYNC_CRON=sync_cron,
        APP_TIMEZONE=app_timezone,
        DATABASE_URL="sqlite+pysqlite:///:memory:",
    )


@pytest.mark.parametrize(
    "sync_cron,app_timezone",
    [
        ("0 11,20 * * *", "UTC"),
        ("0 11,20 * * *", "Europe/Madrid"),
        ("*/30 * * * *", "Europe/Madrid"),
        ("0 23 * * *", "Pacific/Auckland"),
    ],
)
def test_the_published_next_sync_is_the_workers_own_next_fire(
    sync_cron: str, app_timezone: str
) -> None:
    """One schedule, two readers, and they must not be able to disagree.

    What the owner is told and what the worker does are derived from the same
    ``SYNC_CRON`` through the same trigger, so changing the cron changes both with no
    second place to update. A test that asserted "21:00" instead would pass against a
    constant anywhere -- in the client, in a formatter, in a second cron parser -- and
    would prove nothing about the worker.
    """
    settings = make_settings(sync_cron, app_timezone)
    after = datetime(2026, 11, 3, 15, 40, tzinfo=ZoneInfo(app_timezone))

    published = next_sync_at(
        sync_cron=settings.sync_cron,
        timezone_name=settings.app_timezone,
        after=after,
    )
    worker_trigger = worker.build_scheduler(settings).get_jobs()[0].trigger

    assert published == worker_trigger.get_next_fire_time(None, after)


def test_the_next_sync_is_resolved_on_the_owners_clock() -> None:
    """``0 20 * * *`` means 20:00 where the owner lives, not 20:00 UTC.

    The instant handed in is deliberately an hour before the fire time *in UTC* and
    well after it in Madrid, so a function that ignored the zone would answer today
    and the right one answers tomorrow.
    """
    madrid = ZoneInfo("Europe/Madrid")

    nxt = next_sync_at(
        sync_cron="0 20 * * *",
        timezone_name="Europe/Madrid",
        after=datetime(2026, 11, 3, 21, 30, tzinfo=madrid),
    )

    assert nxt is not None
    assert nxt.astimezone(madrid).isoformat() == "2026-11-04T20:00:00+01:00"


def test_an_unparseable_cron_has_no_next_sync_rather_than_a_crash() -> None:
    """The worker fails fast on a bad cron; a read of ``/summary`` must not.

    These are different jobs. A misconfigured cron should stop the worker at startup,
    which ``build_scheduler`` already does, but it must not take the dashboard down
    with it -- the owner needs the screen that would tell them something is wrong.
    """
    assert (
        next_sync_at(sync_cron="not-a-cron", timezone_name="UTC", after=datetime.now(ZoneInfo("UTC")))
        is None
    )

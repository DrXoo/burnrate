from __future__ import annotations

from datetime import datetime, timedelta
from zoneinfo import ZoneInfo

import pytest

from burnrate import worker
from burnrate.config import Settings


def make_settings(sync_cron: str, app_timezone: str = "UTC") -> Settings:
    return Settings(
        SYNC_CRON=sync_cron,
        APP_TIMEZONE=app_timezone,
        DATABASE_URL="sqlite+pysqlite:///:memory:",
    )


def test_build_scheduler_registers_sync_job_from_cron() -> None:
    scheduler = worker.build_scheduler(make_settings("*/30 * * * *"))

    jobs = scheduler.get_jobs()
    assert len(jobs) == 1
    assert jobs[0].id == "enable_banking_sync"
    assert jobs[0].func is worker.run_scheduled_sync


def test_build_scheduler_rejects_invalid_cron() -> None:
    with pytest.raises(ValueError):
        worker.build_scheduler(make_settings("not-a-cron"))


def test_build_scheduler_runs_the_cron_on_the_owners_clock() -> None:
    # "23:00" in SYNC_CRON means 23:00 where the owner lives. Firing it on UTC instead
    # runs the pass at 01:00 local the next civil day, which on the 1st of a month has
    # already rolled the month window over before the old month's last day is fetched.
    scheduler = worker.build_scheduler(make_settings("0 23 * * *", app_timezone="Europe/Madrid"))

    trigger = scheduler.get_jobs()[0].trigger
    assert str(trigger.timezone) == "Europe/Madrid"


def test_main_reports_a_sync_gap_before_it_starts_scheduling(monkeypatch) -> None:
    """The wiring, which is the half nobody usually covers.

    The report is useless if ``main`` never calls it, and the function itself passing
    its own tests says nothing about that. The scheduler is stubbed so ``main`` does
    not block, and the order is asserted as well as the call: a worker that has just
    come back from an outage should say so before it spends half an hour waiting for
    its first cron tick.
    """
    events: list[str] = []

    class StubScheduler:
        def start(self) -> None:
            events.append("scheduler")

        def shutdown(self, wait: bool = True) -> None:
            pass

    monkeypatch.setattr(worker, "get_settings", lambda: make_settings("*/30 * * * *"))
    monkeypatch.setattr(worker, "build_scheduler", lambda settings: StubScheduler())
    monkeypatch.setattr(
        worker, "report_sync_gap_at_startup", lambda settings: events.append("gap report")
    )

    worker.main()

    assert events == ["gap report", "scheduler"]


def test_report_sync_gap_at_startup_is_silent_without_telegram_configured() -> None:
    """Guarded like every other notifier call in the worker, and never raises.

    A worker with no bot token must start normally rather than failing on a
    notification it was never meant to send.
    """
    worker.report_sync_gap_at_startup(make_settings("*/30 * * * *"))


def test_the_default_cadence_stays_inside_the_regulated_access_budget() -> None:
    """A deployment with no ``SYNC_CRON`` must not start outside PSD2.

    The default was ``*/30 * * * *`` -- 48 passes a day -- against a budget of four
    unattended accesses per 24 hours, which a sync spends one of per call per account.
    That is the defect ADR-0015 records, and the default is the one place it can ship
    to someone who never reads a doc.

    Counted by walking the trigger rather than by comparing the cron string, so the
    assertion is about how often the worker *fires* and not about the spelling it was
    configured with.
    """
    settings = Settings(DATABASE_URL="sqlite+pysqlite:///:memory:")
    trigger = worker.build_scheduler(settings).get_jobs()[0].trigger

    start = datetime(2026, 11, 3, tzinfo=ZoneInfo(settings.app_timezone))
    fires = []
    previous = None
    while True:
        nxt = trigger.get_next_fire_time(previous, start if previous is None else previous)
        if nxt is None or nxt >= start + timedelta(days=1):
            break
        fires.append(nxt)
        previous = nxt

    assert len(fires) <= 2, f"the default cadence fires {len(fires)} times a day: {fires}"

"""The sync schedule, and the one place it is read from.

``SYNC_CRON`` has two readers: the worker, which fires on it, and ``/summary``, which
tells the owner when the next pass is due. They are built from the same trigger here
so they cannot disagree -- a second cron parser, in a formatter or in the client,
would be a second place to update and a chance for the screen to promise a time the
worker never intends to honour.

Why the backend answers this at all, rather than publishing the cron for a client to
parse: a client deriving a system fact is the rule ``ADR-0002`` exists for, and the
schedule depends on ``APP_TIMEZONE``, which no browser can know. See
``ADR-0015`` for why the cadence is what it is.
"""

from __future__ import annotations

from datetime import datetime

from apscheduler.triggers.cron import CronTrigger


def build_sync_trigger(*, sync_cron: str, timezone_name: str) -> CronTrigger:
    """Build the trigger the sync worker fires on.

    Raises ``ValueError`` if the cron is not parseable, so a misconfigured worker
    fails at startup rather than silently never syncing.
    """
    return CronTrigger.from_crontab(sync_cron, timezone=timezone_name)


def next_sync_at(*, sync_cron: str, timezone_name: str, after: datetime) -> datetime | None:
    """When the next unattended sync is due, or ``None`` if that cannot be said.

    ``None`` covers a cron the trigger cannot parse and a schedule with no further
    fire time. Both are reported as "unknown" rather than raised, because the caller
    is a dashboard read: a bad cron should stop the worker, not the screen that would
    tell the owner so.

    This answers only what the schedule *says*. It is not a promise the sync will
    happen -- a worker that is not running cannot contradict it, which is why the
    interface shows it only while the connection is healthy. ``ADR-0013`` records
    that hole as deliberately not closed.
    """
    try:
        trigger = build_sync_trigger(sync_cron=sync_cron, timezone_name=timezone_name)
    except ValueError:
        return None
    return trigger.get_next_fire_time(None, after)

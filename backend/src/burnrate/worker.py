from __future__ import annotations

import logging

from apscheduler.schedulers.blocking import BlockingScheduler
from sqlalchemy.orm import Session

from burnrate.config import Settings, get_settings
from burnrate.db.session import SessionLocal
from burnrate.integrations.enable_banking.client import EnableBankingClient
from burnrate.integrations.telegram.client import TelegramClient
from burnrate.logging_config import configure_logging
from burnrate.services.enable_banking_service import EnableBankingService
from burnrate.services.sync_service import SyncRunResult, SyncService
from burnrate.sync_schedule import build_sync_trigger
from burnrate.telegram.notifier import (
    send_expiry_alerts,
    send_reconnect_alerts,
    send_sync_gap_alert,
    send_sync_notification,
)

logger = logging.getLogger("burnrate.sync_worker")

SYNC_JOB_ID = "enable_banking_sync"


def run_scheduled_sync(settings: Settings | None = None) -> None:
    """Run one synchronization pass over all active connections.

    This is the unit the scheduler invokes on each tick. It owns a single
    database session for the run and never raises, so a failing pass cannot
    crash the worker process.
    """
    settings = settings or get_settings()
    session = SessionLocal()
    try:
        client = EnableBankingClient(settings=settings)
        enable_banking_service = EnableBankingService(db=session, settings=settings, client=client)
        sync_service = SyncService(db=session, enable_banking_service=enable_banking_service)
        result = sync_service.sync_all_active_connections()
        session.commit()
        logger.info(
            "Scheduled sync finished: connections=%s succeeded=%s failed=%s",
            result.total_connections,
            result.succeeded,
            result.failed,
        )
        _notify_new_transactions(session=session, result=result, settings=settings)
        _alert_reconnect_needed(session=session, result=result, settings=settings)
        _alert_expiring_connections(session=session, settings=settings)
    except Exception:
        session.rollback()
        logger.exception("Scheduled sync run failed unexpectedly")
    finally:
        session.close()


def _notify_new_transactions(*, session: Session, result: SyncRunResult, settings: Settings) -> None:
    """Best-effort Telegram push after a sync; never disturbs the sync run.

    Kept separate (and fully guarded) so a Telegram outage or misconfiguration
    can't trip the sync's own error path.
    """
    if not settings.telegram_bot_token or not settings.telegram_notify_on_sync:
        return
    try:
        client = TelegramClient(settings=settings)
        send_sync_notification(run_result=result, session=session, client=client, settings=settings)
    except Exception:
        logger.exception("Failed to send new-transaction notification")


def _alert_reconnect_needed(*, session: Session, result: SyncRunResult, settings: Settings) -> None:
    """Best-effort Telegram alert when a sync found a connection needing reconnection.

    Fires as soon as a bank session closes or rejects access with a 401, so the
    user can re-authorize promptly. Guarded like the other notifiers and commits
    its own debounce bookkeeping so the alert isn't repeated every tick.
    """
    if not settings.telegram_bot_token or not settings.telegram_notify_on_sync:
        return
    try:
        client = TelegramClient(settings=settings)
        sent = send_reconnect_alerts(run_result=result, session=session, client=client, settings=settings)
        if sent:
            session.commit()
    except Exception:
        session.rollback()
        logger.exception("Failed to send connection-reconnect alert")


def _alert_expiring_connections(*, session: Session, settings: Settings) -> None:
    """Best-effort proactive Telegram warning for lapsing bank connections.

    Fully guarded like the transaction notifier, and commits its own debounce
    bookkeeping so a warning is not repeated on every sync tick.
    """
    if not settings.telegram_bot_token or not settings.telegram_notify_on_sync:
        return
    try:
        client = TelegramClient(settings=settings)
        sent = send_expiry_alerts(session=session, client=client, settings=settings)
        if sent:
            session.commit()
    except Exception:
        session.rollback()
        logger.exception("Failed to send connection-expiry alert")


def report_sync_gap_at_startup(settings: Settings) -> None:
    """Say so, once, if days of bank data were never fetched while this was down.

    Startup rather than per sync pass, because the failure this covers is the worker
    not running and a process that is not running cannot report itself -- and because
    starting up is what debounces it: a pass runs every half hour, and a permanent gap
    reported per pass would be 48 messages a day for the ninety days of the lookback.

    Guarded and best-effort like every other notifier call here. A worker must start
    whether or not it can send a message.
    """
    if not settings.telegram_bot_token or not settings.telegram_notify_on_sync:
        return
    session = SessionLocal()
    try:
        client = TelegramClient(settings=settings)
        send_sync_gap_alert(session=session, client=client, settings=settings)
    except Exception:
        logger.exception("Failed to report sync gap at startup")
    finally:
        session.close()


def build_scheduler(settings: Settings) -> BlockingScheduler:
    """Build a scheduler that runs the sync pass on the configured cron.

    The cron runs on ``APP_TIMEZONE``, the same clock as every other civil date the
    product derives, because an hour in ``SYNC_CRON`` is one the owner chose by
    looking at their own day. Pinning it to UTC made "0 23 * * *" fire at 01:00 the
    following local day for an owner an hour ahead, and on the 1st of a month that
    run's month window had already rolled over before the old month's last day was
    fetched. ``APP_TIMEZONE`` is validated as an IANA name in ``Settings``.

    Raises ``ValueError`` if ``SYNC_CRON`` is not a valid cron expression so a
    misconfigured worker fails fast at startup instead of silently never syncing.

    The trigger is built by ``sync_schedule.build_sync_trigger``, which is also what
    ``/summary`` reads to tell the owner when the next pass is due. One construction,
    so what the screen promises and what this fires on cannot drift apart.
    """
    scheduler = BlockingScheduler(timezone=settings.app_timezone)
    scheduler.add_job(
        run_scheduled_sync,
        trigger=build_sync_trigger(sync_cron=settings.sync_cron, timezone_name=settings.app_timezone),
        id=SYNC_JOB_ID,
        max_instances=1,
        coalesce=True,
    )
    return scheduler


def main() -> None:
    settings = get_settings()
    configure_logging(settings.log_level)
    logger.info("Starting sync worker with schedule %s (%s)", settings.sync_cron, settings.app_timezone)
    # Before the first cron tick, which since ADR-0015 can be most of a day away: a
    # worker that has just returned from an outage has something to say now, not later.
    report_sync_gap_at_startup(settings)
    scheduler = build_scheduler(settings)
    try:
        scheduler.start()
    except (KeyboardInterrupt, SystemExit):
        logger.info("Sync worker shutting down")
        scheduler.shutdown(wait=False)


if __name__ == "__main__":
    main()

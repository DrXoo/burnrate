from __future__ import annotations

import logging

from apscheduler.schedulers.blocking import BlockingScheduler
from apscheduler.triggers.cron import CronTrigger
from sqlalchemy.orm import Session

from burnrate.config import Settings, get_settings
from burnrate.db.session import SessionLocal
from burnrate.integrations.enable_banking.client import EnableBankingClient
from burnrate.integrations.telegram.client import TelegramClient
from burnrate.logging_config import configure_logging
from burnrate.services.enable_banking_service import EnableBankingService
from burnrate.services.sync_service import SyncRunResult, SyncService
from burnrate.telegram.notifier import send_expiry_alerts, send_sync_notification

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


def build_scheduler(settings: Settings) -> BlockingScheduler:
    """Build a scheduler that runs the sync pass on the configured cron.

    Raises ``ValueError`` if ``SYNC_CRON`` is not a valid cron expression so a
    misconfigured worker fails fast at startup instead of silently never syncing.
    """
    scheduler = BlockingScheduler(timezone="UTC")
    scheduler.add_job(
        run_scheduled_sync,
        trigger=CronTrigger.from_crontab(settings.sync_cron, timezone="UTC"),
        id=SYNC_JOB_ID,
        max_instances=1,
        coalesce=True,
    )
    return scheduler


def main() -> None:
    settings = get_settings()
    configure_logging(settings.log_level)
    logger.info("Starting sync worker with schedule %s", settings.sync_cron)
    scheduler = build_scheduler(settings)
    try:
        scheduler.start()
    except (KeyboardInterrupt, SystemExit):
        logger.info("Sync worker shutting down")
        scheduler.shutdown(wait=False)


if __name__ == "__main__":
    main()

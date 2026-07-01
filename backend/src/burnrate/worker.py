from __future__ import annotations

import logging

from apscheduler.schedulers.blocking import BlockingScheduler
from apscheduler.triggers.cron import CronTrigger

from burnrate.config import Settings, get_settings
from burnrate.db.session import SessionLocal
from burnrate.integrations.enable_banking.client import EnableBankingClient
from burnrate.services.enable_banking_service import EnableBankingService
from burnrate.services.sync_service import SyncService

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
    except Exception:
        session.rollback()
        logger.exception("Scheduled sync run failed unexpectedly")
    finally:
        session.close()


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
    logging.basicConfig(level=logging.INFO)
    settings = get_settings()
    logger.info("Starting sync worker with schedule %s", settings.sync_cron)
    scheduler = build_scheduler(settings)
    try:
        scheduler.start()
    except (KeyboardInterrupt, SystemExit):
        logger.info("Sync worker shutting down")
        scheduler.shutdown(wait=False)


if __name__ == "__main__":
    main()

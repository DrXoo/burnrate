from __future__ import annotations

import pytest

from burnrate import worker
from burnrate.config import Settings


def make_settings(sync_cron: str) -> Settings:
    return Settings(SYNC_CRON=sync_cron, DATABASE_URL="sqlite+pysqlite:///:memory:")


def test_build_scheduler_registers_sync_job_from_cron() -> None:
    scheduler = worker.build_scheduler(make_settings("*/30 * * * *"))

    jobs = scheduler.get_jobs()
    assert len(jobs) == 1
    assert jobs[0].id == "enable_banking_sync"
    assert jobs[0].func is worker.run_scheduled_sync


def test_build_scheduler_rejects_invalid_cron() -> None:
    with pytest.raises(ValueError):
        worker.build_scheduler(make_settings("not-a-cron"))

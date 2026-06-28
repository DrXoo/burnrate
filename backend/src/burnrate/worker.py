from __future__ import annotations

import logging
import time

from burnrate.config import get_settings

logger = logging.getLogger("burnrate.sync_worker")


def main() -> None:
    settings = get_settings()
    logging.basicConfig(level=logging.INFO)
    logger.info("Starting sync worker with schedule %s", settings.sync_cron)
    while True:
        logger.info("Sync worker heartbeat")
        time.sleep(60)


if __name__ == "__main__":
    main()


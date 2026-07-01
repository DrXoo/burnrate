from __future__ import annotations

import logging

LOG_FORMAT = "%(asctime)s %(levelname)s %(name)s: %(message)s"


def configure_logging(level: str = "INFO") -> None:
    """Configure process-wide logging.

    Called once at each runtime entrypoint (API startup, sync worker) so the
    backend and worker emit logs in the same format at the configured level.
    """
    logging.basicConfig(level=level.upper(), format=LOG_FORMAT, force=True)

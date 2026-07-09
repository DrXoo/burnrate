from __future__ import annotations

from dataclasses import dataclass, field
import logging

from sqlalchemy import select
from sqlalchemy.orm import Session

from burnrate.db.models import EnableBankingConnection
from burnrate.integrations.enable_banking.client import EnableBankingAPIError
from burnrate.services.enable_banking_service import EnableBankingService

logger = logging.getLogger(__name__)

# HTTP statuses from Enable Banking that mean the bank consent is gone and only a
# fresh authorization (reconnect) can restore access — retrying won't help.
_REAUTH_STATUS_CODES = frozenset({401, 403})


@dataclass
class ConnectionSyncResult:
    connection_id: str
    aspsp_name: str
    status: str
    accounts_synced: int = 0
    transactions_imported: int = 0
    error: str | None = None
    # True when the connection can only be fixed by re-authorizing in the web app
    # (session closed/expired, or the bank rejected account access with a 401/403).
    needs_reauth: bool = False


@dataclass
class SyncRunResult:
    total_connections: int = 0
    succeeded: int = 0
    skipped: int = 0
    failed: int = 0
    results: list[ConnectionSyncResult] = field(default_factory=list)


class SyncService:
    """Orchestrates background synchronization across all active bank connections.

    Each connection is synced independently so that one failing connection does
    not prevent the others from refreshing. Per-connection sync sessions are still
    recorded by ``EnableBankingService`` for diagnosability.
    """

    def __init__(self, *, db: Session, enable_banking_service: EnableBankingService) -> None:
        self.db = db
        self.enable_banking_service = enable_banking_service

    def sync_all_active_connections(self) -> SyncRunResult:
        connections = self.db.scalars(
            select(EnableBankingConnection)
            .where(EnableBankingConnection.active.is_(True))
            .order_by(EnableBankingConnection.created_at)
        ).all()

        run = SyncRunResult(total_connections=len(connections))
        for connection in connections:
            run.results.append(self._sync_one(connection))
        run.succeeded = sum(1 for result in run.results if result.status == "success")
        run.skipped = sum(1 for result in run.results if result.status == "skipped")
        run.failed = sum(1 for result in run.results if result.status == "failed")
        return run

    def _sync_one(self, connection: EnableBankingConnection) -> ConnectionSyncResult:
        connection_id = str(connection.id)
        try:
            outcome = self.enable_banking_service.sync_connection(connection_id=connection_id)
        except Exception as exc:  # noqa: BLE001 - isolate per-connection failures
            logger.exception("Scheduled sync failed for connection %s", connection_id)
            return ConnectionSyncResult(
                connection_id=connection_id,
                aspsp_name=connection.aspsp_name,
                status="failed",
                error=str(exc),
                needs_reauth=_is_reauth_error(exc),
            )

        status = str(outcome.get("status", "success"))
        if status == "skipped":
            logger.warning("Scheduled sync skipped connection %s: %s", connection_id, outcome.get("message"))
        else:
            logger.info(
                "Scheduled sync succeeded for connection %s: accounts=%s transactions=%s",
                connection_id,
                outcome.get("accounts_synced", 0),
                outcome.get("transactions_imported", 0),
            )
        return ConnectionSyncResult(
            connection_id=connection_id,
            aspsp_name=connection.aspsp_name,
            status=status,
            accounts_synced=int(outcome.get("accounts_synced", 0)),
            transactions_imported=int(outcome.get("transactions_imported", 0)),
            error=outcome.get("message") if status == "skipped" else None,
            # A skipped sync means the session was no longer authorized and the
            # connection was deactivated: only a reconnect brings it back.
            needs_reauth=status == "skipped",
        )


def _is_reauth_error(exc: BaseException) -> bool:
    return isinstance(exc, EnableBankingAPIError) and exc.status_code in _REAUTH_STATUS_CODES

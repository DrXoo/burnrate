from __future__ import annotations

from datetime import UTC, datetime

from sqlalchemy import create_engine, select
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool

from burnrate.db.base import Base
from burnrate.db.models import EnableBankingConnection, SyncSession
from burnrate.integrations.enable_banking.client import EnableBankingAPIError
from burnrate.services.sync_service import SyncService


class FakeEnableBankingService:
    """Stands in for EnableBankingService, recording which connections were synced."""

    def __init__(
        self,
        *,
        db: Session,
        failing_connection_ids: set[str] | None = None,
        expired_connection_ids: set[str] | None = None,
        unauthorized_connection_ids: set[str] | None = None,
    ) -> None:
        self.db = db
        self.failing_connection_ids = failing_connection_ids or set()
        self.expired_connection_ids = expired_connection_ids or set()
        self.unauthorized_connection_ids = unauthorized_connection_ids or set()
        self.synced_connection_ids: list[str] = []

    def sync_connection(self, *, connection_id: str) -> dict[str, object]:
        self.synced_connection_ids.append(connection_id)
        connection = self.db.get(EnableBankingConnection, _as_uuid(connection_id))
        sync_session = SyncSession(
            enable_banking_connection_id=connection.id,
            started_at=datetime.now(UTC),
            status="running",
            imported_accounts_count=0,
            imported_transactions_count=0,
        )
        self.db.add(sync_session)
        self.db.flush()

        if connection_id in self.expired_connection_ids:
            connection.active = False
            sync_session.status = "skipped"
            sync_session.error_summary = "expired"
            sync_session.finished_at = datetime.now(UTC)
            return {"accounts_synced": 0, "transactions_imported": 0, "status": "skipped", "message": "expired"}

        if connection_id in self.unauthorized_connection_ids:
            sync_session.status = "failed"
            sync_session.error_summary = "Enable Banking API error (401)"
            sync_session.finished_at = datetime.now(UTC)
            raise EnableBankingAPIError(status_code=401, detail="unauthorized")

        if connection_id in self.failing_connection_ids:
            sync_session.status = "failed"
            sync_session.error_summary = "boom"
            sync_session.finished_at = datetime.now(UTC)
            raise RuntimeError("boom")

        sync_session.status = "success"
        sync_session.imported_accounts_count = 1
        sync_session.imported_transactions_count = 3
        sync_session.finished_at = datetime.now(UTC)
        return {"accounts_synced": 1, "transactions_imported": 3, "status": "success"}


def _as_uuid(value: str):
    from uuid import UUID

    return UUID(value)


def make_session() -> Session:
    engine = create_engine(
        "sqlite+pysqlite:///:memory:",
        future=True,
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(engine)
    return sessionmaker(bind=engine, autoflush=False, autocommit=False)()


def add_connection(db: Session, *, name: str, active: bool = True) -> EnableBankingConnection:
    connection = EnableBankingConnection(
        aspsp_name=name,
        aspsp_country="FI",
        psu_type="personal",
        session_id=f"session-{name}",
        session_status="AUTHORIZED",
        active=active,
    )
    db.add(connection)
    db.flush()
    return connection


def test_sync_all_active_connections_syncs_every_active_connection() -> None:
    db = make_session()
    first = add_connection(db, name="Nordea")
    second = add_connection(db, name="OP")
    enable_banking = FakeEnableBankingService(db=db)
    service = SyncService(db=db, enable_banking_service=enable_banking)

    result = service.sync_all_active_connections()

    assert result.total_connections == 2
    assert result.succeeded == 2
    assert result.failed == 0
    assert set(enable_banking.synced_connection_ids) == {str(first.id), str(second.id)}
    assert all(item.status == "success" for item in result.results)
    assert result.results[0].transactions_imported == 3


def test_sync_all_active_connections_skips_inactive_connections() -> None:
    db = make_session()
    active = add_connection(db, name="Nordea", active=True)
    add_connection(db, name="Disabled", active=False)
    enable_banking = FakeEnableBankingService(db=db)
    service = SyncService(db=db, enable_banking_service=enable_banking)

    result = service.sync_all_active_connections()

    assert result.total_connections == 1
    assert enable_banking.synced_connection_ids == [str(active.id)]


def test_sync_all_active_connections_reports_skipped_expired_session() -> None:
    db = make_session()
    expired = add_connection(db, name="Expired")
    healthy = add_connection(db, name="Healthy")
    enable_banking = FakeEnableBankingService(db=db, expired_connection_ids={str(expired.id)})
    service = SyncService(db=db, enable_banking_service=enable_banking)

    result = service.sync_all_active_connections()

    assert result.total_connections == 2
    assert result.succeeded == 1
    assert result.skipped == 1
    assert result.failed == 0

    skipped_result = next(item for item in result.results if item.connection_id == str(expired.id))
    assert skipped_result.status == "skipped"
    assert skipped_result.error == "expired"
    assert skipped_result.needs_reauth is True
    assert healthy is not None


def test_sync_all_active_connections_isolates_a_failing_connection() -> None:
    db = make_session()
    failing = add_connection(db, name="Broken")
    healthy = add_connection(db, name="Healthy")
    enable_banking = FakeEnableBankingService(db=db, failing_connection_ids={str(failing.id)})
    service = SyncService(db=db, enable_banking_service=enable_banking)

    result = service.sync_all_active_connections()

    # The failure of one connection must not stop the others from syncing.
    assert set(enable_banking.synced_connection_ids) == {str(failing.id), str(healthy.id)}
    assert result.total_connections == 2
    assert result.succeeded == 1
    assert result.failed == 1

    failed_result = next(item for item in result.results if item.connection_id == str(failing.id))
    assert failed_result.status == "failed"
    assert failed_result.error == "boom"
    # A generic failure (network blip, bug) is not a reconnect signal.
    assert failed_result.needs_reauth is False

    # Both sync sessions (failed and successful) should be persisted for diagnosability.
    db.commit()
    sessions = db.scalars(select(SyncSession)).all()
    statuses = sorted(session.status for session in sessions)
    assert statuses == ["failed", "success"]


def test_sync_flags_reauth_when_bank_rejects_with_401() -> None:
    db = make_session()
    unauthorized = add_connection(db, name="ING")
    enable_banking = FakeEnableBankingService(db=db, unauthorized_connection_ids={str(unauthorized.id)})
    service = SyncService(db=db, enable_banking_service=enable_banking)

    result = service.sync_all_active_connections()

    assert result.failed == 1
    failed_result = result.results[0]
    assert failed_result.status == "failed"
    # A 401 from the bank means the consent is gone — surface it as a reconnect signal.
    assert failed_result.needs_reauth is True

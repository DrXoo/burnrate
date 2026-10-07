from __future__ import annotations

import logging
from datetime import date, datetime, timedelta, timezone
from decimal import Decimal

import pytest
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric import rsa
from sqlalchemy import create_engine, select
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool

from burnrate.api.schemas.enable_banking import StartAuthorizationRequest
from burnrate.config import Settings
from burnrate.db.base import Base
from burnrate.db.models import (
    Account,
    Category,
    EnableBankingAccountMapping,
    EnableBankingAuthRequest,
    EnableBankingConnection,
    SyncSession,
    Transaction,
)
from burnrate.integrations.enable_banking.client import EnableBankingAPIError
from burnrate.services.categorization_service import CategorizationService
from burnrate.services.enable_banking_service import EnableBankingService
from burnrate.services.rules_service import RulesService


class FakeEnableBankingClient:
    def __init__(self) -> None:
        self.transaction_ids = ["tx-1"]
        self.transaction_requests: list[dict[str, object]] = []

    def list_aspsps(self, *, country: str):
        return [{"name": "Nordea", "country": country}]

    def start_authorization(self, **_: object):
        return {"url": "https://auth.example.test/redirect", "authorization_id": "auth-1"}

    def create_session(self, *, code: str):
        assert code == "auth-code"
        return {
            "session_id": "session-123",
            "accounts": [
                {
                    "uid": "account-uid-1",
                    "name": "Main account",
                    "details": "Daily banking",
                    "currency": "EUR",
                    "identification_hash": "hash-1",
                }
            ],
            "aspsp": {"name": "Nordea", "country": "FI"},
            "psu_type": "personal",
            "access": {"valid_until": "2026-01-11T12:00:00+00:00"},
        }

    def get_session(self, *, session_id: str):
        assert session_id == "session-123"
        return {
            "status": "AUTHORIZED",
            "authorized": "2026-01-01T12:00:00+00:00",
            "accounts": ["account-uid-1"],
            "accounts_data": [{"uid": "account-uid-1", "identification_hash": "hash-1"}],
        }

    def get_account_balances(self, *, account_id: str):
        assert account_id == "account-uid-1"
        return {
            "balances": [
                {
                    "balance_type": "CLAV",
                    "balance_amount": {"amount": "123.45", "currency": "EUR"},
                }
            ]
        }

    def get_account_transactions(
        self,
        *,
        account_id: str,
        date_from=None,
        date_to=None,
        transaction_status: str | None = None,
        continuation_key: str | None = None,
    ):
        assert account_id == "account-uid-1"
        assert continuation_key is None
        self.transaction_requests.append(
            {
                "account_id": account_id,
                "date_from": date_from,
                "date_to": date_to,
                "transaction_status": transaction_status,
                "continuation_key": continuation_key,
            }
        )
        if transaction_status is not None:
            # This bank exposes no pending transactions over open banking.
            return {"transactions": {"booked": [], "pending": []}}
        return {
            "transactions": {
                "booked": [
                    {
                        "transaction_id": transaction_id,
                        "transaction_amount": {"amount": "15.99", "currency": "EUR"},
                        "credit_debit_indicator": "DBIT",
                        "status": "BOOK",
                        "booking_date": "2026-01-02",
                        "value_date": "2026-01-02",
                        "remittance_information": ["Coffee shop"],
                        "creditor": {"name": "Cafe"},
                        "debtor": {"name": "Owner"},
                    }
                    for transaction_id in self.transaction_ids
                ],
                "pending": [],
            }
        }


class EmptyTransactionsClient(FakeEnableBankingClient):
    def get_account_transactions(
        self,
        *,
        account_id: str,
        date_from=None,
        date_to=None,
        transaction_status: str | None = None,
        continuation_key: str | None = None,
    ):
        assert account_id == "account-uid-1"
        assert continuation_key is None
        self.transaction_requests.append(
            {
                "account_id": account_id,
                "date_from": date_from,
                "date_to": date_to,
                "transaction_status": transaction_status,
                "continuation_key": continuation_key,
            }
        )
        return {"transactions": [], "continuation_key": None}


class NullPartyTransactionsClient(FakeEnableBankingClient):
    def get_account_transactions(
        self,
        *,
        account_id: str,
        date_from=None,
        date_to=None,
        transaction_status: str | None = None,
        continuation_key: str | None = None,
    ):
        assert account_id == "account-uid-1"
        assert continuation_key is None
        self.transaction_requests.append(
            {
                "account_id": account_id,
                "date_from": date_from,
                "date_to": date_to,
                "transaction_status": transaction_status,
                "continuation_key": continuation_key,
            }
        )
        if transaction_status is not None:
            return {"transactions": [], "continuation_key": None}
        return {
            "transactions": [
                {
                    "transaction_id": "tx-null-party",
                    "transaction_amount": {"amount": "42.00", "currency": "EUR"},
                    "credit_debit_indicator": "DBIT",
                    "status": "BOOK",
                    "booking_date": "2026-01-03",
                    "value_date": "2026-01-03",
                    "remittance_information": ["Provider returned null parties"],
                    "creditor": None,
                    "debtor": None,
                }
            ],
            "continuation_key": None,
        }


class ExpiringSessionClient(FakeEnableBankingClient):
    """Session is AUTHORIZED during the initial callback, then EXPIRED on resync."""

    def __init__(self) -> None:
        super().__init__()
        self.session_status = "AUTHORIZED"

    def get_session(self, *, session_id: str):
        assert session_id == "session-123"
        return {
            "status": self.session_status,
            "authorized": "2026-01-01T12:00:00+00:00",
            "accounts": ["account-uid-1"],
            "accounts_data": [{"uid": "account-uid-1", "identification_hash": "hash-1"}],
        }


class RotatingUidClient(FakeEnableBankingClient):
    """A reconnect issues a fresh per-session uid for the same real account.

    The identification hash stays stable across authorizations, which is how the
    same account must be recognized so it isn't duplicated on reconnect.
    """

    def __init__(self) -> None:
        super().__init__()
        self._session_count = 0
        self.uid = "account-uid-1"

    def create_session(self, *, code: str):
        assert code == "auth-code"
        self._session_count += 1
        self.uid = f"account-uid-{self._session_count}"
        return {
            "session_id": "session-123",
            "accounts": [
                {
                    "uid": self.uid,
                    "name": "Main account",
                    "details": "Daily banking",
                    "currency": "EUR",
                    "identification_hash": "hash-1",
                }
            ],
            "aspsp": {"name": "Nordea", "country": "FI"},
            "psu_type": "personal",
            "access": {"valid_until": "2026-01-11T12:00:00+00:00"},
        }

    def get_session(self, *, session_id: str):
        return {
            "status": "AUTHORIZED",
            "authorized": "2026-01-01T12:00:00+00:00",
            "accounts": [self.uid],
            "accounts_data": [{"uid": self.uid, "identification_hash": "hash-1"}],
        }

    def get_account_balances(self, *, account_id: str):
        assert account_id == self.uid
        return {
            "balances": [
                {"balance_type": "CLAV", "balance_amount": {"amount": "123.45", "currency": "EUR"}}
            ]
        }

    def get_account_transactions(
        self,
        *,
        account_id: str,
        date_from=None,
        date_to=None,
        transaction_status: str | None = None,
        continuation_key: str | None = None,
    ):
        assert account_id == self.uid
        return {"transactions": {"booked": [], "pending": []}}


def make_settings() -> Settings:
    private_key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    private_key_pem = private_key.private_bytes(
        encoding=serialization.Encoding.PEM,
        format=serialization.PrivateFormat.TraditionalOpenSSL,
        encryption_algorithm=serialization.NoEncryption(),
    ).decode("utf-8")
    return Settings(
        ENABLE_BANKING_APP_ID="app-123",
        ENABLE_BANKING_PRIVATE_KEY=private_key_pem,
        ENABLE_BANKING_REDIRECT_URL="http://localhost:8000/api/v1/integrations/enable-banking/callback",
        ENABLE_BANKING_ENVIRONMENT="production",
        ENABLE_BANKING_API_BASE_URL="https://api.enablebanking.com",
        ENABLE_BANKING_TIMEOUT_SECONDS=5,
        DATABASE_URL="sqlite+pysqlite:///:memory:",
    )


def make_session() -> Session:
    engine = create_engine(
        "sqlite+pysqlite:///:memory:",
        future=True,
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(engine)
    return sessionmaker(bind=engine, autoflush=False, autocommit=False)()


def test_enable_banking_service_starts_authorization_and_persists_state() -> None:
    db = make_session()
    service = EnableBankingService(db=db, settings=make_settings(), client=FakeEnableBankingClient())

    response = service.start_authorization(
        StartAuthorizationRequest(
            aspsp_name="Nordea",
            aspsp_country="FI",
            psu_type="personal",
            access_valid_for_days=10,
        )
    )
    db.commit()

    stored = db.scalar(select(EnableBankingAuthRequest).where(EnableBankingAuthRequest.state == response["state"]))
    assert stored is not None
    assert stored.aspsp_name == "Nordea"
    assert response["url"] == "https://auth.example.test/redirect"


def test_enable_banking_service_clamps_valid_until_to_bank_maximum() -> None:
    class MaxValidityClient(FakeEnableBankingClient):
        def list_aspsps(self, *, country: str):
            # 30-day maximum consent validity, expressed in seconds like the real API.
            return [{"name": "Nordea", "country": country, "maximum_consent_validity": 30 * 24 * 3600}]

    db = make_session()
    service = EnableBankingService(db=db, settings=make_settings(), client=MaxValidityClient())

    response = service.start_authorization(
        StartAuthorizationRequest(
            aspsp_name="Nordea",
            aspsp_country="FI",
            psu_type="personal",
            access_valid_for_days=180,
        )
    )

    valid_until = datetime.fromisoformat(response["valid_until"])
    window = valid_until - datetime.now(timezone.utc)
    # Clamped to the 30-day bank maximum (minus a small safety margin), not the requested 180.
    assert timedelta(days=29) < window <= timedelta(days=30)


def test_enable_banking_service_handles_callback_and_imports_initial_data() -> None:
    db = make_session()
    client = FakeEnableBankingClient()
    service = EnableBankingService(db=db, settings=make_settings(), client=client)
    start = service.start_authorization(
        StartAuthorizationRequest(
            aspsp_name="Nordea",
            aspsp_country="FI",
            psu_type="personal",
            access_valid_for_days=10,
        )
    )
    db.commit()

    callback = service.handle_callback(code="auth-code", state=start["state"], error=None, error_description=None)
    db.commit()

    # session_id is encrypted at rest, so it can't be filtered on; the ORM
    # decrypts it on read.
    connection = db.scalar(select(EnableBankingConnection))
    assert connection is not None
    assert connection.session_id == "session-123"
    account = db.scalar(select(Account).where(Account.display_name == "Main account"))
    assert account is not None
    assert account.latest_balance_amount == Decimal("123.45")
    mapping = db.scalar(select(EnableBankingAccountMapping).where(EnableBankingAccountMapping.account_id == account.id))
    assert mapping is not None
    transaction = db.scalar(select(Transaction).where(Transaction.enable_banking_transaction_id == "tx-1"))
    assert transaction is not None
    assert transaction.amount == Decimal("-15.99")
    assert transaction.status == "booked"
    sync_session = db.scalar(select(SyncSession).where(SyncSession.enable_banking_connection_id == connection.id))
    assert sync_session is not None
    assert sync_session.imported_transactions_count == 1
    assert callback["accounts_imported"] == 1
    assert callback["transactions_imported"] == 1
    today = datetime.now(timezone.utc).date()
    booked_requests = [r for r in client.transaction_requests if r["transaction_status"] is None]
    pending_requests = [r for r in client.transaction_requests if r["transaction_status"] == "PDNG"]
    # Pending transactions are fetched separately over a trailing 30-day window,
    # which is also the window the sweep judges.
    assert pending_requests[0]["date_from"] == today - timedelta(days=30)
    assert pending_requests[0]["date_to"] == today
    # The booked call covers at least that window. A constraint, not two numbers kept
    # in step by hand: the sweep deletes a hold the pending response omits, and only
    # the booked call can bring the settled copy of it back.
    assert booked_requests[0]["date_from"] <= pending_requests[0]["date_from"]
    assert booked_requests[0]["date_to"] >= pending_requests[0]["date_to"]


def test_reconnect_supersedes_previous_connection_for_same_bank() -> None:
    db = make_session()
    service = EnableBankingService(db=db, settings=make_settings(), client=FakeEnableBankingClient())

    def connect() -> None:
        start = service.start_authorization(
            StartAuthorizationRequest(
                aspsp_name="Nordea",
                aspsp_country="FI",
                psu_type="personal",
                access_valid_for_days=10,
            )
        )
        db.commit()
        service.handle_callback(code="auth-code", state=start["state"], error=None, error_description=None)
        db.commit()

    connect()
    connect()  # a reconnect of the same bank

    connections = db.scalars(
        select(EnableBankingConnection).order_by(EnableBankingConnection.created_at.asc())
    ).all()
    assert len(connections) == 2
    assert connections[0].active is False  # the earlier one retired
    assert connections[1].active is True  # the reconnect is live
    # Exactly one active connection remains for the bank.
    assert sum(1 for c in connections if c.active) == 1


def test_list_connections_hides_superseded_reconnects() -> None:
    db = make_session()
    service = EnableBankingService(db=db, settings=make_settings(), client=FakeEnableBankingClient())

    def connect() -> None:
        start = service.start_authorization(
            StartAuthorizationRequest(
                aspsp_name="Nordea",
                aspsp_country="FI",
                psu_type="personal",
                access_valid_for_days=10,
            )
        )
        db.commit()
        service.handle_callback(code="auth-code", state=start["state"], error=None, error_description=None)
        db.commit()

    connect()
    connect()
    connect()  # two reconnects of the same bank link

    # The retired rows are kept for their sync history...
    assert len(db.scalars(select(EnableBankingConnection)).all()) == 3

    # ...but only the live one is surfaced, so reconnecting never looks like a
    # duplicated bank.
    connections = service.list_connections()
    assert len(connections) == 1
    live = db.scalar(select(EnableBankingConnection).where(EnableBankingConnection.active.is_(True)))
    assert live is not None
    assert connections[0]["connection_id"] == str(live.id)


def test_list_connections_keeps_distinct_bank_links() -> None:
    db = make_session()
    service = EnableBankingService(db=db, settings=make_settings(), client=FakeEnableBankingClient())

    def connect(*, aspsp_name: str, psu_type: str) -> None:
        start = service.start_authorization(
            StartAuthorizationRequest(
                aspsp_name=aspsp_name,
                aspsp_country="FI",
                psu_type=psu_type,
                access_valid_for_days=10,
            )
        )
        db.commit()
        service.handle_callback(code="auth-code", state=start["state"], error=None, error_description=None)
        db.commit()

    connect(aspsp_name="Nordea", psu_type="personal")
    connect(aspsp_name="Nordea", psu_type="business")  # same bank, separate link
    connect(aspsp_name="OP", psu_type="personal")  # different bank

    # None of these supersede each other, so all three stay visible.
    assert len(service.list_connections()) == 3


def test_list_connections_shows_lapsed_connection_with_no_replacement() -> None:
    db = make_session()
    client = ExpiringSessionClient()
    service = EnableBankingService(db=db, settings=make_settings(), client=client)
    start = service.start_authorization(
        StartAuthorizationRequest(
            aspsp_name="Nordea",
            aspsp_country="FI",
            psu_type="personal",
            access_valid_for_days=10,
        )
    )
    db.commit()
    callback = service.handle_callback(code="auth-code", state=start["state"], error=None, error_description=None)
    db.commit()

    # The bank session has since lapsed, which deactivates the connection.
    client.session_status = "EXPIRED"
    service.sync_connection(connection_id=callback["connection_id"])
    db.commit()

    # A lapsed connection that was never replaced is still the current row for its
    # link, so it must stay visible for the owner to reconnect it.
    connections = service.list_connections()
    assert len(connections) == 1
    assert connections[0]["active"] is False


def test_reconnect_reuses_account_when_uid_changes_but_hash_matches() -> None:
    db = make_session()
    service = EnableBankingService(db=db, settings=make_settings(), client=RotatingUidClient())

    def connect() -> None:
        start = service.start_authorization(
            StartAuthorizationRequest(
                aspsp_name="Nordea",
                aspsp_country="FI",
                psu_type="personal",
                access_valid_for_days=10,
            )
        )
        db.commit()
        service.handle_callback(code="auth-code", state=start["state"], error=None, error_description=None)
        db.commit()

    connect()
    connect()  # reconnect: same real account, new per-session uid, same identification hash

    # The account must not be duplicated — the stable hash re-identifies it.
    accounts = db.scalars(select(Account)).all()
    assert len(accounts) == 1

    # Its single mapping is moved onto the live connection and the new uid so later
    # syncs of the reconnected connection resolve to this same account.
    mappings = db.scalars(select(EnableBankingAccountMapping)).all()
    assert len(mappings) == 1
    active = db.scalar(select(EnableBankingConnection).where(EnableBankingConnection.active.is_(True)))
    assert active is not None
    assert mappings[0].enable_banking_connection_id == active.id
    assert mappings[0].external_account_id == "account-uid-2"
    assert mappings[0].account_id == accounts[0].id


def test_enable_banking_service_logs_empty_transaction_pages(caplog) -> None:
    db = make_session()
    service = EnableBankingService(db=db, settings=make_settings(), client=EmptyTransactionsClient())
    start = service.start_authorization(
        StartAuthorizationRequest(
            aspsp_name="Nordea",
            aspsp_country="FI",
            psu_type="personal",
            access_valid_for_days=10,
        )
    )
    db.commit()

    with caplog.at_level(logging.WARNING):
        callback = service.handle_callback(code="auth-code", state=start["state"], error=None, error_description=None)
    db.commit()

    assert callback["transactions_imported"] == 0
    assert "Fetched Enable Banking transactions for account account-uid-1 status=BOOK page=1 window=" in caplog.text
    assert "'transactions_count': 0" in caplog.text


def test_enable_banking_service_manual_sync_reuses_existing_connection() -> None:
    db = make_session()
    client = FakeEnableBankingClient()
    service = EnableBankingService(db=db, settings=make_settings(), client=client)
    start = service.start_authorization(
        StartAuthorizationRequest(
            aspsp_name="Nordea",
            aspsp_country="FI",
            psu_type="personal",
            access_valid_for_days=10,
        )
    )
    db.commit()

    initial_callback = service.handle_callback(
        code="auth-code",
        state=start["state"],
        error=None,
        error_description=None,
    )
    db.commit()

    # tx-1 was already imported on the initial callback; re-syncing it plus a new
    # tx-2 must count only the genuinely-new transaction (tx-2), not the re-fetched one.
    client.transaction_ids = ["tx-1", "tx-2"]
    sync_result = service.sync_connection(connection_id=initial_callback["connection_id"])
    db.commit()

    transactions = db.scalars(select(Transaction).order_by(Transaction.enable_banking_transaction_id)).all()
    sync_sessions = db.scalars(select(SyncSession).order_by(SyncSession.started_at)).all()

    assert sync_result["accounts_synced"] == 1
    assert sync_result["transactions_imported"] == 1
    assert len(transactions) == 2
    assert transactions[0].enable_banking_transaction_id == "tx-1"
    assert transactions[1].enable_banking_transaction_id == "tx-2"
    assert len(sync_sessions) == 2
    assert sync_sessions[-1].imported_transactions_count == 1
    today = datetime.now(timezone.utc).date()
    booked_requests = [r for r in client.transaction_requests if r["transaction_status"] is None]
    pending_requests = [r for r in client.transaction_requests if r["transaction_status"] == "PDNG"]
    # The most recent resync fetched both statuses over the trailing window, with the
    # booked call still covering everything the sweep is allowed to delete.
    assert pending_requests[-1]["date_from"] == today - timedelta(days=30)
    assert pending_requests[-1]["date_to"] == today
    assert booked_requests[-1]["date_from"] <= pending_requests[-1]["date_from"]
    assert booked_requests[-1]["date_to"] >= pending_requests[-1]["date_to"]


def test_resync_of_unchanged_month_counts_zero_new_transactions() -> None:
    # Booked transactions are re-fetched for the whole current month every sync, so a
    # resync that returns the same transactions must report 0 new (not re-announce them).
    db = make_session()
    client = FakeEnableBankingClient()
    service = EnableBankingService(db=db, settings=make_settings(), client=client)
    start = service.start_authorization(
        StartAuthorizationRequest(
            aspsp_name="Nordea",
            aspsp_country="FI",
            psu_type="personal",
            access_valid_for_days=10,
        )
    )
    db.commit()
    initial = service.handle_callback(code="auth-code", state=start["state"], error=None, error_description=None)
    db.commit()
    assert initial["transactions_imported"] == 1

    resync = service.sync_connection(connection_id=initial["connection_id"])
    db.commit()

    assert resync["transactions_imported"] == 0
    assert len(db.scalars(select(Transaction)).all()) == 1


def test_enable_banking_service_handles_null_creditor_and_debtor() -> None:
    db = make_session()
    service = EnableBankingService(db=db, settings=make_settings(), client=NullPartyTransactionsClient())
    start = service.start_authorization(
        StartAuthorizationRequest(
            aspsp_name="Nordea",
            aspsp_country="FI",
            psu_type="personal",
            access_valid_for_days=10,
        )
    )
    db.commit()

    callback = service.handle_callback(
        code="auth-code",
        state=start["state"],
        error=None,
        error_description=None,
    )
    db.commit()

    transaction = db.scalar(
        select(Transaction).where(Transaction.enable_banking_transaction_id == "tx-null-party")
    )

    assert callback["transactions_imported"] == 1
    assert transaction is not None
    assert transaction.merchant_name is None
    assert transaction.counterparty_name is None


def test_enable_banking_service_lists_connections_with_latest_sync_summary() -> None:
    db = make_session()
    client = FakeEnableBankingClient()
    service = EnableBankingService(db=db, settings=make_settings(), client=client)
    start = service.start_authorization(
        StartAuthorizationRequest(
            aspsp_name="Nordea",
            aspsp_country="FI",
            psu_type="personal",
            access_valid_for_days=10,
        )
    )
    db.commit()

    callback = service.handle_callback(
        code="auth-code",
        state=start["state"],
        error=None,
        error_description=None,
    )
    db.commit()

    connections = service.list_connections()

    assert len(connections) == 1
    assert connections[0]["connection_id"] == callback["connection_id"]
    assert connections[0]["aspsp_name"] == "Nordea"
    assert connections[0]["linked_account_count"] == 1
    assert connections[0]["latest_sync_status"] == "success"
    assert connections[0]["latest_sync_accounts_count"] == 1
    assert connections[0]["latest_sync_transactions_count"] == 1


def test_enable_banking_service_skips_and_deactivates_expired_session() -> None:
    db = make_session()
    client = ExpiringSessionClient()
    service = EnableBankingService(db=db, settings=make_settings(), client=client)
    start = service.start_authorization(
        StartAuthorizationRequest(
            aspsp_name="Nordea",
            aspsp_country="FI",
            psu_type="personal",
            access_valid_for_days=10,
        )
    )
    db.commit()

    callback = service.handle_callback(code="auth-code", state=start["state"], error=None, error_description=None)
    db.commit()
    requests_after_initial_import = len(client.transaction_requests)

    # The bank session has since expired.
    client.session_status = "EXPIRED"
    result = service.sync_connection(connection_id=callback["connection_id"])
    db.commit()

    assert result["status"] == "skipped"
    assert result["session_status"] == "EXPIRED"
    assert result["transactions_imported"] == 0
    assert "expired" in result["message"].lower()

    # session_id is encrypted at rest, so it can't be filtered on; the ORM
    # decrypts it on read.
    connection = db.scalar(select(EnableBankingConnection))
    assert connection is not None
    assert connection.session_id == "session-123"
    assert connection.active is False
    assert connection.session_status == "EXPIRED"

    skipped_session = db.scalar(select(SyncSession).where(SyncSession.status == "skipped"))
    assert skipped_session is not None
    assert "re-authorized" in (skipped_session.error_summary or "")
    # No transaction fetch should have been attempted for the expired session.
    assert len(client.transaction_requests) == requests_after_initial_import


def test_enable_banking_service_applies_existing_rules_during_import() -> None:
    db = make_session()
    client = FakeEnableBankingClient()
    category = Category(name="Coffee", type="expense", active=True)
    db.add(category)
    db.commit()

    rules_service = RulesService(db=db)
    service = EnableBankingService(db=db, settings=make_settings(), client=client)
    start = service.start_authorization(
        StartAuthorizationRequest(
            aspsp_name="Nordea",
            aspsp_country="FI",
            psu_type="personal",
            access_valid_for_days=10,
        )
    )
    db.commit()

    callback = service.handle_callback(
        code="auth-code",
        state=start["state"],
        error=None,
        error_description=None,
    )
    db.commit()
    first_transaction = db.scalar(select(Transaction).where(Transaction.enable_banking_transaction_id == "tx-1"))
    assert first_transaction is not None
    first_transaction.category_id = category.id
    db.commit()

    rules_service.create_rule_from_transaction(transaction_id=str(first_transaction.id))
    db.commit()

    client.transaction_ids = ["tx-1", "tx-2"]
    service.sync_connection(connection_id=callback["connection_id"])
    db.commit()

    second_transaction = db.scalar(select(Transaction).where(Transaction.enable_banking_transaction_id == "tx-2"))

    assert second_transaction is not None
    assert second_transaction.category_id == category.id
    assert second_transaction.matched_rule_id is not None


def test_a_re_imported_transaction_the_owner_ignored_is_not_given_a_category_again() -> None:
    """Ignored outlives a sync, so the rule engine must leave the row alone.

    The rows most likely to be Ignored are the rows most likely to match a rule: a
    rule is how a recurring charge gets its category, and a reimbursed or mis-posted
    instance of one is exactly what the owner excludes. Handing the category back
    returns the money to the figures while the row still reads as excluded, so
    nothing on screen says it happened.
    """
    db = make_session()
    client = FakeEnableBankingClient()
    category = Category(name="Coffee", type="expense", active=True)
    db.add(category)
    db.commit()

    service = EnableBankingService(db=db, settings=make_settings(), client=client)
    connection_id = link_bank(service=service, db=db)
    charge = db.scalar(select(Transaction).where(Transaction.enable_banking_transaction_id == "tx-1"))
    assert charge is not None

    # The owner categorizes the charge, makes a rule of it, then decides this
    # particular instance should not count -- it was refunded in cash.
    charge.category_id = category.id
    db.commit()
    RulesService(db=db).create_rule_from_transaction(transaction_id=str(charge.id))
    db.commit()
    CategorizationService(db=db).exclude_transaction(transaction_id=str(charge.id))
    db.commit()

    service.sync_connection(connection_id=connection_id)
    db.commit()

    ignored = db.scalar(select(Transaction).where(Transaction.enable_banking_transaction_id == "tx-1"))
    assert ignored is not None
    assert ignored.excluded_at is not None
    assert ignored.category_id is None
    assert ignored.matched_rule_id is None


def owner_today() -> date:
    """The owner's calendar day, which ``make_settings`` leaves at UTC."""
    return datetime.now(timezone.utc).date()


def make_pending_payload(
    *,
    transaction_id: str | None = None,
    amount: str = "40.00",
    value_date: date | None = None,
    remittance: str = "Dinner hold",
) -> dict[str, object]:
    """A pending card authorization as a bank reports one: no booking date yet.

    Omitting ``transaction_id`` is the second payload shape the sweep has to
    handle -- the bank supplies no stable identifier, so the import falls back to
    hashing the content.
    """
    payload: dict[str, object] = {
        "transaction_amount": {"amount": amount, "currency": "EUR"},
        "credit_debit_indicator": "DBIT",
        "status": "PDNG",
        "value_date": (value_date or owner_today() - timedelta(days=1)).isoformat(),
        "remittance_information": [remittance],
        "creditor": {"name": "Restaurant"},
        "debtor": {"name": "Owner"},
    }
    if transaction_id is not None:
        payload["transaction_id"] = transaction_id
    return payload


class PendingTransactionsClient(FakeEnableBankingClient):
    """A bank that exposes pending transactions, each response under the test's control.

    Dates are relative to today because the pending fetch window is a trailing
    30 days from the owner's calendar day.
    """

    def __init__(self) -> None:
        super().__init__()
        self.booked_payloads: list[dict[str, object]] = []
        self.pending_payloads: list[dict[str, object]] = [make_pending_payload(transaction_id="hold-1")]

    def get_account_transactions(
        self,
        *,
        account_id: str,
        date_from=None,
        date_to=None,
        transaction_status: str | None = None,
        continuation_key: str | None = None,
    ):
        assert account_id == "account-uid-1"
        self.transaction_requests.append(
            {
                "account_id": account_id,
                "date_from": date_from,
                "date_to": date_to,
                "transaction_status": transaction_status,
                "continuation_key": continuation_key,
            }
        )
        if transaction_status == "PDNG":
            return {"transactions": {"booked": [], "pending": list(self.pending_payloads)}}
        return {"transactions": {"booked": list(self.booked_payloads), "pending": []}}


def link_bank(*, service: EnableBankingService, db: Session) -> str:
    """Complete the authorization handshake and return the new connection id."""
    start = service.start_authorization(
        StartAuthorizationRequest(
            aspsp_name="Nordea",
            aspsp_country="FI",
            psu_type="personal",
            access_valid_for_days=10,
        )
    )
    db.commit()
    callback = service.handle_callback(code="auth-code", state=start["state"], error=None, error_description=None)
    db.commit()
    return callback["connection_id"]


def test_sync_deletes_a_pending_hold_the_bank_stopped_reporting() -> None:
    db = make_session()
    client = PendingTransactionsClient()
    service = EnableBankingService(db=db, settings=make_settings(), client=client)
    connection_id = link_bank(service=service, db=db)
    assert db.scalar(select(Transaction).where(Transaction.enable_banking_transaction_id == "hold-1")) is not None

    # The hold was cancelled at the bank, so it is absent from the next pending response.
    client.pending_payloads = []
    service.sync_connection(connection_id=connection_id)
    db.commit()

    assert db.scalar(select(Transaction).where(Transaction.enable_banking_transaction_id == "hold-1")) is None


def test_sync_keeps_a_pending_hold_the_bank_still_reports() -> None:
    db = make_session()
    client = PendingTransactionsClient()
    service = EnableBankingService(db=db, settings=make_settings(), client=client)
    connection_id = link_bank(service=service, db=db)

    # The client keeps reporting hold-1: the restaurant has not released it yet.
    service.sync_connection(connection_id=connection_id)
    db.commit()

    holds = db.scalars(select(Transaction).where(Transaction.status == "pending")).all()
    assert len(holds) == 1
    assert holds[0].enable_banking_transaction_id == "hold-1"
    assert holds[0].amount == Decimal("-40.00")


def settle(pending_payload: dict[str, object], *, booking_date: date | None = None) -> dict[str, object]:
    """The same purchase once the bank books it: a booking date arrives, the status changes.

    For a bank that supplies no stable identifier this is what makes the row a
    twin -- the content hash standing in for the identifier covers the booking
    date, so the booked copy of one purchase hashes differently from its hold.

    ``booking_date`` defaults to today because most settlements land the day they
    are seen; a bank that books a charge under the date it was authorized is what
    makes the fetch window, not just the sweep window, load-bearing.
    """
    booked = dict(pending_payload)
    booked["status"] = "BOOK"
    booked["booking_date"] = (booking_date or owner_today()).isoformat()
    return booked


def test_a_pending_hold_that_books_under_a_new_identifier_leaves_no_twin() -> None:
    db = make_session()
    client = PendingTransactionsClient()
    # This bank supplies no transaction_id, so the import falls back to the content hash.
    hold = make_pending_payload()
    client.pending_payloads = [hold]
    service = EnableBankingService(db=db, settings=make_settings(), client=client)
    connection_id = link_bank(service=service, db=db)
    assert len(db.scalars(select(Transaction)).all()) == 1

    # The dinner settles: it appears in the booked response and leaves the pending one.
    client.pending_payloads = []
    client.booked_payloads = [settle(hold)]
    service.sync_connection(connection_id=connection_id)
    db.commit()

    transactions = db.scalars(select(Transaction)).all()
    assert len(transactions) == 1
    assert transactions[0].status == "booked"
    assert transactions[0].amount == Decimal("-40.00")


class FailingSecondPendingPageClient(PendingTransactionsClient):
    """The pending fetch returns one page and then fails, so the response is truncated."""

    def __init__(self) -> None:
        super().__init__()
        self.first_page_payloads: list[dict[str, object]] = []

    def get_account_transactions(
        self,
        *,
        account_id: str,
        date_from=None,
        date_to=None,
        transaction_status: str | None = None,
        continuation_key: str | None = None,
    ):
        if transaction_status != "PDNG":
            return super().get_account_transactions(
                account_id=account_id,
                date_from=date_from,
                date_to=date_to,
                transaction_status=transaction_status,
                continuation_key=continuation_key,
            )
        if continuation_key is None:
            return {
                "transactions": {"booked": [], "pending": list(self.first_page_payloads)},
                "continuation_key": "pending-page-2",
            }
        raise EnableBankingAPIError(status_code=502, detail="pending page unavailable")


def test_a_pending_fetch_that_fails_mid_pagination_sweeps_nothing() -> None:
    db = make_session()
    client = PendingTransactionsClient()
    hold_one = make_pending_payload(transaction_id="hold-1")
    hold_two = make_pending_payload(transaction_id="hold-2", amount="12.50", remittance="Lunch hold")
    client.pending_payloads = [hold_one, hold_two]
    service = EnableBankingService(db=db, settings=make_settings(), client=client)
    connection_id = link_bank(service=service, db=db)
    assert len(db.scalars(select(Transaction).where(Transaction.status == "pending")).all()) == 2

    # Only hold-1 arrives before the fetch dies; hold-2 was on the page that never came,
    # so a sweep reading the truncated response would delete a hold that is still live.
    failing_client = FailingSecondPendingPageClient()
    failing_client.first_page_payloads = [hold_one]
    failing_service = EnableBankingService(db=db, settings=make_settings(), client=failing_client)
    with pytest.raises(EnableBankingAPIError):
        failing_service.sync_connection(connection_id=connection_id)
    # The scheduled run isolates a per-connection failure and commits the session anyway.
    db.commit()

    holds = db.scalars(select(Transaction).where(Transaction.status == "pending")).all()
    assert {hold.enable_banking_transaction_id for hold in holds} == {"hold-1", "hold-2"}


def test_the_sweep_leaves_a_pending_hold_the_owner_ignored() -> None:
    db = make_session()
    client = PendingTransactionsClient()
    service = EnableBankingService(db=db, settings=make_settings(), client=client)
    connection_id = link_bank(service=service, db=db)
    hold = db.scalar(select(Transaction).where(Transaction.enable_banking_transaction_id == "hold-1"))
    assert hold is not None
    hold.excluded_at = datetime.now(timezone.utc)
    db.commit()

    # The bank stops reporting it, but Ignored is a decision the owner made: deleting
    # the row would hand the transaction back to the unknown queue on the next import.
    client.pending_payloads = []
    service.sync_connection(connection_id=connection_id)
    db.commit()

    ignored = db.scalar(select(Transaction).where(Transaction.enable_banking_transaction_id == "hold-1"))
    assert ignored is not None
    assert ignored.excluded_at is not None


def test_a_hold_with_no_identifier_survives_resync_on_its_content_hash() -> None:
    db = make_session()
    client = PendingTransactionsClient()
    # No transaction_id: the sweep has to recognise the row by the same fallback hash
    # the import stored it under, or a still-live hold churns on every sync.
    client.pending_payloads = [make_pending_payload()]
    service = EnableBankingService(db=db, settings=make_settings(), client=client)
    connection_id = link_bank(service=service, db=db)
    holds = db.scalars(select(Transaction).where(Transaction.status == "pending")).all()
    assert len(holds) == 1
    original_row_id = holds[0].id

    service.sync_connection(connection_id=connection_id)
    db.commit()

    holds = db.scalars(select(Transaction).where(Transaction.status == "pending")).all()
    assert len(holds) == 1
    assert holds[0].id == original_row_id


def test_the_sweep_leaves_a_pending_hold_older_than_the_fetched_window() -> None:
    db = make_session()
    client = PendingTransactionsClient()
    client.pending_payloads = [
        make_pending_payload(transaction_id="hold-old", value_date=owner_today() - timedelta(days=45))
    ]
    service = EnableBankingService(db=db, settings=make_settings(), client=client)
    connection_id = link_bank(service=service, db=db)

    # The pending fetch covers a trailing 30 days, so the bank was never asked about
    # this hold: its absence from the response is not evidence that it is gone.
    client.pending_payloads = []
    service.sync_connection(connection_id=connection_id)
    db.commit()

    assert db.scalar(select(Transaction).where(Transaction.enable_banking_transaction_id == "hold-old")) is not None


class StandingOrderClient(FakeEnableBankingClient):
    """A bank that reports a scheduled payment in the default call, not the PDNG one.

    ``_extract_transactions`` merges a response's ``pending`` array whichever call
    produced it, and ``SCHD`` normalizes to pending, so a row with pending status can
    enter from the booked fetch. The sweep has to recognise it as reported.
    """

    def __init__(self) -> None:
        super().__init__()
        self.scheduled_payloads: list[dict[str, object]] = [
            {
                "transaction_id": "schd-1",
                "transaction_amount": {"amount": "60.00", "currency": "EUR"},
                "credit_debit_indicator": "DBIT",
                "status": "SCHD",
                "booking_date": owner_today().isoformat(),
                "value_date": owner_today().isoformat(),
                "remittance_information": ["Gym standing order"],
            }
        ]

    def get_account_transactions(
        self,
        *,
        account_id: str,
        date_from=None,
        date_to=None,
        transaction_status: str | None = None,
        continuation_key: str | None = None,
    ):
        assert account_id == "account-uid-1"
        if transaction_status == "PDNG":
            return {"transactions": {"booked": [], "pending": []}}
        return {"transactions": {"booked": [], "pending": list(self.scheduled_payloads)}}


def test_the_sweep_leaves_a_scheduled_payment_the_booked_fetch_reported() -> None:
    db = make_session()
    service = EnableBankingService(db=db, settings=make_settings(), client=StandingOrderClient())
    connection_id = link_bank(service=service, db=db)
    scheduled = db.scalar(select(Transaction).where(Transaction.enable_banking_transaction_id == "schd-1"))
    assert scheduled is not None
    assert scheduled.status == "pending"
    original_row_id = scheduled.id

    # The bank keeps reporting it, just not through the pending call. Sweeping on the
    # pending response alone deletes it, and the next sync re-imports it -- so the row
    # oscillates, re-announcing itself and losing its category on every other sync.
    for _ in range(2):
        assert service.sync_connection(connection_id=connection_id)["transactions_imported"] == 0
        db.commit()

    scheduled = db.scalar(select(Transaction).where(Transaction.enable_banking_transaction_id == "schd-1"))
    assert scheduled is not None
    assert scheduled.id == original_row_id


class UnreadablePayloadClient(PendingTransactionsClient):
    """A bank that answers 200 with a body the extractor does not recognise.

    From the sweep's side this is indistinguishable from an account the bank reports
    as empty, and both arrive without raising: ``_extract_transactions`` falls back
    through two known payload shapes and logs a warning when neither matches, and a
    200 error envelope looks exactly the same. Restricted production returning empty
    results for a linked account is a documented product state, not an error.
    """

    def __init__(self) -> None:
        super().__init__()
        self.unreadable = False

    def get_account_transactions(self, **kwargs):
        if self.unreadable:
            self.transaction_requests.append(kwargs)
            return {"message": "no transactions available"}
        return super().get_account_transactions(**kwargs)


def test_a_sync_that_reports_no_transactions_at_all_sweeps_nothing() -> None:
    # The sweep deletes a pending row the bank did not mention. A response that
    # mentions nothing at all is not evidence about any particular row, and acting
    # on it deletes every live hold in the window -- committed spend the owner's
    # figures depend on, gone in one sync that recorded itself a success.
    db = make_session()
    client = UnreadablePayloadClient()
    service = EnableBankingService(db=db, settings=make_settings(), client=client)
    connection_id = link_bank(service=service, db=db)
    hold = db.scalar(select(Transaction).where(Transaction.enable_banking_transaction_id == "hold-1"))
    assert hold is not None

    client.unreadable = True
    service.sync_connection(connection_id=connection_id)
    db.commit()

    survivor = db.scalar(select(Transaction).where(Transaction.enable_banking_transaction_id == "hold-1"))
    assert survivor is not None
    assert survivor.amount == Decimal("-40.00")


class TopLevelArraysClient(PendingTransactionsClient):
    """A bank that returns the arrays at the top level, with no ``transactions`` wrapper.

    ``_extract_transactions`` has carried this shape as its last fallback since the
    first import landed, so the legibility gate has to recognise it as well. Read as
    illegible, a bank like this one would never have a sweep run at all and its
    phantom holds would accumulate for ever -- the failure the gate itself introduces
    if it is written against one payload shape.
    """

    def get_account_transactions(self, **kwargs):
        if kwargs.get("transaction_status") == "PDNG":
            return {"booked": [], "pending": list(self.pending_payloads)}
        return {"booked": list(self.booked_payloads), "pending": []}


def test_a_sync_whose_arrays_arrive_at_the_top_level_still_sweeps() -> None:
    db = make_session()
    client = TopLevelArraysClient()
    service = EnableBankingService(db=db, settings=make_settings(), client=client)
    connection_id = link_bank(service=service, db=db)
    assert db.scalar(select(Transaction).where(Transaction.enable_banking_transaction_id == "hold-1")) is not None

    # The hold is released, and a settled purchase arrives in the booked response.
    client.pending_payloads = []
    client.booked_payloads = [settle(make_pending_payload(transaction_id="other-1"))]
    service.sync_connection(connection_id=connection_id)
    db.commit()

    assert db.scalar(select(Transaction).where(Transaction.enable_banking_transaction_id == "hold-1")) is None
    assert db.scalar(select(Transaction).where(Transaction.enable_banking_transaction_id == "other-1")) is not None


class UnrecognisedTransactionsShapeClient(PendingTransactionsClient):
    """A bank that wraps its rows in a ``transactions`` object the extractor cannot read.

    The two shapes `_extract_transactions` knows put the rows in ``booked`` and
    ``pending`` arrays, either inside ``transactions`` or at the top level. A third
    bank nesting them under some other key is reporting its holds perfectly clearly
    -- just not in a dialect this code speaks. Every row falls on the floor, which is
    indistinguishable from an empty window unless the shape itself is checked.
    """

    def __init__(self) -> None:
        super().__init__()
        self.unrecognised = False

    def get_account_transactions(self, **kwargs):
        if self.unrecognised:
            self.transaction_requests.append(kwargs)
            return {"transactions": {"entries": [make_pending_payload(transaction_id="hold-1")]}}
        return super().get_account_transactions(**kwargs)


def test_a_sync_whose_transactions_arrive_in_an_unrecognised_shape_sweeps_nothing() -> None:
    # The sharpest form of the gate's job: this bank is still reporting the hold, in a
    # shape the extractor cannot read. Treating that as a legible empty window deletes
    # the row against the bank's own evidence that it is live -- and the loss is not
    # self-healing, because every later sync reads the same unreadable shape.
    db = make_session()
    client = UnrecognisedTransactionsShapeClient()
    service = EnableBankingService(db=db, settings=make_settings(), client=client)
    connection_id = link_bank(service=service, db=db)
    assert db.scalar(select(Transaction).where(Transaction.enable_banking_transaction_id == "hold-1")) is not None

    client.unrecognised = True
    service.sync_connection(connection_id=connection_id)
    db.commit()

    survivor = db.scalar(select(Transaction).where(Transaction.enable_banking_transaction_id == "hold-1"))
    assert survivor is not None
    assert survivor.amount == Decimal("-40.00")


class FlatTransactionsListClient(PendingTransactionsClient):
    """A bank that returns one flat ``transactions`` list, each row carrying its status.

    The third shape ``_extract_transactions`` knows, and the one the rest of this
    module's fakes never produce in a sweep. Read as illegible it would be the
    mirror of the top-level-arrays case: the gate would never let a sweep run for
    this bank, and its phantom holds would accumulate for ever.
    """

    def get_account_transactions(self, **kwargs):
        rows = (
            list(self.pending_payloads)
            if kwargs.get("transaction_status") == "PDNG"
            else list(self.booked_payloads)
        )
        self.transaction_requests.append(kwargs)
        return {"transactions": rows, "continuation_key": None}


def test_a_sync_whose_transactions_arrive_as_one_flat_list_still_sweeps() -> None:
    db = make_session()
    client = FlatTransactionsListClient()
    service = EnableBankingService(db=db, settings=make_settings(), client=client)
    connection_id = link_bank(service=service, db=db)
    assert db.scalar(select(Transaction).where(Transaction.enable_banking_transaction_id == "hold-1")) is not None

    # The hold is released, and a settled purchase arrives in the booked response.
    client.pending_payloads = []
    client.booked_payloads = [settle(make_pending_payload(transaction_id="other-1"))]
    service.sync_connection(connection_id=connection_id)
    db.commit()

    assert db.scalar(select(Transaction).where(Transaction.enable_banking_transaction_id == "hold-1")) is None
    assert db.scalar(select(Transaction).where(Transaction.enable_banking_transaction_id == "other-1")) is not None


class WindowedTransactionsClient(PendingTransactionsClient):
    """A bank that answers only for the window it was asked about.

    Every other fake here returns its payloads whatever dates the service
    requested, so a fetch window too narrow to re-ask for a charge was invisible
    through them: the service could forget to ask and still be handed the answer.
    A real bank answers the window and nothing else.
    """

    def get_account_transactions(
        self,
        *,
        account_id: str,
        date_from=None,
        date_to=None,
        transaction_status: str | None = None,
        continuation_key: str | None = None,
    ):
        payload = super().get_account_transactions(
            account_id=account_id,
            date_from=date_from,
            date_to=date_to,
            transaction_status=transaction_status,
            continuation_key=continuation_key,
        )
        node = payload["transactions"]
        return {
            "transactions": {
                array: [row for row in node[array] if self._reported_in(row, date_from, date_to)]
                for array in ("booked", "pending")
            }
        }

    @staticmethod
    def _reported_in(row: dict[str, object], date_from: date, date_to: date) -> bool:
        reported = row.get("booking_date") or row.get("value_date")
        return date_from <= date.fromisoformat(str(reported)) <= date_to


def test_a_hold_that_books_after_a_month_boundary_is_re_imported_rather_than_lost() -> None:
    db = make_session()
    client = WindowedTransactionsClient()
    hold = make_pending_payload(transaction_id="hold-jan-31", value_date=date(2026, 1, 31))
    client.pending_payloads = [hold]
    january = EnableBankingService(
        db=db,
        settings=make_settings(),
        client=client,
        clock=lambda: datetime(2026, 1, 31, 18, 0, tzinfo=timezone.utc),
    )
    connection_id = link_bank(service=january, db=db)
    assert db.scalar(select(Transaction).where(Transaction.enable_banking_transaction_id == "hold-jan-31")) is not None

    # Overnight the 40.00 card charge settles, and the bank books it under the date
    # it was authorized. On the 1st the hold is absent from the pending response and
    # the booked copy sits in January: a sync that re-asks only for February's booked
    # transactions sweeps the hold and never learns the charge settled, so 40.00 of
    # January's spend ends up in neither status and January is understated for good.
    client.pending_payloads = []
    client.booked_payloads = [settle(hold, booking_date=date(2026, 1, 31))]
    february = EnableBankingService(
        db=db,
        settings=make_settings(),
        client=client,
        clock=lambda: datetime(2026, 2, 1, 9, 0, tzinfo=timezone.utc),
    )
    february.sync_connection(connection_id=connection_id)
    db.commit()

    charges = db.scalars(select(Transaction)).all()
    assert len(charges) == 1
    assert charges[0].status == "booked"
    assert charges[0].amount == Decimal("-40.00")
    assert charges[0].booking_date == date(2026, 1, 31)


def test_the_sweep_deletes_a_cancelled_standing_order_dated_in_the_future() -> None:
    db = make_session()
    client = PendingTransactionsClient()
    # A standing order the bank reports today for a date two weeks out. ``SCHD``
    # normalizes to pending, and its Effective Date resolves to the day it is due,
    # which ``within_month`` counts as this month's spend.
    client.pending_payloads = [
        make_pending_payload(
            transaction_id="schd-due-later",
            amount="60.00",
            value_date=owner_today() + timedelta(days=15),
            remittance="Gym standing order",
        )
        | {"status": "SCHD"}
    ]
    service = EnableBankingService(db=db, settings=make_settings(), client=client)
    connection_id = link_bank(service=service, db=db)
    scheduled = db.scalar(select(Transaction).where(Transaction.enable_banking_transaction_id == "schd-due-later"))
    assert scheduled is not None
    assert scheduled.status == "pending"

    # The owner cancels it at the bank, so it leaves the response. A sweep that stops
    # at today can never reach a row dated after today, and the 60.00 would count as
    # this month's spend for ever. The lower bound is the one that earns its place --
    # it keeps the sweep from judging days the bank was never asked about -- while a
    # row dated past today is inside the fetch's subject matter whatever date it carries.
    client.pending_payloads = []
    service.sync_connection(connection_id=connection_id)
    db.commit()

    assert db.scalar(select(Transaction).where(Transaction.enable_banking_transaction_id == "schd-due-later")) is None


def unmarked(payload: dict[str, object]) -> dict[str, object]:
    """The same row from a bank that marks status by array, not per transaction."""
    return {key: value for key, value in payload.items() if key != "status"}


def test_the_array_a_row_arrives_in_decides_its_status_when_the_row_does_not() -> None:
    db = make_session()
    client = PendingTransactionsClient()
    client.pending_payloads = [unmarked(make_pending_payload(transaction_id="hold-unmarked"))]
    client.booked_payloads = [
        unmarked(settle(make_pending_payload(transaction_id="charge-unmarked", amount="12.00")))
    ]
    service = EnableBankingService(db=db, settings=make_settings(), client=client)
    link_bank(service=service, db=db)

    # Storing the hold as booked is the failure ADR-0003 exists to prevent: it
    # under-reports pending spend, lets a 1.00 pre-authorization project a 900.00 rent
    # as 1.00, and hides the row from the sweep, which filters on pending status.
    hold = db.scalar(select(Transaction).where(Transaction.enable_banking_transaction_id == "hold-unmarked"))
    assert hold is not None
    assert hold.status == "pending"
    # The booked array keeps its meaning too: an unmarked row there has settled.
    charge = db.scalar(select(Transaction).where(Transaction.enable_banking_transaction_id == "charge-unmarked"))
    assert charge is not None
    assert charge.status == "booked"


def test_a_flat_response_to_the_pending_call_stores_its_rows_as_pending() -> None:
    db = make_session()
    client = FlatTransactionsListClient()
    # A bank that uses the flat shape *and* marks status by response rather than per
    # row: there is no array to imply a status, but the call itself asked for PDNG.
    client.pending_payloads = [unmarked(make_pending_payload(transaction_id="hold-flat"))]
    service = EnableBankingService(db=db, settings=make_settings(), client=client)
    link_bank(service=service, db=db)

    # The request is the bank's own context for the answer, and it is strictly better
    # evidence than "assume settled": storing this as booked under-reports pending
    # spend, feeds the fixed step projection a partial authorization, and leaves the
    # row invisible to the sweep for ever.
    hold = db.scalar(select(Transaction).where(Transaction.enable_banking_transaction_id == "hold-flat"))
    assert hold is not None
    assert hold.status == "pending"


def test_a_provider_status_in_lower_case_is_still_recognised() -> None:
    db = make_session()
    client = PendingTransactionsClient()
    # The sharp case: the bank spells the code in lower case *and* puts the row in the
    # booked array, so an unrecognised status falls back to settled and the hold reads
    # as money already gone. A cancellation code would land the same way.
    client.booked_payloads = [make_pending_payload(transaction_id="hold-lowercase") | {"status": "pdng"}]
    client.pending_payloads = []
    service = EnableBankingService(db=db, settings=make_settings(), client=client)
    link_bank(service=service, db=db)

    hold = db.scalar(select(Transaction).where(Transaction.enable_banking_transaction_id == "hold-lowercase"))
    assert hold is not None
    assert hold.status == "pending"


def test_a_charge_the_bank_dated_not_at_all_is_filed_on_the_day_the_sync_ran() -> None:
    db = make_session()
    client = PendingTransactionsClient()
    # No booking date and no value date: the Effective Date chain falls through to the
    # day the row was imported, which is the only thing that decides which month this
    # charge counts in.
    client.pending_payloads = [
        {
            "transaction_id": "hold-undated",
            "transaction_amount": {"amount": "18.00", "currency": "EUR"},
            "credit_debit_indicator": "DBIT",
            "status": "PDNG",
            "remittance_information": ["Undated hold"],
        }
    ]
    service = EnableBankingService(
        db=db,
        settings=make_settings(),
        client=client,
        clock=lambda: datetime(2026, 1, 31, 18, 0, tzinfo=timezone.utc),
    )
    link_bank(service=service, db=db)

    # Stamped from the same clock the fetch window came from. Reading the host's wall
    # clock instead would file the charge in whatever month the process happens to run
    # in, which for a row with no dates of its own is the whole of its month membership.
    hold = db.scalar(select(Transaction).where(Transaction.enable_banking_transaction_id == "hold-undated"))
    assert hold is not None
    assert hold.imported_at.date() == date(2026, 1, 31)

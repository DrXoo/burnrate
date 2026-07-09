from __future__ import annotations

import logging
from datetime import datetime, timedelta, timezone
from decimal import Decimal

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

    connection = db.scalar(select(EnableBankingConnection).where(EnableBankingConnection.session_id == "session-123"))
    assert connection is not None
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
    # Booked transactions are fetched for the current month.
    assert booked_requests[0]["date_from"] == today.replace(day=1)
    assert booked_requests[0]["date_to"] == today
    # Pending transactions are fetched separately over a trailing 30-day window.
    assert pending_requests[0]["date_from"] == today - timedelta(days=30)
    assert pending_requests[0]["date_to"] == today


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
    # The most recent resync fetched booked for the current month and pending over a trailing window.
    assert booked_requests[-1]["date_from"] == today.replace(day=1)
    assert booked_requests[-1]["date_to"] == today
    assert pending_requests[-1]["date_from"] == today - timedelta(days=30)
    assert pending_requests[-1]["date_to"] == today


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

    connection = db.scalar(
        select(EnableBankingConnection).where(EnableBankingConnection.session_id == "session-123")
    )
    assert connection is not None
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

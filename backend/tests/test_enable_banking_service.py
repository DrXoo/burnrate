from __future__ import annotations

import logging
from datetime import datetime, timezone
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
    EnableBankingAccountMapping,
    EnableBankingAuthRequest,
    EnableBankingConnection,
    SyncSession,
    Transaction,
)
from burnrate.services.enable_banking_service import EnableBankingService


class FakeEnableBankingClient:
    def __init__(self) -> None:
        self.transaction_ids = ["tx-1"]

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

    def get_account_transactions(self, *, account_id: str, continuation_key: str | None = None):
        assert account_id == "account-uid-1"
        assert continuation_key is None
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
    def get_account_transactions(self, *, account_id: str, continuation_key: str | None = None):
        assert account_id == "account-uid-1"
        assert continuation_key is None
        return {"transactions": [], "continuation_key": None}


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
    service = EnableBankingService(db=db, settings=make_settings(), client=FakeEnableBankingClient())
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
    assert "Fetched Enable Banking transactions for account account-uid-1 page=1 imported=0" in caplog.text
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

    client.transaction_ids = ["tx-1", "tx-2"]
    sync_result = service.sync_connection(connection_id=initial_callback["connection_id"])
    db.commit()

    transactions = db.scalars(select(Transaction).order_by(Transaction.enable_banking_transaction_id)).all()
    sync_sessions = db.scalars(select(SyncSession).order_by(SyncSession.started_at)).all()

    assert sync_result["accounts_synced"] == 1
    assert sync_result["transactions_imported"] == 2
    assert len(transactions) == 2
    assert transactions[0].enable_banking_transaction_id == "tx-1"
    assert transactions[1].enable_banking_transaction_id == "tx-2"
    assert len(sync_sessions) == 2
    assert sync_sessions[-1].imported_transactions_count == 2


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

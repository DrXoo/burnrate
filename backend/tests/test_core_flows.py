"""End-to-end integration tests wiring the real services together.

These cover the core product loop across service boundaries, beyond the
per-service and per-route unit tests: import bank data, categorize it, budget
for it, and read a summary that reflects it -- then re-sync and confirm the
result is idempotent. Time is pinned via SummaryService(today=...) and a fixed
transaction window so the assertions do not depend on the run date.
"""

from __future__ import annotations

from datetime import date
from decimal import Decimal

from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric import rsa
from sqlalchemy import create_engine, select
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool

from burnrate.api.schemas.enable_banking import StartAuthorizationRequest
from burnrate.config import Settings
from burnrate.db.base import Base
from burnrate.db.models import EnableBankingConnection, Transaction
from burnrate.services.budget_service import BudgetService
from burnrate.services.categorization_service import CategorizationService
from burnrate.services.enable_banking_service import EnableBankingService
from burnrate.services.rules_service import RulesService
from burnrate.services.summary_service import SummaryService

REFERENCE_DAY = date(2026, 1, 15)
MONTH = "2026-01"


def _booked_transaction(*, txid: str, amount: str, booking_date: str, merchant: str) -> dict:
    return {
        "transaction_id": txid,
        "transaction_amount": {"amount": amount, "currency": "EUR"},
        "credit_debit_indicator": "DBIT",
        "status": "BOOK",
        "booking_date": booking_date,
        "value_date": booking_date,
        "remittance_information": [f"{merchant} purchase"],
        "creditor": {"name": merchant},
        "debtor": {"name": "Owner"},
    }


class FakeBankClient:
    """Minimal Enable Banking client returning one account and a mutable ledger."""

    def __init__(self) -> None:
        self.booked = [
            _booked_transaction(txid="tx-1", amount="15.99", booking_date="2026-01-02", merchant="Mercadona")
        ]

    def list_aspsps(self, *, country: str):
        return [{"name": "Nordea", "country": country}]

    def start_authorization(self, **_: object):
        return {"url": "https://auth.example.test/redirect", "authorization_id": "auth-1"}

    def create_session(self, *, code: str):
        assert code == "auth-code"
        return {
            "session_id": "session-123",
            "accounts": [
                {"uid": "acc-1", "name": "Main account", "currency": "EUR", "identification_hash": "hash-1"}
            ],
        }

    def get_session(self, *, session_id: str):
        assert session_id == "session-123"
        return {"status": "AUTHORIZED", "authorized": "2026-01-01T00:00:00+00:00", "accounts": ["acc-1"]}

    def get_account_balances(self, *, account_id: str):
        assert account_id == "acc-1"
        return {
            "balances": [
                {"balance_type": "CLAV", "balance_amount": {"amount": "1000.00", "currency": "EUR"}}
            ]
        }

    def get_account_transactions(
        self, *, account_id: str, date_from=None, date_to=None, transaction_status=None, continuation_key=None
    ):
        assert account_id == "acc-1"
        assert continuation_key is None
        if transaction_status is not None:
            return {"transactions": {"booked": [], "pending": []}}
        return {"transactions": {"booked": list(self.booked), "pending": []}}


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
        ENABLE_BANKING_REDIRECT_URL="http://localhost:8000/callback",
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


def link_and_import(db: Session, service: EnableBankingService) -> str:
    start = service.start_authorization(
        StartAuthorizationRequest(
            aspsp_name="Nordea", aspsp_country="FI", psu_type="personal", access_valid_for_days=10
        )
    )
    db.commit()
    service.handle_callback(code="auth-code", state=start["state"], error=None, error_description=None)
    db.commit()
    connection = db.scalar(select(EnableBankingConnection))
    assert connection is not None
    return str(connection.id)


def test_core_flow_import_categorize_budget_summary_and_idempotent_resync() -> None:
    db = make_session()
    client = FakeBankClient()
    bank = EnableBankingService(db=db, settings=make_settings(), client=client)

    connection_id = link_and_import(db, bank)

    # After import the transaction is present but uncategorized, so it does not
    # yet count as spending.
    summary = SummaryService(db=db).get_summary(month=MONTH, today=REFERENCE_DAY)
    assert summary["current_balance_amount"] == "1000.00"
    assert summary["current_balance_currency"] == "EUR"
    assert summary["uncategorized_count"] == 1
    assert summary["monthly_spending_amount"] == "0.00"

    # Categorize the imported transaction as an expense.
    categorization = CategorizationService(db=db)
    food = categorization.create_category(name="Food", category_type="expense")
    db.commit()
    transaction = db.scalar(select(Transaction).where(Transaction.enable_banking_transaction_id == "tx-1"))
    assert transaction is not None
    categorization.categorize_transaction(transaction_id=str(transaction.id), category_id=food["category_id"])
    db.commit()

    # Budget for that category.
    BudgetService(db=db).create_budget(
        category_id=food["category_id"], amount=Decimal("300.00"), currency="EUR", active_from=date(2026, 1, 1)
    )
    db.commit()

    # The summary now reflects the categorized spend against the budget.
    summary = SummaryService(db=db).get_summary(month=MONTH, today=REFERENCE_DAY)
    assert summary["uncategorized_count"] == 0
    assert summary["monthly_spending_amount"] == "15.99"
    assert summary["monthly_budget_amount"] == "300.00"
    assert summary["budgeted_spending_amount"] == "15.99"
    assert summary["money_left_amount"] == "284.01"
    assert len(summary["budget_usage"]) == 1
    usage = summary["budget_usage"][0]
    assert usage["category_name"] == "Food"
    assert usage["spent_amount"] == "15.99"
    assert usage["remaining_amount"] == "284.01"

    # Re-syncing the same connection must not duplicate the transaction, and it
    # must preserve the manual categorization.
    bank.sync_connection(connection_id=connection_id)
    db.commit()

    transactions = db.scalars(select(Transaction)).all()
    assert len(transactions) == 1
    assert transactions[0].category_id is not None

    summary = SummaryService(db=db).get_summary(month=MONTH, today=REFERENCE_DAY)
    assert summary["monthly_spending_amount"] == "15.99"
    assert summary["uncategorized_count"] == 0


def test_core_flow_rule_auto_categorizes_matching_transaction_on_resync() -> None:
    db = make_session()
    client = FakeBankClient()
    bank = EnableBankingService(db=db, settings=make_settings(), client=client)

    connection_id = link_and_import(db, bank)

    # Manually categorize the first Mercadona transaction and turn it into a rule.
    categorization = CategorizationService(db=db)
    food = categorization.create_category(name="Food", category_type="expense")
    db.commit()
    first = db.scalar(select(Transaction).where(Transaction.enable_banking_transaction_id == "tx-1"))
    assert first is not None
    categorization.categorize_transaction(transaction_id=str(first.id), category_id=food["category_id"])
    db.commit()
    RulesService(db=db).create_rule_from_transaction(transaction_id=str(first.id))
    db.commit()

    # A new Mercadona transaction arrives on the next sync.
    client.booked.append(
        _booked_transaction(txid="tx-2", amount="20.01", booking_date="2026-01-05", merchant="Mercadona")
    )
    bank.sync_connection(connection_id=connection_id)
    db.commit()

    # It should be auto-categorized by the rule, with no manual step.
    second = db.scalar(select(Transaction).where(Transaction.enable_banking_transaction_id == "tx-2"))
    assert second is not None
    assert second.category_id == first.category_id
    assert second.matched_rule_id is not None

    summary = SummaryService(db=db).get_summary(month=MONTH, today=REFERENCE_DAY)
    assert summary["uncategorized_count"] == 0
    assert summary["monthly_spending_amount"] == "36.00"


def test_delete_rule_returns_matched_transactions_to_the_unknown_queue() -> None:
    db = make_session()
    client = FakeBankClient()
    bank = EnableBankingService(db=db, settings=make_settings(), client=client)

    connection_id = link_and_import(db, bank)

    categorization = CategorizationService(db=db)
    food = categorization.create_category(name="Food", category_type="expense")
    db.commit()
    first = db.scalar(select(Transaction).where(Transaction.enable_banking_transaction_id == "tx-1"))
    assert first is not None
    categorization.categorize_transaction(transaction_id=str(first.id), category_id=food["category_id"])
    db.commit()
    rules = RulesService(db=db)
    created = rules.create_rule_from_transaction(transaction_id=str(first.id))
    db.commit()

    # A new Mercadona transaction is auto-categorized by the rule on the next sync.
    client.booked.append(
        _booked_transaction(txid="tx-2", amount="20.01", booking_date="2026-01-05", merchant="Mercadona")
    )
    bank.sync_connection(connection_id=connection_id)
    db.commit()
    second = db.scalar(select(Transaction).where(Transaction.enable_banking_transaction_id == "tx-2"))
    assert second is not None
    assert second.matched_rule_id is not None

    # Deleting the rule de-assigns both rule-matched transactions; with no other
    # rule to catch them, they return to the unknown queue.
    result = rules.delete_rule(rule_id=created["rule_id"])
    db.commit()

    assert result["transactions_touched"] == 2
    assert result["transactions_rematched"] == 0
    assert result["transactions_returned_to_queue"] == 2
    assert rules.list_rules() == []

    for txn in (first, second):
        db.refresh(txn)
        assert txn.category_id is None
        assert txn.matched_rule_id is None

    summary = SummaryService(db=db).get_summary(month=MONTH, today=REFERENCE_DAY)
    assert summary["uncategorized_count"] == 2


def test_delete_rule_rematches_transactions_to_another_active_rule() -> None:
    db = make_session()
    client = FakeBankClient()
    bank = EnableBankingService(db=db, settings=make_settings(), client=client)

    connection_id = link_and_import(db, bank)

    categorization = CategorizationService(db=db)
    food = categorization.create_category(name="Food", category_type="expense")
    snacks = categorization.create_category(name="Snacks", category_type="expense")
    db.commit()
    first = db.scalar(select(Transaction).where(Transaction.enable_banking_transaction_id == "tx-1"))
    assert first is not None
    categorization.categorize_transaction(transaction_id=str(first.id), category_id=food["category_id"])
    db.commit()
    rules = RulesService(db=db)
    primary = rules.create_rule_from_transaction(transaction_id=str(first.id))
    # A second, lower-priority rule that also matches "Mercadona".
    fallback = rules.create_rule_from_transaction(
        transaction_id=str(first.id),
        match_field="merchant_name",
        match_operator="contains",
        match_value="Mercadona",
        category_id=snacks["category_id"],
    )
    db.commit()

    client.booked.append(
        _booked_transaction(txid="tx-2", amount="20.01", booking_date="2026-01-05", merchant="Mercadona")
    )
    bank.sync_connection(connection_id=connection_id)
    db.commit()
    second = db.scalar(select(Transaction).where(Transaction.enable_banking_transaction_id == "tx-2"))
    assert second is not None
    assert str(second.matched_rule_id) == primary["rule_id"]

    # Deleting the primary rule re-runs matching; the fallback rule picks it up.
    result = rules.delete_rule(rule_id=primary["rule_id"])
    db.commit()

    assert result["transactions_rematched"] >= 1
    assert result["transactions_returned_to_queue"] == 0
    assert {rule["rule_id"] for rule in rules.list_rules()} == {fallback["rule_id"]}

    db.refresh(second)
    assert str(second.category_id) == snacks["category_id"]
    assert str(second.matched_rule_id) == fallback["rule_id"]

from __future__ import annotations

from datetime import datetime, timezone
from decimal import Decimal

from sqlalchemy import create_engine, select
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool

from burnrate.db.base import Base
from burnrate.db.models import Account, Category, Transaction
from burnrate.services.categorization_service import CategorizationService


def make_session() -> Session:
    engine = create_engine(
        "sqlite+pysqlite:///:memory:",
        future=True,
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(engine)
    return sessionmaker(bind=engine, autoflush=False, autocommit=False)()


def seed_review_data(db: Session) -> tuple[Transaction, Category]:
    account = Account(
        display_name="Main account",
        currency="EUR",
        included_in_calculations=True,
        latest_balance_amount=Decimal("375.52"),
        latest_balance_currency="EUR",
        last_synced_at=datetime(2026, 6, 30, 8, 0, tzinfo=timezone.utc),
    )
    category = Category(name="Food", type="expense", active=True)
    transaction = Transaction(
        account_id=account.id,
        enable_banking_transaction_id="tx-1",
        booking_date=datetime(2026, 6, 15, tzinfo=timezone.utc).date(),
        value_date=datetime(2026, 6, 15, tzinfo=timezone.utc).date(),
        amount=Decimal("-12.50"),
        currency="EUR",
        description="Coffee shop",
        merchant_name="Cafe",
        counterparty_name=None,
        direction="debit",
        status="booked",
        category_id=None,
        matched_rule_id=None,
        raw_payload={"source": "test"},
        imported_at=datetime(2026, 6, 15, 9, 0, tzinfo=timezone.utc),
    )
    db.add_all([account, category])
    db.flush()
    transaction.account_id = account.id
    db.add(transaction)
    db.commit()
    return transaction, category


def test_categorization_service_lists_and_creates_categories() -> None:
    db = make_session()
    _, category = seed_review_data(db)
    service = CategorizationService(db=db)

    created = service.create_category(name="Transport", category_type="expense")
    categories = service.list_categories()

    assert created["name"] == "Transport"
    assert created["type"] == "expense"
    assert [item["name"] for item in categories] == [category.name, "Transport"]


def test_categorization_service_lists_uncategorized_transactions() -> None:
    db = make_session()
    transaction, _ = seed_review_data(db)
    service = CategorizationService(db=db)

    response = service.list_uncategorized_transactions(month="2026-06", limit=50, offset=0)

    assert response["total_count"] == 1
    assert response["transactions"][0]["transaction_id"] == str(transaction.id)


def test_categorization_service_assigns_category_to_transaction() -> None:
    db = make_session()
    transaction, category = seed_review_data(db)
    service = CategorizationService(db=db)

    response = service.categorize_transaction(
        transaction_id=str(transaction.id),
        category_id=str(category.id),
    )
    db.commit()

    stored = db.scalar(select(Transaction).where(Transaction.id == transaction.id))

    assert response["category_name"] == "Food"
    assert stored is not None
    assert stored.category_id == category.id


def test_categorization_service_can_return_transaction_to_unknown_queue() -> None:
    db = make_session()
    transaction, category = seed_review_data(db)
    service = CategorizationService(db=db)
    service.categorize_transaction(
        transaction_id=str(transaction.id),
        category_id=str(category.id),
    )
    db.commit()

    response = service.uncategorize_transaction(transaction_id=str(transaction.id))
    db.commit()

    stored = db.scalar(select(Transaction).where(Transaction.id == transaction.id))

    assert response["category_id"] is None
    assert response["message"] == "Transaction returned to unknown queue"
    assert stored is not None
    assert stored.category_id is None


def test_categorization_service_excludes_transaction_from_queue() -> None:
    db = make_session()
    transaction, _ = seed_review_data(db)
    service = CategorizationService(db=db)

    response = service.exclude_transaction(transaction_id=str(transaction.id))
    db.commit()

    stored = db.scalar(select(Transaction).where(Transaction.id == transaction.id))
    queue = service.list_uncategorized_transactions(month="2026-06", limit=50, offset=0)

    assert response["message"] == "Transaction excluded from the budget"
    assert stored is not None
    assert stored.excluded_at is not None
    assert stored.category_id is None
    # Excluded rows drop out of the review/unknown queue.
    assert queue["total_count"] == 0


def test_categorization_service_restores_excluded_transaction() -> None:
    db = make_session()
    transaction, _ = seed_review_data(db)
    service = CategorizationService(db=db)
    service.exclude_transaction(transaction_id=str(transaction.id))
    db.commit()

    response = service.restore_transaction(transaction_id=str(transaction.id))
    db.commit()

    stored = db.scalar(select(Transaction).where(Transaction.id == transaction.id))
    queue = service.list_uncategorized_transactions(month="2026-06", limit=50, offset=0)

    assert response["message"] == "Transaction returned to unknown queue"
    assert stored is not None
    assert stored.excluded_at is None
    # Back in the queue, ready to categorize.
    assert queue["total_count"] == 1


def test_categorization_service_uncategorizing_an_ignored_transaction_returns_it_to_the_queue() -> None:
    """The response says the row is back in the queue, so it has to be there.

    Ignored and uncategorized are both "no category", and only ``excluded_at`` tells
    the queue which one it is looking at. Clearing the category alone left the row
    excluded, so the call reported a return to a queue the row never reached.
    """
    db = make_session()
    transaction, _ = seed_review_data(db)
    service = CategorizationService(db=db)
    service.exclude_transaction(transaction_id=str(transaction.id))
    db.commit()

    response = service.uncategorize_transaction(transaction_id=str(transaction.id))
    db.commit()

    stored = db.scalar(select(Transaction).where(Transaction.id == transaction.id))
    queue = service.list_uncategorized_transactions(month="2026-06", limit=50, offset=0)

    assert response["message"] == "Transaction returned to unknown queue"
    assert stored is not None
    assert stored.category_id is None
    assert stored.excluded_at is None
    assert queue["total_count"] == 1


def test_categorization_service_categorizing_clears_exclusion() -> None:
    db = make_session()
    transaction, category = seed_review_data(db)
    service = CategorizationService(db=db)
    service.exclude_transaction(transaction_id=str(transaction.id))
    db.commit()

    service.categorize_transaction(
        transaction_id=str(transaction.id),
        category_id=str(category.id),
    )
    db.commit()

    stored = db.scalar(select(Transaction).where(Transaction.id == transaction.id))

    assert stored is not None
    assert stored.category_id == category.id
    # Assigning a real category is mutually exclusive with being excluded.
    assert stored.excluded_at is None


def test_categorization_service_rejects_duplicate_category_name() -> None:
    db = make_session()
    _, category = seed_review_data(db)
    service = CategorizationService(db=db)

    try:
        service.create_category(name=category.name, category_type="expense")
    except ValueError as exc:
        assert str(exc) == f"Category '{category.name}' already exists"
    else:
        raise AssertionError("Expected duplicate category creation to fail")

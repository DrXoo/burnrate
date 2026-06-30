from __future__ import annotations

from datetime import datetime, timezone
from decimal import Decimal

from sqlalchemy import create_engine, select
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool

from burnrate.db.base import Base
from burnrate.db.models import Account, Category, CategorizationRule, Transaction
from burnrate.services.rules_service import RulesService


def make_session() -> Session:
    engine = create_engine(
        "sqlite+pysqlite:///:memory:",
        future=True,
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(engine)
    return sessionmaker(bind=engine, autoflush=False, autocommit=False)()


def seed_rule_data(db: Session) -> tuple[Transaction, Category]:
    account = Account(
        display_name="Main account",
        currency="EUR",
        included_in_calculations=True,
        included_in_runway=False,
        latest_balance_amount=Decimal("375.52"),
        latest_balance_currency="EUR",
        last_synced_at=datetime(2026, 6, 30, 8, 0, tzinfo=timezone.utc),
    )
    category = Category(name="Food", type="expense", active=True)
    db.add_all([account, category])
    db.flush()

    transaction = Transaction(
        account_id=account.id,
        enable_banking_transaction_id="tx-1",
        booking_date=datetime(2026, 6, 15, tzinfo=timezone.utc).date(),
        value_date=datetime(2026, 6, 15, tzinfo=timezone.utc).date(),
        amount=Decimal("-12.50"),
        currency="EUR",
        description="Mercadona purchase",
        merchant_name="Mercadona",
        counterparty_name=None,
        direction="debit",
        status="booked",
        category_id=category.id,
        matched_rule_id=None,
        raw_payload={"source": "test"},
        imported_at=datetime(2026, 6, 15, 9, 0, tzinfo=timezone.utc),
    )
    uncategorized = Transaction(
        account_id=account.id,
        enable_banking_transaction_id="tx-2",
        booking_date=datetime(2026, 6, 16, tzinfo=timezone.utc).date(),
        value_date=datetime(2026, 6, 16, tzinfo=timezone.utc).date(),
        amount=Decimal("-18.10"),
        currency="EUR",
        description="Mercadona weekly groceries",
        merchant_name="Mercadona",
        counterparty_name=None,
        direction="debit",
        status="booked",
        category_id=None,
        matched_rule_id=None,
        raw_payload={"source": "test"},
        imported_at=datetime(2026, 6, 16, 9, 0, tzinfo=timezone.utc),
    )
    db.add_all([transaction, uncategorized])
    db.commit()
    return transaction, category


def test_rules_service_creates_rule_from_transaction_and_lists_it() -> None:
    db = make_session()
    transaction, category = seed_rule_data(db)
    service = RulesService(db=db)

    rule = service.create_rule_from_transaction(transaction_id=str(transaction.id))
    db.commit()
    rules = service.list_rules()
    stored_transaction = db.scalar(select(Transaction).where(Transaction.id == transaction.id))

    assert rule["category_name"] == category.name
    assert rule["match_field"] == "merchant_name"
    assert rule["match_operator"] == "contains"
    assert rule["match_value"] == "Mercadona"
    assert len(rules) == 1
    assert stored_transaction is not None
    assert stored_transaction.matched_rule_id is not None


def test_rules_service_sets_rule_status() -> None:
    db = make_session()
    transaction, _ = seed_rule_data(db)
    service = RulesService(db=db)
    rule = service.create_rule_from_transaction(transaction_id=str(transaction.id))

    updated = service.set_rule_status(rule_id=rule["rule_id"], active=False)

    assert updated["active"] is False


def test_rules_service_applies_rule_to_existing_uncategorized_transactions() -> None:
    db = make_session()
    transaction, category = seed_rule_data(db)
    service = RulesService(db=db)
    rule = service.create_rule_from_transaction(
        transaction_id=str(transaction.id),
        apply_to_existing_uncategorized=True,
    )
    db.commit()

    target = db.scalar(select(Transaction).where(Transaction.enable_banking_transaction_id == "tx-2"))
    stored_rule = db.scalar(select(CategorizationRule).where(CategorizationRule.match_value == "Mercadona"))

    assert target is not None
    assert stored_rule is not None
    assert target.category_id == category.id
    assert target.matched_rule_id == stored_rule.id


def test_rules_service_updates_rule_and_reapplies_it() -> None:
    db = make_session()
    transaction, category = seed_rule_data(db)
    service = RulesService(db=db)
    created_rule = service.create_rule_from_transaction(transaction_id=str(transaction.id))

    updated_rule = service.update_rule(
        rule_id=created_rule["rule_id"],
        name="Food groceries tail match",
        match_field="description",
        match_operator="ends_with",
        match_value="groceries",
        apply_to_existing_uncategorized=True,
    )
    db.commit()

    target = db.scalar(select(Transaction).where(Transaction.enable_banking_transaction_id == "tx-2"))
    assert target is not None
    stored_rule = db.scalar(select(CategorizationRule).where(CategorizationRule.id == target.matched_rule_id))

    assert updated_rule["name"] == "Food groceries tail match"
    assert updated_rule["match_field"] == "description"
    assert updated_rule["match_operator"] == "ends_with"
    assert updated_rule["match_value"] == "groceries"
    assert stored_rule is not None
    assert target.category_id == category.id
    assert target.matched_rule_id == stored_rule.id


def test_rules_service_create_rule_uses_explicit_category_and_syncs_transaction() -> None:
    db = make_session()
    transaction, _ = seed_rule_data(db)
    travel = Category(name="Travel", type="expense", active=True)
    db.add(travel)
    db.commit()
    service = RulesService(db=db)

    created_rule = service.create_rule_from_transaction(
        transaction_id=str(transaction.id),
        category_id=str(travel.id),
        match_field="description",
        match_operator="contains",
        match_value="purchase",
    )
    db.commit()

    stored_transaction = db.scalar(select(Transaction).where(Transaction.id == transaction.id))

    assert created_rule["category_name"] == "Travel"
    assert stored_transaction is not None
    assert stored_transaction.category_id == travel.id
    assert stored_transaction.matched_rule_id is not None


def test_rules_service_rejects_duplicate_rule_creation() -> None:
    db = make_session()
    transaction, _ = seed_rule_data(db)
    service = RulesService(db=db)
    service.create_rule_from_transaction(transaction_id=str(transaction.id))

    try:
        service.create_rule_from_transaction(transaction_id=str(transaction.id))
    except ValueError as exc:
        assert str(exc) == "An identical categorization rule already exists"
    else:
        raise AssertionError("Expected duplicate rule creation to fail")


def test_rules_service_rejects_duplicate_rule_update() -> None:
    db = make_session()
    transaction, _ = seed_rule_data(db)
    service = RulesService(db=db)
    first_rule = service.create_rule_from_transaction(transaction_id=str(transaction.id))

    transaction_two = db.scalar(select(Transaction).where(Transaction.enable_banking_transaction_id == "tx-2"))
    assert transaction_two is not None
    transaction_two.category_id = transaction.category_id
    second_rule = service.create_rule_from_transaction(
        transaction_id=str(transaction_two.id),
        match_field="description",
        match_operator="contains",
        match_value="groceries",
    )

    try:
        service.update_rule(
            rule_id=second_rule["rule_id"],
            match_field=first_rule["match_field"],
            match_operator=first_rule["match_operator"],
            match_value=first_rule["match_value"],
        )
    except ValueError as exc:
        assert str(exc) == "An identical categorization rule already exists"
    else:
        raise AssertionError("Expected duplicate rule update to fail")

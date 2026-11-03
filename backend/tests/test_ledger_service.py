from __future__ import annotations

from datetime import date, datetime, timezone
from decimal import Decimal

import pytest
from sqlalchemy import create_engine, select
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool

from burnrate.db.base import Base
from burnrate.db.models import (
    Account,
    Budget,
    Category,
    EnableBankingAccountMapping,
    EnableBankingConnection,
    Transaction,
)
from burnrate.services.ledger_service import LedgerService


def make_session() -> Session:
    engine = create_engine(
        "sqlite+pysqlite:///:memory:",
        future=True,
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(engine)
    return sessionmaker(bind=engine, autoflush=False, autocommit=False)()


def seed_ledger_data(db: Session) -> tuple[Account, Account]:
    connection = EnableBankingConnection(
        aspsp_name="ING",
        aspsp_country="ES",
        psu_type="personal",
        session_id="session-1",
        session_status="AUTHORIZED",
        authorized_at=datetime(2026, 6, 29, 8, 0, tzinfo=timezone.utc),
        last_synced_at=datetime(2026, 6, 29, 8, 5, tzinfo=timezone.utc),
        active=True,
    )
    db.add(connection)
    db.flush()

    primary_account = Account(
        display_name="Main account",
        currency="EUR",
        included_in_calculations=True,
        latest_balance_amount=Decimal("375.52"),
        latest_balance_currency="EUR",
        last_synced_at=datetime(2026, 6, 29, 8, 5, tzinfo=timezone.utc),
    )
    secondary_account = Account(
        display_name="Savings",
        currency="EUR",
        included_in_calculations=True,
        latest_balance_amount=Decimal("1000.00"),
        latest_balance_currency="EUR",
        last_synced_at=datetime(2026, 6, 29, 8, 6, tzinfo=timezone.utc),
    )
    db.add_all([primary_account, secondary_account])
    db.flush()

    category = Category(name="Food", type="expense", active=True)
    db.add(category)
    db.flush()

    db.add(
        EnableBankingAccountMapping(
            enable_banking_connection_id=connection.id,
            external_account_id="ext-1",
            external_account_hash="hash-1",
            account_id=primary_account.id,
            last_seen_at=datetime(2026, 6, 29, 8, 5, tzinfo=timezone.utc),
        )
    )

    db.add_all(
        [
            Transaction(
                account_id=primary_account.id,
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
            ),
            Transaction(
                account_id=primary_account.id,
                enable_banking_transaction_id="tx-2",
                booking_date=datetime(2026, 6, 10, tzinfo=timezone.utc).date(),
                value_date=datetime(2026, 6, 10, tzinfo=timezone.utc).date(),
                amount=Decimal("-55.00"),
                currency="EUR",
                description="Groceries",
                merchant_name="Market",
                counterparty_name=None,
                direction="debit",
                status="booked",
                category_id=category.id,
                matched_rule_id=None,
                raw_payload={"source": "test"},
                imported_at=datetime(2026, 6, 10, 9, 0, tzinfo=timezone.utc),
            ),
            Transaction(
                account_id=secondary_account.id,
                enable_banking_transaction_id="tx-3",
                booking_date=datetime(2026, 5, 30, tzinfo=timezone.utc).date(),
                value_date=datetime(2026, 5, 30, tzinfo=timezone.utc).date(),
                amount=Decimal("400.00"),
                currency="EUR",
                description="Transfer",
                merchant_name=None,
                counterparty_name="Employer",
                direction="credit",
                status="pending",
                category_id=None,
                matched_rule_id=None,
                raw_payload={"source": "test"},
                imported_at=datetime(2026, 5, 30, 9, 0, tzinfo=timezone.utc),
            ),
        ]
    )
    db.commit()
    return primary_account, secondary_account


def test_ledger_service_lists_accounts_with_connection_metadata() -> None:
    db = make_session()
    seed_ledger_data(db)
    service = LedgerService(db=db)

    accounts = service.list_accounts()

    assert len(accounts) == 2
    assert accounts[0]["display_name"] == "Main account"
    assert accounts[0]["source_aspsp_name"] == "ING"
    assert accounts[0]["external_account_id"] == "ext-1"
    assert accounts[1]["display_name"] == "Savings"
    assert accounts[1]["source_aspsp_name"] is None


def test_ledger_service_updates_account_calculation_flag() -> None:
    db = make_session()
    primary_account, _ = seed_ledger_data(db)
    service = LedgerService(db=db)

    updated = service.update_account(
        account_id=str(primary_account.id),
        included_in_calculations=False,
    )
    db.commit()

    assert updated["included_in_calculations"] is False


def test_ledger_service_lists_transactions_with_filters_and_pagination() -> None:
    db = make_session()
    primary_account, _ = seed_ledger_data(db)
    service = LedgerService(db=db)

    response = service.list_transactions(
        account_id=str(primary_account.id),
        month="2026-06",
        status="booked",
        categorized=False,
        limit=10,
        offset=0,
    )

    assert response["total_count"] == 1
    assert len(response["transactions"]) == 1
    assert response["transactions"][0]["description"] == "Coffee shop"
    assert response["transactions"][0]["amount"] == "-12.50"
    assert response["transactions"][0]["category_name"] is None
    assert response["transactions"][0]["matched_rule_id"] is None


def test_ledger_service_filters_transactions_by_category() -> None:
    db = make_session()
    seed_ledger_data(db)
    service = LedgerService(db=db)

    category = db.execute(select(Category).where(Category.name == "Food")).scalar_one()

    response = service.list_transactions(category_id=str(category.id))

    assert response["total_count"] == 1
    assert len(response["transactions"]) == 1
    assert response["transactions"][0]["description"] == "Groceries"
    assert response["transactions"][0]["category_name"] == "Food"


def test_ledger_service_rejects_invalid_category_id() -> None:
    db = make_session()
    seed_ledger_data(db)
    service = LedgerService(db=db)

    with pytest.raises(ValueError):
        service.list_transactions(category_id="not-a-uuid")


def test_ledger_service_counts_uncategorized_transactions_for_filters() -> None:
    db = make_session()
    primary_account, _ = seed_ledger_data(db)
    service = LedgerService(db=db)

    count = service.get_uncategorized_transaction_count(
        account_id=str(primary_account.id),
        month="2026-06",
        status="booked",
    )

    assert count == 1


def test_ledger_service_lists_pending_transaction_without_booking_date_by_value_date() -> None:
    db = make_session()
    primary_account, _ = seed_ledger_data(db)
    # Held/pending transactions have no booking_date yet; the month filter must fall
    # back to value_date so they still surface in the current month.
    db.add(
        Transaction(
            account_id=primary_account.id,
            enable_banking_transaction_id="tx-pending",
            booking_date=None,
            value_date=datetime(2026, 6, 20, tzinfo=timezone.utc).date(),
            amount=Decimal("-9.99"),
            currency="EUR",
            description="Held card authorization",
            merchant_name="Store",
            counterparty_name=None,
            direction="debit",
            status="pending",
            category_id=None,
            matched_rule_id=None,
            raw_payload={"source": "test"},
            imported_at=datetime(2026, 6, 20, 9, 0, tzinfo=timezone.utc),
        )
    )
    db.commit()
    service = LedgerService(db=db)

    response = service.list_transactions(
        account_id=str(primary_account.id),
        month="2026-06",
        status="pending",
        limit=10,
        offset=0,
    )

    assert response["total_count"] == 1
    assert response["transactions"][0]["description"] == "Held card authorization"
    assert response["transactions"][0]["booking_date"] is None


def test_ledger_service_rejects_invalid_month_format() -> None:
    db = make_session()
    seed_ledger_data(db)
    service = LedgerService(db=db)

    try:
        service.list_transactions(month="2026/06")
    except ValueError as exc:
        assert str(exc) == "Month must use YYYY-MM format"
    else:
        raise AssertionError("Expected invalid month format to raise ValueError")


def test_ledger_service_puts_an_undated_pending_charge_in_the_review_queue() -> None:
    db = make_session()
    primary_account, _ = seed_ledger_data(db)
    # Neither date supplied, so the month filter has nothing but the import day to
    # go on. Without it the charge sits in no month and the owner is never told
    # there is anything to review.
    db.add(
        Transaction(
            account_id=primary_account.id,
            enable_banking_transaction_id="tx-undated-pending",
            booking_date=None,
            value_date=None,
            amount=Decimal("-18.50"),
            currency="EUR",
            description="Card authorization",
            merchant_name="Bar",
            counterparty_name=None,
            direction="debit",
            status="pending",
            category_id=None,
            matched_rule_id=None,
            raw_payload={"source": "test"},
            imported_at=datetime(2026, 6, 19, 21, 0, tzinfo=timezone.utc),
        )
    )
    db.commit()
    service = LedgerService(db=db)

    queue = service.list_transactions(
        account_id=str(primary_account.id),
        month="2026-06",
        categorized=False,
        limit=10,
        offset=0,
    )
    count = service.get_uncategorized_transaction_count(
        account_id=str(primary_account.id),
        month="2026-06",
    )

    # Beside the seeded Coffee shop, which the queue already surfaced.
    assert sorted(row["description"] for row in queue["transactions"]) == [
        "Card authorization",
        "Coffee shop",
    ]
    assert count == 2


def add_category(db: Session, *, name: str, category_type: str) -> Category:
    category = Category(name=name, type=category_type, active=True)
    db.add(category)
    db.flush()
    return category


def add_budget(
    db: Session,
    *,
    category: Category,
    active_from: date,
    active_to: date | None = None,
) -> None:
    db.add(
        Budget(
            category_id=category.id,
            amount=Decimal("300.00"),
            currency="EUR",
            period_type="monthly",
            active_from=active_from,
            active_to=active_to,
            is_fixed=False,
        )
    )
    db.flush()


def add_june_charge(
    db: Session,
    *,
    account: Account,
    category: Category | None,
    description: str,
    amount: str = "-20.00",
    excluded_at: datetime | None = None,
) -> None:
    db.add(
        Transaction(
            account_id=account.id,
            enable_banking_transaction_id=f"tx-{description.lower().replace(' ', '-')}",
            booking_date=date(2026, 6, 12),
            value_date=date(2026, 6, 12),
            amount=Decimal(amount),
            currency="EUR",
            description=description,
            merchant_name=None,
            counterparty_name=None,
            direction="credit" if Decimal(amount) > 0 else "debit",
            status="booked",
            category_id=category.id if category else None,
            matched_rule_id=None,
            excluded_at=excluded_at,
            raw_payload={"source": "test"},
            imported_at=datetime(2026, 6, 12, 9, 0, tzinfo=timezone.utc),
        )
    )
    db.flush()


def descriptions(response: dict) -> list[str]:
    return [row["description"] for row in response["transactions"]]


def category_named(db: Session, name: str) -> Category:
    return db.execute(select(Category).where(Category.name == name)).scalar_one()


def seed_budget_coverage_scene(db: Session) -> Account:
    """June spend in two expense categories, one of which the month has a budget for.

    Both halves are needed in every test below: the budgeted row is what a filter
    that has stopped reading budgets at all would wrongly include, and the
    unbudgeted one is what keeps a passing assertion from being the empty list.
    """
    primary_account, _ = seed_ledger_data(db)
    add_budget(db, category=category_named(db, "Food"), active_from=date(2026, 1, 1))
    gadgets = add_category(db, name="Gadgets", category_type="expense")
    add_june_charge(db, account=primary_account, category=gadgets, description="Headphones")
    db.commit()
    return primary_account


def test_ledger_service_lists_the_spend_the_month_holds_no_budget_for() -> None:
    db = make_session()
    seed_budget_coverage_scene(db)
    service = LedgerService(db=db)

    response = service.list_transactions(month="2026-06", budgeted=False)

    # Groceries sits in Food, which June holds a budget for, so the month's only gap
    # in the budgets is the Gadgets charge.
    assert descriptions(response) == ["Headphones"]
    assert response["total_count"] == 1


def test_ledger_service_treats_only_categorized_expense_spend_as_unbudgeted() -> None:
    db = make_session()
    primary_account = seed_budget_coverage_scene(db)
    salary = add_category(db, name="Salary", category_type="income")
    add_june_charge(
        db,
        account=primary_account,
        category=salary,
        description="Payday",
        amount="1800.00",
    )
    db.commit()
    service = LedgerService(db=db)

    response = service.list_transactions(month="2026-06", budgeted=False)

    # No budget covers an income category and none ever will, and an uncategorized
    # charge -- the seeded "Coffee shop" -- belongs to the review queue, which has a
    # filter of its own. Either one here would bury the actual budget gaps.
    assert descriptions(response) == ["Headphones"]


def test_ledger_service_reads_a_budget_cancelled_mid_month_as_covering_that_month() -> None:
    db = make_session()
    seed_budget_coverage_scene(db)
    budget = db.execute(
        select(Budget).where(Budget.category_id == category_named(db, "Food").id)
    ).scalar_one()
    budget.active_to = date(2026, 6, 10)
    db.commit()
    service = LedgerService(db=db)

    response = service.list_transactions(month="2026-06", budgeted=False)

    # Budget windows are month-granular (docs/adr/0005): a window the month touches at
    # all counts for the whole month. June's Food spend is budgeted spend even though
    # the budget stopped on the 10th, which is also how the summary counts it.
    assert descriptions(response) == ["Headphones"]


def test_ledger_service_reads_a_budget_that_starts_next_month_as_covering_neither() -> None:
    db = make_session()
    seed_budget_coverage_scene(db)
    budget = db.execute(
        select(Budget).where(Budget.category_id == category_named(db, "Food").id)
    ).scalar_one()
    budget.active_from = date(2026, 7, 1)
    db.commit()
    service = LedgerService(db=db)

    response = service.list_transactions(month="2026-06", budgeted=False)

    # A budget scheduled for July leaves June's spend in that category unbudgeted,
    # even though the category does hold a budget row.
    assert descriptions(response) == ["Headphones", "Groceries"]


def test_ledger_service_lists_the_spend_a_budget_does_cover() -> None:
    db = make_session()
    seed_budget_coverage_scene(db)
    service = LedgerService(db=db)

    response = service.list_transactions(month="2026-06", budgeted=True)

    assert descriptions(response) == ["Groceries"]


def test_ledger_service_leaves_an_ignored_charge_out_of_unbudgeted_spend() -> None:
    db = make_session()
    primary_account = seed_budget_coverage_scene(db)
    # Excluding a charge clears its category, so nothing in the product writes this
    # row today -- a backfill or a stray write can, and Ignored means out of every
    # figure. Stated here rather than inherited from the shape of the join, for the
    # reason ``burnrate.db.dispositions`` gives.
    add_june_charge(
        db,
        account=primary_account,
        category=category_named(db, "Gadgets"),
        description="Refunded gadget",
        excluded_at=datetime(2026, 6, 13, 10, 0, tzinfo=timezone.utc),
    )
    db.commit()
    service = LedgerService(db=db)

    response = service.list_transactions(month="2026-06", budgeted=False)

    assert descriptions(response) == ["Headphones"]


def test_ledger_service_refuses_a_budget_filter_without_a_month() -> None:
    db = make_session()
    seed_budget_coverage_scene(db)
    service = LedgerService(db=db)

    # A budget covers months, so "has no budget" is unanswerable over all of history:
    # it would have to mean "no budget in any month", which is a different question
    # from the one the month-scoped view asks.
    with pytest.raises(ValueError, match="Month is required to filter by budget"):
        service.list_transactions(budgeted=False)


def test_ledger_service_reads_a_budget_created_mid_month_as_covering_that_month() -> None:
    db = make_session()
    seed_budget_coverage_scene(db)
    budget = db.execute(
        select(Budget).where(Budget.category_id == category_named(db, "Food").id)
    ).scalar_one()
    budget.active_from = date(2026, 6, 20)
    db.commit()
    service = LedgerService(db=db)

    response = service.list_transactions(month="2026-06", budgeted=False)

    # The budget starts on the 20th and the Groceries charge landed on the 10th. A
    # window still counts for any month it touches, so an owner who budgets a
    # category today sees this month stop reading as a gap, rather than having to
    # wait for the next one.
    assert descriptions(response) == ["Headphones"]

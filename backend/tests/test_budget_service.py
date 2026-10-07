from __future__ import annotations

from datetime import UTC, date, datetime
from decimal import Decimal

import pytest
from sqlalchemy import create_engine, select
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool

from burnrate.db.base import Base
from burnrate.db.models import Budget, Category
from burnrate.services.budget_service import BudgetService
from burnrate.services.summary_service import SummaryService
from conftest import AHEAD_OF_UTC, BEHIND_UTC


def make_session() -> Session:
    engine = create_engine(
        "sqlite+pysqlite:///:memory:",
        future=True,
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(engine)
    return sessionmaker(bind=engine, autoflush=False, autocommit=False)()


def next_month_start() -> date:
    """A first-of-month that is always in the future, independent of the run date."""
    today = datetime.now(UTC).date()
    if today.month == 12:
        return date(today.year + 1, 1, 1)
    return date(today.year, today.month + 1, 1)


def seed_budget_categories(db: Session) -> tuple[Category, Category]:
    expense = Category(name="Food", type="expense", active=True)
    income = Category(name="Salary", type="income", active=True)
    db.add_all([expense, income])
    db.commit()
    return expense, income


def test_budget_service_lists_and_creates_monthly_budgets() -> None:
    db = make_session()
    expense, _ = seed_budget_categories(db)
    service = BudgetService(db=db)

    created = service.create_budget(
        category_id=str(expense.id),
        amount=Decimal("300.00"),
        currency="eur",
        active_from=date(2026, 7, 1),
    )
    db.commit()
    budgets = service.list_budgets()

    assert created["category_name"] == "Food"
    assert created["currency"] == "EUR"
    assert created["period_type"] == "monthly"
    assert len(budgets) == 1
    assert budgets[0]["amount"] == "300.00"


def test_budget_service_closes_previous_open_budget_when_new_one_starts_later() -> None:
    db = make_session()
    expense, _ = seed_budget_categories(db)
    service = BudgetService(db=db)
    first = service.create_budget(
        category_id=str(expense.id),
        amount=Decimal("300.00"),
        currency="EUR",
        active_from=date(2026, 7, 1),
    )
    service.create_budget(
        category_id=str(expense.id),
        amount=Decimal("350.00"),
        currency="EUR",
        active_from=date(2026, 8, 1),
    )
    db.commit()

    first_budget = db.get(Budget, service._parse_uuid(first["budget_id"], "Budget id"))
    assert first_budget is not None
    assert first_budget.active_to == date(2026, 7, 31)


def test_budget_service_updates_budget_amount_and_currency() -> None:
    db = make_session()
    expense, _ = seed_budget_categories(db)
    service = BudgetService(db=db)
    created = service.create_budget(
        category_id=str(expense.id),
        amount=Decimal("300.00"),
        currency="EUR",
        active_from=date(2026, 7, 1),
    )

    updated = service.update_budget(
        budget_id=created["budget_id"],
        amount=Decimal("325.50"),
        currency="usd",
    )

    assert updated["amount"] == "325.50"
    assert updated["currency"] == "USD"


def test_budget_service_deactivates_budget() -> None:
    db = make_session()
    expense, _ = seed_budget_categories(db)
    service = BudgetService(db=db)
    created = service.create_budget(
        category_id=str(expense.id),
        amount=Decimal("300.00"),
        currency="EUR",
        active_from=next_month_start(),
    )

    response = service.deactivate_budget(budget_id=created["budget_id"])
    db.commit()
    stored = db.scalar(select(Budget).where(Budget.id == service._parse_uuid(created["budget_id"], "Budget id")))

    assert response["status"] == "inactive"
    assert stored is not None
    assert stored.active_to is not None


def test_budget_service_rejects_income_category_budgets() -> None:
    db = make_session()
    _, income = seed_budget_categories(db)
    service = BudgetService(db=db)

    try:
        service.create_budget(
            category_id=str(income.id),
            amount=Decimal("300.00"),
            currency="EUR",
            active_from=date(2026, 7, 1),
        )
    except ValueError as exc:
        assert str(exc) == "Budgets are only supported for expense categories"
    else:
        raise AssertionError("Expected income budget creation to fail")


def test_budget_service_rejects_non_month_start_budget_date() -> None:
    db = make_session()
    expense, _ = seed_budget_categories(db)
    service = BudgetService(db=db)

    try:
        service.create_budget(
            category_id=str(expense.id),
            amount=Decimal("300.00"),
            currency="EUR",
            active_from=date(2026, 7, 2),
        )
    except ValueError as exc:
        assert str(exc) == "Budget active_from must be the first day of a month"
    else:
        raise AssertionError("Expected invalid month start to fail")


def test_budget_service_rejects_overlapping_budget_periods() -> None:
    db = make_session()
    expense, _ = seed_budget_categories(db)
    service = BudgetService(db=db)
    service.create_budget(
        category_id=str(expense.id),
        amount=Decimal("300.00"),
        currency="EUR",
        active_from=date(2026, 8, 1),
    )

    try:
        service.create_budget(
            category_id=str(expense.id),
            amount=Decimal("320.00"),
            currency="EUR",
            active_from=date(2026, 7, 1),
        )
    except ValueError as exc:
        assert str(exc) == "Budget periods must not overlap for the same category"
    else:
        raise AssertionError("Expected overlapping budget creation to fail")


AHEAD_TZ, AHEAD_INSTANT, _ = AHEAD_OF_UTC
BEHIND_TZ, BEHIND_INSTANT, _ = BEHIND_UTC

# The owner's calendar day decides whether a budget starting on the 1st has started.
# Derived from UTC it is wrong for part of every month-end, in whichever direction
# APP_TIMEZONE points -- and a budget reported as scheduled holds no spend, so the
# owner sees a month with no target on the day it begins.
#
# timezone, instant, status of a budget starting 2026-07-01, what the owner sees
BUDGET_DAY_EXAMPLES = [
    (
        AHEAD_TZ,
        AHEAD_INSTANT,
        "active",
        "their July budget has started, while UTC still reads 30 June",
    ),
    (
        BEHIND_TZ,
        BEHIND_INSTANT,
        "scheduled",
        "their July budget has not started yet, while UTC has already turned",
    ),
]


@pytest.mark.parametrize(
    ("timezone_name", "instant", "status", "_what_the_owner_sees"),
    BUDGET_DAY_EXAMPLES,
)
def test_budget_service_decides_a_budgets_status_on_the_owners_day(
    timezone_name: str,
    instant: datetime,
    status: str,
    _what_the_owner_sees: str,
) -> None:
    db = make_session()
    expense, _ = seed_budget_categories(db)
    transport = Category(name="Transport", type="expense", active=True)
    db.add(transport)
    db.commit()
    service = BudgetService(db=db, timezone_name=timezone_name, clock=lambda: instant)

    created = service.create_budget(
        category_id=str(expense.id),
        amount=Decimal("300.00"),
        currency="EUR",
        active_from=date(2026, 7, 1),
    )
    # A budget a month further out is scheduled from either side of the boundary.
    # It is here to make the row above discriminating: read off the wall clock, the
    # status of a July budget is whatever month the suite happens to run in, which
    # is "active" for one of these rows by coincidence rather than by rule.
    ahead = service.create_budget(
        category_id=str(transport.id),
        amount=Decimal("60.00"),
        currency="EUR",
        active_from=date(2026, 8, 1),
    )
    db.commit()

    assert created["status"] == status
    assert created["active"] is (status == "active")
    assert ahead["status"] == "scheduled"
    # The same day has to decide it on the way back out, not just on creation.
    assert service.list_budgets()[0]["status"] == status


# Cancelling a running budget ends it the day before the owner's day, so which day
# that is decides which month the budget's last day falls in -- and a month-granular
# budget counts in full for any month it touches at all.
#
# timezone, instant, the day the budget is recorded as ending, what the owner did
CANCEL_DAY_EXAMPLES = [
    (
        AHEAD_TZ,
        AHEAD_INSTANT,
        date(2026, 6, 30),
        "cancelled just after their midnight on 1 July, while UTC still reads 30 June",
    ),
    (
        BEHIND_TZ,
        BEHIND_INSTANT,
        date(2026, 6, 29),
        "cancelled on their last evening of June, while UTC has already turned",
    ),
]


@pytest.mark.parametrize(
    ("timezone_name", "instant", "ends_on", "_what_the_owner_did"),
    CANCEL_DAY_EXAMPLES,
)
def test_budget_service_closes_a_running_budget_on_the_owners_day(
    timezone_name: str,
    instant: datetime,
    ends_on: date,
    _what_the_owner_did: str,
) -> None:
    """Cancelling a budget is dated off the owner's day, not off UTC's.

    Both directions matter because the two rows straddle a month boundary, and which
    side the recorded day lands on decides which months the budget covered. This test
    is about *whose clock* decides it; what the recorded day should then be is
    ``test_budget_service_cancelling_on_the_first_leaves_the_new_month_unbudgeted``.
    """
    db = make_session()
    expense, _ = seed_budget_categories(db)
    service = BudgetService(db=db, timezone_name=timezone_name, clock=lambda: instant)
    created = service.create_budget(
        category_id=str(expense.id),
        amount=Decimal("300.00"),
        currency="EUR",
        active_from=date(2026, 6, 1),
    )
    db.commit()

    response = service.deactivate_budget(budget_id=created["budget_id"])
    db.commit()

    assert response["active_to"] == ends_on


def test_budget_service_cancelling_on_the_first_leaves_the_new_month_unbudgeted() -> None:
    """Cancelling a budget must not hand it to the month the owner cancelled in.

    A budget is month-granular on the way in -- ``active_from`` has to be a 1st -- but
    ``active_to`` took any day, and ``_get_active_budgets`` counts a budget in full
    for any month it touches at all. So an ``active_to`` of the 1st meant the new
    month inherited the whole thing: the budget list read ``inactive`` while the
    dashboard kept citing the amount, and the owner's daily allowance came from a
    budget they had just switched off.

    Asserted through the summary because that is where the harm is visible; the
    recorded day on its own does not say why it matters.
    """
    db = make_session()
    expense, _ = seed_budget_categories(db)
    # 01:00 on the owner's 1 July. They cancel Food, meaning "no more Food budget".
    service = BudgetService(db=db, timezone_name=AHEAD_TZ, clock=lambda: AHEAD_INSTANT)
    created = service.create_budget(
        category_id=str(expense.id),
        amount=Decimal("300.00"),
        currency="EUR",
        active_from=date(2026, 6, 1),
    )
    db.commit()

    response = service.deactivate_budget(budget_id=created["budget_id"])
    db.commit()
    july = SummaryService(db=db).get_summary(month="2026-07", today=date(2026, 7, 15))

    # It ran through June and no further.
    assert response["active_to"] == date(2026, 6, 30)
    assert response["status"] == "inactive"
    # July never had a budget, so it says so instead of quoting the cancelled one.
    assert july["monthly_budget_amount"] == "0.00"
    assert july["budget_usage"] == []
    assert july["safe_to_spend_status"] == "no_budget"
    # June keeps it: the owner budgeted that month and spent against it.
    june = SummaryService(db=db).get_summary(month="2026-06", today=date(2026, 6, 15))
    assert june["monthly_budget_amount"] == "300.00"

from __future__ import annotations

from datetime import UTC, date, datetime, timedelta
from decimal import Decimal
from uuid import UUID

import pytest
from sqlalchemy import create_engine, event, select
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool

from burnrate.db.base import Base
from burnrate.db.models import Budget, Category
from burnrate.services.budget_service import BudgetService
from burnrate.services.categorization_service import CategorizationService
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


# Cancelling a running budget ends it on the last day of the month before the owner's
# own month, so which month the owner is in decides where the budget's window closes.
# Derived from UTC it is the wrong month for part of every month-end, which costs or
# gifts a whole month's budget -- a month-granular window counts in full.
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
        date(2026, 5, 31),
        "cancelled on their last evening of June, while UTC has already turned to July",
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
    """Cancelling a budget is dated off the owner's month, not off UTC's.

    Both directions matter because the two instants fall in different months on the
    owner's clock, and the month decides where the window closes -- a whole month of
    budget either way. This test is about *whose clock* decides it; what the recorded
    day should then be is
    ``test_budget_service_cancelling_mid_month_leaves_that_month_unbudgeted``.
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


def test_budget_service_reads_a_budgets_status_against_the_month_being_viewed() -> None:
    """The month on screen decides a budget's status, not the day the owner is in.

    The budget list was read off *today* while the dashboard's rows were read off the
    month being viewed, so a rent budget cancelled in October vanished from September
    -- the month it had covered, and whose total the summary still counted it in. Two
    screens showing one month, contradicting each other.

    Both rows and both months are needed to pin the rule down: read off today, Rent is
    inactive and Gym is scheduled whichever month is asked for, so a single row or a
    single month would pass on the old behaviour by coincidence.
    """
    db = make_session()
    seed_budget_categories(db)
    rent = Category(name="Rent", type="expense", active=True)
    gym = Category(name="Gym", type="expense", active=True)
    db.add_all([rent, gym])
    db.commit()
    # The owner's day is 13 October 2026.
    service = BudgetService(
        db=db,
        timezone_name="UTC",
        clock=lambda: datetime(2026, 10, 13, 9, 0, tzinfo=UTC),
    )
    rent_budget = service.create_budget(
        category_id=str(rent.id),
        amount=Decimal("800.00"),
        currency="EUR",
        active_from=date(2025, 1, 1),
        is_fixed=True,
    )
    service.create_budget(
        category_id=str(gym.id),
        amount=Decimal("40.00"),
        currency="EUR",
        active_from=date(2026, 11, 1),
    )
    db.commit()
    # They stopped renting, so they cancel it: the budget ran through 12 October.
    service.deactivate_budget(budget_id=rent_budget["budget_id"])
    db.commit()

    september = {row["category_name"]: row["status"] for row in service.list_budgets(month="2026-09")}
    october = {row["category_name"]: row["status"] for row in service.list_budgets(month="2026-10")}
    november = {row["category_name"]: row["status"] for row in service.list_budgets(month="2026-11")}

    # September was covered by Rent and not yet by Gym.
    assert september == {"Rent": "active", "Gym": "scheduled"}
    # October is the month they cancelled in, so it holds no Rent budget.
    assert october == {"Rent": "inactive", "Gym": "scheduled"}
    # By November Rent had stopped and Gym had started.
    assert november == {"Rent": "inactive", "Gym": "active"}
    # The flag the budgets page filters on has to agree with the status beside it.
    assert [row["active"] for row in service.list_budgets(month="2026-09") if row["category_name"] == "Rent"] == [True]


def test_budget_service_reads_a_mid_month_end_date_as_covering_that_month() -> None:
    """A window ending mid-month still counts that month in full.

    Cancelling records a month end now, so nothing the service writes can land here.
    Rows written before that rule can: the owner's database holds budgets cancelled
    under the old one, dated *yesterday*. Those are read with the same month-granular
    rule as everything else -- the month is counted in full, because a partial month
    is exactly what this project declined to define.

    So the comparison is against the month's first day and not its last, and the one
    day between ``<`` and ``<=`` is a whole month of budget for such a row.
    """
    db = make_session()
    seed_budget_categories(db)
    rent = Category(name="Rent", type="expense", active=True)
    db.add(rent)
    db.commit()
    # A row the old rule wrote: cancelled on 2 October, dated the day before.
    db.add(
        Budget(
            category_id=rent.id,
            amount=Decimal("800.00"),
            currency="EUR",
            period_type="monthly",
            active_from=date(2026, 9, 1),
            active_to=date(2026, 10, 1),
            is_fixed=True,
        )
    )
    db.commit()
    service = BudgetService(
        db=db,
        timezone_name="UTC",
        clock=lambda: datetime(2026, 10, 20, 9, 0, tzinfo=UTC),
    )

    # October is touched by the window, so it holds the whole budget.
    assert [row["status"] for row in service.list_budgets(month="2026-10")] == ["active"]
    # November is the first month it does not reach.
    assert [row["status"] for row in service.list_budgets(month="2026-11")] == ["inactive"]


def test_budget_service_cancelling_mid_month_leaves_that_month_unbudgeted() -> None:
    """Cancelling a budget means the commitment is gone, this month included.

    ``active_to`` was recorded as *yesterday*, so a budget cancelled on the 7th still
    covered the month -- month-granular windows count in full -- and the dashboard
    kept quoting a target the owner had just said would not be paid. Cancelling is a
    statement about what is still owed, not a note that something stopped partway
    through, so the month the owner cancels in loses the budget.

    Recording the last day of the *previous* month is what makes that true while
    keeping the window month-granular: ``active_from`` is always a 1st and
    ``active_to`` is always a month end, so neither edge can land mid-month.

    Asserted through the summary because that is where the owner sees it.
    """
    db = make_session()
    seed_budget_categories(db)
    rent = Category(name="Rent", type="expense", active=True)
    db.add(rent)
    db.commit()
    # The owner's day is 7 October 2026: they say there is no more rent to pay.
    service = BudgetService(
        db=db,
        timezone_name="UTC",
        clock=lambda: datetime(2026, 10, 7, 9, 0, tzinfo=UTC),
    )
    created = service.create_budget(
        category_id=str(rent.id),
        amount=Decimal("800.00"),
        currency="EUR",
        active_from=date(2026, 1, 1),
        is_fixed=True,
    )
    db.commit()

    cancelled = service.deactivate_budget(budget_id=created["budget_id"])
    db.commit()
    september = SummaryService(db=db).get_summary(month="2026-09", today=date(2026, 10, 7))
    october = SummaryService(db=db).get_summary(month="2026-10", today=date(2026, 10, 7))

    # September was the last month it covered, so it ends there and not on the 6th.
    assert cancelled["active_to"] == date(2026, 9, 30)
    assert september["monthly_budget_amount"] == "800.00"
    # October holds no rent budget at all, which reads as having none rather than as
    # a budget of zero.
    assert october["monthly_budget_amount"] == "0.00"
    assert [row["status"] for row in service.list_budgets(month="2026-10")] == ["inactive"]


def test_budget_service_reactivates_a_budget_cancelled_by_mistake() -> None:
    """Cancelling is one click, so it has to be undoable.

    The budget comes back as it was: an open window rolling forward from the month it
    already started in. Nothing is recreated, so the months it covered before the
    mistake keep the same row, the same amount and the same identity -- which is the
    whole reason cancelling never deleted anything.
    """
    db = make_session()
    seed_budget_categories(db)
    pharmacy = Category(name="Pharmacy", type="expense", active=True)
    db.add(pharmacy)
    db.commit()
    # The owner's day is 14 October 2026.
    service = BudgetService(
        db=db,
        timezone_name="UTC",
        clock=lambda: datetime(2026, 10, 14, 9, 0, tzinfo=UTC),
    )
    created = service.create_budget(
        category_id=str(pharmacy.id),
        amount=Decimal("50.00"),
        currency="EUR",
        active_from=date(2026, 6, 1),
    )
    db.commit()
    cancelled = service.deactivate_budget(budget_id=created["budget_id"])
    db.commit()
    assert cancelled["active_to"] == date(2026, 9, 30)
    assert [row["status"] for row in service.list_budgets(month="2026-10")] == ["inactive"]

    restored = service.reactivate_budget(budget_id=created["budget_id"])
    db.commit()

    # Open again, so it rolls forward with no month asked to close it.
    assert restored["budget_id"] == created["budget_id"]
    assert restored["active_to"] is None
    assert restored["active_from"] == date(2026, 6, 1)
    assert restored["status"] == "active"
    # The month the mistake had emptied holds it again, at the amount it always had.
    october = service.list_budgets(month="2026-10")
    assert [(row["status"], row["amount"]) for row in october] == [("active", "50.00")]


def test_budget_service_refuses_to_reactivate_a_budget_a_later_one_replaced() -> None:
    """Reopening a window must not run it into a budget that took over.

    Reactivating clears ``active_to``, so the window rolls forward indefinitely --
    straight through any budget the owner set up for the same category afterwards.
    Two overlapping budgets are what ``create_budget`` already refuses, and they
    would be summed into one inflated figure for every month they share.

    Refusing names the row in the way, because the owner's way out is to cancel or
    change that one -- a message that only said "overlap" would leave them guessing
    which of their budgets it meant.
    """
    db = make_session()
    seed_budget_categories(db)
    pharmacy = Category(name="Pharmacy", type="expense", active=True)
    db.add(pharmacy)
    db.commit()
    service = BudgetService(
        db=db,
        timezone_name="UTC",
        clock=lambda: datetime(2026, 10, 14, 9, 0, tzinfo=UTC),
    )
    cancelled = service.create_budget(
        category_id=str(pharmacy.id),
        amount=Decimal("50.00"),
        currency="EUR",
        active_from=date(2026, 6, 1),
    )
    db.commit()
    service.deactivate_budget(budget_id=cancelled["budget_id"])
    db.commit()
    # The owner moved on and budgeted Pharmacy again from November, at a new amount.
    service.create_budget(
        category_id=str(pharmacy.id),
        amount=Decimal("70.00"),
        currency="EUR",
        active_from=date(2026, 11, 1),
    )
    db.commit()

    try:
        service.reactivate_budget(budget_id=cancelled["budget_id"])
    except ValueError as exc:
        message = str(exc)
    else:
        raise AssertionError("expected reactivating into a later budget to be refused")

    assert "2026-11-01" in message
    assert "Pharmacy" in message
    # The refusal left the row exactly as it was, so November still has one budget.
    db.rollback()
    november = service.list_budgets(month="2026-11")
    assert [(row["status"], row["amount"]) for row in november] == [("active", "70.00"), ("inactive", "50.00")]


def test_budget_rows_report_the_renamed_category() -> None:
    """The label on a budget row is the category's name, so a rename has to show up
    there without the budget row itself being touched."""
    db = make_session()
    expense, _ = seed_budget_categories(db)
    budget_service = BudgetService(db=db)
    created = budget_service.create_budget(
        category_id=str(expense.id),
        amount=Decimal("300.00"),
        currency="EUR",
        active_from=date(2026, 7, 1),
    )
    db.commit()

    CategorizationService(db=db).rename_category(category_id=str(expense.id), name="Groceries")
    db.commit()

    budgets = budget_service.list_budgets(month="2026-07")

    assert [budget["budget_id"] for budget in budgets] == [created["budget_id"]]
    assert budgets[0]["category_name"] == "Groceries"
    assert budgets[0]["amount"] == "300.00"


def test_budget_cannot_be_reactivated_onto_an_archived_category() -> None:
    """Reopening a window has to answer to the same guard that opening one does.

    ``create_budget`` refuses an inactive category. Without the same check here, the
    way to get a live budget on an archived category is to cancel it, archive the
    category -- which is permitted, because the closed window reaches no month -- and
    then reactivate. The month's budget total then counts a category hidden from
    every picker, so nothing can ever be spent against it: a permanently underspent
    budget inflating Safe to Spend Today.
    """
    db = make_session()
    expense, _ = seed_budget_categories(db)
    budget_service = BudgetService(db=db)
    created = budget_service.create_budget(
        category_id=str(expense.id),
        amount=Decimal("40.00"),
        currency="EUR",
        active_from=date(2026, 1, 1),
    )
    budget_service.deactivate_budget(budget_id=created["budget_id"])
    db.commit()
    CategorizationService(db=db).archive_category(category_id=str(expense.id))
    db.commit()

    with pytest.raises(ValueError, match=f"Category '{expense.name}' is inactive"):
        budget_service.reactivate_budget(budget_id=created["budget_id"])


# A fixed instant, so which month is "current" is the test's decision and not the
# calendar's. Cancelling writes a window relative to it.
OCTOBER = datetime(2026, 10, 14, 9, 0, tzinfo=UTC)


def october_service(db: Session) -> BudgetService:
    return BudgetService(db=db, timezone_name="Europe/Madrid", clock=lambda: OCTOBER)


def test_an_emptied_window_does_not_block_a_replacement_for_the_same_month() -> None:
    """Cancelling a budget before it ran leaves a window covering no month at all, and
    a row that covers nothing cannot be overlapped.

    This is the legitimate flow the overlap guard must not refuse: set a budget for
    October, cancel it, then set a different amount for October.
    """
    db = make_session()
    expense, _ = seed_budget_categories(db)
    service = october_service(db)
    first = service.create_budget(
        category_id=str(expense.id),
        amount=Decimal("500.00"),
        currency="EUR",
        active_from=date(2026, 10, 1),
    )
    service.deactivate_budget(budget_id=first["budget_id"])
    db.commit()

    replacement = service.create_budget(
        category_id=str(expense.id),
        amount=Decimal("600.00"),
        currency="EUR",
        active_from=date(2026, 10, 1),
    )
    db.commit()

    assert replacement["amount"] == "600.00"
    assert replacement["status"] == "active"


def test_budget_cannot_be_reactivated_when_a_replacement_starts_the_same_month() -> None:
    """The month a replacement starts in is the month reopening would double.

    A guard that only looks for a *later* budget misses the replacement that starts on
    the same day, and the summary then sums both rows into one inflated figure -- the
    outcome ADR 0005 exists to prevent.
    """
    db = make_session()
    expense, _ = seed_budget_categories(db)
    service = october_service(db)
    first = service.create_budget(
        category_id=str(expense.id),
        amount=Decimal("500.00"),
        currency="EUR",
        active_from=date(2026, 10, 1),
    )
    service.deactivate_budget(budget_id=first["budget_id"])
    db.commit()
    service.create_budget(
        category_id=str(expense.id),
        amount=Decimal("600.00"),
        currency="EUR",
        active_from=date(2026, 10, 1),
    )
    db.commit()

    with pytest.raises(ValueError, match="cannot be reactivated"):
        service.reactivate_budget(budget_id=first["budget_id"])

    # And the month still holds exactly one budget for the category.
    october = [row for row in service.list_budgets(month="2026-10") if row["active"]]
    assert [row["amount"] for row in october] == ["600.00"]


def test_budget_cannot_be_reactivated_across_an_earlier_window_left_open() -> None:
    """Overlap is symmetric, and the guard has to be too.

    An open window that starts *earlier* is not a successor, so a guard phrased as
    "is there a later budget" cannot see it. The service's own flows do not currently
    produce this pair, which is exactly why the rule should hold by construction
    rather than by reasoning across three methods.
    """
    db = make_session()
    expense, _ = seed_budget_categories(db)
    service = october_service(db)
    # Built directly: no sequence of service calls arranges this today.
    earlier_open = Budget(
        category_id=expense.id,
        amount=Decimal("300.00"),
        currency="EUR",
        period_type="monthly",
        active_from=date(2026, 1, 1),
        active_to=None,
        is_fixed=False,
    )
    cancelled_later = Budget(
        category_id=expense.id,
        amount=Decimal("400.00"),
        currency="EUR",
        period_type="monthly",
        active_from=date(2026, 3, 1),
        active_to=date(2026, 5, 31),
        is_fixed=False,
    )
    db.add_all([earlier_open, cancelled_later])
    db.commit()

    with pytest.raises(ValueError, match="cannot be reactivated"):
        service.reactivate_budget(budget_id=str(cancelled_later.id))


def test_a_cancelled_future_budget_does_not_block_an_earlier_month() -> None:
    """An empty window must not block through the date it never reached.

    Cancelling a budget scheduled ahead records an ``active_to`` *before* its own
    ``active_from`` -- here December start, September end. Compared to a window
    starting earlier still, that phantom end looks like an overlap, so the row has to
    be skipped for covering no month rather than merely out-ordered by its dates.
    """
    db = make_session()
    expense, _ = seed_budget_categories(db)
    service = october_service(db)
    scheduled = service.create_budget(
        category_id=str(expense.id),
        amount=Decimal("500.00"),
        currency="EUR",
        active_from=date(2026, 12, 1),
    )
    service.deactivate_budget(budget_id=scheduled["budget_id"])
    db.commit()
    stored = db.get(Budget, UUID(scheduled["budget_id"]))
    assert stored.active_to == date(2026, 9, 30) < stored.active_from

    backfilled = service.create_budget(
        category_id=str(expense.id),
        amount=Decimal("300.00"),
        currency="EUR",
        active_from=date(2026, 9, 1),
    )
    db.commit()

    assert backfilled["amount"] == "300.00"


def test_cancelling_closes_the_window_against_the_month_being_viewed() -> None:
    """The month the owner is looking at decides the window, not the server's clock.

    ``list_budgets`` already answers for the month requested. Cancelling read the
    owner's own month instead, so a click made while paging through September wrote
    October's window: the refetched row came back unchanged and the toast still said
    the budget was cancelled.

    The clock here reads October while the cancellation is issued from September, so
    this also pins the backdated case. Rewriting what a past month reports is allowed
    on purpose -- see ADR 0005 -- because the only person who can do it is the one
    whose spending those months describe. Do not add a guard against it without
    changing that decision first.
    """
    db = make_session()
    expense, _ = seed_budget_categories(db)
    service = october_service(db)
    created = service.create_budget(
        category_id=str(expense.id),
        amount=Decimal("800.00"),
        currency="EUR",
        active_from=date(2026, 1, 1),
    )
    db.commit()

    cancelled = service.deactivate_budget(budget_id=created["budget_id"], month="2026-09")
    db.commit()

    # Gone from September on, which is what cancelling from September means.
    assert cancelled["active_to"] == date(2026, 8, 31)
    assert [row["amount"] for row in service.list_budgets(month="2026-08") if row["active"]] == ["800.00"]
    assert [row for row in service.list_budgets(month="2026-09") if row["active"]] == []


def test_cancelling_without_a_month_still_uses_the_month_the_owner_is_in() -> None:
    db = make_session()
    expense, _ = seed_budget_categories(db)
    service = october_service(db)
    created = service.create_budget(
        category_id=str(expense.id),
        amount=Decimal("800.00"),
        currency="EUR",
        active_from=date(2026, 1, 1),
    )
    db.commit()

    cancelled = service.deactivate_budget(budget_id=created["budget_id"])

    assert cancelled["active_to"] == date(2026, 9, 30)


def test_reactivating_reports_its_status_against_the_month_being_viewed() -> None:
    db = make_session()
    expense, _ = seed_budget_categories(db)
    service = october_service(db)
    created = service.create_budget(
        category_id=str(expense.id),
        amount=Decimal("800.00"),
        currency="EUR",
        active_from=date(2026, 11, 1),
    )
    db.commit()
    service.deactivate_budget(budget_id=created["budget_id"])
    db.commit()

    restored = service.reactivate_budget(budget_id=created["budget_id"], month="2026-11")

    # Reopened, and November is the month that holds it -- read from October it would
    # report "scheduled", which is true of a different month than the one on screen.
    assert restored["status"] == "active"


def test_a_cancelled_budget_reports_that_it_can_be_reopened() -> None:
    db = make_session()
    expense, _ = seed_budget_categories(db)
    service = october_service(db)
    created = service.create_budget(
        category_id=str(expense.id),
        amount=Decimal("800.00"),
        currency="EUR",
        active_from=date(2026, 1, 1),
    )
    service.deactivate_budget(budget_id=created["budget_id"])
    db.commit()

    row = next(r for r in service.list_budgets(month="2026-10") if r["budget_id"] == created["budget_id"])

    assert row["can_reactivate"] is True


def test_a_superseded_budget_reports_that_it_cannot_be_reopened() -> None:
    """The row a later budget replaced is history, not an undoable cancellation.

    It reads as cancelled -- inactive with an end date -- so the list offered it a
    restore button that `reactivate_budget` always refuses.
    """
    db = make_session()
    expense, _ = seed_budget_categories(db)
    service = october_service(db)
    first = service.create_budget(
        category_id=str(expense.id),
        amount=Decimal("500.00"),
        currency="EUR",
        active_from=date(2026, 1, 1),
    )
    service.create_budget(
        category_id=str(expense.id),
        amount=Decimal("600.00"),
        currency="EUR",
        active_from=date(2026, 6, 1),
    )
    db.commit()

    rows = {r["budget_id"]: r for r in service.list_budgets(month="2026-10")}

    assert rows[first["budget_id"]]["status"] == "inactive"
    assert rows[first["budget_id"]]["can_reactivate"] is False


def test_a_cancelled_budget_on_an_archived_category_cannot_be_reopened() -> None:
    db = make_session()
    expense, _ = seed_budget_categories(db)
    service = october_service(db)
    created = service.create_budget(
        category_id=str(expense.id),
        amount=Decimal("40.00"),
        currency="EUR",
        active_from=date(2026, 1, 1),
    )
    service.deactivate_budget(budget_id=created["budget_id"])
    db.commit()
    CategorizationService(db=db).archive_category(category_id=str(expense.id))
    db.commit()

    row = next(r for r in service.list_budgets(month="2026-10") if r["budget_id"] == created["budget_id"])

    assert row["can_reactivate"] is False


def test_a_running_budget_is_not_offered_reopening() -> None:
    db = make_session()
    expense, _ = seed_budget_categories(db)
    service = october_service(db)
    service.create_budget(
        category_id=str(expense.id),
        amount=Decimal("800.00"),
        currency="EUR",
        active_from=date(2026, 1, 1),
    )
    db.commit()

    assert service.list_budgets(month="2026-10")[0]["can_reactivate"] is False


def test_what_the_list_offers_reopening_is_exactly_what_the_endpoint_accepts() -> None:
    """The flag and the guard are one rule, asserted together.

    Two spellings of "can this be reopened" is how the UI came to show a button the
    endpoint always refused. This holds them to the same answer across a set built to
    contain every shape: cancelled, superseded, running, and archived.
    """
    db = make_session()
    expense, _ = seed_budget_categories(db)
    # Budgets are expense-only, so the second shape needs a second expense category.
    other = Category(name="Transport", type="expense", active=True)
    db.add(other)
    db.commit()
    service = october_service(db)

    cancelled = service.create_budget(
        category_id=str(expense.id), amount=Decimal("800.00"), currency="EUR",
        active_from=date(2026, 1, 1),
    )
    service.deactivate_budget(budget_id=cancelled["budget_id"])
    superseded = service.create_budget(
        category_id=str(other.id), amount=Decimal("500.00"), currency="EUR",
        active_from=date(2026, 1, 1),
    )
    running = service.create_budget(
        category_id=str(other.id), amount=Decimal("600.00"), currency="EUR",
        active_from=date(2026, 6, 1),
    )
    db.commit()

    offered, refused = [], []
    for row in service.list_budgets(month="2026-10"):
        try:
            service.reactivate_budget(budget_id=row["budget_id"])
        except ValueError:
            refused.append(row["budget_id"])
        else:
            offered.append(row["budget_id"])
        db.rollback()

    listed_as_reopenable = {
        row["budget_id"] for row in service.list_budgets(month="2026-10") if row["can_reactivate"]
    }
    # Every row the endpoint refuses must not be offered, and vice versa. A running
    # row is accepted by the endpoint as a no-op but is not offered, so it is checked
    # on the one side that matters: nothing offered may be refused.
    assert listed_as_reopenable.isdisjoint(set(refused))
    assert cancelled["budget_id"] in listed_as_reopenable
    assert superseded["budget_id"] in refused
    assert running["budget_id"] not in listed_as_reopenable


def test_reactivating_restores_the_window_whatever_month_it_is_asked_from() -> None:
    """Undo restores; it does not re-cut the window.

    Cancelling is month-relative -- it closes against the month on screen -- so the
    symmetry is tempting to assume. It does not hold: reactivation clears ``active_to``
    outright, and its ``month`` only decides which month the response reports the row's
    status against. Asserted because ADR 0005 states it, and a stated asymmetry with
    no test is the kind that quietly becomes false.
    """
    db = make_session()
    expense, _ = seed_budget_categories(db)
    service = october_service(db)
    created = service.create_budget(
        category_id=str(expense.id),
        amount=Decimal("800.00"),
        currency="EUR",
        active_from=date(2026, 1, 1),
    )
    service.deactivate_budget(budget_id=created["budget_id"], month="2026-09")
    db.commit()
    assert db.get(Budget, UUID(created["budget_id"])).active_to == date(2026, 8, 31)

    # Reopened from a month far from both the cancellation month and the owner's own.
    restored = service.reactivate_budget(budget_id=created["budget_id"], month="2026-12")
    db.commit()

    assert restored["active_to"] is None
    assert db.get(Budget, UUID(created["budget_id"])).active_from == date(2026, 1, 1)
    # Every month from the original start is covered again, including the ones the
    # cancellation had taken away.
    for month in ("2026-08", "2026-09", "2026-10", "2026-12"):
        active = [row for row in service.list_budgets(month=month) if row["active"]]
        assert [row["amount"] for row in active] == ["800.00"], month


def month_last_day(year: int, month: int) -> date:
    first_of_next = date(year + (month == 12), month % 12 + 1, 1)
    return first_of_next - timedelta(days=1)


def statements_for_listing(closed_rows: int) -> int:
    """How many SQL statements one ``list_budgets`` call issues over this many rows.

    Each closed row is a distinct, non-overlapping window, the way a category
    accumulates them: one per amount change the owner has ever made.
    """
    db = make_session()
    expense, _ = seed_budget_categories(db)
    for index in range(closed_rows):
        year, month = 2024 + index // 12, index % 12 + 1
        db.add(
            Budget(
                category_id=expense.id,
                amount=Decimal("10.00"),
                currency="EUR",
                period_type="monthly",
                active_from=date(year, month, 1),
                active_to=month_last_day(year, month),
                is_fixed=False,
            )
        )
    db.commit()

    statements: list[str] = []

    def record(_conn, _cursor, statement, _params, _context, _many) -> None:
        statements.append(statement)

    engine = db.get_bind()
    event.listen(engine, "before_cursor_execute", record)
    try:
        rows = october_service(db).list_budgets(month="2026-10")
    finally:
        event.remove(engine, "before_cursor_execute", record)

    assert len(rows) == closed_rows
    return len(statements)


def test_listing_budgets_does_not_query_once_per_closed_row() -> None:
    """The cost of listing must not grow with the owner's edit history.

    Every amount change leaves a closed row behind for good, and each one was asked
    about separately to decide whether it could be reopened. The month on screen still
    holds three budgets; the call got slower every year.

    Compared between two sizes rather than pinned to a number, so an unrelated query
    added elsewhere does not fail this while the shape it guards is still fine.
    """
    assert statements_for_listing(12) == statements_for_listing(2)

from __future__ import annotations

from datetime import UTC, date, datetime
from decimal import Decimal

from sqlalchemy import create_engine, select
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool

from burnrate.db.base import Base
from burnrate.db.models import Budget, Category
from burnrate.services.budget_service import BudgetService


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

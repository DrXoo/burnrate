from __future__ import annotations

from datetime import date, datetime, timezone
from decimal import Decimal

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from burnrate.db.base import Base
from burnrate.db.models import Account, Budget, Category, Transaction
from burnrate.telegram.formatters import UNKNOWN_COMMAND_TEXT
from burnrate.telegram.router import TelegramCommandRouter


def make_session_factory() -> sessionmaker:
    engine = create_engine(
        "sqlite+pysqlite:///:memory:",
        future=True,
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(engine)
    return sessionmaker(bind=engine, autoflush=False, autocommit=False)


def seed(session_factory: sessionmaker) -> None:
    session = session_factory()
    account = Account(
        display_name="Main",
        currency="EUR",
        included_in_calculations=True,
        latest_balance_amount=Decimal("500.00"),
        latest_balance_currency="EUR",
    )
    session.add(account)
    session.flush()

    food = Category(name="Food", type="expense", active=True)
    session.add(food)
    session.flush()

    session.add(
        Budget(
            category_id=food.id,
            amount=Decimal("200.00"),
            currency="EUR",
            period_type="monthly",
            active_from=date(2026, 6, 1),
            active_to=None,
        )
    )

    imported_at = datetime(2026, 6, 15, 9, 0, tzinfo=timezone.utc)
    session.add(
        Transaction(
            account_id=account.id,
            booking_date=date(2026, 6, 10),
            amount=Decimal("-50.00"),
            currency="EUR",
            description="Groceries",
            direction="debit",
            status="booked",
            category_id=food.id,
            imported_at=imported_at,
        )
    )
    session.add(
        Transaction(
            account_id=account.id,
            booking_date=date(2026, 6, 12),
            amount=Decimal("-30.00"),
            currency="EUR",
            description="Mystery charge",
            merchant_name="Coffee Shop",
            direction="debit",
            status="booked",
            category_id=None,
            imported_at=imported_at,
        )
    )
    session.commit()
    session.close()


def make_router(*, now: datetime | None = None) -> TelegramCommandRouter:
    factory = make_session_factory()
    seed(factory)
    # The seeded uncategorized transaction is dated June 2026, so default the test
    # clock there to keep the current-month /unknown default deterministic.
    clock = (lambda: now) if now is not None else (lambda: datetime(2026, 6, 15, tzinfo=timezone.utc))
    return TelegramCommandRouter(session_factory=factory, clock=clock)


def test_help_lists_commands() -> None:
    text = make_router().handle("/help")

    assert "/summary" in text
    assert "/budgets" in text
    assert "/unknown" in text


def test_start_returns_help() -> None:
    assert make_router().handle("/start") == make_router().handle("/help")


def test_summary_reports_month_and_balance() -> None:
    text = make_router().handle("/summary 2026-06")

    assert "Summary for 2026-06" in text
    assert "Balance: 500.00 EUR" in text
    assert "Budget: 200.00 EUR" in text


def test_budgets_reports_category_status() -> None:
    text = make_router().handle("/budgets 2026-06")

    assert "Budget status for 2026-06" in text
    assert "Food" in text


def test_unknown_lists_uncategorized_transactions() -> None:
    text = make_router().handle("/unknown")

    assert "1 unknown transaction(s)" in text
    assert "Coffee Shop" in text


def test_unknown_defaults_to_current_month_and_excludes_older() -> None:
    # In July the June leftover should no longer show under the bare /unknown.
    text = make_router(now=datetime(2026, 7, 4, tzinfo=timezone.utc)).handle("/unknown")

    assert "No unknown transactions" in text
    assert "Coffee Shop" not in text


def test_unknown_accepts_explicit_month() -> None:
    text = make_router(now=datetime(2026, 7, 4, tzinfo=timezone.utc)).handle("/unknown 2026-06")

    assert "1 unknown transaction(s)" in text
    assert "Coffee Shop" in text


def test_unrecognized_command_returns_help_hint() -> None:
    assert make_router().handle("/nope") == UNKNOWN_COMMAND_TEXT


def test_invalid_month_returns_warning() -> None:
    text = make_router().handle("/summary 2026-13")

    assert text.startswith("⚠️")


def test_command_strips_bot_mention() -> None:
    text = make_router().handle("/summary@BurnRateBot 2026-06")

    assert "Summary for 2026-06" in text

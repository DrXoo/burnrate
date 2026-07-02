from __future__ import annotations

from datetime import date, datetime, timezone
from decimal import Decimal

from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool

from burnrate.db.base import Base
from burnrate.db.models import Account, Budget, Category, Transaction
from burnrate.services.summary_service import SummaryService


def make_session() -> Session:
    engine = create_engine(
        "sqlite+pysqlite:///:memory:",
        future=True,
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(engine)
    return sessionmaker(bind=engine, autoflush=False, autocommit=False)()


def seed_summary_data(db: Session) -> None:
    main_account = Account(
        display_name="Main account",
        currency="EUR",
        included_in_calculations=True,
        included_in_runway=False,
        latest_balance_amount=Decimal("500.00"),
        latest_balance_currency="EUR",
        last_synced_at=datetime(2026, 6, 15, 9, 0, tzinfo=timezone.utc),
    )
    savings_account = Account(
        display_name="Savings",
        currency="EUR",
        included_in_calculations=True,
        included_in_runway=True,
        latest_balance_amount=Decimal("1500.00"),
        latest_balance_currency="EUR",
        last_synced_at=datetime(2026, 6, 15, 9, 0, tzinfo=timezone.utc),
    )
    excluded_account = Account(
        display_name="Side account",
        currency="EUR",
        included_in_calculations=False,
        included_in_runway=False,
        latest_balance_amount=Decimal("900.00"),
        latest_balance_currency="EUR",
        last_synced_at=datetime(2026, 6, 15, 9, 0, tzinfo=timezone.utc),
    )
    db.add_all([main_account, savings_account, excluded_account])
    db.flush()

    food = Category(name="Food", type="expense", active=True)
    utilities = Category(name="Utilities", type="expense", active=True)
    salary = Category(name="Salary", type="income", active=True)
    transfer = Category(name="Internal transfer", type="transfer", active=True)
    db.add_all([food, utilities, salary, transfer])
    db.flush()

    db.add_all(
        [
            Budget(
                category_id=food.id,
                amount=Decimal("300.00"),
                currency="EUR",
                period_type="monthly",
                active_from=date(2026, 6, 1),
                active_to=None,
            ),
            Budget(
                category_id=utilities.id,
                amount=Decimal("100.00"),
                currency="EUR",
                period_type="monthly",
                active_from=date(2026, 6, 1),
                active_to=None,
            ),
        ]
    )

    db.add_all(
        [
            Transaction(
                account_id=main_account.id,
                enable_banking_transaction_id="tx-food",
                booking_date=date(2026, 6, 5),
                value_date=date(2026, 6, 5),
                amount=Decimal("-140.00"),
                currency="EUR",
                description="Groceries",
                merchant_name="Market",
                counterparty_name=None,
                direction="debit",
                status="booked",
                category_id=food.id,
                matched_rule_id=None,
                raw_payload=None,
                imported_at=datetime(2026, 6, 5, 8, 0, tzinfo=timezone.utc),
            ),
            Transaction(
                account_id=main_account.id,
                enable_banking_transaction_id="tx-utilities",
                booking_date=date(2026, 6, 10),
                value_date=date(2026, 6, 10),
                amount=Decimal("-120.00"),
                currency="EUR",
                description="Power bill",
                merchant_name="Electricity",
                counterparty_name=None,
                direction="debit",
                status="booked",
                category_id=utilities.id,
                matched_rule_id=None,
                raw_payload=None,
                imported_at=datetime(2026, 6, 10, 8, 0, tzinfo=timezone.utc),
            ),
            Transaction(
                account_id=main_account.id,
                enable_banking_transaction_id="tx-unknown",
                booking_date=date(2026, 6, 12),
                value_date=date(2026, 6, 12),
                amount=Decimal("-20.00"),
                currency="EUR",
                description="Mystery charge",
                merchant_name="Unknown",
                counterparty_name=None,
                direction="debit",
                status="booked",
                category_id=None,
                matched_rule_id=None,
                raw_payload=None,
                imported_at=datetime(2026, 6, 12, 8, 0, tzinfo=timezone.utc),
            ),
            Transaction(
                account_id=main_account.id,
                enable_banking_transaction_id="tx-income",
                booking_date=date(2026, 6, 3),
                value_date=date(2026, 6, 3),
                amount=Decimal("2000.00"),
                currency="EUR",
                description="Salary",
                merchant_name=None,
                counterparty_name="Employer",
                direction="credit",
                status="booked",
                category_id=salary.id,
                matched_rule_id=None,
                raw_payload=None,
                imported_at=datetime(2026, 6, 3, 8, 0, tzinfo=timezone.utc),
            ),
            Transaction(
                account_id=main_account.id,
                enable_banking_transaction_id="tx-transfer",
                booking_date=date(2026, 6, 8),
                value_date=date(2026, 6, 8),
                amount=Decimal("-100.00"),
                currency="EUR",
                description="Savings transfer",
                merchant_name=None,
                counterparty_name="Savings",
                direction="debit",
                status="booked",
                category_id=transfer.id,
                matched_rule_id=None,
                raw_payload=None,
                imported_at=datetime(2026, 6, 8, 8, 0, tzinfo=timezone.utc),
            ),
            Transaction(
                account_id=main_account.id,
                enable_banking_transaction_id="tx-pending",
                booking_date=date(2026, 6, 14),
                value_date=date(2026, 6, 14),
                amount=Decimal("-25.00"),
                currency="EUR",
                description="Pending snack",
                merchant_name="Cafe",
                counterparty_name=None,
                direction="debit",
                status="pending",
                category_id=food.id,
                matched_rule_id=None,
                raw_payload=None,
                imported_at=datetime(2026, 6, 14, 8, 0, tzinfo=timezone.utc),
            ),
            Transaction(
                account_id=excluded_account.id,
                enable_banking_transaction_id="tx-excluded",
                booking_date=date(2026, 6, 11),
                value_date=date(2026, 6, 11),
                amount=Decimal("-500.00"),
                currency="EUR",
                description="Excluded spend",
                merchant_name="Other",
                counterparty_name=None,
                direction="debit",
                status="booked",
                category_id=food.id,
                matched_rule_id=None,
                raw_payload=None,
                imported_at=datetime(2026, 6, 11, 8, 0, tzinfo=timezone.utc),
            ),
        ]
    )

    db.commit()


def test_summary_service_returns_phase_3_dashboard_metrics() -> None:
    db = make_session()
    seed_summary_data(db)
    service = SummaryService(db=db)

    summary = service.get_summary(month="2026-06", today=date(2026, 6, 15))

    assert summary["month"] == "2026-06"
    assert summary["current_balance_amount"] == "2000.00"
    assert summary["runway_balance_amount"] == "1500.00"
    assert summary["runway_account_count"] == 1
    assert summary["runway_accounts"][0]["display_name"] == "Savings"
    assert summary["runway_drain_amount"] == "90.00"
    assert summary["runway_drain_label"] == "Projected overspend"
    assert summary["runway_message"] == "Runway is based on projected monthly overspend against the active category budgets."
    assert summary["monthly_spending_amount"] == "260.00"
    assert summary["monthly_budget_amount"] == "400.00"
    assert summary["budgeted_spending_amount"] == "260.00"
    assert summary["unbudgeted_spending_amount"] == "0.00"
    assert summary["money_left_amount"] == "140.00"
    assert summary["uncategorized_count"] == 1
    assert summary["days_elapsed"] == 15
    assert summary["days_in_month"] == 30
    assert summary["average_daily_spend_amount"] == "17.33"
    # Budget-anchored projection: 260 spent + 15 remaining days x blended daily
    # (0.5*17.333 actual + 0.5*13.333 budget) = 490.00, so overspend = 490 - 400.
    assert summary["projected_month_end_spend_amount"] == "490.00"
    assert summary["projected_overspend_amount"] == "90.00"
    assert summary["runway_months_left"] == "16.67"
    assert summary["runway_status"] == "stable"
    assert summary["budget_usage"][0]["category_name"] == "Utilities"
    assert summary["budget_usage"][0]["status"] == "over"
    assert summary["budget_usage"][0]["remaining_amount"] == "-20.00"


def test_summary_service_splits_budgeted_and_unbudgeted_spend() -> None:
    db = make_session()
    seed_summary_data(db)
    # A categorized expense in a category that has no budget.
    main_account = db.query(Account).filter(Account.display_name == "Main account").one()
    entertainment = Category(name="Entertainment", type="expense", active=True)
    db.add(entertainment)
    db.flush()
    db.add(
        Transaction(
            account_id=main_account.id,
            enable_banking_transaction_id="tx-entertainment",
            booking_date=date(2026, 6, 6),
            value_date=date(2026, 6, 6),
            amount=Decimal("-30.00"),
            currency="EUR",
            description="Cinema",
            merchant_name="Theatre",
            counterparty_name=None,
            direction="debit",
            status="booked",
            category_id=entertainment.id,
            matched_rule_id=None,
            raw_payload=None,
            imported_at=datetime(2026, 6, 6, 8, 0, tzinfo=timezone.utc),
        )
    )
    db.commit()

    summary = SummaryService(db=db).get_summary(month="2026-06", today=date(2026, 6, 15))

    # monthly_spending reconciles as budgeted + unbudgeted.
    assert summary["monthly_spending_amount"] == "290.00"
    assert summary["budgeted_spending_amount"] == "260.00"
    assert summary["unbudgeted_spending_amount"] == "30.00"
    assert (
        Decimal(summary["budgeted_spending_amount"]) + Decimal(summary["unbudgeted_spending_amount"])
        == Decimal(summary["monthly_spending_amount"])
    )


def test_summary_service_marks_runway_not_available_without_runway_accounts() -> None:
    db = make_session()
    seed_summary_data(db)
    db.query(Account).filter(Account.included_in_runway.is_(True)).update({"included_in_runway": False})
    db.commit()
    service = SummaryService(db=db)

    summary = service.get_summary(month="2026-06", today=date(2026, 6, 15))

    assert summary["runway_balance_amount"] == "0.00"
    assert summary["runway_account_count"] == 0
    assert summary["runway_months_left"] is None
    assert summary["runway_status"] == "not_available"
    assert summary["runway_message"] == "Select one or more reserve accounts to activate runway tracking."


def test_summary_service_uses_projected_monthly_spend_when_no_budgets_exist() -> None:
    db = make_session()
    seed_summary_data(db)
    db.query(Budget).delete()
    db.commit()
    service = SummaryService(db=db)

    summary = service.get_summary(month="2026-06", today=date(2026, 6, 15))

    assert summary["runway_drain_label"] == "Projected monthly spend"
    assert summary["runway_drain_amount"] == "520.00"
    assert summary["runway_months_left"] == "2.88"
    assert summary["runway_status"] == "critical"
    assert (
        summary["runway_message"]
        == "No active budgets are configured, so runway uses projected monthly spending as the drain."
    )


def test_summary_service_rejects_invalid_month_format() -> None:
    db = make_session()
    seed_summary_data(db)
    service = SummaryService(db=db)

    try:
        service.get_summary(month="2026/06", today=date(2026, 6, 15))
    except ValueError as exc:
        assert str(exc) == "Month must use YYYY-MM format"
    else:
        raise AssertionError("Expected invalid month format to raise ValueError")

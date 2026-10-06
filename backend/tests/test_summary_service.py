from __future__ import annotations

from datetime import date, datetime, timezone
from decimal import Decimal

import pytest
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
        latest_balance_amount=Decimal("500.00"),
        latest_balance_currency="EUR",
        last_synced_at=datetime(2026, 6, 15, 9, 0, tzinfo=timezone.utc),
    )
    savings_account = Account(
        display_name="Savings",
        currency="EUR",
        included_in_calculations=True,
        latest_balance_amount=Decimal("1500.00"),
        latest_balance_currency="EUR",
        last_synced_at=datetime(2026, 6, 15, 9, 0, tzinfo=timezone.utc),
    )
    excluded_account = Account(
        display_name="Side account",
        currency="EUR",
        included_in_calculations=False,
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
    assert summary["monthly_spending_amount"] == "260.00"
    assert summary["monthly_income_amount"] == "2000.00"
    assert summary["net_cash_flow_amount"] == "1740.00"
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


def test_summary_service_extrapolates_projection_when_no_budgets_exist() -> None:
    db = make_session()
    seed_summary_data(db)
    db.query(Budget).delete()
    db.commit()
    service = SummaryService(db=db)

    summary = service.get_summary(month="2026-06", today=date(2026, 6, 15))

    # No budgets: variable spend is linearly extrapolated (260 over 15 days -> 520
    # for the full 30). Overspend is measured against budgeted categories, of which
    # there are none, so it stays at zero.
    assert summary["monthly_budget_amount"] == "0.00"
    assert summary["projected_month_end_spend_amount"] == "520.00"
    assert summary["projected_overspend_amount"] == "0.00"


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


def test_summary_service_excludes_fixed_budget_from_pace() -> None:
    db = make_session()
    seed_summary_data(db)
    # Utilities is a lump payment (power bill): mark its budget fixed. Its 120 charge
    # must drop out of the burn rate and be projected as-is instead of rate-scaled.
    utilities = db.query(Category).filter(Category.name == "Utilities").one()
    db.query(Budget).filter(Budget.category_id == utilities.id).update({"is_fixed": True})
    db.commit()

    summary = SummaryService(db=db).get_summary(month="2026-06", today=date(2026, 6, 15))

    # Burn rate now reflects only variable spend (Food 140 / 15 days), not the lump.
    assert summary["average_daily_spend_amount"] == "9.33"
    # Planned variable pace: Food budget 300 / 30 days.
    assert summary["expected_daily_spend_amount"] == "10.00"
    # Variable slice projects 285 (140 + 15 x blended 9.667); fixed adds its actual 120.
    assert summary["projected_month_end_spend_amount"] == "405.00"
    assert summary["projected_overspend_amount"] == "5.00"

    usage = {item["category_name"]: item for item in summary["budget_usage"]}
    assert usage["Utilities"]["is_fixed"] is True
    assert usage["Food"]["is_fixed"] is False


def test_summary_service_fixed_budget_uses_estimate_until_paid() -> None:
    db = make_session()
    seed_summary_data(db)
    # A fixed Rent budget with no charge booked yet should project at its estimate,
    # not zero, and not be rate-extrapolated.
    rent = Category(name="Rent", type="expense", active=True)
    db.add(rent)
    db.flush()
    db.add(
        Budget(
            category_id=rent.id,
            amount=Decimal("900.00"),
            currency="EUR",
            period_type="monthly",
            active_from=date(2026, 6, 1),
            active_to=None,
            is_fixed=True,
        )
    )
    db.commit()

    summary = SummaryService(db=db).get_summary(month="2026-06", today=date(2026, 6, 15))

    # Variable slice unchanged at 490; fixed Rent adds its 900 budgeted estimate.
    assert summary["projected_month_end_spend_amount"] == "1390.00"
    usage = {item["category_name"]: item for item in summary["budget_usage"]}
    assert usage["Rent"]["is_fixed"] is True
    assert usage["Rent"]["spent_amount"] == "0.00"


def test_summary_service_resolves_today_in_the_configured_timezone() -> None:
    # 00:30 on 1 July in Auckland (UTC+12), while UTC still reads 30 June.
    service = SummaryService(
        db=make_session(),
        timezone_name="Pacific/Auckland",
        clock=lambda: datetime(2026, 6, 30, 12, 30, tzinfo=timezone.utc),
    )

    summary = service.get_summary()

    assert summary["month"] == "2026-07"
    assert summary["days_elapsed"] == 1


def test_summary_service_rejects_a_clock_without_a_timezone() -> None:
    # A naive instant would be read as the host's local time, so the same reading
    # would resolve to a different day on a differently configured container.
    service = SummaryService(
        db=make_session(),
        timezone_name="Pacific/Auckland",
        clock=lambda: datetime(2026, 6, 30, 12, 30),
    )

    with pytest.raises(ValueError):
        service.get_summary()


def test_summary_service_reports_the_savings_rate_and_its_verdict() -> None:
    db = make_session()
    seed_summary_data(db)
    service = SummaryService(db=db)

    summary = service.get_summary(month="2026-06", today=date(2026, 6, 15))

    # The seeded month books 2000.00 of salary against 260.00 of spending, so the
    # owner kept 1740.00 -- 87% of what came in, comfortably clear of the band.
    assert summary["savings_rate_percent"] == 87.0
    assert summary["savings_status"] == "on_track"


def test_summary_service_leads_the_budget_rows_with_the_worst_off() -> None:
    db = make_session()
    seed_summary_data(db)
    # The seeded month leaves Utilities over (120.00 of 100.00) and Food on track
    # (140.00 of 300.00). Transport lands between them: 90.00 of 100.00 is a watch.
    main_account = db.query(Account).filter(Account.display_name == "Main account").one()
    transport = Category(name="Transport", type="expense", active=True)
    db.add(transport)
    db.flush()
    db.add(
        Budget(
            category_id=transport.id,
            amount=Decimal("100.00"),
            currency="EUR",
            period_type="monthly",
            active_from=date(2026, 6, 1),
            active_to=None,
        )
    )
    db.add(
        Transaction(
            account_id=main_account.id,
            enable_banking_transaction_id="tx-transport",
            booking_date=date(2026, 6, 7),
            value_date=date(2026, 6, 7),
            amount=Decimal("-90.00"),
            currency="EUR",
            description="Season ticket",
            merchant_name="Rail",
            counterparty_name=None,
            direction="debit",
            status="booked",
            category_id=transport.id,
            matched_rule_id=None,
            raw_payload=None,
            imported_at=datetime(2026, 6, 7, 8, 0, tzinfo=timezone.utc),
        )
    )
    db.commit()

    summary = SummaryService(db=db).get_summary(month="2026-06", today=date(2026, 6, 15))

    rows = [(row["category_name"], row["status"]) for row in summary["budget_usage"]]
    assert rows == [("Utilities", "over"), ("Transport", "watch"), ("Food", "on_track")]


def test_summary_service_reports_every_booked_figure_of_the_seeded_month_to_the_cent() -> None:
    # A pin on the figures the owner already relies on: no change to this module may
    # restate one of them. Every amount below is worked from the seed by hand --
    # 140 food + 120 utilities booked against 300 + 100 budgeted, 2000 salary in,
    # the 100 transfer and the 25 pending charge counting as neither.
    #
    # Every seeded row carries a booking date, so this guards the figures and not
    # the Effective Date fallbacks: the chain always resolves on its first link
    # here. The value-date and import-date links have their own tests below.
    db = make_session()
    seed_summary_data(db)

    summary = SummaryService(db=db).get_summary(month="2026-06", today=date(2026, 6, 15))

    assert {key: summary[key] for key in sorted(summary) if key.endswith("_amount")} == {
        "average_daily_spend_amount": "17.33",
        "budgeted_spending_amount": "260.00",
        "current_balance_amount": "2000.00",
        "expected_daily_spend_amount": "13.33",
        "money_left_amount": "140.00",
        "monthly_budget_amount": "400.00",
        "monthly_income_amount": "2000.00",
        "monthly_spending_amount": "260.00",
        "net_cash_flow_amount": "1740.00",
        "projected_month_end_spend_amount": "490.00",
        "projected_overspend_amount": "90.00",
        "unbudgeted_spending_amount": "0.00",
    }
    assert summary["uncategorized_count"] == 1
    assert summary["savings_rate_percent"] == 87.0
    assert [(row["category_name"], row["spent_amount"]) for row in summary["budget_usage"]] == [
        ("Utilities", "120.00"),
        ("Food", "140.00"),
    ]


def test_summary_service_counts_a_transaction_with_no_booking_date_by_its_value_date() -> None:
    # The bank settled this charge but supplied only a value date. A month window on
    # booking_date alone never matches NULL, so the 30 was invisible to every figure.
    db = make_session()
    seed_summary_data(db)
    main_account = db.query(Account).filter(Account.display_name == "Main account").one()
    food = db.query(Category).filter(Category.name == "Food").one()
    db.add(
        Transaction(
            account_id=main_account.id,
            enable_banking_transaction_id="tx-no-booking-date",
            booking_date=None,
            value_date=date(2026, 6, 18),
            amount=Decimal("-30.00"),
            currency="EUR",
            description="Lunch",
            merchant_name="Canteen",
            counterparty_name=None,
            direction="debit",
            status="booked",
            category_id=food.id,
            matched_rule_id=None,
            raw_payload=None,
            imported_at=datetime(2026, 6, 18, 8, 0, tzinfo=timezone.utc),
        )
    )
    db.commit()

    summary = SummaryService(db=db).get_summary(month="2026-06", today=date(2026, 6, 20))

    assert summary["monthly_spending_amount"] == "290.00"
    assert summary["budgeted_spending_amount"] == "290.00"
    food_row = next(row for row in summary["budget_usage"] if row["category_name"] == "Food")
    assert food_row["spent_amount"] == "170.00"


def test_summary_service_counts_an_undated_pending_charge_in_the_month_it_was_imported() -> None:
    # Restricted-production pending rows can arrive with neither date set. Without a
    # last resort the charge belongs to no month at all, so it reaches no review
    # queue and the owner never sees there is something to categorize.
    db = make_session()
    seed_summary_data(db)
    main_account = db.query(Account).filter(Account.display_name == "Main account").one()
    db.add(
        Transaction(
            account_id=main_account.id,
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
            raw_payload=None,
            imported_at=datetime(2026, 6, 19, 21, 0, tzinfo=timezone.utc),
        )
    )
    db.commit()

    summary = SummaryService(db=db).get_summary(month="2026-06", today=date(2026, 6, 20))

    # The seeded Mystery charge plus this one.
    assert summary["uncategorized_count"] == 2

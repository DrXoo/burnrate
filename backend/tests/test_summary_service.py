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
    assert summary["monthly_spending_amount"] == "285.00"
    assert summary["monthly_income_amount"] == "2000.00"
    assert summary["net_cash_flow_amount"] == "1715.00"
    assert summary["monthly_budget_amount"] == "400.00"
    assert summary["budgeted_spending_amount"] == "285.00"
    assert summary["unbudgeted_spending_amount"] == "0.00"
    assert summary["money_left_amount"] == "115.00"
    assert summary["uncategorized_count"] == 1
    assert summary["days_elapsed"] == 15
    assert summary["days_in_month"] == 30
    assert summary["average_daily_spend_amount"] == "19.00"
    # Budget-anchored projection: 285 spent + 15 remaining days x blended daily
    # (0.5*19.00 actual + 0.5*13.333 budget) = 527.50, so overspend = 527.50 - 400.
    assert summary["projected_month_end_spend_amount"] == "527.50"
    assert summary["projected_overspend_amount"] == "127.50"
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
    assert summary["monthly_spending_amount"] == "315.00"
    assert summary["budgeted_spending_amount"] == "285.00"
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

    # No budgets: variable spend is linearly extrapolated (285 over 15 days -> 570
    # for the full 30). Overspend is measured against budgeted categories, of which
    # there are none, so it stays at zero.
    assert summary["monthly_budget_amount"] == "0.00"
    assert summary["projected_month_end_spend_amount"] == "570.00"
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

    # Burn rate now reflects only variable spend (Food 140 booked + 25 pending, over
    # 15 days), not the lump.
    assert summary["average_daily_spend_amount"] == "11.00"
    # Planned variable pace: Food budget 300 / 30 days.
    assert summary["expected_daily_spend_amount"] == "10.00"
    # Variable slice projects 322.50 (165 + 15 x blended 10.50); fixed adds its
    # actual 120.
    assert summary["projected_month_end_spend_amount"] == "442.50"
    assert summary["projected_overspend_amount"] == "42.50"

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

    # Variable slice unchanged at 527.50; fixed Rent adds its 900 budgeted estimate.
    assert summary["projected_month_end_spend_amount"] == "1427.50"
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

    # The seeded month books 2000.00 of salary against 285.00 of spending (the
    # 25.00 pending snack included, because it is money already committed), so the
    # owner kept 1715.00 -- 85.8% of what came in, comfortably clear of the band.
    assert summary["savings_rate_percent"] == 85.8
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


def test_summary_service_reports_every_figure_of_the_seeded_month_to_the_cent() -> None:
    # A pin on every amount the summary reports, so a change here cannot restate one
    # of them unnoticed. Each is worked from the seed by hand -- 140 food + 120
    # utilities booked and a 25 pending snack, against 300 + 100 budgeted, with 2000
    # salary in, and the 100 transfer and the 20 uncategorized charge counting as
    # neither.
    #
    # The pending snack counts from this phase on: it is the one figure set this
    # ticket deliberately restates, because committed money the bank has not settled
    # yet is still gone. Income stays booked-only -- a credit the bank has not
    # settled is not money kept.
    #
    # Every seeded row carries a booking date, so this guards the figures and not
    # the Effective Date fallbacks: the chain always resolves on its first link
    # here. The value-date and import-date links have their own tests below.
    db = make_session()
    seed_summary_data(db)

    summary = SummaryService(db=db).get_summary(month="2026-06", today=date(2026, 6, 15))

    assert {key: summary[key] for key in sorted(summary) if key.endswith("_amount")} == {
        "average_daily_spend_amount": "19.00",
        "budgeted_spending_amount": "285.00",
        "current_balance_amount": "2000.00",
        "expected_daily_spend_amount": "13.33",
        "money_left_amount": "115.00",
        "monthly_budget_amount": "400.00",
        "monthly_income_amount": "2000.00",
        "monthly_spending_amount": "285.00",
        "net_cash_flow_amount": "1715.00",
        "pending_spend_amount": "25.00",
        "projected_month_end_spend_amount": "527.50",
        "projected_overspend_amount": "127.50",
        "unbudgeted_spending_amount": "0.00",
    }
    assert summary["uncategorized_count"] == 1
    assert summary["savings_rate_percent"] == 85.8
    assert [(row["category_name"], row["spent_amount"]) for row in summary["budget_usage"]] == [
        ("Utilities", "120.00"),
        ("Food", "165.00"),
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

    assert summary["monthly_spending_amount"] == "315.00"
    assert summary["budgeted_spending_amount"] == "315.00"
    food_row = next(row for row in summary["budget_usage"] if row["category_name"] == "Food")
    assert food_row["spent_amount"] == "195.00"


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


def test_summary_service_closes_december_on_the_first_of_january() -> None:
    # December is the only month whose window crosses a year, and the rollover lived
    # duplicated in two services with no test on either. A window that stayed in the
    # same year would end before it started and swallow the whole month.
    db = make_session()
    seed_summary_data(db)
    main_account = db.query(Account).filter(Account.display_name == "Main account").one()
    food = db.query(Category).filter(Category.name == "Food").one()
    for suffix, booking_date, amount in (
        ("new-years-eve", date(2026, 12, 31), "-40.00"),
        ("new-years-day", date(2027, 1, 1), "-25.00"),
    ):
        db.add(
            Transaction(
                account_id=main_account.id,
                enable_banking_transaction_id=f"tx-{suffix}",
                booking_date=booking_date,
                value_date=booking_date,
                amount=Decimal(amount),
                currency="EUR",
                description="Dinner",
                merchant_name="Restaurant",
                counterparty_name=None,
                direction="debit",
                status="booked",
                category_id=food.id,
                matched_rule_id=None,
                raw_payload=None,
                imported_at=datetime(booking_date.year, booking_date.month, booking_date.day, tzinfo=timezone.utc),
            )
        )
    db.commit()

    summary = SummaryService(db=db).get_summary(month="2026-12", today=date(2026, 12, 31))

    assert summary["days_in_month"] == 31
    # New Year's Eve counts, New Year's Day does not: the window ends at 2027-01-01.
    assert summary["monthly_spending_amount"] == "40.00"


def test_summary_service_counts_a_pending_charge_as_spend_this_month() -> None:
    # Last night's card payment is committed money the bank has not settled yet.
    # Counting it only once it books leaves every day's figure optimistic by exactly
    # the amount most likely to matter.
    db = make_session()
    seed_summary_data(db)

    summary = SummaryService(db=db).get_summary(month="2026-06", today=date(2026, 6, 15))

    # 140.00 booked groceries + 120.00 booked power bill + the 25.00 pending snack.
    assert summary["monthly_spending_amount"] == "285.00"
    assert summary["budgeted_spending_amount"] == "285.00"
    # Nothing fixed in the seeded month, so all 285.00 is variable: 285 / 15 days.
    assert summary["average_daily_spend_amount"] == "19.00"
    food_row = next(row for row in summary["budget_usage"] if row["category_name"] == "Food")
    assert food_row["spent_amount"] == "165.00"


def seed_fixed_rent_with_a_pending_hold(db: Session) -> None:
    """A fixed Rent budget of 900.00 whose only charge is a 1.00 pre-authorization."""
    main_account = db.query(Account).filter(Account.display_name == "Main account").one()
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
    db.add(
        Transaction(
            account_id=main_account.id,
            enable_banking_transaction_id="tx-rent-hold",
            booking_date=None,
            value_date=date(2026, 6, 13),
            amount=Decimal("-1.00"),
            currency="EUR",
            description="Rent pre-authorization",
            merchant_name="Landlord",
            counterparty_name=None,
            direction="debit",
            status="pending",
            category_id=rent.id,
            matched_rule_id=None,
            raw_payload=None,
            imported_at=datetime(2026, 6, 13, 8, 0, tzinfo=timezone.utc),
        )
    )
    db.commit()


def test_summary_service_keeps_a_fixed_budget_row_on_its_booked_spend() -> None:
    # A fixed commitment is judged by its estimate until it settles. A 1.00 hold on
    # the rent is not the rent being paid, so the row must still read as not yet
    # paid rather than as 1.00 of 900.00 spent.
    db = make_session()
    seed_summary_data(db)
    seed_fixed_rent_with_a_pending_hold(db)

    summary = SummaryService(db=db).get_summary(month="2026-06", today=date(2026, 6, 15))

    rent_row = next(row for row in summary["budget_usage"] if row["category_name"] == "Rent")
    assert rent_row["spent_amount"] == "0.00"
    assert rent_row["remaining_amount"] == "900.00"
    assert rent_row["status"] == "on_track"


def test_summary_service_projects_a_fixed_budget_at_its_estimate_when_only_a_hold_exists() -> None:
    # The step projection trusts actual spend over the estimate as soon as any spend
    # exists, so a 1.00 pre-authorization would otherwise convince the product that
    # 900.00 of rent will cost 1.00 this month.
    db = make_session()
    seed_summary_data(db)
    seed_fixed_rent_with_a_pending_hold(db)

    summary = SummaryService(db=db).get_summary(month="2026-06", today=date(2026, 6, 15))

    # Variable slice 527.50 as in the seeded month, plus Rent's 900.00 estimate.
    assert summary["projected_month_end_spend_amount"] == "1427.50"


def test_summary_service_keeps_a_hold_on_a_fixed_bill_out_of_the_variable_slice() -> None:
    # The trap this ticket exists to avoid: a total that counted the 1.00 rent hold
    # would hand it straight to the variable slice, which removes only booked fixed
    # spend -- and the variable slice is the one place a hold on a bill must never
    # land, because it would quietly shrink what the owner may spend today on
    # something else.
    db = make_session()
    seed_summary_data(db)
    seed_fixed_rent_with_a_pending_hold(db)

    summary = SummaryService(db=db).get_summary(month="2026-06", today=date(2026, 6, 15))

    # Variable spend is the 140.00 groceries and the 25.00 snack, over 15 days. The
    # rent hold is absent from it, while the pending snack is present.
    assert summary["average_daily_spend_amount"] == "19.00"
    # Nor does the hold reach the month's budget: the 900.00 estimate already stands
    # for the commitment, so counting a hold on top would charge the rent twice.
    assert summary["money_left_amount"] == "1015.00"


def test_summary_service_discloses_the_months_pending_spend() -> None:
    # The figures move without a transaction the owner can point at, because the bank
    # settles a card payment one to three days after they made it. The disclosed total
    # is the unsettled share of monthly spending, so 285.00 spent less 25.00 pending
    # leaves the 260.00 the bank has actually settled.
    db = make_session()
    seed_summary_data(db)
    seed_fixed_rent_with_a_pending_hold(db)

    summary = SummaryService(db=db).get_summary(month="2026-06", today=date(2026, 6, 15))

    # The 25.00 snack alone. The 1.00 rent hold is left out, because the total
    # discloses the pending spend the figures actually counted, and a hold on a fixed
    # bill counts towards none of them.
    assert summary["pending_spend_amount"] == "25.00"
    assert summary["monthly_spending_amount"] == "285.00"
    assert Decimal(summary["monthly_spending_amount"]) - Decimal(summary["pending_spend_amount"]) == Decimal(
        "260.00"
    )


def test_summary_service_reconciles_budgeted_spending_with_the_rows_it_prints() -> None:
    # The dashboard shows budgeted spending beside the per-category rows, so the two
    # have to be the same money. A fixed row reports booked spend only, which means
    # the total cannot count a hold the row is leaving out.
    db = make_session()
    seed_summary_data(db)
    seed_fixed_rent_with_a_pending_hold(db)

    summary = SummaryService(db=db).get_summary(month="2026-06", today=date(2026, 6, 15))

    # 140.00 groceries + 25.00 snack booked and pending in Food, 120.00 in Utilities,
    # and nothing yet in Rent.
    assert summary["budgeted_spending_amount"] == "285.00"
    assert Decimal(summary["budgeted_spending_amount"]) == sum(
        Decimal(row["spent_amount"]) for row in summary["budget_usage"]
    )


def test_summary_service_does_not_report_a_hold_on_a_fixed_bill_as_unbudgeted() -> None:
    # Rent has a budget, so a hold on it is not unbudgeted spend by any reading. The
    # disclosure is a figure the owner acts on -- Telegram prints "incl. X
    # unbudgeted" whenever it is non-zero -- so a hold must not appear there, and
    # monthly spending must not count what no budget-basis figure counts.
    db = make_session()
    seed_summary_data(db)
    seed_fixed_rent_with_a_pending_hold(db)

    summary = SummaryService(db=db).get_summary(month="2026-06", today=date(2026, 6, 15))

    assert summary["unbudgeted_spending_amount"] == "0.00"
    # 140.00 + 25.00 in Food and 120.00 in Utilities. The rent hold counts nowhere
    # until it books: a fixed commitment is judged by its estimate until it settles.
    assert summary["monthly_spending_amount"] == "285.00"

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


# Which month the owner is actually in, as the backend's own clock reads it. The
# dashboard labels a month's tense by comparing the month on screen to this, because
# only this side knows APP_TIMEZONE: a browser deriving the current month from UTC
# disagrees with it for part of every month-end, in whichever direction the offset
# points, and then captions a month with the wrong tense.
#
# timezone, instant, month asked for, the month the owner is in, what the owner is doing
CIVIL_MONTH_EXAMPLES = [
    (
        "Pacific/Honolulu",
        datetime(2026, 7, 1, 2, 0, tzinfo=timezone.utc),
        "2026-07",
        "2026-06",
        "opening a month that has not started while UTC has already turned",
    ),
    (
        "Europe/Madrid",
        datetime(2026, 6, 30, 23, 0, tzinfo=timezone.utc),
        "2026-06",
        "2026-07",
        "looking back at a month that just closed while UTC is still in it",
    ),
]


@pytest.mark.parametrize(
    ("timezone_name", "instant", "month", "current_month", "_what_the_owner_is_doing"),
    CIVIL_MONTH_EXAMPLES,
)
def test_summary_service_names_the_month_the_owner_is_in(
    timezone_name: str,
    instant: datetime,
    month: str,
    current_month: str,
    _what_the_owner_is_doing: str,
) -> None:
    db = make_session()
    seed_summary_data(db)
    service = SummaryService(db=db, timezone_name=timezone_name, clock=lambda: instant)

    summary = service.get_summary(month=month)

    assert summary["month"] == month
    assert summary["current_month"] == current_month
    assert summary["safe_to_spend_status"] == "not_current_month"


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
    # The headline arrives with this ticket: the 115.00 left of the 400.00 budgeted
    # has to cover the 15th and the fifteen days after it, so 7.19 a day. Nothing in
    # the month is fixed, so there is no estimate to overshoot and no overrun.
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
        "fixed_overrun_amount": "0.00",
        "money_left_amount": "115.00",
        "monthly_budget_amount": "400.00",
        "monthly_income_amount": "2000.00",
        "monthly_spending_amount": "285.00",
        "net_cash_flow_amount": "1715.00",
        "pending_spend_amount": "25.00",
        "projected_month_end_spend_amount": "527.50",
        "projected_overspend_amount": "127.50",
        "safe_to_spend_today_amount": "7.19",
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


def test_summary_service_reports_what_the_owner_can_spend_today() -> None:
    # The seeded month budgets 400.00, none of it fixed, and 285.00 of it has gone
    # -- 140.00 of groceries, the 120.00 power bill and the 25.00 snack the bank has
    # not settled yet. That leaves 115.00 to cover the 15th and the fifteen days
    # after it, so 115 over 16 days is 7.1875 a day.
    #
    # On plan, half a month in, 200.00 of the 400.00 would still be there. 115.00 of
    # 200.00 is 0.575 -- past the 0.85 the gauge stays green at, not yet down to the
    # 0.5 that calls the month lost.
    db = make_session()
    seed_summary_data(db)

    summary = SummaryService(db=db).get_summary(month="2026-06", today=date(2026, 6, 15))

    assert summary["safe_to_spend_today_amount"] == "7.19"
    assert summary["safe_to_spend_status"] == "watch"
    assert summary["fixed_overrun_amount"] == "0.00"


def seed_fixed_rent_charged_over_its_estimate(db: Session) -> None:
    """A fixed Rent budget of 900.00 whose charge booked at 950.00."""
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
            enable_banking_transaction_id="tx-rent-charged",
            booking_date=date(2026, 6, 2),
            value_date=date(2026, 6, 2),
            amount=Decimal("-950.00"),
            currency="EUR",
            description="Rent",
            merchant_name="Landlord",
            counterparty_name=None,
            direction="debit",
            status="booked",
            category_id=rent.id,
            matched_rule_id=None,
            raw_payload=None,
            imported_at=datetime(2026, 6, 2, 8, 0, tzinfo=timezone.utc),
        )
    )
    db.commit()


def test_summary_service_takes_a_fixed_budget_overshoot_out_of_the_allowance() -> None:
    # The rent was estimated at 900.00 and charged at 950.00. That 50.00 is already
    # gone, and the system knows it -- the step projection trusts the actual charge --
    # so leaving it in the daily spending money would keep the allowance 50.00 too
    # generous for the rest of the month.
    #
    # The variable budget is still 400.00 with 285.00 spent, so without the overrun
    # the owner would read 7.19 a day. With it, 65.00 covers 16 days: 4.06, and
    # 65.00 against the 200.00 that would be left on plan is 0.325 -- past the 0.5
    # where the month stops being recoverable at the budgeted pace.
    db = make_session()
    seed_summary_data(db)
    seed_fixed_rent_charged_over_its_estimate(db)

    summary = SummaryService(db=db).get_summary(month="2026-06", today=date(2026, 6, 15))

    assert summary["fixed_overrun_amount"] == "50.00"
    assert summary["safe_to_spend_today_amount"] == "4.06"
    assert summary["safe_to_spend_status"] == "over"


def test_summary_service_does_not_deepen_a_fixed_overrun_with_a_hold() -> None:
    # The power bill is a fixed commitment: estimated at 100.00 and booked at 120.00,
    # so 20.00 is already gone and comes out of the allowance. A further 30.00 the
    # bank is only holding is not money gone -- a fixed category is judged by what
    # has settled -- so the overrun stays at 20.00 rather than growing to 50.00 and
    # quietly taking another 1.88 a day off what the owner may spend.
    #
    # The variable slice is Food alone: 300.00 budgeted, 165.00 committed, less the
    # 20.00 overrun leaves 115.00 over 16 days. Against the 150.00 that would be left
    # on plan, 115.00 is 0.767.
    db = make_session()
    seed_summary_data(db)
    utilities = db.query(Category).filter(Category.name == "Utilities").one()
    db.query(Budget).filter(Budget.category_id == utilities.id).update({"is_fixed": True})
    main_account = db.query(Account).filter(Account.display_name == "Main account").one()
    db.add(
        Transaction(
            account_id=main_account.id,
            enable_banking_transaction_id="tx-utilities-hold",
            booking_date=None,
            value_date=date(2026, 6, 14),
            amount=Decimal("-30.00"),
            currency="EUR",
            description="Power top-up",
            merchant_name="Electricity",
            counterparty_name=None,
            direction="debit",
            status="pending",
            category_id=utilities.id,
            matched_rule_id=None,
            raw_payload=None,
            imported_at=datetime(2026, 6, 14, 8, 0, tzinfo=timezone.utc),
        )
    )
    db.commit()

    summary = SummaryService(db=db).get_summary(month="2026-06", today=date(2026, 6, 15))

    assert summary["fixed_overrun_amount"] == "20.00"
    assert summary["safe_to_spend_today_amount"] == "7.19"
    assert summary["safe_to_spend_status"] == "watch"


def test_summary_service_has_no_allowance_to_report_without_a_budget() -> None:
    # Nothing budgeted means there is nothing to divide. A 0.00 would tell the owner
    # they may spend nothing; the status tells them why the figure is missing instead,
    # so the dashboard can prompt them to set a budget.
    db = make_session()
    seed_summary_data(db)
    db.query(Budget).delete()
    db.commit()

    summary = SummaryService(db=db).get_summary(month="2026-06", today=date(2026, 6, 15))

    assert summary["safe_to_spend_today_amount"] is None
    assert summary["safe_to_spend_status"] == "no_budget"


# A month that is not the one today falls in. The budgets are active in both, so the
# only thing making the allowance meaningless is that "today" is somewhere else.
#
# month asked for, today, what the owner is doing
OTHER_MONTH_EXAMPLES = [
    ("2026-06", date(2026, 7, 10), "looking back at a finished month"),
    ("2026-07", date(2026, 6, 15), "looking ahead at a month not yet started"),
]


@pytest.mark.parametrize(("month", "today", "_what_the_owner_is_doing"), OTHER_MONTH_EXAMPLES)
def test_summary_service_has_no_allowance_to_report_outside_the_current_month(
    month: str,
    today: date,
    _what_the_owner_is_doing: str,
) -> None:
    db = make_session()
    seed_summary_data(db)

    summary = SummaryService(db=db).get_summary(month=month, today=today)

    assert summary["monthly_budget_amount"] == "400.00"
    assert summary["safe_to_spend_today_amount"] is None
    assert summary["safe_to_spend_status"] == "not_current_month"


def test_summary_service_counts_a_scheduled_payment_in_the_month_it_falls_due() -> None:
    # A standing order arrives as a hold carrying next month's value date and no
    # booking date, so the effective date files it in the month it is due. A month the
    # owner has not reached therefore already has spend in it, which is why nothing
    # reading this payload may claim an unstarted month is untouched.
    db = make_session()
    seed_summary_data(db)
    main_account = db.query(Account).filter(Account.display_name == "Main account").one()
    food = db.query(Category).filter(Category.name == "Food").one()
    db.add(
        Transaction(
            account_id=main_account.id,
            enable_banking_transaction_id="tx-standing-order",
            booking_date=None,
            value_date=date(2026, 7, 3),
            amount=Decimal("-80.00"),
            currency="EUR",
            description="Meal plan standing order",
            merchant_name="Market",
            counterparty_name=None,
            direction="debit",
            status="pending",
            category_id=food.id,
            matched_rule_id=None,
            raw_payload=None,
            imported_at=datetime(2026, 6, 15, 8, 0, tzinfo=timezone.utc),
        )
    )
    db.commit()

    summary = SummaryService(db=db).get_summary(month="2026-07", today=date(2026, 6, 15))

    # 400.00 budgeted against the one 80.00 charge that falls in July.
    assert summary["safe_to_spend_status"] == "not_current_month"
    assert summary["monthly_budget_amount"] == "400.00"
    assert summary["budgeted_spending_amount"] == "80.00"
    assert summary["pending_spend_amount"] == "80.00"
    assert summary["money_left_amount"] == "320.00"


def test_summary_service_discloses_a_scheduled_payment_no_budget_covers() -> None:
    # The same standing order, in a category nothing budgets for. No budget-basis figure
    # counts it, so money left reads the full budget and the only places the charge
    # surfaces are the month's spend and the unbudgeted disclosure. Anything saying what
    # a month holds has to read those, because the budgeted figure says 0.00 while
    # 80.00 of the owner's money is committed.
    db = make_session()
    seed_summary_data(db)
    main_account = db.query(Account).filter(Account.display_name == "Main account").one()
    hobbies = Category(name="Hobbies", type="expense", active=True)
    db.add(hobbies)
    db.flush()
    db.add(
        Transaction(
            account_id=main_account.id,
            enable_banking_transaction_id="tx-unbudgeted-standing-order",
            booking_date=None,
            value_date=date(2026, 7, 3),
            amount=Decimal("-80.00"),
            currency="EUR",
            description="Climbing gym standing order",
            merchant_name="Gym",
            counterparty_name=None,
            direction="debit",
            status="pending",
            category_id=hobbies.id,
            matched_rule_id=None,
            raw_payload=None,
            imported_at=datetime(2026, 6, 15, 8, 0, tzinfo=timezone.utc),
        )
    )
    db.commit()

    summary = SummaryService(db=db).get_summary(month="2026-07", today=date(2026, 6, 15))

    assert summary["safe_to_spend_status"] == "not_current_month"
    assert summary["monthly_spending_amount"] == "80.00"
    assert summary["unbudgeted_spending_amount"] == "80.00"
    assert summary["budgeted_spending_amount"] == "0.00"
    assert summary["money_left_amount"] == "400.00"


def seed_rent_with_two_budget_rows_in_one_month(db: Session) -> None:
    """A fixed Rent category holding two budget rows in June: 500.00, then 600.00.

    Seeded straight into the session because ``BudgetService`` refuses this shape --
    ``_validate_month_start`` forces a period to begin on the 1st of a month and
    ``_ensure_no_overlap`` rejects a second period touching an existing one. So this
    is a missing invariant in ``SummaryService`` rather than a live miscalculation,
    and the seam that can state it is this one.

    The charge books once, at 1100.00: exactly the two estimates together, so an
    owner in this state is precisely on budget.
    """
    main_account = db.query(Account).filter(Account.display_name == "Main account").one()
    rent = Category(name="Rent", type="expense", active=True)
    db.add(rent)
    db.flush()
    db.add_all(
        [
            Budget(
                category_id=rent.id,
                amount=Decimal("500.00"),
                currency="EUR",
                period_type="monthly",
                active_from=date(2026, 6, 1),
                active_to=date(2026, 6, 14),
                is_fixed=True,
            ),
            Budget(
                category_id=rent.id,
                amount=Decimal("600.00"),
                currency="EUR",
                period_type="monthly",
                active_from=date(2026, 6, 15),
                active_to=None,
                is_fixed=True,
            ),
        ]
    )
    db.add(
        Transaction(
            account_id=main_account.id,
            enable_banking_transaction_id="tx-rent-two-estimates",
            booking_date=date(2026, 6, 2),
            value_date=date(2026, 6, 2),
            amount=Decimal("-1100.00"),
            currency="EUR",
            description="Rent",
            merchant_name="Landlord",
            counterparty_name=None,
            direction="debit",
            status="booked",
            category_id=rent.id,
            matched_rule_id=None,
            raw_payload=None,
            imported_at=datetime(2026, 6, 2, 8, 0, tzinfo=timezone.utc),
        )
    )
    db.commit()


def test_summary_service_counts_a_fixed_commitment_once_when_its_category_has_two_budget_rows() -> None:
    # Rent is estimated at 500.00 and then 600.00 in the same month and the charge
    # books at 1100.00, so the owner is exactly on budget. Pairing each budget row
    # with the category's whole-month spend reads the commitment once per row: 600.00
    # over one estimate plus 500.00 over the other is 1100.00 of overrun invented out
    # of nothing, which zeroes the allowance and flags the month `over`.
    #
    # Folded to one commitment per category -- 1100.00 estimated, 1100.00 booked --
    # there is no overrun, and the variable slice is left alone: 400.00 budgeted with
    # 285.00 committed leaves 115.00 over 16 days, 7.19 a day, which is 0.575 of the
    # 200.00 that would be left on plan.
    db = make_session()
    seed_summary_data(db)
    seed_rent_with_two_budget_rows_in_one_month(db)

    summary = SummaryService(db=db).get_summary(month="2026-06", today=date(2026, 6, 15))

    assert summary["fixed_overrun_amount"] == "0.00"
    assert summary["safe_to_spend_today_amount"] == "7.19"
    assert summary["safe_to_spend_status"] == "watch"
    # The variable slice projects to 527.50, and the rent is added back as its step
    # projection -- once, not once per budget row.
    assert summary["projected_month_end_spend_amount"] == "1627.50"


def test_summary_service_prints_one_budget_row_per_category() -> None:
    # Two budget rows for Rent printed two Rent rows, each claiming the category's
    # whole 1100.00 against its own estimate: the same rent shown paid twice, at 220%
    # of one row and 183.3% of the other. One row per category, with the estimates
    # summed the way the monthly budget total already sums them.
    db = make_session()
    seed_summary_data(db)
    seed_rent_with_two_budget_rows_in_one_month(db)

    summary = SummaryService(db=db).get_summary(month="2026-06", today=date(2026, 6, 15))

    rent_rows = [row for row in summary["budget_usage"] if row["category_name"] == "Rent"]
    assert len(rent_rows) == 1
    assert rent_rows[0]["budget_amount"] == "1100.00"
    assert rent_rows[0]["spent_amount"] == "1100.00"
    assert rent_rows[0]["remaining_amount"] == "0.00"
    assert summary["monthly_budget_amount"] == "1500.00"


def test_summary_service_keeps_a_category_fixed_when_only_one_of_its_rows_says_so() -> None:
    # Utilities is budgeted 100.00 from the 1st and 80.00 from the 15th, and only the
    # later row is marked fixed. Folding the two has to decide the category's slice,
    # and reading the flag off whichever row happens to sort first would hand that
    # decision to SQL: the bill the owner marked fixed would be paced day by day, its
    # 120.00 charge would land in the variable slice, and the whole 180.00 estimate
    # would be offered as day-to-day spending money.
    #
    # Fixed, so the variable slice is Food alone: 300.00 budgeted, 165.00 committed,
    # 135.00 over 16 days is 8.44 a day -- 0.9 of the 150.00 that would be left on plan.
    db = make_session()
    seed_summary_data(db)
    utilities = db.query(Category).filter(Category.name == "Utilities").one()
    db.add(
        Budget(
            category_id=utilities.id,
            amount=Decimal("80.00"),
            currency="EUR",
            period_type="monthly",
            active_from=date(2026, 6, 15),
            active_to=None,
            is_fixed=True,
        )
    )
    db.commit()

    summary = SummaryService(db=db).get_summary(month="2026-06", today=date(2026, 6, 15))

    assert summary["monthly_budget_amount"] == "480.00"
    assert summary["safe_to_spend_today_amount"] == "8.44"
    assert summary["safe_to_spend_status"] == "on_track"
    usage = {row["category_name"]: row for row in summary["budget_usage"]}
    assert usage["Utilities"]["is_fixed"] is True
    assert usage["Utilities"]["budget_amount"] == "180.00"
    assert usage["Utilities"]["spent_amount"] == "120.00"


def ignored_transaction(
    db: Session,
    *,
    external_id: str,
    amount: Decimal,
    category_name: str,
    description: str,
    status: str = "booked",
) -> None:
    """A transaction the owner marked Ignored that still holds a category.

    ``GLOSSARY.md`` defines Ignored as excluded from every metric, and the figures
    used to get that for free: excluding a row cleared its category too, and rows
    with no category fell out of the spend queries anyway. So any path that left a
    category on an excluded row put the money back -- the rule engine was one, a
    manual fix-up or a backfill is the next. See ``db/dispositions.py`` for why the
    predicate is now stated. The state is seeded directly because what is under test
    is the query, not how the row got this way.

    A pending row carries no booking date, as a real hold does not, so its month
    membership resolves through the Effective Date chain.
    """
    main_account = db.query(Account).filter(Account.display_name == "Main account").one()
    category = db.query(Category).filter(Category.name == category_name).one()
    db.add(
        Transaction(
            account_id=main_account.id,
            enable_banking_transaction_id=external_id,
            booking_date=None if status == "pending" else date(2026, 6, 13),
            value_date=date(2026, 6, 13),
            amount=amount,
            currency="EUR",
            description=description,
            merchant_name="Ignored merchant",
            counterparty_name=None,
            direction="debit" if amount < 0 else "credit",
            status=status,
            category_id=category.id,
            matched_rule_id=None,
            raw_payload=None,
            imported_at=datetime(2026, 6, 13, 8, 0, tzinfo=timezone.utc),
            excluded_at=datetime(2026, 6, 13, 9, 0, tzinfo=timezone.utc),
        )
    )
    db.commit()


def test_summary_service_keeps_an_ignored_charge_out_of_every_spend_figure() -> None:
    db = make_session()
    seed_summary_data(db)
    ignored_transaction(
        db,
        external_id="tx-ignored-food",
        amount=Decimal("-60.00"),
        category_name="Food",
        description="Refunded in cash",
    )

    summary = SummaryService(db=db).get_summary(month="2026-06", today=date(2026, 6, 15))

    # The seeded month's figures, unchanged: 140.00 groceries + 120.00 power bill +
    # the 25.00 pending snack. The 60.00 the owner ignored reaches none of them.
    assert summary["monthly_spending_amount"] == "285.00"
    assert summary["budgeted_spending_amount"] == "285.00"
    assert summary["average_daily_spend_amount"] == "19.00"
    food_row = next(row for row in summary["budget_usage"] if row["category_name"] == "Food")
    assert food_row["spent_amount"] == "165.00"
    # The allowance is where the owner feels it: counting the 60.00 would drop it to
    # 3.44 and flip the month to over, on money they had already set aside.
    assert summary["safe_to_spend_today_amount"] == "7.19"
    assert summary["safe_to_spend_status"] == "watch"


def test_summary_service_keeps_an_ignored_hold_out_of_the_pending_slice() -> None:
    """An Ignored row is still Ignored while the bank is only holding it.

    Pending spend counts in the variable slice and is reported on its own (see
    ``docs/adr/0003-pending-spend-is-load-bearing.md``), so it is a second way into
    the allowance that a booked-only test would not reach.
    """
    db = make_session()
    seed_summary_data(db)
    ignored_transaction(
        db,
        external_id="tx-ignored-hold",
        amount=Decimal("-45.00"),
        category_name="Food",
        description="Hold the merchant released",
        status="pending",
    )

    summary = SummaryService(db=db).get_summary(month="2026-06", today=date(2026, 6, 15))

    # The seeded month's only hold is the 25.00 snack.
    assert summary["pending_spend_amount"] == "25.00"
    assert summary["monthly_spending_amount"] == "285.00"
    assert summary["safe_to_spend_today_amount"] == "7.19"
    food_row = next(row for row in summary["budget_usage"] if row["category_name"] == "Food")
    assert food_row["spent_amount"] == "165.00"


def test_summary_service_keeps_an_ignored_credit_out_of_the_income_figure() -> None:
    db = make_session()
    seed_summary_data(db)
    ignored_transaction(
        db,
        external_id="tx-ignored-income",
        amount=Decimal("500.00"),
        category_name="Salary",
        description="Reimbursement the owner does not count as income",
    )

    summary = SummaryService(db=db).get_summary(month="2026-06", today=date(2026, 6, 15))

    # The seeded month's only income is the 2000.00 salary; net cash flow is that
    # less the 285.00 spent. An ignored credit inflates both if the query lets it.
    assert summary["monthly_income_amount"] == "2000.00"
    assert summary["net_cash_flow_amount"] == "1715.00"

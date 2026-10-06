from __future__ import annotations

from decimal import Decimal

import pytest

from burnrate.domain.metrics import (
    FixedCommitment,
    budget_usage_status,
    fixed_overrun,
    safe_to_spend_today,
    savings_verdict,
)


# Worked examples for the budget-usage bands. Each row is a budget the owner set,
# what they have spent against it, and the verdict they should read -- the
# utilization is the figure the dashboard already shows beside the row.
#
# budget, spent, utilization shown, verdict
BUDGET_USAGE_EXAMPLES = [
    ("300.00", "100.00", "33.3", "on_track"),
    ("300.00", "252.00", "84.0", "on_track"),
    ("300.00", "255.00", "85.0", "watch"),
    ("100.00", "100.00", "100.0", "watch"),
    ("100.00", "120.00", "120.0", "over"),
]


@pytest.mark.parametrize(
    ("budget", "spent", "utilization_percent", "expected_status"),
    BUDGET_USAGE_EXAMPLES,
)
def test_budget_usage_status_reads_the_band_the_owner_is_in(
    budget: str,
    spent: str,
    utilization_percent: str,
    expected_status: str,
) -> None:
    status = budget_usage_status(
        remaining_amount=Decimal(budget) - Decimal(spent),
        utilization_percent=Decimal(utilization_percent),
    )

    assert status == expected_status


# Worked examples for the savings bands. Each row is a month's income and its net
# cash flow -- what the owner kept -- with the rate the dashboard should print and
# the verdict it should colour. The rates are written out rather than derived:
# 1740 of 2000 is 87% of income kept, 150 of 3000 is 5%, 1000 of 3000 is a third.
#
# income, net cash flow, rate shown, verdict
SAVINGS_EXAMPLES = [
    ("2000.00", "1740.00", 87.0, "on_track"),
    ("3000.00", "1000.00", 33.3, "on_track"),
    ("2500.00", "250.00", 10.0, "on_track"),
    ("3000.00", "150.00", 5.0, "watch"),
    ("2000.00", "0.00", 0.0, "watch"),
    ("1800.00", "-200.00", -11.1, "over"),
    ("0.00", "-50.00", 0.0, "over"),
    # A month with no income yet -- the 1st, before salary books -- has no share of
    # income to be thin, so it is not a warning. Spending it into the red still is.
    ("0.00", "0.00", 0.0, "on_track"),
    ("0.00", "50.00", 0.0, "on_track"),
]


@pytest.mark.parametrize(
    ("income", "net_cash_flow", "expected_rate_percent", "expected_status"),
    SAVINGS_EXAMPLES,
)
def test_savings_rate_and_status_read_the_share_of_income_kept(
    income: str,
    net_cash_flow: str,
    expected_rate_percent: float,
    expected_status: str,
) -> None:
    verdict = savings_verdict(net_cash_flow=Decimal(net_cash_flow), income=Decimal(income))

    assert float(verdict.rate_percent) == expected_rate_percent
    assert verdict.status == expected_status


# Worked examples for the fixed overrun. Each row is the month's fixed budgets as
# (budgeted estimate, what has actually booked) pairs, and the overrun the owner
# should be charged against their daily allowance. Money already gone.
#
# The third row is the one that matters: rent overshot by 50 while utilities came
# in 20 under, and the answer is 50 rather than 30 -- an underrun on one category
# is not money available to fund an overrun on another.
#
# fixed budgets as (budgeted, booked), overrun
FIXED_OVERRUN_EXAMPLES = [
    ([], "0.00"),
    ([("800.00", "0.00")], "0.00"),
    ([("800.00", "850.00"), ("100.00", "80.00")], "50.00"),
    ([("800.00", "850.00"), ("100.00", "130.00")], "80.00"),
    ([("800.00", "780.00")], "0.00"),
    ([("800.00", "800.00")], "0.00"),
]


@pytest.mark.parametrize(("fixed_budgets", "expected_overrun"), FIXED_OVERRUN_EXAMPLES)
def test_fixed_overrun_sums_what_each_fixed_budget_overshot_by(
    fixed_budgets: list[tuple[str, str]],
    expected_overrun: str,
) -> None:
    overrun = fixed_overrun(
        commitments=[
            FixedCommitment(budgeted=Decimal(budgeted), booked=Decimal(booked))
            for budgeted, booked in fixed_budgets
        ]
    )

    assert overrun == Decimal(expected_overrun)


def test_safe_to_spend_today_spreads_what_is_left_over_the_days_left_counting_today() -> None:
    # Mid-June: a 300.00 variable budget, 150.00 of it spent, and the 15th has
    # started. Sixteen days still have to be paid for -- the 15th among them,
    # because the owner is asking what they may spend today -- so 150.00 has to
    # cover 16 days. 150 / 16 is 9.375, a third of a cent over 9.37.
    verdict = safe_to_spend_today(
        variable_budget_total=Decimal("300.00"),
        variable_budgeted_spend=Decimal("150.00"),
        fixed_overrun=Decimal("0.00"),
        days_in_month=30,
        days_elapsed=15,
        is_current_month=True,
    )

    assert verdict.amount == Decimal("9.38")


def test_safe_to_spend_today_charges_the_owner_for_a_fixed_budget_that_overshot() -> None:
    # The same mid-June month, but the rent came in 50.00 over its estimate. That
    # 50.00 is already gone, so the 150.00 that looked spendable is really 100.00,
    # and the allowance steps down from 9.38 to 100 / 16 = 6.25.
    verdict = safe_to_spend_today(
        variable_budget_total=Decimal("300.00"),
        variable_budgeted_spend=Decimal("150.00"),
        fixed_overrun=Decimal("50.00"),
        days_in_month=30,
        days_elapsed=15,
        is_current_month=True,
    )

    assert verdict.amount == Decimal("6.25")


# An overspent month has nothing left to spread, and a minus figure divided over
# the days left is not an instruction the owner can act on. Both routes into the
# red are here: spending past the budget, and a fixed budget overshooting far
# enough to swallow what was left. Unclamped, the first reads -1.88 a day.
#
# variable budget, variable spend, fixed overrun
NOTHING_LEFT_EXAMPLES = [
    ("300.00", "330.00", "0.00"),
    ("300.00", "280.00", "50.00"),
    ("300.00", "300.00", "0.00"),
]


@pytest.mark.parametrize(
    ("variable_budget_total", "variable_budgeted_spend", "overrun"),
    NOTHING_LEFT_EXAMPLES,
)
def test_safe_to_spend_today_is_never_negative(
    variable_budget_total: str,
    variable_budgeted_spend: str,
    overrun: str,
) -> None:
    verdict = safe_to_spend_today(
        variable_budget_total=Decimal(variable_budget_total),
        variable_budgeted_spend=Decimal(variable_budgeted_spend),
        fixed_overrun=Decimal(overrun),
        days_in_month=30,
        days_elapsed=15,
        is_current_month=True,
    )

    assert verdict.amount == Decimal("0.00")


# The policy table. A 30-day month with a 300.00 variable budget -- a round 10.00
# a day of plan -- read on the four days that matter, with what the owner has
# spent by then. Every figure is worked by hand from the two divisions the metric
# is made of, never recomputed the way the code computes them.
#
# On-Plan Remaining is what would be left had spend tracked the budget exactly:
# 10.00 for every day of the month still to come. So it is 290.00 on the 1st,
# 150.00 on the 15th, 50.00 on the 25th and 10.00 on the 29th, and the ratio of
# what is actually left to that figure sits at 1.0 on every one of those days
# when spend is on plan. That is the whole point of the comparator: the first row
# of each group is the same verdict on every day of the month.
#
# The day-29 on-plan row is the regression. Judged against the planned daily pace
# of 10.00 instead, 5.00 a day reads as a ratio of 0.5 -- "over" -- for an owner
# who has done nothing wrong, every month, in the last week. See
# docs/adr/0002-safe-to-spend-today-definition.md.
#
# The two 15th rows at 7.97 and 4.69 sit exactly on the band edges (0.85 and 0.5)
# and belong to the gentler side of each, so moving either threshold moves them.
#
# day, variable spend, allowance, verdict
SAFE_TO_SPEND_BANDS = [
    (1, "10.00", "9.67", "on_track"),
    (1, "100.00", "6.67", "watch"),
    (1, "200.00", "3.33", "over"),
    (15, "150.00", "9.38", "on_track"),
    (15, "172.50", "7.97", "on_track"),
    (15, "180.00", "7.50", "watch"),
    (15, "225.00", "4.69", "watch"),
    (15, "240.00", "3.75", "over"),
    (25, "250.00", "8.33", "on_track"),
    (25, "265.00", "5.83", "watch"),
    (25, "280.00", "3.33", "over"),
    (29, "290.00", "5.00", "on_track"),
    (29, "294.00", "3.00", "watch"),
    (29, "296.00", "2.00", "over"),
]


@pytest.mark.parametrize(
    ("days_elapsed", "variable_budgeted_spend", "expected_amount", "expected_status"),
    SAFE_TO_SPEND_BANDS,
)
def test_safe_to_spend_today_reads_the_band_the_month_is_in(
    days_elapsed: int,
    variable_budgeted_spend: str,
    expected_amount: str,
    expected_status: str,
) -> None:
    verdict = safe_to_spend_today(
        variable_budget_total=Decimal("300.00"),
        variable_budgeted_spend=Decimal(variable_budgeted_spend),
        fixed_overrun=Decimal("0.00"),
        days_in_month=30,
        days_elapsed=days_elapsed,
        is_current_month=True,
    )

    assert verdict.amount == Decimal(expected_amount)
    assert verdict.status == expected_status


# The last day of the month. One day left to cover, so today's allowance is simply
# everything still left -- the day count including today is what makes that fall
# out rather than needing a case of its own.
#
# On-Plan Remaining is zero here, because a month on plan has spent its budget by
# the time it ends, so there is no ratio to band and the guard decides instead:
# anything left reads on-track, and nothing left reads over. A budget spent to the
# cent therefore pairs a 0.00 allowance with "over", which is the reading the zero
# amount already carries -- budgets exist, the month is current, they are used up.
#
# variable spend, allowance, verdict
LAST_DAY_EXAMPLES = [
    ("280.00", "20.00", "on_track"),
    ("299.99", "0.01", "on_track"),
    ("300.00", "0.00", "over"),
    ("315.00", "0.00", "over"),
]


@pytest.mark.parametrize(
    ("variable_budgeted_spend", "expected_amount", "expected_status"),
    LAST_DAY_EXAMPLES,
)
def test_safe_to_spend_today_resolves_the_last_day_of_the_month(
    variable_budgeted_spend: str,
    expected_amount: str,
    expected_status: str,
) -> None:
    verdict = safe_to_spend_today(
        variable_budget_total=Decimal("300.00"),
        variable_budgeted_spend=Decimal(variable_budgeted_spend),
        fixed_overrun=Decimal("0.00"),
        days_in_month=30,
        days_elapsed=30,
        is_current_month=True,
    )

    assert verdict.amount == Decimal(expected_amount)
    assert verdict.status == expected_status


# The two cases with no allowance to report, where the status carries the reason
# and the amount is null. A null rather than a zero is what lets a zero mean one
# thing only: budgets exist, the month is current, and they are used up.
#
# A month whose budgets are all fixed has a variable total of zero and so lands in
# the first case -- there is no slice for a daily allowance to draw on, and
# printing 0.00 would tell the owner they may spend nothing when the truth is that
# nothing has been budgeted to spend.
#
# When both hold, no-budget wins. It is the more useful of the two: it says what
# the owner can do about it, while telling them a budgetless month finished
# against a plan it never had would say nothing at all.
#
# variable budget, is current month, verdict
UNDEFINED_EXAMPLES = [
    ("0.00", True, "no_budget"),
    ("300.00", False, "not_current_month"),
    ("0.00", False, "no_budget"),
]


@pytest.mark.parametrize(
    ("variable_budget_total", "is_current_month", "expected_status"),
    UNDEFINED_EXAMPLES,
)
def test_safe_to_spend_today_has_no_amount_when_it_has_no_meaning(
    variable_budget_total: str,
    is_current_month: bool,
    expected_status: str,
) -> None:
    verdict = safe_to_spend_today(
        variable_budget_total=Decimal(variable_budget_total),
        variable_budgeted_spend=Decimal("150.00"),
        fixed_overrun=Decimal("0.00"),
        days_in_month=30,
        days_elapsed=15,
        is_current_month=is_current_month,
    )

    assert verdict.amount is None
    assert verdict.status == expected_status

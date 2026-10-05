from __future__ import annotations

from decimal import Decimal

import pytest

from burnrate.domain.metrics import budget_usage_status, savings_verdict


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

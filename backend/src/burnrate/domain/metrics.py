"""Metric policy: the thresholds and bands BurnRate judges a month by.

Pure functions over primitives. Nothing here opens a database session or imports
the ORM, so the rules can be read and tested as a table of worked examples
rather than through a fixture. The services query; this module decides. See
``docs/adr/0001-domain-module-for-metric-policy.md``.
"""

from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal
from typing import Literal

MetricStatus = Literal["on_track", "watch", "over"]
"""The one status vocabulary. Every metric bands into these three words."""

BUDGET_USAGE_WATCH_PERCENT = Decimal("85.0")
SAVINGS_WATCH_PERCENT = Decimal("10.0")


def budget_usage_status(*, remaining_amount: Decimal, utilization_percent: Decimal) -> MetricStatus:
    """Band one category's budget."""
    if remaining_amount < 0:
        return "over"
    if utilization_percent >= BUDGET_USAGE_WATCH_PERCENT:
        return "watch"
    return "on_track"


@dataclass(frozen=True)
class SavingsVerdict:
    """What the owner kept this month, and how that reads."""

    rate_percent: Decimal
    status: MetricStatus


def savings_verdict(*, net_cash_flow: Decimal, income: Decimal) -> SavingsVerdict:
    """Judge the share of this month's income the owner kept.

    The rate is derived once and the band is read off that same rounded figure, so
    the number an interface prints and the colour it prints it in cannot disagree.

    Spending outran income, so nothing was banked: ``over``. Under a tenth of
    income kept is a thin margin: ``watch``. A month with no income at all has no
    share to report and no thin margin to warn about, so it reads ``on_track``
    until something is actually overspent.
    """
    rate_percent = _savings_rate_percent(net_cash_flow=net_cash_flow, income=income)
    status = _savings_status(
        net_cash_flow=net_cash_flow,
        income=income,
        rate_percent=rate_percent,
    )
    return SavingsVerdict(rate_percent=rate_percent, status=status)


def _savings_rate_percent(*, net_cash_flow: Decimal, income: Decimal) -> Decimal:
    if income <= 0:
        return Decimal("0.0")
    return (net_cash_flow / income * Decimal("100.0")).quantize(Decimal("0.1"))


def _savings_status(
    *,
    net_cash_flow: Decimal,
    income: Decimal,
    rate_percent: Decimal,
) -> MetricStatus:
    if net_cash_flow < 0:
        return "over"
    if income <= 0:
        # Nothing has come in yet, so there is no share of income to be thin. A
        # salaried owner is in this state every month until payday, and an amber
        # gauge every month until payday is a warning they would learn to ignore.
        return "on_track"
    if rate_percent < SAVINGS_WATCH_PERCENT:
        return "watch"
    return "on_track"

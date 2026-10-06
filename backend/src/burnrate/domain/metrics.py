"""Metric policy: the thresholds and bands BurnRate judges a month by.

Pure functions over primitives. Nothing here opens a database session or imports
the ORM, so the rules can be read and tested as a table of worked examples
rather than through a fixture. The services query; this module decides. See
``docs/adr/0001-domain-module-for-metric-policy.md``.
"""

from __future__ import annotations

from collections.abc import Iterable
from dataclasses import dataclass
from decimal import Decimal
from typing import Literal

MetricStatus = Literal["on_track", "watch", "over"]
"""The one status vocabulary. Every metric bands into these three words."""

BUDGET_USAGE_WATCH_PERCENT = Decimal("85.0")
SAVINGS_WATCH_PERCENT = Decimal("10.0")
SAFE_TO_SPEND_WATCH_RATIO = Decimal("0.85")
SAFE_TO_SPEND_OVER_RATIO = Decimal("0.5")


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


@dataclass(frozen=True)
class FixedCommitment:
    """One fixed budget and what the bank has actually settled against it."""

    budgeted: Decimal
    booked: Decimal


def fixed_overrun(*, commitments: Iterable[FixedCommitment]) -> Decimal:
    """What the month's fixed commitments have overshot their estimates by.

    Summed per commitment, so an underrun on one fixed category cannot fund an
    overrun on another: a rent charge 50 over its estimate is 50 already gone,
    whatever the utility bill came in under.

    ``booked`` must be the category's settled spend. A pending hold on a bill is
    not the bill being paid, so it reaches this figure only once it books.
    """
    return sum(
        (max(Decimal("0.00"), commitment.booked - commitment.budgeted) for commitment in commitments),
        start=Decimal("0.00"),
    ).quantize(Decimal("0.01"))


SafeToSpendStatus = Literal["no_budget", "not_current_month", "on_track", "watch", "over"]
"""Why the allowance reads as it does. The amount is null for the first two."""


@dataclass(frozen=True)
class SafeToSpendVerdict:
    """What the owner may spend today, and how that reads."""

    amount: Decimal | None
    status: SafeToSpendStatus


def safe_to_spend_today(
    *,
    variable_budget_total: Decimal,
    variable_budgeted_spend: Decimal,
    fixed_overrun: Decimal,
    days_in_month: int,
    days_elapsed: int,
    is_current_month: bool,
) -> SafeToSpendVerdict:
    """What the owner can spend today without putting the month out of reach.

    The day count includes today, so the last day of the month resolves to one day
    to cover and needs no special case. See
    ``docs/adr/0002-safe-to-spend-today-definition.md``.
    """
    if variable_budget_total <= 0:
        # Nothing has been budgeted for day-to-day spend, so there is no allowance to
        # report. A zero would read as "you may spend nothing", which is a different
        # and untrue claim; the owner needs to be told to set a budget instead. A
        # month budgeted entirely to fixed commitments lands here too.
        return SafeToSpendVerdict(amount=None, status="no_budget")
    if not is_current_month:
        # "Today" is not in the month being asked about, so the metric has no
        # meaning. What a past month finished at, or a future one plans, is a
        # different figure and the caller already has it.
        return SafeToSpendVerdict(amount=None, status="not_current_month")

    remaining = variable_budget_total - variable_budgeted_spend - fixed_overrun
    days_remaining = days_in_month - days_elapsed + 1
    spendable = max(Decimal("0.00"), remaining)
    amount = (spendable / Decimal(days_remaining)).quantize(Decimal("0.01"))
    return SafeToSpendVerdict(
        amount=amount,
        status=_safe_to_spend_status(
            remaining=remaining,
            on_plan_remaining=_on_plan_remaining(
                variable_budget_total=variable_budget_total,
                days_in_month=days_in_month,
                days_elapsed=days_elapsed,
            ),
        ),
    )


def _on_plan_remaining(
    *,
    variable_budget_total: Decimal,
    days_in_month: int,
    days_elapsed: int,
) -> Decimal:
    """What would be left of the variable budget had spend tracked the budget exactly."""
    return variable_budget_total * Decimal(days_in_month - days_elapsed) / Decimal(days_in_month)


def _safe_to_spend_status(*, remaining: Decimal, on_plan_remaining: Decimal) -> SafeToSpendStatus:
    """Band what is left against what would be left on plan.

    The comparator is deliberately not the planned daily pace. On-plan spend puts
    this ratio at exactly 1.0 on every day of the month, so the bands mean the same
    thing on the 29th as on the 1st; against the daily pace they would read as a
    warning in the last week of every month for an owner doing nothing wrong.

    The unclamped remainder is banded, so an overspent month reads ``over`` rather
    than sharing the clamped zero with a month that merely finished its budget.
    """
    if on_plan_remaining == 0:
        # The last day of the month: a month on plan has spent its budget by now, so
        # there is no plan left to measure against. Anything still there is spendable
        # today; nothing there means it is used up.
        return "on_track" if remaining > 0 else "over"
    ratio = remaining / on_plan_remaining
    if ratio >= SAFE_TO_SPEND_WATCH_RATIO:
        return "on_track"
    if ratio >= SAFE_TO_SPEND_OVER_RATIO:
        return "watch"
    return "over"

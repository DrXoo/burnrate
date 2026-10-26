"""Baseline policy: how BurnRate decides what is normal for the owner.

Pure functions over primitives, like ``burnrate.domain.metrics`` and for the same
reason (see ``docs/adr/0001-domain-module-for-metric-policy.md``). A sibling of
that module rather than an extension of it: ``metrics`` judges one month against
the budgets the owner set, while this module judges a series of months against
each other, so its inputs are a series rather than a month's figures.
"""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass
from datetime import date, timedelta
from decimal import Decimal
from typing import Literal

BaselineStatus = Literal["ok", "insufficient_history", "month_not_started"]
"""Whether a comparison is offered, and if not, why not.

A month that has not started has no outcome to compare, however much history sits
behind it, so the reason is named here rather than left to be inferred from an
empty list or cross-referenced against the allowance's own tense. That is the
amendment ADR-0002 records: a state each client derives is a state each client can
derive differently.
"""

BaselineComparisonStatus = Literal["no_baseline", "below", "in_line", "above", "anomalous"]
"""One verdict per figure, so that no interface bands a comparison itself.

Five values rather than the three ``MetricStatus`` uses, because this judgement
answers two questions at once: which side of normal the figure is, and whether
that is worth raising. Only ``anomalous`` is a warning.
"""

_CENTS = Decimal("0.01")

BASELINE_COVERAGE_FLOOR_PERCENT = Decimal("5.0")
"""The most of a month's outgoing money that may be unclassified, as a percent.

Loose enough that one forgotten transaction does not disqualify a month, tight
enough that the bias it admits stays under the real month-to-month variation in
the owner's clean months, which is about 12%.
"""

BASELINE_IN_LINE_TOLERANCE_PERCENT = Decimal("15.0")
"""How far either side of the baseline still reads as a normal month.

Taken from the owner's own variation across clean months, which spans about 12%
(2278.96, 2883.25, 2577.11 and 2548.65 for June to September 2026). A tighter
band would report ordinary noise as a change.
"""

BASELINE_ANOMALY_RATIO = Decimal("1.5")
"""The multiple of the baseline at which spend stops being high and starts being
worth interrupting the owner about. Generous on purpose: the mean rests on as few
as two months, so there is no dispersion to set a tighter threshold from, and the
roadmap is explicit that the alerting phase fails by over-firing.
"""

BASELINE_MINIMUM_MONTHS = 2
"""Qualifying Months the window needs before any comparison is offered.

Distinct from the presence floor below, which happens to share its value: this
one is about the window, that one about one category within it. They are kept
apart so either can move without dragging the other.
"""

BASELINE_PRESENCE_FLOOR = 2
"""Qualifying Months a category needs spend in before it earns a baseline.

Below this there is no normal monthly cost to report, and spreading a single
charge across the window would invent one. It is also what makes the divisor rule
safe: dividing by every Qualifying Month is right for a recurring expense and
nonsense for a one-off, and the floor is what keeps the one-off from reaching it.
"""


def category_baseline(*, spend_by_qualifying_month: Sequence[Decimal]) -> Decimal | None:
    """What this category normally costs, over the Qualifying Months given.

    One entry per Qualifying Month in the window, zero for a month the category had
    no spend in. The divisor is therefore the number of Qualifying Months and never
    the number of months the category appeared in: for a recurring expense an absent
    month is a real zero and carries information.

    Returns ``None`` for a category below ``BASELINE_PRESENCE_FLOOR``: too rarely
    spent in to have a normal monthly cost. A month counts as present if it had any
    movement at all, a net refund included, because that is still a month in which
    the owner used the category.

    The caller owes the zeros. A caller that passes only the months with spend gets a
    higher baseline and this function cannot tell, which is why the summary service
    seam carries a test for a category absent from one Qualifying Month.
    """
    months_with_spend = sum(1 for amount in spend_by_qualifying_month if amount)
    if months_with_spend < BASELINE_PRESENCE_FLOOR:
        return None
    total = sum(spend_by_qualifying_month, Decimal("0.00"))
    return (total / Decimal(len(spend_by_qualifying_month))).quantize(_CENTS)


def month_qualifies(*, outgoing_amount: Decimal, unclassified_amount: Decimal) -> bool:
    """Whether a month's classification is complete enough to be baseline input.

    Measured as a share of **money**, never of rows. The owner's June 2026 reads 79%
    classified counting rows and 33% counting money, because the rows they had not
    got to were the large ones; a row-based test admits such a month and then biases
    every category's baseline downwards with no way to notice.

    A month with no outgoing money at all is refused rather than admitted on the
    technicality that nothing in it is unclassified. Such a month would contribute a
    zero to every baseline. It is the weakest signal available for the real problem --
    a month the bank was never fully asked about -- and the stronger one lives in the
    sync-coverage rule.
    """
    if outgoing_amount <= 0:
        return False
    # Cross-multiplied rather than divided, so no rounding can admit a month that is
    # a fraction of a percent past the floor.
    return unclassified_amount * 100 <= BASELINE_COVERAGE_FLOOR_PERCENT * outgoing_amount


def baseline_status(*, qualifying_months_count: int) -> BaselineStatus:
    """Whether there is enough trustworthy history to compare this month against.

    Named rather than left for each interface to infer from a null amount, which is
    the amendment ADR-0002 records for the allowance's status and for the same
    reason: a state each client derives is a state each client can derive
    differently, and the Telegram summary re-deriving the dashboard's month tense is
    how that was learned.
    """
    if qualifying_months_count < BASELINE_MINIMUM_MONTHS:
        return "insufficient_history"
    return "ok"


def comparison_status(*, spend: Decimal, baseline: Decimal | None) -> BaselineComparisonStatus:
    """Which side of normal this figure is, and whether it is worth raising.

    Comparing and firing are deliberately different acts. The deviation is reported
    in both directions, because the owner seeing that they are well below their usual
    spend is half the value of having a baseline at all. An anomaly fires only
    upward: the product exists to stop them overspending, and a month 38% below
    normal -- which the owner's live October is, in Food -- is not something to
    interrupt them for.

    A baseline of zero or less is treated as absent rather than divided by. The
    presence floor makes it nearly unreachable, needing two months whose movements
    cancel out, but a refund can do it and the answer is still that there is nothing
    to compare against.
    """
    if baseline is None or baseline <= 0:
        return "no_baseline"

    ratio = spend / baseline
    if ratio >= BASELINE_ANOMALY_RATIO:
        return "anomalous"

    tolerance = BASELINE_IN_LINE_TOLERANCE_PERCENT / 100
    if ratio > 1 + tolerance:
        return "above"
    if ratio < 1 - tolerance:
        return "below"
    return "in_line"


def deviation_percent(*, spend: Decimal, baseline: Decimal | None) -> Decimal | None:
    """How far this figure sits from normal, signed, as a percent.

    Signed rather than absolute, because the sign is the whole point: an interface
    given a magnitude has to work out the direction from the status, and the owner
    being well under their usual spend is a thing worth saying out loud.

    Quantized to one decimal place, matching every other percent the product
    publishes.
    """
    if baseline is None or baseline <= 0:
        return None
    return ((spend - baseline) / baseline * Decimal("100.0")).quantize(Decimal("0.1"))


def month_sync_covered(
    *,
    month_start: date,
    month_end: date,
    successful_sync_days: Sequence[date],
    fetch_window_days: int,
) -> bool:
    """Whether the bank was actually asked about every day of this month.

    The second of the two tests a Qualifying Month must pass, and the one
    classification coverage is blind to: a month with a sync hole looks perfectly
    classified, because every row it *does* have is filed, while transactions are
    missing outright and no figure anywhere says so. A baseline built on such a month
    is understated, and an understated baseline makes ordinary spend look like an
    anomaly -- the over-firing the roadmap says the alerting phase fails by.

    A sync run on day S fetches the trailing window ``[S - fetch_window_days, S]``, so
    the month is covered only if the windows of its successful syncs union to span
    every one of its days. ``month_end`` is exclusive, matching the month window
    convention everywhere else.

    Only days on which a sync *succeeded* may be passed. That matters most for the
    case this rule exists to catch: an expired consent writes a session row per
    attempt, so counting rows rather than successes would see an unbroken chain of
    sessions running straight through the gap it is meant to detect.
    """
    needed = month_start
    for sync_day in sorted(successful_sync_days):
        window_start = sync_day - timedelta(days=fetch_window_days)
        if window_start > needed:
            # Sorted ascending, so every window from here on starts later still:
            # nothing can reach back to ``needed`` and the gap is real.
            return False
        needed = max(needed, sync_day + timedelta(days=1))
        if needed >= month_end:
            return True
    return False


@dataclass(frozen=True)
class ComparableTotals:
    """The half of a month's spend that can be judged, and what it is judged against."""

    spend: Decimal
    baseline: Decimal | None


def comparable_totals(
    *,
    spend_and_baselines: Sequence[tuple[Decimal, Decimal | None]],
) -> ComparableTotals:
    """Add up only the categories that have a baseline to be compared against.

    This is policy, not arithmetic. A month dominated by a one-off in a category
    with no history would otherwise report catastrophic overspending while every
    ordinary category sat under its own usual figure -- which is the owner's live
    October, where one legal expense is fourteen times the comparable total. The
    aggregate would not merely be unhelpful there; it would be actively wrong about
    the one thing the product exists to say.

    The excluded money is not hidden. The caller reports it beside the comparison as
    Uncomparable Spend, which is the shape Unbudgeted Spend already has: invisible to
    the figure it would corrupt, always disclosed next to it.

    ``baseline`` is ``None`` when nothing in the month has one, so that no caller
    reads a zero as "normally nothing".
    """
    comparable = [
        (spend, baseline) for spend, baseline in spend_and_baselines if baseline is not None
    ]
    if not comparable:
        return ComparableTotals(spend=Decimal("0.00"), baseline=None)
    return ComparableTotals(
        spend=sum((spend for spend, _ in comparable), Decimal("0.00")),
        baseline=sum((baseline for _, baseline in comparable), Decimal("0.00")),
    )


def figure_baseline_amount(*, amounts_by_qualifying_month: Sequence[Decimal]) -> Decimal | None:
    """The mean of a whole-month figure over the Qualifying Months given.

    No presence floor, unlike ``category_baseline``, and that is the decision this
    function exists to state. The floor is for a category the owner spends in too
    rarely to have a normal monthly cost; an aggregate figure has no such notion. A
    month in which nothing came in is a fact about the owner's year, and skipping it
    would report a salary as normal to someone who was paid once in three months.
    """
    if not amounts_by_qualifying_month:
        return None
    total = sum(amounts_by_qualifying_month, Decimal("0.00"))
    return (total / Decimal(len(amounts_by_qualifying_month))).quantize(_CENTS)

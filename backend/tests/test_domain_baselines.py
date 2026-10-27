from __future__ import annotations

from datetime import date
from decimal import Decimal

import pytest

from burnrate.domain.baselines import (
    comparable_totals,
    baseline_status,
    category_baseline,
    comparison_status,
    deviation_percent,
    month_qualifies,
    month_sync_covered,
)


# Worked examples for the trailing mean. Each row is one entry per Qualifying Month
# in the window -- the category's spend in that month, zero for a month it had none
# -- and the baseline the owner should be shown.
#
# The divisor is the number of Qualifying Months, never the number of months the
# category appeared in. For a recurring expense an absent month is a real zero and
# carries information: 600 and 0 and 300 over three qualifying months is 300, not
# the 450 that averaging only the months with spend would give.
#
# spend per qualifying month, baseline
TRAILING_MEAN_EXAMPLES = [
    (["600.00", "300.00"], "450.00"),
    (["600.00", "0.00", "300.00"], "300.00"),
    (["100.00", "100.00", "100.00"], "100.00"),
    # 829.49 over two months is 414.745 exactly, a half cent. Every money figure
    # in the product quantizes with Decimal's default half-even rounding, so this
    # lands on 414.74 rather than up. Pinned here so the convention is stated
    # once rather than discovered by a reader of a dashboard.
    (["256.84", "572.65"], "414.74"),
    (["10.00", "10.00", "10.00"], "10.00"),
    (["100.00", "0.00", "0.00", "100.00"], "50.00"),
]


@pytest.mark.parametrize(("spend_by_month", "expected"), TRAILING_MEAN_EXAMPLES)
def test_category_baseline_divides_by_the_qualifying_months_not_the_months_present(
    spend_by_month: list[str],
    expected: str,
) -> None:
    baseline = category_baseline(
        spend_by_qualifying_month=[Decimal(amount) for amount in spend_by_month],
    )

    assert baseline == Decimal(expected)


# Worked examples for the presence floor. Each row is one entry per Qualifying Month
# and whether the category earns a baseline at all.
#
# A category the owner spent in once has no normal monthly cost, and inventing one by
# spreading a single charge across the window is worse than saying nothing: in the
# owner's live data this is what keeps a one-off relocation, a single toll and one
# holiday from each reporting an invented monthly figure. The floor is two Qualifying
# Months with spend, which is also what makes the divisor rule above safe to apply.
#
# spend per qualifying month, baseline or None
PRESENCE_FLOOR_EXAMPLES = [
    (["500.00", "0.00", "0.00"], None),
    (["0.00", "0.00", "500.00"], None),
    (["0.00", "0.00", "0.00"], None),
    (["500.00", "100.00", "0.00"], "200.00"),
    (["0.00", "300.00", "300.00"], "200.00"),
    (["500.00"], None),
]


@pytest.mark.parametrize(("spend_by_month", "expected"), PRESENCE_FLOOR_EXAMPLES)
def test_category_baseline_refuses_a_category_the_owner_rarely_spends_in(
    spend_by_month: list[str],
    expected: str | None,
) -> None:
    baseline = category_baseline(
        spend_by_qualifying_month=[Decimal(amount) for amount in spend_by_month],
    )

    assert baseline == (Decimal(expected) if expected is not None else None)


# Worked examples for classification coverage. Each row is a month's total outgoing
# amount, how much of it the owner has not classified, and whether the month may be
# used as baseline input.
#
# The first five rows are the owner's own months as of 2026-10-26, which is why the
# measure is by amount and not by row count. June reads 79% classified counting rows
# and 33% counting money, because the unclassified rows are the large ones: a
# row-based measure would have admitted a two-thirds-empty month as clean baseline
# input and biased every category's baseline downwards, silently.
#
# outgoing, unclassified, qualifies
COVERAGE_EXAMPLES = [
    ("7002.82", "4661.72", False),  # 2026-06, 66.6% unclassified
    ("8602.36", "4952.77", False),  # 2026-07, 57.6%
    ("2858.00", "0.00", True),      # 2026-08, fully classified
    ("2566.53", "0.00", True),      # 2026-09, fully classified
    ("9479.13", "212.99", True),    # 2026-10, 2.2%
    ("1000.00", "50.00", True),     # exactly at the floor, which is inclusive
    ("1000.00", "50.01", False),    # a cent past it
    ("1000.00", "1000.00", False),  # nothing classified at all
]


@pytest.mark.parametrize(("outgoing", "unclassified", "expected"), COVERAGE_EXAMPLES)
def test_month_qualifies_on_the_share_of_money_classified_not_the_share_of_rows(
    outgoing: str,
    unclassified: str,
    expected: bool,
) -> None:
    qualifies = month_qualifies(
        outgoing_amount=Decimal(outgoing),
        unclassified_amount=Decimal(unclassified),
    )

    assert qualifies is expected


def test_month_qualifies_refuses_a_month_with_no_outgoing_money_at_all() -> None:
    """A month showing no spend is not evidence of a frugal month.

    Nothing is unclassified in such a month, so a share-based test would admit it and
    then contribute a zero to every category's baseline, dragging all of them down --
    the silently-low failure this rule exists to prevent. It is refused here on the
    weakest available evidence; ticket 03 catches the subtler and more likely case,
    a month holding *some* data with a sync gap through the middle of it.
    """
    assert month_qualifies(outgoing_amount=Decimal("0.00"), unclassified_amount=Decimal("0.00")) is False


# Worked examples for the minimum history. Each row is how many Qualifying Months the
# window found and the state the backend reports.
#
# The state is named here rather than left to each interface to infer from a null
# amount, following the amendment ADR-0002 records for the allowance's status: one
# interface inferring it is one interface that can infer it differently. Two months
# is the floor, which is what the owner has today -- the feature works from the day
# it ships, by one month's margin.
#
# qualifying months, status
MINIMUM_HISTORY_EXAMPLES = [
    (0, "insufficient_history"),
    (1, "insufficient_history"),
    (2, "ok"),
    (3, "ok"),
    (12, "ok"),
]


@pytest.mark.parametrize(("qualifying_months", "expected"), MINIMUM_HISTORY_EXAMPLES)
def test_baseline_status_names_too_little_history_rather_than_reporting_a_thin_mean(
    qualifying_months: int,
    expected: str,
) -> None:
    assert baseline_status(qualifying_months_count=qualifying_months) == expected


# Worked examples for the comparison bands. Each row is what the owner spent in a
# category, what that category normally costs them, and the one verdict the backend
# publishes so that no interface bands the figure itself.
#
# The bands: in_line is the closed interval 0.85 to 1.15 of the baseline, which is
# where the owner's real month-to-month variation sits in clean months; above is past
# 1.15 but short of the anomaly ratio; anomalous is 1.5 of the baseline or more.
#
# Comparing and firing are different acts. The deviation is reported in both
# directions because a quiet month is information, but an anomaly only ever fires
# upward: the product exists to stop the owner overspending, and the roadmap is
# explicit that Phase 10 fails by over-firing. The first row is the owner's own
# October Food figure against its Aug-Sep baseline -- 38% below, and good news.
#
# spend, baseline, verdict
COMPARISON_EXAMPLES = [
    ("256.84", "414.74", "below"),       # live October Food: far below, fires nothing
    ("0.00", "1000.00", "below"),        # spent nothing at all
    ("849.99", "1000.00", "below"),      # a cent under the in_line band
    ("850.00", "1000.00", "in_line"),    # the lower edge, inclusive
    ("1000.00", "1000.00", "in_line"),   # exactly normal
    ("1150.00", "1000.00", "in_line"),   # the upper edge, inclusive
    ("1150.01", "1000.00", "above"),     # a cent past it
    ("1499.99", "1000.00", "above"),     # a cent short of the anomaly ratio
    ("1500.00", "1000.00", "anomalous"), # the anomaly ratio, inclusive
    ("9000.00", "1000.00", "anomalous"), # far past it
]


@pytest.mark.parametrize(("spend", "baseline", "expected"), COMPARISON_EXAMPLES)
def test_comparison_status_bands_the_month_against_what_is_normal(
    spend: str,
    baseline: str,
    expected: str,
) -> None:
    status = comparison_status(
        spend=Decimal(spend),
        baseline=Decimal(baseline),
        fires_anomalies=True,
    )

    assert status == expected


# An anomaly fires upward on spend, and income is not spend. A month in which more
# money came in than usual -- a bonus, a refund, a late invoice finally paid -- is
# reported in full and flagged as nothing, because "unusually high" is the wording
# both clients give an anomaly and there is nothing wrong with being paid.
#
# The band above the anomaly ratio collapses into ``above``; every other band is
# untouched, which is what the second and third rows pin.
#
# figure, baseline, verdict
INCOME_EXAMPLES = [
    ("3000.00", "2000.00", "above"),     # a bonus month: high, and not a warning
    ("9000.00", "2000.00", "above"),     # far past the ratio, still just above
    ("1000.00", "2000.00", "below"),     # the direction that would be worth saying
    ("2000.00", "2000.00", "in_line"),
]


@pytest.mark.parametrize(("figure", "baseline", "expected"), INCOME_EXAMPLES)
def test_comparison_status_never_fires_an_anomaly_on_a_figure_that_is_not_spend(
    figure: str,
    baseline: str,
    expected: str,
) -> None:
    status = comparison_status(
        spend=Decimal(figure),
        baseline=Decimal(baseline),
        fires_anomalies=False,
    )

    assert status == expected


# A category below the presence floor has no baseline, and the live October case for
# it is a one-off legal expense of 8403.83 -- larger than every other category in the
# month put together. There is nothing to compare it against and the product says so
# rather than reporting it as the worst overspend it has ever seen.
NO_BASELINE_EXAMPLES = [
    ("8403.83", None),
    ("0.00", None),
    ("100.00", "0.00"),
]


@pytest.mark.parametrize(("spend", "baseline"), NO_BASELINE_EXAMPLES)
def test_comparison_status_makes_no_claim_without_a_baseline(
    spend: str,
    baseline: str | None,
) -> None:
    status = comparison_status(
        spend=Decimal(spend),
        baseline=Decimal(baseline) if baseline is not None else None,
        fires_anomalies=True,
    )

    assert status == "no_baseline"


# Worked examples for the deviation the owner reads beside the verdict. Signed, so
# that a quiet month reads as a quiet month rather than as an unexplained absence of
# warning, and quantized to one decimal place like every other percent the product
# publishes.
#
# spend, baseline, deviation
DEVIATION_EXAMPLES = [
    ("256.84", "414.74", "-38.1"),   # live October Food against its Aug-Sep baseline
    ("1000.00", "1000.00", "0.0"),
    ("1500.00", "1000.00", "50.0"),
    ("500.00", "1000.00", "-50.0"),
    ("0.00", "1000.00", "-100.0"),
    ("2000.00", "1000.00", "100.0"),
]


@pytest.mark.parametrize(("spend", "baseline", "expected"), DEVIATION_EXAMPLES)
def test_deviation_percent_is_signed_so_a_quiet_month_reads_as_one(
    spend: str,
    baseline: str,
    expected: str,
) -> None:
    deviation = deviation_percent(spend=Decimal(spend), baseline=Decimal(baseline))

    assert deviation == Decimal(expected)


def test_deviation_percent_is_absent_without_a_baseline() -> None:
    assert deviation_percent(spend=Decimal("8403.83"), baseline=None) is None
    assert deviation_percent(spend=Decimal("100.00"), baseline=Decimal("0.00")) is None


# Worked examples for sync coverage, all for September 2026 against a 30-day fetch
# window. Each row is the days successful syncs ran on and whether the month was
# fully asked about.
#
# A sync run on day S fetches the window [S - 30, S], so a month is covered only if
# the windows of its successful syncs union to span every one of its days. This is
# the test classification coverage cannot perform: a month with a sync hole looks
# perfectly classified, because every row it does have is filed, while transactions
# are missing outright and no figure anywhere says so.
#
# sync days, covered
SYNC_COVERAGE_EXAMPLES = [
    # The ordinary case: a daily cron, windows overlapping thirty deep.
    ([date(2026, 9, d) for d in range(1, 31)] + [date(2026, 10, 1)], True),
    # Two runs are enough when their windows meet: [Aug 16, Sep 15] and [Sep 1, Oct 1].
    ([date(2026, 9, 15), date(2026, 10, 1)], True),
    # One run on the 1st of October reaches back over the whole of September.
    ([date(2026, 10, 1)], True),
    # And one on the 30th still does: [Aug 31, Sep 30] spans every day of the month.
    ([date(2026, 9, 30)], True),
    # A day short. [Aug 30, Sep 29] leaves the 30th never asked about.
    ([date(2026, 9, 29)], False),
    # A day late. [Sep 2, Oct 2] never asks about the 1st.
    ([date(2026, 10, 2)], False),
    # The real failure: syncs stop on the 5th and resume six weeks later, so
    # [Aug 6, Sep 5] and [Sep 20, Oct 20] leave the 6th to the 19th unasked.
    ([date(2026, 9, 5), date(2026, 10, 20)], False),
    # Nothing ran at all.
    ([], False),
    # Everything ran before the month, so its window closed before the month opened.
    ([date(2026, 8, 20)], False),
    # Coverage by *chain*, which is the case that separates this rule from a weaker
    # one. Neither window spans September alone and the second one opens well after
    # the month did -- [Aug 21, Sep 20] and [Sep 15, Oct 15] -- but they overlap, so
    # together they reach every day. A cron that slowed from daily to weekly produces
    # exactly this, and judging each window against the month's first day instead of
    # against what is still unaccounted for would reject it.
    ([date(2026, 9, 20), date(2026, 10, 15)], True),
    # A longer chain of the same, three windows deep.
    ([date(2026, 9, 10), date(2026, 10, 5), date(2026, 10, 25)], True),
    # And the chain broken by one day: [Aug 21, Sep 20] then [Sep 22, Oct 22] leaves
    # the 21st unasked, which the month's first day alone can never reveal.
    ([date(2026, 9, 20), date(2026, 10, 22)], False),
]


@pytest.mark.parametrize(("sync_days", "expected"), SYNC_COVERAGE_EXAMPLES)
def test_month_sync_covered_asks_whether_the_bank_was_asked_about_every_day(
    sync_days: list[date],
    expected: bool,
) -> None:
    covered = month_sync_covered(
        month_start=date(2026, 9, 1),
        month_end=date(2026, 10, 1),
        successful_sync_days=sync_days,
        fetch_window_days=30,
    )

    assert covered is expected


def test_month_sync_covered_does_not_care_what_order_the_syncs_arrive_in() -> None:
    """The caller hands over rows from a database, and row order is not a promise."""
    unordered = [date(2026, 10, 1), date(2026, 8, 20), date(2026, 9, 15)]

    assert (
        month_sync_covered(
            month_start=date(2026, 9, 1),
            month_end=date(2026, 10, 1),
            successful_sync_days=unordered,
            fetch_window_days=30,
        )
        is True
    )


def test_comparable_totals_leave_out_what_has_no_baseline() -> None:
    """The owner's live October, which is why the aggregate is split at all.

    Three categories: Food at 256.84 against a usual 414.74, Invoices at 44.95
    against 179.94, and a one-off legal expense of 8403.83 with no history and so no
    baseline. The comparable half is 301.79 spent where 594.68 is usual -- a bit over
    half, a notably quiet month.

    Folding the uncomparable category in gives 8705.62 against 594.68, fourteen times
    normal, and the product would report catastrophic overspending in a month where
    every ordinary category came in under its own usual figure. The excluded money is
    not hidden; it is reported beside the comparison, which is the shape Unbudgeted
    Spend already has.
    """
    totals = comparable_totals(
        spend_and_baselines=[
            (Decimal("256.84"), Decimal("414.74")),
            (Decimal("44.95"), Decimal("179.94")),
            (Decimal("8403.83"), None),
        ],
    )

    assert totals.spend == Decimal("301.79")
    assert totals.baseline == Decimal("594.68")


# Each row is the per-category spend and baseline pairs, and the comparable spend and
# comparable baseline they add up to.
#
# pairs, comparable spend, comparable baseline
COMPARABLE_TOTALS_EXAMPLES = [
    ([("100.00", "80.00")], "100.00", "80.00"),
    ([("100.00", "80.00"), ("50.00", "60.00")], "150.00", "140.00"),
    # Nothing has a baseline: there is no comparison to offer and no total to offer
    # it against, but the spend still has to be accounted for somewhere.
    ([("100.00", None), ("50.00", None)], "0.00", None),
    ([], "0.00", None),
    # A category with a baseline and no spend this month counts as zero spend against
    # its usual figure, which is the point of the divisor rule one layer down.
    ([("0.00", "80.00")], "0.00", "80.00"),
]


@pytest.mark.parametrize(("pairs", "spend", "baseline"), COMPARABLE_TOTALS_EXAMPLES)
def test_comparable_totals_add_up_only_the_categories_that_can_be_compared(
    pairs: list[tuple[str, str | None]],
    spend: str,
    baseline: str | None,
) -> None:
    totals = comparable_totals(
        spend_and_baselines=[
            (Decimal(each_spend), Decimal(each_baseline) if each_baseline is not None else None)
            for each_spend, each_baseline in pairs
        ],
    )

    assert totals.spend == Decimal(spend)
    assert totals.baseline == (Decimal(baseline) if baseline is not None else None)

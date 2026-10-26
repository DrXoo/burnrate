"""Baselines: what each figure normally is for the owner.

Owns the queries that read *other* months. ``SummaryService`` composes it and asks
one question -- "the baselines for this month" -- rather than depending on a broad
persistence API, because the next consumer is the alerting phase, which wants the
same answer without a summary around it.

Nothing is stored and there is no migration. Every figure is recomputed from
transactions on each request, which is what `AGENTS.md` requires of a derived
metric and what makes the owner's own corrections take effect at once: in this
product the past changes, by a budget cancelled from a past month (ADR-0005), by
the pending sweep, and by an Unknown Transaction finally being classified.
"""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass
from datetime import UTC, date, datetime, timedelta
from decimal import Decimal
from uuid import UUID

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from burnrate.clock import civil_date
from burnrate.db.dispositions import awaiting_categorization, not_ignored
from burnrate.db.effective_date import month_window, within_month
from burnrate.db.models import Account, Category, SyncSession, Transaction
from burnrate.domain.metrics import MonthTense
# ``as_utc`` lives under connection expiry rather than beside the clock, which is
# the wrong home for it -- but it is the repo's one answer for a datetime read back
# naive from SQLite, and duplicating it here would be worse than importing it.
from burnrate.services.connection_expiry import as_utc
from burnrate.services.enable_banking_service import TRANSACTION_WINDOW
from burnrate.domain.baselines import (
    BaselineComparisonStatus,
    BaselineStatus,
    baseline_status,
    category_baseline,
    comparable_totals,
    comparison_status,
    deviation_percent,
    figure_baseline_amount,
    month_qualifies,
    month_sync_covered,
)

COMMITTED_STATUSES = ("booked", "pending")
"""The same statuses the summary counts as spend: settled, or committed by the owner."""

NO_SPEND = Decimal("0.00")


@dataclass(frozen=True)
class CategoryComparison:
    """One category's month against its own normal."""

    category_id: UUID
    category_name: str
    spend_amount: Decimal
    baseline_amount: Decimal | None
    deviation_percent: Decimal | None
    comparison_status: BaselineComparisonStatus


@dataclass(frozen=True)
class MonthTotals:
    """One month's income and spending, on the same basis the summary reports them."""

    income: Decimal
    spending: Decimal

    @property
    def net(self) -> Decimal:
        return self.income - self.spending


@dataclass(frozen=True)
class FigureBaseline:
    """One figure against its own normal."""

    baseline_amount: Decimal | None
    deviation_percent: Decimal | None
    comparison_status: BaselineComparisonStatus


NO_COMPARISON = FigureBaseline(
    baseline_amount=None,
    deviation_percent=None,
    comparison_status="no_baseline",
)


@dataclass(frozen=True)
class Baselines:
    """Everything the summary needs to publish a comparison, and nothing else."""

    status: BaselineStatus
    qualifying_months_count: int
    categories: tuple[CategoryComparison, ...]
    # The spend the comparison can actually speak to, and what it speaks to it
    # against. The rest of the month's spending is the caller's residual to disclose.
    comparable_spend: Decimal
    comparable: FigureBaseline
    income: FigureBaseline
    # Amount only, no band. A ratio on a figure that can cross zero means nothing,
    # and an owner whose usual month is a deficit would carry a negative baseline
    # that the band logic reads as no baseline at all -- a verdict denying what the
    # amount beside it states. The two figures side by side already say it.
    net_cash_flow_baseline: Decimal | None


class BaselineService:
    def __init__(self, *, db: Session, timezone_name: str = "UTC") -> None:
        self.db = db
        # Sync instants are stored in UTC; coverage is judged in civil days, because
        # the fetch window the sync actually used was derived from the owner's own
        # today. See ``burnrate/clock.py``.
        self._timezone_name = timezone_name

    def baselines_for(
        self,
        *,
        month_value: str,
        month_tense: MonthTense,
        reference_day: date,
        window_months: int,
    ) -> Baselines:
        """The comparison for one month, or the reason there is none.

        The tense is taken rather than worked out: comparing two dates is a calendar
        fact the caller already established, and only the caller knows which day the
        owner is on.
        """
        if month_tense == "not_started":
            return Baselines(
                status="month_not_started",
                qualifying_months_count=0,
                categories=(),
                comparable_spend=NO_SPEND,
                comparable=NO_COMPARISON,
                income=NO_COMPARISON,
                net_cash_flow_baseline=None,
            )

        candidates = _preceding_months(month_value, window_months)
        # Fetched once rather than per candidate month: the rule needs runs from after
        # a month as well as during it, since a window reaches backwards.
        sync_days = self._successful_sync_days(since=month_window(candidates[0])[0])
        qualifying = [
            month for month in candidates if self._month_qualifies(month, sync_days=sync_days)
        ]
        status = baseline_status(qualifying_months_count=len(qualifying))

        # The month on screen and every month behind it are measured over the same
        # part of the month, so that a part-month is never read against whole ones.
        # Phase 8 paid for the alternative in the budget pacing, where a comparison
        # with no time term flipped an on-plan month to a warning around day 26.
        cutoff_day = reference_day.day if month_tense == "current" else None

        # Income and total spending for the month on screen and every Qualifying
        # Month, read once each: the income baseline and the net cash flow baseline
        # are both built from them.
        monthly = {
            month: self._month_totals(month, cutoff_day=cutoff_day)
            for month in [month_value, *qualifying]
        }

        this_month = self._category_spend(month_value, cutoff_day=cutoff_day)
        past_months = [self._category_spend(month, cutoff_day=cutoff_day) for month in qualifying]

        reached = set(this_month) | {category for month in past_months for category in month}
        names = self._category_names(reached)

        comparisons = []
        for category_id in reached:
            spend = this_month.get(category_id, NO_SPEND)
            baseline = (
                category_baseline(
                    spend_by_qualifying_month=[
                        month.get(category_id, NO_SPEND) for month in past_months
                    ],
                )
                if status == "ok"
                else None
            )
            comparisons.append(
                CategoryComparison(
                    category_id=category_id,
                    category_name=names[category_id],
                    spend_amount=spend,
                    baseline_amount=baseline,
                    deviation_percent=deviation_percent(spend=spend, baseline=baseline),
                    comparison_status=comparison_status(spend=spend, baseline=baseline),
                )
            )

        comparisons.sort(key=lambda row: row.category_name)
        totals = comparable_totals(
            spend_and_baselines=[(row.spend_amount, row.baseline_amount) for row in comparisons],
        )
        return Baselines(
            status=status,
            qualifying_months_count=len(qualifying),
            categories=tuple(comparisons),
            comparable_spend=totals.spend,
            comparable=_figure_baseline(spend=totals.spend, baseline=totals.baseline),
            income=self._aggregate_baseline(
                this_month=monthly[month_value].income,
                past_months=[monthly[month].income for month in qualifying],
                offered=status == "ok",
            ),
            net_cash_flow_baseline=(
                figure_baseline_amount(
                    amounts_by_qualifying_month=[monthly[month].net for month in qualifying],
                )
                if status == "ok"
                else None
            ),
        )

    def _month_qualifies(self, month_value: str, *, sync_days: Sequence[date]) -> bool:
        """Both tests, because each is blind to the other.

        Classification coverage asks whether the owner has filed the month's money.
        Sync coverage asks whether the bank was ever asked about all of it. A month
        with a hole passes the first test perfectly -- every row it holds is filed --
        while transactions are missing outright, and the resulting baseline is
        understated with nothing anywhere to say so.
        """
        month_start, month_end = month_window(month_value)
        if not month_sync_covered(
            month_start=month_start,
            month_end=month_end,
            successful_sync_days=sync_days,
            fetch_window_days=TRANSACTION_WINDOW.days,
        ):
            return False
        outgoing, unclassified = self._outgoing_and_unclassified(month_value)
        return month_qualifies(outgoing_amount=outgoing, unclassified_amount=unclassified)

    def _successful_sync_days(self, *, since: date) -> list[date]:
        """The owner's civil days on which a sync actually succeeded.

        Only ``success`` counts. ``skipped`` is the status an expired consent writes,
        once per attempt, so it papers over the very gap this rule exists to find;
        ``failed`` learned nothing and ``running`` has not finished learning.

        Bounded below by the oldest candidate month, less a day for the timezone
        conversion: a run whose window closed before a month opened cannot cover any
        part of it.
        """
        floor = datetime(since.year, since.month, since.day, tzinfo=UTC) - timedelta(days=1)
        instants = self.db.scalars(
            select(SyncSession.started_at).where(
                func.lower(SyncSession.status) == "success",
                SyncSession.started_at >= floor,
            )
        ).all()
        return sorted(
            {
                civil_date(timezone_name=self._timezone_name, instant=as_utc(instant))
                for instant in instants
                if instant is not None
            }
        )

    def _outgoing_and_unclassified(self, month_value: str) -> tuple[Decimal, Decimal]:
        """How much money left the account that month, and how much of it is unfiled.

        The denominator is every outgoing row rather than every *expense* row, because
        an unclassified row has no category to tell a purchase from a transfer. Asking
        what share of the money that left is still unfiled is answerable without
        knowing what any of it was, which is the only question that can be asked of a
        month the owner has not finished reviewing.
        """
        month_start, month_end = month_window(month_value)
        outgoing = self._sum_outgoing(month_start=month_start, month_end=month_end)
        unfiled = self._sum_outgoing(
            month_start=month_start,
            month_end=month_end,
            awaiting_review_only=True,
        )
        return outgoing, unfiled

    def _sum_outgoing(
        self,
        *,
        month_start: date,
        month_end: date,
        awaiting_review_only: bool = False,
    ) -> Decimal:
        conditions = [
            Account.included_in_calculations.is_(True),
            within_month(month_start=month_start, month_end=month_end),
            func.lower(Transaction.status).in_(COMMITTED_STATUSES),
            Transaction.amount < 0,
            not_ignored(),
        ]
        if awaiting_review_only:
            conditions.append(awaiting_categorization())
        total = self.db.scalar(
            select(func.coalesce(func.sum(Transaction.amount), NO_SPEND))
            .select_from(Transaction)
            .join(Account, Account.id == Transaction.account_id)
            .where(*conditions)
        ) or NO_SPEND
        return (-Decimal(total)).quantize(Decimal("0.01"))

    def _category_spend(self, month_value: str, *, cutoff_day: int | None) -> dict[UUID, Decimal]:
        """Spend per category for one month, to the cutoff day where there is one.

        Archived Categories are excluded here rather than filtered later: they keep
        their historical figures, per ADR-0007, but a category the owner retired
        reporting itself below its baseline every month for ever is noise.
        """
        month_start, month_end = _month_window_to_cutoff(month_value, cutoff_day=cutoff_day)
        rows = self.db.execute(
            select(
                Transaction.category_id,
                func.coalesce(func.sum(Transaction.amount), NO_SPEND),
            )
            .select_from(Transaction)
            .join(Account, Account.id == Transaction.account_id)
            .join(Category, Category.id == Transaction.category_id)
            .where(
                Account.included_in_calculations.is_(True),
                within_month(month_start=month_start, month_end=month_end),
                func.lower(Transaction.status).in_(COMMITTED_STATUSES),
                Category.type == "expense",
                Category.active.is_(True),
                not_ignored(),
            )
            .group_by(Transaction.category_id)
        ).all()
        return {
            category_id: (-Decimal(total)).quantize(Decimal("0.01"))
            for category_id, total in rows
            if category_id is not None
        }

    def _category_names(self, category_ids: set[UUID]) -> dict[UUID, str]:
        if not category_ids:
            return {}
        rows = self.db.execute(
            select(Category.id, Category.name).where(Category.id.in_(category_ids))
        ).all()
        return {category_id: name for category_id, name in rows}


    def _aggregate_baseline(
        self,
        *,
        this_month: Decimal,
        past_months: Sequence[Decimal],
        offered: bool,
    ) -> FigureBaseline:
        """One whole-month figure against its mean, or no claim at all."""
        baseline = figure_baseline_amount(amounts_by_qualifying_month=past_months) if offered else None
        return _figure_baseline(spend=this_month, baseline=baseline)

    def _month_totals(self, month_value: str, *, cutoff_day: int | None) -> MonthTotals:
        """A month's income and total spending, on the same basis the summary uses."""
        income = self._month_income(month_value, cutoff_day=cutoff_day)
        spending = self._month_spending(month_value, cutoff_day=cutoff_day)
        return MonthTotals(income=income, spending=spending)

    def _month_spending(self, month_value: str, *, cutoff_day: int | None) -> Decimal:
        """Total spending for one month, matching the month's own spending figure.

        Committed statuses, every expense category, archived included -- the filters
        of the figure this feeds rather than those of the per-category list, which
        excludes archived categories because it is a list the owner reads.
        """
        month_start, month_end = _month_window_to_cutoff(month_value, cutoff_day=cutoff_day)
        total = self.db.scalar(
            select(func.coalesce(func.sum(Transaction.amount), NO_SPEND))
            .select_from(Transaction)
            .join(Account, Account.id == Transaction.account_id)
            .join(Category, Category.id == Transaction.category_id)
            .where(
                Account.included_in_calculations.is_(True),
                within_month(month_start=month_start, month_end=month_end),
                func.lower(Transaction.status).in_(COMMITTED_STATUSES),
                Category.type == "expense",
                not_ignored(),
            )
        ) or NO_SPEND
        return (-Decimal(total)).quantize(Decimal("0.01"))

    def _month_income(self, month_value: str, *, cutoff_day: int | None) -> Decimal:
        """Income for one month, to the cutoff day where there is one.

        Booked only, matching the figure this is compared against: a credit the bank
        has not settled is not money kept, which is the asymmetry ADR-0003 records.

        Archived categories are *not* excluded here, unlike the per-category spend
        query. Each baseline matches the filters of the figure it is compared against,
        and the month's income figure counts every income category, so excluding
        archived ones would compare a narrower total against a wider one.
        """
        month_start, month_end = _month_window_to_cutoff(month_value, cutoff_day=cutoff_day)
        total = self.db.scalar(
            select(func.coalesce(func.sum(Transaction.amount), NO_SPEND))
            .select_from(Transaction)
            .join(Account, Account.id == Transaction.account_id)
            .join(Category, Category.id == Transaction.category_id)
            .where(
                Account.included_in_calculations.is_(True),
                within_month(month_start=month_start, month_end=month_end),
                func.lower(Transaction.status) == "booked",
                Category.type == "income",
                not_ignored(),
            )
        ) or NO_SPEND
        return Decimal(total).quantize(Decimal("0.01"))


def _preceding_months(month_value: str, count: int) -> list[str]:
    """The ``count`` months immediately before ``month_value``, oldest first.

    The window is a maximum reach rather than a requirement: how many of these
    actually qualify is what the baseline rests on, and that count is published so
    the owner can see how much to trust it.
    """
    year, month = (int(part) for part in month_value.split("-"))
    months = []
    for _ in range(count):
        month -= 1
        if month == 0:
            year, month = year - 1, 12
        months.append(f"{year:04d}-{month:02d}")
    return sorted(months)


def _month_window_to_cutoff(month_value: str, *, cutoff_day: int | None) -> tuple[date, date]:
    """The month, or its first ``cutoff_day`` days, as a half-open window.

    ``within_month`` is half-open, so including day N means ending at N+1. The cutoff
    clamps to the month's own length, which is what lets a 31st be compared against a
    September: the shorter month contributes all of itself rather than overflowing.
    """
    month_start, month_end = month_window(month_value)
    if cutoff_day is None:
        return month_start, month_end
    days_in_month = (month_end - month_start).days
    return month_start, month_start + timedelta(days=min(cutoff_day, days_in_month))


def _figure_baseline(*, spend: Decimal, baseline: Decimal | None) -> FigureBaseline:
    """Band one figure against its baseline, or state that there is none to band."""
    return FigureBaseline(
        baseline_amount=baseline,
        deviation_percent=deviation_percent(spend=spend, baseline=baseline),
        comparison_status=comparison_status(spend=spend, baseline=baseline),
    )


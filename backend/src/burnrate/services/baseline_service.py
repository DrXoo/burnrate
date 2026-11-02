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

from collections.abc import Collection, Sequence
from dataclasses import dataclass
from datetime import UTC, date, datetime, timedelta
from decimal import Decimal
from uuid import UUID

from sqlalchemy import ColumnElement, func, select, true
from sqlalchemy.orm import Session

from burnrate.clock import civil_date
from burnrate.db.budget_windows import budget_month_status, is_event_budget
from burnrate.db.counted_spend import spend_counts
from burnrate.db.dispositions import awaiting_categorization, not_ignored
from burnrate.db.effective_date import month_window, within_month
from burnrate.db.models import Account, Budget, Category, SyncSession, Transaction
from burnrate.domain.metrics import MonthTense
# ``as_utc`` lives under connection expiry rather than beside the clock, which is
# the wrong home for it -- but it is the repo's one answer for a datetime read back
# naive from SQLite, and duplicating it here would be worse than importing it.
from burnrate.services.connection_expiry import as_utc
from burnrate.services.enable_banking_service import TRANSACTION_WINDOW
from burnrate.services.sync_coverage_service import successful_sync_days
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


@dataclass(frozen=True)
class BudgetCategories:
    """What a month's Fixed Budgets say about it, as two sets of category ids.

    ``fixed`` decides whether a hold counts; ``event`` decides whether the month's
    spend in that category is baseline input at all. Kept together because they are
    read off the same windows in one pass.
    """

    fixed: set[UUID]
    event: set[UUID]


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

        # Which categories a Fixed Budget covered, month by month: the rule that a
        # hold on a fixed bill counts towards nothing is the month's own, because the
        # owner can make a category fixed, or cancel it, between two months. Read
        # once per month and handed to both spend queries, so the per-category rows
        # and the month's total cannot disagree about what counted.
        budgets = self._budget_categories_by_month([month_value, *qualifying])

        # An Event Budget's spend is excluded from baseline *input* and from nothing
        # else, so the exclusion is passed per month rather than applied inside the
        # queries: empty for the month on screen, whose figures count every euro that
        # left, and populated for the months behind it, which are what "normal" is
        # computed from. Applying it to the month on screen too would print a Divorce
        # row reading 0.00 beside a headline that counts the 8,400, and would make
        # this a quieter ``excluded_at`` -- a primitive the product already has.
        NO_EVENTS: set[UUID] = set()

        # Income and total spending for the month on screen and every Qualifying
        # Month, read once each: the income baseline and the net cash flow baseline
        # are both built from them.
        monthly = {
            month: self._month_totals(
                month,
                cutoff_day=cutoff_day,
                fixed_category_ids=budgets[month].fixed,
                event_category_ids=NO_EVENTS if month == month_value else budgets[month].event,
            )
            for month in [month_value, *qualifying]
        }

        this_month = self._category_spend(
            month_value,
            cutoff_day=cutoff_day,
            fixed_category_ids=budgets[month_value].fixed,
            event_category_ids=NO_EVENTS,
        )
        past_months = [
            self._category_spend(
                month,
                cutoff_day=cutoff_day,
                fixed_category_ids=budgets[month].fixed,
                event_category_ids=budgets[month].event,
            )
            for month in qualifying
        ]

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
                    comparison_status=comparison_status(
                        spend=spend,
                        baseline=baseline,
                        fires_anomalies=True,
                    ),
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
            comparable=_figure_baseline(
                spend=totals.spend,
                baseline=totals.baseline,
                fires_anomalies=True,
            ),
            # The one figure here that is not spend, and so the one that is banded
            # without being fired on.
            income=self._aggregate_baseline(
                this_month=monthly[month_value].income,
                past_months=[monthly[month].income for month in qualifying],
                offered=status == "ok",
                fires_anomalies=False,
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

        Read through ``sync_coverage_service`` rather than queried here, because the
        gap alert needs the same history and two readings of it is how two readers
        come to disagree. The rule about which statuses count lives with the query.
        """
        return successful_sync_days(
            db=self.db,
            since=since,
            timezone_name=self._timezone_name,
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

    def _budget_categories_by_month(self, months: Sequence[str]) -> dict[str, BudgetCategories]:
        """The categories a Fixed Budget covered, and which of those were events, per month.

        Each month is asked in its own right rather than taking the month on screen's
        answer for the whole window: a budget's window is month-granular (ADR-0005),
        so a category the owner made fixed in September was not fixed in August and
        its August hold counted at the time.

        One query for every month, then the window rule applied in Python, rather
        than a query per month: there are few Fixed Budgets and several months, and
        this service is already the expensive half of the summary request. The rule
        is ``budget_covers_month``'s own pure twin, which is why the two live
        together -- a second spelling of it here is the defect this whole fix is
        about.

        Both answers come off the same rows because they are answers about the same
        windows: a category whose budget makes it fixed in a month and one whose
        budget makes that month an event are read from one fetch, so no later change
        can move one and leave the other behind.
        """
        windows = self.db.execute(
            select(Budget.category_id, Budget.active_from, Budget.active_to).where(
                Budget.is_fixed.is_(True)
            )
        ).all()
        by_month = {}
        for month_value in months:
            month_start, month_end = month_window(month_value)
            by_month[month_value] = BudgetCategories(
                fixed={
                    category_id
                    for category_id, active_from, active_to in windows
                    if budget_month_status(
                        active_from=active_from,
                        active_to=active_to,
                        month_start=month_start,
                        month_end=month_end,
                    )
                    == "active"
                },
                event={
                    category_id
                    for category_id, active_from, active_to in windows
                    # Every row here is already fixed, and the flag is passed anyway
                    # so the predicate states the whole rule rather than half of it.
                    if is_event_budget(
                        is_fixed=True,
                        active_from=active_from,
                        active_to=active_to,
                        month_start=month_start,
                        month_end=month_end,
                    )
                },
            )
        return by_month

    def _category_spend(
        self,
        month_value: str,
        *,
        cutoff_day: int | None,
        fixed_category_ids: set[UUID],
        event_category_ids: set[UUID],
    ) -> dict[UUID, Decimal]:
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
                spend_counts(fixed_category_ids=fixed_category_ids),
                _outside_an_event(event_category_ids),
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
        fires_anomalies: bool,
    ) -> FigureBaseline:
        """One whole-month figure against its mean, or no claim at all."""
        baseline = figure_baseline_amount(amounts_by_qualifying_month=past_months) if offered else None
        return _figure_baseline(
            spend=this_month,
            baseline=baseline,
            fires_anomalies=fires_anomalies,
        )

    def _month_totals(
        self,
        month_value: str,
        *,
        cutoff_day: int | None,
        fixed_category_ids: set[UUID],
        event_category_ids: set[UUID],
    ) -> MonthTotals:
        """A month's income and total spending, on the same basis the summary uses."""
        income = self._month_income(month_value, cutoff_day=cutoff_day)
        spending = self._month_spending(
            month_value,
            cutoff_day=cutoff_day,
            fixed_category_ids=fixed_category_ids,
            event_category_ids=event_category_ids,
        )
        return MonthTotals(income=income, spending=spending)

    def _month_spending(
        self,
        month_value: str,
        *,
        cutoff_day: int | None,
        fixed_category_ids: set[UUID],
        event_category_ids: set[UUID],
    ) -> Decimal:
        """Total spending for one month, matching the month's own spending figure.

        Committed statuses, every expense category, archived included -- the filters
        of the figure this feeds rather than those of the per-category list, which
        excludes archived categories because it is a list the owner reads. A hold on
        a fixed bill is left out here as well, because the figure this is compared
        against leaves it out.
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
                spend_counts(fixed_category_ids=fixed_category_ids),
                _outside_an_event(event_category_ids),
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


def _outside_an_event(event_category_ids: Collection[UUID]) -> ColumnElement[bool]:
    """Rows a baseline may be computed from: everything bar an Event Budget's spend.

    Private to this module on purpose, and deliberately not beside ``spend_counts``
    where the other shared spend predicate lives. The rule is "excluded from every
    baseline", so the only callers that may have it are the two queries that build
    one. In a shared module it would sooner or later be added to a figure, and an
    Event Budget that vanished from the month's own spending would be an
    ``excluded_at`` wearing a different word.

    ``true()`` when nothing is an event, rather than a ``NOT IN ()`` against an empty
    set, so neither caller needs a branch -- the same shape ``spend_counts`` uses.
    """
    if not event_category_ids:
        return true()
    return Transaction.category_id.notin_(list(event_category_ids))


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


def _figure_baseline(
    *,
    spend: Decimal,
    baseline: Decimal | None,
    fires_anomalies: bool,
) -> FigureBaseline:
    """Band one figure against its baseline, or state that there is none to band."""
    return FigureBaseline(
        baseline_amount=baseline,
        deviation_percent=deviation_percent(spend=spend, baseline=baseline),
        comparison_status=comparison_status(
            spend=spend,
            baseline=baseline,
            fires_anomalies=fires_anomalies,
        ),
    )


from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from datetime import UTC, date, datetime
from decimal import Decimal
from typing import Any
from uuid import UUID

from sqlalchemy import func, or_, select
from sqlalchemy.orm import Session

from burnrate.clock import civil_date
from burnrate.db.effective_date import month_window, within_month
from burnrate.db.models import Account, Budget, Category, Transaction
from burnrate.domain.metrics import MetricStatus, budget_usage_status, savings_verdict


COMMITTED_STATUSES = ("booked", "pending")
"""The statuses that count as spend: the bank has settled it, or the owner committed it."""


@dataclass(frozen=True)
class SpendByStatus:
    """Month-to-date spend, split by whether the bank has settled it.

    The two halves stay separable from the query to the figure because pending
    spend counts in the variable slice and nowhere else: a fixed commitment is
    judged by its estimate until it settles, so a partial hold on a bill must not
    reach the step projection, the fixed overrun or a fixed category's row. See
    ``docs/adr/0003-pending-spend-is-load-bearing.md``.
    """

    booked: Decimal = Decimal("0.00")
    pending: Decimal = Decimal("0.00")

    @property
    def total(self) -> Decimal:
        """Everything committed, settled or not."""
        return (self.booked + self.pending).quantize(Decimal("0.01"))


NO_SPEND = SpendByStatus()


@dataclass(frozen=True)
class ActiveBudgetWindow:
    category_id: UUID
    category_name: str
    amount: Decimal
    currency: str
    is_fixed: bool


class SummaryService:
    def __init__(
        self,
        *,
        db: Session,
        timezone_name: str = "UTC",
        clock: Callable[[], datetime] | None = None,
    ) -> None:
        self.db = db
        self._timezone_name = timezone_name
        self._clock = clock or (lambda: datetime.now(UTC))

    def get_summary(
        self,
        *,
        month: str | None = None,
        today: date | None = None,
    ) -> dict[str, Any]:
        reference_day = today or civil_date(
            timezone_name=self._timezone_name,
            instant=self._clock(),
        )
        month_start, month_end, month_value = self._resolve_month(month=month, reference_day=reference_day)
        days_in_month = (month_end - month_start).days
        days_elapsed = self._days_elapsed_in_month(
            month_start=month_start,
            reference_day=reference_day,
            days_in_month=days_in_month,
        )

        calculation_balance, calculation_currency, _ = self._sum_account_balances()
        uncategorized_count = self._count_uncategorized_transactions(
            month_start=month_start,
            month_end=month_end,
        )

        active_budgets = self._get_active_budgets(month_start=month_start, month_end=month_end)
        monthly_budget = sum((budget.amount for budget in active_budgets), start=Decimal("0.00"))

        spent_by_budget_category = self._get_budget_category_spend(
            month_start=month_start,
            month_end=month_end,
            category_ids=[budget.category_id for budget in active_budgets],
        )
        # One rule, two readers: the budgeted total and the per-category rows must
        # count the same money, or the dashboard prints a figure its own rows
        # contradict. A category is fixed when an active budget of its own says so.
        fixed_category_ids = {budget.category_id for budget in active_budgets if budget.is_fixed}
        fixed_spend_by_category = {
            category_id: spent_by_budget_category.get(category_id, NO_SPEND)
            for category_id in fixed_category_ids
        }
        fixed_booked_spend = sum(
            (spend.booked for spend in fixed_spend_by_category.values()),
            start=Decimal("0.00"),
        )
        fixed_pending_spend = sum(
            (spend.pending for spend in fixed_spend_by_category.values()),
            start=Decimal("0.00"),
        )

        # A hold on a fixed bill counts towards nothing until it books: the budgeted
        # estimate already stands for the whole commitment, so counting a partial
        # authorization on top would charge the owner for the same rent twice. It is
        # taken out here, once, rather than at each figure that would otherwise have
        # to remember to exclude it -- and taking it out of the month total is what
        # keeps it from resurfacing as unbudgeted spend.
        monthly_spend = self._get_monthly_spend(month_start=month_start, month_end=month_end)
        monthly_spending = (monthly_spend.total - fixed_pending_spend).quantize(Decimal("0.01"))
        # What the figures above counted but the bank has not settled, so a movement
        # in them has a cause the owner can read. It discloses the pending spend that
        # counted, which is why the hold removed from the month total is removed here
        # too: monthly spending less this is what the bank has actually settled.
        pending_spending = (monthly_spend.pending - fixed_pending_spend).quantize(Decimal("0.01"))
        monthly_income = self._get_monthly_income(month_start=month_start, month_end=month_end)
        # Net cash flow this month: what landed in income categories minus what left
        # in expense categories. Transfers are excluded on both sides, and it feeds no
        # projection. Spending counts committed money, pending included, while income
        # stays booked-only -- a credit the bank has not settled is not money kept,
        # and both halves of that asymmetry read in the cautious direction.
        net_cash_flow = (monthly_income - monthly_spending).quantize(Decimal("0.01"))
        savings = savings_verdict(net_cash_flow=net_cash_flow, income=monthly_income)
        budgeted_spending = sum(
            (
                self._counted_spend(spend=spend, is_fixed=category_id in fixed_category_ids)
                for category_id, spend in spent_by_budget_category.items()
            ),
            start=Decimal("0.00"),
        )
        # Spend in categorized expense categories that have no budget. Together with
        # budgeted_spending this reconciles monthly_spending (= budgeted + unbudgeted),
        # so the dashboard's two spend figures no longer look like they disagree.
        unbudgeted_spending = (monthly_spending - budgeted_spending).quantize(Decimal("0.01"))
        money_left = monthly_budget - budgeted_spending

        # Fixed budgets (rent, utilities) are lump/scheduled payments: they must not
        # be extrapolated from a daily rate. Each one projects as a step -- its actual
        # charge once anything has booked (which can land over or under the budgeted
        # estimate), otherwise the budgeted estimate. Carving them out keeps a day-1
        # rent charge from inflating the burn rate and the projection.
        fixed_budgets = [budget for budget in active_budgets if budget.is_fixed]
        fixed_budget_total = sum((budget.amount for budget in fixed_budgets), start=Decimal("0.00"))
        # Booked fixed spend alone feeds the step projection, because the projection
        # trusts actual spend over the estimate as soon as any spend exists and a
        # partial hold would wreck it.
        fixed_projected = sum(
            (
                self._project_fixed(
                    budget=budget,
                    spent=fixed_spend_by_category[budget.category_id].booked,
                )
                for budget in fixed_budgets
            ),
            start=Decimal("0.00"),
        )

        # Everything else accrues day by day, so it keeps the pace-based projection.
        # Both figures it is taken from already exclude a hold on a fixed bill, so
        # only booked fixed spend is left to remove -- which is what keeps such a
        # hold out of the variable slice, the one place it must never land.
        variable_budget_total = monthly_budget - fixed_budget_total
        variable_spend = (monthly_spending - fixed_booked_spend).quantize(Decimal("0.01"))
        variable_budgeted_spend = (budgeted_spending - fixed_booked_spend).quantize(Decimal("0.01"))

        # Burn rate reflects the *variable* daily pace only -- fixed lumps are excluded
        # so it captures controllable day-to-day spend. Expected burn is the planned
        # variable pace (variable budgets spread evenly across the month).
        average_daily_spend = Decimal("0.00")
        if days_elapsed > 0:
            average_daily_spend = (variable_spend / Decimal(days_elapsed)).quantize(Decimal("0.01"))
        expected_daily_spend = Decimal("0.00")
        if days_in_month > 0:
            expected_daily_spend = (variable_budget_total / Decimal(days_in_month)).quantize(Decimal("0.01"))

        # Full-month spend projections. For the variable slice, when budgets exist we
        # regress the observed daily pace toward the budgeted pace, weighted by how
        # far into the month we are, so an early-month spike doesn't blow the
        # projection out of proportion; without budgets we fall back to a straight
        # linear extrapolation. The fixed slice is added back as its step projection.
        # Overspend compares on the *budgeted* basis so both sides live in the
        # same universe as the budget.
        if variable_budget_total > 0:
            variable_projected = self._project_spend(
                spend_to_date=variable_spend,
                budget_reference=variable_budget_total,
                days_elapsed=days_elapsed,
                days_in_month=days_in_month,
            )
            variable_budgeted_projected = self._project_spend(
                spend_to_date=variable_budgeted_spend,
                budget_reference=variable_budget_total,
                days_elapsed=days_elapsed,
                days_in_month=days_in_month,
            )
        else:
            variable_projected = self._extrapolate_spend(
                spend_to_date=variable_spend,
                days_elapsed=days_elapsed,
                days_in_month=days_in_month,
            )
            variable_budgeted_projected = variable_budgeted_spend

        projected_month_end_spend = (variable_projected + fixed_projected).quantize(Decimal("0.01"))
        projected_budgeted_spend = (variable_budgeted_projected + fixed_projected).quantize(Decimal("0.01"))

        projected_overspend = max(projected_budgeted_spend - monthly_budget, Decimal("0.00"))

        # Worst first, so the rows the owner must act on lead the list. Sorting the
        # serialized rows rather than the budgets means the order is read off the
        # same status and utilization the badges show, instead of deriving them twice.
        budget_usage = sorted(
            (
                self._serialize_budget_usage(
                    budget=budget,
                    spend=spent_by_budget_category.get(budget.category_id, NO_SPEND),
                )
                for budget in active_budgets
            ),
            key=self._budget_usage_sort_key,
        )

        return {
            "month": month_value,
            "current_balance_amount": self._format_decimal(calculation_balance),
            "current_balance_currency": calculation_currency,
            "monthly_spending_amount": self._format_decimal(monthly_spending),
            "pending_spend_amount": self._format_decimal(pending_spending),
            "monthly_income_amount": self._format_decimal(monthly_income),
            "net_cash_flow_amount": self._format_decimal(net_cash_flow),
            "savings_rate_percent": float(savings.rate_percent),
            "savings_status": savings.status,
            "monthly_budget_amount": self._format_decimal(monthly_budget),
            "budgeted_spending_amount": self._format_decimal(budgeted_spending),
            "unbudgeted_spending_amount": self._format_decimal(unbudgeted_spending),
            "money_left_amount": self._format_decimal(money_left),
            "uncategorized_count": uncategorized_count,
            "days_elapsed": days_elapsed,
            "days_in_month": days_in_month,
            "average_daily_spend_amount": self._format_decimal(average_daily_spend),
            "expected_daily_spend_amount": self._format_decimal(expected_daily_spend),
            "projected_month_end_spend_amount": self._format_decimal(projected_month_end_spend),
            "projected_overspend_amount": self._format_decimal(projected_overspend),
            "budget_usage": budget_usage,
        }

    def _resolve_month(self, *, month: str | None, reference_day: date) -> tuple[date, date, str]:
        """Resolve the requested month, defaulting to the one the reference day is in."""
        month_value = month if month is not None else reference_day.strftime("%Y-%m")
        month_start, month_end = month_window(month_value)
        return month_start, month_end, month_value

    def _days_elapsed_in_month(self, *, month_start: date, reference_day: date, days_in_month: int) -> int:
        month_key = (month_start.year, month_start.month)
        reference_key = (reference_day.year, reference_day.month)
        if month_key < reference_key:
            return days_in_month
        if month_key > reference_key:
            return 0
        return min(reference_day.day, days_in_month)

    def _sum_account_balances(self) -> tuple[Decimal, str | None, int]:
        query = (
            select(
                Account.latest_balance_amount,
                Account.latest_balance_currency,
            )
            .where(Account.latest_balance_amount.is_not(None))
            .where(Account.included_in_calculations.is_(True))
        )

        rows = self.db.execute(query).all()
        total = sum((amount for amount, _currency in rows if amount is not None), start=Decimal("0.00"))
        currencies = sorted({currency for _amount, currency in rows if currency})
        currency = currencies[0] if len(currencies) == 1 else None
        return total.quantize(Decimal("0.01")), currency, len(rows)

    def _count_uncategorized_transactions(self, *, month_start: date, month_end: date) -> int:
        count_query = (
            select(func.count())
            .select_from(Transaction)
            .join(Account, Account.id == Transaction.account_id)
            .where(
                Account.included_in_calculations.is_(True),
                within_month(month_start=month_start, month_end=month_end),
                Transaction.category_id.is_(None),
                Transaction.excluded_at.is_(None),
            )
        )
        return self.db.scalar(count_query) or 0

    def _get_monthly_spend(self, *, month_start: date, month_end: date) -> SpendByStatus:
        status = func.lower(Transaction.status)
        rows = self.db.execute(
            select(
                status,
                func.coalesce(func.sum(Transaction.amount), Decimal("0.00")),
            )
            .select_from(Transaction)
            .join(Account, Account.id == Transaction.account_id)
            .join(Category, Category.id == Transaction.category_id)
            .where(
                Account.included_in_calculations.is_(True),
                within_month(month_start=month_start, month_end=month_end),
                status.in_(COMMITTED_STATUSES),
                Category.type == "expense",
            )
            .group_by(status)
        ).all()

        totals = {
            row_status: (-Decimal(total_amount)).quantize(Decimal("0.01"))
            for row_status, total_amount in rows
        }
        return SpendByStatus(
            booked=totals.get("booked", Decimal("0.00")),
            pending=totals.get("pending", Decimal("0.00")),
        )

    def _get_monthly_income(self, *, month_start: date, month_end: date) -> Decimal:
        total_amount = self.db.scalar(
            select(func.coalesce(func.sum(Transaction.amount), Decimal("0.00")))
            .select_from(Transaction)
            .join(Account, Account.id == Transaction.account_id)
            .join(Category, Category.id == Transaction.category_id)
            .where(
                Account.included_in_calculations.is_(True),
                within_month(month_start=month_start, month_end=month_end),
                func.lower(Transaction.status) == "booked",
                Category.type == "income",
            )
        ) or Decimal("0.00")
        # Income transactions are credits (positive amounts), so no sign flip.
        return Decimal(total_amount).quantize(Decimal("0.01"))

    def _get_active_budgets(self, *, month_start: date, month_end: date) -> list[ActiveBudgetWindow]:
        rows = self.db.execute(
            select(Budget, Category.name)
            .join(Category, Category.id == Budget.category_id)
            .where(
                Budget.active_from < month_end,
                or_(Budget.active_to.is_(None), Budget.active_to >= month_start),
            )
            .order_by(Category.name.asc(), Budget.active_from.desc(), Budget.created_at.desc())
        ).all()

        return [
            ActiveBudgetWindow(
                category_id=budget.category_id,
                category_name=category_name,
                amount=budget.amount.quantize(Decimal("0.01")),
                currency=budget.currency,
                is_fixed=budget.is_fixed,
            )
            for budget, category_name in rows
        ]

    def _get_budget_category_spend(
        self,
        *,
        month_start: date,
        month_end: date,
        category_ids: list[UUID],
    ) -> dict[UUID, SpendByStatus]:
        if not category_ids:
            return {}

        status = func.lower(Transaction.status)
        rows = self.db.execute(
            select(
                Transaction.category_id,
                status,
                func.coalesce(func.sum(Transaction.amount), Decimal("0.00")),
            )
            .select_from(Transaction)
            .join(Account, Account.id == Transaction.account_id)
            .where(
                Account.included_in_calculations.is_(True),
                within_month(month_start=month_start, month_end=month_end),
                status.in_(COMMITTED_STATUSES),
                Transaction.category_id.in_(category_ids),
            )
            .group_by(Transaction.category_id, status)
        ).all()

        booked: dict[UUID, Decimal] = {}
        pending: dict[UUID, Decimal] = {}
        for category_id, row_status, total_amount in rows:
            if category_id is None:
                continue
            bucket = booked if row_status == "booked" else pending
            bucket[category_id] = (-Decimal(total_amount)).quantize(Decimal("0.01"))

        return {
            category_id: SpendByStatus(
                booked=booked.get(category_id, Decimal("0.00")),
                pending=pending.get(category_id, Decimal("0.00")),
            )
            for category_id in booked.keys() | pending.keys()
        }

    def _serialize_budget_usage(
        self,
        *,
        budget: ActiveBudgetWindow,
        spend: SpendByStatus,
    ) -> dict[str, Any]:
        spent_amount = self._counted_spend(spend=spend, is_fixed=budget.is_fixed)
        remaining_amount = (budget.amount - spent_amount).quantize(Decimal("0.01"))
        utilization = (spent_amount / budget.amount * Decimal("100.0")).quantize(Decimal("0.1"))
        status = budget_usage_status(remaining_amount=remaining_amount, utilization_percent=utilization)

        return {
            "category_id": str(budget.category_id),
            "category_name": budget.category_name,
            "budget_amount": self._format_decimal(budget.amount),
            "spent_amount": self._format_decimal(spent_amount),
            "remaining_amount": self._format_decimal(remaining_amount),
            "currency": budget.currency,
            "utilization_percent": float(utilization),
            "status": status,
            "is_fixed": budget.is_fixed,
        }

    def _counted_spend(self, *, spend: SpendByStatus, is_fixed: bool) -> Decimal:
        """How much of a category's spend a budget-basis figure counts.

        A variable category counts pending spend; a fixed one does not, because a
        hold on a bill is not the bill being paid and its row has to keep reading as
        not yet paid. Both the rows and the totals beside them read this, so the two
        cannot drift apart.
        """
        return spend.booked if is_fixed else spend.total

    def _budget_usage_sort_key(self, row: dict[str, Any]) -> tuple[int, float, str]:
        priority: dict[MetricStatus, int] = {"over": 0, "watch": 1, "on_track": 2}
        return priority[row["status"]], -row["utilization_percent"], row["category_name"].lower()

    def _project_fixed(self, *, budget: ActiveBudgetWindow, spent: Decimal) -> Decimal:
        """Step projection for a fixed/lump budget (rent, utilities).

        Once any spend has booked in the category we trust the actual amount -- it can
        land over or under the budgeted estimate. Until the charge appears we assume it
        will cost the budgeted amount. Never rate-extrapolated.

        ``spent`` must be the category's *booked* spend. A pending pre-authorization
        is not the bill being paid, and passing it here would project a 900.00 rent as
        the 1.00 the bank is holding.
        """
        if spent > 0:
            return spent.quantize(Decimal("0.01"))
        return budget.amount.quantize(Decimal("0.01"))

    def _extrapolate_spend(
        self, *, spend_to_date: Decimal, days_elapsed: int, days_in_month: int
    ) -> Decimal:
        """Straight linear extrapolation of spend to the full month (no budget prior)."""
        if days_elapsed <= 0:
            return Decimal("0.00")
        if days_elapsed >= days_in_month:
            return spend_to_date.quantize(Decimal("0.01"))
        daily = spend_to_date / Decimal(days_elapsed)
        return (daily * Decimal(days_in_month)).quantize(Decimal("0.01"))

    def _project_spend(
        self,
        *,
        spend_to_date: Decimal,
        budget_reference: Decimal,
        days_elapsed: int,
        days_in_month: int,
    ) -> Decimal:
        """Budget-anchored, confidence-weighted full-month spend projection.

        The remaining-day daily rate blends the observed pace with the budgeted
        pace, weighted by ``days_elapsed / days_in_month``. Early in the month the
        budget dominates (little signal); late in the month the observed pace does.
        """
        if days_elapsed <= 0:
            # No signal yet: assume spending simply tracks the budget.
            return budget_reference.quantize(Decimal("0.01"))
        if days_elapsed >= days_in_month:
            return spend_to_date.quantize(Decimal("0.01"))

        days_remaining = days_in_month - days_elapsed
        confidence = Decimal(days_elapsed) / Decimal(days_in_month)
        actual_daily = spend_to_date / Decimal(days_elapsed)
        budget_daily = budget_reference / Decimal(days_in_month)
        blended_daily = confidence * actual_daily + (Decimal("1") - confidence) * budget_daily
        return (spend_to_date + Decimal(days_remaining) * blended_daily).quantize(Decimal("0.01"))

    def _format_decimal(self, value: Decimal) -> str:
        return format(value.quantize(Decimal("0.01")), ".2f")

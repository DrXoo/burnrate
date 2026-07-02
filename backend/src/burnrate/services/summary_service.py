from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, date, datetime
from decimal import Decimal
from typing import Any
from uuid import UUID

from sqlalchemy import func, or_, select
from sqlalchemy.orm import Session

from burnrate.db.models import Account, Budget, Category, Transaction


@dataclass(frozen=True)
class ActiveBudgetWindow:
    category_id: UUID
    category_name: str
    amount: Decimal
    currency: str


@dataclass(frozen=True)
class RunwayAccountBalance:
    account_id: UUID
    display_name: str
    balance_amount: Decimal
    balance_currency: str | None


class SummaryService:
    def __init__(self, *, db: Session) -> None:
        self.db = db

    def get_summary(
        self,
        *,
        month: str | None = None,
        today: date | None = None,
    ) -> dict[str, Any]:
        reference_day = today or datetime.now(UTC).date()
        month_start, month_end, month_value = self._resolve_month(month=month, reference_day=reference_day)
        days_in_month = (month_end - month_start).days
        days_elapsed = self._days_elapsed_in_month(
            month_start=month_start,
            reference_day=reference_day,
            days_in_month=days_in_month,
        )

        calculation_balance, calculation_currency, _ = self._sum_account_balances(runway_only=False)
        runway_balance, runway_currency, runway_accounts = self._get_runway_accounts()
        uncategorized_count = self._count_uncategorized_transactions(
            month_start=month_start,
            month_end=month_end,
        )

        active_budgets = self._get_active_budgets(month_start=month_start, month_end=month_end)
        monthly_budget = sum((budget.amount for budget in active_budgets), start=Decimal("0.00"))

        monthly_spending = self._get_monthly_spending(month_start=month_start, month_end=month_end)
        monthly_income = self._get_monthly_income(month_start=month_start, month_end=month_end)
        # Net cash flow this month: what landed in income categories minus what left
        # in expense categories. Transfers are excluded on both sides. Pure reporting
        # of booked transactions -- it does not feed runway or projections.
        net_cash_flow = (monthly_income - monthly_spending).quantize(Decimal("0.01"))
        spent_by_budget_category = self._get_budget_category_spend(
            month_start=month_start,
            month_end=month_end,
            category_ids=[budget.category_id for budget in active_budgets],
        )
        budgeted_spending = sum(spent_by_budget_category.values(), start=Decimal("0.00"))
        # Spend in categorized expense categories that have no budget. Together with
        # budgeted_spending this reconciles monthly_spending (= budgeted + unbudgeted),
        # so the dashboard's two spend figures no longer look like they disagree.
        unbudgeted_spending = (monthly_spending - budgeted_spending).quantize(Decimal("0.01"))
        money_left = monthly_budget - budgeted_spending

        average_daily_spend = Decimal("0.00")
        if days_elapsed > 0:
            average_daily_spend = (monthly_spending / Decimal(days_elapsed)).quantize(Decimal("0.01"))

        # Full-month spend projections. When budgets exist we regress the observed
        # daily pace toward the budgeted pace, weighted by how far into the month we
        # are, so an early-month spike (e.g. rent on day 1) doesn't blow the
        # projection out of proportion. Overspend/runway compare on the *budgeted*
        # basis so both sides live in the same universe as the budget. Without
        # budgets there is no prior to lean on, so we fall back to a straight linear
        # extrapolation of actual spend.
        if monthly_budget > 0:
            projected_month_end_spend = self._project_spend(
                spend_to_date=monthly_spending,
                budget_reference=monthly_budget,
                days_elapsed=days_elapsed,
                days_in_month=days_in_month,
            )
            projected_budgeted_spend = self._project_spend(
                spend_to_date=budgeted_spending,
                budget_reference=monthly_budget,
                days_elapsed=days_elapsed,
                days_in_month=days_in_month,
            )
        else:
            projected_month_end_spend = self._extrapolate_spend(
                spend_to_date=monthly_spending,
                days_elapsed=days_elapsed,
                days_in_month=days_in_month,
            )
            projected_budgeted_spend = projected_month_end_spend

        projected_overspend = max(projected_budgeted_spend - monthly_budget, Decimal("0.00"))
        runway_drain_amount, runway_drain_label = self._runway_drain(
            projected_month_end_spend=projected_month_end_spend,
            projected_overspend=projected_overspend,
            monthly_budget=monthly_budget,
        )
        runway_months_left = None
        if runway_drain_amount > 0 and runway_balance > 0:
            runway_months_left = (runway_balance / runway_drain_amount).quantize(Decimal("0.01"))

        budget_usage = [
            self._serialize_budget_usage(
                budget=budget,
                spent_amount=spent_by_budget_category.get(budget.category_id, Decimal("0.00")),
            )
            for budget in sorted(
                active_budgets,
                key=lambda item: (
                    self._budget_usage_sort_key(
                        budget_amount=item.amount,
                        spent_amount=spent_by_budget_category.get(item.category_id, Decimal("0.00")),
                    ),
                    item.category_name.lower(),
                ),
            )
        ]

        return {
            "month": month_value,
            "current_balance_amount": self._format_decimal(calculation_balance),
            "current_balance_currency": calculation_currency,
            "runway_balance_amount": self._format_decimal(runway_balance),
            "runway_balance_currency": runway_currency,
            "runway_account_count": len(runway_accounts),
            "runway_accounts": [
                {
                    "account_id": str(account.account_id),
                    "display_name": account.display_name,
                    "balance_amount": self._format_decimal(account.balance_amount),
                    "balance_currency": account.balance_currency,
                }
                for account in runway_accounts
            ],
            "runway_drain_amount": self._format_decimal(runway_drain_amount),
            "runway_drain_currency": runway_currency or calculation_currency,
            "runway_drain_label": runway_drain_label,
            "runway_message": self._runway_message(
                runway_accounts=runway_accounts,
                monthly_budget=monthly_budget,
                runway_drain_amount=runway_drain_amount,
            ),
            "monthly_spending_amount": self._format_decimal(monthly_spending),
            "monthly_income_amount": self._format_decimal(monthly_income),
            "net_cash_flow_amount": self._format_decimal(net_cash_flow),
            "monthly_budget_amount": self._format_decimal(monthly_budget),
            "budgeted_spending_amount": self._format_decimal(budgeted_spending),
            "unbudgeted_spending_amount": self._format_decimal(unbudgeted_spending),
            "money_left_amount": self._format_decimal(money_left),
            "uncategorized_count": uncategorized_count,
            "days_elapsed": days_elapsed,
            "days_in_month": days_in_month,
            "average_daily_spend_amount": self._format_decimal(average_daily_spend),
            "projected_month_end_spend_amount": self._format_decimal(projected_month_end_spend),
            "projected_overspend_amount": self._format_decimal(projected_overspend),
            "runway_months_left": self._format_decimal(runway_months_left) if runway_months_left is not None else None,
            "runway_status": self._runway_status(
                runway_drain_amount=runway_drain_amount,
                runway_months_left=runway_months_left,
                runway_account_count=len(runway_accounts),
            ),
            "budget_usage": budget_usage,
        }

    def _resolve_month(self, *, month: str | None, reference_day: date) -> tuple[date, date, str]:
        if month is None:
            month_value = reference_day.strftime("%Y-%m")
            month_start = date(reference_day.year, reference_day.month, 1)
        else:
            month_start = self._parse_month(month)
            month_value = month

        if month_start.month == 12:
            month_end = date(month_start.year + 1, 1, 1)
        else:
            month_end = date(month_start.year, month_start.month + 1, 1)

        return month_start, month_end, month_value

    def _parse_month(self, value: str) -> date:
        try:
            year_text, month_text = value.split("-", maxsplit=1)
            month_start = date(int(year_text), int(month_text), 1)
        except (TypeError, ValueError) as exc:
            raise ValueError("Month must use YYYY-MM format") from exc

        return month_start

    def _days_elapsed_in_month(self, *, month_start: date, reference_day: date, days_in_month: int) -> int:
        month_key = (month_start.year, month_start.month)
        reference_key = (reference_day.year, reference_day.month)
        if month_key < reference_key:
            return days_in_month
        if month_key > reference_key:
            return 0
        return min(reference_day.day, days_in_month)

    def _sum_account_balances(self, *, runway_only: bool) -> tuple[Decimal, str | None, int]:
        query = select(
            Account.latest_balance_amount,
            Account.latest_balance_currency,
        ).where(Account.latest_balance_amount.is_not(None))

        if runway_only:
            query = query.where(Account.included_in_runway.is_(True))
        else:
            query = query.where(Account.included_in_calculations.is_(True))

        rows = self.db.execute(query).all()
        total = sum((amount for amount, _currency in rows if amount is not None), start=Decimal("0.00"))
        currencies = sorted({currency for _amount, currency in rows if currency})
        currency = currencies[0] if len(currencies) == 1 else None
        return total.quantize(Decimal("0.01")), currency, len(rows)

    def _get_runway_accounts(self) -> tuple[Decimal, str | None, list[RunwayAccountBalance]]:
        rows = self.db.execute(
            select(
                Account.id,
                Account.display_name,
                Account.latest_balance_amount,
                Account.latest_balance_currency,
            )
            .where(
                Account.included_in_runway.is_(True),
                Account.latest_balance_amount.is_not(None),
            )
            .order_by(Account.display_name.asc(), Account.created_at.asc())
        ).all()

        accounts = [
            RunwayAccountBalance(
                account_id=account_id,
                display_name=display_name,
                balance_amount=balance_amount.quantize(Decimal("0.01")),
                balance_currency=balance_currency,
            )
            for account_id, display_name, balance_amount, balance_currency in rows
            if balance_amount is not None
        ]
        total = sum((account.balance_amount for account in accounts), start=Decimal("0.00"))
        currencies = sorted({account.balance_currency for account in accounts if account.balance_currency})
        currency = currencies[0] if len(currencies) == 1 else None
        return total.quantize(Decimal("0.01")), currency, accounts

    def _count_uncategorized_transactions(self, *, month_start: date, month_end: date) -> int:
        count_query = (
            select(func.count())
            .select_from(Transaction)
            .join(Account, Account.id == Transaction.account_id)
            .where(
                Account.included_in_calculations.is_(True),
                Transaction.booking_date >= month_start,
                Transaction.booking_date < month_end,
                Transaction.category_id.is_(None),
            )
        )
        return self.db.scalar(count_query) or 0

    def _get_monthly_spending(self, *, month_start: date, month_end: date) -> Decimal:
        total_amount = self.db.scalar(
            select(func.coalesce(func.sum(Transaction.amount), Decimal("0.00")))
            .select_from(Transaction)
            .join(Account, Account.id == Transaction.account_id)
            .join(Category, Category.id == Transaction.category_id)
            .where(
                Account.included_in_calculations.is_(True),
                Transaction.booking_date >= month_start,
                Transaction.booking_date < month_end,
                func.lower(Transaction.status) == "booked",
                Category.type == "expense",
            )
        ) or Decimal("0.00")
        return (-Decimal(total_amount)).quantize(Decimal("0.01"))

    def _get_monthly_income(self, *, month_start: date, month_end: date) -> Decimal:
        total_amount = self.db.scalar(
            select(func.coalesce(func.sum(Transaction.amount), Decimal("0.00")))
            .select_from(Transaction)
            .join(Account, Account.id == Transaction.account_id)
            .join(Category, Category.id == Transaction.category_id)
            .where(
                Account.included_in_calculations.is_(True),
                Transaction.booking_date >= month_start,
                Transaction.booking_date < month_end,
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
            )
            for budget, category_name in rows
        ]

    def _get_budget_category_spend(
        self,
        *,
        month_start: date,
        month_end: date,
        category_ids: list[UUID],
    ) -> dict[UUID, Decimal]:
        if not category_ids:
            return {}

        rows = self.db.execute(
            select(
                Transaction.category_id,
                func.coalesce(func.sum(Transaction.amount), Decimal("0.00")),
            )
            .select_from(Transaction)
            .join(Account, Account.id == Transaction.account_id)
            .where(
                Account.included_in_calculations.is_(True),
                Transaction.booking_date >= month_start,
                Transaction.booking_date < month_end,
                func.lower(Transaction.status) == "booked",
                Transaction.category_id.in_(category_ids),
            )
            .group_by(Transaction.category_id)
        ).all()

        return {
            category_id: (-Decimal(total_amount)).quantize(Decimal("0.01"))
            for category_id, total_amount in rows
            if category_id is not None
        }

    def _serialize_budget_usage(
        self,
        *,
        budget: ActiveBudgetWindow,
        spent_amount: Decimal,
    ) -> dict[str, Any]:
        remaining_amount = (budget.amount - spent_amount).quantize(Decimal("0.01"))
        utilization = (spent_amount / budget.amount * Decimal("100.0")).quantize(Decimal("0.1"))
        status = self._budget_usage_status(remaining_amount=remaining_amount, utilization=utilization)

        return {
            "category_id": str(budget.category_id),
            "category_name": budget.category_name,
            "budget_amount": self._format_decimal(budget.amount),
            "spent_amount": self._format_decimal(spent_amount),
            "remaining_amount": self._format_decimal(remaining_amount),
            "currency": budget.currency,
            "utilization_percent": float(utilization),
            "status": status,
        }

    def _budget_usage_sort_key(self, *, budget_amount: Decimal, spent_amount: Decimal) -> tuple[int, Decimal]:
        remaining_amount = budget_amount - spent_amount
        utilization = (spent_amount / budget_amount * Decimal("100.0")).quantize(Decimal("0.1"))
        status = self._budget_usage_status(remaining_amount=remaining_amount, utilization=utilization)
        priority = {"over": 0, "watch": 1, "on_track": 2}[status]
        return priority, -utilization

    def _budget_usage_status(self, *, remaining_amount: Decimal, utilization: Decimal) -> str:
        if remaining_amount < 0:
            return "over"
        if utilization >= Decimal("85.0"):
            return "watch"
        return "on_track"

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

    def _runway_drain(
        self,
        *,
        projected_month_end_spend: Decimal,
        projected_overspend: Decimal,
        monthly_budget: Decimal,
    ) -> tuple[Decimal, str]:
        if monthly_budget > 0:
            return projected_overspend, "Projected overspend"
        return projected_month_end_spend, "Projected monthly spend"

    def _runway_message(
        self,
        *,
        runway_accounts: list[RunwayAccountBalance],
        monthly_budget: Decimal,
        runway_drain_amount: Decimal,
    ) -> str:
        if not runway_accounts:
            return "Select one or more reserve accounts to activate runway tracking."
        if runway_drain_amount <= 0:
            return "Current spending is within the active monthly budget, so runway is not being consumed."
        if monthly_budget <= 0:
            return "No active budgets are configured, so runway uses projected monthly spending as the drain."
        return "Runway is based on projected monthly overspend against the active category budgets."

    def _runway_status(
        self,
        *,
        runway_drain_amount: Decimal,
        runway_months_left: Decimal | None,
        runway_account_count: int,
    ) -> str:
        if runway_account_count == 0:
            return "not_available"
        if runway_drain_amount <= 0:
            return "stable"
        if runway_months_left is None or runway_months_left < Decimal("3.00"):
            return "critical"
        if runway_months_left < Decimal("6.00"):
            return "watch"
        return "stable"

    def _format_decimal(self, value: Decimal) -> str:
        return format(value.quantize(Decimal("0.01")), ".2f")

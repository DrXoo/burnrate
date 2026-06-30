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
        runway_balance, runway_currency, runway_accounts = self._sum_account_balances(runway_only=True)
        uncategorized_count = self._count_uncategorized_transactions(
            month_start=month_start,
            month_end=month_end,
        )

        active_budgets = self._get_active_budgets(month_start=month_start, month_end=month_end)
        monthly_budget = sum((budget.amount for budget in active_budgets), start=Decimal("0.00"))

        monthly_spending = self._get_monthly_spending(month_start=month_start, month_end=month_end)
        spent_by_budget_category = self._get_budget_category_spend(
            month_start=month_start,
            month_end=month_end,
            category_ids=[budget.category_id for budget in active_budgets],
        )
        budgeted_spending = sum(spent_by_budget_category.values(), start=Decimal("0.00"))
        money_left = monthly_budget - budgeted_spending

        raw_average_daily_spend = Decimal("0.00")
        average_daily_spend = Decimal("0.00")
        projected_month_end_spend = Decimal("0.00")
        if days_elapsed > 0:
            raw_average_daily_spend = monthly_spending / Decimal(days_elapsed)
            average_daily_spend = raw_average_daily_spend.quantize(Decimal("0.01"))
            if days_elapsed == days_in_month:
                projected_month_end_spend = monthly_spending
            else:
                projected_month_end_spend = (raw_average_daily_spend * Decimal(days_in_month)).quantize(
                    Decimal("0.01")
                )

        projected_overspend = max(projected_month_end_spend - monthly_budget, Decimal("0.00"))
        runway_months_left = None
        if projected_overspend > 0 and runway_balance > 0:
            runway_months_left = (runway_balance / projected_overspend).quantize(Decimal("0.01"))

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
            "monthly_spending_amount": self._format_decimal(monthly_spending),
            "monthly_budget_amount": self._format_decimal(monthly_budget),
            "budgeted_spending_amount": self._format_decimal(budgeted_spending),
            "money_left_amount": self._format_decimal(money_left),
            "uncategorized_count": uncategorized_count,
            "days_elapsed": days_elapsed,
            "days_in_month": days_in_month,
            "average_daily_spend_amount": self._format_decimal(average_daily_spend),
            "projected_month_end_spend_amount": self._format_decimal(projected_month_end_spend),
            "projected_overspend_amount": self._format_decimal(projected_overspend),
            "runway_months_left": self._format_decimal(runway_months_left) if runway_months_left is not None else None,
            "runway_status": self._runway_status(
                projected_overspend=projected_overspend,
                runway_months_left=runway_months_left,
                runway_accounts=runway_accounts,
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

    def _runway_status(
        self,
        *,
        projected_overspend: Decimal,
        runway_months_left: Decimal | None,
        runway_accounts: int,
    ) -> str:
        if runway_accounts == 0:
            return "not_available"
        if projected_overspend <= 0:
            return "stable"
        if runway_months_left is None or runway_months_left < Decimal("3.00"):
            return "critical"
        if runway_months_left < Decimal("6.00"):
            return "watch"
        return "stable"

    def _format_decimal(self, value: Decimal) -> str:
        return format(value.quantize(Decimal("0.01")), ".2f")

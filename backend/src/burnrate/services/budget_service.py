from __future__ import annotations

from datetime import date, timedelta
from decimal import Decimal
from typing import Any
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.orm import Session

from burnrate.clock import civil_date
from burnrate.db.models import Budget, Category


class BudgetService:
    def __init__(self, *, db: Session, timezone_name: str = "UTC") -> None:
        self.db = db
        self._timezone_name = timezone_name

    def _civil_today(self) -> date:
        return civil_date(timezone_name=self._timezone_name)

    def list_budgets(self) -> list[dict[str, Any]]:
        rows = self.db.execute(
            select(Budget, Category.name, Category.type)
            .join(Category, Category.id == Budget.category_id)
            .order_by(Category.name.asc(), Budget.active_from.desc(), Budget.created_at.desc())
        ).all()
        today = self._civil_today()
        return [
            self._serialize_budget(
                budget=budget,
                category_name=category_name,
                category_type=category_type,
                today=today,
            )
            for budget, category_name, category_type in rows
        ]

    def create_budget(
        self,
        *,
        category_id: str,
        amount: Decimal,
        currency: str,
        active_from: date,
        is_fixed: bool = False,
    ) -> dict[str, Any]:
        category = self._resolve_budget_category(category_id)
        normalized_currency = self._normalize_currency(currency)
        normalized_amount = self._normalize_amount(amount)
        self._validate_month_start(active_from)

        previous_budget = self._find_open_budget_before_date(
            category_id=category.id,
            active_from=active_from,
        )
        if previous_budget is not None:
            previous_budget.active_to = active_from - timedelta(days=1)

        self._ensure_no_overlap(category_id=category.id, active_from=active_from)

        budget = Budget(
            category_id=category.id,
            amount=normalized_amount,
            currency=normalized_currency,
            period_type="monthly",
            active_from=active_from,
            active_to=None,
            is_fixed=is_fixed,
        )
        self.db.add(budget)
        self.db.flush()

        return self._serialize_budget(
            budget=budget,
            category_name=category.name,
            category_type=category.type,
            today=self._civil_today(),
        )

    def update_budget(
        self,
        *,
        budget_id: str,
        amount: Decimal,
        currency: str,
        is_fixed: bool | None = None,
    ) -> dict[str, Any]:
        budget = self.db.get(Budget, self._parse_uuid(budget_id, "Budget id"))
        if budget is None:
            raise ValueError(f"Budget not found for id {budget_id}")

        category = self.db.get(Category, budget.category_id)
        assert category is not None

        budget.amount = self._normalize_amount(amount)
        budget.currency = self._normalize_currency(currency)
        if is_fixed is not None:
            budget.is_fixed = is_fixed

        return self._serialize_budget(
            budget=budget,
            category_name=category.name,
            category_type=category.type,
            today=self._civil_today(),
        )

    def deactivate_budget(self, *, budget_id: str) -> dict[str, Any]:
        budget = self.db.get(Budget, self._parse_uuid(budget_id, "Budget id"))
        if budget is None:
            raise ValueError(f"Budget not found for id {budget_id}")

        category = self.db.get(Category, budget.category_id)
        assert category is not None

        today = self._civil_today()
        if budget.active_from >= today:
            # A budget that has not actually started yet (starts today or later)
            # becomes inactive immediately rather than staying active for today.
            budget.active_to = budget.active_from - timedelta(days=1)
        else:
            budget.active_to = today

        return self._serialize_budget(
            budget=budget,
            category_name=category.name,
            category_type=category.type,
            today=today,
        )

    def _serialize_budget(
        self,
        *,
        budget: Budget,
        category_name: str,
        category_type: str,
        today: date,
    ) -> dict[str, Any]:
        status = self._budget_status(budget, today=today)
        return {
            "budget_id": str(budget.id),
            "category_id": str(budget.category_id),
            "category_name": category_name,
            "category_type": category_type,
            "amount": f"{budget.amount:.2f}",
            "currency": budget.currency,
            "period_type": budget.period_type,
            "active_from": budget.active_from,
            "active_to": budget.active_to,
            "is_fixed": budget.is_fixed,
            "active": status == "active",
            "status": status,
        }

    def _resolve_budget_category(self, category_id: str) -> Category:
        category = self.db.get(Category, self._parse_uuid(category_id, "Category id"))
        if category is None:
            raise ValueError(f"Category not found for id {category_id}")
        if not category.active:
            raise ValueError(f"Category '{category.name}' is inactive")
        if category.type != "expense":
            raise ValueError("Budgets are only supported for expense categories")
        return category

    def _find_open_budget_before_date(self, *, category_id: UUID, active_from: date) -> Budget | None:
        budgets = self.db.scalars(
            select(Budget)
            .where(Budget.category_id == category_id)
            .order_by(Budget.active_from.desc(), Budget.created_at.desc())
        ).all()
        for budget in budgets:
            if budget.active_to is None and budget.active_from < active_from:
                return budget
        return None

    def _ensure_no_overlap(self, *, category_id: UUID, active_from: date) -> None:
        new_end = date.max
        budgets = self.db.scalars(
            select(Budget)
            .where(Budget.category_id == category_id)
            .order_by(Budget.active_from.asc(), Budget.created_at.asc())
        ).all()
        for budget in budgets:
            budget_end = budget.active_to or date.max
            if budget.active_from <= new_end and active_from <= budget_end:
                raise ValueError("Budget periods must not overlap for the same category")

    def _budget_status(self, budget: Budget, *, today: date) -> str:
        if budget.active_to is not None and budget.active_to < budget.active_from:
            return "inactive"
        if today < budget.active_from:
            return "scheduled"
        if budget.active_to is not None and today > budget.active_to:
            return "inactive"
        return "active"

    def _normalize_currency(self, value: str) -> str:
        normalized = value.strip().upper()
        if len(normalized) != 3 or not normalized.isalpha():
            raise ValueError("Currency must be a 3-letter code")
        return normalized

    def _normalize_amount(self, value: Decimal) -> Decimal:
        if value <= 0:
            raise ValueError("Budget amount must be greater than zero")
        return value.quantize(Decimal("0.01"))

    def _validate_month_start(self, value: date) -> None:
        if value.day != 1:
            raise ValueError("Budget active_from must be the first day of a month")

    def _parse_uuid(self, value: str, label: str) -> UUID:
        try:
            return UUID(value)
        except ValueError as exc:
            raise ValueError(f"{label} must be a valid UUID") from exc

from __future__ import annotations

from datetime import date
from decimal import Decimal
from typing import Literal

from pydantic import BaseModel, Field


class BudgetSummaryResponse(BaseModel):
    budget_id: str
    category_id: str
    category_name: str
    category_type: Literal["expense", "income", "transfer"]
    amount: str
    currency: str
    period_type: Literal["monthly"]
    active_from: date
    active_to: date | None = None
    is_fixed: bool = False
    active: bool
    status: Literal["active", "scheduled", "inactive"]
    # Whether reopening this row would be accepted. Decided in the backend, with the
    # same function the reactivate endpoint refuses with, so an interface never offers
    # a restore that is always rejected.
    can_reactivate: bool = False


class BudgetListResponse(BaseModel):
    budgets: list[BudgetSummaryResponse]


class CreateBudgetRequest(BaseModel):
    category_id: str
    amount: Decimal = Field(gt=0, decimal_places=2)
    currency: str = Field(min_length=3, max_length=3, default="EUR")
    active_from: date
    is_fixed: bool = False


class UpdateBudgetRequest(BaseModel):
    amount: Decimal = Field(gt=0, decimal_places=2)
    currency: str = Field(min_length=3, max_length=3)
    is_fixed: bool | None = None

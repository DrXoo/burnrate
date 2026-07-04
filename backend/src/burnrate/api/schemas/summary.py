from __future__ import annotations

from typing import Literal

from pydantic import BaseModel


class BudgetUsageResponse(BaseModel):
    category_id: str
    category_name: str
    budget_amount: str
    spent_amount: str
    remaining_amount: str
    currency: str
    utilization_percent: float
    status: Literal["on_track", "watch", "over"]
    is_fixed: bool = False


class RunwayAccountResponse(BaseModel):
    account_id: str
    display_name: str
    balance_amount: str
    balance_currency: str | None


class SummaryResponse(BaseModel):
    month: str
    current_balance_amount: str
    current_balance_currency: str | None
    runway_balance_amount: str
    runway_balance_currency: str | None
    runway_account_count: int
    runway_accounts: list[RunwayAccountResponse]
    runway_drain_amount: str
    runway_drain_currency: str | None
    runway_drain_label: str
    runway_message: str
    monthly_spending_amount: str
    monthly_income_amount: str
    net_cash_flow_amount: str
    monthly_budget_amount: str
    budgeted_spending_amount: str
    unbudgeted_spending_amount: str
    money_left_amount: str
    uncategorized_count: int
    days_elapsed: int
    days_in_month: int
    average_daily_spend_amount: str
    expected_daily_spend_amount: str
    projected_month_end_spend_amount: str
    projected_overspend_amount: str
    runway_months_left: str | None
    runway_status: Literal["stable", "watch", "critical", "not_available"]
    budget_usage: list[BudgetUsageResponse]

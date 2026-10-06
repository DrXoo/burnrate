from __future__ import annotations

from pydantic import BaseModel

from burnrate.domain.metrics import MetricStatus


class BudgetUsageResponse(BaseModel):
    category_id: str
    category_name: str
    budget_amount: str
    spent_amount: str
    remaining_amount: str
    currency: str
    utilization_percent: float
    status: MetricStatus
    is_fixed: bool = False


class SummaryResponse(BaseModel):
    month: str
    current_balance_amount: str
    current_balance_currency: str | None
    monthly_spending_amount: str
    pending_spend_amount: str
    monthly_income_amount: str
    net_cash_flow_amount: str
    savings_rate_percent: float
    savings_status: MetricStatus
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
    budget_usage: list[BudgetUsageResponse]

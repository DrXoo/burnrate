from __future__ import annotations

from pydantic import BaseModel

from burnrate.domain.baselines import BaselineComparisonStatus, BaselineStatus
from burnrate.domain.metrics import MetricStatus, SafeToSpendStatus


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


class FigureBaselineResponse(BaseModel):
    """One whole-month figure against its own normal.

    Shared by the two figures a band reads sensibly on. Net cash flow has no entry
    here on purpose: a ratio on a figure that can cross zero means nothing, and an
    owner whose usual month is a deficit would carry a negative baseline that the
    band logic reads as no baseline at all.
    """

    baseline_amount: str | None
    deviation_percent: float | None
    comparison_status: BaselineComparisonStatus


class CategoryBaselineResponse(BaseModel):
    """One category's month against its own normal.

    A list of its own rather than fields on ``BudgetUsageResponse``: that list is
    built from active budgets, so a category the owner spends in but never budgeted
    would be silently missing -- which is exactly the money Unbudgeted Spend exists
    to disclose.

    ``spend_amount`` is the figure the comparison is about and can differ from the
    month's headline for the current month, because both sides are measured to the
    same day of the month. A standing order due later in the month counts toward the
    month's spending and not toward this.
    """

    category_id: str
    category_name: str
    spend_amount: str
    # Null rather than zero when the category is below the presence floor or there is
    # too little history: a zero reads as a real figure, which is the reason ADR-0002
    # already records for the allowance. It is "0.00" in the one case the floor does
    # not reach -- two months whose movements cancel out -- and ``comparison_status``
    # is then ``no_baseline``, which is the field a client must read. A client keying
    # on the amount published "normally 0.00 · no baseline yet".
    baseline_amount: str | None
    deviation_percent: float | None
    comparison_status: BaselineComparisonStatus


class SummaryResponse(BaseModel):
    month: str
    # The month the owner is in, on the owner's own clock. A client compares the month
    # it asked for against this to decide tense, rather than against a month of its own.
    current_month: str
    # Null when there is no allowance to report, which the status distinguishes from
    # an allowance of zero: budgets exist, the month is current, they are used up.
    safe_to_spend_today_amount: str | None
    safe_to_spend_status: SafeToSpendStatus
    fixed_overrun_amount: str
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
    # Whether a comparison is offered and, when it is not, why not -- too little
    # trustworthy history, or a month with no outcome yet. Named here so no client
    # infers the reason from an empty list or from the allowance's own tense.
    baseline_status: BaselineStatus
    # How many Qualifying Months the means rest on, so the owner can see how much
    # to trust them. Uniform across categories, which is why it is not repeated on
    # each row.
    baseline_months_count: int
    category_baselines: list[CategoryBaselineResponse]
    # The spend the comparison can speak to, and the rest. Uncomparable Spend is the
    # residual -- monthly spending less the comparable half -- so the two reconcile
    # against the headline rather than against a third total of their own. Every euro
    # in it is one the comparison cannot speak to: a category with no baseline, a
    # category the owner archived, or spend dated after today's cutoff.
    comparable_spend_amount: str
    uncomparable_spend_amount: str
    comparable_spend_baseline: FigureBaselineResponse
    monthly_income_baseline: FigureBaselineResponse
    # Amount only, no verdict. See FigureBaselineResponse.
    net_cash_flow_baseline_amount: str | None

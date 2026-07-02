from __future__ import annotations

from burnrate.api.routes.summary import get_summary
from burnrate.main import create_app


class FakeSummaryService:
    def get_summary(self, *, month: str | None = None):
        assert month == "2026-06"
        return {
            "month": "2026-06",
            "current_balance_amount": "2000.00",
            "current_balance_currency": "EUR",
            "runway_balance_amount": "1500.00",
            "runway_balance_currency": "EUR",
            "runway_account_count": 1,
            "runway_accounts": [
                {
                    "account_id": "acc-2",
                    "display_name": "Savings",
                    "balance_amount": "1500.00",
                    "balance_currency": "EUR",
                }
            ],
            "runway_drain_amount": "120.00",
            "runway_drain_currency": "EUR",
            "runway_drain_label": "Projected overspend",
            "runway_message": "Runway is based on projected monthly overspend against the active category budgets.",
            "monthly_spending_amount": "260.00",
            "monthly_budget_amount": "400.00",
            "budgeted_spending_amount": "260.00",
            "unbudgeted_spending_amount": "0.00",
            "money_left_amount": "140.00",
            "uncategorized_count": 1,
            "days_elapsed": 15,
            "days_in_month": 30,
            "average_daily_spend_amount": "17.33",
            "projected_month_end_spend_amount": "519.90",
            "projected_overspend_amount": "119.90",
            "runway_months_left": "12.51",
            "runway_status": "stable",
            "budget_usage": [
                {
                    "category_id": "cat-1",
                    "category_name": "Utilities",
                    "budget_amount": "100.00",
                    "spent_amount": "120.00",
                    "remaining_amount": "-20.00",
                    "currency": "EUR",
                    "utilization_percent": 120.0,
                    "status": "over",
                }
            ],
        }


def test_summary_route_uses_service_dependency() -> None:
    response = get_summary(month="2026-06", service=FakeSummaryService())

    assert response.month == "2026-06"
    assert response.current_balance_amount == "2000.00"
    assert response.runway_accounts[0].display_name == "Savings"
    assert response.budget_usage[0].status == "over"


def test_app_exposes_phase_3_summary_path() -> None:
    app = create_app()
    paths = set(app.openapi()["paths"].keys())

    assert "/api/v1/summary" in paths

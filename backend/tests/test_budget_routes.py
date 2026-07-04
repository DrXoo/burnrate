from __future__ import annotations

from datetime import date
from decimal import Decimal

from burnrate.api.routes.budgets import create_budget, deactivate_budget, list_budgets, update_budget
from burnrate.api.schemas.budgets import CreateBudgetRequest, UpdateBudgetRequest
from burnrate.main import create_app


class FakeBudgetService:
    def list_budgets(self):
        return [
            {
                "budget_id": "budget-1",
                "category_id": "cat-1",
                "category_name": "Food",
                "category_type": "expense",
                "amount": "300.00",
                "currency": "EUR",
                "period_type": "monthly",
                "active_from": date(2026, 7, 1),
                "active_to": None,
                "is_fixed": False,
                "active": False,
                "status": "scheduled",
            }
        ]

    def create_budget(self, **_: object):
        return self.list_budgets()[0]

    def update_budget(self, *, budget_id: str, amount: Decimal, currency: str, is_fixed: bool | None = None):
        assert budget_id == "budget-1"
        payload = self.list_budgets()[0]
        payload["amount"] = f"{amount:.2f}"
        payload["currency"] = currency.upper()
        if is_fixed is not None:
            payload["is_fixed"] = is_fixed
        return payload

    def deactivate_budget(self, *, budget_id: str):
        assert budget_id == "budget-1"
        payload = self.list_budgets()[0]
        payload["active_to"] = date(2026, 6, 30)
        payload["status"] = "inactive"
        payload["active"] = False
        return payload


def test_budget_routes_use_service_dependency() -> None:
    service = FakeBudgetService()

    list_response = list_budgets(service=service)
    create_response = create_budget(
        CreateBudgetRequest(
            category_id="cat-1",
            amount=Decimal("300.00"),
            currency="EUR",
            active_from=date(2026, 7, 1),
        ),
        service=service,
    )
    update_response = update_budget(
        budget_id="budget-1",
        request=UpdateBudgetRequest(amount=Decimal("325.50"), currency="USD"),
        service=service,
    )
    deactivate_response = deactivate_budget(
        budget_id="budget-1",
        service=service,
    )

    assert list_response.budgets[0].category_name == "Food"
    assert create_response.amount == "300.00"
    assert update_response.currency == "USD"
    assert deactivate_response.status == "inactive"


def test_app_exposes_phase_3_budget_paths() -> None:
    app = create_app()
    paths = set(app.openapi()["paths"].keys())

    assert "/api/v1/budgets" in paths
    assert "/api/v1/budgets/{budget_id}" in paths
    assert "/api/v1/budgets/{budget_id}/deactivate" in paths

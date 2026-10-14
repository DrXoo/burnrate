from __future__ import annotations

from datetime import date
from decimal import Decimal

from burnrate.api.routes.budgets import (
    create_budget,
    deactivate_budget,
    list_budgets,
    reactivate_budget,
    update_budget,
)
from fastapi import HTTPException, status

from burnrate.api.schemas.budgets import CreateBudgetRequest, UpdateBudgetRequest
from burnrate.main import create_app


class FakeBudgetService:
    """A service that answers the month it was asked about, not a fixed payload.

    The row below starts in July 2026, so its status depends on the month it is read
    against: active for July onwards, scheduled for anything earlier. A fake that
    returned one status whatever was requested would agree with a route that dropped
    the month, which is the defect these tests exist to catch.
    """

    def list_budgets(self, *, month: str | None = None):
        reached_july = month is None or month >= "2026-07"
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
                "active": reached_july,
                "status": "active" if reached_july else "scheduled",
            }
        ]

    def create_budget(self, **_: object):
        return self.list_budgets()[0]

    def update_budget(
        self,
        *,
        budget_id: str,
        amount: Decimal,
        currency: str,
        is_fixed: bool | None = None,
        month: str | None = None,
    ):
        assert budget_id == "budget-1"
        payload = self.list_budgets()[0]
        payload["amount"] = f"{amount:.2f}"
        payload["currency"] = currency.upper()
        if is_fixed is not None:
            payload["is_fixed"] = is_fixed
        return payload

    def deactivate_budget(self, *, budget_id: str, month: str | None = None):
        self.cancelled_month = month
        assert budget_id == "budget-1"
        payload = self.list_budgets()[0]
        payload["active_to"] = date(2026, 6, 30)
        payload["status"] = "inactive"
        payload["active"] = False
        return payload

    def reactivate_budget(self, *, budget_id: str, month: str | None = None):
        self.reopened_month = month
        if budget_id != "budget-1":
            raise ValueError(f"Budget not found for id {budget_id}")
        payload = self.list_budgets()[0]
        payload["active_to"] = None
        payload["status"] = "active"
        payload["active"] = True
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


def test_budget_list_route_reads_the_status_against_the_month_being_viewed() -> None:
    """The month on screen reaches the service, so the list agrees with the summary.

    The route took no month at all, so the budgets page could only ever be told
    about the owner's current day while the summary beside it answered for the month
    being viewed.
    """
    service = FakeBudgetService()

    june = list_budgets(month="2026-06", service=service)
    july = list_budgets(month="2026-07", service=service)
    unspecified = list_budgets(service=service)

    # June is before the row starts; July is the month it begins.
    assert [row.status for row in june.budgets] == ["scheduled"]
    assert [row.status for row in july.budgets] == ["active"]
    # No month asked for means the month the owner is in, which the service resolves.
    assert [row.status for row in unspecified.budgets] == ["active"]


def test_budget_list_route_rejects_a_month_that_is_not_yyyy_mm() -> None:
    app = create_app()
    month_param = next(
        parameter
        for parameter in app.openapi()["paths"]["/api/v1/budgets"]["get"]["parameters"]
        if parameter["name"] == "month"
    )

    # The same pattern the summary route validates against, so one malformed month
    # cannot be a 422 on one endpoint and a 500 on the other.
    assert month_param["schema"]["anyOf"][0]["pattern"] == r"^\d{4}-\d{2}$"


def test_budget_reactivate_route_reopens_the_window() -> None:
    """Cancelling is undoable through its own endpoint, not by recreating the budget.

    A budget recreated instead would be a different row, so the months the cancelled
    one covered would answer differently depending on which row a figure read.
    """
    response = reactivate_budget(budget_id="budget-1", service=FakeBudgetService())

    assert response.active_to is None
    assert response.status == "active"


def test_budget_reactivate_route_reports_a_missing_budget_as_not_found() -> None:
    try:
        reactivate_budget(budget_id="budget-404", service=FakeBudgetService())
    except HTTPException as exc:
        assert exc.status_code == status.HTTP_404_NOT_FOUND
    else:
        raise AssertionError("expected a missing budget to be reported as 404")


def test_app_exposes_the_budget_reactivate_path() -> None:
    app = create_app()

    assert "/api/v1/budgets/{budget_id}/reactivate" in set(app.openapi()["paths"].keys())


def test_budget_mutation_routes_pass_the_month_being_viewed_through() -> None:
    """Cancelling and reopening answer for the month on screen, like listing does.

    The routes took no month, so the service fell back to the server's clock and a
    click made while paging through another month wrote that month's window.
    """
    service = FakeBudgetService()

    deactivate_budget(budget_id="budget-1", month="2026-09", service=service)
    reactivate_budget(budget_id="budget-1", month="2026-09", service=service)

    assert service.cancelled_month == "2026-09"
    assert service.reopened_month == "2026-09"


def test_every_budget_route_validates_the_month_the_same_way() -> None:
    """Compared against the list route's own schema rather than a restated pattern.

    These endpoints answer about the same month as each other, so one spelling of it
    must not be accepted by one and refused by another -- and asserting the shape by
    hand would pass while the two drifted.
    """
    app = create_app()
    paths = app.openapi()["paths"]

    def month_schema(path: str, method: str):
        params = paths[path][method].get("parameters", [])
        found = next((item for item in params if item["name"] == "month"), None)
        assert found is not None, f"{method.upper()} {path} takes no month"
        return found["schema"]

    expected = month_schema("/api/v1/budgets", "get")
    for path, method in (
        ("/api/v1/budgets", "post"),
        ("/api/v1/budgets/{budget_id}", "patch"),
        ("/api/v1/budgets/{budget_id}/deactivate", "post"),
        ("/api/v1/budgets/{budget_id}/reactivate", "post"),
    ):
        assert month_schema(path, method) == expected

from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query, status

from burnrate.api.dependencies import get_budget_service
from burnrate.api.schemas.budgets import (
    BudgetListResponse,
    BudgetSummaryResponse,
    CreateBudgetRequest,
    UpdateBudgetRequest,
)
from burnrate.services.budget_service import BudgetService

router = APIRouter(tags=["budgets"])


@router.get("/budgets", response_model=BudgetListResponse)
def list_budgets(
    month: Annotated[str | None, Query(pattern=r"^\d{4}-\d{2}$")] = None,
    service: BudgetService = Depends(get_budget_service),
) -> BudgetListResponse:
    """List every budget, with each row's status read against the month being viewed.

    The month is optional and defaults to the one the owner is in, matching
    ``/summary`` -- the two have to answer for the same month or the budgets page and
    the dashboard contradict each other.

    ``Annotated`` carries the query metadata so the default stays a real ``None``.
    Spelled as the default value instead, omitting the argument hands the callable a
    ``Query`` object, which only shows up when the function is called directly.
    """
    try:
        budgets = service.list_budgets(month=month)
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc

    return BudgetListResponse(budgets=budgets)


@router.post("/budgets", response_model=BudgetSummaryResponse, status_code=status.HTTP_201_CREATED)
def create_budget(
    request: CreateBudgetRequest,
    month: Annotated[str | None, Query(pattern=r"^\d{4}-\d{2}$")] = None,
    service: BudgetService = Depends(get_budget_service),
) -> BudgetSummaryResponse:
    try:
        payload = service.create_budget(
            category_id=request.category_id,
            amount=request.amount,
            currency=request.currency,
            active_from=request.active_from,
            is_fixed=request.is_fixed,
            month=month,
        )
    except ValueError as exc:
        message = str(exc)
        if "not found" in message.lower():
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=message) from exc
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=message) from exc

    return BudgetSummaryResponse.model_validate(payload)


@router.patch("/budgets/{budget_id}", response_model=BudgetSummaryResponse)
def update_budget(
    budget_id: str,
    request: UpdateBudgetRequest,
    month: Annotated[str | None, Query(pattern=r"^\d{4}-\d{2}$")] = None,
    service: BudgetService = Depends(get_budget_service),
) -> BudgetSummaryResponse:
    try:
        payload = service.update_budget(
            budget_id=budget_id,
            amount=request.amount,
            currency=request.currency,
            is_fixed=request.is_fixed,
            month=month,
        )
    except ValueError as exc:
        message = str(exc)
        if "not found" in message.lower():
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=message) from exc
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=message) from exc

    return BudgetSummaryResponse.model_validate(payload)


@router.post("/budgets/{budget_id}/reactivate", response_model=BudgetSummaryResponse)
def reactivate_budget(
    budget_id: str,
    month: Annotated[str | None, Query(pattern=r"^\d{4}-\d{2}$")] = None,
    service: BudgetService = Depends(get_budget_service),
) -> BudgetSummaryResponse:
    """Undo a cancellation, reopening the budget's window on the same row."""
    try:
        payload = service.reactivate_budget(budget_id=budget_id, month=month)
    except ValueError as exc:
        message = str(exc)
        if "not found" in message.lower():
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=message) from exc
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=message) from exc

    return BudgetSummaryResponse.model_validate(payload)


@router.post("/budgets/{budget_id}/deactivate", response_model=BudgetSummaryResponse)
def deactivate_budget(
    budget_id: str,
    month: Annotated[str | None, Query(pattern=r"^\d{4}-\d{2}$")] = None,
    service: BudgetService = Depends(get_budget_service),
) -> BudgetSummaryResponse:
    try:
        payload = service.deactivate_budget(budget_id=budget_id, month=month)
    except ValueError as exc:
        message = str(exc)
        if "not found" in message.lower():
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=message) from exc
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=message) from exc

    return BudgetSummaryResponse.model_validate(payload)

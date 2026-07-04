from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, status

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
    service: BudgetService = Depends(get_budget_service),
) -> BudgetListResponse:
    return BudgetListResponse(budgets=service.list_budgets())


@router.post("/budgets", response_model=BudgetSummaryResponse, status_code=status.HTTP_201_CREATED)
def create_budget(
    request: CreateBudgetRequest,
    service: BudgetService = Depends(get_budget_service),
) -> BudgetSummaryResponse:
    try:
        payload = service.create_budget(
            category_id=request.category_id,
            amount=request.amount,
            currency=request.currency,
            active_from=request.active_from,
            is_fixed=request.is_fixed,
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
    service: BudgetService = Depends(get_budget_service),
) -> BudgetSummaryResponse:
    try:
        payload = service.update_budget(
            budget_id=budget_id,
            amount=request.amount,
            currency=request.currency,
            is_fixed=request.is_fixed,
        )
    except ValueError as exc:
        message = str(exc)
        if "not found" in message.lower():
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=message) from exc
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=message) from exc

    return BudgetSummaryResponse.model_validate(payload)


@router.post("/budgets/{budget_id}/deactivate", response_model=BudgetSummaryResponse)
def deactivate_budget(
    budget_id: str,
    service: BudgetService = Depends(get_budget_service),
) -> BudgetSummaryResponse:
    try:
        payload = service.deactivate_budget(budget_id=budget_id)
    except ValueError as exc:
        message = str(exc)
        if "not found" in message.lower():
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=message) from exc
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=message) from exc

    return BudgetSummaryResponse.model_validate(payload)

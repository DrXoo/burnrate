from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Query, status

from burnrate.api.dependencies import get_categorization_service
from burnrate.api.schemas.categorization import (
    CategorizeTransactionRequest,
    CategoryListResponse,
    CategorySummaryResponse,
    CreateCategoryRequest,
    TransactionCategoryStateResponse,
    UncategorizedTransactionListResponse,
)
from burnrate.services.categorization_service import CategorizationService

router = APIRouter(tags=["categorization"])


@router.get("/categories", response_model=CategoryListResponse)
def list_categories(
    service: CategorizationService = Depends(get_categorization_service),
) -> CategoryListResponse:
    return CategoryListResponse(categories=service.list_categories())


@router.post("/categories", response_model=CategorySummaryResponse, status_code=status.HTTP_201_CREATED)
def create_category(
    request: CreateCategoryRequest,
    service: CategorizationService = Depends(get_categorization_service),
) -> CategorySummaryResponse:
    try:
        payload = service.create_category(name=request.name, category_type=request.type)
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc

    return CategorySummaryResponse.model_validate(payload)


@router.get("/transactions/uncategorized", response_model=UncategorizedTransactionListResponse)
def list_uncategorized_transactions(
    account_id: str | None = Query(default=None),
    month: str | None = Query(default=None, pattern=r"^\d{4}-\d{2}$"),
    status_filter: str | None = Query(default=None, alias="status"),
    limit: int = Query(default=100, ge=1, le=200),
    offset: int = Query(default=0, ge=0),
    service: CategorizationService = Depends(get_categorization_service),
) -> UncategorizedTransactionListResponse:
    try:
        payload = service.list_uncategorized_transactions(
            account_id=account_id,
            month=month,
            status=status_filter,
            limit=limit,
            offset=offset,
        )
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc

    return UncategorizedTransactionListResponse.model_validate(payload)


@router.post("/transactions/{transaction_id}/categorize", response_model=TransactionCategoryStateResponse)
def categorize_transaction(
    transaction_id: str,
    request: CategorizeTransactionRequest,
    service: CategorizationService = Depends(get_categorization_service),
) -> TransactionCategoryStateResponse:
    try:
        payload = service.categorize_transaction(
            transaction_id=transaction_id,
            category_id=request.category_id,
        )
    except ValueError as exc:
        message = str(exc)
        if "not found" in message.lower():
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=message) from exc
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=message) from exc

    return TransactionCategoryStateResponse.model_validate(payload)


@router.post("/transactions/{transaction_id}/uncategorize", response_model=TransactionCategoryStateResponse)
def uncategorize_transaction(
    transaction_id: str,
    service: CategorizationService = Depends(get_categorization_service),
) -> TransactionCategoryStateResponse:
    try:
        payload = service.uncategorize_transaction(transaction_id=transaction_id)
    except ValueError as exc:
        message = str(exc)
        if "not found" in message.lower():
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=message) from exc
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=message) from exc

    return TransactionCategoryStateResponse.model_validate(payload)


@router.post("/transactions/{transaction_id}/exclude", response_model=TransactionCategoryStateResponse)
def exclude_transaction(
    transaction_id: str,
    service: CategorizationService = Depends(get_categorization_service),
) -> TransactionCategoryStateResponse:
    try:
        payload = service.exclude_transaction(transaction_id=transaction_id)
    except ValueError as exc:
        message = str(exc)
        if "not found" in message.lower():
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=message) from exc
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=message) from exc

    return TransactionCategoryStateResponse.model_validate(payload)


@router.post("/transactions/{transaction_id}/restore", response_model=TransactionCategoryStateResponse)
def restore_transaction(
    transaction_id: str,
    service: CategorizationService = Depends(get_categorization_service),
) -> TransactionCategoryStateResponse:
    try:
        payload = service.restore_transaction(transaction_id=transaction_id)
    except ValueError as exc:
        message = str(exc)
        if "not found" in message.lower():
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=message) from exc
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=message) from exc

    return TransactionCategoryStateResponse.model_validate(payload)

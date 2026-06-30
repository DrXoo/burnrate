from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Query, status

from burnrate.api.dependencies import get_ledger_service
from burnrate.api.schemas.ledger import AccountListResponse, TransactionListResponse, UncategorizedCountResponse
from burnrate.services.ledger_service import LedgerService

router = APIRouter(tags=["ledger"])


@router.get("/accounts", response_model=AccountListResponse)
def list_accounts(
    service: LedgerService = Depends(get_ledger_service),
) -> AccountListResponse:
    return AccountListResponse(accounts=service.list_accounts())


@router.get("/transactions", response_model=TransactionListResponse)
def list_transactions(
    account_id: str | None = Query(default=None),
    month: str | None = Query(default=None, pattern=r"^\d{4}-\d{2}$"),
    status_filter: str | None = Query(default=None, alias="status"),
    categorized: bool | None = Query(default=None),
    limit: int = Query(default=100, ge=1, le=200),
    offset: int = Query(default=0, ge=0),
    service: LedgerService = Depends(get_ledger_service),
) -> TransactionListResponse:
    try:
        payload = service.list_transactions(
            account_id=account_id,
            month=month,
            status=status_filter,
            categorized=categorized,
            limit=limit,
            offset=offset,
        )
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc

    return TransactionListResponse.model_validate(payload)


@router.get("/transactions/uncategorized/count", response_model=UncategorizedCountResponse)
def get_uncategorized_transaction_count(
    account_id: str | None = Query(default=None),
    month: str | None = Query(default=None, pattern=r"^\d{4}-\d{2}$"),
    status_filter: str | None = Query(default=None, alias="status"),
    service: LedgerService = Depends(get_ledger_service),
) -> UncategorizedCountResponse:
    try:
        count = service.get_uncategorized_transaction_count(
            account_id=account_id,
            month=month,
            status=status_filter,
        )
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc

    return UncategorizedCountResponse(count=count)

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Query, status

from burnrate.api.dependencies import get_enable_banking_service
from burnrate.api.schemas.enable_banking import (
    AspspListResponse,
    AuthorizationCallbackResponse,
    StartAuthorizationRequest,
    StartAuthorizationResponse,
)
from burnrate.integrations.enable_banking.client import EnableBankingAPIError
from burnrate.services.enable_banking_service import EnableBankingService

router = APIRouter(prefix="/integrations/enable-banking", tags=["enable-banking"])
public_router = APIRouter(tags=["enable-banking"])


@router.get("/aspsps", response_model=AspspListResponse)
def list_aspsps(
    country: str = Query(..., min_length=2, max_length=2),
    service: EnableBankingService = Depends(get_enable_banking_service),
) -> AspspListResponse:
    try:
        return AspspListResponse(aspsps=service.list_aspsps(country=country))
    except EnableBankingAPIError as exc:
        raise HTTPException(status_code=exc.status_code, detail=exc.detail) from exc


@router.post("/auth/start", response_model=StartAuthorizationResponse, status_code=status.HTTP_201_CREATED)
def start_authorization(
    request: StartAuthorizationRequest,
    service: EnableBankingService = Depends(get_enable_banking_service),
) -> StartAuthorizationResponse:
    try:
        return StartAuthorizationResponse.model_validate(service.start_authorization(request))
    except EnableBankingAPIError as exc:
        raise HTTPException(status_code=exc.status_code, detail=exc.detail) from exc


@router.get("/callback", response_model=AuthorizationCallbackResponse)
@public_router.get("/enable_banking_items/callback", response_model=AuthorizationCallbackResponse)
def enable_banking_callback(
    code: str | None = Query(default=None),
    state: str | None = Query(default=None),
    error: str | None = Query(default=None),
    error_description: str | None = Query(default=None),
    service: EnableBankingService = Depends(get_enable_banking_service),
) -> AuthorizationCallbackResponse:
    if not state:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Missing callback state")

    try:
        payload = service.handle_callback(
            code=code,
            state=state,
            error=error,
            error_description=error_description,
        )
        return AuthorizationCallbackResponse.model_validate(payload)
    except ValueError as exc:
        message = str(exc)
        if "not found" in message.lower():
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=message) from exc
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=message) from exc
    except EnableBankingAPIError as exc:
        raise HTTPException(status_code=exc.status_code, detail=exc.detail) from exc

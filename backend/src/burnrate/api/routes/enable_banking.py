from __future__ import annotations

from urllib.parse import urlencode

from fastapi import APIRouter, Depends, HTTPException, Query, status
from fastapi.responses import RedirectResponse

from burnrate.api.dependencies import enforce_rate_limit, get_enable_banking_service
from burnrate.api.schemas.enable_banking import (
    AspspListResponse,
    EnableBankingConnectionListResponse,
    ManualSyncResponse,
    StartAuthorizationRequest,
    StartAuthorizationResponse,
)
from burnrate.config import Settings, get_settings
from burnrate.integrations.enable_banking.client import EnableBankingAPIError
from burnrate.services.enable_banking_service import EnableBankingService


def _connect_redirect(*, web_base_url: str, params: dict[str, object]) -> RedirectResponse:
    """Redirect the user's browser back to the Web UI with a connection result."""
    target = f"{web_base_url.rstrip('/')}/?{urlencode(params)}"
    return RedirectResponse(url=target, status_code=status.HTTP_303_SEE_OTHER)

router = APIRouter(prefix="/integrations/enable-banking", tags=["enable-banking"])
public_router = APIRouter(tags=["enable-banking"])


@router.get("/connections", response_model=EnableBankingConnectionListResponse)
def list_connections(
    service: EnableBankingService = Depends(get_enable_banking_service),
) -> EnableBankingConnectionListResponse:
    return EnableBankingConnectionListResponse(connections=service.list_connections())


@router.get(
    "/aspsps",
    response_model=AspspListResponse,
    dependencies=[Depends(enforce_rate_limit("enable_banking_aspsps"))],
)
def list_aspsps(
    country: str = Query(..., min_length=2, max_length=2),
    service: EnableBankingService = Depends(get_enable_banking_service),
) -> AspspListResponse:
    try:
        return AspspListResponse(aspsps=service.list_aspsps(country=country))
    except EnableBankingAPIError as exc:
        raise HTTPException(status_code=exc.status_code, detail=exc.detail) from exc


@router.post(
    "/auth/start",
    response_model=StartAuthorizationResponse,
    status_code=status.HTTP_201_CREATED,
    dependencies=[Depends(enforce_rate_limit("enable_banking_auth_start"))],
)
def start_authorization(
    request: StartAuthorizationRequest,
    service: EnableBankingService = Depends(get_enable_banking_service),
) -> StartAuthorizationResponse:
    try:
        return StartAuthorizationResponse.model_validate(service.start_authorization(request))
    except EnableBankingAPIError as exc:
        raise HTTPException(status_code=exc.status_code, detail=exc.detail) from exc


@public_router.get("/api/v1/integrations/enable-banking/callback")
@public_router.get("/enable_banking_items/callback")
def enable_banking_callback(
    code: str | None = Query(default=None),
    state: str | None = Query(default=None),
    error: str | None = Query(default=None),
    error_description: str | None = Query(default=None),
    service: EnableBankingService = Depends(get_enable_banking_service),
    settings: Settings = Depends(get_settings),
) -> RedirectResponse:
    """Handle the bank redirect and send the browser back to the Web UI with a result.

    The bank sends the user's browser here after consent, so this endpoint always
    responds with a redirect to the Web UI rather than JSON.
    """
    web_base_url = settings.app_web_base_url

    if not state:
        return _connect_redirect(
            web_base_url=web_base_url,
            params={"connect": "error", "message": "Missing callback state"},
        )

    try:
        payload = service.handle_callback(
            code=code,
            state=state,
            error=error,
            error_description=error_description,
        )
    except ValueError as exc:
        return _connect_redirect(
            web_base_url=web_base_url,
            params={"connect": "error", "message": str(exc)},
        )
    except EnableBankingAPIError as exc:
        return _connect_redirect(
            web_base_url=web_base_url,
            params={"connect": "error", "message": f"Enable Banking error ({exc.status_code})"},
        )

    accounts_imported = int(payload.get("accounts_imported", 0) or 0)
    return _connect_redirect(
        web_base_url=web_base_url,
        params={
            "connect": "success" if accounts_imported > 0 else "empty",
            "accounts": accounts_imported,
            "imported": int(payload.get("transactions_imported", 0) or 0),
        },
    )


@router.post(
    "/connections/{connection_id}/sync",
    response_model=ManualSyncResponse,
    dependencies=[Depends(enforce_rate_limit("enable_banking_sync"))],
)
def sync_connection(
    connection_id: str,
    service: EnableBankingService = Depends(get_enable_banking_service),
) -> ManualSyncResponse:
    try:
        payload = service.sync_connection(connection_id=connection_id)
        return ManualSyncResponse.model_validate(payload)
    except ValueError as exc:
        message = str(exc)
        if "not found" in message.lower():
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=message) from exc
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=message) from exc
    except EnableBankingAPIError as exc:
        raise HTTPException(status_code=exc.status_code, detail=exc.detail) from exc

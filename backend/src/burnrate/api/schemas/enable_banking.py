from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, Field


class StartAuthorizationRequest(BaseModel):
    aspsp_name: str = Field(min_length=1)
    aspsp_country: str = Field(min_length=2, max_length=2)
    psu_type: Literal["personal", "business"] = "personal"
    access_valid_for_days: int = Field(default=180, ge=1, le=180)


class StartAuthorizationResponse(BaseModel):
    authorization_id: str | None = None
    psu_id_hash: str | None = None
    state: str
    url: str
    valid_until: str


# The bank session token is never exposed to clients: it is a live credential
# for the bank API, the UI has no use for it, and shipping it would undo the
# point of encrypting it at rest. `sync_session_id` below is our own sync-run id,
# not a bank token.
class AuthorizationCallbackResponse(BaseModel):
    connection_id: str
    session_status: str
    accounts_returned: int
    accounts_imported: int
    transactions_imported: int
    message: str | None = None


class ManualSyncResponse(BaseModel):
    connection_id: str
    sync_session_id: str
    session_status: str
    accounts_synced: int
    transactions_imported: int
    message: str | None = None


class AspspListResponse(BaseModel):
    aspsps: list[dict[str, Any]]


class EnableBankingConnectionSummary(BaseModel):
    connection_id: str
    aspsp_name: str
    aspsp_country: str
    psu_type: str
    session_status: str | None = None
    active: bool
    authorized_at: str | None = None
    last_synced_at: str | None = None
    expires_at: str | None = None
    days_until_expiry: int | None = None
    expiry_status: Literal["unknown", "active", "expiring_soon", "expired"] = "unknown"
    linked_account_count: int
    latest_sync_status: str | None = None
    latest_sync_started_at: str | None = None
    latest_sync_finished_at: str | None = None
    latest_sync_accounts_count: int | None = None
    latest_sync_transactions_count: int | None = None
    latest_sync_error_summary: str | None = None


class EnableBankingConnectionListResponse(BaseModel):
    connections: list[EnableBankingConnectionSummary]

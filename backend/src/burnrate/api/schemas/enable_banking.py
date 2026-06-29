from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, Field


class StartAuthorizationRequest(BaseModel):
    aspsp_name: str = Field(min_length=1)
    aspsp_country: str = Field(min_length=2, max_length=2)
    psu_type: Literal["personal", "business"] = "personal"
    access_valid_for_days: int = Field(default=10, ge=1, le=90)


class StartAuthorizationResponse(BaseModel):
    authorization_id: str | None = None
    psu_id_hash: str | None = None
    state: str
    url: str
    valid_until: str


class AuthorizationCallbackResponse(BaseModel):
    connection_id: str
    session_id: str
    session_status: str
    accounts_returned: int
    accounts_imported: int
    transactions_imported: int
    message: str | None = None


class AspspListResponse(BaseModel):
    aspsps: list[dict[str, Any]]


from __future__ import annotations

from pydantic import BaseModel, Field


class AccountSummaryResponse(BaseModel):
    account_id: str
    display_name: str
    currency: str
    latest_balance_amount: str | None = None
    latest_balance_currency: str | None = None
    included_in_calculations: bool
    included_in_runway: bool
    last_synced_at: str | None = None
    source_connection_id: str | None = None
    source_aspsp_name: str | None = None
    source_aspsp_country: str | None = None
    external_account_id: str | None = None


class AccountListResponse(BaseModel):
    accounts: list[AccountSummaryResponse]


class TransactionSummaryResponse(BaseModel):
    transaction_id: str
    account_id: str
    account_display_name: str
    booking_date: str | None = None
    value_date: str | None = None
    amount: str
    currency: str
    description: str | None = None
    merchant_name: str | None = None
    counterparty_name: str | None = None
    direction: str
    status: str
    category_id: str | None = None
    imported_at: str


class TransactionListResponse(BaseModel):
    transactions: list[TransactionSummaryResponse]
    total_count: int
    limit: int
    offset: int


class UncategorizedCountResponse(BaseModel):
    count: int = Field(ge=0)

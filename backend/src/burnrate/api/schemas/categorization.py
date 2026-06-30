from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field

from burnrate.api.schemas.ledger import TransactionSummaryResponse


class CategorySummaryResponse(BaseModel):
    category_id: str
    name: str
    type: Literal["expense", "income", "transfer"]
    active: bool


class CategoryListResponse(BaseModel):
    categories: list[CategorySummaryResponse]


class CreateCategoryRequest(BaseModel):
    name: str = Field(min_length=1, max_length=80)
    type: Literal["expense", "income", "transfer"] = "expense"


class UncategorizedTransactionListResponse(BaseModel):
    transactions: list[TransactionSummaryResponse]
    total_count: int
    limit: int
    offset: int


class CategorizeTransactionRequest(BaseModel):
    category_id: str


class TransactionCategoryStateResponse(BaseModel):
    transaction_id: str
    category_id: str | None = None
    category_name: str | None = None
    message: str | None = None

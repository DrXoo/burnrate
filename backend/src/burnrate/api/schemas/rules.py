from __future__ import annotations

from typing import Literal

from pydantic import BaseModel


MatchField = Literal["description", "merchant_name", "counterparty_name"]
MatchOperator = Literal["contains", "equals", "starts_with", "ends_with", "regex"]


class RuleSummaryResponse(BaseModel):
    rule_id: str
    name: str | None = None
    match_field: MatchField
    match_operator: MatchOperator
    match_value: str
    category_id: str
    category_name: str
    priority: int
    active: bool
    created_from_manual_classification: bool


class RuleListResponse(BaseModel):
    rules: list[RuleSummaryResponse]


class CreateRuleFromTransactionRequest(BaseModel):
    name: str | None = None
    match_field: MatchField | None = None
    match_operator: MatchOperator = "contains"
    match_value: str | None = None
    category_id: str | None = None
    apply_to_existing_uncategorized: bool = False


class UpdateRuleRequest(BaseModel):
    name: str | None = None
    match_field: MatchField
    match_operator: MatchOperator
    match_value: str
    apply_to_existing_uncategorized: bool = False


class SetRuleStatusRequest(BaseModel):
    active: bool

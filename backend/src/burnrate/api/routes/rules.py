from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, status

from burnrate.api.dependencies import get_rules_service
from burnrate.api.schemas.rules import (
    CreateRuleFromTransactionRequest,
    RuleDeletionResponse,
    RuleListResponse,
    RuleSummaryResponse,
    SetRuleStatusRequest,
    UpdateRuleRequest,
)
from burnrate.services.rules_service import RulesService

router = APIRouter(tags=["rules"])


@router.get("/rules", response_model=RuleListResponse)
def list_rules(
    service: RulesService = Depends(get_rules_service),
) -> RuleListResponse:
    return RuleListResponse(rules=service.list_rules())


@router.post("/transactions/{transaction_id}/rules", response_model=RuleSummaryResponse, status_code=status.HTTP_201_CREATED)
def create_rule_from_transaction(
    transaction_id: str,
    request: CreateRuleFromTransactionRequest,
    service: RulesService = Depends(get_rules_service),
) -> RuleSummaryResponse:
    try:
        payload = service.create_rule_from_transaction(
            transaction_id=transaction_id,
            name=request.name,
            match_field=request.match_field,
            match_operator=request.match_operator,
            match_value=request.match_value,
            category_id=request.category_id,
            apply_to_existing_uncategorized=request.apply_to_existing_uncategorized,
        )
    except ValueError as exc:
        message = str(exc)
        if "not found" in message.lower():
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=message) from exc
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=message) from exc

    return RuleSummaryResponse.model_validate(payload)


@router.post("/rules/{rule_id}/status", response_model=RuleSummaryResponse)
def set_rule_status(
    rule_id: str,
    request: SetRuleStatusRequest,
    service: RulesService = Depends(get_rules_service),
) -> RuleSummaryResponse:
    try:
        payload = service.set_rule_status(rule_id=rule_id, active=request.active)
    except ValueError as exc:
        message = str(exc)
        if "not found" in message.lower():
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=message) from exc
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=message) from exc

    return RuleSummaryResponse.model_validate(payload)


@router.delete("/rules/{rule_id}", response_model=RuleDeletionResponse)
def delete_rule(
    rule_id: str,
    service: RulesService = Depends(get_rules_service),
) -> RuleDeletionResponse:
    try:
        payload = service.delete_rule(rule_id=rule_id)
    except ValueError as exc:
        message = str(exc)
        if "not found" in message.lower():
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=message) from exc
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=message) from exc

    return RuleDeletionResponse.model_validate(payload)


@router.patch("/rules/{rule_id}", response_model=RuleSummaryResponse)
def update_rule(
    rule_id: str,
    request: UpdateRuleRequest,
    service: RulesService = Depends(get_rules_service),
) -> RuleSummaryResponse:
    try:
        payload = service.update_rule(
            rule_id=rule_id,
            name=request.name,
            match_field=request.match_field,
            match_operator=request.match_operator,
            match_value=request.match_value,
            apply_to_existing_uncategorized=request.apply_to_existing_uncategorized,
        )
    except ValueError as exc:
        message = str(exc)
        if "not found" in message.lower():
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=message) from exc
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=message) from exc

    return RuleSummaryResponse.model_validate(payload)

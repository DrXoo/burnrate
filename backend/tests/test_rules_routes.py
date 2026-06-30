from __future__ import annotations

from burnrate.api.routes.rules import create_rule_from_transaction, list_rules, set_rule_status, update_rule
from burnrate.api.schemas.rules import CreateRuleFromTransactionRequest, SetRuleStatusRequest, UpdateRuleRequest
from burnrate.main import create_app


class FakeRulesService:
    def list_rules(self):
        return [
            {
                "rule_id": "rule-1",
                "name": "Food from merchant_name contains Mercadona",
                "match_field": "merchant_name",
                "match_operator": "contains",
                "match_value": "Mercadona",
                "category_id": "cat-1",
                "category_name": "Food",
                "priority": 1,
                "active": True,
                "created_from_manual_classification": True,
            }
        ]

    def create_rule_from_transaction(self, *, transaction_id: str, **_: object):
        assert transaction_id == "tx-1"
        return self.list_rules()[0]

    def set_rule_status(self, *, rule_id: str, active: bool):
        assert rule_id == "rule-1"
        payload = self.list_rules()[0]
        payload["active"] = active
        return payload

    def update_rule(self, *, rule_id: str, **_: object):
        assert rule_id == "rule-1"
        payload = self.list_rules()[0]
        payload["match_operator"] = "starts_with"
        payload["match_value"] = "Merca"
        return payload


def test_rules_routes_use_service_dependency() -> None:
    service = FakeRulesService()

    list_response = list_rules(service=service)
    create_response = create_rule_from_transaction(
        transaction_id="tx-1",
        request=CreateRuleFromTransactionRequest(),
        service=service,
    )
    status_response = set_rule_status(
        rule_id="rule-1",
        request=SetRuleStatusRequest(active=False),
        service=service,
    )
    update_response = update_rule(
        rule_id="rule-1",
        request=UpdateRuleRequest(
            name="Food starter",
            match_field="merchant_name",
            match_operator="starts_with",
            match_value="Merca",
            apply_to_existing_uncategorized=True,
        ),
        service=service,
    )

    assert list_response.rules[0].match_value == "Mercadona"
    assert create_response.category_name == "Food"
    assert status_response.active is False
    assert update_response.match_operator == "starts_with"


def test_app_exposes_phase_3_rules_paths() -> None:
    app = create_app()
    paths = set(app.openapi()["paths"].keys())

    assert "/api/v1/rules" in paths
    assert "/api/v1/transactions/{transaction_id}/rules" in paths
    assert "/api/v1/rules/{rule_id}/status" in paths
    assert "/api/v1/rules/{rule_id}" in paths

from __future__ import annotations

from burnrate.api.routes.enable_banking import (
    enable_banking_callback,
    list_aspsps,
    start_authorization,
)
from burnrate.api.schemas.enable_banking import StartAuthorizationRequest
from burnrate.main import create_app


class FakeRouteService:
    def list_aspsps(self, *, country: str):
        return [{"name": "Nordea", "country": country}]

    def start_authorization(self, request):
        return {
            "authorization_id": "auth-1",
            "psu_id_hash": None,
            "state": "state-123",
            "url": "https://auth.example.test/redirect",
            "valid_until": "2026-01-11T12:00:00+00:00",
        }

    def handle_callback(self, *, code, state, error, error_description):
        assert code == "callback-code"
        assert state == "state-123"
        return {
            "connection_id": "conn-1",
            "session_id": "session-1",
            "session_status": "AUTHORIZED",
            "accounts_returned": 1,
            "accounts_imported": 1,
            "transactions_imported": 2,
            "message": None,
        }


def test_enable_banking_routes_use_service_dependency() -> None:
    service = FakeRouteService()

    aspsps_response = list_aspsps(country="FI", service=service)
    start_response = start_authorization(
        StartAuthorizationRequest(
            aspsp_name="Nordea",
            aspsp_country="FI",
            psu_type="personal",
            access_valid_for_days=10,
        ),
        service=service,
    )
    callback_response = enable_banking_callback(
        code="callback-code",
        state="state-123",
        error=None,
        error_description=None,
        service=service,
    )

    assert aspsps_response.aspsps[0]["name"] == "Nordea"
    assert start_response.state == "state-123"
    assert callback_response.transactions_imported == 2


def test_app_exposes_both_enable_banking_callback_paths() -> None:
    app = create_app()
    paths = set(app.openapi()["paths"].keys())

    assert "/api/v1/integrations/enable-banking/callback" in paths
    assert "/enable_banking_items/callback" in paths

from __future__ import annotations

import pytest
from fastapi import HTTPException

from burnrate.integrations.enable_banking.client import EnableBankingAPIError
from burnrate.api.routes.enable_banking import (
    enable_banking_callback,
    list_connections,
    list_aspsps,
    sync_connection,
    start_authorization,
)
from burnrate.api.schemas.enable_banking import StartAuthorizationRequest
from burnrate.config import Settings
from burnrate.main import create_app


def make_web_settings() -> Settings:
    return Settings(WEB_BASE_URL="http://web.test")


class FakeRouteService:
    def list_connections(self):
        return [
            {
                "connection_id": "conn-1",
                "aspsp_name": "Nordea",
                "aspsp_country": "FI",
                "psu_type": "personal",
                "session_id": "session-1",
                "session_status": "AUTHORIZED",
                "active": True,
                "authorized_at": "2026-01-01T12:00:00+00:00",
                "last_synced_at": "2026-01-02T12:00:00+00:00",
                "linked_account_count": 1,
                "latest_sync_status": "success",
                "latest_sync_started_at": "2026-01-02T12:00:00+00:00",
                "latest_sync_finished_at": "2026-01-02T12:00:01+00:00",
                "latest_sync_accounts_count": 1,
                "latest_sync_transactions_count": 2,
                "latest_sync_error_summary": None,
            }
        ]

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

    def sync_connection(self, *, connection_id):
        assert connection_id == "conn-1"
        return {
            "connection_id": "conn-1",
            "sync_session_id": "sync-1",
            "session_id": "session-1",
            "session_status": "AUTHORIZED",
            "accounts_synced": 1,
            "transactions_imported": 2,
            "message": None,
        }


def test_enable_banking_routes_use_service_dependency() -> None:
    service = FakeRouteService()

    connections_response = list_connections(service=service)
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
        settings=make_web_settings(),
    )
    sync_response = sync_connection(connection_id="conn-1", service=service)

    assert connections_response.connections[0].connection_id == "conn-1"
    assert aspsps_response.aspsps[0]["name"] == "Nordea"
    assert start_response.state == "state-123"
    assert callback_response.status_code == 303
    callback_location = callback_response.headers["location"]
    assert callback_location.startswith("http://web.test/?")
    assert "connect=success" in callback_location
    assert "imported=2" in callback_location
    assert sync_response.sync_session_id == "sync-1"


def test_enable_banking_callback_redirects_error_to_web_ui() -> None:
    class FailingService:
        def handle_callback(self, *, code, state, error, error_description):
            raise ValueError("Authorization request not found for state bad-state")

    response = enable_banking_callback(
        code=None,
        state="bad-state",
        error=None,
        error_description=None,
        service=FailingService(),
        settings=make_web_settings(),
    )

    assert response.status_code == 303
    location = response.headers["location"]
    assert location.startswith("http://web.test/?")
    assert "connect=error" in location


def test_enable_banking_callback_redirects_when_state_missing() -> None:
    class UnusedService:
        def handle_callback(self, *, code, state, error, error_description):
            raise AssertionError("handle_callback should not be called without state")

    response = enable_banking_callback(
        code=None,
        state=None,
        error=None,
        error_description=None,
        service=UnusedService(),
        settings=make_web_settings(),
    )

    assert response.status_code == 303
    assert "connect=error" in response.headers["location"]


def test_app_exposes_both_enable_banking_callback_paths() -> None:
    app = create_app()
    paths = set(app.openapi()["paths"].keys())

    assert "/api/v1/integrations/enable-banking/connections" in paths
    assert "/api/v1/integrations/enable-banking/callback" in paths
    assert "/api/v1/integrations/enable-banking/connections/{connection_id}/sync" in paths
    assert "/enable_banking_items/callback" in paths


class RefusingBankService(FakeRouteService):
    """A bank that refuses the sync with a status of the test's choosing."""

    def __init__(self, status_code: int) -> None:
        self.status_code = status_code

    def sync_connection(self, *, connection_id):
        raise EnableBankingAPIError(
            status_code=self.status_code,
            detail={"error": "ASPSP_RATE_LIMIT_EXCEEDED", "psu_reference": "do-not-echo"},
        )


def test_a_spent_access_budget_is_not_reported_as_a_broken_bank() -> None:
    """A 429 and a 503 called for opposite reactions and read identically.

    Every bank failure became "The bank service returned an error (upstream status
    429)" with a 502, so "the bank is down, go and look" and "today's allowance is
    spent, wait" differed by one number in a message the owner had to interpret. They
    spent an evening on the wrong one.

    The discriminator is in the body rather than the status, and deliberately: this
    endpoint already answers **429** from BurnRate's own `enable_banking_sync` limiter,
    and **503** for a backend with no password configured. Either status reused here
    would be ambiguous with something that has a different remedy, so the status is
    chosen for honest semantics and the `code` is what a client keys on.
    """
    with pytest.raises(HTTPException) as exc_info:
        sync_connection(connection_id="conn-1", service=RefusingBankService(429))

    detail = exc_info.value.detail
    assert detail["code"] == "bank_rate_limit"
    # No upstream status reused as BurnRate's own, for the reason _bank_error records:
    # a bank 401 passed through would read as the owner's session expiring.
    assert exc_info.value.status_code != 429
    # Nothing is lost, and saying so is what makes this calm rather than alarming --
    # a later sync still reaches back across the fetch window.
    assert "lost" in detail["message"].lower()
    assert "do-not-echo" not in str(detail)


def test_every_other_bank_failure_still_reports_as_a_bad_gateway() -> None:
    """The rate limit is carved out of `_bank_error`, not substituted for it."""
    with pytest.raises(HTTPException) as exc_info:
        sync_connection(connection_id="conn-1", service=RefusingBankService(503))

    assert exc_info.value.status_code == 502
    assert "do-not-echo" not in str(exc_info.value.detail)

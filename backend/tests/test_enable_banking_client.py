from __future__ import annotations

from datetime import date, datetime, timezone
import json

import httpx
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric import rsa

import pytest

from burnrate.config import Settings
from burnrate.integrations.enable_banking.client import (
    EnableBankingAPIError,
    EnableBankingClient,
)


def make_settings(*, max_retries: int = 3, retry_backoff_seconds: float = 0.0) -> Settings:
    private_key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    private_key_pem = private_key.private_bytes(
        encoding=serialization.Encoding.PEM,
        format=serialization.PrivateFormat.TraditionalOpenSSL,
        encryption_algorithm=serialization.NoEncryption(),
    ).decode("utf-8")
    return Settings(
        ENABLE_BANKING_APP_ID="app-123",
        ENABLE_BANKING_PRIVATE_KEY=private_key_pem,
        ENABLE_BANKING_PRIVATE_KEY_PATH="",
        ENABLE_BANKING_REDIRECT_URL="http://localhost:8000/api/v1/integrations/enable-banking/callback",
        ENABLE_BANKING_ENVIRONMENT="production",
        ENABLE_BANKING_API_BASE_URL="https://api.enablebanking.com",
        ENABLE_BANKING_TIMEOUT_SECONDS=5,
        ENABLE_BANKING_MAX_RETRIES=max_retries,
        ENABLE_BANKING_RETRY_BACKOFF_SECONDS=retry_backoff_seconds,
        DATABASE_URL="sqlite:///ignored.db",
    )


def test_enable_banking_client_sends_jwt_bearer_header() -> None:
    captured: dict[str, str] = {}

    def handler(request: httpx.Request) -> httpx.Response:
        captured["authorization"] = request.headers["Authorization"]
        captured["url"] = str(request.url)
        return httpx.Response(200, json={"aspsps": []})

    client = EnableBankingClient(
        settings=make_settings(),
        transport=httpx.MockTransport(handler),
    )

    payload = client.list_aspsps(country="fi")

    assert payload == []
    assert captured["authorization"].startswith("Bearer ")
    assert captured["url"].endswith("/aspsps?country=FI")


def test_enable_banking_client_posts_start_authorization_payload() -> None:
    captured: dict[str, str] = {}

    def handler(request: httpx.Request) -> httpx.Response:
        captured["body"] = request.content.decode("utf-8")
        return httpx.Response(200, json={"url": "https://example.com/auth"})

    client = EnableBankingClient(
        settings=make_settings(),
        transport=httpx.MockTransport(handler),
    )

    response = client.start_authorization(
        aspsp_name="Nordea",
        aspsp_country="fi",
        state="state-123",
        redirect_url="http://localhost/callback",
        psu_type="personal",
        valid_until=datetime(2026, 1, 10, tzinfo=timezone.utc),
    )

    assert response["url"] == "https://example.com/auth"
    payload = json.loads(captured["body"])
    assert payload["aspsp"]["name"] == "Nordea"
    assert payload["aspsp"]["country"] == "FI"
    assert payload["state"] == "state-123"


def test_enable_banking_client_sends_transaction_date_window() -> None:
    captured: dict[str, str] = {}

    def handler(request: httpx.Request) -> httpx.Response:
        captured["url"] = str(request.url)
        return httpx.Response(200, json={"transactions": []})

    client = EnableBankingClient(
        settings=make_settings(),
        transport=httpx.MockTransport(handler),
    )

    payload = client.get_account_transactions(
        account_id="account-123",
        date_from=date(2026, 6, 1),
        date_to=date(2026, 6, 30),
    )

    assert payload == {"transactions": []}
    assert captured["url"].endswith(
        "/accounts/account-123/transactions?date_from=2026-06-01&date_to=2026-06-30"
    )


def test_enable_banking_client_retries_transient_transport_error_then_succeeds() -> None:
    attempts = {"count": 0}

    def handler(request: httpx.Request) -> httpx.Response:
        attempts["count"] += 1
        if attempts["count"] < 3:
            raise httpx.ConnectError("connection refused", request=request)
        return httpx.Response(200, json={"aspsps": []})

    sleeps: list[float] = []
    client = EnableBankingClient(
        settings=make_settings(max_retries=3, retry_backoff_seconds=0.5),
        transport=httpx.MockTransport(handler),
        sleep=sleeps.append,
    )

    payload = client.list_aspsps(country="fi")

    assert payload == []
    assert attempts["count"] == 3
    # Exponential backoff: 0.5 * 2**0, then 0.5 * 2**1.
    assert sleeps == [0.5, 1.0]


def test_enable_banking_client_retries_on_retryable_status_code() -> None:
    attempts = {"count": 0}

    def handler(request: httpx.Request) -> httpx.Response:
        attempts["count"] += 1
        if attempts["count"] == 1:
            return httpx.Response(503, json={"error": "unavailable"})
        return httpx.Response(200, json={"aspsps": []})

    sleeps: list[float] = []
    client = EnableBankingClient(
        settings=make_settings(max_retries=3, retry_backoff_seconds=0.0),
        transport=httpx.MockTransport(handler),
        sleep=sleeps.append,
    )

    payload = client.list_aspsps(country="fi")

    assert payload == []
    assert attempts["count"] == 2
    assert sleeps == [0.0]


def test_enable_banking_client_does_not_retry_client_error() -> None:
    attempts = {"count": 0}

    def handler(request: httpx.Request) -> httpx.Response:
        attempts["count"] += 1
        return httpx.Response(400, json={"error": "bad request"})

    sleeps: list[float] = []
    client = EnableBankingClient(
        settings=make_settings(max_retries=3, retry_backoff_seconds=0.0),
        transport=httpx.MockTransport(handler),
        sleep=sleeps.append,
    )

    with pytest.raises(EnableBankingAPIError) as exc_info:
        client.list_aspsps(country="fi")

    assert exc_info.value.status_code == 400
    assert attempts["count"] == 1
    assert sleeps == []


def test_enable_banking_client_gives_up_after_max_retries() -> None:
    attempts = {"count": 0}

    def handler(request: httpx.Request) -> httpx.Response:
        attempts["count"] += 1
        return httpx.Response(503, json={"error": "unavailable"})

    sleeps: list[float] = []
    client = EnableBankingClient(
        settings=make_settings(max_retries=2, retry_backoff_seconds=0.0),
        transport=httpx.MockTransport(handler),
        sleep=sleeps.append,
    )

    with pytest.raises(EnableBankingAPIError) as exc_info:
        client.list_aspsps(country="fi")

    assert exc_info.value.status_code == 503
    # Initial attempt + 2 retries = 3 calls.
    assert attempts["count"] == 3
    assert len(sleeps) == 2

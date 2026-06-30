from __future__ import annotations

from datetime import date, datetime, timezone
import json

import httpx
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric import rsa

from burnrate.config import Settings
from burnrate.integrations.enable_banking.client import EnableBankingClient


def make_settings() -> Settings:
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

from __future__ import annotations

from datetime import date, datetime, timezone
import json
import logging

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


def test_enable_banking_client_does_not_retry_a_rate_limit() -> None:
    """A 429 is the daily access budget for a consent, not a transient fault.

    Enable Banking answers an over-budget access with ``ASPSP_RATE_LIMIT_EXCEEDED``,
    and PSD2 measures that budget in days. Retrying it cannot succeed, and each retry
    is charged as another access -- so the retries deepen the overdraft that caused
    the error and push recovery further into tomorrow. Observed on 2026-11-03: one
    rate-limited balances call cost four accesses of a budget of four.
    """
    attempts = {"count": 0}

    def handler(request: httpx.Request) -> httpx.Response:
        attempts["count"] += 1
        return httpx.Response(429, json={"error": "ASPSP_RATE_LIMIT_EXCEEDED"})

    sleeps: list[float] = []
    client = EnableBankingClient(
        settings=make_settings(max_retries=3, retry_backoff_seconds=0.0),
        transport=httpx.MockTransport(handler),
        sleep=sleeps.append,
    )

    with pytest.raises(EnableBankingAPIError) as exc_info:
        client.list_aspsps(country="fi")

    assert exc_info.value.status_code == 429
    assert attempts["count"] == 1
    assert sleeps == []


def test_enable_banking_client_logs_a_rate_limit_as_a_rate_limit(
    caplog: pytest.LogCaptureFixture,
) -> None:
    """A spent budget and a broken bank must not read the same in the logs.

    Both used to surface only as a caller's traceback saying "Enable Banking API
    error (<status>)", so the two cases differed by one number and otherwise looked
    identical -- and they call for opposite reactions: a 503 means go and look, a 429
    means wait. The owner spent an evening on the wrong one.

    The bank's body is deliberately not logged. ``_bank_error`` already refuses to
    echo provider detail to a client, and a log file is no safer a place for it.
    """
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(429, json={"error": "ASPSP_RATE_LIMIT_EXCEEDED", "psu": "secret"})

    client = EnableBankingClient(
        settings=make_settings(max_retries=3, retry_backoff_seconds=0.0),
        transport=httpx.MockTransport(handler),
        sleep=lambda _: None,
    )

    with caplog.at_level(logging.WARNING, logger="burnrate.integrations.enable_banking.client"):
        with pytest.raises(EnableBankingAPIError):
            client.list_aspsps(country="fi")

    logged = caplog.text
    assert "rate limit" in logged.lower()
    assert "/aspsps" in logged
    assert "retrying" not in logged.lower()
    assert "secret" not in logged


def test_enable_banking_client_does_not_call_an_outage_a_rate_limit(
    caplog: pytest.LogCaptureFixture,
) -> None:
    """The calming message must not be told about a bank that is actually down.

    This exists because deleting the status check in ``_log_rate_limit`` left every
    test green: the rate-limit message would have been attached to a 503 and to a
    400, telling the owner to wait while the bank was broken. The guard had no test,
    so it was a rule in name only.
    """
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(503, json={"error": "unavailable"})

    client = EnableBankingClient(
        settings=make_settings(max_retries=1, retry_backoff_seconds=0.0),
        transport=httpx.MockTransport(handler),
        sleep=lambda _: None,
    )

    with caplog.at_level(logging.WARNING, logger="burnrate.integrations.enable_banking.client"):
        with pytest.raises(EnableBankingAPIError):
            client.list_aspsps(country="fi")

    assert "rate limit" not in caplog.text.lower()

from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from burnrate.api.dependencies import (
    _login_rate_limiter,
    _rate_limiter,
    get_enable_banking_service,
)
from burnrate.config import Settings, get_settings
from burnrate.main import create_app
from burnrate.security import hash_password

PASSWORD = "hardening-test-password"
ASPSPS_URL = "/api/v1/integrations/enable-banking/aspsps?country=ES"


class FakeEnableBankingService:
    def list_aspsps(self, *, country: str) -> list[dict[str, object]]:
        return []


def make_settings(**overrides: object) -> Settings:
    base: dict[str, object] = {
        "AUTH_PASSWORD_HASH": hash_password(PASSWORD),
        "AUTH_SECRET_KEY": "hardening-signing-key",
        "AUTH_COOKIE_SECURE": False,
        "APP_ENV": "development",
        "DATABASE_URL": "sqlite:///ignored.db",
    }
    base.update(overrides)
    return Settings(**base)


def build_client(settings: Settings) -> TestClient:
    app = create_app()
    app.dependency_overrides[get_settings] = lambda: settings
    app.dependency_overrides[get_enable_banking_service] = lambda: FakeEnableBankingService()
    return TestClient(app)


@pytest.fixture(autouse=True)
def _reset_limiters():
    _login_rate_limiter.cache_clear()
    _rate_limiter.cache_clear()
    yield
    _login_rate_limiter.cache_clear()
    _rate_limiter.cache_clear()


def _login(client: TestClient) -> None:
    assert client.post("/api/v1/auth/login", json={"password": PASSWORD}).status_code == 200


def test_security_headers_present_on_responses() -> None:
    client = build_client(make_settings())
    response = client.get("/api/v1/health")
    assert response.headers["X-Content-Type-Options"] == "nosniff"
    assert response.headers["X-Frame-Options"] == "DENY"
    assert response.headers["Referrer-Policy"] == "no-referrer"
    assert response.headers["Cache-Control"] == "no-store"


def test_cors_preflight_uses_explicit_methods_not_wildcard() -> None:
    client = build_client(make_settings())
    response = client.options(
        "/api/v1/health",
        headers={"Origin": "http://localhost:3000", "Access-Control-Request-Method": "GET"},
    )
    assert response.status_code == 200
    allow_methods = response.headers.get("access-control-allow-methods", "")
    assert "*" not in allow_methods
    assert "GET" in allow_methods and "PATCH" in allow_methods
    assert response.headers.get("access-control-allow-origin") == "http://localhost:3000"


def test_bank_endpoint_is_rate_limited() -> None:
    settings = make_settings(BANK_RATE_LIMIT_MAX_REQUESTS=2, BANK_RATE_LIMIT_WINDOW_SECONDS=60)
    client = build_client(settings)
    _login(client)

    assert client.get(ASPSPS_URL).status_code == 200
    assert client.get(ASPSPS_URL).status_code == 200
    throttled = client.get(ASPSPS_URL)
    assert throttled.status_code == 429
    assert throttled.headers.get("Retry-After") is not None


def test_rate_limited_endpoint_still_requires_auth_first() -> None:
    # require_auth runs before the limiter, so anonymous callers get 401, not 429,
    # and cannot burn the rate-limit budget without a session.
    client = build_client(make_settings(BANK_RATE_LIMIT_MAX_REQUESTS=1))
    for _ in range(3):
        assert client.get(ASPSPS_URL).status_code == 401

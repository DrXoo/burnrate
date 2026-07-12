from __future__ import annotations

import time

import pytest
from fastapi.testclient import TestClient

from burnrate.api.dependencies import _login_rate_limiter, get_ledger_service
from burnrate.config import Settings, get_settings
from burnrate.main import create_app
from burnrate.security import (
    create_session_token,
    hash_password,
    verify_password,
    verify_session_token,
)

PASSWORD = "correct-horse-battery-staple"


class FakeLedgerService:
    def list_accounts(self) -> list[dict[str, object]]:
        return []


def make_settings(**overrides: object) -> Settings:
    base: dict[str, object] = {
        "AUTH_PASSWORD_HASH": hash_password(PASSWORD),
        "AUTH_SECRET_KEY": "unit-test-signing-key",
        "AUTH_COOKIE_SECURE": False,
        "APP_ENV": "development",
        "DATABASE_URL": "sqlite:///ignored.db",
    }
    base.update(overrides)
    return Settings(**base)


def build_client(settings: Settings) -> TestClient:
    app = create_app()
    app.dependency_overrides[get_settings] = lambda: settings
    app.dependency_overrides[get_ledger_service] = lambda: FakeLedgerService()
    return TestClient(app)


@pytest.fixture(autouse=True)
def _reset_rate_limiter():
    _login_rate_limiter.cache_clear()
    yield
    _login_rate_limiter.cache_clear()


def test_health_is_open() -> None:
    client = build_client(make_settings())
    assert client.get("/api/v1/health").status_code == 200


def test_protected_route_requires_authentication() -> None:
    client = build_client(make_settings())
    response = client.get("/api/v1/accounts")
    assert response.status_code == 401


def test_login_rejects_wrong_password() -> None:
    settings = make_settings()
    client = build_client(settings)

    response = client.post("/api/v1/auth/login", json={"password": "wrong"})

    assert response.status_code == 401
    assert settings.auth_cookie_name not in response.cookies


def test_login_grants_access_and_reports_identity() -> None:
    settings = make_settings()
    client = build_client(settings)

    login = client.post("/api/v1/auth/login", json={"password": PASSWORD})
    assert login.status_code == 200
    assert login.json() == {"authenticated": True}
    assert settings.auth_cookie_name in login.cookies

    # The session cookie now unlocks protected routes...
    assert client.get("/api/v1/accounts").status_code == 200
    # ...and /auth/me reflects the authenticated state.
    assert client.get("/api/v1/auth/me").json() == {"authenticated": True}


def test_logout_clears_the_session() -> None:
    settings = make_settings()
    client = build_client(settings)

    client.post("/api/v1/auth/login", json={"password": PASSWORD})
    logout = client.post("/api/v1/auth/logout")
    assert logout.status_code == 200
    assert logout.json() == {"authenticated": False}

    assert client.get("/api/v1/accounts").status_code == 401
    assert client.get("/api/v1/auth/me").json() == {"authenticated": False}


def test_me_is_unauthenticated_without_a_cookie() -> None:
    client = build_client(make_settings())
    assert client.get("/api/v1/auth/me").json() == {"authenticated": False}


def test_login_locks_out_after_repeated_failures() -> None:
    settings = make_settings(AUTH_LOGIN_MAX_ATTEMPTS=3, AUTH_LOGIN_LOCKOUT_SECONDS=60)
    client = build_client(settings)

    for _ in range(3):
        assert client.post("/api/v1/auth/login", json={"password": "wrong"}).status_code == 401

    # The next attempt is throttled even though the password is now correct.
    throttled = client.post("/api/v1/auth/login", json={"password": PASSWORD})
    assert throttled.status_code == 429


def test_unconfigured_auth_fails_closed() -> None:
    settings = make_settings(AUTH_PASSWORD_HASH="", AUTH_SECRET_KEY="")
    client = build_client(settings)

    # Protected routes must be unreachable, not open, when auth is unset.
    assert client.get("/api/v1/accounts").status_code == 503
    assert client.post("/api/v1/auth/login", json={"password": PASSWORD}).status_code == 503


def test_enable_banking_callback_stays_public() -> None:
    # The bank redirects the browser here with no session; it must not 401.
    client = build_client(make_settings())
    response = client.get("/enable_banking_items/callback", follow_redirects=False)
    assert response.status_code == 303


def test_password_hash_round_trips() -> None:
    digest = hash_password(PASSWORD)
    assert verify_password(PASSWORD, digest) is True
    assert verify_password("nope", digest) is False
    assert verify_password(PASSWORD, "") is False


def test_session_token_round_trips_and_expires() -> None:
    token = create_session_token(secret_key="k", max_age_seconds=3600)
    assert verify_session_token(secret_key="k", token=token) == "owner"
    assert verify_session_token(secret_key="other", token=token) is None

    expired = create_session_token(secret_key="k", max_age_seconds=-1)
    time.sleep(0.01)
    assert verify_session_token(secret_key="k", token=expired) is None

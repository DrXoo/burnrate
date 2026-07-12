from __future__ import annotations

from collections.abc import Callable
from functools import lru_cache

from fastapi import Depends, HTTPException, Request, Response, status
from sqlalchemy.orm import Session

from burnrate.config import Settings, get_settings
from burnrate.db.session import get_db
from burnrate.integrations.enable_banking.client import EnableBankingClient
from burnrate.security import (
    LoginRateLimiter,
    RateLimiter,
    create_session_token,
    verify_session_token,
)
from burnrate.services.budget_service import BudgetService
from burnrate.services.categorization_service import CategorizationService
from burnrate.services.enable_banking_service import EnableBankingService
from burnrate.services.ledger_service import LedgerService
from burnrate.services.rules_service import RulesService
from burnrate.services.summary_service import SummaryService


@lru_cache(maxsize=1)
def _login_rate_limiter(max_attempts: int, lockout_seconds: int) -> LoginRateLimiter:
    return LoginRateLimiter(max_attempts=max_attempts, lockout_seconds=lockout_seconds)


def get_login_rate_limiter(
    settings: Settings = Depends(get_settings),
) -> LoginRateLimiter:
    return _login_rate_limiter(
        settings.auth_login_max_attempts,
        settings.auth_login_lockout_seconds,
    )


@lru_cache(maxsize=None)
def _rate_limiter(bucket: str, max_requests: int, window_seconds: int) -> RateLimiter:
    return RateLimiter(max_requests=max_requests, window_seconds=window_seconds)


def enforce_rate_limit(bucket: str) -> Callable[..., None]:
    """Build a dependency that fixed-window rate-limits a route by client IP.

    Buckets are independent, so a burst of syncs will not exhaust the budget for
    starting a new bank authorization. Applied on top of ``require_auth``, so it
    guards the upstream bank API from an authenticated client looping requests.
    """

    def dependency(
        request: Request,
        settings: Settings = Depends(get_settings),
    ) -> None:
        limiter = _rate_limiter(
            bucket,
            settings.bank_rate_limit_max_requests,
            settings.bank_rate_limit_window_seconds,
        )
        key = request.client.host if request.client is not None else "unknown"
        retry_after = limiter.hit(key)
        if retry_after > 0:
            raise HTTPException(
                status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                detail="Rate limit exceeded. Please slow down and try again shortly.",
                headers={"Retry-After": str(int(retry_after) + 1)},
            )

    return dependency


def get_optional_identity(
    request: Request,
    settings: Settings = Depends(get_settings),
) -> str | None:
    """Return the caller's identity from the session cookie, or None if absent."""
    token = request.cookies.get(settings.auth_cookie_name)
    if not token:
        return None
    return verify_session_token(secret_key=settings.auth_secret_key, token=token)


def _set_session_cookie(*, response: Response, settings: Settings, token: str) -> None:
    response.set_cookie(
        key=settings.auth_cookie_name,
        value=token,
        max_age=settings.auth_session_max_age_seconds,
        httponly=True,
        secure=settings.auth_cookie_secure,
        samesite="strict",
        path="/",
    )


def require_auth(
    request: Request,
    response: Response,
    settings: Settings = Depends(get_settings),
) -> str:
    """Gate a route behind a valid session cookie.

    Fails closed: if authentication is not configured the route is unreachable
    (503) rather than open. On success the session cookie is re-issued so an
    active user's window slides forward instead of expiring mid-use.
    """
    if not settings.auth_configured:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Authentication is not configured",
        )
    token = request.cookies.get(settings.auth_cookie_name)
    identity = verify_session_token(secret_key=settings.auth_secret_key, token=token) if token else None
    if identity is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Authentication required",
        )
    refreshed = create_session_token(
        secret_key=settings.auth_secret_key,
        max_age_seconds=settings.auth_session_max_age_seconds,
    )
    _set_session_cookie(response=response, settings=settings, token=refreshed)
    return identity


def get_enable_banking_client(
    settings: Settings = Depends(get_settings),
) -> EnableBankingClient:
    return EnableBankingClient(settings=settings)


def get_enable_banking_service(
    db: Session = Depends(get_db),
    settings: Settings = Depends(get_settings),
    client: EnableBankingClient = Depends(get_enable_banking_client),
) -> EnableBankingService:
    return EnableBankingService(db=db, settings=settings, client=client)


def get_ledger_service(
    db: Session = Depends(get_db),
) -> LedgerService:
    return LedgerService(db=db)


def get_categorization_service(
    db: Session = Depends(get_db),
) -> CategorizationService:
    return CategorizationService(db=db)


def get_rules_service(
    db: Session = Depends(get_db),
) -> RulesService:
    return RulesService(db=db)


def get_budget_service(
    db: Session = Depends(get_db),
) -> BudgetService:
    return BudgetService(db=db)


def get_summary_service(
    db: Session = Depends(get_db),
) -> SummaryService:
    return SummaryService(db=db)

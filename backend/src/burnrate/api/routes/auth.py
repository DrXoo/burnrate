from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Request, Response, status
from pydantic import BaseModel

from burnrate.api.dependencies import (
    _set_session_cookie,
    get_login_rate_limiter,
    get_optional_identity,
)
from burnrate.config import Settings, get_settings
from burnrate.security import (
    LoginRateLimiter,
    create_session_token,
    verify_password,
)

router = APIRouter(prefix="/auth", tags=["auth"])


class LoginRequest(BaseModel):
    password: str


class AuthStatusResponse(BaseModel):
    authenticated: bool


def _client_key(request: Request) -> str:
    client = request.client
    return client.host if client is not None else "unknown"


@router.post("/login", response_model=AuthStatusResponse)
def login(
    payload: LoginRequest,
    request: Request,
    response: Response,
    settings: Settings = Depends(get_settings),
    limiter: LoginRateLimiter = Depends(get_login_rate_limiter),
) -> AuthStatusResponse:
    if not settings.auth_configured:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Authentication is not configured",
        )

    key = _client_key(request)
    locked_for = limiter.seconds_until_unlocked(key)
    if locked_for > 0:
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail=f"Too many attempts. Try again in {int(locked_for) + 1} seconds.",
        )

    if not verify_password(payload.password, settings.auth_password_hash):
        limiter.record_failure(key)
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid credentials",
        )

    limiter.reset(key)
    token = create_session_token(
        secret_key=settings.auth_secret_key,
        max_age_seconds=settings.auth_session_max_age_seconds,
    )
    _set_session_cookie(response=response, settings=settings, token=token)
    return AuthStatusResponse(authenticated=True)


@router.post("/logout", response_model=AuthStatusResponse)
def logout(
    response: Response,
    settings: Settings = Depends(get_settings),
) -> AuthStatusResponse:
    response.delete_cookie(
        key=settings.auth_cookie_name,
        path="/",
        httponly=True,
        secure=settings.auth_cookie_secure,
        samesite="strict",
    )
    return AuthStatusResponse(authenticated=False)


@router.get("/me", response_model=AuthStatusResponse)
def me(
    identity: str | None = Depends(get_optional_identity),
) -> AuthStatusResponse:
    return AuthStatusResponse(authenticated=identity is not None)

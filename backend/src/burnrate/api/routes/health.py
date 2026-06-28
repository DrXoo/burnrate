from __future__ import annotations

from fastapi import APIRouter

from burnrate.config import get_settings

router = APIRouter(tags=["health"])


@router.get("/health")
def healthcheck() -> dict[str, str]:
    settings = get_settings()
    return {
        "status": "ok",
        "service": "burnrate-backend",
        "environment": settings.app_env,
    }


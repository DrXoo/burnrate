from __future__ import annotations

import logging
from contextlib import asynccontextmanager

from fastapi import Depends, FastAPI
from fastapi.middleware.cors import CORSMiddleware

from burnrate.api.dependencies import require_auth
from burnrate.api.observability import register_observability
from burnrate.api.security_headers import register_security_headers
from burnrate.logging_config import configure_logging
from burnrate.api.routes.auth import router as auth_router
from burnrate.api.routes.budgets import router as budgets_router
from burnrate.api.routes.categorization import router as categorization_router
from burnrate.api.routes.enable_banking import public_router as enable_banking_public_router
from burnrate.api.routes.enable_banking import router as enable_banking_router
from burnrate.api.routes.health import router as health_router
from burnrate.api.routes.ledger import router as ledger_router
from burnrate.api.routes.rules import router as rules_router
from burnrate.api.routes.summary import router as summary_router
from burnrate.config import get_settings


@asynccontextmanager
async def lifespan(app: FastAPI):
    settings = get_settings()
    configure_logging(settings.log_level)
    logger = logging.getLogger("burnrate.api")
    logger.info("BurnRate API starting (env=%s)", settings.app_env)
    if not settings.auth_configured:
        logger.warning(
            "Authentication is NOT configured: set AUTH_PASSWORD_HASH and "
            "AUTH_SECRET_KEY. Protected endpoints will refuse requests (503) "
            "until this is set."
        )
    yield


def create_app() -> FastAPI:
    settings = get_settings()

    # Only expose the interactive API schema in development; in production the
    # full endpoint surface should not be advertised.
    expose_docs = settings.is_development

    app = FastAPI(
        title="BurnRate API",
        version="0.1.0",
        docs_url="/docs" if expose_docs else None,
        redoc_url="/redoc" if expose_docs else None,
        openapi_url="/openapi.json" if expose_docs else None,
        lifespan=lifespan,
    )
    register_observability(app)
    register_security_headers(app)
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origins,
        allow_credentials=True,
        # Only the verbs and headers the Web UI actually uses, instead of "*".
        allow_methods=["GET", "POST", "PATCH", "DELETE", "OPTIONS"],
        allow_headers=["Accept", "Content-Type"],
    )

    # Open routes: health probe, the auth endpoints themselves, and the bank
    # OAuth callback (the browser arrives here from the bank with no session;
    # it is guarded by the unguessable authorization `state`).
    app.include_router(health_router, prefix="/api/v1")
    app.include_router(auth_router, prefix="/api/v1")
    app.include_router(enable_banking_public_router)

    # Everything else requires a valid session cookie.
    protected = Depends(require_auth)
    app.include_router(enable_banking_router, prefix="/api/v1", dependencies=[protected])
    app.include_router(ledger_router, prefix="/api/v1", dependencies=[protected])
    app.include_router(categorization_router, prefix="/api/v1", dependencies=[protected])
    app.include_router(rules_router, prefix="/api/v1", dependencies=[protected])
    app.include_router(budgets_router, prefix="/api/v1", dependencies=[protected])
    app.include_router(summary_router, prefix="/api/v1", dependencies=[protected])
    return app


app = create_app()

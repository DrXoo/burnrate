from __future__ import annotations

import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from burnrate.api.observability import register_observability
from burnrate.logging_config import configure_logging
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
    logging.getLogger("burnrate.api").info("BurnRate API starting (env=%s)", settings.app_env)
    yield


def create_app() -> FastAPI:
    settings = get_settings()

    app = FastAPI(
        title="BurnRate API",
        version="0.1.0",
        docs_url="/docs",
        openapi_url="/openapi.json",
        lifespan=lifespan,
    )
    register_observability(app)
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origins,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )
    app.include_router(health_router, prefix="/api/v1")
    app.include_router(enable_banking_router, prefix="/api/v1")
    app.include_router(ledger_router, prefix="/api/v1")
    app.include_router(categorization_router, prefix="/api/v1")
    app.include_router(rules_router, prefix="/api/v1")
    app.include_router(budgets_router, prefix="/api/v1")
    app.include_router(summary_router, prefix="/api/v1")
    app.include_router(enable_banking_public_router)
    return app


app = create_app()

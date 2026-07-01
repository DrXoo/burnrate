from __future__ import annotations

import logging

from fastapi import FastAPI, HTTPException
from fastapi.testclient import TestClient

from burnrate.api.observability import register_observability
from burnrate.logging_config import configure_logging
from burnrate.main import create_app


def build_app_with_routes() -> FastAPI:
    app = FastAPI()
    register_observability(app)

    @app.get("/boom")
    def boom():
        raise RuntimeError("kaboom")

    @app.get("/not-found")
    def not_found():
        raise HTTPException(status_code=404, detail="missing thing")

    @app.get("/ok")
    def ok():
        return {"ok": True}

    return app


def test_unhandled_exception_returns_shaped_500_and_is_logged(caplog) -> None:
    client = TestClient(build_app_with_routes(), raise_server_exceptions=False)

    with caplog.at_level(logging.ERROR):
        response = client.get("/boom")

    assert response.status_code == 500
    assert response.json() == {"detail": "Internal server error"}
    # The failure must be logged with enough context to diagnose it.
    assert "Unhandled error on GET /boom" in caplog.text
    assert "kaboom" in caplog.text


def test_http_exception_is_not_swallowed_by_handler() -> None:
    client = TestClient(build_app_with_routes(), raise_server_exceptions=False)

    response = client.get("/not-found")

    # Deliberate HTTPExceptions must keep their status/detail, not become a 500.
    assert response.status_code == 404
    assert response.json() == {"detail": "missing thing"}


def test_request_logging_middleware_logs_method_path_and_status(caplog) -> None:
    client = TestClient(build_app_with_routes())

    with caplog.at_level(logging.INFO, logger="burnrate.request"):
        client.get("/ok")

    assert "GET /ok -> 200" in caplog.text


def test_configure_logging_sets_root_level() -> None:
    try:
        configure_logging("WARNING")
        assert logging.getLogger().level == logging.WARNING
    finally:
        configure_logging("INFO")


def test_create_app_registers_exception_handler() -> None:
    app = create_app()

    assert Exception in app.exception_handlers

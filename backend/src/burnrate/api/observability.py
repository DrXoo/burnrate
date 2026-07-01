from __future__ import annotations

import logging
import time
from collections.abc import Awaitable, Callable

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse, Response

logger = logging.getLogger("burnrate.api")
request_logger = logging.getLogger("burnrate.request")


async def log_requests(
    request: Request,
    call_next: Callable[[Request], Awaitable[Response]],
) -> Response:
    """Log each handled request with its method, path, status, and duration."""
    started_at = time.perf_counter()
    response = await call_next(request)
    duration_ms = (time.perf_counter() - started_at) * 1000
    request_logger.info(
        "%s %s -> %s (%.1fms)",
        request.method,
        request.url.path,
        response.status_code,
        duration_ms,
    )
    return response


async def handle_unexpected_exception(request: Request, exc: Exception) -> JSONResponse:
    """Log an unhandled error with traceback and return a consistent 500 shape.

    Deliberate ``HTTPException``s keep their own handler, so this only fires for
    genuinely unexpected failures. The client never sees a stack trace.
    """
    logger.exception("Unhandled error on %s %s", request.method, request.url.path)
    return JSONResponse(status_code=500, content={"detail": "Internal server error"})


def register_observability(app: FastAPI) -> None:
    app.middleware("http")(log_requests)
    app.add_exception_handler(Exception, handle_unexpected_exception)

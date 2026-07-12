from __future__ import annotations

from collections.abc import Awaitable, Callable

from fastapi import FastAPI, Request
from fastapi.responses import Response

# Applied to every API response. Deliberately conservative and framework-safe:
# no Content-Security-Policy here (the docs UI in development loads its own
# assets, and the meaningful CSP lives on the web server that serves the SPA).
# HSTS is intentionally omitted — it belongs on the TLS-terminating proxy and is
# a no-op (or a foot-gun) over plain http.
_SECURITY_HEADERS = {
    "X-Content-Type-Options": "nosniff",
    "X-Frame-Options": "DENY",
    "Referrer-Policy": "no-referrer",
    "Cross-Origin-Opener-Policy": "same-origin",
    # Financial data should never be cached by intermediaries or the browser.
    "Cache-Control": "no-store",
}


async def add_security_headers(
    request: Request,
    call_next: Callable[[Request], Awaitable[Response]],
) -> Response:
    response = await call_next(request)
    for header, value in _SECURITY_HEADERS.items():
        # setdefault: never clobber a header a route set deliberately.
        response.headers.setdefault(header, value)
    return response


def register_security_headers(app: FastAPI) -> None:
    app.middleware("http")(add_security_headers)

"""Reverse-proxy gateway authentication (OT LAN — not for public internet)."""

from __future__ import annotations

import os

from fastapi import Request
from starlette.responses import JSONResponse

# Caddy sets this header on traffic to the API; the browser never holds this secret.
_GATEWAY_HEADER = "x-bas-lite-gateway-token"

# Liveness/readiness for Docker without the gateway secret (do not expose API port to the LAN).
_EXEMPT_PATHS = frozenset({"/api/v1/health", "/app8/api/health"})

# EventSource and browser WebSocket cannot attach X-Bas-Lite-Gateway-Token; SPA sends it on fetch only.
_EXEMPT_PATH_PREFIXES: tuple[str, ...] = (
    "/app8/api/system/container-logs/stream",
    "/app8/api/ws/",
)


def attach_gateway_auth_if_configured(app) -> None:
    token = (os.environ.get("BAS_LITE_GATEWAY_TOKEN") or "").strip()
    if not token:
        return
    expected = f"Bearer {token}"

    @app.middleware("http")
    async def _require_gateway_header(request: Request, call_next):  # type: ignore[misc]
        if request.url.path in _EXEMPT_PATHS:
            return await call_next(request)
        if any(request.url.path.startswith(p) for p in _EXEMPT_PATH_PREFIXES):
            return await call_next(request)
        got = (request.headers.get(_GATEWAY_HEADER) or "").strip()
        exp = expected.strip()
        if got != exp:
            return JSONResponse(
                status_code=401,
                content={
                    "detail": "Missing or invalid gateway token (set BAS_LITE_GATEWAY_TOKEN on api; SPA loads it from /app8/config.runtime.js in Docker).",
                },
            )
        return await call_next(request)

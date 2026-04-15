"""Reverse-proxy gateway authentication (OT LAN — not for public internet)."""

from __future__ import annotations

import os

from fastapi import Request
from starlette.responses import JSONResponse

# Caddy sets this header on traffic to the API; the browser never holds this secret.
_GATEWAY_HEADER = "x-bas-lite-gateway-token"

# Liveness/readiness for Docker without the gateway secret (do not expose API port to the LAN).
_EXEMPT_PATHS = frozenset({"/api/v1/health", "/app8/api/health"})


def attach_gateway_auth_if_configured(app) -> None:
    token = (os.environ.get("BAS_LITE_GATEWAY_TOKEN") or "").strip()
    if not token:
        return
    expected = f"Bearer {token}"

    @app.middleware("http")
    async def _require_gateway_header(request: Request, call_next):  # type: ignore[misc]
        if request.url.path in _EXEMPT_PATHS:
            return await call_next(request)
        if request.headers.get(_GATEWAY_HEADER) != expected:
            return JSONResponse(
                status_code=401,
                content={"detail": "Missing or invalid gateway token (configure Caddy header_up)."},
            )
        return await call_next(request)

"""BAS Lite: easy-aso supervisor + legacy /app8/api for the React SPA."""

from __future__ import annotations

from easy_aso.supervisor.app import create_supervisor_app

from bas_lite_api.gateway_auth import attach_gateway_auth_if_configured
from bas_lite_api.legacy_routes import register_legacy

app = create_supervisor_app()
register_legacy(app)
attach_gateway_auth_if_configured(app)

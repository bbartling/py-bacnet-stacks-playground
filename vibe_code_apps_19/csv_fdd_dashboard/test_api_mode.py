"""Smoke tests for DASHBOARD_MODE=api (headless JSON API, Flavor A)."""

from __future__ import annotations

from fastapi.testclient import TestClient


def test_api_mode_root_and_no_html_shell():
    from app import create_app

    client = TestClient(create_app("api"))
    r = client.get("/")
    assert r.status_code == 200
    body = r.json()
    assert body["mode"] == "api"
    assert body["docs"] == "/docs"

    r2 = client.get("/index.html")
    assert r2.status_code == 404
    assert "api mode" in r2.json().get("error", "").lower()

    r3 = client.get("/health")
    assert r3.status_code in (200, 503)
    assert r3.json()["mode"] == "api"

    r4 = client.get("/api/pages")
    assert r4.status_code == 200
    assert "pages" in r4.json()

"""Smoke tests for Vibe 21 Flask demand_hourly API."""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

_VIBE21 = Path(__file__).resolve().parents[1]
if str(_VIBE21) not in sys.path:
    sys.path.insert(0, str(_VIBE21))


@pytest.fixture(scope="module")
def client():
    from flask_app.app import create_app
    from flask_app.model_loader import clear_bundle_cache

    clear_bundle_cache()
    app = create_app()
    app.config["TESTING"] = True
    with app.test_client() as c:
        yield c


def test_health(client):
    r = client.get("/api/v1/health")
    assert r.status_code in (200, 503)
    data = r.get_json()
    assert data["service"] == "vibe21-dm-twin"


def test_root_stub_without_webgl(client):
    r = client.get("/")
    assert r.status_code == 200
    data = r.get_json()
    assert data["service"] == "vibe21-dm-twin"
    assert "health" in data
    assert data.get("notebook") == "/notebooks/demand_hourly"


def test_notebook_html_route(client):
    r = client.get("/notebooks/demand_hourly")
    assert r.status_code == 200
    assert "html" in r.content_type.lower() or r.data[:20].lower().startswith(b"<!doctype") or b"<html" in r.data[:200].lower()


def test_twin_manifest(client):
    r = client.get("/api/v1/twin/manifest")
    assert r.status_code == 200
    data = r.get_json()
    assert data["twin_run_id"] == "geo_b100_dual_ahu_shape_ops11"
    assert "zones" in data


def test_models_and_predict(client):
    h = client.get("/api/v1/health")
    if h.status_code != 200:
        pytest.skip(f"model not loadable: {h.get_json()}")
    m = client.get("/api/v1/models")
    assert m.status_code == 200
    assert m.get_json()["models"][0]["model_id"] == "demand_hourly_v1"
    r = client.post(
        "/api/v1/predict/demand_hourly",
        json={
            "hour_ending": 15,
            "oat_c": 34.0,
            "rh_pct": 50.0,
            "strategy_id": "precool_shift",
            "phase": "precool",
            "precool_f": 3.0,
            "in_dr_window": 1,
            "facility_kw_lag1": 220.0,
            "facility_kw_lag2": 210.0,
            "oat_lag1": 33.0,
        },
    )
    assert r.status_code == 200, r.get_json()
    data = r.get_json()
    assert "facility_kw" in data
    assert data["unit"] == "kW"
    assert data["model_status"] == "CANDIDATE"
    assert data["provenance"]["source"] == "ENERGYPLUS_SIMULATED"

"""FastAPI surface for the live twin."""

from fastapi.testclient import TestClient

from vibe24.api import create_app
from vibe24.runtime import TwinRuntime


def test_healthz_and_write_relinquish():
    rt = TwinRuntime()
    app = create_app(rt, auto_tick=False)
    client = TestClient(app)

    hz = client.get("/healthz")
    assert hz.status_code == 200
    assert hz.json()["claim"] == "SURROGATE_PLANT_V1"

    points = client.get("/points")
    assert points.status_code == 200
    names = {p["name"] for p in points.json()["points"]}
    assert {"ZONE-T", "HEAT-SP", "COOL-SP"}.issubset(names)

    w = client.post("/points/HEAT-SP/write", json={"value": 69.0, "priority": 8, "source": "ui"})
    assert w.status_code == 200
    body = w.json()
    assert body["present_value"] == 69.0
    assert body["winning_priority"] == 8

    r = client.post("/points/HEAT-SP/relinquish", json={"priority": 8})
    assert r.status_code == 200
    assert r.json()["winning_priority"] == 16

    tick = client.post("/tick?sim_minutes=5")
    assert tick.status_code == 200
    assert "ZONE-T" in tick.json()["sensors"]


def test_cannot_write_sensor():
    app = create_app(TwinRuntime(), auto_tick=False)
    client = TestClient(app)
    resp = client.post("/points/ZONE-T/write", json={"value": 80.0, "priority": 8})
    assert resp.status_code == 400

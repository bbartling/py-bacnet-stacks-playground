"""FastAPI surface for the live twin."""

from fastapi.testclient import TestClient

from vibe24.api import create_app
from vibe24.runtime import TwinRuntime


def test_healthz_and_zone_sp_writes_eff():
    rt = TwinRuntime()
    app = create_app(rt, auto_tick=False)
    client = TestClient(app)

    hz = client.get("/healthz")
    assert hz.status_code == 200
    assert "PLANT" in hz.json()["claim"] or "ENERGYPLUS" in hz.json()["claim"] or "SURROGATE" in hz.json()["claim"]

    points = client.get("/points")
    assert points.status_code == 200
    payload = points.json()
    names = {p["name"] for p in payload["points"]}
    assert {"ZONE-T", "ZONE-SP", "DEADBAND", "HEAT-EFF", "COOL-EFF"}.issubset(names)
    clock = payload["clock"]
    assert clock["month"] == 7 and clock["day"] == 15

    w = client.post("/points/ZONE-SP/write", json={"value": 70.0, "priority": 8, "source": "ui"})
    assert w.status_code == 200
    body = w.json()
    assert body["present_value"] == 70.0
    assert body["heat_eff"] == 69.0
    assert body["cool_eff"] == 71.0

    # HEAT-EFF is sensor — writes rejected
    bad = client.post("/points/HEAT-EFF/write", json={"value": 60.0, "priority": 8})
    assert bad.status_code == 400

    r = client.post("/points/ZONE-SP/relinquish", json={"priority": 8})
    assert r.status_code == 200

    tick = client.post("/tick?sim_minutes=5")
    assert tick.status_code == 200
    assert "ZONE-T" in tick.json()["sensors"]


def test_live_speed_and_pause():
    rt = TwinRuntime(wall_seconds_per_sim_minute=12.0)
    app = create_app(rt, auto_tick=False)
    client = TestClient(app)

    r = client.post("/speed", json={"realtime_factor": 10})
    assert r.status_code == 200
    assert r.json()["clock"]["realtime_factor"] == 10.0
    assert rt.wall_seconds_per_sim_minute == 6.0

    p = client.post("/pause", json={"paused": True})
    assert p.status_code == 200
    assert p.json()["clock"]["paused"] is True

    s = client.post("/step?sim_minutes=1")
    assert s.status_code == 200

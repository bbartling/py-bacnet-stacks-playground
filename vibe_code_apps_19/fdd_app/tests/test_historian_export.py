"""Tests for open-fdd historian export bridge."""

import json

import pandas as pd

import historian_export as he


def test_row_from_frame_maps_roles():
    idx = pd.date_range("2026-05-01", periods=3, freq="5min", tz="UTC")
    d = pd.DataFrame({
        "timestamp": idx,
        "zone_t": [72.0, 73.0, 74.0],
        "oa_t": [65.0, 66.0, 67.0],
    })
    resolved = {"zone_t": "zone_t", "oa_t": "oa_t"}
    rows = he._row_from_frame("VAV_1", d, resolved)
    assert len(rows) == 3
    assert rows[0]["equipment_id"] == "VAV_1"
    assert rows[0]["zn_t"] == 72.0
    assert rows[0]["oa_t"] == 65.0


def test_needs_export_missing(tmp_path, monkeypatch):
    monkeypatch.setattr(he, "export_dir", lambda: tmp_path / "hist" / "vibe19")
    assert he.needs_export() is True


def test_export_meta_written(tmp_path, monkeypatch):
    dest = tmp_path / "hist" / "vibe19"
    monkeypatch.setattr(he, "export_dir", lambda: dest)
    monkeypatch.setattr(he, "export_all", lambda **kw: {
        "ok": True, "row_count": 0, "path": str(dest / "telemetry_pivot.jsonl"),
        "data_token": "tok", "equipment_count": 0, "errors": [],
    })
    meta = he.export_all()
    assert meta["ok"] is True

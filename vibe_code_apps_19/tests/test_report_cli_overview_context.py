"""CLI overview_context wiring (BUG-015)."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

import pandas as pd

from app.reporting.cli import _overview_context_from_dataset


@dataclass
class _FakeDS:
    building_id: str = "B1"
    frames: dict = field(default_factory=dict)
    weather: Any = None
    role_map: dict = field(default_factory=dict)
    params: dict = field(default_factory=dict)
    prefer_web_oat: bool = True
    chw_leave_max_f: float = 48.0
    use_mech_cooling_status_proof: bool = True
    session_config: dict | None = None


def test_overview_context_from_dataset_includes_frames_and_settings():
    idx = pd.date_range("2026-06-01", periods=3, freq="h", tz="UTC")
    frames = {"AHU_1": pd.DataFrame({"x": [1, 2, 3]}, index=idx)}
    ds = _FakeDS(
        frames=frames,
        role_map={"AHU_1": {"supply-fan-status": "fan"}},
        session_config={"zone_lo_f": 68.0, "zone_hi_f": 76.0},
        params={"OAT-METEO": {"oat_err": 4.0}},
    )
    ctx = _overview_context_from_dataset(ds)
    assert ctx["frames"] is frames
    assert ctx["role_map"]["AHU_1"]["supply-fan-status"] == "fan"
    assert ctx["zone_lo_f"] == 68.0
    assert ctx["oat_err"] == 4.0
    assert ctx["span_hours"] is not None
    assert "frames" not in __import__(
        "app.reporting.overview_export", fromlist=["overview_settings_from_context"]
    ).overview_settings_from_context(ctx)

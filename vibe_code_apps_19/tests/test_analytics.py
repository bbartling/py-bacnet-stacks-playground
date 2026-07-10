"""Analytics helpers for Overview / Analytics tabs."""

from __future__ import annotations

import pandas as pd

from app.analytics import dataset_time_span, motor_run_hours_for_frame, motor_run_hours_totals


def test_dataset_time_span():
    idx = pd.date_range("2024-01-01", periods=3, freq="1h", tz="UTC")
    frames = {"AHU_1": pd.DataFrame({"x": [1, 2, 3]}, index=idx)}
    span = dataset_time_span(frames)
    assert span["start"] == idx[0]
    assert span["end"] == idx[-1]
    assert span["span_hours"] == 2.0


def test_motor_run_hours():
    idx = pd.date_range("2024-01-01", periods=10, freq="6min", tz="UTC")
    # 5 of 10 samples on at 6 min → 0.5 hours
    df = pd.DataFrame({"fan_cmd": [0, 0, 0, 0, 0, 100, 100, 100, 100, 100]}, index=idx)
    rows = motor_run_hours_for_frame(df, poll_seconds=360.0, equipment_id="AHU_1")
    assert len(rows) == 1
    assert rows[0]["run_hours"] == 0.5
    tot = motor_run_hours_totals(pd.DataFrame(rows))
    assert tot["fan_hours"] == 0.5


def test_mech_cooling_bins_chiller_not_cool_valve_ahu():
    from app.analytics import mech_cooling_oat_bins

    idx = pd.date_range("2024-06-01", periods=10, freq="1h", tz="UTC")
    ch = pd.DataFrame(
        {"chw_pump_cmd": [100] * 10, "oa_t": [50, 55, 60, 65, 70, 75, 80, 85, 90, 95]},
        index=idx,
    )
    ch.attrs["equipment_type"] = "CHW_PLANT"
    ahu_valve = pd.DataFrame(
        {"clg_valve_pct": [100] * 10, "oa_t": [70] * 10, "fan_cmd": [50] * 10},
        index=idx,
    )
    ahu_valve.attrs["equipment_type"] = "AHU"
    ahu_dx = pd.DataFrame(
        {"compressor_status": [1] * 10, "oa_t": [72] * 10},
        index=idx,
    )
    ahu_dx.attrs["equipment_type"] = "AHU"
    bins = mech_cooling_oat_bins(
        {"CHW_1": ch, "AHU_VALVE": ahu_valve, "AHU_DX": ahu_dx},
        role_map={},
    )
    sources = set(bins["equipment_id"]) if not bins.empty else set()
    assert "CHW_1" in sources
    assert "AHU_DX" in sources
    assert "AHU_VALVE" not in sources


def test_all_rules_have_confirm_min():
    from app.rules import RULES

    for r in RULES:
        keys = {p.key for p in r.params}
        assert "confirm_min" in keys, r.id
        conf = next(p for p in r.params if p.key == "confirm_min")
        assert conf.default == 0.0, r.id
        assert conf.min == 0.0, r.id

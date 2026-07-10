"""Analytics helpers for Overview / Analytics tabs."""

from __future__ import annotations

import pandas as pd
import pytest

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


def test_mech_cooling_bins_flexible_proof():
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
    # Default: include AHU CHW valve
    bins = mech_cooling_oat_bins(
        {"CHW_1": ch, "AHU_VALVE": ahu_valve, "AHU_DX": ahu_dx},
        role_map={},
        include_ahu_chw_valve=True,
    )
    sources = set(bins["equipment_id"]) if not bins.empty else set()
    assert "CHW_1" in sources
    assert "AHU_DX" in sources
    assert "AHU_VALVE" in sources
    # Opt out of valve
    bins2 = mech_cooling_oat_bins(
        {"CHW_1": ch, "AHU_VALVE": ahu_valve, "AHU_DX": ahu_dx},
        role_map={},
        include_ahu_chw_valve=False,
    )
    sources2 = set(bins2["equipment_id"]) if not bins2.empty else set()
    assert "AHU_VALVE" not in sources2


def test_mech_cooling_chiller_amps_and_chw_temp():
    from app.analytics import mech_cooling_run_mask

    idx = pd.date_range("2024-06-01", periods=5, freq="1h", tz="UTC")
    df = pd.DataFrame(
        {"chiller_amps": [0, 0, 20, 30, 0], "chw_supply_t": [55, 55, 55, 44, 44]},
        index=idx,
    )
    run, kind = mech_cooling_run_mask(df, equipment_type="CHILLER", equipment_id="CHILLER_2")
    assert kind == "chiller_amps"
    assert bool(run.iloc[2])


def test_motor_run_hours_weekly():
    from app.analytics import motor_run_hours_weekly
    from app.charts import motor_weekly_runtime_chart

    idx = pd.date_range("2024-01-01", periods=14 * 24, freq="1h", tz="UTC")  # 2 weeks
    # On for first week only
    on = [1.0] * (7 * 24) + [0.0] * (7 * 24)
    df = pd.DataFrame({"fan_status": on, "fan_cmd": [100.0] * len(idx)}, index=idx)
    df.attrs["poll_seconds"] = 3600.0
    df.attrs["equipment_type"] = "AHU"
    frames = {"AHU_1": df}
    weekly = motor_run_hours_weekly(frames, role_map={})
    assert not weekly.empty
    assert set(weekly["signal"]) == {"fan_status"}  # prefers status over cmd
    assert set(weekly["plant_group"]) == {"air"}
    assert weekly["hours"].sum() == pytest.approx(7 * 24.0, rel=0.01)
    fig = motor_weekly_runtime_chart(weekly, title="Air side — supply fans")
    assert fig is not None


def test_motor_weekly_three_plants_pumps_chiller_tower():
    from app.analytics import motor_run_hours_weekly

    idx = pd.date_range("2024-01-01", periods=48, freq="1h", tz="UTC")
    on = [1.0] * 24 + [0.0] * 24

    ahu = pd.DataFrame(
        {
            "supply_fan_status": on,
            "return_fan_status": [1.0] * 48,  # must NOT appear
            "fan_cmd": [50.0] * 48,
        },
        index=idx,
    )
    ahu.attrs.update({"poll_seconds": 3600.0, "equipment_type": "AHU"})

    boiler = pd.DataFrame(
        {
            "hwp1_s": on,
            "hwp1_c": [100.0] * 48,
            "hwp2_s": on,
            "hwp2_c": [100.0] * 48,
            "hwp3_c": on,  # status missing → use cmd
        },
        index=idx,
    )
    boiler.attrs.update({"poll_seconds": 3600.0, "equipment_type": "BOILER"})

    chiller = pd.DataFrame(
        {
            "chiller_status": on,
            "cwp1_s": on,
            "tower_fan_status": on,
            "chw_supply_t": [44.0] * 48,
        },
        index=idx,
    )
    chiller.attrs.update({"poll_seconds": 3600.0, "equipment_type": "CHW_PLANT"})

    # No cmd — estimate from leave temp
    chiller2 = pd.DataFrame(
        {"chw_supply_t": [44.0] * 24 + [55.0] * 24},
        index=idx,
    )
    chiller2.attrs.update({"poll_seconds": 3600.0, "equipment_type": "CHILLER"})

    weekly = motor_run_hours_weekly(
        {
            "AHU_1": ahu,
            "BOILERS_PUMPS": boiler,
            "CHILLER_1": chiller,
            "CHILLER_2": chiller2,
        },
        role_map={},
        chw_leave_max_f=48.0,
    )
    assert not weekly.empty
    air = weekly[weekly["plant_group"] == "air"]
    assert set(air["label"]) == {"AHU_1 · fan_status"}
    assert "return" not in " ".join(air["label"]).lower()

    boiler_w = weekly[weekly["plant_group"] == "boiler"]
    labels_b = set(boiler_w["label"])
    assert "BOILERS_PUMPS · HWP1" in labels_b
    assert "BOILERS_PUMPS · HWP2" in labels_b
    assert "BOILERS_PUMPS · HWP3" in labels_b

    chill = weekly[weekly["plant_group"] == "chiller"]
    labels_c = set(chill["label"])
    assert any("CHILLER_1" in x and "chiller" in x for x in labels_c)
    assert any("CWP" in x.upper() for x in labels_c)
    assert any("tower" in x.lower() for x in labels_c)
    assert any("CHILLER_2" in x and "chw_leave" in x for x in labels_c)


def test_all_rules_have_confirm_min():
    from app.rules import RULES

    for r in RULES:
        keys = {p.key for p in r.params}
        assert "confirm_min" in keys, r.id
        conf = next(p for p in r.params if p.key == "confirm_min")
        assert conf.default == 0.0, r.id
        assert conf.min == 0.0, r.id

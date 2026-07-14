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
    df = pd.DataFrame({"fan-cmd": [0, 0, 0, 0, 0, 100, 100, 100, 100, 100]}, index=idx)
    rows = motor_run_hours_for_frame(df, poll_seconds=360.0, equipment_id="AHU_1")
    assert len(rows) == 1
    assert rows[0]["run_hours"] == 0.5
    tot = motor_run_hours_totals(pd.DataFrame(rows))
    assert tot["fan_hours"] == 0.5


def test_mech_cooling_bins_flexible_proof():
    from app.analytics import mech_cooling_oat_bins

    idx = pd.date_range("2024-06-01", periods=10, freq="1h", tz="UTC")
    ch = pd.DataFrame(
        {"chw-pump-cmd": [100] * 10, "outside-air-temp": [50, 55, 60, 65, 70, 75, 80, 85, 90, 95]},
        index=idx,
    )
    ch.attrs["equipment_type"] = "CHW_PLANT"
    ahu_valve = pd.DataFrame(
        {"cooling-valve": [100] * 10, "outside-air-temp": [70] * 10, "fan-cmd": [50] * 10},
        index=idx,
    )
    ahu_valve.attrs["equipment_type"] = "AHU"
    ahu_dx = pd.DataFrame(
        {"compressor-status": [1] * 10, "outside-air-temp": [72] * 10},
        index=idx,
    )
    ahu_dx.attrs["equipment_type"] = "AHU"
    # CHW valves never appear; DX + chiller pump do
    bins = mech_cooling_oat_bins(
        {"CHW_1": ch, "AHU_VALVE": ahu_valve, "AHU_DX": ahu_dx},
        role_map={},
        include_ahu_chw_valve=True,  # ignored — valves still excluded
    )
    sources = set(bins["equipment_id"]) if not bins.empty else set()
    assert "CHW_1" in sources
    assert "AHU_DX" in sources
    assert "AHU_VALVE" not in sources
    # Bins sorted cold → hot
    assert list(bins["bin_start"]) == sorted(bins["bin_start"])


def test_mech_cooling_chiller_amps_and_chw_temp():
    from app.analytics import mech_cooling_run_mask

    idx = pd.date_range("2024-06-01", periods=5, freq="1h", tz="UTC")
    df = pd.DataFrame(
        {"chiller-amps": [0, 0, 20, 30, 0], "chilled-water-supply-temp": [55, 55, 55, 44, 44]},
        index=idx,
    )
    run, kind = mech_cooling_run_mask(df, equipment_type="CHILLER", equipment_id="CHILLER_2")
    assert kind == "chiller-amps"
    assert bool(run.iloc[2])
    # Leave temp alone → no run proof (pump/status required)
    df2 = pd.DataFrame({"chilled-water-supply-temp": [44.0] * 5}, index=idx)
    run2, kind2 = mech_cooling_run_mask(df2, equipment_type="CHILLER", equipment_id="CHILLER_2")
    assert run2 is None
    assert kind2 == ""


def test_occupied_hours_and_weekly_oat():
    from app.analytics import motor_run_hours_weekly
    from app.occupancy import OccupancySchedule, occupied_hours_per_week

    sched = OccupancySchedule()  # Mon–Fri 06–18 default
    assert occupied_hours_per_week(sched) == pytest.approx(5 * 12.0)
    idx = pd.date_range("2024-01-01", periods=48, freq="1h", tz="UTC")
    df = pd.DataFrame(
        {"fan-status": [1.0] * 48, "outside-air-temp": [40.0] * 24 + [60.0] * 24},
        index=idx,
    )
    df.attrs.update({"poll_seconds": 3600.0, "equipment_type": "AHU"})
    weekly = motor_run_hours_weekly({"AHU_1": df}, role_map={}, prefer_web_oat=False)
    assert "avg_oat_f" in weekly.columns
    assert weekly["avg_oat_f"].notna().any()


def test_motor_run_hours_weekly():
    from app.analytics import motor_run_hours_weekly
    from app.charts import motor_weekly_runtime_chart

    idx = pd.date_range("2024-01-01", periods=14 * 24, freq="1h", tz="UTC")  # 2 weeks
    # On for first week only
    on = [1.0] * (7 * 24) + [0.0] * (7 * 24)
    df = pd.DataFrame({"fan-status": on, "fan-cmd": [100.0] * len(idx)}, index=idx)
    df.attrs["poll_seconds"] = 3600.0
    df.attrs["equipment_type"] = "AHU"
    frames = {"AHU_1": df}
    weekly = motor_run_hours_weekly(frames, role_map={})
    assert not weekly.empty
    assert set(weekly["signal"]) == {"fan-status"}  # prefers status over cmd
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
            "fan-cmd": [50.0] * 48,
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
            "chiller-status": on,  # must NOT drive weekly chiller series
            "cwp1_s": on,
            "tower_fan_status": on,
            "chilled-water-supply-temp": [44.0] * 48,
        },
        index=idx,
    )
    chiller.attrs.update({"poll_seconds": 3600.0, "equipment_type": "CHW_PLANT"})

    # No pump — must NOT invent leave-temp runtime
    chiller2 = pd.DataFrame(
        {"chilled-water-supply-temp": [44.0] * 24 + [55.0] * 24, "chiller-status": on},
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
        role_map={"CHILLER_1": {"chw-pump-status": "cwp1_s"}},
        chw_leave_max_f=48.0,
    )
    assert not weekly.empty
    air = weekly[weekly["plant_group"] == "air"]
    assert set(air["label"]) == {"AHU_1 · fan-status"}
    assert "return" not in " ".join(air["label"]).lower()

    boiler_w = weekly[weekly["plant_group"] == "boiler"]
    labels_b = set(boiler_w["label"])
    assert "BOILERS_PUMPS · HWP1" in labels_b
    assert "BOILERS_PUMPS · HWP2" in labels_b
    assert "BOILERS_PUMPS · HWP3" in labels_b

    chill = weekly[weekly["plant_group"] == "chiller"]
    labels_c = set(chill["label"])
    # Designated pump preferred over chiller_status when both exist
    assert any("CHILLER_1" in x and "chw-pump-status" in x for x in labels_c)
    assert not any("CHILLER_1" in x and "chiller-status" in x for x in labels_c)
    assert not any("chw_leave" in x for x in labels_c)
    # No pump: status fallback is allowed
    assert any("CHILLER_2" in x and "chiller-status" in x for x in labels_c)
    assert any("CWP" in x.upper() or "tower" in x.lower() for x in labels_c)


def test_chiller_runtime_leave_temp_only_still_empty():
    from app.analytics import motor_run_hours_weekly

    idx = pd.date_range("2024-01-01", periods=24, freq="1h", tz="UTC")
    ch = pd.DataFrame({"chilled-water-supply-temp": [44.0] * 12 + [55.0] * 12}, index=idx)
    ch.attrs.update({"poll_seconds": 3600.0, "equipment_type": "CHILLER"})
    weekly = motor_run_hours_weekly({"CHILLER_ONLY_TEMP": ch}, role_map={})
    chill = weekly[weekly["plant_group"] == "chiller"] if not weekly.empty else weekly
    assert chill.empty or not any("CHILLER_ONLY_TEMP" in str(x) for x in chill.get("label", []))


def test_chiller_runtime_compressor_status_fallback():
    from app.analytics import motor_run_hours_weekly

    idx = pd.date_range("2024-01-01", periods=24, freq="1h", tz="UTC")
    on = [1.0] * 12 + [0.0] * 12
    ch = pd.DataFrame({"compressor-status": on, "chilled-water-supply-temp": [44.0] * 24}, index=idx)
    ch.attrs.update({"poll_seconds": 3600.0, "equipment_type": "CHILLER"})
    weekly = motor_run_hours_weekly({"CH_DX": ch}, role_map={})
    chill = weekly[weekly["plant_group"] == "chiller"]
    assert any("CH_DX" in x and "compressor-status" in x for x in set(chill["label"]))


def test_chiller_runtime_linked_pump_equipment():
    from app.analytics import motor_run_hours_weekly

    idx = pd.date_range("2024-01-01", periods=24, freq="1h", tz="UTC")
    on = [1.0] * 12 + [0.0] * 12
    ch = pd.DataFrame({"chilled-water-supply-temp": [55.0] * 24}, index=idx)
    ch.attrs.update({"poll_seconds": 3600.0, "equipment_type": "CHILLER"})
    pumps = pd.DataFrame({"cwp1_s": on}, index=idx)
    pumps.attrs.update({"poll_seconds": 3600.0, "equipment_type": "CHW_PLANT"})
    weekly = motor_run_hours_weekly(
        {"CHILLER_1": ch, "CHW_PUMPS": pumps},
        role_map={
            "CHILLER_1": {
                "chw_pump_equipment": "CHW_PUMPS",
                "chw-pump-status": "cwp1_s",
            }
        },
    )
    chill = weekly[weekly["plant_group"] == "chiller"]
    assert any("CHILLER_1" in x and "chw-pump-status" in x for x in set(chill["label"]))
    assert chill.loc[chill["equipment_id"] == "CHILLER_1", "hours"].sum() == pytest.approx(12.0)


def test_all_rules_have_confirm_min():
    from app.rules import RULES

    for r in RULES:
        keys = {p.key for p in r.params}
        assert "confirm_min" in keys, r.id
        conf = next(p for p in r.params if p.key == "confirm_min")
        # CHW-NOLOAD-1 intentionally defaults to 30 minutes persistence
        expected = 30.0 if r.id == "CHW-NOLOAD-1" else 5.0
        assert conf.default == expected, r.id
        assert conf.min == 0.0, r.id
        assert conf.max == 60.0, r.id


def test_economizer_weather_summary_irregular_timestamps():
    from app.analytics import economizer_weather_summary

    # Irregular spacing: 5min then 10min then 5min…
    idx = pd.to_datetime(
        [
            "2024-06-01T00:00:00Z",
            "2024-06-01T00:05:00Z",
            "2024-06-01T00:15:00Z",
            "2024-06-01T00:20:00Z",
            "2024-06-01T00:30:00Z",
            "2024-06-01T00:35:00Z",
        ],
        utc=True,
    )
    ahu = pd.DataFrame(
        {
            "web-outside-air-temp": [65.0] * 6,
            "web-outside-air-dewpoint": [50.0] * 6,
            "outside-air-damper": [20.0, 20.0, 95.0, 95.0, 40.0, 40.0],
            "cooling-valve": [50.0] * 6,
            "compressor-status": [0, 0, 0, 0, 1, 1],
        },
        index=idx,
    )
    ahu.attrs["equipment_type"] = "AHU"
    # Midwinter sample for ECON-6 style hours — second frame colder
    cold = ahu.copy()
    cold["web-outside-air-temp"] = [20.0] * 6
    cold["compressor-status"] = [0] * 6
    cold.attrs["equipment_id"] = "AHU_COLD"
    cold.attrs["equipment_type"] = "AHU"
    ahu.attrs["equipment_id"] = "AHU_1"
    frames = {"AHU_1": ahu, "AHU_COLD": cold}
    role_map = {
        "AHU_1": {"equipment_type": "AHU"},
        "AHU_COLD": {"equipment_type": "AHU"},
    }
    out = economizer_weather_summary(frames, role_map)
    assert not out.empty
    row = out.loc[out["equipment_id"] == "AHU_1"].iloc[0]
    assert row["opportunity_hours"] > 0
    assert row["integrated_noncompliant_hours"] > 0
    assert row["integrated_compliant_hours"] > 0
    cold_row = out.loc[out["equipment_id"] == "AHU_COLD"].iloc[0]
    assert cold_row["winter_economizing_hours_below_25f"] > 0
    assert cold_row["prohibited_mech_hours_below_60f"] == 0.0


def test_resolve_equipment_type_priority_and_aliases():
    from app.site_model import normalize_equipment_type, resolve_equipment_type, stamp_equipment_type

    assert normalize_equipment_type("heatPump") == "HP"
    assert normalize_equipment_type("RTU") == "AHU"
    idx = pd.date_range("2024-01-01", periods=2, freq="1h", tz="UTC")
    df = pd.DataFrame({"x": [1, 2]}, index=idx)
    # id would say UNKNOWN; map wins
    assert (
        resolve_equipment_type(
            "UNIT_9",
            df=df,
            role_map={"UNIT_9": {"equipment_type": "BOILER", "pump-status": "p"}},
        )
        == "BOILER"
    )
    stamp_equipment_type(df, "RTU_1", column_map={"equipment": {"RTU_1": {"equipType": "rtu"}}})
    assert df.attrs["equipment_type"] == "AHU"


def test_motor_omit_fan_when_map_has_no_fan_roles():
    """Agent map without fan roles must not invent supply fan from raw columns."""
    from app.analytics import discover_plant_motor_series

    idx = pd.date_range("2024-01-01", periods=24, freq="1h", tz="UTC")
    ahu = pd.DataFrame(
        {"supply_fan_status": [1.0] * 24, "discharge-air-temp": [55.0] * 24},
        index=idx,
    )
    ahu.attrs.update({"poll_seconds": 3600.0, "equipment_type": "AHU"})
    found = discover_plant_motor_series(
        {"AHU_1": ahu},
        role_map={"AHU_1": {"discharge-air-temp": "discharge-air-temp", "equipment_type": "AHU"}},
    )
    assert not any(s["motor_kind"] == "fan" for s in found)


def test_rcx_typed_membership_no_id_substring():
    from app.rcx_plots import collect_oat_scatter

    idx = pd.date_range("2024-01-01", periods=3, freq="1h", tz="UTC")
    # Id looks like AHU but typed as BOILER — must not join AHU scatter
    df = pd.DataFrame({"hot-water-supply-temp": [140.0, 141.0, 142.0]}, index=idx)
    df.attrs["equipment_type"] = "BOILER"
    wx = pd.DataFrame({"web-outside-air-temp": [30.0, 32.0, 34.0]}, index=idx)
    out = collect_oat_scatter(
        {"AHU_LOOKALIKE": df},
        role_map={"AHU_LOOKALIKE": {"hot-water-supply-temp": "hot-water-supply-temp"}},
        y_role="hot-water-supply-temp",
        weather=wx,
        equipment_types=("AHU",),
    )
    assert out.empty
    out2 = collect_oat_scatter(
        {"AHU_LOOKALIKE": df},
        role_map={"AHU_LOOKALIKE": {"hot-water-supply-temp": "hot-water-supply-temp"}},
        y_role="hot-water-supply-temp",
        weather=wx,
        equipment_types=("BOILER",),
    )
    assert not out2.empty

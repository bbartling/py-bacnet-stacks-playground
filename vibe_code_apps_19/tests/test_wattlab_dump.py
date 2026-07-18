"""WattLab dump helpers — sensor stats, diurnal profiles, FDD findings."""

from __future__ import annotations

from pathlib import Path

import pandas as pd

from app.rules.base import RuleResult
from app.wattlab_dump import (
    critical_sensor_roles,
    diurnal_profiles,
    fdd_findings_table,
    sensor_stats_tables,
    setpoints_table,
    write_fdd_timeseries,
    write_manifest,
    write_wattlab_readme,
)


def _frames_and_map():
    idx = pd.date_range("2024-03-04 08:00", periods=8, freq="1h", tz="UTC")  # Monday
    ahu = pd.DataFrame(
        {
            "discharge-air-temp": [55.0, 55.5, 56.0, 55.2, 70.0, 70.5, 71.0, 70.2],
            "duct-static-pressure": [1.5] * 4 + [0.1] * 4,
            "duct-static-pressure-sp": [1.5] * 8,
            "fan-status": [1, 1, 1, 1, 0, 0, 0, 0],
        },
        index=idx,
    )
    ahu.attrs["equipment_type"] = "AHU"
    # No proof roles at all — appears only in the "all" slice
    meter = pd.DataFrame({"elec-power": [40.0] * 8}, index=idx)
    meter.attrs["equipment_type"] = "METER"
    frames = {"AHU_1": ahu, "METER_1": meter}
    role_map = {
        "AHU_1": {c: c for c in ahu.columns} | {"equipment_type": "AHU"},
        "METER_1": {"elec-power": "elec-power", "equipment_type": "METER"},
    }
    return frames, role_map


def test_sensor_stats_tables_slices_by_fan_proof():
    frames, role_map = _frames_and_map()
    tables = sensor_stats_tables(frames, role_map)
    assert set(tables) == {"all", "fan_on", "fan_off"}

    allt = tables["all"]
    assert {"equipment_id", "equipment_type", "role", "proof", "n", "mean", "p50"} <= set(allt.columns)
    # every mapped role present in "all"
    ahu_roles = set(allt.loc[allt["equipment_id"] == "AHU_1", "role"])
    assert "discharge-air-temp" in ahu_roles and "duct-static-pressure" in ahu_roles
    assert (allt["equipment_id"] == "METER_1").any()

    on = tables["fan_on"]
    off = tables["fan_off"]
    # fan-on slice: DAT mean ~55; fan-off ~70
    dat_on = on[(on["equipment_id"] == "AHU_1") & (on["role"] == "discharge-air-temp")]
    dat_off = off[(off["equipment_id"] == "AHU_1") & (off["role"] == "discharge-air-temp")]
    assert dat_on.iloc[0]["mean"] < 60 < dat_off.iloc[0]["mean"]
    assert dat_on.iloc[0]["n"] == 4 and dat_off.iloc[0]["n"] == 4
    # METER has no proof — excluded from on/off slices
    assert not (on["equipment_id"] == "METER_1").any()
    assert not (off["equipment_id"] == "METER_1").any()
    # proof column labels the mask source
    assert dat_on.iloc[0]["proof"] == "fan-status"


def test_setpoints_table_occupied_unoccupied_medians():
    idx = pd.date_range("2024-03-04 00:00", periods=24, freq="1h", tz="America/Chicago")
    # SP resets at night: 1.5 occupied (8-17), 0.5 otherwise
    sp_vals = [1.5 if 8 <= h < 18 else 0.5 for h in idx.hour]
    ahu = pd.DataFrame({"duct-static-pressure-sp": sp_vals}, index=idx)
    ahu.attrs["equipment_type"] = "AHU"
    frames = {"AHU_1": ahu}
    role_map = {"AHU_1": {"duct-static-pressure-sp": "duct-static-pressure-sp", "equipment_type": "AHU"}}

    df = setpoints_table(frames, role_map)
    assert len(df) == 1
    row = df.iloc[0]
    assert row["role"] == "duct-static-pressure-sp"
    assert row["median_occupied"] is not None and row["median_unoccupied"] is not None
    assert row["median_occupied"] > row["median_unoccupied"]
    assert row["n_occupied"] + row["n_unoccupied"] == 24


def test_critical_sensor_roles_data_model_driven():
    frames, role_map = _frames_and_map()
    roles = critical_sensor_roles(role_map, frames)
    # discharge-air-temp and duct-static are sweep roles; *-sp included
    assert "discharge-air-temp" in roles
    assert "duct-static-pressure" in roles
    assert "duct-static-pressure-sp" in roles
    # elec-power is not a critical / sweep / required / setpoint role
    assert "elec-power" not in roles


def test_diurnal_profiles_shape_and_keys():
    # Cover weekday + weekend with fan on/off
    idx = pd.date_range("2024-03-04 00:00", periods=48, freq="1h", tz="UTC")  # Mon–Tue
    fan = [1 if 6 <= t.hour < 18 else 0 for t in idx]
    ahu = pd.DataFrame(
        {
            "discharge-air-temp": [55.0 + (t.hour % 5) for t in idx],
            "fan-status": fan,
            "duct-static-pressure-sp": [1.5] * len(idx),
        },
        index=idx,
    )
    ahu.attrs["equipment_type"] = "AHU"
    frames = {"AHU_1": ahu}
    role_map = {
        "AHU_1": {
            "discharge-air-temp": "discharge-air-temp",
            "fan-status": "fan-status",
            "duct-static-pressure-sp": "duct-static-pressure-sp",
            "equipment_type": "AHU",
        }
    }
    df = diurnal_profiles(frames, role_map)
    assert not df.empty
    required = {
        "equipment_id",
        "equipment_type",
        "role",
        "source",
        "day_type",
        "fan_state",
        "hour",
        "n",
        "mean",
        "p50",
    }
    assert required <= set(df.columns)
    assert set(df["day_type"].unique()) <= {"weekday", "weekend", "holiday"}
    assert set(df["fan_state"].unique()) <= {"all", "on", "off"}
    assert df["hour"].between(0, 23).all()
    assert (df["equipment_id"] == "AHU_1").all()
    assert "discharge-air-temp" in set(df["role"])
    # fan_state=on rows should exist for daytime hours
    assert (df["fan_state"] == "on").any()
    assert (df["fan_state"] == "off").any()


def test_diurnal_profiles_holiday_slice():
    # Independence Day 2024
    idx = pd.date_range("2024-07-04 00:00", periods=24, freq="1h", tz="UTC")
    ahu = pd.DataFrame(
        {
            "discharge-air-temp": [60.0] * 24,
            "fan-status": [1] * 24,
        },
        index=idx,
    )
    ahu.attrs["equipment_type"] = "AHU"
    frames = {"AHU_1": ahu}
    role_map = {
        "AHU_1": {
            "discharge-air-temp": "discharge-air-temp",
            "fan-status": "fan-status",
            "equipment_type": "AHU",
        }
    }
    df = diurnal_profiles(frames, role_map)
    assert (df["day_type"] == "holiday").any()
    assert not (df["day_type"] == "weekday").any()


def test_fdd_findings_and_timeseries(tmp_path: Path):
    idx = pd.date_range("2024-03-04 08:00", periods=4, freq="1h", tz="UTC")
    raw = pd.Series([False, True, True, False], index=idx)
    confirmed = pd.Series([False, False, True, False], index=idx)
    result = RuleResult(
        rule_id="FC1",
        equipment_id="AHU_1",
        status="FAULT",
        applicable=True,
        equipment_type="AHU",
        fault_hours=1.0,
        fault_pct=25.0,
        fault_sample_count=1,
        sample_count=4,
        metrics={"foo": 1.5, "sensors": ["a", "b"]},
        notes="test",
        raw_fault=raw,
        confirmed_fault=confirmed,
        plot_series={"discharge-air-temp": pd.Series([55.0, 56.0, 57.0, 58.0], index=idx)},
    )
    findings = fdd_findings_table([result])
    assert len(findings) == 1
    assert findings.iloc[0]["rule_id"] == "FC1"
    assert findings.iloc[0]["confirmed_fault"] is True or findings.iloc[0]["confirmed_fault"] == True
    assert "metric_foo" in findings.columns
    assert findings.iloc[0]["metric_foo"] == 1.5

    paths = write_fdd_timeseries([result], tmp_path)
    assert len(paths) == 1
    assert paths[0].name == "FC1__AHU_1.csv"
    ts = pd.read_csv(paths[0])
    assert "raw_fault" in ts.columns and "confirmed_fault" in ts.columns
    assert "discharge-air-temp" in ts.columns


def test_write_manifest_and_readme(tmp_path: Path):
    readme = write_wattlab_readme(tmp_path)
    assert readme.is_file()
    assert "sensor_diurnal_24h" in readme.read_text(encoding="utf-8")
    seed = tmp_path / "model_seed.json"
    seed.write_text('{"project_id": "x"}', encoding="utf-8")
    written = {"model_seed": seed, "readme_wattlab": readme}
    man = write_manifest(tmp_path, written)
    assert man.is_file()
    import json

    payload = json.loads(man.read_text(encoding="utf-8"))
    assert payload["schema_version"] == "wattlab_dump_v2"
    paths = {f["path"] for f in payload["files"]}
    assert "MANIFEST.json" in paths
    assert "model_seed.json" in paths

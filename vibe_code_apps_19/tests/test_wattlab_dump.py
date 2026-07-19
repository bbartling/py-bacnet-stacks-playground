"""WattLab dump helpers — sensor stats, diurnal profiles, FDD findings."""

from __future__ import annotations

import json
from pathlib import Path

import pandas as pd
import pytest

from app.model_seed import build_model_seed_dict, infer_schedules
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


_V3_SENSOR_STAT_COLS = {
    "count",
    "valid_count",
    "missing_pct",
    "duration_hours",
    "min",
    "max",
    "mean",
    "std",
    "p01",
    "p05",
    "p25",
    "p50",
    "p75",
    "p95",
    "p99",
    "median_occupied",
    "median_unoccupied",
    "median_fan_on",
    "median_fan_off",
    "median_weekday",
    "median_weekend",
    "flatline_pct",
    "out_of_range_pct",
    "units",
    "source",
    "source_column",
    "equipment_id",
    "start",
    "end",
    # legacy retained
    "n",
}


def test_sensor_stats_tables_include_v3_expanded_fields():
    """Additive v3 statistics with known multi-day occupied/fan/weekday medians."""
    # Mon 2024-03-04 + Sat 2024-03-09 in America/Chicago (default occupancy TZ).
    # Occupancy schedule: weekdays 06:00–18:00 occupied; Saturday never occupied.
    mon = pd.date_range("2024-03-04 08:00", periods=4, freq="1h", tz="America/Chicago")
    mon_night = pd.date_range("2024-03-04 20:00", periods=4, freq="1h", tz="America/Chicago")
    sat = pd.date_range("2024-03-09 08:00", periods=4, freq="1h", tz="America/Chicago")
    sat_night = pd.date_range("2024-03-09 20:00", periods=4, freq="1h", tz="America/Chicago")
    idx = mon.union(mon_night).union(sat).union(sat_night)
    # Known slice values:
    #   occupied + fan-on (Mon 8–11): 55
    #   unoccupied + fan-off (Mon 20–23): 40
    #   weekend + fan-on (Sat 8–11): 70
    #   weekend + fan-off (Sat 20–23): 30
    #   one missing + one out-of-range spike on last weekend-off sample
    dat = [55.0, 55.0, 55.0, 55.0, 40.0, 40.0, 40.0, 40.0, 70.0, 70.0, 70.0, 70.0, 30.0, 30.0, None, 999.0]
    fan = [1, 1, 1, 1, 0, 0, 0, 0, 1, 1, 1, 1, 0, 0, 0, 0]
    ahu = pd.DataFrame(
        {"discharge-air-temp": dat, "fan-status": fan},
        index=idx,
    )
    ahu.attrs["equipment_type"] = "AHU"
    ahu.attrs["poll_seconds"] = 3600.0
    frames = {"AHU_1": ahu}
    role_map = {
        "AHU_1": {
            "discharge-air-temp": "discharge-air-temp",
            "fan-status": "fan-status",
            "equipment_type": "AHU",
        }
    }

    tables = sensor_stats_tables(frames, role_map)
    allt = tables["all"]
    assert _V3_SENSOR_STAT_COLS <= set(allt.columns)

    row = allt[(allt["equipment_id"] == "AHU_1") & (allt["role"] == "discharge-air-temp")].iloc[0]
    assert row["count"] == 16
    assert row["valid_count"] == 15
    assert row["n"] == 15
    assert row["missing_pct"] == pytest.approx(100.0 * 1 / 16, abs=0.01)
    assert row["duration_hours"] > 0
    assert row["min"] == pytest.approx(30.0)
    assert row["max"] == pytest.approx(999.0)
    assert row["median_occupied"] == pytest.approx(55.0)
    assert row["median_unoccupied"] == pytest.approx(40.0)  # med of 40×4,70×4,30×2,999
    assert row["median_fan_on"] == pytest.approx(62.5)  # med(55×4, 70×4)
    assert row["median_fan_off"] == pytest.approx(40.0)  # med(40×4, 30×2, 999)
    assert row["median_weekday"] == pytest.approx(47.5)  # med(55×4, 40×4)
    assert row["median_weekend"] == pytest.approx(70.0)  # med(70×4, 30×2, 999)
    assert row["out_of_range_pct"] == pytest.approx(100.0 * 1 / 15, abs=0.01)
    assert row["units"] == "°F"
    assert row["source"] == "role_map"
    assert row["source_column"] == "discharge-air-temp"
    assert "2024-03-04" in str(row["start"])
    assert "2024-03-09" in str(row["end"])


def test_model_seed_inferred_parameters_include_provenance():
    """Inferred schedule params expose source equipment/role/column, method, n, confidence, editable."""
    idx = pd.date_range("2024-01-01", periods=48, freq="1h", tz="UTC")
    fan = [0.0] * 6 + [100.0] * 12 + [0.0] * 6
    fan = fan + fan
    df = pd.DataFrame({"fan-status": fan}, index=idx)
    df.attrs.update({"poll_seconds": 3600.0, "equipment_type": "AHU"})
    role_map = {"AHU_1": {"fan-status": "fan-status", "equipment_type": "AHU"}}
    _table, payload = infer_schedules({"AHU_1": df}, role_map=role_map)
    seed = build_model_seed_dict(building_id="B1", schedule_payload=payload)

    inferred = seed.get("inferred_parameters") or payload.get("inferred_parameters")
    assert inferred, "expected inferred_parameters on seed or schedule payload"
    # Normalize to list of parameter records
    records = inferred if isinstance(inferred, list) else list(inferred.values())
    assert records
    rec = records[0]
    required = {
        "source_equipment",
        "source_role",
        "source_column",
        "method",
        "sample_count",
        "confidence",
        "editable",
    }
    assert required <= set(rec)
    assert rec["source_equipment"] == "AHU_1"
    assert rec["source_role"]
    assert rec["source_column"]
    assert rec["method"]
    assert int(rec["sample_count"]) > 0
    assert 0.0 <= float(rec["confidence"]) <= 1.0
    assert rec["editable"] is True or rec["editable"] is False


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
    # Compact evidence references shared telemetry instead of copying plot columns.
    assert "telemetry_path" in ts.columns
    assert "discharge-air-temp" not in ts.columns


def test_write_manifest_and_readme(tmp_path: Path):
    readme = write_wattlab_readme(tmp_path)
    assert readme.is_file()
    assert "sensor_diurnal_24h" in readme.read_text(encoding="utf-8")
    seed = tmp_path / "model_seed.json"
    seed.write_text('{"project_id": "x"}', encoding="utf-8")
    written = {"model_seed": seed, "readme_wattlab": readme}
    man = write_manifest(
        tmp_path,
        written,
        profile="summary",
        result_status_counts={"FAULT": 1, "PASS": 2},
        applicable_count=3,
        non_applicable_count=1,
        files_suppressed=3,
        payload_file_count=2,
        payload_uncompressed_bytes=500,
        package_file_count=3,
        metrics_scope={
            "payload": "all files including final run_report.json, excluding MANIFEST.json",
            "package_file_count": "on-disk files after MANIFEST.json is written",
        },
        stage_seconds={
            "rule_execution": 0.1,
            "analytics": 0.2,
            "serialization": 0.3,
            "compression": 0.05,
        },
        stage_scope={
            "analytics": "compute-only analytics before writing payload files",
            "serialization": "writing payload files including final run_report.json",
            "compression": "optional in-memory zip of payload only (not whole-package claim)",
        },
    )
    assert man.is_file()

    payload = json.loads(man.read_text(encoding="utf-8"))
    assert payload["schema_version"] == "wattlab_dump_v3"
    assert payload["export_profile"] == "summary"
    assert payload["result_status_counts"]["FAULT"] == 1
    assert payload["applicable_count"] == 3
    assert payload["non_applicable_count"] == 1
    assert payload["files_suppressed"] == 3
    assert payload["payload_file_count"] == 2
    assert payload["payload_uncompressed_bytes"] == 500
    assert payload["package_file_count"] == 3
    assert "MANIFEST.json" in payload["metrics_scope"]["payload"] or "excluding MANIFEST" in payload["metrics_scope"]["payload"]
    assert payload["stage_seconds"]["serialization"] == pytest.approx(0.3)
    assert "serialization" in payload["stage_scope"]
    paths = {f["path"] for f in payload["files"]}
    assert "MANIFEST.json" in paths
    assert "model_seed.json" in paths
    # Do not publish ambiguous whole-package compressed_bytes as exact
    assert "compressed_bytes" not in payload or payload.get("metrics_scope", {}).get(
        "compressed_bytes"
    )

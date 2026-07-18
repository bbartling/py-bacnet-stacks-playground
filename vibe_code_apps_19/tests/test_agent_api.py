"""Agent API + CLI smoke tests on a tiny synthetic package."""

from __future__ import annotations

import json
import subprocess
import sys
import zipfile
from pathlib import Path

import pandas as pd
import pytest

from app.agent_api import (
    export_agent_bundle,
    load_package_path,
    make_session_config,
    run_analytics,
    run_rcx_coverage,
    run_rules,
)
from app.package_io import SCHEMA_VERSION, SESSION_SCHEMA


def _write_tiny_package(root: Path) -> Path:
    root.mkdir(parents=True, exist_ok=True)
    (root / "manifest.json").write_text(
        json.dumps(
            {
                "schema_version": SCHEMA_VERSION,
                "building_id": "TINY_B1",
                "grid_minutes": 5,
                "timezone": "UTC",
            }
        ),
        encoding="utf-8",
    )
    (root / "session_config.json").write_text(
        json.dumps(
            {
                "schema_version": SESSION_SCHEMA,
                "unit_system": "imperial",
                "prefer_web_oat": True,
                "role_map": {
                    "AHU_1": {
                        "discharge-air-temp": "discharge_air_temp_f",
                        "outside-air-temp": "outside_air_temp_f",
                        "fan-status": "supply_fan_status",
                    }
                },
                "params": {"OAT-METEO": {"oat_err": 5.0, "confirm_min": 0.0}},
            }
        ),
        encoding="utf-8",
    )
    idx = pd.date_range("2024-06-01", periods=12, freq="5min", tz="UTC")
    ahu = pd.DataFrame(
        {
            "timestamp_utc": idx.strftime("%Y-%m-%dT%H:%M:%SZ"),
            "discharge_air_temp_f": [55.0] * 12,
            "outside_air_temp_f": [70.0] * 12,
            "supply_fan_status": [1] * 12,
            "mixed_air_temp_f": [60.0] * 12,
            "return_air_temp_f": [72.0] * 12,
            "oa_damper_cmd": [20.0] * 12,
            "cooling_valve": [10.0] * 12,
        }
    )
    ahu_dir = root / "AHU_1"
    ahu_dir.mkdir()
    ahu.to_csv(ahu_dir / "history_wide.csv", index=False)
    (ahu_dir / "column_map.json").write_text(
        json.dumps(
            {
                "equipType": "ahu",
                "points": {
                    "discharge-air-temp": "discharge_air_temp_f",
                    "outside-air-temp": "outside_air_temp_f",
                    "fan-status": "supply_fan_status",
                },
            }
        ),
        encoding="utf-8",
    )
    wx_dir = root / "weather"
    wx_dir.mkdir()
    wx = pd.DataFrame(
        {
            "timestamp_utc": idx.strftime("%Y-%m-%dT%H:%M:%SZ"),
            "web-outside-air-temp": [68.0] * 12,
            "web-outside-air-humidity": [45.0] * 12,
        }
    )
    wx.to_csv(wx_dir / "history_wide.csv", index=False)
    # Optional column_map.json
    (root / "column_map.json").write_text(
        json.dumps(
            {
                "version": 1,
                "building": "TINY_B1",
                "equipment": {
                    "AHU_1": {
                        "equipment_type": "AHU",
                        "column_roles": {
                            "discharge-air-temp": "discharge_air_temp_f",
                            "outside-air-temp": "outside_air_temp_f",
                            "fan-status": "supply_fan_status",
                        },
                    }
                },
            }
        ),
        encoding="utf-8",
    )
    return root


def test_agent_api_load_run_export(tmp_path: Path):
    pkg = _write_tiny_package(tmp_path / "pkg")
    ds = load_package_path(pkg)
    assert ds.building_id == "TINY_B1"
    assert "AHU_1" in ds.frames
    assert ds.has_web_weather
    assert ds.package_report.get("has_column_map") is True
    assert ds.role_map.get("AHU_1", {}).get("discharge-air-temp") == "discharge_air_temp_f"

    run = run_rules(ds)
    assert run.meta["rule_catalog_count"] == 59
    assert run.meta["result_count"] == 59  # one equipment × canonical rules
    assert sum(run.status_counts.values()) == 59

    analytics = run_analytics(ds)
    assert "motor_hours" in analytics
    rcx = run_rcx_coverage(ds)
    assert not rcx.empty
    assert "preset_id" in rcx.columns

    out = tmp_path / "out"
    written = export_agent_bundle(ds, run, out)
    assert (out / "run_report.json").is_file()
    assert (out / "fdd_summary.csv").is_file()
    assert (out / "fault_settings.json").is_file()
    assert (out / "session_config.json").is_file()
    assert (out / "role_map.yaml").is_file()
    assert (out / "rcx_preset_coverage.csv").is_file()
    assert (out / "model_seed.json").is_file()
    assert (out / "schedule_inference.json").is_file()
    assert (out / "operating_signatures.csv").is_file()
    assert (out / "weather_observed.csv").is_file()
    # WattLab dump additions
    assert (out / "README_WATTLAB.md").is_file()
    assert (out / "MANIFEST.json").is_file()
    assert (out / "sensor_stats_all.csv").is_file()
    assert (out / "sensor_stats_fan_on.csv").is_file()
    assert (out / "fdd_findings.csv").is_file()
    assert (out / "data_model.csv").is_file()
    stats_all = pd.read_csv(out / "sensor_stats_all.csv")
    assert {"equipment_id", "role", "n", "mean", "p50"} <= set(stats_all.columns)
    assert (stats_all["equipment_id"] == "AHU_1").any()
    # AHU_1 fan is always on → the fan_off slice is empty and its CSV skipped
    assert not (out / "sensor_stats_fan_off.csv").is_file()
    findings = pd.read_csv(out / "fdd_findings.csv")
    assert {"rule_id", "equipment_id", "status", "confirmed_fault"} <= set(findings.columns)
    assert len(findings) == len(run.results)
    # Per-rule timeseries directory (at least some rules emit masks)
    ts_dir = out / "fdd_timeseries"
    assert ts_dir.is_dir()
    assert any(ts_dir.glob("*.csv"))
    # Diurnal may be empty for tiny short windows — only assert when present
    if (out / "sensor_diurnal_24h.csv").is_file():
        diurnal = pd.read_csv(out / "sensor_diurnal_24h.csv")
        assert {"day_type", "fan_state", "hour", "role"} <= set(diurnal.columns)
    manifest = json.loads((out / "MANIFEST.json").read_text(encoding="utf-8"))
    assert manifest["schema_version"] == "wattlab_dump_v2"
    assert any(f["path"] == "fdd_findings.csv" for f in manifest["files"])
    seed = json.loads((out / "model_seed.json").read_text(encoding="utf-8"))
    assert seed["project_id"] == "TINY_B1"
    assert "data_window" in seed
    assert "role_map_gap_report" in written or (out / "role_map_gap_report.csv").is_file()
    # Tiny package is clean → package_health may be ok with empty issues
    assert "package_health" in (ds.package_report or {})
    if (out / "package_health.json").is_file():
        health = json.loads((out / "package_health.json").read_text(encoding="utf-8"))
        assert health.get("grade") in {"ok", "degraded", "incomplete"}
        assert "summary_lines" in health


def test_agent_api_load_zip(tmp_path: Path):
    pkg = _write_tiny_package(tmp_path / "pkg")
    zpath = tmp_path / "tiny.zip"
    with zipfile.ZipFile(zpath, "w") as zf:
        for f in pkg.rglob("*"):
            if f.is_file():
                zf.write(f, f.relative_to(pkg).as_posix())
    ds = load_package_path(zpath)
    assert ds.building_id == "TINY_B1"
    assert len(ds.frames) == 1


def test_make_session_config_includes_params():
    cfg = make_session_config({"AHU_1": {"discharge-air-temp": "dat"}}, {"VAV-1": {"confirm_min": 15.0}})
    assert cfg["schema_version"] == SESSION_SCHEMA
    assert cfg["role_map"]["AHU_1"]["discharge-air-temp"] == "dat"
    assert cfg["params"]["VAV-1"]["confirm_min"] == 15.0
    assert cfg["prefer_web_oat"] is True


def test_make_session_config_plant_toggles_roundtrip():
    from app.package_io import SessionConfig

    cfg = make_session_config(
        {"AHU_1": {"fan-status": "fan-status"}},
        {"SCHED-1": {"confirm_min": 10.0}},
        unit_system="metric",
        prefer_web_oat=False,
        chw_leave_max_f=46.0,
        include_ahu_chw_valve=True,  # accepted but always coerced False
    )
    sc = SessionConfig.model_validate(cfg)
    assert sc.unit_system == "metric"
    assert sc.prefer_web_oat is False
    assert sc.chw_leave_max_f == 46.0
    assert sc.include_ahu_chw_valve is False
    assert sc.params["SCHED-1"]["confirm_min"] == 10.0
    assert sc.role_map["AHU_1"]["fan-status"] == "fan-status"


def test_cli_smoke(tmp_path: Path):
    pkg = _write_tiny_package(tmp_path / "pkg")
    out = tmp_path / "cli_out"
    script = Path(__file__).resolve().parents[1] / "scripts" / "agent_afdd.py"
    proc = subprocess.run(
        [
            sys.executable,
            str(script),
            "--package",
            str(pkg),
            "--out",
            str(out),
            "--run-all",
        ],
        cwd=str(script.parents[1]),
        capture_output=True,
        text=True,
        check=False,
    )
    assert proc.returncode == 0, proc.stdout + proc.stderr
    assert (out / "run_report.json").is_file()
    assert (out / "fdd_summary.csv").is_file()
    assert (out / "motor_hours.csv").is_file()

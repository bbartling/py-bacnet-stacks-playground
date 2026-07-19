"""wattlab.twin — generalized dump → gaps → profile → bridge (no building hardcoding)."""

from __future__ import annotations

import json
import zipfile
from datetime import date, datetime, timedelta
from pathlib import Path
from urllib.error import URLError

import pytest

from wattlab.twin import prepare_twin


def _no_network_opener(url: str) -> bytes:
    raise URLError("test blocks network")


def _write_generic_dump(root: Path, *, with_identity: bool = False) -> Path:
    """Minimal WattLab dump that looks like any building — not BUILDING_100."""
    root.mkdir(parents=True, exist_ok=True)
    seed = {
        "project_id": "DEMO_SITE_A",
        "building_type": "office" if with_identity else None,
        "city": "detroit" if with_identity else None,
        "floor_area_ft2": 120000 if with_identity else None,
        "lat": 42.33 if with_identity else None,
        "lon": -83.05 if with_identity else None,
        "data_window": {"start_utc": "2024-06-01T00:00:00Z", "end_utc": "2024-06-30T23:00:00Z"},
        "schedule_hints": {"weekday_start_hour": 6.0, "weekday_stop_hour": 18.0},
        "field_sources": {
            "building_type": {"source": "user_required"},
            "floor_area_ft2": {"source": "user_required"},
            "city": {"source": "user_required"},
        },
    }
    (root / "model_seed.json").write_text(json.dumps(seed), encoding="utf-8")
    (root / "run_report.json").write_text(json.dumps({"building_id": "DEMO_SITE_A"}), encoding="utf-8")
    (root / "MANIFEST.json").write_text(
        json.dumps(
            {
                "schema_version": "wattlab_dump_v2",
                "file_count": 4,
                "files": [
                    {"path": "MANIFEST.json", "kind": "manifest", "purpose": "index", "how_to_use": "read first"},
                    {"path": "fdd_findings.csv", "kind": "fdd", "purpose": "findings", "how_to_use": "bridge"},
                ],
            }
        ),
        encoding="utf-8",
    )
    (root / "fdd_findings.csv").write_text(
        "rule_id,equipment_id,equipment_type,status,applicable,confirmed_fault,fault_hours,fault_pct,notes\n"
        "SCHED-247,AHU_1,AHU,FAULT,True,True,120.0,15.0,always on\n"
        "MECH-OAT-1,CHILLER_1,CHILLER,FAULT,True,True,40.0,5.0,lockout\n",
        encoding="utf-8",
    )
    (root / "operating_signatures.csv").write_text(
        "equipment_id,kind,bin_start,bin_label,hours_available,hours_on,on_fraction\n"
        "AHU_1,fan,60,60-65,100,80,0.8\n",
        encoding="utf-8",
    )
    (root / "economizer_weather.csv").write_text(
        "equipment_id,prohibited_mech_hours_below_60f\nAHU_1,150\n",
        encoding="utf-8",
    )
    return root


def test_prepare_twin_needs_input_without_identity(tmp_path: Path):
    root = _write_generic_dump(tmp_path / "dump", with_identity=False)
    report = prepare_twin(root, out_dir=tmp_path / "out")
    assert report["status"] == "NEEDS_INPUT"
    assert set(report["required_missing"]) >= {"building_type", "city", "floor_area_ft2"}
    assert (tmp_path / "out" / "intake_report.json").is_file()
    # Must not invent a resolved profile when gaps remain
    assert not (tmp_path / "out" / "resolved_profile.json").is_file()


def test_prepare_twin_ready_with_inputs_and_bridge(tmp_path: Path):
    root = _write_generic_dump(tmp_path / "dump", with_identity=False)
    inputs = {
        "building_type": "office",
        "city": "detroit",
        "floor_area_ft2": 120000,
        "floors": 4,
        "lat": 42.33,
        "lon": -83.05,
    }
    report = prepare_twin(
        root,
        inputs=inputs,
        out_dir=tmp_path / "out",
        dry_run=True,
        measure_set="better",
        opener=_no_network_opener,
    )
    assert report["status"] == "READY"
    assert report["building_id"] == "DEMO_SITE_A"
    assert (tmp_path / "out" / "resolved_profile.json").is_file()
    assert (tmp_path / "out" / "bridge.json").is_file()
    bridge = json.loads((tmp_path / "out" / "bridge.json").read_text(encoding="utf-8"))
    assert bridge["stats"]["fdd_source"] == "fdd_findings.csv"
    assert "ECM-AHU-SCHED-ALIGN" in bridge["measure_ids"]
    assert "ECM-CHILLER-LOCKOUT" in bridge["measure_ids"]
    # No BUILDING_100 leakage
    blob = json.dumps(report)
    assert "BUILDING_100" not in blob


def test_prepare_twin_from_zip(tmp_path: Path):
    root = _write_generic_dump(tmp_path / "dump", with_identity=True)
    z = tmp_path / "dump.zip"
    with zipfile.ZipFile(z, "w") as zf:
        for p in root.rglob("*"):
            if p.is_file():
                zf.write(p, p.relative_to(root).as_posix())
    report = prepare_twin(
        z,
        out_dir=tmp_path / "out_zip",
        measure_set="good",
        opener=_no_network_opener,
    )
    assert report["status"] == "READY"
    assert report["manifest"]["has_manifest"] is True
    assert (tmp_path / "out_zip" / "ecm_plan_dry_run.json").is_file()


def _om_payload(*, start: date, hours: int = 48) -> bytes:
    times = [
        (datetime(start.year, start.month, start.day) + timedelta(hours=i)).strftime(
            "%Y-%m-%dT%H:%M"
        )
        for i in range(hours)
    ]
    n = len(times)
    hourly = {
        "time": times,
        "temperature_2m": [30.0] * n,
        "dew_point_2m": [20.0] * n,
        "relative_humidity_2m": [50.0] * n,
        "surface_pressure": [990.0] * n,
        "shortwave_radiation": [100.0] * n,
        "direct_normal_irradiance": [200.0] * n,
        "diffuse_radiation": [50.0] * n,
        "wind_speed_10m": [8.0] * n,
        "wind_direction_10m": [270.0] * n,
    }
    payload = {
        "latitude": 42.33,
        "longitude": -83.05,
        "timezone": "GMT",
        "hourly": hourly,
        "hourly_units": {
            "time": "iso8601",
            "temperature_2m": "°F",
            "dew_point_2m": "°F",
            "relative_humidity_2m": "%",
            "surface_pressure": "hPa",
            "shortwave_radiation": "W/m²",
            "direct_normal_irradiance": "W/m²",
            "diffuse_radiation": "W/m²",
            "wind_speed_10m": "mp/h",
            "wind_direction_10m": "°",
        },
    }
    return json.dumps(payload).encode("utf-8")


def test_prepare_twin_open_meteo_amy_without_weather_observed(tmp_path: Path):
    root = _write_generic_dump(tmp_path / "dump", with_identity=True)
    # No weather_observed.csv — lat/lon + data_window should trigger Open-Meteo
    opener_calls: list[str] = []

    def opener(url: str) -> bytes:
        opener_calls.append(url)
        return _om_payload(start=date(2024, 6, 1), hours=48)

    report = prepare_twin(
        root,
        out_dir=tmp_path / "out_amy",
        dry_run=True,
        opener=opener,
    )
    assert report["status"] == "READY"
    assert opener_calls, "expected Open-Meteo download"
    amy = report.get("amy_weather") or {}
    assert amy.get("status") == "READY"
    assert amy.get("mode") == "ACTUAL_YEAR_CALIBRATION"
    assert Path(amy["amy_epw"]).is_file()
    assert Path(amy["weather_observed_csv"]).is_file()
    profile = json.loads(
        (tmp_path / "out_amy" / "resolved_profile.json").read_text(encoding="utf-8")
    )
    assert profile["energyplus"]["epw"] == amy["amy_epw"]


def test_prepare_twin_custom_idf(tmp_path: Path):
    root = _write_generic_dump(tmp_path / "dump", with_identity=False)
    idf = tmp_path / "my_building.idf"
    idf.write_text("Version,26.1;\n", encoding="utf-8")
    report = prepare_twin(
        root,
        inputs={
            "building_type": "office",
            "city": "detroit",
            "floor_area_ft2": 90000,
            "custom_idf": str(idf),
        },
        out_dir=tmp_path / "out_idf",
        opener=_no_network_opener,
    )
    assert report["status"] == "READY"
    profile = json.loads(
        (tmp_path / "out_idf" / "resolved_profile.json").read_text(encoding="utf-8")
    )
    assert profile["energyplus"]["prototype_idf"] == str(idf)
    assert profile["field_sources"]["prototype_idf"]["source"] == "user"


def test_calibrate_blocks_missing_identity(tmp_path: Path):
    from wattlab.calibrate import run_calibration

    root = _write_generic_dump(tmp_path / "dump", with_identity=False)
    (root / "weather_observed.csv").write_text(
        "timestamp_utc,web-outside-air-temp\n2024-06-01T00:00:00Z,70\n",
        encoding="utf-8",
    )
    with pytest.raises(ValueError, match="NEEDS_INPUT"):
        run_calibration(root, dry_run=True)

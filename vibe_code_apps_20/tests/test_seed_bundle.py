"""wattlab.seed — vibe19 WattLab dump loader + gap report."""

from __future__ import annotations

import json
import zipfile
from pathlib import Path

from wattlab.seed import gap_report, load_bundle


def _write_dump(root: Path) -> Path:
    root.mkdir(parents=True, exist_ok=True)
    (root / "model_seed.json").write_text(
        json.dumps(
            {
                "project_id": "TINY_B1",
                "building_type": "office",
                "city": "madison",
                "floor_area_ft2": 25000,
                "data_window": {"start": "2024-06-01", "end": "2024-06-30"},
                "utility_bills": [{"month": m, "kwh": 10000 + m, "therms": None} for m in range(1, 13)],
            }
        ),
        encoding="utf-8",
    )
    (root / "schedule_inference.json").write_text(json.dumps({"equipment": {}, "data_window": {}}), encoding="utf-8")
    (root / "operating_signatures.csv").write_text(
        "equipment_id,bin_start,on_fraction\nAHU_1,50,0.5\nAHU_1,60,0.9\n", encoding="utf-8"
    )
    (root / "sensor_stats_all.csv").write_text(
        "equipment_id,equipment_type,role,n,mean\nAHU_1,AHU,discharge-air-temp,10,55.0\n", encoding="utf-8"
    )
    (root / "fdd_summary.csv").write_text(
        "rule_id,equipment_id,status\nFC1,AHU_1,fault\n", encoding="utf-8"
    )
    (root / "fdd_findings.csv").write_text(
        "rule_id,equipment_id,status,confirmed_fault,fault_hours\nFC1,AHU_1,FAULT,True,2.5\n",
        encoding="utf-8",
    )
    (root / "sensor_diurnal_24h.csv").write_text(
        "equipment_id,role,day_type,fan_state,hour,n,mean\n"
        "AHU_1,discharge-air-temp,weekday,on,8,10,55.0\n",
        encoding="utf-8",
    )
    (root / "data_model.csv").write_text(
        "equipment_id,equipment_type,haystack_point,csv_column\n"
        "AHU_1,AHU,discharge-air-temp,DAT\n",
        encoding="utf-8",
    )
    (root / "MANIFEST.json").write_text(
        json.dumps(
            {
                "schema_version": "wattlab_dump_v2",
                "files": [{"path": "fdd_findings.csv", "kind": "fdd"}],
            }
        ),
        encoding="utf-8",
    )
    ts = root / "fdd_timeseries"
    ts.mkdir(exist_ok=True)
    (ts / "FC1__AHU_1.csv").write_text(
        "timestamp,raw_fault,confirmed_fault\n2024-06-01T00:00:00Z,0,0\n",
        encoding="utf-8",
    )
    return root


def test_load_bundle_from_dir(tmp_path: Path):
    root = _write_dump(tmp_path / "dump")
    b = load_bundle(root)
    assert b.building_id == "TINY_B1"
    assert b.model_seed["city"] == "madison"
    assert len(b.operating_signatures) == 2
    assert len(b.sensor_stats_all) == 1
    assert len(b.fdd_summary) == 1
    assert len(b.fdd_findings) == 1
    assert len(b.sensor_diurnal_24h) == 1
    assert b.manifest.get("schema_version") == "wattlab_dump_v2"
    assert b.fdd_timeseries_dir is not None and b.fdd_timeseries_dir.is_dir()
    # bills pulled from model_seed when no CSV present
    assert b.has_bills and len(b.utility_bills) == 12

    s = b.summary()
    assert s["building_id"] == "TINY_B1"
    assert s["has_bills"] is True
    assert s["tables"]["operating_signatures"] == 2
    assert s["findings_rows"] == 1
    assert s["has_manifest"] is True
    assert s["has_fdd_timeseries"] is True


def test_load_bundle_from_zip(tmp_path: Path):
    root = _write_dump(tmp_path / "dump")
    z = tmp_path / "dump.zip"
    with zipfile.ZipFile(z, "w") as zf:
        for p in root.rglob("*"):
            if p.is_file():
                zf.write(p, p.relative_to(root).as_posix())
    b = load_bundle(z, extract_dir=tmp_path / "extracted")
    assert b.building_id == "TINY_B1"
    assert not b.operating_signatures.empty


def test_gap_report_flags_missing(tmp_path: Path):
    root = _write_dump(tmp_path / "dump")
    b = load_bundle(root)
    rows = {r["field"]: r for r in gap_report(b)}
    assert rows["building_type"]["status"] == "ok"
    assert rows["city"]["status"] == "ok"
    assert rows["floor_area_ft2"]["status"] == "ok"
    # No utility rates or measure costs in the dump
    assert rows["utility"]["status"] == "missing"
    assert rows["measure_costs"]["status"] == "missing"
    assert rows["utility_bills"]["status"] == "ok"
    assert rows["weather_observed"]["status"] == "missing"

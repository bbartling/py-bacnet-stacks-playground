"""Package column_map.json, RCx coverage, role-map gap, fault settings I/O."""

from __future__ import annotations

import json
from pathlib import Path

import pandas as pd

from app.agent_api import make_session_config
from app.package_io import SCHEMA_VERSION, load_package_from_dir
from app.rcx_plots import rcx_preset_coverage
from app.role_map_gap import build_role_map_gap_report
from app.tuning_report import build_tuning_assistant_report


def _tiny_frames():
    idx = pd.date_range("2024-01-01", periods=8, freq="5min", tz="UTC")
    ahu = pd.DataFrame(
        {
            "sat": [55.0] * 8,
            "mat": [60.0] * 8,
            "rat": [72.0] * 8,
            "fan_status": [1] * 8,
            "oa_damper_pct": [20.0] * 8,
        },
        index=idx,
    )
    ahu.attrs["equipment_type"] = "AHU"
    ahu.attrs["poll_seconds"] = 300.0
    vav = pd.DataFrame({"zone_t": [72.0] * 8, "zone_flow": [300.0] * 8}, index=idx)
    vav.attrs["equipment_type"] = "VAV"
    vav.attrs["poll_seconds"] = 300.0
    return {"AHU_1": ahu, "VAV_1": vav}


def test_package_loads_column_map(tmp_path: Path):
    root = tmp_path / "pkg"
    root.mkdir()
    (root / "manifest.json").write_text(
        json.dumps(
            {
                "schema_version": SCHEMA_VERSION,
                "building_id": "CM_B1",
                "grid_minutes": 5,
                "timezone": "UTC",
            }
        ),
        encoding="utf-8",
    )
    idx = pd.date_range("2024-01-01", periods=4, freq="5min", tz="UTC")
    eq = root / "AHU_1"
    eq.mkdir()
    pd.DataFrame(
        {
            "timestamp_utc": idx.strftime("%Y-%m-%dT%H:%M:%SZ"),
            "discharge_air_temp_f": [55.0] * 4,
        }
    ).to_csv(eq / "history_wide.csv", index=False)
    (eq / "column_map.json").write_text(
        json.dumps(
            {
                "version": 1,
                "equipment": {
                    "AHU_1": {
                        "equipment_type": "AHU",
                        "column_roles": {"sat": "discharge_air_temp_f"},
                    }
                },
            }
        ),
        encoding="utf-8",
    )
    result = load_package_from_dir(root)
    assert result.column_map is not None
    assert result.report["has_column_map"] is True
    assert result.report["column_map_equipment_count"] == 1
    assert result.report["column_map_issue_count"] == 0


def test_rcx_preset_coverage_shape():
    frames = _tiny_frames()
    role_map = {
        "AHU_1": {"sat": "sat", "mat": "mat", "rat": "rat", "fan_status": "fan_status", "oa_damper_pct": "oa_damper_pct"},
        "VAV_1": {"zone_t": "zone_t", "zone_flow": "zone_flow"},
    }
    wx = pd.DataFrame(
        {"wx_oa_t": [50.0] * 8},
        index=frames["AHU_1"].index,
    )
    cov = rcx_preset_coverage(frames, role_map, weather=wx)
    assert len(cov) >= 10
    assert set(["preset_id", "title", "chart_type", "series_count", "row_count", "empty_reason"]).issubset(
        cov.columns
    )
    zone = cov[cov["preset_id"] == "zone_temps"].iloc[0]
    assert int(zone["series_count"]) >= 1


def test_role_map_gap_report():
    frames = _tiny_frames()
    role_map = {"AHU_1": {"sat": "sat"}, "VAV_1": {"zone_t": "zone_t"}}
    wx = pd.DataFrame({"wx_oa_t": [45.0] * 8}, index=frames["AHU_1"].index)
    gap = build_role_map_gap_report(frames, role_map, weather=wx)
    assert len(gap) == 2
    assert "missing_roles" in gap.columns
    assert "skipped_rules_missing_roles" in gap.columns
    assert bool(gap.loc[gap["equipment_id"] == "VAV_1", "has_web_weather_fallback"].iloc[0])


def test_fault_settings_roundtrip_in_session_config(tmp_path: Path):
    params = {"VAV-1": {"confirm_min": 30.0, "zone_lo": 66.0}}
    cfg = make_session_config({"AHU_1": {"sat": "dat"}}, params)
    path = tmp_path / "session_config.json"
    path.write_text(json.dumps(cfg), encoding="utf-8")
    loaded = json.loads(path.read_text(encoding="utf-8"))
    assert loaded["params"]["VAV-1"]["confirm_min"] == 30.0
    fault_path = tmp_path / "fault_settings.json"
    fault_path.write_text(json.dumps(params), encoding="utf-8")
    assert json.loads(fault_path.read_text())["VAV-1"]["zone_lo"] == 66.0


def test_tuning_assistant_report_fields():
    from app.rules.base import RuleResult

    results = [
        RuleResult("SV-STALE", "AHU_1", "FAULT", True, fault_hours=10.0),
        RuleResult("SV-FLATLINE", "AHU_1", "FAULT", True, fault_hours=8.0),
        RuleResult("VAV-1", "VAV_1", "PASS", True, fault_hours=0.0),
    ]
    rep = build_tuning_assistant_report(tuned=results, params={"SV-STALE": {"stale_hours": 6}}, has_web_weather=True)
    assert "recommended_plots" in rep
    assert "suggested_tuning_candidates" in rep
    assert rep["web_weather_used"] is True
    assert rep["stale_flatline_dominance_warning"] is True

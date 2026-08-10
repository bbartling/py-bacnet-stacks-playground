"""Tests for vibe20-style SiteUiBundle + load-profile metrics."""
from __future__ import annotations

import json
from pathlib import Path

import pandas as pd
import pytest

from eplus_gym_app.idf_geometry import parse_idf_geometry
from eplus_gym_app.load_profiles import (
    closeness_pivot,
    find_peak_demand_day,
    load_bas_demand_oat,
    load_closeness_table,
    shape_closeness_from_hourly,
)
from eplus_gym_app.plots import demand_vs_oat_figure, dial_progression_figure
from eplus_gym_app.site_bundle import SCHEMA, load_site_ui_bundle


def _write_min_site(tmp: Path) -> Path:
    (tmp / "utilities").mkdir(parents=True)
    (tmp / "reports").mkdir(parents=True)
    (tmp / "plots" / "analytics").mkdir(parents=True)
    campus = {
        "campus_id": "test_es",
        "label": "Test ES",
        "siteRef": "test_es",
        "lat": 43.0,
        "lon": -89.0,
        "buildings": [
            {
                "building_id": "main",
                "floor_area_ft2": 90000,
                "property_type": "k12_school",
            }
        ],
        "meters": [],
    }
    (tmp / "utilities" / "campus.json").write_text(
        json.dumps(campus), encoding="utf-8"
    )
    # 48 hours BAS×OAT
    rows = []
    for i in range(48):
        rows.append(
            {
                "hour_utc": f"2026-01-26T{i % 24:02d}:00:00+00:00",
                "day_type": "Weekday" if i < 24 else "Weekend",
                "kw_avg": 100.0 + i,
                "oat_f": -5.0 + i * 0.1,
            }
        )
    # fix: need proper unique hours across two days
    rows = []
    for day, dtype in (("2026-01-26", "Weekday"), ("2026-01-27", "Weekend")):
        for h in range(24):
            rows.append(
                {
                    "hour_utc": f"{day}T{h:02d}:00:00+00:00",
                    "day_type": dtype,
                    "kw_avg": 80.0 + h * 5 + (20 if day.endswith("26") else 0),
                    "oat_f": -6.0 + h * 0.5,
                }
            )
    pd.DataFrame(rows).to_csv(
        tmp / "reports" / "demand_vs_web_weather_hourly.csv", index=False
    )
    closeness = []
    for dtype in ("weekday", "weekend"):
        for model in ("E20", "A04"):
            for comp in (
                "Base load",
                "Morning ramp",
                "Afternoon",
                "Evening setback",
                "Full-day",
            ):
                closeness.append(
                    {
                        "day_type": dtype,
                        "model": model,
                        "component": comp,
                        "closeness_pct": 70.0,
                        "pct_error": 5.0,
                        "obs_kw": 100.0,
                        "sim_kw": 105.0,
                    }
                )
    close_path = (
        tmp
        / "plots"
        / "analytics"
        / "winter_shape_closeness_a04_ladder.csv"
    )
    pd.DataFrame(closeness).to_csv(close_path, index=False)
    manifest = {
        "schema_version": SCHEMA,
        "campus_json": "utilities/campus.json",
        "bas_demand_oat_csv": "reports/demand_vs_web_weather_hourly.csv",
        "utility_peak_kw": 284.8,
        "idf_pin": None,
        "farm_parquet": None,
        "honesty": {
            "bas": "BAS_INTERVAL_METER",
            "dial_ladder": "W2A_PHYSICAL_DSM",
            "farm": "STRUCTURAL_LOAD_DIAGNOSTIC",
        },
        "dial_ladder": {
            "peak_day": "2026-01-26",
            "precomputed_closeness_csv": str(
                close_path.relative_to(tmp)
            ).replace("\\", "/"),
            "models": [],
        },
    }
    (tmp / "reports" / "site_ui_bundle_v1.json").write_text(
        json.dumps(manifest), encoding="utf-8"
    )
    return tmp


def test_site_bundle_loads_campus_and_layers(tmp_path: Path):
    site = _write_min_site(tmp_path)
    b = load_site_ui_bundle(site)
    assert b.campus.campus_id == "test_es"
    assert b.bas_demand_oat_csv.is_file()
    assert b.dial_ladder.peak_day == "2026-01-26"
    assert b.promote is False


def test_bas_peak_and_closeness(tmp_path: Path):
    site = _write_min_site(tmp_path)
    b = load_site_ui_bundle(site)
    bas = load_bas_demand_oat(b)
    day, peak_kw, _ = find_peak_demand_day(bas)
    assert day == "2026-01-26"
    assert peak_kw > 0
    close = load_closeness_table(b)
    piv = closeness_pivot(close, day_type="weekday")
    assert "A04" in piv.columns
    assert "Full-day" in piv.index


def test_shape_closeness_formula():
    hourly = pd.DataFrame(
        {
            "hour": list(range(24)),
            "obs": [100.0] * 24,
            "sim": [110.0] * 24,
        }
    )
    m = shape_closeness_from_hourly(hourly, weekend=False)
    assert m["Base load"]["closeness_pct"] == pytest.approx(90.0)
    assert m["Full-day"]["pct_error"] == pytest.approx(10.0)


def test_demand_vs_oat_figure(tmp_path: Path):
    site = _write_min_site(tmp_path)
    b = load_site_ui_bundle(site)
    bas = load_bas_demand_oat(b)
    fig = demand_vs_oat_figure(bas, peak_day="2026-01-26")
    assert fig is not None
    overlay = {
        "day": "2026-01-26",
        "utility_peak_kw": 284.8,
        "series": {
            "Actual": pd.DataFrame({"hod": [0, 1], "kw": [100.0, 120.0]}),
            "A04": pd.DataFrame({"hod": [0, 1], "kw": [90.0, 110.0]}),
        },
    }
    fig2 = dial_progression_figure(overlay)
    assert len(fig2.data) >= 2


def test_idf_geometry_lakeside_pin():
    idf = (
        Path(__file__).resolve().parents[1]
        / "models"
        / "eplus"
        / "lakeside_6zone_gshp_best.idf"
    )
    if not idf.is_file():
        pytest.skip("IdealLoads IDF not in repo")
    geom = parse_idf_geometry(idf)
    assert len(geom.surfaces) > 10
    assert len(geom.zone_names) >= 1
    summary = geom.summary()
    assert summary.get("n_surfaces", 0) > 0

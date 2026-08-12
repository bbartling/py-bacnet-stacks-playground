"""Tests for eplus_gym month helpers + Streamlit data layer (no EnergyPlus / no Streamlit server)."""
from __future__ import annotations

import json
from pathlib import Path

import pandas as pd
import pytest

from eplus_gym.month_calendar import (
    DEPLOYABLE_STRATEGIES,
    build_month_scenarios,
    coverage_for_month,
    days_in_month,
    month_kpis,
    parse_month,
    write_month_scorecard,
)
from eplus_gym_app.data import available_months, load_month_slice, mean_daily_profiles, month_summary
from eplus_gym_app.plots import facility_overlay_figure, kpi_table


def test_parse_and_days_in_month():
    assert parse_month("2026-01") == (2026, 1)
    days = days_in_month("2026-02")
    assert len(days) == 28
    assert days[0] == "2026-02-01"
    assert days[-1] == "2026-02-28"


def test_build_month_scenarios_counts():
    sc = build_month_scenarios(["2026-01"], ["baseline", "deep_setback"])
    assert len(sc) == 31 * 2
    assert sc[0]["arm"] == "baseline"


def test_coverage_and_kpis_synthetic(tmp_path: Path):
    farm = tmp_path / "eplus" / "dsm_farm_paired"
    farm.mkdir(parents=True)
    rows = []
    for day in ("2026-01-05", "2026-01-06"):
        for sid in ("baseline", "deep_setback"):
            for q in range(96):
                rows.append(
                    {
                        "day": day,
                        "strategy_id": sid,
                        "quarter_index": q,
                        "facility_kw": 100.0 + q * 0.1,
                        "oat_f": 10.0,
                    }
                )
    pd.DataFrame(rows).to_parquet(
        farm / "heating_dsm_eplus_paired_15min_v1.parquet", index=False
    )
    cov = coverage_for_month(tmp_path, "2026-01", ["baseline", "deep_setback"])
    assert cov["strategies"]["baseline"]["n_days"] == 2
    kpis = month_kpis(tmp_path, "2026-01", ["baseline"])
    assert kpis[0]["n_days"] == 2
    assert kpis[0]["peak_kw"] is not None
    out = tmp_path / "score"
    path = write_month_scorecard(
        out, yyyy_mm="2026-01", strategies=["baseline"], site=tmp_path
    )
    assert path.is_file()


def test_app_data_layer(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    farm = tmp_path / "eplus" / "dsm_farm_paired"
    farm.mkdir(parents=True)
    rows = []
    for q in range(96):
        rows.append(
            {
                "day": "2026-01-11",
                "strategy_id": "baseline",
                "quarter_index": q,
                "step": q,
                "facility_kw": 50.0 + q,
                "oat_f": 5.0,
            }
        )
    pd.DataFrame(rows).to_parquet(
        farm / "heating_dsm_eplus_paired_15min_v1.parquet", index=False
    )
    monkeypatch.setenv("LAKESIDE_SITE_ROOT", str(tmp_path))
    months = available_months(tmp_path)
    assert "2026-01" in months
    df = load_month_slice("2026-01", ["baseline"], site=tmp_path)
    assert len(df) == 96
    profiles = mean_daily_profiles(df)
    assert not profiles.empty
    summary = month_summary("2026-01", ["baseline"], site=tmp_path)
    assert summary["promote"] is False
    fig = facility_overlay_figure(profiles, month="2026-01")
    assert fig is not None
    assert not kpi_table(summary["kpis"]).empty


def test_deployable_strategies_no_prbs():
    assert "baseline" in DEPLOYABLE_STRATEGIES
    assert all(not s.startswith("prbs") for s in DEPLOYABLE_STRATEGIES)


def test_streamlit_apptest_smoke(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    """Frontend smoke via Streamlit AppTest (no live EnergyPlus)."""
    pytest.importorskip("streamlit")
    from streamlit.testing.v1 import AppTest

    # Minimal site UI bundle + farm so overview + tabs load
    (tmp_path / "utilities").mkdir(parents=True)
    (tmp_path / "reports").mkdir(parents=True)
    (tmp_path / "utilities" / "campus.json").write_text(
        json.dumps(
            {
                "campus_id": "test_es",
                "label": "Test ES",
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
        ),
        encoding="utf-8",
    )
    rows_h = []
    for day, peak in (("2025-12-15", 180.0), ("2026-01-26", 286.0), ("2026-02-10", 210.0)):
        for h in range(24):
            rows_h.append(
                {
                    "hour_utc": f"{day}T{h:02d}:00:00-06:00",
                    "day_type": "Weekday",
                    "kw_avg": peak if h == 8 else 90.0 + h,
                    "oat_f": -5.0,
                }
            )
    pd.DataFrame(rows_h).to_csv(
        tmp_path / "reports" / "demand_vs_web_weather_hourly.csv", index=False
    )
    (tmp_path / "reports" / "site_ui_bundle_v1.json").write_text(
        json.dumps(
            {
                "schema_version": "site_ui_bundle_v1",
                "campus_json": "utilities/campus.json",
                "bas_demand_oat_csv": "reports/demand_vs_web_weather_hourly.csv",
                "default_model_id": "A04",
                "idf_pin": "lakeside_w2a_a04_dual_champion.idf",
                "model_catalog": [
                    {
                        "id": "A04",
                        "label": "A04 champion",
                        "family": "W2A_PHYSICAL_DSM",
                        "idf_pin": "lakeside_w2a_a04_dual_champion.idf",
                        "scorecard": "models/eplus/best_scorecard_a04_dual.json",
                        "champion": True,
                        "dial_id": "A04",
                    }
                ],
                "dial_ladder": {
                    "peak_day": "2026-01-26",
                    "models": [],
                    "precomputed_closeness_csv": "plots/analytics/eplus_gl14_vs_peak285/winter_shape_closeness_a04_ladder.csv",
                },
                "honesty": {"bas": "BAS_INTERVAL_METER"},
            }
        ),
        encoding="utf-8",
    )

    farm = tmp_path / "eplus" / "dsm_farm_paired"
    farm.mkdir(parents=True)
    rows = [
        {
            "day": "2026-01-11",
            "strategy_id": "baseline",
            "quarter_index": q,
            "step": q,
            "facility_kw": 50.0 + q,
            "oat_f": 5.0,
        }
        for q in range(96)
    ]
    pd.DataFrame(rows).to_parquet(
        farm / "heating_dsm_eplus_paired_15min_v1.parquet", index=False
    )
    weather = tmp_path / "eplus" / "weather"
    weather.mkdir(parents=True, exist_ok=True)
    (weather / "madison_amy_202508_202607.epw").write_text("EPW", encoding="utf-8")
    (weather / "madison_tmy_screening.epw").write_text("EPW", encoding="utf-8")
    close_dir = tmp_path / "plots" / "analytics" / "eplus_gl14_vs_peak285"
    close_dir.mkdir(parents=True, exist_ok=True)
    pd.DataFrame(
        [
            {
                "day_type": "weekday",
                "model": "A04",
                "component": "Full-day",
                "closeness_pct": 80.0,
                "obs_kw": 200.0,
                "sim_kw": 160.0,
            },
            {
                "day_type": "weekend",
                "model": "A04",
                "component": "Full-day",
                "closeness_pct": 75.0,
                "obs_kw": 180.0,
                "sim_kw": 135.0,
            },
        ]
    ).to_csv(close_dir / "winter_shape_closeness_a04_ladder.csv", index=False)
    monkeypatch.setenv("LAKESIDE_SITE_ROOT", str(tmp_path))
    at = AppTest.from_file(
        str(Path(__file__).resolve().parents[1] / "eplus_gym_app" / "streamlit_app.py")
    )
    at.run(timeout=90)
    assert not at.exception
    assert any("Site DSM" in str(t.value) for t in at.title)
    labels = " ".join(str(getattr(w, "label", "")) for w in list(at.radio) + list(at.selectbox))
    assert "IDF source" not in labels
    assert "campus.json" not in labels.lower()
    assert "Demand / interval CSV" not in labels
    assert "Strategy" not in labels
    assert len(at.dataframe) >= 1
    def _copy() -> str:
        blobs = []
        for attr in (
            "caption",
            "markdown",
            "info",
            "warning",
            "text",
            "metric",
            "header",
            "subheader",
            "title",
        ):
            for w in getattr(at, attr, []):
                blobs.append(str(getattr(w, "label", "")))
                blobs.append(str(getattr(w, "value", w)))
        return " ".join(blobs)

    home = _copy()
    assert "W2A_PHYSICAL_DSM" in home
    assert "not" in home.lower() and "IdealLoads" in home and "BOPTEST" in home
    assert "Building and fuel" not in home

    at.session_state["lakeside_main_tabs"] = "Run DSM"
    at.session_state["dsm_period"] = "Winter (Dec–Feb)"
    at.run(timeout=90)
    assert not at.exception
    assert not list(at.error)
    radios = [str(getattr(w, "label", "")) for w in at.radio]
    assert any("Weather" in lab for lab in radios)
    sliders = list(at.select_slider)
    assert sliders, "expected Period select_slider"
    copy = _copy()
    assert "typical-year EPW on that date" not in copy
    assert "Open-Meteo actual year" in copy
    assert "CLOSED_LOOP_RULE_DR" in copy
    assert "AMY is **not** a typical-year EPW" in copy
    assert "Will simulate closed-loop all 5 strategies" in copy
    assert "2025-12-15" in copy
    assert "2026-02-10" in copy
    assert "5568 steps" in copy
    for sid in ("baseline", "flat_24_7", "deep_setback", "stagger_preheat", "morning_all_on"):
        assert sid in copy
    at.session_state["lakeside_main_tabs"] = "Calibration"
    at.run(timeout=90)
    assert not at.exception
    assert not list(at.error)
    cal = _copy()
    assert "Weekday closeness % (electric kW)" in cal
    assert "Weekend closeness % (electric kW)" in cal
    assert "E+ peak kW" in cal
    assert "E+ kWh" in cal
    assert "E+ vs Actual peak" in cal
    assert "E+ vs Actual kWh" in cal
    assert "GL14 fuel bills" in cal
    assert "Locked to last Run DSM" in cal or "Follows the Run DSM tab" in cal

    at.session_state["lakeside_main_tabs"] = "Fuel"
    at.run(timeout=90)
    assert not at.exception
    assert not list(at.error)
    fuel = _copy()
    assert "Fuel" in fuel or "GL14" in fuel or "bill" in fuel.lower() or "EUI" in fuel

    at.session_state["lakeside_main_tabs"] = "ECMs"
    at.run(timeout=90)
    assert not at.exception
    assert not list(at.error)
    ecm = _copy()
    assert "ecm" in ecm.lower() or "ECM" in ecm or "measure" in ecm.lower()

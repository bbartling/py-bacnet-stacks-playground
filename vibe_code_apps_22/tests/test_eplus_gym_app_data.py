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


def test_cli_and_pure_helpers_smoke(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    """CLI-first smoke (Streamlit REMOVED)."""
    from eplus_gym_app.ecm_panel import load_ecm_compare
    from eplus_gym_app.optimize_tomorrow import list_studies
    from eplus_gym_app.site_bundle import load_site_ui_bundle
    from eplus_gym_app.site_config import load_site_dsm_config, save_site_dsm_config
    from eplus_gym_app.plots import eui_peer_bullet_figure as _peer_fig
    from eplus_native.six_zone_htg_stage import ACTION_KEYS

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
    (tmp_path / "eplus" / "models").mkdir(parents=True)
    (tmp_path / "eplus" / "models" / "demo.idf").write_text(
        "Version,24.2;\nBuilding,Demo,0,Suburbs,0.04,0.4,FullExterior,25,6;\n",
        encoding="utf-8",
    )
    (tmp_path / "reports" / "demand_vs_web_weather_hourly.csv").write_text(
        "hour_utc,day_type,kw_avg,oat_f\n"
        "2026-01-26T08:00:00-06:00,Weekday,200.0,-5.0\n",
        encoding="utf-8",
    )
    (tmp_path / "reports" / "site_ui_bundle_v1.json").write_text(
        json.dumps(
            {
                "schema_version": "site_ui_bundle_v1",
                "campus_json": "utilities/campus.json",
                "bas_demand_oat_csv": "reports/demand_vs_web_weather_hourly.csv",
                "default_model_id": "CHAMPION",
                "current_model_id": "CHAMPION",
                "dsm_champion": "CHAMPION",
                "idf_pin": "demo.idf",
                "model_catalog": [
                    {
                        "id": "CHAMPION",
                        "label": "Demo",
                        "family": "W2A_PHYSICAL_DSM",
                        "idf_pin": "demo.idf",
                        "champion": True,
                    }
                ],
                "honesty": {"bas": "BAS_INTERVAL_METER"},
            }
        ),
        encoding="utf-8",
    )
    (tmp_path / "reports" / "ecm_compare.json").write_text(
        json.dumps({"measures": []}), encoding="utf-8"
    )
    monkeypatch.setenv("LAKESIDE_SITE_ROOT", str(tmp_path))
    monkeypatch.setenv("SITE_ROOT", str(tmp_path))
    assert load_site_ui_bundle(tmp_path) is not None
    cfg = load_site_dsm_config(tmp_path)
    assert save_site_dsm_config(tmp_path, cfg).is_file()
    assert list_studies(tmp_path) == []
    assert load_ecm_compare(tmp_path)["schema"]
    assert ACTION_KEYS[0] == "1F_A"
    assert callable(_peer_fig)
    assert not (
        Path(__file__).resolve().parents[1] / "eplus_gym_app" / "streamlit_app.py"
    ).is_file()

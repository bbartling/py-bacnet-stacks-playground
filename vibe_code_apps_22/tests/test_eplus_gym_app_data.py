"""Tests for eplus_gym month helpers + Streamlit data layer (no EnergyPlus / no Streamlit server)."""
from __future__ import annotations

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
    monkeypatch.setenv("LAKESIDE_SITE_ROOT", str(tmp_path))
    at = AppTest.from_file(
        str(Path(__file__).resolve().parents[1] / "eplus_gym_app" / "streamlit_app.py")
    )
    at.run()
    assert not at.exception
    titles = [el.value for el in at.title]
    assert any("Lakeside E+ gym" in str(t) for t in titles)

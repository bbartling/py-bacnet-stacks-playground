"""Unit tests for monthly dial ±% chart helpers."""

from wattlab.studio.monthly_dial_chart import (
    bar_colors,
    history_heatmap_matrix,
    monthly_pct_series,
    season_summary,
)


def _sample_months():
    return [
        {
            "month": "2024-01",
            "observed_kwh": 1000,
            "modeled_kwh": 1200,
            "observed_therms": 500,
            "modeled_therms": 400,
        },
        {
            "month": "2024-07",
            "observed_kwh": 1000,
            "modeled_kwh": 850,
            "observed_therms": 100,
            "modeled_therms": 100,
        },
        {
            "month": "2024-10",
            "observed_kwh": 1000,
            "modeled_kwh": 1000,
            "observed_therms": 200,
            "modeled_therms": 260,
        },
    ]


def test_monthly_pct_series_signs():
    elec = monthly_pct_series(_sample_months(), fuel="elec")
    assert [r["month"] for r in elec] == ["Jan", "Jul", "Oct"]
    assert elec[0]["pct_off"] == 20.0  # over
    assert elec[1]["pct_off"] == -15.0  # under
    assert elec[2]["pct_off"] == 0.0
    gas = monthly_pct_series(_sample_months(), fuel="gas")
    assert gas[0]["pct_off"] == -20.0
    assert gas[2]["pct_off"] == 30.0


def test_bar_colors_band():
    colors = bar_colors([20.0, -20.0, 5.0], ok_band_pct=15.0)
    assert colors[0] != colors[1]
    assert len(colors) == 3


def test_season_summary():
    series = monthly_pct_series(_sample_months(), fuel="elec")
    seas = season_summary(series)
    assert "DJF" in seas and "JJA" in seas and "SON" in seas


def test_history_heatmap_empty_without_dirs():
    data = history_heatmap_matrix([{"run": 1}], fuel="elec")
    assert data["months"] == []
    assert data["runs"] == []

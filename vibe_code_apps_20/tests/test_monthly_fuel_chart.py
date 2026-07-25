"""Tests for monthly modeled-vs-actual fuel chart helpers."""

from __future__ import annotations

from wattlab.studio.monthly_fuel_chart import (
    build_modeled_vs_actual_figure,
    has_fuel_pairs,
    normalize_per_month_rows,
)
from wattlab.studio.proxies import resolve_proxy_inputs


def test_normalize_aliases_simulated_and_bill():
    rows = normalize_per_month_rows(
        [
            {
                "month": "2024-12",
                "bill_kwh": 5956.528,
                "simulated_kwh": 7195.9,
                "actual_therms": 100.0,
                "model_therms": 148.0,
            }
        ]
    )
    assert rows[0]["observed_kwh"] == 5956.528
    assert rows[0]["modeled_kwh"] == 7195.9
    assert rows[0]["simulated_kwh"] == 7195.9
    assert rows[0]["observed_therms"] == 100.0
    assert rows[0]["modeled_therms"] == 148.0
    assert has_fuel_pairs(rows, fuel="elec")
    assert has_fuel_pairs(rows, fuel="gas")


def test_build_modeled_vs_actual_figure_elec():
    fig = build_modeled_vs_actual_figure(
        [
            {"month": "2024-01", "observed_kwh": 100.0, "simulated_kwh": 110.0},
            {"month": "2024-02", "observed_kwh": 90.0, "modeled_kwh": 88.0},
        ],
        fuel="elec",
    )
    assert fig is not None
    assert len(fig.data) == 2


def test_build_modeled_vs_actual_figure_none_without_pairs():
    assert build_modeled_vs_actual_figure([{"month": "2024-01", "observed_kwh": 1}], fuel="elec") is None


def test_resolve_proxy_inputs_uses_nameplate():
    inputs = resolve_proxy_inputs(
        {
            "conditioned_floor_area_ft2": 100_000.0,
            "cooling_tons": 250.0,
            "fan_hp": 100.0,
        }
    )
    assert inputs["area_ft2"] == 100_000.0
    assert inputs["cooling_tons"] == 250.0
    assert inputs["fan_hp"] == 100.0
    assert abs(inputs["fan_kw"] - 74.6) < 0.01
    assert inputs["supply_cfm"] >= 250.0 * 400.0
    assert "fan_hp" in inputs["sources"]
    assert "cooling_tons" in inputs["sources"]


def test_resolve_proxy_inputs_area_fallback():
    inputs = resolve_proxy_inputs({"floor_area_ft2": 50_000.0})
    assert inputs["area_ft2"] == 50_000.0
    assert inputs["cooling_tons"] is None
    assert inputs["fan_hp"] is None
    assert inputs["supply_cfm"] == 50_000.0  # 1 cfm/ft2

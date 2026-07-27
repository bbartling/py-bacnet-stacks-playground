"""Parity: WattLab local ECM math vs Open-FDD ``open_fdd.ecm_engineering``.

Do not delete ``wattlab.bench`` duplicates until these pass. Core numeric
outputs must match; detail-row key names may differ (``temp`` vs ``temp_f``).
"""

from __future__ import annotations

import pytest

from wattlab.bench import runner  # noqa: F401  — registers algorithms + esco
from wattlab.bench.registry import get as wattlab_get
from wattlab.engineering import openfdd_ecm as adapter
from wattlab.weather.bins import OperatingSchedule, washington_dc_noaa


def _sched(shifts=(8.0, 8.0, 4.0), days=5.0, override=0.0) -> dict:
    return {"shifts": list(shifts), "days_per_week": days, "override_allowance": override}


# ---------------------------------------------------------------------------
# Registry algorithms (dict-in)
# ---------------------------------------------------------------------------

@pytest.mark.parametrize(
    "name,inputs,keys",
    [
        (
            "fan_affinity",
            {
                "design_kw": 10.0,
                "baseline_speed_fraction": 1.0,
                "proposed_speed_fraction": 0.8,
                "hours": 1000.0,
                "power_exponent": 3.0,
            },
            ("baseline_kwh", "proposed_kwh", "savings_kwh"),
        ),
        (
            "schedule_reduction",
            {
                "equipment_kw": 10.0,
                "baseline_annual_hours": 2000.0,
                "proposed_annual_hours": 1500.0,
                "average_load_fraction": 1.0,
            },
            ("baseline_kwh", "proposed_kwh", "savings_kwh", "reduced_hours"),
        ),
        (
            "boiler_efficiency_improvement",
            {
                "annual_heating_mmbtu": 1000.0,
                "baseline_efficiency": 0.80,
                "proposed_efficiency": 0.90,
            },
            ("baseline_therms", "proposed_therms", "savings_therms"),
        ),
        (
            "kw_per_ton_improvement",
            {
                "annual_ton_hours": 50000.0,
                "baseline_kw_per_ton": 0.85,
                "proposed_kw_per_ton": 0.70,
            },
            ("baseline_kwh", "proposed_kwh", "savings_kwh"),
        ),
        (
            "outside_air_sensible",
            {
                "outside_air_cfm": 2000.0,
                "average_delta_t_f": 15.0,
                "hours": 2000.0,
                "system_efficiency": 0.8,
                "fuel": "natural_gas",
            },
            ("load_btu", "input_btu", "savings_therms"),
        ),
    ],
)
def test_algorithm_parity(name, inputs, keys):
    local = wattlab_get(name)(dict(inputs))
    remote = adapter.calculate(name, dict(inputs))
    for key in keys:
        assert local[key] == pytest.approx(remote[key], rel=1e-9, abs=1e-6), key


def test_finance_simple_payback_parity():
    assert adapter.ofdd_simple_payback(10000.0, 2500.0) == pytest.approx(4.0)
    assert adapter.ofdd_simple_payback(10000.0, 0.0) is None


def test_finance_npv_parity_vs_wattlab_escalated():
    """Open-FDD npv(cost, annual, years, rate, escalation) ↔ WattLab cash-flow NPV."""
    from wattlab.finance import escalated_cash_flows, npv as wattlab_npv

    cost, annual, years, rate, esc = 20000.0, 4000.0, 15, 0.05, 0.0
    ofdd = adapter.ofdd_npv(cost, annual, years=years, discount_rate=rate, escalation=esc)
    flows = escalated_cash_flows(annual, years, escalation_rate=esc)
    local = wattlab_npv(flows, rate, cost)
    assert ofdd == pytest.approx(local, rel=1e-9, abs=1e-6)


def test_psychrometrics_parity():
    from wattlab.weather.bins import sat_enthalpy_btu_lb

    for twb in (73.5, 63.1, 53.4, 25.9, 8.4):
        assert sat_enthalpy_btu_lb(twb) == pytest.approx(
            adapter.ofdd_sat_enthalpy_btu_lb(twb), rel=1e-9, abs=1e-9
        )


def test_engineering_crosscheck_helper():
    out = adapter.engineering_crosscheck(100.0, 110.0)
    assert out["agreement_ratio"] == pytest.approx(1.1)
    assert out["verdict"] == "REASONABLE_SCREENING_ALIGNMENT"


# ---------------------------------------------------------------------------
# Bin methods (scheduling fan / cooling / heating)
# ---------------------------------------------------------------------------

def _bin_inputs() -> dict:
    bins = washington_dc_noaa()
    # Use explicit enthalpies so OA cooling matches between local MCWB curve and Open-FDD
    records = []
    for r in bins.rows:
        records.append({
            "temp": r.temp,
            "shift_hours": list(r.shift_hours),
            "mcwb": r.mcwb,
            "enthalpy": r.oa_enthalpy,
        })
    return {
        "fan_kw_total": 25.0,
        "oa_cfm_total": 8000.0,
        "kw_per_ton": 0.8,
        "boiler_efficiency": 0.8,
        "balance_point_f": 55.0,
        "supply_enthalpy": 23.2,
        "existing_schedule": _sched((8, 8, 4), 5.0),
        "proposed_schedule": _sched((0, 8, 2), 5.0, override=0.1),
        "bins": records,
    }


def test_scheduling_fan_bins_parity():
    i = _bin_inputs()
    local = wattlab_get("scheduling_fan_bins")(i)
    remote = adapter.scheduling_fan_bins(i)
    for key in ("baseline_kwh", "proposed_kwh", "savings_kwh", "hours_reduction_fraction"):
        assert local[key] == pytest.approx(remote[key], rel=1e-9, abs=1e-6), key


def test_scheduling_cooling_bins_parity():
    i = _bin_inputs()
    local = wattlab_get("scheduling_cooling_bins")(i)
    remote = adapter.scheduling_cooling_bins(i)
    for key in ("baseline_kwh", "proposed_kwh", "savings_kwh"):
        assert local[key] == pytest.approx(remote[key], rel=1e-9, abs=1e-4), key


def test_scheduling_heating_bins_parity():
    i = _bin_inputs()
    local = wattlab_get("scheduling_heating_bins")(i)
    remote = adapter.scheduling_heating_bins(i)
    for key in ("baseline_mmbtu", "proposed_mmbtu", "savings_mmbtu", "savings_therms"):
        assert local[key] == pytest.approx(remote[key], rel=1e-9, abs=1e-6), key


def test_hours_reduction_fraction_parity():
    existing = OperatingSchedule.from_dict(_sched((8, 8, 4), 5))
    proposed = OperatingSchedule.from_dict(_sched((0, 8, 2), 5, 0.1))
    from wattlab.weather.bins import hours_reduction_fraction as local_hr

    assert local_hr(existing, proposed) == pytest.approx(
        adapter.ofdd_hours_reduction_fraction(
            adapter.to_ofdd_schedule(_sched((8, 8, 4), 5)),
            adapter.to_ofdd_schedule(_sched((0, 8, 2), 5, 0.1)),
        )
    )


def test_list_calculators_nonempty():
    names = adapter.list_calculators()
    assert "fan_affinity" in names
    assert "boiler_efficiency_improvement" in names

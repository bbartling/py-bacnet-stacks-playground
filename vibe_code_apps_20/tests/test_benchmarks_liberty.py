"""Golden tests for wattlab.benchmarks against the Liberty campus bills.

Anchor values come from independent hand analysis of the same CSVs
(Dec 2024 – Nov 2025 window, 1 kWh = 3,412 Btu, 1 Mcf = 1.037 MMBtu):
combined electric 2,928,898 kWh; gas 4,206.9 / 5,481.7 Mcf; campus site EUI
71.6 kBtu/ft2; 50/50 split EUIs 66.9 / 76.3; gas-share split 62.2 / 81.0.
"""

from __future__ import annotations

from pathlib import Path

import pandas as pd
import pytest

from wattlab.benchmarks import (
    Campus,
    allocation_scenarios,
    annual_summary,
    compare_eui,
    latest_complete_window,
    load_bill_csv,
)

ROOT = Path(__file__).resolve().parents[1]
# Checked-in privacy-safe fixture (examples/liberty/*.csv stay gitignored).
CAMPUS_JSON = ROOT / "tests" / "fixtures" / "shared_meter_campus" / "campus.json"
ELEC_CSV = CAMPUS_JSON.parent / "shared_electric_summary.csv"


@pytest.fixture(scope="module")
def campus() -> Campus:
    return Campus.from_json(CAMPUS_JSON)


def test_bill_loader_handles_thousands_and_duplicate_months(campus):
    gas100 = next(m for m in campus.meters if m.meter_id == "gas_100")
    # Source CSV has two 2019-07 rows (71.1 + 14.7) — loader must sum them.
    row = gas100.bills[gas100.bills["month"] == "2019-07"]
    assert len(row) == 1
    assert row["usage"].iloc[0] == pytest.approx(85.8, abs=0.01)
    # Thousands separators parse ("1,260.9" → 1260.9)
    assert gas100.bills[gas100.bills["month"] == "2016-03"]["usage"].iloc[0] == pytest.approx(1260.9)


def test_electric_loader_picks_kwh_and_demand():
    elec = load_bill_csv(ELEC_CSV)
    jan15 = elec[elec["month"] == "2015-01"]
    assert jan15["usage"].iloc[0] == pytest.approx(281890)
    assert jan15["demand_kw"].iloc[0] == pytest.approx(594)


def test_latest_common_window_is_dec24_nov25(campus):
    window = latest_complete_window([m.months() for m in campus.meters])
    assert window is not None
    assert window[0] == "2024-12" and window[-1] == "2025-11" and len(window) == 12


def test_annual_summary_matches_hand_analysis(campus):
    s = annual_summary(campus, allocation="area_weighted")
    assert s["campus"]["kwh"] == pytest.approx(2_928_898, abs=1)
    assert s["campus"]["site_eui_kbtu_ft2"] == pytest.approx(71.6, abs=0.1)
    by_id = {b["building_id"]: b for b in s["buildings"]}
    assert by_id["liberty_50"]["mcf"] == pytest.approx(4206.9, abs=0.1)
    assert by_id["liberty_100"]["mcf"] == pytest.approx(5481.7, abs=0.1)
    assert by_id["liberty_50"]["gas_kbtu_ft2"] == pytest.approx(31.2, abs=0.1)
    assert by_id["liberty_100"]["gas_kbtu_ft2"] == pytest.approx(40.6, abs=0.1)
    # Equal areas → area_weighted == 50/50 split
    assert by_id["liberty_50"]["site_eui_kbtu_ft2"] == pytest.approx(66.9, abs=0.1)
    assert by_id["liberty_100"]["site_eui_kbtu_ft2"] == pytest.approx(76.3, abs=0.1)


def test_gas_share_allocation_matches_hand_analysis(campus):
    s = annual_summary(campus, allocation="gas_share")
    by_id = {b["building_id"]: b for b in s["buildings"]}
    assert by_id["liberty_50"]["site_eui_kbtu_ft2"] == pytest.approx(62.2, abs=0.1)
    assert by_id["liberty_100"]["site_eui_kbtu_ft2"] == pytest.approx(81.0, abs=0.1)
    # Electric splits by gas share but totals are conserved.
    assert by_id["liberty_50"]["kwh"] + by_id["liberty_100"]["kwh"] == pytest.approx(2_928_898, abs=1)


def test_manual_allocation_and_scenarios(campus):
    s = annual_summary(campus, allocation="manual", manual_shares={"liberty_50": 0.4, "liberty_100": 0.6})
    by_id = {b["building_id"]: b for b in s["buildings"]}
    assert by_id["liberty_50"]["kwh"] == pytest.approx(2_928_898 * 0.4, rel=1e-6)
    scen = allocation_scenarios(campus)
    methods = {r["allocation"] for r in scen}
    assert methods == {"area_weighted", "equal", "gas_share"}  # manual needs shares


def test_year_month_matrix_shape_and_gaps(campus):
    from wattlab.benchmarks.meters import year_month_matrix

    gas50 = next(m for m in campus.meters if m.meter_id == "gas_50")
    mat = year_month_matrix(gas50.bills)
    assert list(mat.columns) == list(range(1, 13))
    assert mat.index[0] > mat.index[-1]  # newest year first
    # Source CSV has no 2016-08 row for building 50 → honest gap, not zero.
    assert pd.isna(mat.loc[2016, 8])
    # 2016-03 parses with thousands separator.
    assert mat.loc[2016, 3] == pytest.approx(1189.4)
    # Building 50 skips 2025-12 (the reason the common window ends 2025-11).
    assert pd.isna(mat.loc[2025, 12])


def test_compare_eui_bands(campus):
    s = annual_summary(campus, allocation="area_weighted")
    by_id = {b["building_id"]: b for b in s["buildings"]}
    b50 = compare_eui(by_id["liberty_50"]["site_eui_kbtu_ft2"], "office")
    b100 = compare_eui(by_id["liberty_100"]["site_eui_kbtu_ft2"], "office")
    assert b50["band"] == "within_band" and b50["p50"] == 52.9
    assert b100["band"] == "above_p80"
    # Unknown type falls back to CBECS all-commercial
    fb = compare_eui(71.6, "spaceport")
    assert fb["property_type_matched"] == "fallback_commercial_all"
    assert fb["p50"] == 70.6

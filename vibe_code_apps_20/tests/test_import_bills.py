"""wattlab seed import-bills — privacy-safe monthly CSV → utility_bills."""

from __future__ import annotations

import json
from pathlib import Path

from wattlab.calibrate import compare_bills_to_monthly, normalize_bill_month_key
from wattlab.seed.import_bills import normalize_monthly_bills, write_utility_bills_csv

FIXTURE = Path(__file__).resolve().parent / "fixtures" / "shared_meter_campus"


def test_import_bills_yyyy_mm_and_share(tmp_path: Path):
    result = normalize_monthly_bills(
        electric_csv=FIXTURE / "shared_electric_summary.csv",
        gas_csv=FIXTURE / "building_b_gas_summary.csv",
        gas_unit="mcf",
        window="2024-12:2025-11",
        electric_share=0.5,
        allocation_method="area_weighted",
    )
    assert len(result["rows"]) == 12
    assert result["rows"][0]["month"] == "2024-12"
    assert result["provenance"]["allocation_method"] == "area_weighted"
    # Half of Dec-2024 shared electric (171857)
    assert result["rows"][0]["kwh"] == 171857 * 0.5
    out = tmp_path / "utility_bills.csv"
    write_utility_bills_csv(result["rows"], out)
    text = out.read_text(encoding="utf-8")
    assert "2024-12" in text and "kwh" in text


def test_compare_bills_period_mismatch_refuses_false_g14():
    bills = [{"month": "2024-12", "kwh": 1000.0, "therms": 100.0}]
    # Simulation months are bare 1–12 (legacy EP table) for year 2026 telemetry.
    monthly = [{"month": 12, "electricity_kwh": 1000.0, "natural_gas_therm": 100.0}]
    cmp = compare_bills_to_monthly(
        bills,
        monthly,
        data_window={"start_utc": "2026-03-16", "end_utc": "2026-07-17"},
    )
    assert cmp["pass_fail"] == "period_mismatch"
    assert cmp["period_mismatch"] is True
    assert cmp["months_compared"] == 0


def test_compare_bills_cross_year_window_joins_twelve_months():
    """BUG-W-G14-YEAR: Dec'24–Nov'25 bills + bare Jan–Dec sim → 12 months."""
    from wattlab.calibrate import month_keys_for_data_window

    months = []
    y, m = 2024, 12
    for _ in range(12):
        months.append(f"{y:04d}-{m:02d}")
        m += 1
        if m > 12:
            m = 1
            y += 1
    bills = [{"month": mo, "kwh": 1000.0, "therms": 100.0} for mo in months]
    monthly = [
        {"month": i, "electricity_kwh": 1000.0, "natural_gas_therm": 100.0}
        for i in range(1, 13)
    ]
    window = {
        "start_utc": "2024-12-01T00:00:00Z",
        "end_utc": "2025-11-30T23:59:59Z",
        "start": "2024-12-01",
        "end": "2025-11-30",
    }
    assert month_keys_for_data_window(window) == months
    cmp = compare_bills_to_monthly(bills, monthly, data_window=window)
    assert cmp["months_compared"] == 12
    assert cmp["period_mismatch"] is False
    assert cmp["pass_fail"] == "pass"
    assert {p["month"] for p in cmp["per_month"]} == set(months)


def test_compare_bills_legacy_int_months_still_join():
    bills = [{"month": m, "kwh": 1000.0, "therms": 100.0} for m in range(1, 13)]
    monthly = [
        {"month": m, "electricity_kwh": 1000.0, "natural_gas_therm": 100.0}
        for m in range(1, 13)
    ]
    cmp = compare_bills_to_monthly(bills, monthly)
    assert cmp["pass_fail"] == "pass"
    assert cmp["months_compared"] == 12


def test_run_calibration_no_artifacts_local_shadow():
    """BUG-W-ARTIFACTS: inner ARTIFACTS import must not shadow module binding."""
    import inspect

    from wattlab import calibrate as cal_mod

    src = inspect.getsource(cal_mod.run_calibration)
    assert "from wattlab.config import ARTIFACTS" not in src
    # Module-level ARTIFACTS remains usable (would UnboundLocalError if shadowed).
    assert cal_mod.ARTIFACTS is not None


def test_normalize_bill_month_key():
    assert normalize_bill_month_key("2025-07-15") == "2025-07"
    assert normalize_bill_month_key(7, default_year=2025) == "2025-07"
    assert normalize_bill_month_key(7) == "0001-07"

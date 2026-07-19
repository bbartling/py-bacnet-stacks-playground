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


def test_compare_bills_legacy_int_months_still_join():
    bills = [{"month": m, "kwh": 1000.0, "therms": 100.0} for m in range(1, 13)]
    monthly = [
        {"month": m, "electricity_kwh": 1000.0, "natural_gas_therm": 100.0}
        for m in range(1, 13)
    ]
    cmp = compare_bills_to_monthly(bills, monthly)
    assert cmp["pass_fail"] == "pass"
    assert cmp["months_compared"] == 12


def test_normalize_bill_month_key():
    assert normalize_bill_month_key("2025-07-15") == "2025-07"
    assert normalize_bill_month_key(7, default_year=2025) == "2025-07"
    assert normalize_bill_month_key(7) == "0001-07"

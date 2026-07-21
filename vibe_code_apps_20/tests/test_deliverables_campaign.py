"""Tests for calibrate campaign helpers + client deliverables."""

from __future__ import annotations

from pathlib import Path

from wattlab.calibrate import scale_monthly_energy
from wattlab.calibrate_campaign import data_window_from_bill_months
from wattlab.deliverables import (
    build_executive_markdown,
    build_results_workbook_bytes,
    package_deliverables,
)


def test_data_window_from_bill_months():
    w = data_window_from_bill_months(["2024-03", "2024-01", "2024-12"])
    assert w["start"] == "2024-01-01"
    assert w["end"] == "2024-12-31"
    assert w["bill_months_first"] == "2024-01"
    assert w["bill_months_last"] == "2024-12"


def test_scale_monthly_energy():
    rows = [{"month": 1, "electricity_kwh": 100.0, "natural_gas_therm": 10.0}]
    out = scale_monthly_energy(rows, area_scale=14.0)
    assert out[0]["electricity_kwh"] == 1400.0
    assert out[0]["electricity_kwh_unscaled"] == 100.0
    assert out[0]["natural_gas_therm"] == 140.0


def test_deliverable_package(tmp_path: Path):
    scorecard = {
        "run_id": "test_run",
        "status": "CONCEPTUAL_ONLY",
        "overall": "fail",
        "prototype_area_scale": 14.0,
        "sizing_scenario": "autosize",
        "weather_suitability": {"mode": "ACTUAL_YEAR_CALIBRATION", "reason": "AMY"},
        "annual": {
            "electricity_kwh_year": 1000.0,
            "site_eui_kbtu_ft2_year": 20.0,
            "peak_demand_kw": 15.0,
            "monthly": [{"month": 1, "electricity_kwh": 80.0}],
        },
        "utility_bills": {
            "pass_fail": "fail",
            "months_compared": 1,
            "stats_electricity": {"nmbe_pct": 12.0, "cvrmse_pct": 20.0},
            "per_month": [
                {
                    "month": "2024-01",
                    "observed_kwh": 100.0,
                    "simulated_kwh": 80.0,
                    "delta_kwh": -20.0,
                }
            ],
        },
    }
    md = build_executive_markdown(scorecard=scorecard, profile={"display_name": "Test Bldg"})
    assert "Executive summary" in md
    assert "G14" in md or "Guideline 14" in md or "pass/fail" in md.lower()

    xlsx = build_results_workbook_bytes(scorecard=scorecard)
    assert xlsx[:2] == b"PK"  # zip/xlsx magic

    run_dir = tmp_path / "run"
    run_dir.mkdir()
    (run_dir / "cal_ready.idf").write_text("Version,26.1;\n", encoding="utf-8")
    (run_dir / "amy.epw").write_text("LOCATION,Test\n", encoding="utf-8")
    (run_dir / "eplustbl.htm").write_text("<html>ok</html>", encoding="utf-8")

    out = tmp_path / "deliverable_test_run"
    meta = package_deliverables(
        out_dir=out,
        run_dir=run_dir,
        scorecard=scorecard,
        profile={"display_name": "Test Bldg", "building_type": "office"},
    )
    assert meta["ok"] is True
    assert Path(meta["report_md"]).is_file()
    assert Path(meta["workbook_xlsx"]).is_file()
    assert Path(meta["zip_path"]).is_file()
    assert (out / "03_Models" / "Baseline" / "Building_Baseline.idf").is_file()
    assert (out / "03_Models" / "Baseline" / "Weather.epw").is_file()
    assert (out / "04_Outputs" / "Baseline" / "eplustbl.htm").is_file()

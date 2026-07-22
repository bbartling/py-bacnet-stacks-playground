"""Tests for calibrate campaign helpers + client deliverables."""

from __future__ import annotations

import json
from pathlib import Path
from unittest.mock import patch

from wattlab.calibrate import scale_monthly_energy
from wattlab.calibrate_campaign import (
    data_window_from_bill_months,
    ensure_bill_aligned_weather,
    run_calibrate_campaign,
    weather_csv_covers_window,
)
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


def test_campaign_replaces_dump_data_window(tmp_path: Path):
    """BUG-W-SEED-WINDOW-MERGE: bill window replaces dump; dump kept under dump_data_window."""
    seed = {
        "building_type": "office",
        "city": "troy",
        "floor_area_ft2": 140000,
        "lat": 42.56,
        "lon": -83.12,
        "data_window": {
            "start_utc": "2026-03-16T00:00:00Z",
            "end_utc": "2026-07-17T10:00:00Z",
            "span_hours": 2961,
        },
    }
    (tmp_path / "model_seed.json").write_text(json.dumps(seed), encoding="utf-8")
    bills = tmp_path / "utility_bills.csv"
    rows = ["month,kwh,therms"]
    y, m = 2024, 12
    for _ in range(12):
        rows.append(f"{y:04d}-{m:02d},1000,50")
        m += 1
        if m > 12:
            m = 1
            y += 1
    bills.write_text("\n".join(rows) + "\n", encoding="utf-8")

    plan = run_calibrate_campaign(
        bundle=tmp_path,
        bills_csv=bills,
        dry_run=True,
    )
    assert plan["data_window"]["start"] == "2024-12-01"
    assert plan["data_window"]["end"] == "2025-11-30"
    assert "span_hours" not in plan["data_window"]
    assert plan["dump_data_window"]["span_hours"] == 2961

    campaign_seed = json.loads(
        (tmp_path / "model_seed_campaign.json").read_text(encoding="utf-8")
    )
    assert campaign_seed["data_window"]["start"] == "2024-12-01"
    assert "span_hours" not in campaign_seed["data_window"]
    assert campaign_seed["dump_data_window"]["span_hours"] == 2961


def test_merge_answers_into_seed_and_campaign(tmp_path: Path):
    from wattlab.calibrate_campaign import merge_answers_into_seed

    seed = {"building_type": None, "city": None, "floor_area_ft2": None}
    answers = {
        "building_type": "office",
        "city": "detroit",
        "floor_area_ft2": 140000,
        "lat": 42.3314,
        "lon": -83.0458,
        "floors": 6,
    }
    merged = merge_answers_into_seed(seed, answers)
    assert merged["city"] == "detroit"
    assert merged["lat"] == 42.3314
    assert merged["weather_pin_rule"] == "lat_lon_overrides_city_label"

    (tmp_path / "model_seed.json").write_text(json.dumps(seed), encoding="utf-8")
    answers_path = tmp_path / "answers.json"
    answers_path.write_text(json.dumps(answers), encoding="utf-8")
    bills = tmp_path / "utility_bills.csv"
    bills.write_text("month,kwh,therms\n2024-12,1000,50\n2025-01,1100,55\n", encoding="utf-8")
    plan = run_calibrate_campaign(
        bundle=tmp_path,
        bills_csv=bills,
        answers_path=answers_path,
        dry_run=True,
    )
    campaign_seed = json.loads(
        (tmp_path / "model_seed_campaign.json").read_text(encoding="utf-8")
    )
    assert campaign_seed["city"] == "detroit"
    assert campaign_seed["floor_area_ft2"] == 140000.0
    assert plan["weather_pin_rule"] == "lat_lon_overrides_city_label"
    assert plan["prototype_area_scale"] is not None
    assert plan["prototype_area_scale"] > 10


def test_weather_csv_covers_window(tmp_path: Path):
    window = {
        "start": "2024-12-01",
        "end": "2025-11-30",
        "start_utc": "2024-12-01T00:00:00Z",
        "end_utc": "2025-11-30T23:59:59Z",
    }
    covering = tmp_path / "wx_ok.csv"
    covering.write_text(
        "timestamp_utc,web-outside-air-temp\n"
        "2024-12-01T00:00:00Z,30\n"
        "2025-11-30T23:00:00Z,40\n",
        encoding="utf-8",
    )
    assert weather_csv_covers_window(covering, window) is True

    dump_partial = tmp_path / "wx_2026.csv"
    dump_partial.write_text(
        "timestamp_utc,web-outside-air-temp\n"
        "2026-03-16T00:00:00Z,50\n"
        "2026-07-17T10:00:00Z,70\n",
        encoding="utf-8",
    )
    assert weather_csv_covers_window(dump_partial, window) is False


def test_ensure_bill_aligned_weather_stashes_off_window(tmp_path: Path):
    """BUG-W-DUMP-WX-VS-BILLS: off-window dump weather is stashed; Open-Meteo invoked."""
    window = data_window_from_bill_months(["2024-12", "2025-11"])
    wx = tmp_path / "weather_observed.csv"
    wx.write_text(
        "timestamp_utc,web-outside-air-temp\n"
        "2026-03-16T00:00:00Z,50\n"
        "2026-07-17T10:00:00Z,70\n",
        encoding="utf-8",
    )
    seed = {"lat": 42.56, "lon": -83.12, "data_window": window}

    with patch(
        "wattlab.twin.maybe_build_amy_from_open_meteo",
        return_value={"ok": True, "source": "open_meteo"},
    ) as mock_amy:
        out = ensure_bill_aligned_weather(
            tmp_path, seed, window, fetch_open_meteo_if_missing=True
        )
    assert mock_amy.called
    assert out["weather_source"] == "open_meteo_amy"
    assert "stashed_weather" in out
    assert not wx.is_file()
    assert Path(out["stashed_weather"]).is_file()


def test_ensure_bill_aligned_weather_keeps_covering(tmp_path: Path):
    window = data_window_from_bill_months(["2024-12", "2025-11"])
    wx = tmp_path / "weather_observed.csv"
    wx.write_text(
        "timestamp_utc,web-outside-air-temp\n"
        "2024-12-01T00:00:00Z,30\n"
        "2025-11-30T23:00:00Z,40\n",
        encoding="utf-8",
    )
    seed = {"lat": 42.56, "lon": -83.12, "data_window": window}
    with patch("wattlab.twin.maybe_build_amy_from_open_meteo") as mock_amy:
        out = ensure_bill_aligned_weather(
            tmp_path, seed, window, fetch_open_meteo_if_missing=True
        )
    assert not mock_amy.called
    assert out["weather_source"] == "existing_weather_observed"
    assert wx.is_file()


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

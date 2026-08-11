"""DSM console helpers (lookup / live routing + KPIs)."""
from __future__ import annotations

from pathlib import Path

import pandas as pd
import pytest

from eplus_gym.lookup_emulator import STEPS
from eplus_gym_app.dsm_console import (
    dsm_kpis,
    meter_peak_day_for_period,
    resolve_dsm_mode,
    run_dsm_lookup,
    stage_idf_for_day,
)


def _w2a_farm(site: Path, day: str = "2026-01-26") -> None:
    farm = site / "eplus" / "dsm_farm_w2a"
    farm.mkdir(parents=True)
    rows = []
    for sid, base in (("baseline", 200.0), ("deep_setback", 160.0)):
        for q in range(STEPS):
            rows.append(
                {
                    "day": day,
                    "strategy_id": sid,
                    "quarter_index": q,
                    "facility_kw": base + 0.2 * q,
                    "oat_f": 8.0,
                }
            )
    pd.DataFrame(rows).to_parquet(farm / "heating_dsm_w2a_15min_v1.parquet", index=False)


def test_resolve_lookup_when_w2a_farm_exists(tmp_path: Path):
    _w2a_farm(tmp_path)
    mode, reason = resolve_dsm_mode(tmp_path)
    assert mode == "lookup"
    assert "farm" in reason.lower()


def test_resolve_error_without_farm_or_live(tmp_path: Path, monkeypatch):
    monkeypatch.setattr("eplus_gym_app.dsm_console.energyplus_available", lambda: False)
    mode, reason = resolve_dsm_mode(tmp_path)
    assert mode == "error"
    assert "IdealLoads" in reason


def test_dsm_kpis_vs_baseline_and_actual():
    df = pd.DataFrame({"facility_kw": [100.0, 200.0, 150.0]})
    kpis = dsm_kpis(
        df,
        {"honesty": "W2A_PHYSICAL_DSM", "provenance": "FARM_LOOKUP_EMULATOR", "promote": False},
        actual_peak_kw=220.0,
        baseline_peak_kw=250.0,
    )
    assert kpis["peak_kw"] == pytest.approx(200.0)
    assert kpis["kwh"] == pytest.approx((100 + 200 + 150) * 0.25)
    assert kpis["vs_actual_pct"] == pytest.approx((200 - 220) / 220 * 100)
    assert kpis["vs_baseline_pct"] == pytest.approx((200 - 250) / 250 * 100)
    assert kpis["promote"] is False


def test_run_dsm_lookup_returns_frame(tmp_path: Path):
    _w2a_farm(tmp_path)
    pack = run_dsm_lookup(
        site_root=tmp_path,
        strategy_id="deep_setback",
        day="2026-01-26",
    )
    assert pack["meta"]["family"] == "w2a"
    assert pack["meta"]["honesty"] == "W2A_PHYSICAL_DSM"
    assert not pack["frame"].empty
    assert pack["kpis"]["peak_kw"] < 220


def test_stage_idf_for_day_does_not_overwrite_source(tmp_path: Path):
    src = tmp_path / "champion.idf"
    src.write_text(
        "RunPeriod,\n"
        "  CalibrationWindow,  !- Name\n"
        "  8,                  !- Begin Month\n"
        "  1,                  !- Begin Day of Month\n"
        "  2025,               !- Begin Year\n"
        "  7,                  !- End Month\n"
        "  2,                  !- End Day of Month\n"
        "  2026;               !- End Year\n",
        encoding="utf-8",
    )
    dest = tmp_path / "staged.idf"
    stage_idf_for_day(src, dest, "2026-01-26")
    assert "CalibrationWindow" in src.read_text(encoding="utf-8")
    staged = dest.read_text(encoding="utf-8")
    assert "DSM_2026-01-26" in staged
    assert "26," in staged
    with pytest.raises(ValueError, match="overwrite"):
        stage_idf_for_day(src, src, "2026-01-26")


def test_meter_peak_day_calendar_month_not_always_anchor():
    rows = []
    for day, peak in (("2026-01-26", 280.0), ("2026-02-03", 190.0), ("2026-02-14", 240.0)):
        for h in range(24):
            rows.append(
                {
                    "hour_utc": pd.Timestamp(f"{day}T{h:02d}:00:00+00:00"),
                    "kw_avg": peak if h == 8 else 80.0,
                    "oat_f": 10.0,
                    "local_day": day,
                    "hod": float(h),
                }
            )
    bas = pd.DataFrame(rows)
    jan = meter_peak_day_for_period(
        bas, preset="Peak day", peak_anchor="2026-01-26"
    )
    assert jan["day"] == "2026-01-26"
    feb = meter_peak_day_for_period(
        bas, preset="Calendar month", peak_anchor="2026-01-26", month="2026-02"
    )
    assert feb["day"] == "2026-02-14"
    assert feb["actual_peak_kw"] == pytest.approx(240.0)
    assert "2026-02" in feb["why"]


def test_meter_index_zero_from_api_csv():
    from eplus_gym.runner import _meter_indices_from_api_csv, _meter_lookup_key

    raw = (
        b"**ACTUATORS**\n"
        b"Actuator,Foo,Bar,Baz,[W]\n"
        b"**METERS**\n"
        b"OutputMeter,Electricity:Facility,J\n"
        b"OutputMeter,Electricity:Building,J\n"
        b"**VARIABLES**\n"
        b"OutputVariable,Site Outdoor Air Drybulb Temperature,Environment,C\n"
    )
    idx = _meter_indices_from_api_csv(raw)
    assert idx[_meter_lookup_key("Electricity:Facility")] == 0
    assert idx["ELECTRICITY:BUILDING"] == 1
    assert "SITE OUTDOOR AIR DRYBULB TEMPERATURE" not in idx

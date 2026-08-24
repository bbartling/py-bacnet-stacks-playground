import csv

import pandas as pd
import pytest

from vibe23.b59_campaign_runner import (
    FACILITY_SCOPE_LABEL,
    TIME_BASIS_LABEL,
    _admission,
    monthly_facility_kwh,
    parse_hourly_facility_meter,
    parse_hourly_meter,
    parse_measured_monthly_kwh,
    preregistered_candidates,
    score_facility_proxy,
)


def test_preregistered_candidates_are_exactly_50_and_repeats_are_frozen():
    candidates = preregistered_candidates()
    assert [candidate.run_id for candidate in candidates] == [f"R{index:02d}" for index in range(1, 51)]
    assert candidates[0].parameters == candidates[1].parameters
    assert candidates[46].parameters == candidates[47].parameters == candidates[48].parameters == candidates[49].parameters
    assert candidates[48].holdout and candidates[49].holdout
    high_cooling_incumbent = candidates[17].parameters
    restarted = preregistered_candidates(incumbent=high_cooling_incumbent)
    assert len(restarted) == 50
    assert restarted[46].parameters == high_cooling_incumbent


def test_parse_hourly_facility_meter_and_score_disclose_legacy_reserved_labels(tmp_path):
    path = tmp_path / "eplusout.csv"
    with path.open("w", newline="", encoding="utf-8") as stream:
        writer = csv.writer(stream)
        writer.writerow(["Date/Time", "Electricity:Facility [J](Hourly)"])
        for month in range(1, 13):
            writer.writerow([f"{month}/01 01:00:00", 3_600_000])
    simulated = monthly_facility_kwh(parse_hourly_facility_meter(path))
    measured = pd.Series([1.0] * 12, index=range(1, 13), name="measured_kwh")
    result = score_facility_proxy(simulated, measured)
    assert result["tuning_months"] == list(range(1, 10))
    assert result["holdout_months"] == [10, 11, 12]
    assert FACILITY_SCOPE_LABEL in result["comparison_labels"]
    assert TIME_BASIS_LABEL in result["comparison_labels"]
    assert result["full_year_gl14"]["passes"]
    assert result["holdout_gl14"]["passes"]
    assert "not blind holdout" in result["reserved_validation_disclosure"]


def test_parse_rejects_multiple_or_non_hourly_facility_meters(tmp_path):
    path = tmp_path / "bad.csv"
    path.write_text("Date/Time,Electricity:Facility [J](Hourly),Electricity:Facility [J](Hourly)\n1/01 01:00,1,1\n")
    with pytest.raises(ValueError, match="exactly one"):
        parse_hourly_facility_meter(path)
    with pytest.raises(ValueError, match="exactly one"):
        parse_hourly_meter(path, "B59:ScopeAudit:PartialMeterBoundProxy")


def test_energyplus_end_of_hour_times_are_unique_and_iso_month_targets_parse(tmp_path):
    hourly = tmp_path / "eplusout.csv"
    with hourly.open("w", newline="", encoding="utf-8") as stream:
        writer = csv.writer(stream)
        writer.writerow(["Date/Time", "Electricity:Facility [J](Hourly)"])
        for hour in range(1, 25):
            writer.writerow([f"1/01 {hour:02d}:00:00", 3_600_000])
    parsed = parse_hourly_facility_meter(hourly)
    assert len(parsed) == 24
    assert parsed.index[0] == pd.Timestamp("2020-01-01 00:00")
    assert parsed.index[-1] == pd.Timestamp("2020-01-01 23:00")

    measured_path = tmp_path / "measured.csv"
    pd.DataFrame(
        {
            "month": pd.date_range("2020-01-01", periods=12, freq="MS", tz="UTC"),
            "energy_kwh": range(1, 13),
        }
    ).to_csv(measured_path, index=False)
    measured = parse_measured_monthly_kwh(measured_path)
    assert measured.index.tolist() == list(range(1, 13))


def test_admission_requires_complete_annual_meters_and_sizing_evidence(tmp_path):
    path = tmp_path / "eplusout.csv"
    with path.open("w", newline="", encoding="utf-8") as stream:
        writer = csv.writer(stream)
        writer.writerow(
            [
                "Date/Time",
                "Electricity:Facility [J](Hourly)",
                "B59:ScopeAudit:PartialMeterBoundProxy [J](Hourly)",
            ]
        )
        for stamp in pd.date_range("2020-01-01", "2021-01-01", freq="h", inclusive="left"):
            writer.writerow([f"{stamp.month:02d}/{stamp.day:02d} {stamp.hour + 1:02d}:00:00", 1.0, 1.0])
    (tmp_path / "eplusout.end").write_text(
        "EnergyPlus Completed Successfully-- 0 Warning; 0 Severe Errors;\n",
        encoding="utf-8",
    )
    (tmp_path / "eplusout.eio").write_text("truncated sizing table\n", encoding="utf-8")
    admitted, reasons = _admission(tmp_path, 0)
    assert admitted is False
    assert reasons == ["sizing_evidence_incomplete"]

    (tmp_path / "eplusout.eio").write_text("sizing table\nEnd of Data\n", encoding="utf-8")
    assert _admission(tmp_path, 0) == (True, [])

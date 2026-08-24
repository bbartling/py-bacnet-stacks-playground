import json

import numpy as np
import pandas as pd

from vibe23.charts import build_calibration_chart_pack, build_gl14_campaign_progress


def test_monthly_chart_pack_is_hashed_and_never_claims_calibration(tmp_path):
    source = tmp_path / "monthly.csv"
    values = np.linspace(100_000.0, 130_000.0, 12)
    pd.DataFrame(
        {
            "timestamp": pd.date_range("2019-01-01", periods=12, freq="MS", tz="America/Los_Angeles"),
            "measured": values,
            "simulated": values * 1.01,
        }
    ).to_csv(source, index=False)

    output = tmp_path / "figures"
    manifest = build_calibration_chart_pack(
        source,
        output,
        data_kind="interval_energy",
        unit="kWh",
        energy_unit="kWh",
        timezone="America/Los_Angeles",
    )
    assert manifest["claim_status"] == "DIAGNOSTIC_ONLY_NOT_A_CALIBRATION_CLAIM"
    assert manifest["monthly_gl14_style"]["threshold_passes"] is True
    assert manifest["monthly_gl14_style"]["minimum_complete_month_count_passes"] is True
    assert manifest["monthly_gl14_style"]["calibration_claim_eligible"] is False
    assert manifest["hourly_gl14_style"]["available"] is False
    assert len(manifest["artifacts"]) == 11  # five PNG/SVG pairs plus monthly CSV
    for artifact in manifest["artifacts"]:
        assert artifact["sha256"]
        assert (output / artifact["path"]).is_file()
    saved = json.loads((output / "chart_manifest.json").read_text(encoding="utf-8"))
    assert saved["source"]["sha256"] == manifest["source"]["sha256"]


def test_hourly_chart_pack_adds_typical_profiles_and_residual_heatmap(tmp_path):
    source = tmp_path / "hourly.csv"
    timestamps = pd.date_range("2019-01-01", periods=24 * 35, freq="1h", tz="UTC")
    hours = timestamps.hour.to_numpy()
    measured = 250.0 + 40.0 * np.sin(2 * np.pi * hours / 24.0)
    pd.DataFrame(
        {"timestamp": timestamps, "measured": measured, "simulated": measured + 3.0}
    ).to_csv(source, index=False)

    output = tmp_path / "figures"
    manifest = build_calibration_chart_pack(source, output, data_kind="mean_power")
    assert manifest["hourly_gl14_style"]["available"] is True
    assert manifest["semantics"]["native_interval_hours_median"] == 1.0
    names = {row["path"] for row in manifest["artifacts"]}
    assert "fig05_typical_day_profiles.png" in names
    assert "fig06_residual_weekday_hour_heatmap.svg" in names


def test_campaign_progress_requires_hashes_and_marks_numeric_gate_provisional(tmp_path):
    source = tmp_path / "campaign.csv"
    digest = "a" * 64
    pd.DataFrame(
        {
            "iteration": [1, 2, 3],
            "parameter_family": ["schedules", "internal_loads", "constructions"],
            "nmbe_pct": [12.0, 6.0, 2.0],
            "cvrmse_pct": [22.0, 16.0, 10.0],
            "complete_months": [12, 12, 12],
            "idf_sha256": [digest] * 3,
            "epw_sha256": [digest] * 3,
            "target_sha256": [digest] * 3,
        }
    ).to_csv(source, index=False)
    output = tmp_path / "campaign_figures"
    manifest = build_gl14_campaign_progress(source, output)
    assert manifest["claim_status"] == "NUMERIC_MONTHLY_GATE_MET_PROVISIONAL"
    assert manifest["first_numeric_gate_iteration"] == 3
    assert manifest["best_iteration_by_gate_distance"] == 3
    assert (output / "monthly_gl14_progress_by_iteration.png").is_file()
    assert (output / "campaign_chart_manifest.json").is_file()

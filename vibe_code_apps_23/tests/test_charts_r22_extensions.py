"""Tests for extended R22-style calibration charts."""

from __future__ import annotations

from pathlib import Path

import pandas as pd

from vibe23.charts import (
    build_extended_monthly_charts,
    build_profile_pct_chart,
)


def test_extended_monthly_charts_create_peak_and_panels(tmp_path: Path) -> None:
    index = pd.date_range("2020-01-01", periods=12, freq="MS")
    monthly = pd.DataFrame(
        {
            "measured": [100.0, 110.0, 90.0, 95.0, 100.0, 105.0, 100.0, 120.0, 100.0, 95.0, 80.0, 85.0],
            "simulated": [103.0, 108.0, 92.0, 96.0, 101.0, 104.0, 102.0, 88.0, 99.0, 94.0, 82.0, 86.0],
        },
        index=index,
    )
    measured_peaks = pd.Series(range(50, 62), index=index, dtype=float)
    simulated_peaks = pd.Series(range(48, 60), index=index, dtype=float)
    written = build_extended_monthly_charts(
        monthly,
        measured_peak_kw=measured_peaks,
        simulated_peak_kw=simulated_peaks,
        title="test",
        output_dir=tmp_path,
    )
    stems = {path.stem for path in written}
    assert "fig07_per_month_kwh_panels" in stems
    assert "fig08_monthly_peak_kw" in stems
    assert (tmp_path / "fig07_per_month_kwh_panels.png").is_file()
    assert (tmp_path / "fig08_monthly_peak_kw.svg").is_file()


def test_profile_pct_difference_uses_simulated_minus_measured(tmp_path: Path) -> None:
    hourly_index = pd.date_range("2020-01-06 08:00", periods=48, freq="h")
    hourly = pd.DataFrame(
        {
            "measured": [10.0] * 48,
            "simulated": [11.0] * 48,
        },
        index=hourly_index,
    )
    written = build_profile_pct_chart(hourly, title="test", output_dir=tmp_path)
    assert any(path.stem == "fig09_profile_pct_difference" for path in written)
    assert (tmp_path / "fig09_profile_pct_difference.png").is_file()

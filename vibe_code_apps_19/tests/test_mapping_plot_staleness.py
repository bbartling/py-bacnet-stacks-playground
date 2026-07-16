"""Mapping edits must refresh FDD plot series (prefer live df over baked plot_series)."""

from __future__ import annotations

import pandas as pd

from app.charts import rule_plot_series
from app.rules.base import finalize_result


def _df(n: int = 12) -> pd.DataFrame:
    idx = pd.date_range("2024-06-01", periods=n, freq="5min", tz="UTC")
    return pd.DataFrame(
        {
            "outside-air-damper": [10.0] * n,  # wrong / old mapping values
            "mad_c": [90.0] * n,  # correct damper column
            "cooling-valve": [40.0] * n,
            "fan-status": [1] * n,
        },
        index=idx,
    )


def test_rule_plot_series_prefers_live_df_over_baked():
    """After remap, live outside-air-damper must win over stale baked series."""
    raw = _df()
    # Simulate previous run baked with wrong damper values (all 10).
    baked = {
        "outside-air-damper": pd.Series([10.0] * len(raw), index=raw.index),
        "cooling-valve": raw["cooling-valve"],
    }
    result = finalize_result(
        "ECON-3",
        "AHU_1",
        pd.Series([False] * len(raw), index=raw.index),
        poll_seconds=300.0,
        confirm_seconds=0.0,
        plot_series=baked,
    )
    # Live mapped frame: role outside-air-damper now points at mad_c values (90).
    live = raw.rename(columns={"mad_c": "outside-air-damper-src"}).copy()
    live["outside-air-damper"] = raw["mad_c"]
    series = rule_plot_series(
        live,
        result,
        required_roles=["outside-air-damper", "cooling-valve"],
    )
    assert "outside-air-damper" in series
    assert float(series["outside-air-damper"].iloc[0]) == 90.0
    assert float(series["cooling-valve"].iloc[0]) == 40.0


def test_rule_plot_series_keeps_derived_baked_keys():
    """Non-column baked keys (e.g. sweep labels) remain when not in live df."""
    idx = pd.date_range("2024-01-01", periods=6, freq="h", tz="UTC")
    df = pd.DataFrame({"cooling-valve": [10.0] * 6}, index=idx)
    baked = {
        "control-output:heating-valve": pd.Series([5.0] * 6, index=idx),
        "cooling-valve": pd.Series([99.0] * 6, index=idx),  # stale — live wins
    }
    result = finalize_result(
        "PID-HUNT-1",
        "AHU_1",
        pd.Series([False] * 6, index=idx),
        poll_seconds=300.0,
        confirm_seconds=0.0,
        plot_series=baked,
    )
    series = rule_plot_series(df, result, required_roles=["cooling-valve"])
    assert float(series["cooling-valve"].iloc[0]) == 10.0
    assert "control-output:heating-valve" in series

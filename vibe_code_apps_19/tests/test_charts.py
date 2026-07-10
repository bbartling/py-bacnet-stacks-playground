"""Unit-separated rule plots."""

from __future__ import annotations

import pandas as pd

from app.charts import rule_result_chart
from app.rules.base import finalize_result


def test_rule_result_chart_separates_units_and_fault():
    idx = pd.date_range("2024-01-01", periods=20, freq="5min", tz="UTC")
    df = pd.DataFrame(
        {
            "sat": [55.0 + i * 0.1 for i in range(20)],
            "oa_damper_pct": [20.0 + i for i in range(20)],
        },
        index=idx,
    )
    raw = pd.Series([False] * 10 + [True] * 10, index=idx)
    result = finalize_result(
        "FC1",
        "AHU_1",
        raw,
        poll_seconds=300.0,
        confirm_seconds=300.0,
        plot_series={"sat": df["sat"], "oa_damper_pct": df["oa_damper_pct"]},
    )
    fig = rule_result_chart(
        df,
        result,
        required_roles=["sat", "oa_damper_pct"],
        units_map={"sat": "°F", "oa_damper_pct": "%"},
    )
    assert fig is not None
    # At least 2 data rows + fault row → multiple y-axes / subplot titles
    assert len(fig.layout.annotations) >= 2 or fig.layout.grid is not None
    y_titles = [fig.layout[k].title.text for k in fig.layout if k.startswith("yaxis")]
    # °F and % must not share a single axis title as a combined string with both
    assert not any(t and "°F" in str(t) and "%" in str(t) for t in y_titles)

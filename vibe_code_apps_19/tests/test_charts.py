"""Unit-separated / multi-axis rule plots."""

from __future__ import annotations

import pandas as pd

from app.charts import RAINBOW_PALETTE, rule_result_chart
from app.rules.base import finalize_result


def test_rule_result_chart_unique_axes_and_rainbow():
    idx = pd.date_range("2024-01-01", periods=20, freq="5min", tz="UTC")
    df = pd.DataFrame(
        {
            "sat": [55.0 + i * 0.1 for i in range(20)],
            "oa_damper_pct": [20.0 + i for i in range(20)],
            "duct_static": [0.5 + i * 0.01 for i in range(20)],
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
        plot_series={
            "sat": df["sat"],
            "oa_damper_pct": df["oa_damper_pct"],
            "duct_static": df["duct_static"],
        },
    )
    fig = rule_result_chart(
        df,
        result,
        required_roles=["sat", "oa_damper_pct", "duct_static"],
        units_map={"sat": "°F", "oa_damper_pct": "%", "duct_static": "in.w.c."},
    )
    assert fig is not None
    y_axes = [k for k in fig.layout if k.startswith("yaxis")]
    assert len(y_axes) >= 3  # temp, pct, static (+ fault)
    # °F and % must not share one combined axis title
    titles = [getattr(fig.layout[k].title, "text", None) for k in y_axes]
    assert not any(t and "°F" in str(t) and "%" in str(t) for t in titles)
    colors = [tr.line.color for tr in fig.data if getattr(tr.line, "color", None)]
    assert len(set(colors)) >= 3
    assert all(c in RAINBOW_PALETTE or "rgba" in str(c) for c in colors)


def test_fc1_equation_has_no_mojibake():
    from app.rules import RULES_BY_ID

    eq = RULES_BY_ID["FC1"].equation
    assert "Γ" not in eq
    assert "┬" not in eq
    assert "≥" in eq or ">=" in eq or "Fan" in eq

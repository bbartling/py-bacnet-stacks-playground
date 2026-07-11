"""Unit-separated / multi-axis rule plots + Plotly downsampling caps."""

from __future__ import annotations

import pandas as pd

from app.charts import (
    RAINBOW_PALETTE,
    downsample_series_for_plot,
    max_plot_points,
    multi_equipment_box,
    multi_equipment_timeseries,
    oat_scatter,
    rule_result_chart,
    select_plot_positions,
)
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


def test_select_plot_positions_preserves_ends_and_cap():
    pos = select_plot_positions(20_000, 500)
    assert len(pos) <= 500
    assert int(pos[0]) == 0
    assert int(pos[-1]) == 19_999


def test_max_plot_points_env(monkeypatch):
    monkeypatch.setenv("VIBE19_MAX_PLOT_POINTS", "1234")
    assert max_plot_points() == 1234
    monkeypatch.setenv("VIBE19_MAX_PLOT_POINTS", "not-int")
    assert max_plot_points() == 5000
    monkeypatch.delenv("VIBE19_MAX_PLOT_POINTS", raising=False)
    assert max_plot_points() == 5000


def test_downsample_preserves_first_last_and_cap():
    idx = pd.date_range("2024-01-01", periods=25_000, freq="min", tz="UTC")
    s = pd.Series(range(25_000), index=idx, dtype=float)
    out = downsample_series_for_plot(s, max_points=1000)
    assert len(out) <= 1000
    assert out.index[0] == idx[0]
    assert out.index[-1] == idx[-1]


def test_downsample_prefers_fault_transitions():
    n = 10_000
    idx = pd.date_range("2024-01-01", periods=n, freq="min", tz="UTC")
    s = pd.Series(0.0, index=idx)
    fault = pd.Series(False, index=idx)
    # sharp pulse in the middle
    fault.iloc[4000:4010] = True
    out = downsample_series_for_plot(s, max_points=200, fault_mask=fault)
    assert len(out) <= 200
    positions = set(idx.get_indexer(out.index))
    # rising edge at 4000 and falling edge at 4010 should be preferred
    assert 4000 in positions
    assert 4010 in positions


def test_rule_result_chart_caps_large_series(monkeypatch):
    monkeypatch.setenv("VIBE19_MAX_PLOT_POINTS", "800")
    n = 22_000
    idx = pd.date_range("2024-01-01", periods=n, freq="min", tz="UTC")
    df = pd.DataFrame({"sat": range(n), "oa_damper_pct": range(n)}, index=idx, dtype=float)
    raw = pd.Series([False] * (n // 2) + [True] * (n - n // 2), index=idx)
    result = finalize_result(
        "FC1",
        "AHU_1",
        raw,
        poll_seconds=60.0,
        confirm_seconds=300.0,
        plot_series={"sat": df["sat"], "oa_damper_pct": df["oa_damper_pct"]},
    )
    # Full-res rule math unchanged
    assert result.confirmed_fault is not None
    assert len(result.confirmed_fault) == n
    fault_hours_full = result.fault_hours

    fig = rule_result_chart(df, result, required_roles=["sat", "oa_damper_pct"], max_points=800)
    assert fig is not None
    for tr in fig.data:
        assert len(tr.x) <= 800
        assert len(tr.y) <= 800
    # ends preserved on signal traces
    sig = next(tr for tr in fig.data if tr.name and "sat" in str(tr.name))
    assert pd.Timestamp(sig.x[0]) == idx[0]
    assert pd.Timestamp(sig.x[-1]) == idx[-1]
    # re-finalize would be same; chart path must not mutate result
    assert result.fault_hours == fault_hours_full
    assert len(result.confirmed_fault) == n


def test_multi_equipment_timeseries_and_box_cap():
    n = 21_000
    idx = pd.date_range("2024-01-01", periods=n, freq="min", tz="UTC")
    series_map = {
        "AHU_1": pd.Series(range(n), index=idx, dtype=float),
        "AHU_2": pd.Series(range(n, 0, -1), index=idx, dtype=float),
    }
    fig_ts = multi_equipment_timeseries(series_map, title="t", max_points=600)
    assert fig_ts is not None
    for tr in fig_ts.data:
        assert len(tr.x) <= 600
        assert pd.Timestamp(tr.x[0]) == idx[0]
        assert pd.Timestamp(tr.x[-1]) == idx[-1]

    fig_box = multi_equipment_box(series_map, title="b", max_points=600)
    assert fig_box is not None
    for tr in fig_box.data:
        assert len(tr.y) <= 600


def test_oat_scatter_cap():
    n = 20_500
    long_df = pd.DataFrame(
        {
            "equipment_id": ["CH_1"] * n,
            "oat": list(range(n)),
            "y": list(range(n)),
        }
    )
    fig = oat_scatter(long_df, title="scatter", max_points=700)
    assert fig is not None
    assert len(fig.data[0].x) <= 700

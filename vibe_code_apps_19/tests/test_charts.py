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
            "discharge-air-temp": [55.0 + i * 0.1 for i in range(20)],
            "outside-air-damper": [20.0 + i for i in range(20)],
            "duct-static-pressure": [0.5 + i * 0.01 for i in range(20)],
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
            "discharge-air-temp": df["discharge-air-temp"],
            "outside-air-damper": df["outside-air-damper"],
            "duct-static-pressure": df["duct-static-pressure"],
        },
    )
    fig = rule_result_chart(
        df,
        result,
        required_roles=["discharge-air-temp", "outside-air-damper", "duct-static-pressure"],
        units_map={"discharge-air-temp": "°F", "outside-air-damper": "%", "duct-static-pressure": "in.w.c."},
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
    df = pd.DataFrame({"discharge-air-temp": range(n), "outside-air-damper": range(n)}, index=idx, dtype=float)
    raw = pd.Series([False] * (n // 2) + [True] * (n - n // 2), index=idx)
    result = finalize_result(
        "FC1",
        "AHU_1",
        raw,
        poll_seconds=60.0,
        confirm_seconds=300.0,
        plot_series={"discharge-air-temp": df["discharge-air-temp"], "outside-air-damper": df["outside-air-damper"]},
    )
    # Full-res rule math unchanged
    assert result.confirmed_fault is not None
    assert len(result.confirmed_fault) == n
    fault_hours_full = result.fault_hours

    fig = rule_result_chart(df, result, required_roles=["discharge-air-temp", "outside-air-damper"], max_points=800)
    assert fig is not None
    for tr in fig.data:
        assert len(tr.x) <= 800
        assert len(tr.y) <= 800
    # ends preserved on signal traces
    sig = next(tr for tr in fig.data if tr.name and "discharge-air-temp" in str(tr.name))
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


def _fc2_frame(n: int = 12, **extra) -> pd.DataFrame:
    idx = pd.date_range("2024-01-01", periods=n, freq="5min", tz="UTC")
    data = {
        "mixed-air-temp": [55.0] * n,
        "outside-air-temp": [50.0] * n,
        "return-air-temp": [70.0] * n,
        "fan-cmd": [60.0] * n,
    }
    data.update({k: [v] * n for k, v in extra.items()})
    return pd.DataFrame(data, index=idx)


def test_plot_series_motor_status_and_dewpoint_lines():
    """Every rule plot gets a 0/1 motor lane; temp plots with OAT also get web dewpoint."""
    from app.rules.cookbook_catalog import RULES_BY_ID
    from app.rules.runner import _plot_series_for_rule

    df = _fc2_frame(**{"fan-status": 1, "web-outside-air-dewpoint": 45.0})
    out = _plot_series_for_rule(RULES_BY_ID["FC2"], df)
    assert "fan-status" in out
    assert "web-outside-air-dewpoint" in out

    # bool lane renders on its own axis in the combined figure
    from app.rules.base import finalize_result

    raw = pd.Series([False] * 6 + [True] * 6, index=df.index)
    result = finalize_result(
        "FC2", "AHU_1", raw, poll_seconds=300.0, confirm_seconds=0.0, plot_series=out
    )
    fig = rule_result_chart(df, result, required_roles=list(out.keys()))
    assert fig is not None
    names = [str(tr.name) for tr in fig.data]
    assert any("fan-status" in nm for nm in names)
    assert any("web-outside-air-dewpoint" in nm for nm in names)


def test_plot_series_motor_on_derived_from_cmd():
    from app.rules.cookbook_catalog import RULES_BY_ID
    from app.rules.runner import _plot_series_for_rule

    out = _plot_series_for_rule(RULES_BY_ID["FC2"], _fc2_frame())
    assert "motor-on" in out
    assert set(pd.unique(out["motor-on"])).issubset({0, 1})


def test_multi_equipment_timeseries_status_overlay():
    idx = pd.date_range("2024-01-01", periods=48, freq="30min", tz="UTC")
    series_map = {"AHU_1": pd.Series(range(48), index=idx, dtype=float)}
    status_map = {"AHU_1": pd.Series([1] * 24 + [0] * 24, index=idx)}
    fig = multi_equipment_timeseries(series_map, title="t", status_map=status_map)
    assert fig is not None
    overlay = [tr for tr in fig.data if str(tr.name).endswith("· motor on")]
    assert len(overlay) == 1
    assert overlay[0].yaxis == "y2"
    assert fig.layout.yaxis2 is not None

    # No status_map → unchanged single-axis figure
    fig_plain = multi_equipment_timeseries(series_map, title="t")
    assert fig_plain is not None
    assert all(not str(tr.name).endswith("· motor on") for tr in fig_plain.data)


def test_collect_status_series_fan_and_cmd_proof():
    from app.rcx_plots import collect_status_series

    idx = pd.date_range("2024-01-01", periods=12, freq="5min", tz="UTC")
    ahu1 = pd.DataFrame(
        {"discharge-air-temp": [55.0] * 12, "fan-status": [1] * 6 + [0] * 6}, index=idx
    )
    ahu2 = pd.DataFrame(
        {"discharge-air-temp": [56.0] * 12, "fan-cmd": [80.0] * 6 + [0.0] * 6}, index=idx
    )
    no_proof = pd.DataFrame({"discharge-air-temp": [57.0] * 12}, index=idx)
    for eq, df in (("AHU_1", ahu1), ("AHU_2", ahu2), ("AHU_3", no_proof)):
        df.attrs["equipment_id"] = eq
        df.attrs["equipment_type"] = "AHU"
    frames = {"AHU_1": ahu1, "AHU_2": ahu2, "AHU_3": no_proof}
    out = collect_status_series(frames, {}, equipment_types=("AHU",))
    assert set(out) == {"AHU_1", "AHU_2"}
    for s in out.values():
        assert set(pd.unique(s)).issubset({0, 1})


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

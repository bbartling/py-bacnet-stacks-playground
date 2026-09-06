"""Chart helpers accept display unit labels."""
from __future__ import annotations

from vibe23.studio.charts import outdoor_kwh_cost_figure, playback_figure


def test_outdoor_kwh_cost_figure_accepts_temp_unit_label():
    fig = outdoor_kwh_cost_figure(
        hourly_kwh=[1.0] * 24,
        outdoor_f=[20.0] * 24,
        hourly_cost=[0.1] * 24,
        title="unit test",
        temp_unit_label="°C",
    )
    assert fig is not None
    titles = [getattr(a, "text", "") for a in (fig.layout.annotations or [])]
    assert any("°C" in str(t) for t in titles)


def test_playback_figure_accepts_temp_unit_label():
    n = 12
    hours = [i / 12 for i in range(n)]
    fig = playback_figure(
        hours=hours,
        house_kw=[1.0] * n,
        purchased_kw=None,
        temp_f=[22.0] * n,
        price=[0.2] * n,
        soc_pct=None,
        cumulative_house_kwh=[float(i) for i in range(n)],
        cumulative_purchased_kwh=None,
        step=3,
        title="unit test",
        temp_unit_label="°C",
    )
    assert fig is not None
    titles = [getattr(a, "text", "") for a in (fig.layout.annotations or [])]
    assert any("°C" in str(t) for t in titles)

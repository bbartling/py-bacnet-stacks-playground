"""Smoke tests for peer bullet + ASCII UI + AppTest Site Config tab."""
from __future__ import annotations

from pathlib import Path

from eplus_gym_app.plots import eui_peer_bullet_figure


def test_eui_peer_bullet_figure_smoke():
    fig = eui_peer_bullet_figure(
        peer_p20=31.0,
        peer_p50=48.5,
        peer_p80=65.0,
        series=[{"label": "Lakeside", "eui": 42.0, "color": "#1f77b4", "symbol": "diamond"}],
        title="k12 peers",
    )
    assert fig is not None
    assert len(fig.data) >= 1


def test_dsm_console_ascii_only():
    text = (Path(__file__).resolve().parents[1] / "eplus_gym_app" / "dsm_console.py").read_text(
        encoding="utf-8"
    )
    assert "â†" not in text
    assert "â€" not in text
    bad = [c for c in text if ord(c) > 127]
    assert not bad, f"non-ascii chars remain: {bad[:10]!r}"

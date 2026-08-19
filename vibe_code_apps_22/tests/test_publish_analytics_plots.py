from __future__ import annotations

import base64
import json
from pathlib import Path

import pytest

from plots.w2a_dial._build_enhanced_gl14_charts import build_charts
from scripts.vibe22_publish_analytics_plots import publish_all


def test_build_enhanced_gl14_charts(tmp_path: Path) -> None:
    analytics = tmp_path / "plots" / "analytics" / "eplus_gl14_vs_peak285"
    analytics.mkdir(parents=True)
    (analytics / "a04_dial_scorecard.csv").write_text(
        "model,nmbe_pct,cvrmse_pct,gl14,jan26_peak_kw\n"
        "E20,-4.0,12.0,PASS,270.0\n"
        "A04,1.0,10.0,PASS,287.0\n",
        encoding="utf-8",
    )
    payload = build_charts(analytics_dir=analytics)
    assert len(payload["models"]) == 2
    assert (analytics / "gl14_gate_scatter_enhanced.png").is_file()
    assert (analytics / "gl14_peak_pareto_enhanced.png").is_file()
    assert (analytics / "enhanced_gl14_payload.json").is_file()


def test_publish_analytics_plots_smoke(tmp_path: Path) -> None:
    site = tmp_path / "site"
    plots = site / "plots" / "analytics"
    plots.mkdir(parents=True)
    png = base64.b64decode(
        "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mP8/x8AAwMCAO5yR0kAAAAASUVORK5CYII="
    )
    for fn in (
        "gl14_progress_by_iteration.png",
        "gl14_status_by_iteration.png",
        "monthly_kwh_model_vs_obs_best.png",
        "monthly_fuel_pct_model_vs_actual_best.png",
        "monthly_fuel_share_pct_best.png",
        "monthly_panels_actual_vs_model_best.png",
        "monthly_peak_kw_model_vs_obs_best.png",
        "monthly_error_heatmap.png",
    ):
        (plots / fn).write_bytes(png)

    dest = tmp_path / "figures"
    records, prov = publish_all(source_root=site, dest_figure_root=dest, overwrite=False)
    assert len(records) == 8
    assert prov.is_file()
    manifest = json.loads((dest / "plot_manifest.json").read_text(encoding="utf-8"))
    assert len(manifest["plots"]) == 8


def test_scorecard_label_mismatch_raises(tmp_path: Path) -> None:
    analytics = tmp_path / "analytics"
    analytics.mkdir()
    (analytics / "a04_dial_scorecard.csv").write_text(
        "model,nmbe_pct,cvrmse_pct,gl14,jan26_peak_kw\n"
        "BAD,-20.0,30.0,PASS,280.0\n",
        encoding="utf-8",
    )
    with pytest.raises(ValueError, match="inconsistent"):
        build_charts(analytics_dir=analytics)

"""AHU free-cooling economizer diagnostic points + charts."""

from __future__ import annotations

import numpy as np
import pandas as pd

from app.analytics import economizer_free_cooling_diagnostics
from app.charts import (
    economizer_delta_scatter,
    economizer_mat_residual_chart,
    economizer_temps_overlay,
)


def _ahu_frame(n: int = 120) -> pd.DataFrame:
    idx = pd.date_range("2026-04-15", periods=n, freq="5min", tz="UTC")
    # Fan always on; OAT well below RAT so |ΔT| > 10°F; damper opens mid-window
    rat = np.full(n, 74.0)
    oat = np.linspace(55.0, 62.0, n)
    damper = np.concatenate([np.full(n // 3, 15.0), np.linspace(15, 90, n - n // 3)])
    # Perfect mix: MAT = RAT + (damper/100)*(OAT-RAT)
    mat = rat + (damper / 100.0) * (oat - rat)
    sat = mat - 4.0
    return pd.DataFrame(
        {
            "fan_status": 1,
            "oa_t": oat,
            "ra_t": rat,
            "ma_t": mat,
            "sa_t": sat,
            "oad": damper,
        },
        index=idx,
    )


ROLE_MAP = {
    "AHU_1": {
        "equipment_type": "AHU",
        "fan-status": "fan_status",
        "outside-air-temp": "oa_t",
        "return-air-temp": "ra_t",
        "mixed-air-temp": "ma_t",
        "discharge-air-temp": "sa_t",
        "outside-air-damper": "oad",
    }
}


def test_economizer_diag_fan_on_and_identifiable():
    frames = {"AHU_1": _ahu_frame()}
    diag = economizer_free_cooling_diagnostics(frames, ROLE_MAP)
    pts = diag["points"]
    metrics = diag["metrics"]
    assert not pts.empty
    assert bool(pts["fan_on"].all())
    assert int(pts["identifiable"].sum()) > 50
    assert metrics.iloc[0]["has_damper"]
    # Near-perfect mix → slope ~1, R² high, residual near 0
    assert abs(float(metrics.iloc[0]["oa_frac_vs_damper_slope"]) - 1.0) < 0.15
    assert float(metrics.iloc[0]["oa_frac_vs_damper_r2"]) > 0.9
    assert abs(float(metrics.iloc[0]["median_mat_resid_f"])) < 0.5


def test_economizer_diag_skips_fan_off():
    df = _ahu_frame(40)
    df["fan_status"] = 0
    diag = economizer_free_cooling_diagnostics({"AHU_1": df}, ROLE_MAP)
    assert diag["points"].empty
    assert any(s["reason"].startswith("no_fan") for s in diag["skipped"])


def test_economizer_diag_suppresses_low_delta_t():
    df = _ahu_frame(60)
    # Force OAT ≈ RAT → not identifiable
    df["oa_t"] = df["ra_t"] + 2.0
    df["ma_t"] = df["ra_t"] + 0.5
    diag = economizer_free_cooling_diagnostics({"AHU_1": df}, ROLE_MAP)
    pts = diag["points"]
    assert not pts.empty
    assert int(pts["identifiable"].sum()) == 0
    assert economizer_delta_scatter(pts) is None


def test_economizer_charts_build():
    diag = economizer_free_cooling_diagnostics({"AHU_1": _ahu_frame()}, ROLE_MAP)
    pts = diag["points"]
    assert economizer_delta_scatter(pts, dt_min_f=10.0) is not None
    assert economizer_mat_residual_chart(pts) is not None
    assert economizer_temps_overlay(pts, equipment_id="AHU_1") is not None

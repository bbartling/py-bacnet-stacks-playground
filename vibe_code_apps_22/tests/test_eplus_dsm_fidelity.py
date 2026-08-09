"""ML hybrid vs IdealLoads farm: spike gate + shape corr floor (synthetic)."""
from __future__ import annotations

import sys
from pathlib import Path

import numpy as np
import pytest

_APP = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(_APP / "ml"))

from hybrid_sanity import PLANT_PEAK_CAP_KW, assert_walk_sane  # noqa: E402


def _corr(a: np.ndarray, b: np.ndarray) -> float:
    if a.std() < 1e-9 or b.std() < 1e-9:
        return 0.0
    return float(np.corrcoef(a, b)[0, 1])


def test_spike_walk_fails_fidelity_gate():
    eplus = np.linspace(100, 250, 96)
    hybrid = eplus.copy()
    hybrid[40] = 1000.0
    steps = [
        {
            "hybrid_facility_kw": float(hybrid[i]),
            "delta_facility_kw": float(hybrid[i] - eplus[i]),
            "baseline_facility_kw": float(eplus[i]),
        }
        for i in range(96)
    ]
    reason = assert_walk_sane({"steps": steps, "summary": {}})
    assert reason is not None
    # Spike must reject even if series still somewhat correlates with E+
    assert float(hybrid.max()) > PLANT_PEAK_CAP_KW
    assert reason.code == "hybrid_above_plant_cap"


def test_sane_aligned_series_passes_corr_floor():
    eplus = 150.0 + 40.0 * np.sin(np.linspace(0, 2 * np.pi, 96))
    hybrid = eplus + np.random.default_rng(0).normal(0, 5, size=96)
    hybrid = np.clip(hybrid, 0, PLANT_PEAK_CAP_KW)
    steps = [
        {
            "hybrid_facility_kw": float(hybrid[i]),
            "delta_facility_kw": float(hybrid[i] - eplus[i]),
            "baseline_facility_kw": float(eplus[i]),
        }
        for i in range(96)
    ]
    assert assert_walk_sane({"steps": steps, "summary": {}}) is None
    assert _corr(hybrid, eplus) >= 0.85

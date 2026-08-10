"""Treatment-effect gates + weather fail-closed (synthetic)."""
from __future__ import annotations

import sys
from pathlib import Path

import numpy as np
import pytest

_APP = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(_APP / "ml"), str(_APP / "scripts")]

from physics_families import (  # noqa: E402
    STRUCTURAL_LOAD_DIAGNOSTIC,
    W2A_PHYSICAL_DSM,
    label_for_farm,
    resolve_w2a_dsm_seed,
)
from treatment_validation import (  # noqa: E402
    delta_peak_error,
    treatment_sign_accuracy,
    write_treatment_validation_csv,
)


def test_physics_family_labels():
    assert label_for_farm(ideal_loads=True) == STRUCTURAL_LOAD_DIAGNOSTIC
    assert label_for_farm(ideal_loads=False) == W2A_PHYSICAL_DSM
    p = resolve_w2a_dsm_seed()
    assert p.name.startswith("lakeside_w2a_a04")


def test_treatment_sign_fixture():
    baseline = np.full(96, 100.0)
    dsm = baseline.copy()
    dsm[20:36] += 40.0  # morning heating increase
    delta = dsm - baseline
    morning = np.zeros(96, dtype=bool)
    morning[20:36] = True
    assert treatment_sign_accuracy(delta, expected_positive_mask=morning) >= 0.9
    assert abs(delta_peak_error(baseline, dsm, measured_delta_peak=40.0)) < 1e-6


def test_identical_control_zero_delta():
    x = np.linspace(80, 200, 96)
    assert float(np.max(np.abs(x - x))) == 0.0


def test_write_treatment_validation_scaffold(tmp_path):
    out = tmp_path / "treatment_validation.csv"
    write_treatment_validation_csv(out, rows=[{"strategy": "deep_setback", "delta_peak_err": 0.0, "sign_acc": 1.0}])
    assert out.is_file()


def test_no_promotable_weather_fallback_gate():
    """Compile must refuse silent rh=50/ghi=0 when oat present but rh/ghi NaN."""
    import pandas as pd
    from feature_compile_heating_dsm import compile_features

    n = 4
    df = pd.DataFrame(
        {
            "day": ["2026-01-26"] * n,
            "hour_ending": [1, 2, 3, 4],
            "month": [1] * n,
            "doy": [26] * n,
            "is_weekend": [0.0] * n,
            "occupied": [0.0] * n,
            "facility_kw": [100.0] * n,
            "oat_f": [20.0] * n,
            "rh_pct": [np.nan] * n,
            "ghi": [np.nan] * n,
            "weather_source": ["hourly_history"] * n,
            **{f"zone_temp_{z}_f": [68.0] * n for z in ("1F_A", "1F_B", "1F_C", "1F_D", "2F_A", "2F_B")},
            **{f"hp_on_{z}": [1.0] * n for z in ("1F_A", "1F_B", "1F_C", "1F_D", "2F_A", "2F_B")},
            **{f"occ_frac_{z}": [0.0] * n for z in ("1F_A", "1F_B", "1F_C", "1F_D", "2F_A", "2F_B")},
            "strategy_id": ["baseline"] * n,
            "arm": ["baseline"] * n,
        }
    )
    with pytest.raises(ValueError, match="rh_pct/ghi missing"):
        compile_features(df)


def test_pre_roll_filter_keeps_eval_day_only():
    from eplus_heating_dsm_farm import filter_rows_to_evaluation_day

    rows = [
        {"day": "2026-01-23", "facility_kw": 1.0},
        {"day": "2026-01-26", "facility_kw": 2.0},
        {"day": "2026-01-26", "facility_kw": 3.0},
    ]
    kept = filter_rows_to_evaluation_day(rows, "2026-01-26")
    assert len(kept) == 2
    assert all(r["day"] == "2026-01-26" for r in kept)

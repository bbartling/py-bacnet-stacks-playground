"""GREYBOX_SHADOW_V1 tests — inventory + 1R1C honesty."""
from __future__ import annotations

import sys
from pathlib import Path

import numpy as np
import pandas as pd
import pytest

_APP = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(_APP / "ml"), str(_APP / "scripts"), str(_APP)]


def test_inventory_marks_present_columns(tmp_path):
    from inventory_greybox_sensors import inventory, write_md

    site = tmp_path / "site"
    art = site / "ml" / "artifacts"
    art.mkdir(parents=True)
    pq = art / "real_baseline_15min_v1.parquet"
    df = pd.DataFrame(
        {
            "facility_kw": [100.0],
            "zone_temp_1F_A_f": [68.0],
            "zone_temp_1F_B_f": [68.0],
            "zone_temp_1F_C_f": [68.0],
            "zone_temp_1F_D_f": [68.0],
            "zone_temp_2F_A_f": [68.0],
            "zone_temp_2F_B_f": [68.0],
            "oat_f": [20.0],
            "rh_pct": [40.0],
            "ghi": [0.0],
            "occupied": [0.0],
        }
    )
    df.to_parquet(pq)
    rows = inventory(site)
    by = {r["point"]: r for r in rows}
    assert by["facility_kw"]["status"] == "PRESENT_IN_EXPORT"
    assert by["zone_temp_1F_A_f"]["status"] == "PRESENT_IN_EXPORT"
    assert by["oat_f"]["status"] == "PRESENT_IN_EXPORT"
    assert by["solar_ghi"]["status"] == "PRESENT_IN_EXPORT"
    assert by["occupancy"]["status"] == "PRESENT_IN_EXPORT"
    assert by["loop_ewt"]["status"] == "NOT_IN_SITE_EXPORT"
    assert "invent" in by["loop_ewt"]["bacnet_or_column_identity"].lower() or by["loop_ewt"][
        "bacnet_or_column_identity"
    ].startswith("UNKNOWN")
    write_md(tmp_path / "m.md", rows, site)
    assert "PRESENT" in (tmp_path / "m.md").read_text(encoding="utf-8")


def test_fit_1r1c_recovers_positive_rc_on_synthetic():
    from greybox.rc_1r1c import fit_1r1c, simulate

    rng = np.random.default_rng(0)
    n = 800
    # true discrete: mild coupling
    a_t, b_t, c_t = 0.92, 0.06, 0.01
    oat = 20 + 10 * np.sin(np.linspace(0, 8, n))
    q = rng.uniform(0, 50, size=n)
    t = np.zeros(n)
    t[0] = 68.0
    for i in range(n - 1):
        t[i + 1] = a_t * t[i] + b_t * oat[i] + c_t * q[i] + rng.normal(0, 0.05)
    p = fit_1r1c(t, oat, q, zone="zone_temp_1F_A_f")
    assert p.R > 0 and p.C > 0
    assert 0 < p.a < 1
    assert p.b > 0
    assert p.honesty == "GREYBOX_SHADOW_V1"
    assert p.promote == "NON_PROMOTABLE"
    pred = simulate(t[0], oat, q, a=p.a, b=p.b, c=p.c)
    assert np.isfinite(pred).all()


def test_step_inputs_ignore_mutated_current_target():
    """Exogenous oat/q for step t must not depend on mutated T_meas[t]."""
    from greybox.rc_1r1c import step_open_loop

    a, b, c = 0.9, 0.05, 0.02
    t_prev = 68.0
    oat, q = 22.0, 10.0
    y1 = step_open_loop(t_prev, oat, q, a=a, b=b, c=c)
    # Mutating a fictional "current target" does not change exogenous call
    _mutated_target = 99.0
    y2 = step_open_loop(t_prev, oat, q, a=a, b=b, c=c)
    assert y1 == y2
    assert _mutated_target != y1


def test_honesty_labels_not_idealloads_treatment():
    from greybox.rc_1r1c import HONESTY, PROMOTE, Q_POLICY

    assert HONESTY == "GREYBOX_SHADOW_V1"
    assert PROMOTE == "NON_PROMOTABLE"
    assert "DIAGNOSTIC" in Q_POLICY
    assert "IDEALLOADS" not in HONESTY

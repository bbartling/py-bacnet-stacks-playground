"""GREYBOX identification honesty — deployable forecast must not use future meter Q."""
from __future__ import annotations

import importlib
import inspect
import subprocess
import sys
from pathlib import Path

import numpy as np
import pytest

_APP = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(_APP / "ml"), str(_APP / "scripts"), str(_APP)]


def test_greybox_forecast_has_no_future_meter_input():
    from greybox.rc_1r1c import simulate_deployable

    t0 = 68.0
    oat = np.linspace(20.0, 30.0, 20)
    # Deployable path must not accept facility_kw / meter-derived arrays
    with pytest.raises((TypeError, ValueError)):
        simulate_deployable(
            t0,
            oat,
            facility_kw=np.ones(20) * 80.0,  # type: ignore[call-arg]
            a=0.9,
            b=0.1,
            c=0.0,
        )
    pred = simulate_deployable(t0, oat, a=0.9, b=0.1, c=0.0)
    assert len(pred) == len(oat)
    assert np.isfinite(pred).all()


def test_q_eff_diagnostic_forbidden_in_runtime_rollout():
    from greybox.rc_1r1c import Q_POLICY, simulate_deployable

    oat = np.ones(16) * 25.0
    with pytest.raises(ValueError, match="DIAGNOSTIC|deployable|forbidden"):
        simulate_deployable(
            68.0,
            oat,
            q_eff=np.ones(16) * 10.0,
            q_policy=Q_POLICY,
            a=0.9,
            b=0.1,
            c=0.01,
        )


def test_greybox_beats_open_loop_persistence_free_response():
    from greybox.benchmarks import (
        free_response_mask,
        horizon_mae,
        persistence_forecast,
        simulate_oat_only,
    )
    from greybox.rc_1r1c import fit_1r1c, simulate

    rng = np.random.default_rng(42)
    n = 400
    # Strong OAT coupling free-response (Q≈0)
    a_t, b_t = 0.85, 0.15
    oat = 10 + 20 * np.sin(np.linspace(0, 12, n))
    q = np.zeros(n)
    t = np.zeros(n)
    t[0] = 70.0
    for i in range(n - 1):
        t[i + 1] = a_t * t[i] + b_t * oat[i] + rng.normal(0, 0.02)
    occ = np.zeros(n)  # unoccupied = free response
    mask = free_response_mask(occ, facility_kw=np.full(n, 20.0))
    assert mask.sum() > 50

    p = fit_1r1c(t, oat, q, zone="zone_temp_1F_A_f")
    # Deployable free-response roll on a holdout window
    i0 = int(n * 0.7)
    tt, oo = t[i0:], oat[i0:]
    pred = simulate(float(tt[0]), oo[:-1], np.zeros(len(oo) - 1), a=p.a, b=p.b, c=0.0)
    pers = persistence_forecast(float(tt[0]), len(pred))
    mae_m = horizon_mae(tt[1:], pred, steps=16)  # 4h
    mae_p = horizon_mae(tt[1:], pers, steps=16)
    assert mae_m < mae_p, f"1R1C {mae_m} should beat persistence {mae_p}"
    oat_only = simulate_oat_only(float(tt[0]), oo[:-1])
    # Model should be at least competitive with naive OAT-only on this synthetic
    assert horizon_mae(tt[1:], pred, steps=16) <= horizon_mae(tt[1:], oat_only, steps=16) * 1.25


def test_greybox_parameter_boundary_gate():
    from greybox.benchmarks import parameter_boundary_flags, physics_gate_from_params

    flags = parameter_boundary_flags(a=0.999999, b=1e-6, c=0.0)
    assert flags["a_near_one"] is True
    assert flags["b_at_floor"] is True
    gate = physics_gate_from_params(a=0.999999, b=1e-6, c=0.0, beats_persistence=True)
    assert gate["physics_pass"] is False
    assert gate["reason"] == "BOUND_HIT"


def test_greybox_gate_failure_returns_nonzero(tmp_path):
    from greybox.benchmarks import blocking_exit_code

    assert blocking_exit_code(physics_pass=False, deployable_ok=True) != 0
    assert blocking_exit_code(physics_pass=True, deployable_ok=False) != 0
    assert blocking_exit_code(physics_pass=True, deployable_ok=True) == 0

    # Script must wire the same semantics (importable main returns nonzero)
    script = _APP / "scripts" / "train_greybox_identification_v1.py"
    assert script.is_file()
    # Force gate fail via CLI flag if present; else call evaluate helper used by script
    from train_greybox_identification_v1 import evaluate_gates_for_exit

    code = evaluate_gates_for_exit(
        {
            "physics_pass": False,
            "deployable_ok": False,
            "bound_hit": True,
            "beats_persistence": False,
        }
    )
    assert code != 0


def test_runtime_rejects_missing_required_feature():
    from hybrid_rollout import _row_features

    with pytest.raises(ValueError, match="missing|required|finite"):
        _row_features({"oat_f": 20.0}, ["oat_f", "rh_pct", "ghi"])


def test_runtime_requires_finite_weather_96():
    from hybrid_rollout import build_row

    state = {
        "facility_kw_lag1": 10.0,
        "facility_kw_lag2": 10.0,
        "oat_lag1": 20.0,
        "zone_temp_1F_A_f_lag1": 68.0,
        "zone_temp_1F_B_f_lag1": 68.0,
        "zone_temp_1F_C_f_lag1": 68.0,
        "zone_temp_1F_D_f_lag1": 68.0,
        "zone_temp_2F_A_f_lag1": 68.0,
        "zone_temp_2F_B_f_lag1": 68.0,
    }
    schedule = {"strategy_id": "baseline"}
    meta = {"month": 1, "doy": 1, "is_weekend": 0.0, "occupied_schedule": [0.0] * 96}
    # oat present but rh/ghi missing → fail closed
    weather_bad = {"oat_f": [20.0] * 96}
    with pytest.raises(ValueError, match="rh_pct|ghi|weather|finite"):
        build_row(
            step=0,
            weather=weather_bad,
            schedule=schedule,
            state=state,
            meta=meta,
            hdd_acc=0.0,
        )
    weather_ok = {
        "oat_f": [20.0] * 96,
        "rh_pct": [40.0] * 96,
        "ghi": [100.0] * 96,
    }
    row, _ = build_row(
        step=0,
        weather=weather_ok,
        schedule=schedule,
        state=state,
        meta=meta,
        hdd_acc=0.0,
    )
    assert row["rh_pct"] == 40.0
    assert row["ghi"] == 100.0


def test_no_production_bacnet_write_api():
    """Static/behavioral: production tree must not expose BACnet write helpers."""
    root = _APP
    forbidden = (
        "WriteProperty",
        "write_property",
        "WritePropertyMultiple",
        "bacnet_write",
        "BacnetWrite",
    )
    skip_parts = {"node_modules", ".venv", "__pycache__", ".git"}
    skip_files = {
        "test_greybox_identification_honesty.py",
        "test_control_twin_lab_v1.py",
        "greybox_forecast_honesty.md",
    }
    hits: list[str] = []
    for path in root.rglob("*"):
        if path.suffix.lower() not in {".py", ".rs", ".ts", ".js"}:
            continue
        if any(p in skip_parts for p in path.parts):
            continue
        if path.name in skip_files:
            continue
        try:
            text = path.read_text(encoding="utf-8", errors="ignore")
        except OSError:
            continue
        for tok in forbidden:
            if tok in text:
                hits.append(f"{path.relative_to(root)}:{tok}")
    assert hits == [], f"BACnet write surface found: {hits}"

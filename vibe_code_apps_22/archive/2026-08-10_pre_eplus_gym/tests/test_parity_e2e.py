"""Parity + lightweight E2E checks (no GPU / no long train)."""
from __future__ import annotations

import json
import sys
from pathlib import Path

import numpy as np
import pytest

_APP = Path(__file__).resolve().parents[1]
_ML = _APP / "ml"
_SCRIPTS = _APP / "scripts"
sys.path.insert(0, str(_ML))
sys.path.insert(0, str(_SCRIPTS))

from energy_math import quarter_hour_kwh  # noqa: E402
from feature_compile_15min import FEATURE_COLS_15MIN_MT  # noqa: E402
from hybrid_rollout import (  # noqa: E402
    HybridModels,
    build_row,
    init_state_from_contract,
    load_joblib_model,
    make_fixture_contract,
    rollout_96,
)
from promote_hybrid_ship import _reject_provisional_heldout  # noqa: E402

_ART = _ML / "artifacts"
_ONNX_BASE = _ART / "real_baseline_15min_v1.onnx"
_ONNX_DELTA = _ART / "eplus_delta_15min_v1.onnx"
_JOBLIB_BASE = _ART / "real_baseline_15min_v1.joblib"
_META_BASE = _ART / "real_baseline_15min_v1_feature_meta.json"
_WALK = _ART / "hybrid_dsm_96_v1_walk.json"


def _row_vector(row: dict, cols: list[str]) -> np.ndarray:
    return np.array([float(row.get(c, 0.0)) for c in cols], dtype=np.float32)


def _feature_rows_at_steps(strategy: str, steps: tuple[int, ...]):
    contract = make_fixture_contract(seed=21, dsm_strategy=strategy)
    state = init_state_from_contract(contract["init"])
    meta = contract["calendar"]
    weather = contract["weather_forecast_96"]
    schedule = contract["dsm_control_96"]
    rows = []
    hdd = 0.0
    for t in range(max(steps) + 1):
        row, hdd = build_row(
            step=t,
            weather=weather,
            schedule=schedule,
            state=state,
            meta=meta,
            hdd_acc=hdd,
        )
        if t in steps:
            rows.append((t, row))
    return contract, rows


def test_control_fixture_feature_vector_parity():
    meta_cols = list(FEATURE_COLS_15MIN_MT)
    if _META_BASE.is_file():
        meta = json.loads(_META_BASE.read_text(encoding="utf-8"))
        meta_cols = list(meta.get("feature_cols") or meta_cols)
        assert len(meta_cols) == len(FEATURE_COLS_15MIN_MT)

    for sid in ("baseline", "stagger_preheat"):
        contract, rows = _feature_rows_at_steps(sid, (0, 20, 48))
        assert len(rows) == 3
        if sid == "stagger_preheat":
            assert contract["dsm_control_96"]["stagger_min"] == pytest.approx(60.0)
        for _t, row in rows:
            vec = _row_vector(row, meta_cols)
            assert vec.shape == (len(meta_cols),)
            if sid == "stagger_preheat":
                assert row["stagger_min"] == pytest.approx(60.0)
                assert row["strategy_stagger_preheat"] == pytest.approx(1.0)
            else:
                assert row["strategy_baseline"] == pytest.approx(1.0)


@pytest.mark.skipif(
    not (_ONNX_BASE.is_file() and _ONNX_DELTA.is_file()),
    reason="ONNX artifacts not present",
)
def test_joblib_vs_onnx_predictions_loose_tol():
    ort = pytest.importorskip("onnxruntime")
    if not _JOBLIB_BASE.is_file():
        pytest.skip("joblib baseline missing — ONNX present but cannot compare")

    model, cols, _tcols = load_joblib_model(_JOBLIB_BASE)
    sess = ort.InferenceSession(str(_ONNX_BASE), providers=["CPUExecutionProvider"])
    _, rows = _feature_rows_at_steps("stagger_preheat", (0, 20, 48))
    X = np.stack([_row_vector(r, cols) for _, r in rows], axis=0)
    sk = np.asarray(model.predict(X), dtype=np.float64)
    on = np.asarray(sess.run(None, {"features": X})[0], dtype=np.float64)
    assert sk.shape == on.shape
    assert float(np.max(np.abs(sk - on))) < 1e-3


def test_walk_summary_kwh_matches_quarter_hour_energy():
    if not _WALK.is_file():
        pytest.skip("hybrid walk JSON not present")
    walk = json.loads(_WALK.read_text(encoding="utf-8"))
    steps = walk.get("steps") or []
    if len(steps) != 96:
        pytest.skip("walk does not have 96 steps")
    base_kw = [float(s["baseline_facility_kw"]) for s in steps]
    hyb_kw = [float(s["hybrid_facility_kw"]) for s in steps]
    summary = walk.get("summary") or {}
    assert summary["cumulative_kwh_baseline"] == pytest.approx(quarter_hour_kwh(base_kw), rel=1e-9)
    assert summary["cumulative_kwh_hybrid"] == pytest.approx(quarter_hour_kwh(hyb_kw), rel=1e-9)


def test_promote_rejects_provisional_note_thin():
    """Thin fail-closed check — full matrix lives in test_promote_hybrid_gates."""
    with pytest.raises(ValueError):
        _reject_provisional_heldout(
            {"note": "provisional_from_teacher_forced_until_notebook_retrain"},
            "baseline",
        )


def test_live_input_sensitivity_smoke():
    """Changing init facility_kw / oat changes rollout peak+kWh when models exist."""
    c0 = make_fixture_contract(seed=21, dsm_strategy="stagger_preheat")
    c1 = make_fixture_contract(seed=21, dsm_strategy="stagger_preheat")
    c1["init"]["facility_kw"] = float(c0["init"]["facility_kw"]) + 25.0
    c1["init"]["facility_kw_lag2"] = float(c1["init"]["facility_kw"])
    c1["init"]["oat_f"] = float(c0["init"]["oat_f"]) - 15.0
    # Contract fields must differ even without models.
    assert c1["init"]["facility_kw"] != c0["init"]["facility_kw"]
    assert c1["init"]["oat_f"] != c0["init"]["oat_f"]

    if not (_JOBLIB_BASE.is_file() and (_ART / "eplus_delta_15min_v1.joblib").is_file()):
        return

    base_m, cols, _ = load_joblib_model(_JOBLIB_BASE)
    delta_m, dcols, _ = load_joblib_model(_ART / "eplus_delta_15min_v1.joblib")
    assert cols == dcols
    models = HybridModels(baseline=base_m, delta=delta_m, feature_cols=cols)
    out0 = rollout_96(models, c0)
    out1 = rollout_96(models, c1)
    s0, s1 = out0["summary"], out1["summary"]
    changed = (
        s0["peak_kw_baseline"] != s1["peak_kw_baseline"]
        or s0["cumulative_kwh_baseline"] != s1["cumulative_kwh_baseline"]
        or s0["peak_kw_hybrid"] != s1["peak_kw_hybrid"]
        or s0["cumulative_kwh_hybrid"] != s1["cumulative_kwh_hybrid"]
    )
    assert changed, "expected live init change to move peak and/or kWh"

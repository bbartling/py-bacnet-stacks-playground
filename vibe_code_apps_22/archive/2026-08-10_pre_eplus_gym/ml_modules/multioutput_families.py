"""Shared multi-output family builders for baseline + delta bake-offs.

Families follow sklearn MultiOutput / Chain patterns (see MultiOutputRegressor docs)
and expose a uniform ``predict → (n, 7)`` interface for recursive rollout.
"""
from __future__ import annotations

from typing import Any, Callable

import numpy as np
from sklearn.ensemble import (
    ExtraTreesRegressor,
    GradientBoostingRegressor,
    HistGradientBoostingRegressor,
    RandomForestRegressor,
)
from sklearn.multioutput import MultiOutputRegressor, RegressorChain


class NativeMultiOutputWrapper:
    """Wrap a native multi-output estimator (Y shape (n, 7))."""

    def __init__(self, est: Any):
        self.est = est

    def fit(self, X, Y):
        self.est.fit(X, Y)
        return self

    def predict(self, X):
        out = np.asarray(self.est.predict(X), dtype=float)
        if out.ndim == 1:
            out = out.reshape(-1, 1)
        return out


def lean_family_protos(*, n_jobs: int = 1) -> dict[str, Any]:
    """Prototype estimators keyed by family name (not yet wrapped)."""
    return {
        "random_forest": RandomForestRegressor(
            n_estimators=120, max_depth=16, min_samples_leaf=2, random_state=21, n_jobs=n_jobs
        ),
        "extra_trees": ExtraTreesRegressor(
            n_estimators=120, max_depth=16, min_samples_leaf=2, random_state=21, n_jobs=n_jobs
        ),
        "gradient_boosting": GradientBoostingRegressor(
            n_estimators=80, max_depth=3, learning_rate=0.1, random_state=21
        ),
        "hist_gradient_boosting": HistGradientBoostingRegressor(
            max_depth=8, learning_rate=0.08, max_iter=120, random_state=21
        ),
        "regressor_chain_kw_first": GradientBoostingRegressor(
            n_estimators=60, max_depth=3, learning_rate=0.1, random_state=21
        ),
        "extra_trees_native_multi": ExtraTreesRegressor(
            n_estimators=120, max_depth=16, min_samples_leaf=2, random_state=21, n_jobs=n_jobs
        ),
    }


def wrap_family(name: str, proto: Any, *, n_jobs: int = 1) -> Any:
    """Build a fitted-ready estimator for ``name`` from a prototype."""
    params = dict(proto.get_params())
    if "n_jobs" in params:
        params["n_jobs"] = n_jobs
    est = proto.__class__(**params)
    if name == "extra_trees_native_multi":
        return NativeMultiOutputWrapper(est)
    if name == "regressor_chain_kw_first":
        # order: facility_kw (0) then zones 1..6
        return RegressorChain(est, order=list(range(7)), cv=None, random_state=21)
    return MultiOutputRegressor(est, n_jobs=n_jobs)


def make_fit_fn(
    families: dict[str, Any] | None = None,
    *,
    X: np.ndarray,
    Y: np.ndarray,
    n_jobs: int = 1,
) -> tuple[list[str], Callable[[str, np.ndarray], Any]]:
    """Return (family_names, fit_fn(name, tr_mask) -> model)."""
    protos = families or lean_family_protos(n_jobs=n_jobs)
    names = list(protos)

    def fit_fn(name: str, tr_mask: np.ndarray) -> Any:
        m = wrap_family(name, protos[name], n_jobs=n_jobs)
        m.fit(X[tr_mask], Y[tr_mask])
        return m

    return names, fit_fn


def pick_recursive_champion(
    families: list[str],
    cv_recursive: dict[str, dict[str, Any]],
    *,
    peak_key: str = "facility_kw_mae_peak_05_09",
    alt_peak_key: str = "mae_delta_kw_peak",
) -> str:
    """Select family with lowest recursive morning-peak MAE (never TF)."""

    def score(fam: str) -> float:
        blk = cv_recursive.get(fam) or {}
        for k in (peak_key, alt_peak_key):
            v = blk.get(k)
            if v is not None:
                try:
                    return float(v)
                except (TypeError, ValueError):
                    continue
        return float("inf")

    return min(families, key=score)


def spike_stats_from_per_day(
    per_day: dict[str, dict[str, Any]],
    *,
    plant_cap_kw: float = 450.0,
) -> dict[str, float]:
    """Aggregate held-out day scores for spike risk fields on cards."""
    if not per_day:
        return {
            "max_abs_delta_kw_heldout": 0.0,
            "frac_days_spike_over_cap": 0.0,
            "n_heldout_days": 0.0,
        }
    mags = []
    spikes = 0
    for m in per_day.values():
        if not isinstance(m, dict):
            continue
        # prefer peak mag error; else facility peak MAE as weak proxy
        for k in ("daily_peak_mag_error_kw", "facility_kw_mae_peak_05_09", "mae_delta_kw_peak"):
            if m.get(k) is not None:
                try:
                    mags.append(abs(float(m[k])))
                except (TypeError, ValueError):
                    pass
                break
        pred_peak = m.get("pred_peak_kw") or m.get("peak_pred_kw")
        if pred_peak is not None:
            try:
                if float(pred_peak) > plant_cap_kw:
                    spikes += 1
            except (TypeError, ValueError):
                pass
    n = max(len(per_day), 1)
    return {
        "max_abs_delta_kw_heldout": float(max(mags) if mags else 0.0),
        "frac_days_spike_over_cap": float(spikes) / float(n),
        "n_heldout_days": float(len(per_day)),
    }

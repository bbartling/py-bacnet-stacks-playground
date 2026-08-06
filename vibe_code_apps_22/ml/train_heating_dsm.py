"""Train hourly facility_kw heating DSM surrogate (sklearn) with day-group holdout."""

from __future__ import annotations

import argparse
import hashlib
import json
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import joblib
import numpy as np
import pandas as pd
from sklearn.ensemble import (
    ExtraTreesRegressor,
    GradientBoostingRegressor,
)
from sklearn.metrics import mean_absolute_error, mean_squared_error, make_scorer
from sklearn.model_selection import GroupKFold, RandomizedSearchCV

_ML = Path(__file__).resolve().parent
if str(_ML) not in sys.path:
    sys.path.insert(0, str(_ML))

from artifact_paths import artifact_paths, train_parquet_path  # noqa: E402
from feature_compile_heating_dsm import (  # noqa: E402
    FEATURE_COLS,
    assert_no_future_leakage,
    matrix_xy,
    morning_peak_mask,
)


def _metrics(y_true: np.ndarray, y_pred: np.ndarray, peak: np.ndarray | None = None) -> dict[str, float]:
    out = {
        "rmse": float(np.sqrt(mean_squared_error(y_true, y_pred))),
        "mae": float(np.mean(np.abs(y_true - y_pred))),
    }
    if peak is not None and peak.any():
        out["rmse_peak_05_09"] = float(np.sqrt(mean_squared_error(y_true[peak], y_pred[peak])))
        out["mae_peak_05_09"] = float(mean_absolute_error(y_true[peak], y_pred[peak]))
    else:
        out["rmse_peak_05_09"] = out["rmse"]
        out["mae_peak_05_09"] = out["mae"]
    return out


def _mean_scores(scores: list[dict[str, float]]) -> dict[str, float]:
    keys = scores[0].keys()
    return {k: float(np.mean([s[k] for s in scores])) for k in keys}


def bake_off(
    df: pd.DataFrame,
    *,
    n_splits: int = 5,
    n_iter: int = 40,
    n_iter_extra_trees: int | None = None,
) -> dict[str, Any]:
    """GroupKFold bake-off. Wider grids (~2×) per family; ExtraTrees gets extra trials."""
    assert_no_future_leakage(df)
    X, y, groups, cols = matrix_xy(df)
    peak = morning_peak_mask(df)
    uniq = np.unique(groups)
    n_splits = min(n_splits, max(2, len(uniq)))
    gkf = GroupKFold(n_splits=n_splits)
    mae_scorer = make_scorer(mean_absolute_error, greater_is_better=False)
    et_iters = int(n_iter_extra_trees if n_iter_extra_trees is not None else max(80, n_iter * 2))

    search_spaces: dict[str, tuple[Any, dict[str, list]]] = {
        # Slim bake-off: linear/RF/HGB lost to GB on peak MAE; keep GB + ExtraTrees.
        "gradient_boosting": (
            GradientBoostingRegressor(random_state=21),
            {
                "n_estimators": [80, 120, 160, 200, 280, 360, 450, 550],
                "learning_rate": [0.02, 0.03, 0.05, 0.07, 0.1, 0.12, 0.15, 0.2],
                "max_depth": [2, 3, 4, 5, 6, 7, 8],
                "min_samples_leaf": [1, 2, 4, 6, 8, 12, 20, 30],
                "min_samples_split": [2, 4, 6, 10, 16],
                "subsample": [0.55, 0.7, 0.8, 0.9, 1.0],
                "max_features": [0.35, 0.5, 0.7, 0.85, 1.0, "sqrt", "log2"],
                "loss": ["squared_error", "huber"],
                "alpha": [0.7, 0.85, 0.9],  # used when loss=huber
                "ccp_alpha": [0.0, 1e-5, 1e-4],
                "tol": [1e-4, 1e-3],
            },
        ),
        "extra_trees": (
            ExtraTreesRegressor(random_state=21, n_jobs=-1),
            {
                "n_estimators": [150, 220, 300, 400, 500, 600, 750],
                "max_depth": [8, 10, 14, 18, 22, 28, 36, None],
                "min_samples_split": [2, 3, 4, 6, 8, 12, 16],
                "min_samples_leaf": [1, 2, 3, 4, 5, 8, 12],
                "max_features": [0.25, 0.35, 0.5, 0.65, 0.8, 0.95, 1.0, "sqrt", "log2"],
                "bootstrap": [False, True],
                "criterion": ["squared_error", "friedman_mse"],
                "ccp_alpha": [0.0, 1e-6, 1e-5, 1e-4, 5e-4, 1e-3],
                "min_impurity_decrease": [0.0, 1e-6, 1e-5, 1e-4, 5e-4],
                "max_leaf_nodes": [None, 128, 256, 512, 1024, 2048],
            },
        ),
    }

    cv_scores: dict[str, list[dict[str, float]]] = {k: [] for k in search_spaces}
    best_params: dict[str, dict[str, Any]] = {}
    tuned_models: dict[str, Any] = {}
    pers_scores: list[dict[str, float]] = []
    lag_i = cols.index("facility_kw_lag1")
    search_iters: dict[str, int] = {}

    for name, (proto, space) in search_spaces.items():
        n_combos = 1
        for v in space.values():
            n_combos *= max(len(v), 1)
        budget = et_iters if name == "extra_trees" else n_iter
        if name == "gradient_boosting":
            budget = max(budget, int(n_iter * 1.25))
        iters = min(budget, n_combos)
        search_iters[name] = iters
        search = RandomizedSearchCV(
            proto,
            space,
            n_iter=iters,
            scoring=mae_scorer,
            cv=gkf,
            random_state=21,
            n_jobs=-1,
            refit=True,
            error_score=np.nan,
        )
        search.fit(X, y, groups=groups)
        best_params[name] = dict(search.best_params_)
        tuned_models[name] = search.best_estimator_

    for tr, te in gkf.split(X, y, groups):
        y_te = y[te]
        p_te = peak[te]
        pers_scores.append(_metrics(y_te, X[te, lag_i], p_te))
        for name, est in tuned_models.items():
            m = est.__class__(**est.get_params())
            m.fit(X[tr], y[tr])
            cv_scores[name].append(_metrics(y_te, m.predict(X[te]), p_te))

    summary = {"persistence": _mean_scores(pers_scores)}
    for name in search_spaces:
        summary[name] = _mean_scores(cv_scores[name])

    champ_name = min(search_spaces.keys(), key=lambda n: summary[n]["mae_peak_05_09"])
    beat = summary[champ_name]["mae_peak_05_09"] < summary["persistence"]["mae_peak_05_09"]
    champ = tuned_models[champ_name].__class__(**tuned_models[champ_name].get_params())
    champ.fit(X, y)

    leaderboard = [
        {
            "family": n,
            "oof_metrics": summary[n],
            "best_params": best_params[n],
            "n_iter_searched": search_iters[n],
        }
        for n in search_spaces
    ]
    leaderboard.sort(key=lambda e: e["oof_metrics"]["mae_peak_05_09"])

    return {
        "model": champ,
        "champion": champ_name,
        "best_params": best_params[champ_name],
        "best_params_by_family": best_params,
        "tuned_models": tuned_models,
        "feature_cols": cols,
        "cv": summary,
        "leaderboard": leaderboard,
        "beat_persistence_peak": beat,
        "n_rows": int(len(df)),
        "n_days": int(df["day"].nunique()),
        "n_splits": n_splits,
        "n_iter": n_iter,
        "n_iter_extra_trees": et_iters,
        "search_iters": search_iters,
        "X": X,
        "y": y,
        "groups": groups,
        "peak": peak,
    }


def main(argv: list[str] | None = None) -> int:
    """Deprecated hourly ship path — hybrid Real+E+ is the only production train."""
    _ = argv
    print(
        "REFUSED: heating_dsm_hourly_v1 ship path is quarantined.\n"
        "Use the hybrid Real+E+ pipeline instead:\n"
        "  python -u scripts/build_real_15min_store.py\n"
        "  python -u ml/train_real_baseline_15min.py\n"
        "  python -u scripts/eplus_heating_dsm_farm.py --smoke|--medium\n"
        "  python -u ml/train_eplus_delta_15min.py\n"
        "  python -u scripts/promote_hybrid_ship.py\n"
        "See vibe22_agent_spec/HEATING_DSM.md",
        file=sys.stderr,
    )
    return 2


if __name__ == "__main__":
    raise SystemExit(main())

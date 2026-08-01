"""Plot + dump helpers for the demand_hourly training notebook (Kaggle-style)."""

from __future__ import annotations

import hashlib
import json
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import joblib
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
from sklearn.ensemble import ExtraTreesRegressor
from sklearn.metrics import mean_absolute_error, mean_squared_error
from sklearn.model_selection import GroupKFold, RandomizedSearchCV
from sklearn.metrics import make_scorer

_ML = Path(__file__).resolve().parent
if str(_ML) not in sys.path:
    sys.path.insert(0, str(_ML))

from artifact_paths import JOBLIB_NAME, CARD_NAME, TUNING_NAME, default_model_dir  # noqa: E402
from feature_compile_dm import FEATURE_COLS, assert_no_future_leakage, matrix_xy, peak_mask  # noqa: E402
from tune_demand_hourly import SEARCH_SPACES, _clone_fit_params, _metrics, _oof_predict  # noqa: E402


def family_cv_mae_bars(leaderboard: list[dict[str, Any]], persistence_peak: float, ax=None):
    """Bar chart of OOF peak MAE by family vs persistence."""
    ax = ax or plt.gca()
    names = [e["family"] for e in leaderboard]
    maes = [e["oof_metrics"]["mae_peak_14_16"] for e in leaderboard]
    colors = ["#2a9d8f" if m < persistence_peak else "#e76f51" for m in maes]
    ax.barh(names, maes, color=colors)
    ax.axvline(persistence_peak, color="#264653", ls="--", label=f"persistence {persistence_peak:.2f}")
    ax.set_xlabel("OOF peak MAE (HE 14–16) [kW]")
    ax.set_title("Family bake-off — peak MAE (lower is better)")
    ax.legend(loc="best")
    return ax


def extratrees_search_scatter(cv_results: dict, ax=None):
    """Scatter mean CV MAE vs n_estimators colored by max_depth (from RandomizedSearchCV)."""
    ax = ax or plt.gca()
    df = pd.DataFrame(cv_results)
    # RandomizedSearchCV stores params as param_* and mean_test_score (neg MAE)
    mae = -df["mean_test_score"].to_numpy()
    n_est = df["param_n_estimators"].astype(float)
    depth = df["param_max_depth"].apply(lambda x: -1 if x is None or (isinstance(x, float) and np.isnan(x)) else int(x))
    sc = ax.scatter(n_est, mae, c=depth, cmap="viridis", alpha=0.85, edgecolors="k", linewidths=0.3)
    plt.colorbar(sc, ax=ax, label="max_depth (−1 = None)")
    ax.set_xlabel("n_estimators")
    ax.set_ylabel("CV MAE [kW]")
    ax.set_title("ExtraTrees hyperparam search (CV MAE)")
    return ax


def pred_vs_actual(y_true: np.ndarray, y_pred: np.ndarray, ax=None):
    ax = ax or plt.gca()
    ax.scatter(y_true, y_pred, s=8, alpha=0.35, c="#457b9d")
    lo = float(min(y_true.min(), y_pred.min()))
    hi = float(max(y_true.max(), y_pred.max()))
    ax.plot([lo, hi], [lo, hi], "k--", lw=1)
    ax.set_xlabel("Actual facility_kw")
    ax.set_ylabel("Predicted facility_kw")
    ax.set_title("OOF pred vs actual")
    rmse = float(np.sqrt(mean_squared_error(y_true, y_pred)))
    mae = float(mean_absolute_error(y_true, y_pred))
    ax.text(0.02, 0.98, f"MAE={mae:.2f}\nRMSE={rmse:.2f}", transform=ax.transAxes, va="top", fontsize=9)
    return ax


def residual_hist(y_true: np.ndarray, y_pred: np.ndarray, ax=None):
    ax = ax or plt.gca()
    resid = y_pred - y_true
    ax.hist(resid, bins=40, color="#a8dadc", edgecolor="#1d3557")
    ax.axvline(0, color="#e63946", ls="--")
    ax.set_xlabel("Residual (pred − actual) [kW]")
    ax.set_title("OOF residual distribution")
    return ax


def feature_importance_bar(model: Any, feature_names: list[str], top_n: int = 15, ax=None):
    ax = ax or plt.gca()
    if not hasattr(model, "feature_importances_"):
        ax.text(0.5, 0.5, "no feature_importances_", ha="center")
        return ax
    imp = np.asarray(model.feature_importances_, dtype=float)
    order = np.argsort(imp)[::-1][:top_n]
    ax.barh([feature_names[i] for i in order][::-1], imp[order][::-1], color="#2a9d8f")
    ax.set_xlabel("Importance")
    ax.set_title(f"Top {top_n} feature importances")
    return ax


def run_extratrees_search(
    df: pd.DataFrame,
    *,
    n_iter: int = 48,
    n_splits: int = 5,
    random_state: int = 21,
) -> dict[str, Any]:
    """Focused ExtraTrees RandomizedSearchCV for notebook plots + optional dump."""
    assert_no_future_leakage(FEATURE_COLS)
    X, y, groups, cols = matrix_xy(df)
    peak = peak_mask(df)
    uniq = np.unique(groups)
    n_splits = min(n_splits, max(2, len(uniq)))
    gkf = GroupKFold(n_splits=n_splits)
    mae_scorer = make_scorer(mean_absolute_error, greater_is_better=False)
    proto, space = SEARCH_SPACES["extra_trees"]
    n_combos = 1
    for v in space.values():
        n_combos *= max(len(v), 1)
    iters = min(n_iter, n_combos)
    search = RandomizedSearchCV(
        proto,
        space,
        n_iter=iters,
        scoring=mae_scorer,
        cv=gkf,
        random_state=random_state,
        n_jobs=-1,
        refit=True,
    )
    search.fit(X, y, groups=groups)
    oof = _oof_predict(
        lambda p=dict(search.best_params_), e=search.best_estimator_: _clone_fit_params(
            e, p, random_state=random_state
        ),
        X,
        y,
        groups,
        gkf,
    )
    return {
        "search": search,
        "model": search.best_estimator_,
        "best_params": dict(search.best_params_),
        "oof": oof,
        "y": y,
        "peak": peak,
        "feature_cols": cols,
        "oof_metrics": _metrics(y, oof, peak),
        "cv_results": search.cv_results_,
        "n_splits": n_splits,
        "n_rows": int(len(df)),
        "n_days": int(df["day"].nunique()),
    }


def dump_champion_bundle(
    model: Any,
    *,
    feature_cols: list[str],
    champion: str,
    best_params: dict[str, Any],
    oof_metrics: dict[str, float],
    n_rows: int,
    n_days: int,
    training_parquet: str | Path,
    training_source: str = "ENERGYPLUS_SIMULATED",
    out_dir: Path | None = None,
    leaderboard: list[dict[str, Any]] | None = None,
    persistence: dict[str, float] | None = None,
) -> Path:
    """Write joblib + model card (+ optional tuning) into flask_app/models/."""
    out_dir = out_dir or default_model_dir()
    out_dir.mkdir(parents=True, exist_ok=True)
    artifact = out_dir / JOBLIB_NAME
    joblib.dump(
        {
            "model": model,
            "feature_cols": list(feature_cols),
            "champion": champion,
            "best_params": best_params,
            "schema": "vibe21.dm_hourly_row.v1",
        },
        artifact,
    )
    sha = hashlib.sha256(artifact.read_bytes()).hexdigest()
    beat = False
    if persistence and "mae_peak_14_16" in persistence:
        beat = oof_metrics.get("mae_peak_14_16", 1e9) < persistence["mae_peak_14_16"]
    card = {
        "schema_version": "vibe21.model_registry.v1",
        "model_id": "demand_hourly_v1",
        "family": "OPERATIONAL_DEMAND",
        "artifact": str(artifact),
        "artifact_sha256": sha,
        "status": "CANDIDATE",
        "targets": ["facility_kw"],
        "champion": champion,
        "best_params": best_params,
        "feature_cols": list(feature_cols),
        "cv_metrics": {"champion_oof": oof_metrics, **({"persistence": persistence} if persistence else {})},
        "beat_persistence_peak": beat,
        "n_rows": n_rows,
        "n_days": n_days,
        "training_parquet": str(training_parquet),
        "training_source": training_source,
        "sklearn_version": __import__("sklearn").__version__,
        "created_utc": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "honesty": (
            "Hyperparam-tuned surrogate for Unity DR knobs. "
            "CANDIDATE until BAS-validated. "
            f"Source={training_source}."
        ),
        "unity_contract": {
            "inputs": ["oat_c", "rh_pct", "hour_ending", "strategy_id", "action knobs"],
            "output": "facility_kw",
        },
    }
    (out_dir / CARD_NAME).write_text(json.dumps(card, indent=2) + "\n", encoding="utf-8")
    if leaderboard is not None:
        tuning = {
            "persistence": persistence,
            "leaderboard": leaderboard,
            "champion": champion,
            "best_params": best_params,
            "beat_persistence_peak": beat,
            "n_rows": n_rows,
            "n_days": n_days,
            "feature_cols": list(feature_cols),
        }
        (out_dir / TUNING_NAME).write_text(json.dumps(tuning, indent=2) + "\n", encoding="utf-8")
    return artifact

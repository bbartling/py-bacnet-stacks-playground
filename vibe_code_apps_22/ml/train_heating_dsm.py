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
    HistGradientBoostingRegressor,
    RandomForestRegressor,
)
from sklearn.linear_model import ElasticNet, Ridge
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
    n_iter: int = 24,
    n_iter_extra_trees: int | None = None,
) -> dict[str, Any]:
    """GroupKFold bake-off. ExtraTrees gets a wider HVAC/tabular search + more trials."""
    assert_no_future_leakage(df)
    X, y, groups, cols = matrix_xy(df)
    peak = morning_peak_mask(df)
    uniq = np.unique(groups)
    n_splits = min(n_splits, max(2, len(uniq)))
    gkf = GroupKFold(n_splits=n_splits)
    mae_scorer = make_scorer(mean_absolute_error, greater_is_better=False)
    # Beefy ET budget: correlated weather/lag features + thin day groups
    et_iters = int(n_iter_extra_trees if n_iter_extra_trees is not None else max(48, n_iter * 2))

    search_spaces: dict[str, tuple[Any, dict[str, list]]] = {
        "ridge": (Ridge(), {"alpha": np.logspace(-3, 3, 16).tolist()}),
        "elasticnet": (
            ElasticNet(max_iter=5000, random_state=21),
            {"alpha": np.logspace(-3, 1, 10).tolist(), "l1_ratio": [0.1, 0.3, 0.5, 0.7, 0.9]},
        ),
        "rf": (
            RandomForestRegressor(random_state=21, n_jobs=-1),
            {
                "n_estimators": [100, 160, 240, 320],
                "max_depth": [8, 12, 16, 24, None],
                "min_samples_leaf": [1, 2, 4],
                "max_features": [0.5, 0.8, "sqrt"],
            },
        ),
        # Classic GBM — strong on small tabular HVAC farms; sequential trees catch
        # nonlinear OAT×lag interactions ExtraTrees sometimes under-smooths.
        "gradient_boosting": (
            GradientBoostingRegressor(random_state=21),
            {
                "n_estimators": [100, 150, 200, 300, 400],
                "learning_rate": [0.03, 0.05, 0.08, 0.1, 0.15],
                "max_depth": [2, 3, 4, 5, 6],
                "min_samples_leaf": [2, 4, 8, 12, 20],
                "min_samples_split": [2, 5, 10],
                "subsample": [0.7, 0.85, 1.0],
                "max_features": [0.5, 0.7, 1.0, "sqrt"],
                "loss": ["squared_error", "huber"],
            },
        ),
        # ExtraTrees: strong on noisy IdealLoads+COP + lag-heavy heating DSM rows.
        # Wider grid covers depth vs leaf regularization, feature subsampling for
        # correlated OAT/HDD/lag columns, and light CCP pruning.
        "extra_trees": (
            ExtraTreesRegressor(random_state=21, n_jobs=-1),
            {
                "n_estimators": [200, 300, 400, 500, 600],
                "max_depth": [10, 14, 18, 24, 32, None],
                "min_samples_split": [2, 4, 6, 10, 16],
                "min_samples_leaf": [1, 2, 3, 5, 8],
                "max_features": [0.35, 0.5, 0.65, 0.8, 1.0, "sqrt", "log2"],
                "bootstrap": [False, True],
                "criterion": ["squared_error", "friedman_mse"],
                "ccp_alpha": [0.0, 1e-5, 1e-4, 5e-4, 1e-3],
                "min_impurity_decrease": [0.0, 1e-5, 1e-4, 5e-4],
                "max_leaf_nodes": [None, 256, 512, 1024],
            },
        ),
        "hgb": (
            HistGradientBoostingRegressor(random_state=21),
            {
                "learning_rate": [0.03, 0.06, 0.1],
                "max_depth": [4, 6, 8, None],
                "max_iter": [150, 250, 400],
                "min_samples_leaf": [10, 20, 40],
            },
        ),
    }

    cv_scores: dict[str, list[dict[str, float]]] = {k: [] for k in search_spaces}
    best_params: dict[str, dict[str, Any]] = {}
    tuned_models: dict[str, Any] = {}
    pers_scores: list[dict[str, float]] = []
    lag_i = cols.index("facility_kw_lag1")

    for name, (proto, space) in search_spaces.items():
        n_combos = 1
        for v in space.values():
            n_combos *= max(len(v), 1)
        budget = et_iters if name == "extra_trees" else n_iter
        iters = min(budget, n_combos)
        # max_samples only valid when bootstrap=True — filter invalid draws via search
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
        "n_iter_extra_trees": et_iters,
        "X": X,
        "y": y,
        "groups": groups,
        "peak": peak,
    }


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--parquet", type=Path, default=None)
    ap.add_argument("--out-dir", type=Path, default=None)
    ap.add_argument("--n-splits", type=int, default=5)
    ap.add_argument("--n-iter", type=int, default=24, help="RandomizedSearch trials per family")
    ap.add_argument(
        "--n-iter-extra-trees",
        type=int,
        default=56,
        help="ExtraTrees trials (wider HVAC/tabular grid)",
    )
    ap.add_argument("--skip-onnx", action="store_true", help="Skip skl2onnx desktop export")
    args = ap.parse_args(argv)

    pq = args.parquet or train_parquet_path()
    paths = artifact_paths(args.out_dir)
    if not pq.is_file():
        print(f"missing {pq} — run eplus_heating_dsm_farm.py or build_bootstrap_dataset.py", file=sys.stderr)
        return 2

    df = pd.read_parquet(pq)
    src = "BAS_BOOTSTRAP_PROXY"
    if "provenance" in df.columns and len(df):
        src = str(df["provenance"].iloc[0])
    result = bake_off(
        df,
        n_splits=args.n_splits,
        n_iter=args.n_iter,
        n_iter_extra_trees=args.n_iter_extra_trees,
    )

    # Desktop ONNX always ships ExtraTrees (best skl2onnx tree ensemble for this stack).
    et_model = result["tuned_models"]["extra_trees"]
    et_params = result["best_params_by_family"]["extra_trees"]
    et_peak = float(result["cv"]["extra_trees"]["mae_peak_05_09"])

    joblib.dump(
        {
            "model": result["model"],
            "extra_trees_model": et_model,
            "feature_cols": result["feature_cols"],
            "champion": result["champion"],
            "best_params": result.get("best_params"),
            "extra_trees_params": et_params,
            "schema": "lakeside.heating_dsm_hourly.v1",
        },
        paths["joblib"],
    )
    sha = hashlib.sha256(paths["joblib"].read_bytes()).hexdigest()

    card = {
        "schema_version": "lakeside.model_registry.v1",
        "model_id": "heating_dsm_hourly_v1",
        "family": "HEATING_DSM_DEMAND",
        "artifact": str(paths["joblib"]),
        "artifact_sha256": sha,
        "status": "CANDIDATE",
        "targets": ["facility_kw"],
        "champion": result["champion"],
        "best_params": result.get("best_params"),
        "desktop_onnx_family": "extra_trees",
        "extra_trees_params": et_params,
        "cv_metrics": result["cv"],
        "beat_persistence_peak": result["beat_persistence_peak"],
        "peak_window": "HE_05_09_local",
        "n_rows": result["n_rows"],
        "n_days": result["n_days"],
        "n_iter_extra_trees": result.get("n_iter_extra_trees"),
        "training_parquet": str(pq),
        "training_source": src,
        "sklearn_version": __import__("sklearn").__version__,
        "created_utc": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "honesty": (
            "Heating DSM surrogate for 6-Area HP occupancy / preheat. "
            f"Source={src}. IdealLoads+COP proxy when ENERGYPLUS_SIMULATED. "
            "Desktop ONNX = sklearn ExtraTrees (skl2onnx). "
            "CANDIDATE — not tariff-grade. Zone-temp multi-target farm is Phase B2."
        ),
        "feature_cols": FEATURE_COLS,
    }
    paths["card"].write_text(json.dumps(card, indent=2) + "\n", encoding="utf-8")

    champ_summary = {
        "champion": result["champion"],
        "desktop_onnx_family": "extra_trees",
        "beat_persistence_peak": result["beat_persistence_peak"],
        "cv": result["cv"],
        "leaderboard": [
            {"family": e["family"], "oof_metrics": e["oof_metrics"]} for e in result["leaderboard"]
        ],
    }
    paths["champion_summary"].write_text(
        json.dumps(champ_summary, indent=2) + "\n", encoding="utf-8"
    )

    onnx_info: dict[str, Any] = {}
    if not args.skip_onnx:
        from export_sklearn_onnx import (  # noqa: WPS433
            copy_ship_to_desktop,
            export_sklearn_onnx,
            roundtrip_check,
        )

        meta = export_sklearn_onnx(
            et_model,
            n_features=len(result["feature_cols"]),
            onnx_path=paths["onnx"],
            meta_path=paths["feature_meta"],
            feature_cols=result["feature_cols"],
            champion="extra_trees",
            model_display_name="ExtraTreesRegressor",
            best_params=et_params,
            training_source=src,
            honesty=card["honesty"],
            cv_metrics=result["cv"]["extra_trees"],
            cv_peak_mae=et_peak,
        )
        max_abs = roundtrip_check(et_model, paths["onnx"], result["X"], n=48)
        desk = copy_ship_to_desktop(paths["onnx"], paths["feature_meta"])
        onnx_info = {
            "onnx": str(paths["onnx"]),
            "feature_meta": str(paths["feature_meta"]),
            "desktop_copy": str(desk),
            "roundtrip_max_abs": max_abs,
            "cv_mae_peak_05_09": et_peak,
        }
        print(f"wrote ONNX {paths['onnx']}  roundtrip_max_abs={max_abs:.6g}")
        print(f"copied ship artifacts → {desk}")

    print(
        json.dumps(
            {
                "model_id": card["model_id"],
                "status": card["status"],
                "champion": card["champion"],
                "desktop_onnx_family": "extra_trees",
                "beat_persistence_peak": card["beat_persistence_peak"],
                "cv_metrics": {
                    k: result["cv"][k]
                    for k in ("persistence", "extra_trees", result["champion"])
                    if k in result["cv"]
                },
                "extra_trees_params": et_params,
                "artifact": card["artifact"],
                "onnx": onnx_info,
            },
            indent=2,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

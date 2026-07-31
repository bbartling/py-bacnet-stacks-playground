"""GroupKFold hyperparameter hunt for demand_hourly_v1 (Unity DR knobs)."""

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
from sklearn.ensemble import HistGradientBoostingRegressor, RandomForestRegressor
from sklearn.linear_model import ElasticNet, Ridge
from sklearn.metrics import mean_absolute_error, mean_squared_error, make_scorer
from sklearn.model_selection import GroupKFold, RandomizedSearchCV

_ML = Path(__file__).resolve().parent
if str(_ML) not in sys.path:
    sys.path.insert(0, str(_ML))

from feature_compile_dm import FEATURE_COLS, compile_features, matrix_xy, peak_mask  # noqa: E402
from train_demand_hourly import load_farm_frame, _workspace  # noqa: E402


def _metrics(y_true: np.ndarray, y_pred: np.ndarray, peak: np.ndarray | None = None) -> dict[str, float]:
    out = {
        "rmse": float(np.sqrt(mean_squared_error(y_true, y_pred))),
        "mae": float(mean_absolute_error(y_true, y_pred)),
    }
    if peak is not None and peak.any():
        out["rmse_peak_14_16"] = float(np.sqrt(mean_squared_error(y_true[peak], y_pred[peak])))
        out["mae_peak_14_16"] = float(mean_absolute_error(y_true[peak], y_pred[peak]))
    else:
        out["rmse_peak_14_16"] = out["rmse"]
        out["mae_peak_14_16"] = out["mae"]
    return out


SEARCH_SPACES: dict[str, tuple[Any, dict[str, list]]] = {
    "ridge": (
        Ridge(),
        {"alpha": np.logspace(-3, 3, 20).tolist()},
    ),
    "elasticnet": (
        ElasticNet(max_iter=5000, random_state=21),
        {
            "alpha": np.logspace(-3, 1, 12).tolist(),
            "l1_ratio": [0.1, 0.3, 0.5, 0.7, 0.9, 0.95],
        },
    ),
    "rf": (
        RandomForestRegressor(random_state=21, n_jobs=-1),
        {
            "n_estimators": [80, 120, 200],
            "max_depth": [6, 10, 16, None],
            "min_samples_leaf": [1, 2, 4, 8],
        },
    ),
    "hgb": (
        HistGradientBoostingRegressor(random_state=21),
        {
            "learning_rate": [0.03, 0.05, 0.08, 0.12],
            "max_depth": [3, 5, 8, None],
            "max_iter": [100, 200, 400],
            "min_samples_leaf": [10, 20, 40],
        },
    ),
}


def tune(
    df: pd.DataFrame,
    *,
    n_splits: int = 5,
    n_iter: int = 40,
    random_state: int = 21,
) -> dict[str, Any]:
    X, y, groups, cols = matrix_xy(df)
    peak = peak_mask(df)
    uniq = np.unique(groups)
    n_splits = min(n_splits, max(2, len(uniq)))
    gkf = GroupKFold(n_splits=n_splits)
    mae_scorer = make_scorer(mean_absolute_error, greater_is_better=False)

    # Persistence baseline
    lag_i = cols.index("facility_kw_lag1")
    pers_fold = []
    for _, te in gkf.split(X, y, groups):
        pers_fold.append(_metrics(y[te], X[te, lag_i], peak[te]))
    persistence = {
        k: float(np.mean([f[k] for f in pers_fold])) for k in pers_fold[0]
    }

    leaderboard: list[dict[str, Any]] = []
    best_name = None
    best_est = None
    best_peak = float("inf")
    best_params: dict[str, Any] = {}

    for name, (proto, space) in SEARCH_SPACES.items():
        n_combos = 1
        for v in space.values():
            n_combos *= max(len(v), 1)
        iters = min(n_iter, n_combos)
        print(f"tune {name} n_iter={iters} …", flush=True)
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
        pred = search.best_estimator_.predict(X)
        # Holdout-style peak via CV predictions
        oof = np.zeros_like(y)
        for tr, te in gkf.split(X, y, groups):
            m = search.best_estimator_.__class__(**search.best_params_)
            if "random_state" in m.get_params():
                m.set_params(random_state=random_state)
            if "n_jobs" in m.get_params():
                m.set_params(n_jobs=-1)
            m.fit(X[tr], y[tr])
            oof[te] = m.predict(X[te])
        met = _metrics(y, oof, peak)
        entry = {
            "family": name,
            "best_params": search.best_params_,
            "cv_neg_mae": float(search.best_score_),
            "oof_metrics": met,
            "beat_persistence_peak": met["mae_peak_14_16"] < persistence["mae_peak_14_16"],
        }
        leaderboard.append(entry)
        print(
            f"  {name} peak_mae={met['mae_peak_14_16']:.3f} "
            f"vs pers={persistence['mae_peak_14_16']:.3f} params={search.best_params_}",
            flush=True,
        )
        if met["mae_peak_14_16"] < best_peak:
            best_peak = met["mae_peak_14_16"]
            best_name = name
            best_est = search.best_estimator_
            best_params = search.best_params_

    assert best_est is not None and best_name is not None
    # Refit champion on all data with best params
    champ = best_est.__class__(**best_params)
    if "random_state" in champ.get_params():
        champ.set_params(random_state=random_state)
    if "n_jobs" in champ.get_params():
        champ.set_params(n_jobs=-1)
    champ.fit(X, y)

    return {
        "model": champ,
        "champion": best_name,
        "best_params": best_params,
        "feature_cols": cols,
        "persistence": persistence,
        "leaderboard": leaderboard,
        "beat_persistence_peak": best_peak < persistence["mae_peak_14_16"],
        "n_rows": int(len(df)),
        "n_days": int(df["day"].nunique()),
        "n_splits": n_splits,
    }


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--parquet", type=Path, default=None)
    ap.add_argument("--out-dir", type=Path, default=None)
    ap.add_argument("--n-iter", type=int, default=40)
    ap.add_argument("--n-splits", type=int, default=5)
    args = ap.parse_args(argv)

    ws = _workspace()
    pq = args.parquet or (ws / "reports" / "dm_hourly_farm" / "dm_hourly_rows.parquet")
    out_dir = args.out_dir or (ws / "models")
    out_dir.mkdir(parents=True, exist_ok=True)
    if not pq.is_file():
        print(f"missing {pq}", file=sys.stderr)
        return 2

    df = load_farm_frame(pq)
    # Prefer physics-grade farms; warn if proxy
    src = None
    fs = pq.parent / "farm_summary.json"
    farm_summary = {}
    if fs.is_file():
        farm_summary = json.loads(fs.read_text(encoding="utf-8"))
        src = farm_summary.get("source")
        print(f"training_source={src}", flush=True)

    result = tune(df, n_splits=args.n_splits, n_iter=args.n_iter)
    artifact = out_dir / "demand_hourly_v1.joblib"
    joblib.dump(
        {
            "model": result["model"],
            "feature_cols": result["feature_cols"],
            "champion": result["champion"],
            "best_params": result["best_params"],
            "schema": "vibe21.dm_hourly_row.v1",
        },
        artifact,
    )
    sha = hashlib.sha256(artifact.read_bytes()).hexdigest()

    tuning = {
        "persistence": result["persistence"],
        "leaderboard": result["leaderboard"],
        "champion": result["champion"],
        "best_params": result["best_params"],
        "beat_persistence_peak": result["beat_persistence_peak"],
        "n_rows": result["n_rows"],
        "n_days": result["n_days"],
        "feature_cols": FEATURE_COLS,
    }
    (out_dir / "demand_hourly_v1_tuning.json").write_text(
        json.dumps(tuning, indent=2) + "\n", encoding="utf-8"
    )

    card = {
        "schema_version": "vibe21.model_registry.v1",
        "model_id": "demand_hourly_v1",
        "family": "OPERATIONAL_DEMAND",
        "artifact": str(artifact),
        "artifact_sha256": sha,
        "status": "CANDIDATE",
        "targets": ["facility_kw"],
        "champion": result["champion"],
        "best_params": result["best_params"],
        "cv_metrics": {
            "persistence": result["persistence"],
            **{e["family"]: e["oof_metrics"] for e in result["leaderboard"]},
        },
        "beat_persistence_peak": result["beat_persistence_peak"],
        "n_rows": result["n_rows"],
        "n_days": result["n_days"],
        "training_parquet": str(pq),
        "training_source": src or "unknown",
        "engine": farm_summary.get("engine"),
        "sklearn_version": __import__("sklearn").__version__,
        "created_utc": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "honesty": (
            "Hyperparam-tuned surrogate for Unity DR knobs. "
            "CANDIDATE until BAS-validated. "
            f"Source={src}."
        ),
        "unity_contract": {
            "inputs": ["oat_c", "rh_pct", "hour_ending", "strategy_id", "action knobs"],
            "output": "facility_kw",
        },
    }
    (out_dir / "demand_hourly_v1_model_card.json").write_text(
        json.dumps(card, indent=2) + "\n", encoding="utf-8"
    )
    print(
        json.dumps(
            {
                "champion": result["champion"],
                "best_params": result["best_params"],
                "beat_persistence_peak": result["beat_persistence_peak"],
                "persistence_peak_mae": result["persistence"]["mae_peak_14_16"],
                "leaderboard_peak_mae": {
                    e["family"]: e["oof_metrics"]["mae_peak_14_16"] for e in result["leaderboard"]
                },
                "artifact": str(artifact),
                "training_source": src,
            },
            indent=2,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

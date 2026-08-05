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
from sklearn.ensemble import ExtraTreesRegressor, HistGradientBoostingRegressor, RandomForestRegressor
from sklearn.linear_model import ElasticNet, Ridge
from sklearn.metrics import mean_absolute_error, mean_squared_error
from sklearn.model_selection import GroupKFold

_ML = Path(__file__).resolve().parent
if str(_ML) not in sys.path:
    sys.path.insert(0, str(_ML))

from artifact_paths import artifact_paths, bootstrap_parquet_path  # noqa: E402
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


def bake_off(df: pd.DataFrame, *, n_splits: int = 5) -> dict[str, Any]:
    assert_no_future_leakage(df)
    X, y, groups, cols = matrix_xy(df)
    peak = morning_peak_mask(df)
    uniq = np.unique(groups)
    n_splits = min(n_splits, max(2, len(uniq)))

    prototypes: dict[str, Any] = {
        "ridge": Ridge(alpha=1.0),
        "elasticnet": ElasticNet(alpha=0.05, l1_ratio=0.3, max_iter=5000, random_state=21),
        "rf": RandomForestRegressor(
            n_estimators=120, max_depth=12, min_samples_leaf=2, n_jobs=-1, random_state=21
        ),
        "extra_trees": ExtraTreesRegressor(
            n_estimators=200,
            max_depth=12,
            min_samples_split=5,
            min_samples_leaf=1,
            max_features=0.8,
            bootstrap=False,
            n_jobs=-1,
            random_state=21,
        ),
        "hgb": HistGradientBoostingRegressor(
            max_depth=6, learning_rate=0.08, max_iter=250, random_state=21
        ),
    }

    cv_scores: dict[str, list[dict[str, float]]] = {k: [] for k in prototypes}
    pers_scores: list[dict[str, float]] = []
    lag_i = cols.index("facility_kw_lag1")

    gkf = GroupKFold(n_splits=n_splits)
    for tr, te in gkf.split(X, y, groups):
        y_te = y[te]
        p_te = peak[te]
        pers_scores.append(_metrics(y_te, X[te, lag_i], p_te))
        for name, proto in prototypes.items():
            m = proto.__class__(**proto.get_params())
            m.fit(X[tr], y[tr])
            cv_scores[name].append(_metrics(y_te, m.predict(X[te]), p_te))

    summary = {"persistence": _mean_scores(pers_scores)}
    for name in prototypes:
        summary[name] = _mean_scores(cv_scores[name])

    champ_name = min(
        prototypes.keys(),
        key=lambda n: summary[n]["mae_peak_05_09"],
    )
    beat = summary[champ_name]["mae_peak_05_09"] < summary["persistence"]["mae_peak_05_09"]

    champ = prototypes[champ_name].__class__(**prototypes[champ_name].get_params())
    champ.fit(X, y)

    leaderboard = [
        {"family": n, "oof_metrics": summary[n], "best_params": prototypes[n].get_params()}
        for n in prototypes
    ]
    leaderboard.sort(key=lambda e: e["oof_metrics"]["mae_peak_05_09"])

    return {
        "model": champ,
        "champion": champ_name,
        "feature_cols": cols,
        "cv": summary,
        "leaderboard": leaderboard,
        "beat_persistence_peak": beat,
        "n_rows": int(len(df)),
        "n_days": int(df["day"].nunique()),
        "n_splits": n_splits,
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
    args = ap.parse_args(argv)

    pq = args.parquet or bootstrap_parquet_path()
    paths = artifact_paths(args.out_dir)
    if not pq.is_file():
        print(f"missing {pq} — run build_bootstrap_dataset.py first", file=sys.stderr)
        return 2

    df = pd.read_parquet(pq)
    result = bake_off(df, n_splits=args.n_splits)

    joblib.dump(
        {
            "model": result["model"],
            "feature_cols": result["feature_cols"],
            "champion": result["champion"],
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
        "cv_metrics": result["cv"],
        "beat_persistence_peak": result["beat_persistence_peak"],
        "peak_window": "HE_05_09_local",
        "n_rows": result["n_rows"],
        "n_days": result["n_days"],
        "training_parquet": str(pq),
        "training_source": "BAS_BOOTSTRAP_PROXY",
        "sklearn_version": __import__("sklearn").__version__,
        "created_utc": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "honesty": (
            "Screening surrogate for 6-Area HP occupancy / preheat DSM. "
            "Trained on BAS_BOOTSTRAP_PROXY (physics-ish scenario tags), not EnergyPlus. "
            "Replace parquet with E+ DM farm before APPROVED. Not tariff-grade."
        ),
        "feature_cols": FEATURE_COLS,
    }
    paths["card"].write_text(json.dumps(card, indent=2) + "\n", encoding="utf-8")

    champ_summary = {
        "champion": result["champion"],
        "beat_persistence_peak": result["beat_persistence_peak"],
        "cv": result["cv"],
        "leaderboard": [
            {"family": e["family"], "oof_metrics": e["oof_metrics"]} for e in result["leaderboard"]
        ],
    }
    paths["champion_summary"].write_text(
        json.dumps(champ_summary, indent=2) + "\n", encoding="utf-8"
    )

    print(
        json.dumps(
            {
                "model_id": card["model_id"],
                "status": card["status"],
                "champion": card["champion"],
                "beat_persistence_peak": card["beat_persistence_peak"],
                "cv_metrics": {
                    k: result["cv"][k]
                    for k in ("persistence", result["champion"])
                    if k in result["cv"]
                },
                "artifact": card["artifact"],
            },
            indent=2,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

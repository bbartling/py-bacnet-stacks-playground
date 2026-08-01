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
from sklearn.ensemble import (
    ExtraTreesRegressor,
    GradientBoostingRegressor,
    HistGradientBoostingRegressor,
    RandomForestRegressor,
    StackingRegressor,
    VotingRegressor,
)
from sklearn.linear_model import ElasticNet, Ridge
from sklearn.metrics import mean_absolute_error, mean_squared_error, make_scorer
from sklearn.model_selection import GroupKFold, RandomizedSearchCV

_ML = Path(__file__).resolve().parent
if str(_ML) not in sys.path:
    sys.path.insert(0, str(_ML))

from feature_compile_dm import (  # noqa: E402
    FEATURE_COLS,
    TARGET_COLS,
    available_target_cols,
    compile_features,
    matrix_xy,
    peak_mask,
)
from train_demand_hourly import load_farm_frame, _workspace  # noqa: E402
from artifact_paths import (  # noqa: E402
    MODEL_STEM_V1,
    MODEL_STEM_V2,
    default_model_dir,
    mirror_to_wattlab,
)


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
    "extra_trees": (
        ExtraTreesRegressor(random_state=21, n_jobs=-1),
        {
            "n_estimators": [100, 200, 300, 400],
            "max_depth": [6, 10, 16, None],
            "min_samples_leaf": [1, 2, 4, 8],
            "min_samples_split": [2, 5, 10],
            "max_features": ["sqrt", "log2", 0.5, 0.8, 1.0],
            "max_leaf_nodes": [None, 64, 128, 256],
            "bootstrap": [False, True],
        },
    ),
    "gbr": (
        GradientBoostingRegressor(random_state=21),
        {
            "learning_rate": [0.03, 0.05, 0.08, 0.12],
            "max_depth": [2, 3, 5],
            "n_estimators": [100, 200, 300],
            "min_samples_leaf": [10, 20, 40],
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


def _clone_fit_params(est: Any, params: dict[str, Any], *, random_state: int = 21) -> Any:
    m = est.__class__(**params)
    if "random_state" in m.get_params():
        m.set_params(random_state=random_state)
    if "n_jobs" in m.get_params():
        m.set_params(n_jobs=-1)
    return m


def _oof_predict(
    est_factory,
    X: np.ndarray,
    y: np.ndarray,
    groups: np.ndarray,
    gkf: GroupKFold,
) -> np.ndarray:
    oof = np.zeros_like(y, dtype=float)
    for tr, te in gkf.split(X, y, groups):
        m = est_factory()
        m.fit(X[tr], y[tr])
        oof[te] = m.predict(X[te])
    return oof


def tune(
    df: pd.DataFrame,
    *,
    n_splits: int = 5,
    n_iter: int = 40,
    random_state: int = 21,
    champion_refine_iter: int = 60,
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
    tuned: dict[str, Any] = {}
    tuned_params: dict[str, dict[str, Any]] = {}

    for name, (proto, space) in SEARCH_SPACES.items():
        n_combos = 1
        for v in space.values():
            n_combos *= max(len(v), 1)
        # ExtraTrees gets a denser search after expanding the space
        family_iter = int(n_iter * 1.5) if name == "extra_trees" else n_iter
        iters = min(family_iter, n_combos)
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
        tuned[name] = search.best_estimator_
        tuned_params[name] = dict(search.best_params_)
        oof = _oof_predict(
            lambda p=dict(search.best_params_), e=search.best_estimator_: _clone_fit_params(
                e, p, random_state=random_state
            ),
            X,
            y,
            groups,
            gkf,
        )
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

    # Ensembles from tuned tree/boosting families
    tree_keys = [k for k in ("hgb", "gbr", "rf", "extra_trees") if k in tuned]
    if len(tree_keys) >= 2:
        print(f"ensemble voting over {tree_keys} …", flush=True)
        vote_estimators = [(k, tuned[k]) for k in tree_keys]
        vote = VotingRegressor(estimators=vote_estimators)
        oof_vote = _oof_predict(lambda: VotingRegressor(
            estimators=[(k, _clone_fit_params(tuned[k], tuned_params[k], random_state=random_state)) for k in tree_keys]
        ), X, y, groups, gkf)
        met_v = _metrics(y, oof_vote, peak)
        leaderboard.append(
            {
                "family": "voting",
                "best_params": {"members": tree_keys, "weights": "uniform"},
                "cv_neg_mae": -met_v["mae"],
                "oof_metrics": met_v,
                "beat_persistence_peak": met_v["mae_peak_14_16"] < persistence["mae_peak_14_16"],
            }
        )
        print(f"  voting peak_mae={met_v['mae_peak_14_16']:.3f}", flush=True)
        tuned["voting"] = vote
        tuned_params["voting"] = {"members": tree_keys}

        print(f"ensemble stacking over {tree_keys} (Ridge meta) …", flush=True)

        def _make_stack():
            return StackingRegressor(
                estimators=[
                    (k, _clone_fit_params(tuned[k], tuned_params[k], random_state=random_state))
                    for k in tree_keys
                ],
                final_estimator=Ridge(alpha=1.0),
                cv=min(3, n_splits),
                n_jobs=-1,
            )

        oof_stack = _oof_predict(_make_stack, X, y, groups, gkf)
        met_s = _metrics(y, oof_stack, peak)
        leaderboard.append(
            {
                "family": "stacking",
                "best_params": {"members": tree_keys, "final_estimator": "Ridge(alpha=1.0)"},
                "cv_neg_mae": -met_s["mae"],
                "oof_metrics": met_s,
                "beat_persistence_peak": met_s["mae_peak_14_16"] < persistence["mae_peak_14_16"],
            }
        )
        print(f"  stacking peak_mae={met_s['mae_peak_14_16']:.3f}", flush=True)
        tuned["stacking"] = _make_stack()
        tuned_params["stacking"] = {"members": tree_keys, "final_estimator": "Ridge(alpha=1.0)"}

    # Pick champion by peak OOF MAE
    best_name = None
    best_peak = float("inf")
    for e in leaderboard:
        pk = e["oof_metrics"]["mae_peak_14_16"]
        if pk < best_peak:
            best_peak = pk
            best_name = e["family"]
    assert best_name is not None

    # Extra hyperparam pass on the best *single-model* family (not ensemble)
    single_families = set(SEARCH_SPACES.keys())
    refine_family = best_name if best_name in single_families else min(
        (e for e in leaderboard if e["family"] in single_families),
        key=lambda e: e["oof_metrics"]["mae_peak_14_16"],
    )["family"]

    if refine_family in SEARCH_SPACES and champion_refine_iter > 0:
        proto, space = SEARCH_SPACES[refine_family]
        n_combos = 1
        for v in space.values():
            n_combos *= max(len(v), 1)
        iters = min(champion_refine_iter, n_combos)
        print(
            f"champion refine: {refine_family} RandomizedSearchCV n_iter={iters} …",
            flush=True,
        )
        search = RandomizedSearchCV(
            proto,
            space,
            n_iter=iters,
            scoring=mae_scorer,
            cv=gkf,
            random_state=random_state + 7,
            n_jobs=-1,
            refit=True,
        )
        search.fit(X, y, groups=groups)
        oof = _oof_predict(
            lambda: _clone_fit_params(search.best_estimator_, search.best_params_, random_state=random_state),
            X,
            y,
            groups,
            gkf,
        )
        met = _metrics(y, oof, peak)
        # Replace / update leaderboard entry for this family
        leaderboard = [e for e in leaderboard if e["family"] != refine_family]
        leaderboard.append(
            {
                "family": refine_family,
                "best_params": search.best_params_,
                "cv_neg_mae": float(search.best_score_),
                "oof_metrics": met,
                "beat_persistence_peak": met["mae_peak_14_16"] < persistence["mae_peak_14_16"],
                "refined": True,
            }
        )
        tuned[refine_family] = search.best_estimator_
        tuned_params[refine_family] = dict(search.best_params_)
        print(
            f"  refined {refine_family} peak_mae={met['mae_peak_14_16']:.3f} params={search.best_params_}",
            flush=True,
        )
        # Rebuild voting/stacking with refined member if present
        if "voting" in tuned and refine_family in tree_keys:
            tree_keys = [k for k in ("hgb", "gbr", "rf", "extra_trees") if k in tuned]
            oof_vote = _oof_predict(lambda: VotingRegressor(
                estimators=[(k, _clone_fit_params(tuned[k], tuned_params[k], random_state=random_state)) for k in tree_keys]
            ), X, y, groups, gkf)
            met_v = _metrics(y, oof_vote, peak)
            leaderboard = [e for e in leaderboard if e["family"] != "voting"]
            leaderboard.append(
                {
                    "family": "voting",
                    "best_params": {"members": tree_keys, "weights": "uniform"},
                    "cv_neg_mae": -met_v["mae"],
                    "oof_metrics": met_v,
                    "beat_persistence_peak": met_v["mae_peak_14_16"] < persistence["mae_peak_14_16"],
                    "refined": True,
                }
            )
            tuned["voting"] = VotingRegressor(estimators=[(k, tuned[k]) for k in tree_keys])
            print(f"  re-eval voting peak_mae={met_v['mae_peak_14_16']:.3f}", flush=True)

            def _make_stack2():
                return StackingRegressor(
                    estimators=[
                        (k, _clone_fit_params(tuned[k], tuned_params[k], random_state=random_state))
                        for k in tree_keys
                    ],
                    final_estimator=Ridge(alpha=1.0),
                    cv=min(3, n_splits),
                    n_jobs=-1,
                )

            oof_stack = _oof_predict(_make_stack2, X, y, groups, gkf)
            met_s = _metrics(y, oof_stack, peak)
            leaderboard = [e for e in leaderboard if e["family"] != "stacking"]
            leaderboard.append(
                {
                    "family": "stacking",
                    "best_params": {"members": tree_keys, "final_estimator": "Ridge(alpha=1.0)"},
                    "cv_neg_mae": -met_s["mae"],
                    "oof_metrics": met_s,
                    "beat_persistence_peak": met_s["mae_peak_14_16"] < persistence["mae_peak_14_16"],
                    "refined": True,
                }
            )
            tuned["stacking"] = _make_stack2()
            print(f"  re-eval stacking peak_mae={met_s['mae_peak_14_16']:.3f}", flush=True)

    # Final champion pick
    best_name = None
    best_peak = float("inf")
    for e in leaderboard:
        pk = e["oof_metrics"]["mae_peak_14_16"]
        if pk < best_peak:
            best_peak = pk
            best_name = e["family"]
    assert best_name is not None
    best_params = next(e["best_params"] for e in leaderboard if e["family"] == best_name)

    # Fit champion on all data
    if best_name in ("voting", "stacking"):
        champ = tuned[best_name]
        champ.fit(X, y)
    else:
        champ = _clone_fit_params(tuned[best_name], tuned_params[best_name], random_state=random_state)
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
        "refined_family": refine_family,
    }


def _metrics_multi(
    y_true: np.ndarray,
    y_pred: np.ndarray,
    target_names: list[str],
    peak: np.ndarray | None = None,
) -> dict[str, Any]:
    """Per-target MAE/RMSE plus facility_kw peak MAE (index 0 assumed facility)."""
    per: dict[str, dict[str, float]] = {}
    for i, name in enumerate(target_names):
        yt = y_true[:, i]
        yp = y_pred[:, i]
        per[name] = {
            "mae": float(mean_absolute_error(yt, yp)),
            "rmse": float(np.sqrt(mean_squared_error(yt, yp))),
        }
    out: dict[str, Any] = {"per_target": per, "mae_mean": float(np.mean([v["mae"] for v in per.values()]))}
    # facility_kw peak for DR honesty
    if peak is not None and peak.any() and "facility_kw" in target_names:
        i = target_names.index("facility_kw")
        out["mae_peak_14_16_facility_kw"] = float(
            mean_absolute_error(y_true[peak, i], y_pred[peak, i])
        )
    elif "facility_kw" in target_names:
        out["mae_peak_14_16_facility_kw"] = per["facility_kw"]["mae"]
    return out


def tune_multitarget(
    df: pd.DataFrame,
    *,
    n_splits: int = 3,
    n_iter: int = 24,
    random_state: int = 21,
    target_cols: list[str] | None = None,
) -> dict[str, Any]:
    """ExtraTrees multi-output surrogate over twin I/O TARGET_COLS."""
    targets = target_cols or available_target_cols(df)
    if "facility_kw" not in targets:
        raise ValueError("facility_kw required in multi-target train")
    # Keep canonical order
    targets = [c for c in TARGET_COLS if c in targets]
    work = df.dropna(subset=targets).copy()
    if len(work) < 48:
        raise ValueError(f"Too few complete twin I/O rows after dropna: {len(work)}")

    X, y, groups, cols = matrix_xy(work, multi_target=True, target_cols=targets)
    peak = peak_mask(work)
    uniq = np.unique(groups)
    n_splits = min(n_splits, max(2, len(uniq)))
    gkf = GroupKFold(n_splits=n_splits)
    mae_scorer = make_scorer(mean_absolute_error, greater_is_better=False)

    # Persistence baseline on facility_kw only
    lag_i = cols.index("facility_kw_lag1")
    fac_i = targets.index("facility_kw")
    pers_fold = []
    for _, te in gkf.split(X, y, groups):
        pers_fold.append(
            {
                "mae": float(mean_absolute_error(y[te, fac_i], X[te, lag_i])),
                "rmse": float(np.sqrt(mean_squared_error(y[te, fac_i], X[te, lag_i]))),
                "mae_peak_14_16": float(
                    mean_absolute_error(y[te, fac_i][peak[te]], X[te, lag_i][peak[te]])
                )
                if peak[te].any()
                else float(mean_absolute_error(y[te, fac_i], X[te, lag_i])),
            }
        )
    persistence = {k: float(np.mean([f[k] for f in pers_fold])) for k in pers_fold[0]}

    proto, space = SEARCH_SPACES["extra_trees"]
    n_combos = 1
    for v in space.values():
        n_combos *= max(len(v), 1)
    iters = min(n_iter, n_combos)
    print(f"tune multitarget ExtraTrees n_iter={iters} targets={len(targets)} …", flush=True)
    search = RandomizedSearchCV(
        ExtraTreesRegressor(random_state=random_state, n_jobs=-1),
        space,
        n_iter=iters,
        scoring=mae_scorer,
        cv=gkf,
        random_state=random_state,
        n_jobs=-1,
        refit=True,
    )
    search.fit(X, y, groups=groups)

    def _factory():
        return _clone_fit_params(search.best_estimator_, search.best_params_, random_state=random_state)

    oof = np.zeros_like(y, dtype=float)
    for tr, te in gkf.split(X, y, groups):
        m = _factory()
        m.fit(X[tr], y[tr])
        oof[te] = m.predict(X[te])
    met = _metrics_multi(y, oof, targets, peak)

    champ = _factory()
    champ.fit(X, y)
    return {
        "model": champ,
        "champion": "extra_trees",
        "best_params": dict(search.best_params_),
        "feature_cols": cols,
        "target_cols": targets,
        "persistence": persistence,
        "oof_metrics": met,
        "beat_persistence_peak": met.get("mae_peak_14_16_facility_kw", 1e9)
        < persistence["mae_peak_14_16"],
        "n_rows": int(len(work)),
        "n_days": int(work["day"].nunique()),
        "n_splits": n_splits,
        "schema": "vibe21.dm_hourly_row.v2",
    }


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--parquet", type=Path, default=None)
    ap.add_argument("--out-dir", type=Path, default=None, help="Default: flask_app/models/")
    ap.add_argument("--also-wattlab", action="store_true", help="Mirror artifacts to wattlab models/")
    ap.add_argument("--n-iter", type=int, default=40)
    ap.add_argument("--n-splits", type=int, default=5)
    ap.add_argument("--champion-refine-iter", type=int, default=60)
    ap.add_argument(
        "--multi-target",
        action="store_true",
        help="Train ExtraTrees multi-output twin I/O model → demand_hourly_v2",
    )
    args = ap.parse_args(argv)

    ws = _workspace()
    pq = args.parquet or (ws / "reports" / "dm_hourly_farm" / "dm_hourly_rows.parquet")
    out_dir = args.out_dir or default_model_dir()
    out_dir.mkdir(parents=True, exist_ok=True)
    if not pq.is_file():
        print(f"missing {pq}", file=sys.stderr)
        return 2

    df = load_farm_frame(pq)
    src = None
    fs = pq.parent / "farm_summary.json"
    farm_summary = {}
    if fs.is_file():
        farm_summary = json.loads(fs.read_text(encoding="utf-8"))
        src = farm_summary.get("source")
        print(f"training_source={src} profile={farm_summary.get('profile')}", flush=True)

    if args.multi_target:
        result = tune_multitarget(df, n_splits=min(args.n_splits, 3), n_iter=max(12, args.n_iter // 2))
        stem = MODEL_STEM_V2
        artifact = out_dir / f"{stem}.joblib"
        joblib.dump(
            {
                "model": result["model"],
                "feature_cols": result["feature_cols"],
                "target_cols": result["target_cols"],
                "champion": result["champion"],
                "best_params": result["best_params"],
                "schema": result["schema"],
                "multi_target": True,
            },
            artifact,
        )
        sha = hashlib.sha256(artifact.read_bytes()).hexdigest()
        profile = farm_summary.get("profile", "unknown")
        tuning = {
            "mode": "multi_target",
            "persistence_facility_kw": result["persistence"],
            "oof_metrics": result["oof_metrics"],
            "champion": result["champion"],
            "best_params": result["best_params"],
            "beat_persistence_peak": result["beat_persistence_peak"],
            "n_rows": result["n_rows"],
            "n_days": result["n_days"],
            "feature_cols": FEATURE_COLS,
            "target_cols": result["target_cols"],
        }
        (out_dir / f"{stem}_tuning.json").write_text(json.dumps(tuning, indent=2) + "\n", encoding="utf-8")
        card = {
            "schema_version": "vibe21.model_registry.v1",
            "model_id": stem,
            "family": "OPERATIONAL_DEMAND_MULTITARGET",
            "artifact": str(artifact),
            "artifact_sha256": sha,
            "status": "CANDIDATE",
            "farm_profile": profile,
            "targets": result["target_cols"],
            "champion": result["champion"],
            "best_params": result["best_params"],
            "feature_cols": FEATURE_COLS,
            "cv_metrics": result["oof_metrics"],
            "beat_persistence_peak": result["beat_persistence_peak"],
            "n_rows": result["n_rows"],
            "n_days": result["n_days"],
            "training_parquet": str(pq),
            "training_source": src or "unknown",
            "engine": farm_summary.get("engine"),
            "sklearn_version": __import__("sklearn").__version__,
            "created_utc": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
            "honesty": (
                f"Multi-target ExtraTrees twin I/O surrogate (farm_profile={profile}). "
                "CANDIDATE / ENERGYPLUS_SIMULATED until BAS-validated. "
                "Pilot is thinner than the 40-day champion — re-farm full for production."
            ),
            "unity_contract": {
                "inputs": ["oat_c", "rh_pct", "hour_ending", "strategy_id", "action knobs"],
                "output": "facility_kw + twin_io dict",
            },
        }
        (out_dir / f"{stem}_model_card.json").write_text(json.dumps(card, indent=2) + "\n", encoding="utf-8")
        if args.also_wattlab:
            mirror_to_wattlab(out_dir, stem=stem)
        print(
            json.dumps(
                {
                    "model_id": stem,
                    "champion": result["champion"],
                    "n_targets": len(result["target_cols"]),
                    "mae_peak_facility": result["oof_metrics"].get("mae_peak_14_16_facility_kw"),
                    "mae_mean": result["oof_metrics"].get("mae_mean"),
                    "artifact": str(artifact),
                    "farm_profile": profile,
                },
                indent=2,
            )
        )
        return 0

    result = tune(
        df,
        n_splits=args.n_splits,
        n_iter=args.n_iter,
        champion_refine_iter=args.champion_refine_iter,
    )
    stem = MODEL_STEM_V1
    artifact = out_dir / f"{stem}.joblib"
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
    (out_dir / f"{stem}_tuning.json").write_text(json.dumps(tuning, indent=2) + "\n", encoding="utf-8")

    card = {
        "schema_version": "vibe21.model_registry.v1",
        "model_id": stem,
        "family": "OPERATIONAL_DEMAND",
        "artifact": str(artifact),
        "artifact_sha256": sha,
        "status": "CANDIDATE",
        "targets": ["facility_kw"],
        "champion": result["champion"],
        "best_params": result["best_params"],
        "refined_family": result.get("refined_family"),
        "feature_cols": FEATURE_COLS,
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
    (out_dir / f"{stem}_model_card.json").write_text(json.dumps(card, indent=2) + "\n", encoding="utf-8")
    if args.also_wattlab:
        mirror_to_wattlab(out_dir, stem=stem)
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

#!/usr/bin/env python
"""Train 7-output real BAS 15-min baseline (GB / ExtraTrees / RF) with nested CV.

Exports ``real_baseline_15min_v1`` artifacts — not desktop ship stem until hybrid promote.
Honesty label: HYBRID_SCREENING (component A — measured only).
"""
from __future__ import annotations

import argparse
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
    RandomForestRegressor,
)
from sklearn.metrics import mean_absolute_error, mean_squared_error
from sklearn.model_selection import GroupKFold, ParameterSampler
from sklearn.multioutput import MultiOutputRegressor

_ML = Path(__file__).resolve().parent
_APP = _ML.parent
if str(_ML) not in sys.path:
    sys.path.insert(0, str(_ML))
if str(_APP) not in sys.path:
    sys.path.insert(0, str(_APP))

from feature_compile_15min import (  # noqa: E402
    FEATURE_COLS_15MIN_MT,
    ensure_strategy_onehots,
    matrix_xy_15min_multi,
    morning_peak_mask_15min,
    recursive_rollout_day,
)
from feature_compile_heating_dsm import TARGET_COLS  # noqa: E402
from lakeside.paths import site_root  # noqa: E402

STEM = "real_baseline_15min_v1"
HONESTY = "HYBRID_SCREENING"


def _metrics_multi(y_true: np.ndarray, y_pred: np.ndarray, peak: np.ndarray | None = None) -> dict[str, Any]:
    out: dict[str, Any] = {}
    for i, name in enumerate(TARGET_COLS):
        yt, yp = y_true[:, i], y_pred[:, i]
        out[name] = {
            "mae": float(mean_absolute_error(yt, yp)),
            "rmse": float(np.sqrt(mean_squared_error(yt, yp))),
        }
        if peak is not None and peak.any():
            out[name]["mae_peak_05_09"] = float(mean_absolute_error(yt[peak], yp[peak]))
            out[name]["rmse_peak_05_09"] = float(
                np.sqrt(mean_squared_error(yt[peak], yp[peak]))
            )
    out["facility_kw_mae"] = out["facility_kw"]["mae"]
    out["facility_kw_mae_peak_05_09"] = out["facility_kw"].get(
        "mae_peak_05_09", out["facility_kw"]["mae"]
    )
    out["zone_temp_mae_mean"] = float(
        np.mean([out[c]["mae"] for c in TARGET_COLS[1:]])
    )
    return out


def _clone_multi(est: MultiOutputRegressor) -> MultiOutputRegressor:
    return MultiOutputRegressor(est.estimator.__class__(**est.estimator.get_params()), n_jobs=-1)


def _fit_family(
    name: str,
    X: np.ndarray,
    Y: np.ndarray,
    groups: np.ndarray,
    *,
    n_iter: int,
    inner_splits: int,
    rng: np.random.RandomState,
) -> tuple[MultiOutputRegressor, dict[str, Any], float]:
    spaces: dict[str, dict[str, list]] = {
        "gradient_boosting": {
            "n_estimators": [80, 120, 160, 220],
            "learning_rate": [0.03, 0.05, 0.08, 0.12],
            "max_depth": [2, 3, 4, 5],
            "min_samples_leaf": [2, 4, 8, 16],
            "subsample": [0.7, 0.85, 1.0],
        },
        "extra_trees": {
            "n_estimators": [150, 250, 400],
            "max_depth": [12, 20, 28, None],
            "min_samples_leaf": [1, 2, 4],
            "max_features": [0.5, 0.8, "sqrt"],
        },
        "random_forest": {
            "n_estimators": [150, 250, 400],
            "max_depth": [12, 20, 28, None],
            "min_samples_leaf": [1, 2, 4],
            "max_features": [0.5, 0.8, "sqrt"],
        },
    }
    proto = {
        "gradient_boosting": GradientBoostingRegressor(random_state=21),
        "extra_trees": ExtraTreesRegressor(random_state=21, n_jobs=1),
        "random_forest": RandomForestRegressor(random_state=21, n_jobs=1),
    }[name]
    space = spaces[name]
    uniq = np.unique(groups)
    n_inner = min(inner_splits, max(2, len(uniq)))
    gkf = GroupKFold(n_splits=n_inner)
    sampler = list(ParameterSampler(space, n_iter=n_iter, random_state=rng))
    best_score = float("inf")
    best_params: dict[str, Any] = {}
    for params in sampler:
        scores = []
        for tr, te in gkf.split(X, Y, groups):
            est = MultiOutputRegressor(proto.__class__(**{**proto.get_params(), **params}), n_jobs=-1)
            est.fit(X[tr], Y[tr])
            pred = est.predict(X[te])
            scores.append(mean_absolute_error(Y[te][:, 0], pred[:, 0]))
        m = float(np.mean(scores))
        if m < best_score:
            best_score = m
            best_params = dict(params)
    final = MultiOutputRegressor(proto.__class__(**{**proto.get_params(), **best_params}), n_jobs=-1)
    final.fit(X, Y)
    return final, best_params, best_score


def nested_bake_off(
    df: pd.DataFrame,
    *,
    outer_splits: int = 3,
    inner_splits: int = 2,
    n_iter: int = 8,
    families: list[str] | None = None,
) -> dict[str, Any]:
    families = families or ["gradient_boosting", "extra_trees", "random_forest"]
    df = ensure_strategy_onehots(df)
    X, Y, groups, cols, tcols, feat = matrix_xy_15min_multi(df)
    peak = morning_peak_mask_15min(feat)
    uniq = np.unique(groups)
    n_outer = min(outer_splits, max(2, len(uniq)))
    gkf_outer = GroupKFold(n_splits=n_outer)
    rng = np.random.RandomState(21)

    oof_tf: dict[str, list[dict]] = {f: [] for f in families}
    oof_rec: dict[str, list[dict]] = {f: [] for f in families}
    best_params_outer: dict[str, list[dict]] = {f: [] for f in families}

    for fold, (tr, te) in enumerate(gkf_outer.split(X, Y, groups)):
        print(f"outer fold {fold + 1}/{n_outer} train={len(tr)} test={len(te)}", flush=True)
        Xtr, Ytr, gtr = X[tr], Y[tr], groups[tr]
        Xte, Yte = X[te], Y[te]
        peak_te = peak[te]
        day_te = feat.iloc[te]
        for fam in families:
            model, params, _ = _fit_family(
                fam, Xtr, Ytr, gtr, n_iter=n_iter, inner_splits=inner_splits, rng=rng
            )
            best_params_outer[fam].append(params)
            pred_tf = model.predict(Xte)
            oof_tf[fam].append(_metrics_multi(Yte, pred_tf, peak_te))
            # recursive by day
            rec_preds = []
            rec_true = []
            rec_peak = []
            for day, sub in day_te.groupby("day"):
                idx = sub.index.to_numpy()
                # map to local positions within te
                local = np.where(np.isin(te, idx))[0]
                if len(local) < 80:
                    continue
                sub_sorted = sub.sort_values("step_15")
                yp = recursive_rollout_day(model, sub_sorted, cols, tcols)
                yt = sub_sorted[TARGET_COLS].to_numpy(dtype=float)
                pk = morning_peak_mask_15min(sub_sorted)
                rec_preds.append(yp)
                rec_true.append(yt)
                rec_peak.append(pk)
            if rec_preds:
                yt = np.vstack(rec_true)
                yp = np.vstack(rec_preds)
                pk = np.concatenate(rec_peak)
                oof_rec[fam].append(_metrics_multi(yt, yp, pk))
            print(
                f"  {fam} TF peak MAE={oof_tf[fam][-1]['facility_kw_mae_peak_05_09']:.3f}",
                flush=True,
            )

    def _mean(scores: list[dict]) -> dict:
        if not scores:
            return {}
        keys = scores[0].keys()
        out = {}
        for k in keys:
            if isinstance(scores[0][k], dict):
                out[k] = {
                    kk: float(np.mean([s[k][kk] for s in scores if kk in s[k]]))
                    for kk in scores[0][k]
                }
            else:
                out[k] = float(np.mean([s[k] for s in scores]))
        return out

    summary_tf = {f: _mean(oof_tf[f]) for f in families}
    summary_rec = {f: _mean(oof_rec[f]) for f in families}
    champ = min(families, key=lambda f: summary_tf[f].get("facility_kw_mae_peak_05_09", 1e9))

    # refit champion on all data with median-ish last params
    last_params = best_params_outer[champ][-1] if best_params_outer[champ] else {}
    proto_map = {
        "gradient_boosting": GradientBoostingRegressor(random_state=21),
        "extra_trees": ExtraTreesRegressor(random_state=21, n_jobs=1),
        "random_forest": RandomForestRegressor(random_state=21, n_jobs=1),
    }
    base = proto_map[champ]
    champ_model = MultiOutputRegressor(base.__class__(**{**base.get_params(), **last_params}), n_jobs=-1)
    champ_model.fit(X, Y)

    # also fit all families full-data for export choice
    tuned: dict[str, Any] = {champ: champ_model}
    for fam in families:
        if fam == champ:
            continue
        p = best_params_outer[fam][-1] if best_params_outer[fam] else {}
        b = proto_map[fam]
        m = MultiOutputRegressor(b.__class__(**{**b.get_params(), **p}), n_jobs=-1)
        m.fit(X, Y)
        tuned[fam] = m

    return {
        "model": champ_model,
        "tuned_models": tuned,
        "champion": champ,
        "best_params": last_params,
        "best_params_by_family": {f: best_params_outer[f][-1] if best_params_outer[f] else {} for f in families},
        "feature_cols": cols,
        "target_cols": tcols,
        "cv_teacher_forced": summary_tf,
        "cv_recursive_96": summary_rec,
        "n_rows": int(len(feat)),
        "n_days": int(feat["day"].nunique()),
        "outer_splits": n_outer,
        "n_iter": n_iter,
        "X": X,
        "Y": Y,
        "groups": groups,
        "peak": peak,
        "frame": feat,
    }


def export_onnx_multi(model: MultiOutputRegressor, n_features: int, path: Path) -> None:
    """Export multi-output sklearn model; output name ``outputs`` [batch, 7]."""
    from skl2onnx import convert_sklearn
    from skl2onnx.common.data_types import FloatTensorType

    onx = convert_sklearn(
        model,
        initial_types=[("features", FloatTensorType([None, n_features]))],
        target_opset=12,
    )
    # rename first output
    if onx.graph.output:
        old = onx.graph.output[0].name
        new = "outputs"
        if old != new:
            for node in onx.graph.node:
                for i, o in enumerate(list(node.output)):
                    if o == old:
                        node.output[i] = new
            onx.graph.output[0].name = new
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(onx.SerializeToString())


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--parquet", type=Path, default=None)
    ap.add_argument("--out-dir", type=Path, default=None)
    ap.add_argument("--outer-splits", type=int, default=3)
    ap.add_argument("--inner-splits", type=int, default=2)
    ap.add_argument("--n-iter", type=int, default=6)
    ap.add_argument("--max-days", type=int, default=None, help="optional day subsample for speed")
    ap.add_argument("--winter-only", action="store_true")
    args = ap.parse_args(argv)

    site = site_root()
    pq = args.parquet or (site / "ml" / "artifacts" / "real_baseline_15min_v1.parquet")
    if not pq.is_file():
        raise FileNotFoundError(f"missing {pq} — run scripts/build_real_15min_store.py")
    df = pd.read_parquet(pq)
    if (df.get("provenance") is not None) and not (df["provenance"] == "REAL_BAS_15MIN").all():
        raise ValueError("refusing non-REAL_BAS store")
    if args.winter_only:
        df = df[df["month"].isin([11, 12, 1, 2, 3])].copy()
    if args.max_days:
        days = sorted(df["day"].unique())[: args.max_days]
        df = df[df["day"].isin(days)].copy()

    out_dir = args.out_dir or (_ML / "artifacts")
    out_dir.mkdir(parents=True, exist_ok=True)

    result = nested_bake_off(
        df,
        outer_splits=args.outer_splits,
        inner_splits=args.inner_splits,
        n_iter=args.n_iter,
    )
    joblib_path = out_dir / f"{STEM}.joblib"
    onnx_path = out_dir / f"{STEM}.onnx"
    meta_path = out_dir / f"{STEM}_feature_meta.json"
    card_path = out_dir / f"{STEM}_model_card.json"

    joblib.dump(
        {
            "model": result["model"],
            "feature_cols": result["feature_cols"],
            "target_cols": result["target_cols"],
            "champion": result["champion"],
        },
        joblib_path,
    )
    try:
        export_onnx_multi(result["model"], len(result["feature_cols"]), onnx_path)
    except Exception as e:
        print(f"ONNX export failed: {e}", flush=True)

    meta = {
        "stem": STEM,
        "feature_cols": result["feature_cols"],
        "target_cols": result["target_cols"],
        "n_features": len(result["feature_cols"]),
        "n_outputs": len(result["target_cols"]),
        "scaler": "identity",
        "honesty": HONESTY,
        "component": "A_real_baseline",
        "resolution": "15min",
    }
    meta_path.write_text(json.dumps(meta, indent=2), encoding="utf-8")

    card = {
        "stem": STEM,
        "honesty": HONESTY,
        "provenance": "REAL_BAS_15MIN",
        "champion": result["champion"],
        "best_params": result["best_params"],
        "best_params_by_family": result["best_params_by_family"],
        "cv_teacher_forced": result["cv_teacher_forced"],
        "cv_recursive_96": result["cv_recursive_96"],
        "n_rows": result["n_rows"],
        "n_days": result["n_days"],
        "outer_splits": result["outer_splits"],
        "n_iter_inner": result["n_iter"],
        "built_at_utc": datetime.now(timezone.utc).isoformat(),
        "lag_init_policy": "measured_midnight_state_from_JSON_or_first_row",
    }
    card_path.write_text(json.dumps(card, indent=2), encoding="utf-8")
    print(json.dumps({"champion": result["champion"], "card": str(card_path)}, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

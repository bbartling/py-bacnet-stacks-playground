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


HORIZON_STEPS = (1, 4, 12, 24, 48, 96)


def heldout_recursive_metrics(
    model,
    feat_df: pd.DataFrame,
    te_idx: np.ndarray,
    cols: list[str],
    tcols: list[str],
    peak_mask: np.ndarray | None = None,
) -> dict[str, Any]:
    """Recursive 96-step metrics on held-out days (>=80 rows) in a test fold.

    Peak window = step_15 in [20, 36] (HE 05–09). Horizon keys are absolute
    error at 1-based step horizons {1,4,12,24,48,96} when the day is long enough.
    ``peak_mask`` is accepted for API symmetry with fold peak arrays; day peak
    is always derived from step_15 on the day frame.
    """
    del peak_mask  # day-level peak from step_15; fold mask unused
    day_te = feat_df.iloc[list(te_idx)]
    day_scores: list[dict[str, Any]] = []
    for _day, sub in day_te.groupby("day"):
        if len(sub) < 80:
            continue
        sub_sorted = sub.sort_values("step_15")
        yp = recursive_rollout_day(model, sub_sorted, cols, tcols)
        yt = sub_sorted[list(tcols)].to_numpy(dtype=float)
        n = len(sub_sorted)
        pk = morning_peak_mask_15min(sub_sorted)
        fac_err = np.abs(yp[:, 0] - yt[:, 0])
        score: dict[str, Any] = {
            "facility_kw_mae": float(np.mean(fac_err)),
            "facility_kw_rmse": float(np.sqrt(np.mean((yp[:, 0] - yt[:, 0]) ** 2))),
            "facility_kw_mae_peak_05_09": float(np.mean(fac_err[pk]))
            if np.any(pk)
            else float(np.mean(fac_err)),
            "zone_temp_mae_mean": float(np.mean(np.abs(yp[:, 1:] - yt[:, 1:]))),
            "n_steps": int(n),
        }
        for h in HORIZON_STEPS:
            idx = h - 1
            if 0 <= idx < n:
                score[f"horizon_mae_step_{h}"] = float(abs(yp[idx, 0] - yt[idx, 0]))
        day_scores.append(score)

    if not day_scores:
        return {}

    keys: set[str] = set()
    for s in day_scores:
        keys.update(s.keys())
    out: dict[str, Any] = {"n_heldout_days": int(len(day_scores))}
    for k in sorted(keys):
        vals = [s[k] for s in day_scores if k in s]
        if vals:
            out[k] = float(np.mean(vals))
    return out


def _mean_metric_dicts(scores: list[dict]) -> dict:
    """Mean nested metric dicts; skip empty entries."""
    scores = [s for s in scores if s]
    if not scores:
        return {}
    keys = scores[0].keys()
    out: dict[str, Any] = {}
    for k in keys:
        if isinstance(scores[0].get(k), dict):
            sub_keys = scores[0][k].keys()
            out[k] = {
                kk: float(np.mean([s[k][kk] for s in scores if k in s and kk in s[k]]))
                for kk in sub_keys
            }
        else:
            vals = [s[k] for s in scores if k in s and np.isfinite(s[k])]
            if vals:
                out[k] = float(np.mean(vals))
    return out


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
            "n_estimators": [80, 120, 160, 220, 300],
            "learning_rate": [0.02, 0.03, 0.05, 0.08, 0.12],
            "max_depth": [2, 3, 4, 5],
            "min_samples_leaf": [2, 4, 8, 16],
            "subsample": [0.7, 0.85, 1.0],
        },
        "extra_trees": {
            "n_estimators": [150, 250, 400, 500],
            "max_depth": [12, 20, 28, None],
            "min_samples_leaf": [1, 2, 4, 8],
            "max_features": [0.5, 0.8, "sqrt"],
        },
        "random_forest": {
            "n_estimators": [150, 250, 400, 500],
            "max_depth": [12, 20, 28, None],
            "min_samples_leaf": [1, 2, 4, 8],
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
        for fam in families:
            model, params, _ = _fit_family(
                fam, Xtr, Ytr, gtr, n_iter=n_iter, inner_splits=inner_splits, rng=rng
            )
            best_params_outer[fam].append(params)
            pred_tf = model.predict(Xte)
            oof_tf[fam].append(_metrics_multi(Yte, pred_tf, peak_te))
            rec = heldout_recursive_metrics(model, feat, te, cols, tcols, peak_te)
            if rec:
                oof_rec[fam].append(rec)
            print(
                f"  {fam} TF peak MAE={oof_tf[fam][-1]['facility_kw_mae_peak_05_09']:.3f}",
                flush=True,
            )

    summary_tf = {f: _mean_metric_dicts(oof_tf[f]) for f in families}
    summary_rec = {f: _mean_metric_dicts(oof_rec[f]) for f in families}
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
        "cv_recursive_96_heldout": summary_rec,
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


def lean_bake_off(
    df: pd.DataFrame,
    *,
    n_splits: int = 3,
) -> dict[str, Any]:
    """Fixed-hyperparam GroupKFold bake-off (notebook default — wall-clock honest)."""
    from feature_compile_15min import ensure_strategy_onehots

    df = ensure_strategy_onehots(df)
    X, Y, groups, cols, tcols, feat = matrix_xy_15min_multi(df)
    X = np.nan_to_num(X, nan=0.0, posinf=0.0, neginf=0.0)
    peak = morning_peak_mask_15min(feat)
    families = {
        "random_forest": RandomForestRegressor(
            n_estimators=120, max_depth=16, min_samples_leaf=2, random_state=21, n_jobs=-1
        ),
        "extra_trees": ExtraTreesRegressor(
            n_estimators=120, max_depth=16, min_samples_leaf=2, random_state=21, n_jobs=-1
        ),
        "gradient_boosting": GradientBoostingRegressor(
            n_estimators=80, max_depth=3, learning_rate=0.1, random_state=21
        ),
    }
    uniq = np.unique(groups)
    gkf = GroupKFold(n_splits=min(n_splits, max(2, len(uniq))))
    tf: dict[str, list] = {k: [] for k in families}
    rec_held: dict[str, list] = {k: [] for k in families}
    for fold, (tr, te) in enumerate(gkf.split(X, Y, groups)):
        print(f"lean fold {fold + 1}/{gkf.get_n_splits()}", flush=True)
        for name, proto in families.items():
            m = MultiOutputRegressor(proto.__class__(**proto.get_params()), n_jobs=1)
            m.fit(X[tr], Y[tr])
            pred = m.predict(X[te])
            tf[name].append(_metrics_multi(Y[te], pred, peak[te]))
            held = heldout_recursive_metrics(m, feat, te, cols, tcols, peak[te])
            if held:
                rec_held[name].append(held)
            print(f"  {name} peak MAE={tf[name][-1]['facility_kw_mae_peak_05_09']:.3f}", flush=True)

    summary = {f: _mean_metric_dicts(v) for f, v in tf.items()}
    summary_rec = {f: _mean_metric_dicts(v) for f, v in rec_held.items()}
    champ = min(families, key=lambda n: summary[n]["facility_kw_mae_peak_05_09"])
    proto = families[champ]
    model = MultiOutputRegressor(proto.__class__(**proto.get_params()), n_jobs=1)
    model.fit(X, Y)
    # debug: in-sample first-day recursive (not a held-out claim)
    sample_day = str(feat["day"].iloc[0])
    sub = feat[feat["day"] == sample_day].sort_values("step_15")
    yp = recursive_rollout_day(model, sub, cols, tcols)
    yt = sub[TARGET_COLS].to_numpy(dtype=float)
    debug_in_sample = {
        "sample_day": sample_day,
        "facility_kw_mae": float(np.mean(np.abs(yp[:, 0] - yt[:, 0]))),
        "zone_temp_mae_mean": float(np.mean(np.abs(yp[:, 1:] - yt[:, 1:]))),
        "note": "in_sample_first_day_not_heldout",
    }
    return {
        "model": model,
        "champion": champ,
        "best_params": proto.get_params(),
        "best_params_by_family": {k: v.get_params() for k, v in families.items()},
        "feature_cols": cols,
        "target_cols": tcols,
        "cv_teacher_forced": summary,
        "cv_recursive_96_heldout": summary_rec,
        "debug_in_sample_recursive": {champ: debug_in_sample},
        "n_rows": int(len(feat)),
        "n_days": int(feat["day"].nunique()),
        "outer_splits": int(gkf.get_n_splits()),
        "n_iter": 0,
        "frame": feat,
        "X": X,
        "Y": Y,
        "groups": groups,
        "peak": peak,
    }


def export_real_baseline_artifacts(result: dict[str, Any], out_dir: Path) -> dict[str, Path]:
    """Write joblib / ONNX / meta / model card for component A."""
    out_dir = Path(out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
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
        "trained_via": "notebook",
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
        "cv_recursive_96_heldout": result.get("cv_recursive_96_heldout", {}),
        "debug_in_sample_recursive": result.get("debug_in_sample_recursive"),
        "n_rows": result["n_rows"],
        "n_days": result["n_days"],
        "outer_splits": result["outer_splits"],
        "n_iter_inner": result["n_iter"],
        "built_at_utc": datetime.now(timezone.utc).isoformat(),
        "lag_init_policy": "measured_midnight_state_from_JSON_or_first_row",
        "trained_via": "notebook",
    }
    if card["debug_in_sample_recursive"] is None:
        card.pop("debug_in_sample_recursive")
    card_path.write_text(json.dumps(card, indent=2), encoding="utf-8")
    return {
        "joblib": joblib_path,
        "onnx": onnx_path,
        "meta": meta_path,
        "card": card_path,
    }


def load_real_baseline_frame(
    *,
    parquet: Path | None = None,
    winter_only: bool = True,
    max_days: int | None = 36,
) -> pd.DataFrame:
    site = site_root()
    pq = parquet or (site / "ml" / "artifacts" / "real_baseline_15min_v1.parquet")
    if not pq.is_file():
        raise FileNotFoundError(f"missing {pq} — run scripts/build_real_15min_store.py")
    df = pd.read_parquet(pq)
    if (df.get("provenance") is not None) and not (df["provenance"] == "REAL_BAS_15MIN").all():
        raise ValueError("refusing non-REAL_BAS store")
    if winter_only:
        df = df[df["month"].isin([11, 12, 1, 2, 3])].copy()
    if max_days:
        days = sorted(df["day"].unique())[: int(max_days)]
        df = df[df["day"].isin(days)].copy()
    return df


def main(argv: list[str] | None = None) -> int:
    from notebook_gate import cli_train_allowed, refuse_cli_train

    if not cli_train_allowed():
        return refuse_cli_train("real baseline (component A)")

    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--parquet", type=Path, default=None)
    ap.add_argument("--out-dir", type=Path, default=None)
    ap.add_argument("--outer-splits", type=int, default=3)
    ap.add_argument("--inner-splits", type=int, default=2)
    ap.add_argument("--n-iter", type=int, default=6)
    ap.add_argument("--max-days", type=int, default=None)
    ap.add_argument("--winter-only", action="store_true")
    args = ap.parse_args(argv)

    df = load_real_baseline_frame(
        parquet=args.parquet,
        winter_only=args.winter_only,
        max_days=args.max_days,
    )
    out_dir = args.out_dir or (_ML / "artifacts")
    result = nested_bake_off(
        df,
        outer_splits=args.outer_splits,
        inner_splits=args.inner_splits,
        n_iter=args.n_iter,
    )
    paths = export_real_baseline_artifacts(result, out_dir)
    print(json.dumps({"champion": result["champion"], "card": str(paths["card"])}, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

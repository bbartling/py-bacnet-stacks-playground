#!/usr/bin/env python
"""Train 7-output real BAS 15-min baseline (GB / ExtraTrees / RF) with nested CV.

Exports ``real_baseline_15min_v1`` artifacts — not desktop ship stem until hybrid promote.
Honesty label: HYBRID_SCREENING (component A — measured only).
"""
from __future__ import annotations

import argparse
import hashlib
import json
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable

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

from chrono_splits import build_split_manifest, write_manifest  # noqa: E402
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
FEATURE_CONTRACT_VERSION = "FEATURE_COLS_15MIN_MT"
CONTROL_CONTRACT_VERSION = "control_strategies_v1"
# Notes / statuses that would betray a non-honest held-out metric. Code must
# never emit these into ``cv_recursive_96_heldout``; promote rejects them too.
FORBIDDEN_NOTE_TOKENS = (
    "provisional",
    "teacher_forced",
    "debug",
    "in_sample",
    "not_evaluated",
    "insufficient",
)


def _sha256_file(path: Path) -> str | None:
    path = Path(path)
    if not path.is_file():
        return None
    h = hashlib.sha256()
    h.update(path.read_bytes())
    return h.hexdigest()


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
PEAK_STEP_LO, PEAK_STEP_HI = 20, 36  # HE 05–09 window on step_15


def _day_mask(feat: pd.DataFrame, days: list[Any]) -> np.ndarray:
    dset = {str(d) for d in days}
    return feat["day"].astype(str).isin(dset).to_numpy()


def evaluate_recursive_days(
    model,
    feat: pd.DataFrame,
    day_list: list[Any],
    cols: list[str],
    tcols: list[str],
    *,
    min_rows: int = 80,
) -> dict[str, Any]:
    """Real recursive (self-lag) metrics over an explicit ``day_list``.

    Never teacher-forced: lags are seeded from the measured midnight state then
    fed the model's own predictions. Returns per-day scores plus an aggregate
    whose ``n_heldout_days`` is the count of *unique* evaluated days (not a mean
    of fold counts). Peak window = ``step_15`` in [20, 36] (HE 05–09).

    Per-day metrics: facility MAE/RMSE, peak-window MAE, daily peak-magnitude
    error, peak-timing absolute error (steps), daily kWh error, mean zone MAE and
    per-zone MAE, and absolute horizon errors at steps {1,4,12,24,48,96}.
    """
    dset = {str(d) for d in day_list}
    sub_all = feat[feat["day"].astype(str).isin(dset)]
    per_day: dict[str, dict[str, Any]] = {}
    for day, sub in sub_all.groupby("day"):
        if len(sub) < min_rows:
            continue
        s = sub.sort_values("step_15")
        yp = recursive_rollout_day(model, s, cols, tcols)
        yt = s[list(tcols)].to_numpy(dtype=float)
        n = len(s)
        pk = morning_peak_mask_15min(s)
        fac_p, fac_t = yp[:, 0], yt[:, 0]
        err = np.abs(fac_p - fac_t)
        score: dict[str, Any] = {
            "facility_kw_mae": float(np.mean(err)),
            "facility_kw_rmse": float(np.sqrt(np.mean((fac_p - fac_t) ** 2))),
            "facility_kw_mae_peak_05_09": float(np.mean(err[pk]))
            if np.any(pk)
            else float(np.mean(err)),
            "daily_peak_mag_error_kw": float(abs(float(np.max(fac_p)) - float(np.max(fac_t)))),
            "peak_timing_abs_error_steps": float(
                abs(int(np.argmax(fac_p)) - int(np.argmax(fac_t)))
            ),
            "daily_kwh_error": float(abs(fac_p.sum() * 0.25 - fac_t.sum() * 0.25)),
            "zone_temp_mae_mean": float(np.mean(np.abs(yp[:, 1:] - yt[:, 1:]))),
            "n_steps": int(n),
        }
        for zi, zc in enumerate(list(tcols)[1:]):
            score[f"zone_mae_{zc}"] = float(np.mean(np.abs(yp[:, 1 + zi] - yt[:, 1 + zi])))
        for h in HORIZON_STEPS:
            idx = h - 1
            if 0 <= idx < n:
                score[f"horizon_mae_step_{h}"] = float(abs(fac_p[idx] - fac_t[idx]))
        per_day[str(day)] = score

    agg = _agg_day_scores(list(per_day.values()))
    agg["per_day"] = per_day
    return agg


def _agg_day_scores(scores: list[dict]) -> dict[str, Any]:
    """Mean flat day-score dicts; ``n_heldout_days`` = number of days."""
    scores = [s for s in scores if s]
    if not scores:
        return {"n_heldout_days": 0}
    keys: set[str] = set()
    for s in scores:
        keys.update(k for k in s.keys() if k != "per_day")
    out: dict[str, Any] = {"n_heldout_days": int(len(scores))}
    for k in sorted(keys):
        vals = [
            s[k]
            for s in scores
            if k in s and s[k] is not None and np.isfinite(s[k])
        ]
        if vals:
            out[k] = float(np.mean(vals))
    return out


def compute_baselines(
    feat: pd.DataFrame,
    train_days: list[Any],
    eval_days: list[Any],
) -> dict[str, Any]:
    """Naive references: persistence (lag1) and same-hour-of-day train mean.

    Evaluated on ``eval_days`` facility_kw; the same-hour mean is fit on
    ``train_days`` only. Peak-window MAE uses step_15 in [20, 36].
    """
    train_set = {str(d) for d in train_days}
    eval_set = {str(d) for d in eval_days}
    ev = feat[feat["day"].astype(str).isin(eval_set)]
    tr = feat[feat["day"].astype(str).isin(train_set)]
    out: dict[str, Any] = {"n_eval_days": int(ev["day"].nunique()) if not ev.empty else 0}
    if ev.empty:
        return out
    yt = pd.to_numeric(ev["facility_kw"], errors="coerce").to_numpy(dtype=float)
    pk = morning_peak_mask_15min(ev)

    def _mae(pred: np.ndarray) -> dict[str, Any]:
        m = np.isfinite(pred) & np.isfinite(yt)
        res: dict[str, Any] = {}
        if m.any():
            res["facility_kw_mae"] = float(np.mean(np.abs(pred[m] - yt[m])))
            pm = pk & m
            res["facility_kw_mae_peak_05_09"] = (
                float(np.mean(np.abs(pred[pm] - yt[pm]))) if pm.any() else None
            )
        return res

    if "facility_kw_lag1" in ev.columns:
        yp = pd.to_numeric(ev["facility_kw_lag1"], errors="coerce").to_numpy(dtype=float)
        pers = _mae(yp)
        if pers:
            out["persistence_lag1"] = pers

    if not tr.empty:
        hod = (
            pd.to_numeric(tr["facility_kw"], errors="coerce")
            .groupby(tr["step_15"].to_numpy())
            .mean()
        )
        pred = ev["step_15"].map(hod).to_numpy(dtype=float)
        shm = _mae(pred)
        if shm:
            out["same_hour_of_day_mean"] = shm
    return out


def _manifest_eval_families(
    feat: pd.DataFrame,
    X: np.ndarray,
    Y: np.ndarray,
    cols: list[str],
    tcols: list[str],
    family_names: list[str],
    fit_fn: Callable[[str, np.ndarray], Any],
    manifest: dict[str, Any],
    peak: np.ndarray,
) -> tuple[dict, dict, dict, str]:
    """Run rolling-origin folds; return (tf_summary, rec_summary, per_day, champ).

    Champion is selected by minimum **recursive** peak-window MAE on the rolling
    validation days (teacher-forced is still reported, never used to select).
    """
    per_day_rec: dict[str, dict] = {f: {} for f in family_names}
    tf_scores: dict[str, list] = {f: [] for f in family_names}
    for fold in manifest.get("folds", []):
        tr_days, va_days = fold["train"], fold["val"]
        tr_mask = _day_mask(feat, tr_days)
        va_mask = _day_mask(feat, va_days)
        if not tr_mask.any() or not va_mask.any():
            continue
        for f in family_names:
            model = fit_fn(f, tr_mask)
            pred = model.predict(X[va_mask])
            tf_scores[f].append(_metrics_multi(Y[va_mask], pred, peak[va_mask]))
            ev = evaluate_recursive_days(model, feat, va_days, cols, tcols)
            per_day_rec[f].update(ev.get("per_day", {}))
    summary_tf = {f: _mean_metric_dicts(tf_scores[f]) for f in family_names}
    summary_rec = {f: _agg_day_scores(list(per_day_rec[f].values())) for f in family_names}
    pool = [
        f
        for f in family_names
        if summary_rec[f].get("facility_kw_mae_peak_05_09") is not None
    ] or list(family_names)
    champ = min(pool, key=lambda f: summary_rec[f].get("facility_kw_mae_peak_05_09", 1e9))
    return summary_tf, summary_rec, per_day_rec, champ


def _write_eval_per_day(
    out_dir: Path,
    champion: str,
    per_day_by_family: dict[str, dict],
    final_test_recursive: dict[str, Any] | None = None,
) -> Path:
    """Write per-day recursive scores to ``eval/baseline_recursive_days.json``."""
    eval_dir = Path(out_dir) / "eval"
    eval_dir.mkdir(parents=True, exist_ok=True)
    path = eval_dir / "baseline_recursive_days.json"
    doc = {
        "champion": champion,
        "rolling_val_per_day": {
            fam: pd for fam, pd in per_day_by_family.items()
        },
        "final_winter_test_recursive": final_test_recursive or {},
    }
    path.write_text(json.dumps(doc, indent=2), encoding="utf-8")
    return path


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
    split_manifest: dict[str, Any] | None = None,
    out_dir: Path | None = None,
) -> dict[str, Any]:
    """Nested-CV bake-off. Champion selected on **recursive** peak MAE.

    When ``split_manifest`` is provided, folds come from the leakage-safe
    chronological manifest (per-fold hyperparameter tuning on the fold's train
    days), the final model is fit on ``dev_days`` only, and a separate
    ``final_test_recursive`` is computed on ``final_winter_test``. Recursive
    metrics are always real (never copied from teacher-forced).
    """
    families = families or ["gradient_boosting", "extra_trees", "random_forest"]
    df = ensure_strategy_onehots(df)
    X, Y, groups, cols, tcols, feat = matrix_xy_15min_multi(df)
    peak = morning_peak_mask_15min(feat)
    rng = np.random.RandomState(21)
    proto_map = {
        "gradient_boosting": GradientBoostingRegressor(random_state=21),
        "extra_trees": ExtraTreesRegressor(random_state=21, n_jobs=1),
        "random_forest": RandomForestRegressor(random_state=21, n_jobs=1),
    }
    best_params_by_family: dict[str, dict] = {f: {} for f in families}

    if split_manifest is not None:
        def fit_fn(fam: str, tr_mask: np.ndarray) -> Any:
            model, params, _ = _fit_family(
                fam, X[tr_mask], Y[tr_mask], groups[tr_mask],
                n_iter=n_iter, inner_splits=inner_splits, rng=rng,
            )
            best_params_by_family[fam] = params
            return model

        summary_tf, summary_rec, per_day_rec, champ = _manifest_eval_families(
            feat, X, Y, cols, tcols, families, fit_fn, split_manifest, peak
        )
        dev_mask = _day_mask(feat, split_manifest.get("dev_days", []))
        if not dev_mask.any():
            raise ValueError("split_manifest dev_days match no rows in this frame")
        tuned: dict[str, Any] = {}
        for fam in families:
            m, params, _ = _fit_family(
                fam, X[dev_mask], Y[dev_mask], groups[dev_mask],
                n_iter=n_iter, inner_splits=inner_splits, rng=rng,
            )
            best_params_by_family[fam] = params
            tuned[fam] = m
        champ_model = tuned[champ]
        final_days = split_manifest.get("final_winter_test", [])
        final_test_rec = (
            {fam: evaluate_recursive_days(tuned[fam], feat, final_days, cols, tcols) for fam in families}
            if final_days
            else {}
        )
        base_eval_days = final_days or [d for fold in split_manifest.get("folds", []) for d in fold["val"]]
        baselines = compute_baselines(feat, split_manifest.get("dev_days", []), base_eval_days)
        n_outer = len(split_manifest.get("folds", []))
    else:
        uniq = np.unique(groups)
        n_outer = min(outer_splits, max(2, len(uniq)))
        gkf_outer = GroupKFold(n_splits=n_outer)
        oof_tf: dict[str, list[dict]] = {f: [] for f in families}
        per_day_rec = {f: {} for f in families}
        best_params_outer: dict[str, list[dict]] = {f: [] for f in families}
        for fold, (tr, te) in enumerate(gkf_outer.split(X, Y, groups)):
            print(f"outer fold {fold + 1}/{n_outer} train={len(tr)} test={len(te)}", flush=True)
            te_days = list(pd.unique(feat.iloc[te]["day"]))
            for fam in families:
                model, params, _ = _fit_family(
                    fam, X[tr], Y[tr], groups[tr], n_iter=n_iter, inner_splits=inner_splits, rng=rng
                )
                best_params_outer[fam].append(params)
                pred_tf = model.predict(X[te])
                oof_tf[fam].append(_metrics_multi(Y[te], pred_tf, peak[te]))
                ev = evaluate_recursive_days(model, feat, te_days, cols, tcols)
                per_day_rec[fam].update(ev.get("per_day", {}))
                print(
                    f"  {fam} TF peak MAE={oof_tf[fam][-1]['facility_kw_mae_peak_05_09']:.3f}",
                    flush=True,
                )
        summary_tf = {f: _mean_metric_dicts(oof_tf[f]) for f in families}
        summary_rec = {f: _agg_day_scores(list(per_day_rec[f].values())) for f in families}
        pool = [
            f for f in families if summary_rec[f].get("facility_kw_mae_peak_05_09") is not None
        ] or families
        champ = min(pool, key=lambda f: summary_rec[f].get("facility_kw_mae_peak_05_09", 1e9))
        for f in families:
            best_params_by_family[f] = best_params_outer[f][-1] if best_params_outer[f] else {}
        tuned = {}
        for fam in families:
            p = best_params_by_family[fam]
            b = proto_map[fam]
            m = MultiOutputRegressor(b.__class__(**{**b.get_params(), **p}), n_jobs=-1)
            m.fit(X, Y)
            tuned[fam] = m
        champ_model = tuned[champ]
        all_days = list(pd.unique(feat["day"]))
        baselines = compute_baselines(feat, all_days, all_days)
        final_test_rec = {}

    if out_dir is not None:
        _write_eval_per_day(Path(out_dir), champ, per_day_rec, final_test_rec)

    return {
        "model": champ_model,
        "tuned_models": tuned,
        "champion": champ,
        "best_params": best_params_by_family.get(champ, {}),
        "best_params_by_family": best_params_by_family,
        "feature_cols": cols,
        "target_cols": tcols,
        "cv_teacher_forced": summary_tf,
        "cv_recursive_96_heldout": summary_rec,
        "final_test_recursive": final_test_rec,
        "baselines": baselines,
        "split_manifest": split_manifest,
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


def _lean_families() -> dict[str, Any]:
    return {
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


def lean_bake_off(
    df: pd.DataFrame,
    *,
    n_splits: int = 3,
    split_manifest: dict[str, Any] | None = None,
    out_dir: Path | None = None,
) -> dict[str, Any]:
    """Fixed-hyperparam bake-off (notebook default — wall-clock honest).

    When ``split_manifest`` is provided, evaluation is leakage-safe and
    chronological: champion selection uses **recursive** peak MAE on the
    rolling-origin validation days; the final model is fit on ``dev_days`` only;
    a separate ``final_test_recursive`` is computed on ``final_winter_test``
    (never used for selection). Without a manifest, a GroupKFold(day) fallback is
    used, still selecting on recursive peak MAE. Recursive metrics are never
    copied from teacher-forced.
    """
    df = ensure_strategy_onehots(df)
    X, Y, groups, cols, tcols, feat = matrix_xy_15min_multi(df)
    X = np.nan_to_num(X, nan=0.0, posinf=0.0, neginf=0.0)
    peak = morning_peak_mask_15min(feat)
    families = _lean_families()
    fam_names = list(families)

    def fit_fn(name: str, tr_mask: np.ndarray) -> Any:
        proto = families[name]
        m = MultiOutputRegressor(proto.__class__(**proto.get_params()), n_jobs=1)
        m.fit(X[tr_mask], Y[tr_mask])
        return m

    if split_manifest is not None:
        summary_tf, summary_rec, per_day_rec, champ = _manifest_eval_families(
            feat, X, Y, cols, tcols, fam_names, fit_fn, split_manifest, peak
        )
        dev_mask = _day_mask(feat, split_manifest.get("dev_days", []))
        if not dev_mask.any():
            raise ValueError("split_manifest dev_days match no rows in this frame")
        tuned = {name: fit_fn(name, dev_mask) for name in fam_names}
        model = tuned[champ]
        final_days = split_manifest.get("final_winter_test", [])
        final_test_rec = (
            {name: evaluate_recursive_days(tuned[name], feat, final_days, cols, tcols) for name in fam_names}
            if final_days
            else {}
        )
        base_eval_days = final_days or [d for fold in split_manifest.get("folds", []) for d in fold["val"]]
        baselines = compute_baselines(feat, split_manifest.get("dev_days", []), base_eval_days)
        n_outer = len(split_manifest.get("folds", []))
    else:
        uniq = np.unique(groups)
        gkf = GroupKFold(n_splits=min(n_splits, max(2, len(uniq))))
        per_day_rec = {f: {} for f in fam_names}
        tf: dict[str, list] = {f: [] for f in fam_names}
        for fold, (tr, te) in enumerate(gkf.split(X, Y, groups)):
            print(f"lean fold {fold + 1}/{gkf.get_n_splits()}", flush=True)
            te_days = list(pd.unique(feat.iloc[te]["day"]))
            for name in fam_names:
                m = fit_fn(name, tr)
                pred = m.predict(X[te])
                tf[name].append(_metrics_multi(Y[te], pred, peak[te]))
                ev = evaluate_recursive_days(m, feat, te_days, cols, tcols)
                per_day_rec[name].update(ev.get("per_day", {}))
                print(f"  {name} peak MAE={tf[name][-1]['facility_kw_mae_peak_05_09']:.3f}", flush=True)
        summary_tf = {f: _mean_metric_dicts(tf[f]) for f in fam_names}
        summary_rec = {f: _agg_day_scores(list(per_day_rec[f].values())) for f in fam_names}
        pool = [
            f for f in fam_names if summary_rec[f].get("facility_kw_mae_peak_05_09") is not None
        ] or fam_names
        champ = min(pool, key=lambda n: summary_rec[n].get("facility_kw_mae_peak_05_09", 1e9))
        model = fit_fn(champ, np.ones(len(feat), dtype=bool))
        tuned = {champ: model}
        all_days = list(pd.unique(feat["day"]))
        baselines = compute_baselines(feat, all_days, all_days)
        final_test_rec = {}
        n_outer = int(gkf.get_n_splits())

    if out_dir is not None:
        _write_eval_per_day(Path(out_dir), champ, per_day_rec, final_test_rec)

    return {
        "model": model,
        "champion": champ,
        "best_params": families[champ].get_params(),
        "best_params_by_family": {k: v.get_params() for k, v in families.items()},
        "feature_cols": cols,
        "target_cols": tcols,
        "cv_teacher_forced": summary_tf,
        "cv_recursive_96_heldout": summary_rec,
        "final_test_recursive": final_test_rec,
        "baselines": baselines,
        "split_manifest": split_manifest,
        "n_rows": int(len(feat)),
        "n_days": int(feat["day"].nunique()),
        "outer_splits": n_outer,
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
        "feature_contract_version": FEATURE_CONTRACT_VERSION,
        "control_contract_version": CONTROL_CONTRACT_VERSION,
        "trained_via": "notebook",
    }
    meta_path.write_text(json.dumps(meta, indent=2), encoding="utf-8")

    # Persist the chrono split manifest (if any) so its hash can be recorded.
    split_manifest_path: Path | None = None
    manifest = result.get("split_manifest")
    if manifest:
        split_manifest_path = write_manifest(out_dir / "eval" / "split_manifest.json", manifest)

    hashes = {
        "onnx_sha256": _sha256_file(onnx_path),
        "split_manifest_sha256": _sha256_file(split_manifest_path) if split_manifest_path else None,
    }

    card = {
        "stem": STEM,
        "honesty": HONESTY,
        "provenance": "REAL_BAS_15MIN",
        "champion": result["champion"],
        "champion_selected_by": "recursive_facility_kw_mae_peak_05_09",
        "best_params": result["best_params"],
        "best_params_by_family": result["best_params_by_family"],
        "cv_teacher_forced": result["cv_teacher_forced"],
        "cv_recursive_96_heldout": result.get("cv_recursive_96_heldout", {}),
        "final_test_recursive": result.get("final_test_recursive", {}),
        "baselines": result.get("baselines", {}),
        "n_rows": result["n_rows"],
        "n_days": result["n_days"],
        "outer_splits": result["outer_splits"],
        "n_iter_inner": result["n_iter"],
        "built_at_utc": datetime.now(timezone.utc).isoformat(),
        "lag_init_policy": "measured_midnight_state_from_JSON_or_first_row",
        "feature_contract_version": FEATURE_CONTRACT_VERSION,
        "control_contract_version": CONTROL_CONTRACT_VERSION,
        "hashes": hashes,
        "trained_via": "notebook",
    }
    if split_manifest_path is not None:
        card["split_manifest_path"] = str(split_manifest_path)
    # Debug-only in-sample recursive may be attached by callers; keep it clearly
    # labeled and NEVER as the held-out CV. It is not part of the honest metrics.
    dbg = result.get("debug_in_sample_recursive")
    if dbg:
        card["debug_in_sample_recursive"] = dbg
    _assert_no_provisional_heldout(card["cv_recursive_96_heldout"])
    card_path.write_text(json.dumps(card, indent=2), encoding="utf-8")
    return {
        "joblib": joblib_path,
        "onnx": onnx_path,
        "meta": meta_path,
        "card": card_path,
    }


def _assert_no_provisional_heldout(held: Any) -> None:
    """Fail loudly if held-out recursive metrics contain forbidden note tokens."""

    def _scan(obj: Any) -> None:
        if isinstance(obj, dict):
            for k, v in obj.items():
                if isinstance(v, str) and k in ("note", "status"):
                    low = v.lower()
                    if any(tok in low for tok in FORBIDDEN_NOTE_TOKENS):
                        raise ValueError(
                            f"refusing to export card: cv_recursive_96_heldout carries "
                            f"forbidden {k}={v!r}"
                        )
                _scan(v)
        elif isinstance(obj, list):
            for x in obj:
                _scan(x)

    _scan(held)


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
    manifest = build_split_manifest(df)
    result = nested_bake_off(
        df,
        outer_splits=args.outer_splits,
        inner_splits=args.inner_splits,
        n_iter=args.n_iter,
        split_manifest=manifest,
        out_dir=out_dir,
    )
    paths = export_real_baseline_artifacts(result, out_dir)
    print(json.dumps({"champion": result["champion"], "card": str(paths["card"])}, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

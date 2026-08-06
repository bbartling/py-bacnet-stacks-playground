#!/usr/bin/env python
"""Build paired E+ delta table and train 7-out delta surrogate (component B)."""
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
from feature_compile_heating_dsm import TARGET_COLS, ZONE_TEMP_COLS  # noqa: E402
from train_real_baseline_15min import export_onnx_multi  # noqa: E402

STEM = "eplus_delta_15min_v1"
DELTA_PARQUET = "eplus_delta_15min_v1.parquet"
HONESTY = "HYBRID_SCREENING"
DELTA_TARGETS = ["delta_facility_kw", *[f"delta_{c}" for c in ZONE_TEMP_COLS]]


def build_delta_frame(paired: pd.DataFrame) -> pd.DataFrame:
    """Join DSM − baseline on pair_id + timestamp alignment."""
    need = {"pair_id", "arm", "facility_kw", *ZONE_TEMP_COLS}
    missing = need - set(paired.columns)
    if missing:
        raise ValueError(f"paired farm missing {missing}")
    # only pairs with both arms
    counts = paired.groupby("pair_id")["arm"].nunique()
    both = counts[counts >= 2].index
    df = paired[paired["pair_id"].isin(both)].copy()
    base = df[df["arm"] == "baseline"].copy()
    dsm = df[df["arm"] == "dsm"].copy()
    # align keys
    keys = ["pair_id"]
    if "quarter_index" in df.columns:
        keys.append("quarter_index")
    elif "eplus_stamp" in df.columns:
        keys.append("eplus_stamp")
    else:
        keys.append("hour_ending")

    base_y = base[keys + ["facility_kw", *ZONE_TEMP_COLS]].rename(
        columns={
            "facility_kw": "baseline_facility_kw",
            **{c: f"baseline_{c}" for c in ZONE_TEMP_COLS},
        }
    )
    merged = dsm.merge(base_y, on=keys, how="inner", suffixes=("", "_b"))
    if merged.empty:
        raise ValueError("no paired DSM/baseline rows to differ")
    merged["delta_facility_kw"] = merged["facility_kw"] - merged["baseline_facility_kw"]
    for c in ZONE_TEMP_COLS:
        merged[f"delta_{c}"] = merged[c] - merged[f"baseline_{c}"]
    # train targets = deltas; keep absolute cols for reference
    out = merged.copy()
    out["facility_kw"] = out["delta_facility_kw"]
    for c in ZONE_TEMP_COLS:
        out[c] = out[f"delta_{c}"]
    # causal lags on delta targets within pair-day
    if "day" not in out.columns:
        out["day"] = out["pair_id"].astype(str)
    out = out.sort_values(["pair_id", "day"] + [k for k in keys if k != "pair_id"]).reset_index(drop=True)
    g = out.groupby("pair_id", sort=False)
    out["facility_kw_lag1"] = g["facility_kw"].shift(1)
    out["facility_kw_lag2"] = g["facility_kw"].shift(2)
    if "oat_f" in out.columns:
        out["oat_lag1"] = g["oat_f"].shift(1)
    for c in ZONE_TEMP_COLS:
        out[f"{c}_lag1"] = g[c].shift(1)
    # calendar features if missing
    if "step_15" not in out.columns:
        if "quarter_index" in out.columns:
            out["step_15"] = pd.to_numeric(out["quarter_index"], errors="coerce").astype(int) % 96
        else:
            he = pd.to_numeric(out.get("hour_ending", 0), errors="coerce")
            out["step_15"] = (he * 4).astype(int).clip(0, 95)
    if "sin_step" not in out.columns:
        out["sin_step"] = np.sin(2 * np.pi * out["step_15"] / 96.0)
        out["cos_step"] = np.cos(2 * np.pi * out["step_15"] / 96.0)
    for c in ("hdd65", "hdd65_cum_night", "hours_to_occupy", "sum_occ_frac", "sum_hp_on"):
        if c not in out.columns:
            if c == "hdd65" and "oat_f" in out.columns:
                out[c] = np.maximum(0.0, 65.0 - pd.to_numeric(out["oat_f"], errors="coerce"))
            elif c == "sum_occ_frac":
                cols = [x for x in out.columns if x.startswith("occ_frac_")]
                out[c] = out[cols].sum(axis=1) if cols else 0.0
            elif c == "sum_hp_on":
                cols = [x for x in out.columns if x.startswith("hp_on_")]
                out[c] = out[cols].sum(axis=1) if cols else 0.0
            elif c == "hours_to_occupy":
                out[c] = np.maximum(0.0, (28 - out["step_15"]) / 4.0)
            else:
                out[c] = 0.0
    out["provenance"] = "ENERGYPLUS_NATIVE_DELTA"
    out["honesty"] = HONESTY
    return out


def _fit_family(name, X, Y, groups, n_iter, inner_splits, rng):
    spaces = {
        "gradient_boosting": {
            "n_estimators": [60, 100, 160],
            "learning_rate": [0.05, 0.1, 0.15],
            "max_depth": [2, 3, 4],
            "min_samples_leaf": [2, 4, 8],
        },
        "extra_trees": {
            "n_estimators": [120, 220, 350],
            "max_depth": [10, 18, None],
            "min_samples_leaf": [1, 2, 4],
            "max_features": [0.5, 0.8, "sqrt"],
        },
        "random_forest": {
            "n_estimators": [120, 220, 350],
            "max_depth": [10, 18, None],
            "min_samples_leaf": [1, 2, 4],
            "max_features": [0.5, 0.8, "sqrt"],
        },
    }
    proto = {
        "gradient_boosting": GradientBoostingRegressor(random_state=21),
        "extra_trees": ExtraTreesRegressor(random_state=21, n_jobs=1),
        "random_forest": RandomForestRegressor(random_state=21, n_jobs=1),
    }[name]
    uniq = np.unique(groups)
    gkf = GroupKFold(n_splits=min(inner_splits, max(2, len(uniq))))
    best_score, best_params = float("inf"), {}
    for params in ParameterSampler(spaces[name], n_iter=n_iter, random_state=rng):
        scores = []
        for tr, te in gkf.split(X, Y, groups):
            est = MultiOutputRegressor(proto.__class__(**{**proto.get_params(), **params}), n_jobs=-1)
            est.fit(X[tr], Y[tr])
            pred = est.predict(X[te])
            scores.append(mean_absolute_error(Y[te][:, 0], pred[:, 0]))
        m = float(np.mean(scores))
        if m < best_score:
            best_score, best_params = m, dict(params)
    final = MultiOutputRegressor(proto.__class__(**{**proto.get_params(), **best_params}), n_jobs=-1)
    final.fit(X, Y)
    return final, best_params, best_score


def train_delta(df: pd.DataFrame, *, outer_splits: int = 3, n_iter: int = 4) -> dict[str, Any]:
    df = ensure_strategy_onehots(df)
    X, Y, groups, cols, tcols, feat = matrix_xy_15min_multi(df)
    peak = morning_peak_mask_15min(feat)
    families = ["gradient_boosting", "extra_trees", "random_forest"]
    uniq = np.unique(groups)
    gkf = GroupKFold(n_splits=min(outer_splits, max(2, len(uniq))))
    rng = np.random.RandomState(21)
    summary = {f: [] for f in families}
    params_last = {}
    for fold, (tr, te) in enumerate(gkf.split(X, Y, groups)):
        print(f"delta outer fold {fold+1}", flush=True)
        for fam in families:
            model, params, _ = _fit_family(fam, X[tr], Y[tr], groups[tr], n_iter, 2, rng)
            params_last[fam] = params
            pred = model.predict(X[te])
            summary[fam].append(
                {
                    "mae_delta_kw": float(mean_absolute_error(Y[te, 0], pred[:, 0])),
                    "rmse_delta_kw": float(np.sqrt(mean_squared_error(Y[te, 0], pred[:, 0]))),
                    "mae_delta_kw_peak": float(
                        mean_absolute_error(Y[te, 0][peak[te]], pred[:, 0][peak[te]])
                    )
                    if peak[te].any()
                    else float(mean_absolute_error(Y[te, 0], pred[:, 0])),
                    "mae_delta_temp_mean": float(np.mean(np.abs(Y[te, 1:] - pred[:, 1:]))),
                }
            )
    def mean_scores(xs):
        return {k: float(np.mean([s[k] for s in xs])) for k in xs[0]}

    cv = {f: mean_scores(summary[f]) for f in families}
    champ = min(families, key=lambda f: cv[f]["mae_delta_kw_peak"])
    proto = {
        "gradient_boosting": GradientBoostingRegressor(random_state=21),
        "extra_trees": ExtraTreesRegressor(random_state=21, n_jobs=1),
        "random_forest": RandomForestRegressor(random_state=21, n_jobs=1),
    }[champ]
    model = MultiOutputRegressor(
        proto.__class__(**{**proto.get_params(), **params_last[champ]}), n_jobs=-1
    )
    model.fit(X, Y)
    return {
        "model": model,
        "champion": champ,
        "best_params": params_last[champ],
        "cv_teacher_forced": cv,
        "feature_cols": cols,
        "target_cols": tcols,
        "n_rows": len(feat),
        "n_days": int(feat["day"].nunique()) if "day" in feat.columns else int(feat["pair_id"].nunique()),
    }


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--paired-parquet", type=Path, default=None)
    ap.add_argument("--out-dir", type=Path, default=None)
    ap.add_argument("--n-iter", type=int, default=4)
    ap.add_argument("--outer-splits", type=int, default=3)
    args = ap.parse_args(argv)

    out_dir = args.out_dir or (_ML / "artifacts")
    out_dir.mkdir(parents=True, exist_ok=True)
    paired_path = args.paired_parquet or (out_dir / "heating_dsm_eplus_paired_15min_v1.parquet")
    paired = pd.read_parquet(paired_path)
    # manifest hash gate
    if "provenance" in paired.columns and not (paired["provenance"] == "ENERGYPLUS_NATIVE_RUN").all():
        raise ValueError("refusing paired farm without ENERGYPLUS_NATIVE_RUN")
    if "input_hash" not in paired.columns or paired["input_hash"].isna().any():
        raise ValueError("hash gate failed: missing input_hash on rows")
    if "run_model_hash" in paired.columns and paired["run_model_hash"].isna().any():
        raise ValueError("hash gate failed: missing run_model_hash")

    delta = build_delta_frame(paired)
    delta_path = out_dir / DELTA_PARQUET
    delta.to_parquet(delta_path, index=False)
    print(f"delta rows={len(delta)} pairs={delta['pair_id'].nunique()} -> {delta_path}", flush=True)

    result = train_delta(delta, outer_splits=args.outer_splits, n_iter=args.n_iter)
    joblib.dump(
        {
            "model": result["model"],
            "feature_cols": result["feature_cols"],
            "target_cols": result["target_cols"],
            "champion": result["champion"],
            "targets_are_deltas": True,
        },
        out_dir / f"{STEM}.joblib",
    )
    try:
        export_onnx_multi(result["model"], len(result["feature_cols"]), out_dir / f"{STEM}.onnx")
    except Exception as e:
        print(f"ONNX export failed: {e}", flush=True)

    meta = {
        "stem": STEM,
        "feature_cols": result["feature_cols"],
        "target_cols": result["target_cols"],
        "delta_target_names": DELTA_TARGETS,
        "n_features": len(result["feature_cols"]),
        "n_outputs": 7,
        "honesty": HONESTY,
        "component": "B_eplus_delta",
        "targets_are_deltas": True,
    }
    (out_dir / f"{STEM}_feature_meta.json").write_text(json.dumps(meta, indent=2), encoding="utf-8")
    card = {
        "stem": STEM,
        "honesty": HONESTY,
        "provenance": "ENERGYPLUS_NATIVE_DELTA",
        "champion": result["champion"],
        "best_params": result["best_params"],
        "cv_teacher_forced": result["cv_teacher_forced"],
        "n_rows": result["n_rows"],
        "n_days": result["n_days"],
        "built_at_utc": datetime.now(timezone.utc).isoformat(),
        "paired_source": str(paired_path),
    }
    (out_dir / f"{STEM}_model_card.json").write_text(json.dumps(card, indent=2), encoding="utf-8")
    print(json.dumps({"champion": result["champion"], "cv": result["cv_teacher_forced"]}, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

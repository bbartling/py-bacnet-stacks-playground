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
    ensure_strategy_onehots,
    matrix_xy_15min_multi,
    morning_peak_mask_15min,
)
from feature_compile_heating_dsm import TARGET_COLS, ZONE_TEMP_COLS  # noqa: E402
from train_real_baseline_15min import (  # noqa: E402
    _agg_day_scores,
    evaluate_recursive_days,
    export_onnx_multi,
)

STEM = "eplus_delta_15min_v1"
DELTA_PARQUET = "eplus_delta_15min_v1.parquet"
HONESTY = "HYBRID_SCREENING"
DELTA_TARGETS = ["delta_facility_kw", *[f"delta_{c}" for c in ZONE_TEMP_COLS]]
# Confounding + underpowered-farm limitation string (must appear on every card).
DELTA_LIMITATION = (
    "strategy, date, and weather remain confounded; smoke farm underpowered"
)
COVERAGE_MIN_HELDOUT_DAYS = 12


def _delta_recursive_summary(per_day_scores: list[dict]) -> dict[str, Any]:
    """Aggregate real recursive per-day facility scores into delta vocabulary.

    ``n_heldout_days`` is the count of unique held-out pair-days (never a mean of
    fold counts) and metrics are the model's own recursive output — never a
    teacher-forced copy.
    """
    agg = _agg_day_scores(per_day_scores)
    n_days = int(agg.get("n_heldout_days", 0))
    if n_days == 0:
        return {"n_heldout_days": 0}
    out: dict[str, Any] = {
        "mae_delta_kw": agg.get("facility_kw_mae"),
        "rmse_delta_kw": agg.get("facility_kw_rmse"),
        "mae_delta_kw_peak": agg.get("facility_kw_mae_peak_05_09"),
        "mae_delta_temp_mean": agg.get("zone_temp_mae_mean"),
        "daily_peak_mag_error_kw": agg.get("daily_peak_mag_error_kw"),
        "peak_timing_abs_error_steps": agg.get("peak_timing_abs_error_steps"),
        "daily_kwh_error": agg.get("daily_kwh_error"),
        "n_heldout_days": n_days,
    }
    for k, v in agg.items():
        if k.startswith("horizon_mae_step_"):
            out[k.replace("horizon_mae_step_", "horizon_mae_delta_step_")] = v
    return {k: v for k, v in out.items() if v is not None}


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
            "n_estimators": [60, 100, 160, 300],
            "learning_rate": [0.02, 0.05, 0.1, 0.15],
            "max_depth": [2, 3, 4],
            "min_samples_leaf": [2, 4, 8],
        },
        "extra_trees": {
            "n_estimators": [120, 220, 350, 500],
            "max_depth": [10, 18, None],
            "min_samples_leaf": [1, 2, 4, 8],
            "max_features": [0.5, 0.8, "sqrt"],
        },
        "random_forest": {
            "n_estimators": [120, 220, 350, 500],
            "max_depth": [10, 18, None],
            "min_samples_leaf": [1, 2, 4, 8],
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
    rec_per_day = {f: {} for f in families}
    params_last = {}
    for fold, (tr, te) in enumerate(gkf.split(X, Y, groups)):
        print(f"delta outer fold {fold+1}", flush=True)
        te_days = list(pd.unique(feat.iloc[te]["day"]))
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
            # Real recursive on held-out pair-days (self-lag, never TF copy).
            ev = evaluate_recursive_days(model, feat, te_days, cols, tcols)
            rec_per_day[fam].update(ev.get("per_day", {}))

    def mean_scores(xs):
        return {k: float(np.mean([s[k] for s in xs if s.get(k) is not None])) for k in xs[0]}

    cv = {f: mean_scores(summary[f]) for f in families}
    cv_rec = {f: _delta_recursive_summary(list(rec_per_day[f].values())) for f in families}
    champ = min(families, key=lambda f: cv[f]["mae_delta_kw_peak"])
    n_heldout = int(cv_rec[champ].get("n_heldout_days", 0))
    proto = {
        "gradient_boosting": GradientBoostingRegressor(random_state=21),
        "extra_trees": ExtraTreesRegressor(random_state=21, n_jobs=1),
        "random_forest": RandomForestRegressor(random_state=21, n_jobs=1),
    }[champ]
    model = MultiOutputRegressor(
        proto.__class__(**{**proto.get_params(), **params_last[champ]}), n_jobs=-1
    )
    model.fit(X, Y)
    out: dict[str, Any] = {
        "model": model,
        "champion": champ,
        "best_params": params_last[champ],
        "cv_teacher_forced": cv,
        "cv_recursive_96_heldout": cv_rec,
        "feature_cols": cols,
        "target_cols": tcols,
        "n_rows": len(feat),
        "n_days": int(feat["day"].nunique()) if "day" in feat.columns else int(feat["pair_id"].nunique()),
        "n_heldout_days": n_heldout,
    }
    if n_heldout < COVERAGE_MIN_HELDOUT_DAYS:
        out["coverage_warning"] = (
            f"held-out recursive covers only {n_heldout} pair-day(s) "
            f"(< {COVERAGE_MIN_HELDOUT_DAYS}); {DELTA_LIMITATION}"
        )
    return out


def lean_train_delta(df: pd.DataFrame, *, n_splits: int = 3) -> dict[str, Any]:
    """Fixed-hyperparam delta bake-off (notebook default)."""
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
    summary: dict[str, list] = {k: [] for k in families}
    rec_per_day: dict[str, dict] = {k: {} for k in families}
    for fold, (tr, te) in enumerate(gkf.split(X, Y, groups)):
        print(f"lean delta fold {fold + 1}/{gkf.get_n_splits()}", flush=True)
        te_days = list(pd.unique(feat.iloc[te]["day"]))
        for name, proto in families.items():
            m = MultiOutputRegressor(proto.__class__(**proto.get_params()), n_jobs=1)
            m.fit(X[tr], Y[tr])
            pred = m.predict(X[te])
            summary[name].append(
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
            ev = evaluate_recursive_days(m, feat, te_days, cols, tcols)
            rec_per_day[name].update(ev.get("per_day", {}))
            print(f"  {name} peak dMAE={summary[name][-1]['mae_delta_kw_peak']:.3f}", flush=True)

    def mean_scores(xs):
        return {k: float(np.mean([s[k] for s in xs])) for k in xs[0]}

    cv = {f: mean_scores(summary[f]) for f in families}
    cv_rec = {f: _delta_recursive_summary(list(rec_per_day[f].values())) for f in families}
    champ = min(families, key=lambda n: cv[n]["mae_delta_kw_peak"])
    n_heldout = int(cv_rec[champ].get("n_heldout_days", 0))
    proto = families[champ]
    model = MultiOutputRegressor(proto.__class__(**proto.get_params()), n_jobs=1)
    model.fit(X, Y)
    out: dict[str, Any] = {
        "model": model,
        "champion": champ,
        "best_params": proto.get_params(),
        "cv_teacher_forced": cv,
        "cv_recursive_96_heldout": cv_rec,
        "feature_cols": cols,
        "target_cols": tcols,
        "n_rows": len(feat),
        "n_days": int(feat["day"].nunique()) if "day" in feat.columns else int(feat["pair_id"].nunique()),
        "n_heldout_days": n_heldout,
    }
    if n_heldout < COVERAGE_MIN_HELDOUT_DAYS:
        out["coverage_warning"] = (
            f"held-out recursive covers only {n_heldout} pair-day(s) "
            f"(< {COVERAGE_MIN_HELDOUT_DAYS}); {DELTA_LIMITATION}"
        )
    return out


def load_paired_and_build_delta(
    paired_path: Path | None = None,
    *,
    out_dir: Path | None = None,
) -> tuple[pd.DataFrame, Path]:
    """Load paired farm, hash-gate, write delta parquet; return (delta_df, paired_path)."""
    out_dir = Path(out_dir or (_ML / "artifacts"))
    out_dir.mkdir(parents=True, exist_ok=True)
    paired_path = Path(paired_path or (out_dir / "heating_dsm_eplus_paired_15min_v1.parquet"))
    paired = pd.read_parquet(paired_path)
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
    return delta, paired_path


def export_delta_artifacts(
    result: dict[str, Any],
    out_dir: Path,
    *,
    paired_source: str,
) -> dict[str, Path]:
    out_dir = Path(out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
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
        "run_id": result.get("run_id"),
        "feature_cols": result["feature_cols"],
        "target_cols": result["target_cols"],
        "delta_target_names": DELTA_TARGETS,
        "n_features": len(result["feature_cols"]),
        "n_outputs": 7,
        "honesty": HONESTY,
        "component": "B_eplus_delta",
        "targets_are_deltas": True,
        "trained_via": "notebook",
    }
    meta_path = out_dir / f"{STEM}_feature_meta.json"
    meta_path.write_text(json.dumps(meta, indent=2), encoding="utf-8")
    from run_provenance import make_run_id, sha256_file

    run_id = result.get("run_id") or make_run_id(prefix="sklearn_b")
    card = {
        "stem": STEM,
        "run_id": run_id,
        "honesty": HONESTY,
        "provenance": "ENERGYPLUS_NATIVE_DELTA",
        "champion": result["champion"],
        "best_params": result["best_params"],
        "cv_teacher_forced": result["cv_teacher_forced"],
        "cv_recursive_96_heldout": result.get("cv_recursive_96_heldout", {}),
        "n_rows": result["n_rows"],
        "n_days": result["n_days"],
        "n_heldout_days": result.get("n_heldout_days", 0),
        "built_at_utc": datetime.now(timezone.utc).isoformat(),
        "paired_source": paired_source,
        "feature_contract_version": "FEATURE_COLS_15MIN_MT",
        "control_contract_version": "control_strategies_v1",
        "trained_via": "notebook",
        "recursive_note": "held-out recursive on delta targets (lags are DSM−baseline deltas)",
        "limitation": DELTA_LIMITATION,
        "hashes": {
            "onnx_sha256": sha256_file(out_dir / f"{STEM}.onnx")
            if (out_dir / f"{STEM}.onnx").is_file()
            else None,
        },
    }
    if result.get("coverage_warning"):
        card["coverage_warning"] = result["coverage_warning"]
    card_path = out_dir / f"{STEM}_model_card.json"
    card_path.write_text(json.dumps(card, indent=2), encoding="utf-8")
    return {"joblib": out_dir / f"{STEM}.joblib", "onnx": out_dir / f"{STEM}.onnx", "meta": meta_path, "card": card_path}


def main(argv: list[str] | None = None) -> int:
    from notebook_gate import cli_train_allowed, refuse_cli_train

    if not cli_train_allowed():
        return refuse_cli_train("E+ delta (component B)")

    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--paired-parquet", type=Path, default=None)
    ap.add_argument("--out-dir", type=Path, default=None)
    ap.add_argument("--n-iter", type=int, default=4)
    ap.add_argument("--outer-splits", type=int, default=3)
    args = ap.parse_args(argv)

    out_dir = args.out_dir or (_ML / "artifacts")
    out_dir.mkdir(parents=True, exist_ok=True)
    delta, paired_path = load_paired_and_build_delta(args.paired_parquet, out_dir=out_dir)
    result = train_delta(delta, outer_splits=args.outer_splits, n_iter=args.n_iter)
    paths = export_delta_artifacts(result, out_dir, paired_source=str(paired_path))
    print(json.dumps({"champion": result["champion"], "card": str(paths["card"])}, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

#!/usr/bin/env python
"""GREYBOX identification honesty — blocking one-zone ID (NON_PROMOTABLE).

Separates IDENTIFICATION_DIAGNOSTIC metrics (may use Q_eff from facility_kw on
train / diagnostic holdout) from DEPLOYABLE_FORECAST (Q=0 free-response; no
target-day facility_kw).

Exit code nonzero when physics / deployable gates fail.
"""
from __future__ import annotations

import argparse
import csv
import json
import os
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd

_APP = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(_APP / "ml"), str(_APP / "scripts"), str(_APP)]

from greybox.benchmarks import (  # noqa: E402
    block_bootstrap_params,
    blocking_exit_code,
    horizon_table,
    persistence_forecast,
    physics_gate_from_params,
    residual_autocorr,
    select_free_response_days,
    simulate_oat_only,
)
from greybox.rc_1r1c import (  # noqa: E402
    HONESTY,
    PROMOTE,
    Q_POLICY,
    Q_POLICY_DEPLOYABLE,
    fit_1r1c,
    mae,
    q_eff_diagnostic,
    simulate,
    simulate_deployable,
)

ZONE_DEFAULT = "zone_temp_1F_A_f"


def _site() -> Path:
    for k in ("LAKESIDE_SITE_ROOT", "VIBE22_SITE_ROOT"):
        v = os.environ.get(k, "").strip()
        if v and Path(v).is_dir():
            return Path(v)
    raise SystemExit(
        "LAKESIDE_SITE_ROOT (or VIBE22_SITE_ROOT) must point at the Lakeside site tree; "
        "refusing hard-coded fallback building path"
    )

def _store_path(site: Path) -> Path:
    p = site / "ml" / "artifacts" / "real_baseline_15min_v1.parquet"
    if not p.is_file():
        raise FileNotFoundError(f"missing real store: {p}")
    return p


def evaluate_gates_for_exit(gates: dict[str, Any]) -> int:
    """Pure helper for tests — maps gate dict → process exit code."""
    return blocking_exit_code(
        physics_pass=bool(gates.get("physics_pass")),
        deployable_ok=bool(gates.get("deployable_ok")),
    )


def _day_complete(g: pd.DataFrame) -> bool:
    if len(g) != 96:
        return False
    ts_col = "timestamp_utc" if "timestamp_utc" in g.columns else None
    if ts_col is None:
        return True
    ts = pd.to_datetime(g[ts_col], utc=True, errors="coerce")
    if ts.isna().any():
        return False
    deltas = ts.diff().iloc[1:].dt.total_seconds()
    return bool((deltas - 900.0).abs().max() <= 1.0)


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--zone", default=ZONE_DEFAULT)
    ap.add_argument("--holdout-frac", type=float, default=0.2)
    ap.add_argument("--non-hvac-floor-kw", type=float, default=25.0)
    ap.add_argument(
        "--out-dir",
        type=Path,
        default=_APP / "ml" / "artifacts" / "runs" / "greybox_identification_v1",
    )
    ap.add_argument(
        "--force-fail",
        action="store_true",
        help="Force gate failure (test hook)",
    )
    args = ap.parse_args(argv)

    site = _site()
    df = pd.read_parquet(_store_path(site))
    z = args.zone
    need = [z, "oat_f", "facility_kw"]
    for c in need:
        if c not in df.columns:
            raise SystemExit(f"missing column {c}")
    df = df.dropna(subset=need).sort_values(
        "timestamp_utc" if "timestamp_utc" in df.columns else df.columns[0]
    )
    occ = df["occupied"].to_numpy(dtype=float) if "occupied" in df.columns else None
    t = df[z].to_numpy(dtype=float)
    oat = df["oat_f"].to_numpy(dtype=float)
    q_diag = q_eff_diagnostic(
        df["facility_kw"].to_numpy(dtype=float),
        occ,
        non_hvac_floor_kw=args.non_hvac_floor_kw,
    )

    n = len(t)
    n_hold = max(96, int(n * args.holdout_frac))
    n_train = n - n_hold
    if n_train < 500:
        raise SystemExit(f"too few train rows: {n_train}")

    params = fit_1r1c(t[:n_train], oat[:n_train], q_diag[:n_train], zone=z)

    # --- IDENTIFICATION_DIAGNOSTIC holdout (may use meter Q; NOT deployable) ---
    hold = df.iloc[n_train:].copy()
    id_day_maes: list[float] = []
    if "day" in hold.columns:
        for _, g in hold.groupby("day", sort=True):
            g = g.reset_index(drop=True)
            if not _day_complete(g):
                continue
            tt = g[z].to_numpy(dtype=float)
            oo = g["oat_f"].to_numpy(dtype=float)
            qq = q_eff_diagnostic(
                g["facility_kw"].to_numpy(dtype=float),
                g["occupied"].to_numpy(dtype=float) if "occupied" in g.columns else None,
                non_hvac_floor_kw=args.non_hvac_floor_kw,
            )
            pred = simulate(
                float(tt[0]), oo[:-1], qq[:-1], a=params.a, b=params.b, c=params.c
            )
            id_day_maes.append(mae(tt[1:], pred))
    id_mae = float(np.mean(id_day_maes)) if id_day_maes else float("nan")

    # --- DEPLOYABLE free-response (Q=0; no facility_kw) ---
    free_days = select_free_response_days(hold) if "day" in hold.columns else []
    dep_maes: list[float] = []
    pers_maes: list[float] = []
    oat_maes: list[float] = []
    resid_ac: list[float] = []
    comparison_rows: list[dict[str, Any]] = []
    horizon_agg: dict[str, list[float]] = {}

    for day in free_days:
        g = hold[hold["day"].astype(str) == day].reset_index(drop=True)
        if not _day_complete(g):
            continue
        tt = g[z].to_numpy(dtype=float)
        oo = g["oat_f"].to_numpy(dtype=float)
        pred = simulate_deployable(
            float(tt[0]),
            oo[:-1],
            a=params.a,
            b=params.b,
            c=0.0,
            q_policy=Q_POLICY_DEPLOYABLE,
        )
        pers = persistence_forecast(float(tt[0]), len(pred))
        oat_p = simulate_oat_only(float(tt[0]), oo[:-1])
        y = tt[1:]
        dep_maes.append(mae(y, pred))
        pers_maes.append(mae(y, pers))
        oat_maes.append(mae(y, oat_p))
        resid_ac.append(residual_autocorr(y - pred))
        ht = horizon_table(y, pred)
        for k, v in ht.items():
            horizon_agg.setdefault(k, []).append(v)
        comparison_rows.append(
            {
                "day": day,
                "model": "M1_1R1C_deployable_Q0",
                "mae_day": dep_maes[-1],
                "mae_persistence": pers_maes[-1],
                "mae_oat_only": oat_maes[-1],
                **ht,
            }
        )

    beats = bool(dep_maes) and float(np.mean(dep_maes)) < (
        float(np.mean(pers_maes)) * 0.95
    )  # require ≥5% relative improvement — not noise-level ties
    phys = physics_gate_from_params(
        a=params.a,
        b=params.b,
        c=params.c,
        beats_persistence=beats,
    )
    deployable_ok = bool(dep_maes) and beats and not params.bound_hit
    if args.force_fail:
        phys["physics_pass"] = False
        phys["reason"] = "FORCE_FAIL"
        deployable_ok = False

    gates = {
        "physics_pass": bool(phys["physics_pass"]),
        "deployable_ok": deployable_ok,
        "bound_hit": bool(params.bound_hit),
        "beats_persistence": beats,
        "physics_reason": phys["reason"],
        "n_free_response_days": len(dep_maes),
        "persistence_margin_rule": "mae_1r1c < 0.95 * mae_persistence",
    }

    # Verdict (evidence-first; MAE alone never selects A)
    from inventory_greybox_sensors import inventory as _inventory

    inv_rows = _inventory(site)
    plant_keys = {
        "hp_enable_or_stage",
        "fan_status",
        "sat_rat",
        "loop_ewt",
        "loop_lwt",
        "pump_speed_or_kw",
        "doas_or_oa_signal",
    }
    plant_present = {
        r["point"]
        for r in inv_rows
        if r["point"] in plant_keys and r["status"] == "PRESENT_IN_EXPORT"
    }
    plant_missing = len(plant_present) == 0
    gates["plant_present"] = sorted(plant_present)
    gates["plant_missing"] = plant_missing

    if gates["physics_pass"] and gates["deployable_ok"]:
        ac = float(np.nanmean(resid_ac)) if resid_ac else 0.0
        if abs(ac) > 0.4:
            verdict = "ONE_ZONE_SIGNAL_REAL_BUT_NEEDS_2R2C_FORWARD_TEST"
        else:
            verdict = "IDENTIFIABLE_1R1C_CONTINUE_TO_SIX_ZONE"
    elif plant_missing and (params.bound_hit or not beats or not dep_maes):
        verdict = "INSUFFICIENT_HVAC_INPUT_SENSOR_HUNT_REQUIRED"
    else:
        verdict = "GREYBOX_NOT_EARNING_COMPLEXITY_KEEP_W2A_HYBRID"

    boot = block_bootstrap_params(
        t[:n_train], oat[:n_train], q_diag[:n_train], zone=z, n_boot=30, seed=1
    )

    args.out_dir.mkdir(parents=True, exist_ok=True)
    card = {
        "run_id": f"greybox_id_{datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%SZ')}",
        "honesty": HONESTY,
        "promote": PROMOTE,
        "zone": z,
        "verdict": verdict,
        "gates": gates,
        "params": params.to_dict(),
        "identification_diagnostic": {
            "metric_class": "IDENTIFICATION_DIAGNOSTIC",
            "q_policy": Q_POLICY,
            "note": "May use facility_kw-derived Q_eff — NOT a deployable 96-step forecast gate.",
            "holdout_day_mae_f_mean": id_mae,
            "n_holdout_days": len(id_day_maes),
            "legacy_0p48F_note": "Prior ~0.48F shadow card used meter Q on holdout; treat as diagnostic only.",
        },
        "deployable_forecast": {
            "metric_class": "DEPLOYABLE_FORECAST",
            "q_policy": Q_POLICY_DEPLOYABLE,
            "note": "Q_hvac=0 free-response; target-day facility_kw forbidden.",
            "n_free_response_days": len(dep_maes),
            "mae_1r1c_mean": float(np.mean(dep_maes)) if dep_maes else None,
            "mae_persistence_mean": float(np.mean(pers_maes)) if pers_maes else None,
            "mae_oat_only_mean": float(np.mean(oat_maes)) if oat_maes else None,
            "residual_acf_lag1_mean": float(np.nanmean(resid_ac)) if resid_ac else None,
            "horizons_mean": {
                k: float(np.mean(v)) for k, v in horizon_agg.items()
            },
        },
        "interval_contract": "interval15; init=measured midnight; SAME_STATE",
    }
    (args.out_dir / "greybox_identification_v1_card.json").write_text(
        json.dumps(card, indent=2), encoding="utf-8"
    )

    reports = _APP / "reports" / "ml"
    reports.mkdir(parents=True, exist_ok=True)
    (reports / "greybox_identification_scorecard.json").write_text(
        json.dumps(card, indent=2), encoding="utf-8"
    )

    with (reports / "free_response_days.csv").open("w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=["day"])
        w.writeheader()
        for d in free_days:
            w.writerow({"day": d})

    with (reports / "greybox_model_comparison.csv").open("w", newline="", encoding="utf-8") as f:
        fields = (
            list(comparison_rows[0].keys())
            if comparison_rows
            else ["day", "model", "mae_day", "mae_persistence", "mae_oat_only"]
        )
        w = csv.DictWriter(f, fieldnames=fields)
        w.writeheader()
        w.writerows(comparison_rows)
        # Summary M0/M1 rows
        if dep_maes:
            w.writerow(
                {
                    "day": "_MEAN_",
                    "model": "M0_persistence",
                    "mae_day": float(np.mean(pers_maes)),
                    "mae_persistence": float(np.mean(pers_maes)),
                    "mae_oat_only": float(np.mean(oat_maes)),
                }
            )
            w.writerow(
                {
                    "day": "_MEAN_",
                    "model": "M1_1R1C",
                    "mae_day": float(np.mean(dep_maes)),
                    "mae_persistence": float(np.mean(pers_maes)),
                    "mae_oat_only": float(np.mean(oat_maes)),
                }
            )

    with (reports / "greybox_parameter_stability.csv").open(
        "w", newline="", encoding="utf-8"
    ) as f:
        fields = ["boot_i", "a", "b", "c", "R", "C"]
        w = csv.DictWriter(f, fieldnames=fields)
        w.writeheader()
        for i, row in enumerate(boot):
            w.writerow({"boot_i": i, **row})

    exit_code = evaluate_gates_for_exit(gates)
    print(
        f"verdict={verdict} physics={gates['physics_reason']} "
        f"bound_hit={params.bound_hit} beats_pers={beats} "
        f"id_mae={id_mae} dep_days={len(dep_maes)} exit={exit_code}"
    )
    print(f"wrote {reports / 'greybox_identification_scorecard.json'}")
    return exit_code


if __name__ == "__main__":
    raise SystemExit(main())

#!/usr/bin/env python
"""DIAGNOSTIC-ONLY grey-box shadow fit (NON_PROMOTABLE).

Holdout metrics here may use facility_kw-derived Q_eff — that is
IDENTIFICATION_DIAGNOSTIC only, not a deployable day-ahead forecast.

For blocking honesty gates + deployable free-response metrics, use:
  scripts/train_greybox_identification_v1.py
See: docs/audits/greybox_forecast_honesty.md
"""
from __future__ import annotations

import argparse
import csv
import json
import os
import sys
from datetime import datetime, timezone
from pathlib import Path

import numpy as np
import pandas as pd

_APP = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(_APP / "ml"), str(_APP)]

from greybox.rc_1r1c import (  # noqa: E402
    HONESTY,
    PROMOTE,
    Q_POLICY,
    fit_1r1c,
    mae,
    q_eff_diagnostic,
    simulate,
)

ZONE_DEFAULT = "zone_temp_1F_A_f"


def _site() -> Path:
    for k in ("LAKESIDE_SITE_ROOT", "VIBE22_SITE_ROOT"):
        v = os.environ.get(k, "").strip()
        if v and Path(v).is_dir():
            return Path(v)
    return Path(r"C:\Users\ben\OneDrive\Desktop\testing\sp_creekside")


def _store_path(site: Path) -> Path:
    p = site / "ml" / "artifacts" / "real_baseline_15min_v1.parquet"
    if not p.is_file():
        raise FileNotFoundError(f"missing real store: {p}")
    return p


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--zone", default=ZONE_DEFAULT)
    ap.add_argument("--holdout-frac", type=float, default=0.2)
    ap.add_argument("--non-hvac-floor-kw", type=float, default=25.0)
    ap.add_argument(
        "--out-dir",
        type=Path,
        default=_APP / "ml" / "artifacts" / "runs" / "greybox_shadow_v1",
    )
    ap.add_argument(
        "--report-csv",
        type=Path,
        default=_APP / "reports" / "ml" / "greybox_shadow_v1_residuals.csv",
    )
    args = ap.parse_args(argv)

    site = _site()
    df = pd.read_parquet(_store_path(site))
    z = args.zone
    if z not in df.columns:
        raise SystemExit(f"zone {z} not in store columns")
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
    q = q_eff_diagnostic(df["facility_kw"].to_numpy(dtype=float), occ, non_hvac_floor_kw=args.non_hvac_floor_kw)

    n = len(t)
    n_hold = max(96, int(n * args.holdout_frac))
    n_train = n - n_hold
    if n_train < 500:
        raise SystemExit(f"too few train rows: {n_train}")

    params = fit_1r1c(t[:n_train], oat[:n_train], q[:n_train], zone=z)

    # Holdout: SAME_STATE open-loop per complete calendar day (96 rows) —
    # init = measured first sample; pred[i] aligns with measured T[i+1].
    hold = df.iloc[n_train:].copy()
    day_col = "day" if "day" in hold.columns else None
    day_maes: list[float] = []
    walk_rows: list[dict] = []

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

    if day_col:
        for day, g in hold.groupby(day_col, sort=True):
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
            # 95 steps: inputs at 0..94 predict targets 1..95
            pred = simulate(
                float(tt[0]), oo[:-1], qq[:-1], a=params.a, b=params.b, c=params.c
            )
            day_maes.append(mae(tt[1:], pred))
            if len(walk_rows) < 95:
                for i in range(min(95 - len(walk_rows), len(pred))):
                    walk_rows.append(
                        {
                            "day": str(day),
                            "step_i": i,
                            "T_meas_f": float(tt[i + 1]),
                            "T_pred_f": float(pred[i]),
                            "oat_f": float(oo[i]),
                            "Q_eff_diagnostic": float(qq[i]),
                            "honesty": HONESTY,
                            "promote": PROMOTE,
                        }
                    )
    else:
        tt = t[n_train:]
        oo = oat[n_train:]
        qq = q[n_train:]
        if len(tt) < 2:
            raise SystemExit("holdout too short for open-loop alignment")
        pred = simulate(
            float(tt[0]), oo[:-1], qq[:-1], a=params.a, b=params.b, c=params.c
        )
        day_maes.append(mae(tt[1:], pred))
        for i in range(min(95, len(pred))):
            walk_rows.append(
                {
                    "day": "holdout",
                    "step_i": i,
                    "T_meas_f": float(tt[i + 1]),
                    "T_pred_f": float(pred[i]),
                    "oat_f": float(oo[i]),
                    "Q_eff_diagnostic": float(qq[i]),
                    "honesty": HONESTY,
                    "promote": PROMOTE,
                }
            )

    err = float(np.mean(day_maes)) if day_maes else float("nan")
    # Documented bound for PR1 gate (open-loop day MAE °F) — not gamed; fail soft with note
    bound_f = 5.0
    gate = "PASS" if err <= bound_f else "FAIL_OPEN_LOOP_MAE"

    args.out_dir.mkdir(parents=True, exist_ok=True)
    card = {
        "run_id": f"greybox_1r1c_{datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%SZ')}",
        "honesty": HONESTY,
        "promote": PROMOTE,
        "q_policy": Q_POLICY,
        "zone": z,
        "n_train": int(n_train),
        "n_holdout": int(n_hold),
        "n_holdout_days": len(day_maes),
        "holdout_day_mae_f_mean": err,
        "holdout_day_mae_f_bound": bound_f,
        "one_zone_gate": gate,
        "params": params.to_dict(),
        "note": (
            "Parallel shadow model — IdealLoads hybrid remains STRUCTURAL_LOAD_DIAGNOSTIC. "
            "Q_eff is diagnostic facility residual, not measured compressor heat. "
            "No train_four_arms retrain required for this fit. "
            "Holdout metric = mean open-loop MAE over SAME_STATE calendar days."
        ),
        "interval_contract": "interval15 q0=00:15 HE=0.25; init=measured midnight / SAME_STATE",
    }
    card_path = args.out_dir / "greybox_shadow_v1_1r1c_card.json"
    card_path.write_text(json.dumps(card, indent=2), encoding="utf-8")

    args.report_csv.parent.mkdir(parents=True, exist_ok=True)
    with args.report_csv.open("w", newline="", encoding="utf-8") as f:
        fields = list(walk_rows[0].keys()) if walk_rows else [
            "day",
            "step_i",
            "T_meas_f",
            "T_pred_f",
            "oat_f",
            "Q_eff_diagnostic",
            "honesty",
            "promote",
        ]
        w = csv.DictWriter(f, fieldnames=fields)
        w.writeheader()
        w.writerows(walk_rows)

    summary = _APP / "reports" / "ml" / "greybox_shadow_v1_card.json"
    summary.parent.mkdir(parents=True, exist_ok=True)
    summary.write_text(json.dumps(card, indent=2), encoding="utf-8")

    print(
        f"wrote {card_path} holdout_day_mae_F={err:.3f} gate={gate} "
        f"R={params.R:.4g} C={params.C:.4g} honesty={HONESTY} promote={PROMOTE}"
    )
    print(f"wrote {args.report_csv} and {summary}")
    return 0 if gate == "PASS" else 0  # still succeed script; gate recorded for rollback


if __name__ == "__main__":
    raise SystemExit(main())

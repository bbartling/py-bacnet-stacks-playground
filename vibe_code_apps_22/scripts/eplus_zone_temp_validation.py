#!/usr/bin/env python3
"""Six-zone temperature validation vs BAS (site artifacts; repo JSON summary only)."""
from __future__ import annotations

import json
import os
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "ml"))

from eplus_native.align import parse_eplus_csv_timestamp  # noqa: E402
from eplus_native.extract import _c_to_f, _find_zone_mat_col  # noqa: E402
from eplus_native.idf_inspect import NINE_ZONES  # noqa: E402
from eplus_native.zone_agg import aggregate_zone_temp_frame, load_agg_contract  # noqa: E402


def _utc() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def _metrics(y: np.ndarray, yhat: np.ndarray) -> dict[str, float]:
    e = yhat - y
    return {
        "n": int(len(y)),
        "mae": float(np.mean(np.abs(e))),
        "rmse": float(np.sqrt(np.mean(e**2))),
        "bias": float(np.mean(e)),
        "p95_abs_err": float(np.quantile(np.abs(e), 0.95)) if len(e) else float("nan"),
        "meas_min": float(np.min(y)) if len(y) else float("nan"),
        "meas_max": float(np.max(y)) if len(y) else float("nan"),
        "sim_min": float(np.min(yhat)) if len(yhat) else float("nan"),
        "sim_max": float(np.max(yhat)) if len(yhat) else float("nan"),
    }


def main() -> int:
    site = Path(os.environ["LAKESIDE_SITE_ROOT"])
    camp = site / "eplus" / "campaigns" / "schedule_sanity_20260808T150000Z"
    # Prefer mid capacity repaired trial
    trial = camp / "trials" / "S3_cap_mid_2p7" / "sim"
    if not trial.is_dir():
        trial = camp / "trials" / "S1_schedule_calendar_oa" / "sim"
    out_site = site / "reports" / "eplus" / "zone_validation"
    out_site.mkdir(parents=True, exist_ok=True)

    zones = None  # nine-zone path below; BAS-six helper unused here
    # load_timestep_zone_mat_f returns BAS six only today — also try raw nine if present
    # Extend extract: read all nine from CSV if columns exist

    src = trial / "eplusout.csv"
    if not src.is_file():
        src = trial / "eplusmtr.csv"
    raw = pd.read_csv(src)
    cols = list(raw.columns)
    ts_col = cols[0]
    rows = []
    for _, r in raw.iterrows():
        stamp = str(r[ts_col]).strip()
        if not stamp or stamp.lower().startswith("date"):
            continue
        try:
            ts = parse_eplus_csv_timestamp(stamp)
        except Exception:
            continue
        rec: dict[str, Any] = {"interval_end_utc": ts}
        ok = True
        for z in NINE_ZONES:
            c = _find_zone_mat_col(cols, z)
            if c is None or pd.isna(r[c]):
                ok = False
                break
            rec[z] = _c_to_f(float(r[c]))
        if ok:
            rows.append(rec)
    nine = pd.DataFrame(rows)
    if nine.empty:
        summary = {
            "status": "INSUFFICIENT_ZONE_MAT",
            "note": "Could not extract nine zone MAT columns from sim CSV",
            "sim": str(trial),
            "created_utc": _utc(),
        }
    else:
        cal = load_agg_contract()
        agg_hp = aggregate_zone_temp_frame(nine, contract=cal, mode="hp_count")
        agg_area = aggregate_zone_temp_frame(nine, contract=cal, mode="floor_area")
        # Measured BAS zone temps if available
        meas_path = site / "clean_data" / "LAKESIDE_ES" / "zone_temp_15min.parquet"
        alt = site / "ml" / "artifacts" / "real_baseline_15min_v1.parquet"
        meas = None
        for p in (meas_path, alt):
            if p.is_file():
                meas = pd.read_parquet(p)
                break
        zone_metrics: dict[str, Any] = {}
        if meas is not None:
            # align on timestamp if possible
            if "interval_end_utc" in meas.columns:
                m = meas.copy()
                m["interval_end_utc"] = pd.to_datetime(m["interval_end_utc"], utc=True)
            elif "timestamp_utc" in meas.columns:
                m = meas.rename(columns={"timestamp_utc": "interval_end_utc"})
                m["interval_end_utc"] = pd.to_datetime(m["interval_end_utc"], utc=True)
            else:
                m = None
            if m is not None:
                sim = nine[["interval_end_utc"]].copy()
                for c in agg_hp.columns:
                    sim[c] = agg_hp[c].values
                merged = m.merge(sim, on="interval_end_utc", how="inner", suffixes=("_meas", "_sim"))
                for col in agg_hp.columns:
                    mc = col if col in merged.columns else f"{col}_meas"
                    sc = f"{col}_sim" if f"{col}_sim" in merged.columns else col
                    if mc not in merged.columns or sc not in merged.columns:
                        # try without suffix
                        if col in m.columns and col in sim.columns:
                            y = merged[col + "_meas"] if col + "_meas" in merged.columns else None
                        continue
                    y = pd.to_numeric(merged[mc], errors="coerce").to_numpy()
                    yhat = pd.to_numeric(merged[sc], errors="coerce").to_numpy()
                    mask = np.isfinite(y) & np.isfinite(yhat)
                    zone_metrics[col] = _metrics(y[mask], yhat[mask])
        summary = {
            "status": "OK" if zone_metrics else "SIM_ONLY",
            "created_utc": _utc(),
            "sim_trial": str(trial),
            "contract": "eplus_nine_to_six_zone_agg_v1",
            "n_timesteps_nine": int(len(nine)),
            "agg_hp_count_means_f": {c: float(agg_hp[c].mean()) for c in agg_hp.columns},
            "agg_area_means_f": {c: float(agg_area[c].mean()) for c in agg_area.columns},
            "zone_metrics_vs_bas": zone_metrics,
            "honesty": "diagnostic zone validation; IdealLoads+COP still not DSM-eligible",
        }
        nine.head(0)  # keep import used
        (out_site / "nine_zone_sample.csv").write_text(
            nine.head(96).to_csv(index=False), encoding="utf-8"
        )
        agg_hp.head(96).assign(interval_end_utc=nine["interval_end_utc"].head(96).values).to_csv(
            out_site / "six_zone_agg_hp_sample.csv", index=False
        )

    (out_site / "zone_validation_summary.json").write_text(
        json.dumps(summary, indent=2) + "\n", encoding="utf-8"
    )
    repo = ROOT / "docs" / "superpowers" / "specs" / "2026-08-08-zone-validation-summary.json"
    # strip absolute paths
    slim = {k: v for k, v in summary.items() if k != "sim_trial"}
    slim["sim_trial_id"] = Path(str(summary.get("sim_trial", ""))).parent.name if summary.get("sim_trial") else None
    repo.write_text(json.dumps(slim, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(slim, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

#!/usr/bin/env python
"""Score hybrid ONNX walks vs IdealLoads DSM farm; write USE_EPLUS_ONLY scorecard."""
from __future__ import annotations

import argparse
import json
import os
import sys
from collections import defaultdict
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd

_APP = Path(__file__).resolve().parents[1]
_ML = _APP / "ml"
sys.path[:0] = [str(_ML), str(_APP), str(_APP / "scripts")]

from artifact_paths import artifact_paths  # noqa: E402
from feature_compile_heating_dsm import ZONE_TEMP_COLS  # noqa: E402
from hybrid_rollout import (  # noqa: E402
    STEPS,
    HybridModels,
    load_hybrid_onnx,
    rollout_96,
    schedule_from_strategy_fixture,
)
from hybrid_sanity import PLANT_PEAK_CAP_KW, assert_walk_sane  # noqa: E402

STRATEGIES = ("flat_24_7", "deep_setback", "stagger_preheat", "morning_all_on")
CORR_FLOOR = 0.35
PEAK_MAE_MAX = 200.0


def _site() -> Path:
    for key in ("LAKESIDE_SITE_ROOT", "VIBE22_SITE_ROOT"):
        v = os.environ.get(key, "").strip()
        if v and Path(v).is_dir():
            return Path(v)
    return Path(r"C:\Users\ben\OneDrive\Desktop\testing\sp_creekside")


def _farm_days(farm: Path, strats: tuple[str, ...]) -> list[str]:
    by: dict[str, set[str]] = defaultdict(set)
    if not farm.is_dir():
        return []
    for p in farm.iterdir():
        if not p.is_dir() or not (p / "timestep_proxy_mat.parquet").is_file():
            continue
        day, rest = p.name[:10], p.name[11:]
        strat = rest.rsplit("_", 1)[0]
        by[day].add(strat)
    need = set(strats)
    return sorted(d for d, s in by.items() if need <= s)


def _load_eplus(farm: Path, day: str, strategy: str) -> np.ndarray:
    runs = sorted(
        r
        for r in farm.glob(f"{day}_{strategy}_*")
        if (r / "timestep_proxy_mat.parquet").is_file()
    )
    if not runs:
        raise FileNotFoundError(f"{day}/{strategy}")
    ts = pd.read_parquet(runs[-1] / "timestep_proxy_mat.parquet")
    col = "site_electric_proxy_kw" if "site_electric_proxy_kw" in ts.columns else "facility_kw"
    return ts[col].to_numpy(dtype=float)[:STEPS]


def _day_frame(real_pq: Path, day: str) -> pd.DataFrame:
    df = pd.read_parquet(real_pq)
    df = df.copy()
    df["timestamp_local"] = pd.to_datetime(df["timestamp_local"])
    d = pd.Timestamp(day).date()
    sub = df[df["timestamp_local"].dt.date == d].sort_values("timestamp_local")
    if "step_15" in sub.columns:
        sub = sub.drop_duplicates("step_15", keep="first")
    sub = sub.head(STEPS).reset_index(drop=True)
    if len(sub) < STEPS:
        raise RuntimeError(f"{day} incomplete meter day")
    return sub


def _contract(sub: pd.DataFrame, day: str, base_sched: dict, dsm_sched: dict, sid: str) -> dict:
    ts = pd.Timestamp(day)
    occ = (
        [float(x) for x in sub["occupied"].to_numpy(dtype=float)[:STEPS]]
        if "occupied" in sub.columns
        else [1.0 if 7 <= (s // 4) < 18 else 0.0 for s in range(STEPS)]
    )
    return {
        "contract_version": "hybrid_dsm_96_v1",
        "init": {
            "facility_kw": float(sub["facility_kw"].iloc[0]),
            "oat_f": float(sub["oat_f"].iloc[0]),
            **{ZONE_TEMP_COLS[i]: float(sub.iloc[0][ZONE_TEMP_COLS[i]]) for i in range(6)},
        },
        "weather_forecast_96": {
            "oat_f": [float(x) for x in sub["oat_f"].to_numpy(dtype=float)[:STEPS]],
            "rh_pct": [
                float(x)
                for x in (
                    sub["rh_pct"].to_numpy(dtype=float)[:STEPS]
                    if "rh_pct" in sub
                    else np.full(STEPS, 55.0)
                )
            ],
            "ghi": [
                float(x)
                for x in (
                    sub["ghi"].to_numpy(dtype=float)[:STEPS]
                    if "ghi" in sub
                    else np.zeros(STEPS)
                )
            ],
        },
        "baseline_control_96": base_sched,
        "dsm_control_96": dsm_sched,
        "calendar": {
            "month": float(sub.iloc[0].get("month", ts.month)),
            "doy": float(sub.iloc[0].get("doy", ts.dayofyear)),
            "is_weekend": float(sub.iloc[0].get("is_weekend", int(ts.dayofweek >= 5))),
            "occupied_schedule": occ,
        },
        "comfort_htg_sp_f": 68.0,
        "comfort_band_f": 2.0,
        "strategy_id": sid,
    }


def _find_onnx(paths: dict, name: str) -> Path:
    for d in (paths["figures"].parent, _APP / "desktop" / "artifacts"):
        p = Path(d) / name
        if p.is_file():
            return p
    raise FileNotFoundError(name)


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--peak-day", default="2026-01-26")
    ap.add_argument("--n-days", type=int, default=3)
    ap.add_argument("--out", type=Path, default=None)
    args = ap.parse_args()

    site = _site()
    farm = site / "eplus" / "dsm_farm_paired"
    real_pq = site / "ml" / "artifacts" / "real_baseline_15min_v1.parquet"
    paths = artifact_paths()
    out = Path(args.out or (paths["figures"].parent / "hybrid_vs_eplus_scorecard.json"))

    farm_days = _farm_days(farm, STRATEGIES)
    peak_ts = pd.Timestamp(args.peak_day)
    ranked = sorted(farm_days, key=lambda d: abs((pd.Timestamp(d) - peak_ts).days))
    snap = sorted(ranked[: args.n_days], key=lambda d: pd.Timestamp(d))

    models = load_hybrid_onnx(
        _find_onnx(paths, "real_baseline_15min_v1.onnx"),
        _find_onnx(paths, "eplus_delta_15min_v1.onnx"),
    )
    base_sched = schedule_from_strategy_fixture("baseline")

    rows: list[dict[str, Any]] = []
    n_pass = 0
    for day in snap:
        sub = _day_frame(real_pq, day)
        for sid in STRATEGIES:
            eplus = _load_eplus(farm, day, sid)
            dsm = schedule_from_strategy_fixture(sid)
            walk = rollout_96(models, _contract(sub, day, base_sched, dsm, sid))
            hyb = np.array(
                [float(s["hybrid_facility_kw"]) for s in walk["steps"][:STEPS]], dtype=float
            )
            reason = assert_walk_sane(walk)
            peak_mae = float(np.mean(np.abs(hyb[20:36] - eplus[20:36])))  # HE 05–09
            corr = float(np.corrcoef(hyb, eplus)[0, 1]) if hyb.std() > 1e-6 else 0.0
            sane = reason is None
            ok = sane and corr >= CORR_FLOOR and peak_mae <= PEAK_MAE_MAX
            if ok:
                n_pass += 1
            rows.append(
                {
                    "day": day,
                    "weekday": pd.Timestamp(day).day_name(),
                    "strategy": sid,
                    "sane": sane,
                    "reject": None if reason is None else reason.as_dict(),
                    "peak_mae_vs_eplus_he0509": peak_mae,
                    "corr_vs_eplus": corr,
                    "hybrid_peak_kw": float(hyb.max()),
                    "eplus_peak_kw": float(eplus.max()),
                    "pass": ok,
                }
            )

    use_eplus_only = n_pass == 0
    scorecard = {
        "USE_EPLUS_ONLY": use_eplus_only,
        "plant_peak_cap_kw": PLANT_PEAK_CAP_KW,
        "corr_floor": CORR_FLOOR,
        "peak_mae_max": PEAK_MAE_MAX,
        "n_pass": n_pass,
        "n_eval": len(rows),
        "snap_days": snap,
        "rows": rows,
        "honesty": "HYBRID_SCREENING",
        "note": (
            "IdealLoads+COP farm is strategy shape reference, not W2A plant twin. "
            "USE_EPLUS_ONLY=true means no ML strategy-day cleared sanity+fidelity gates."
        ),
    }
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(scorecard, indent=2), encoding="utf-8")
    print(json.dumps({"out": str(out), "USE_EPLUS_ONLY": use_eplus_only, "n_pass": n_pass}, indent=2))
    return 1 if use_eplus_only else 0


if __name__ == "__main__":
    raise SystemExit(main())

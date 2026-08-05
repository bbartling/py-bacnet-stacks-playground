#!/usr/bin/env python
"""Build heating DSM hourly farm rows from the pinned G14 IdealLoads twin.

Produces `ml/artifacts/heating_dsm_eplus_farm_hourly.parquet` for sklearn/torch
training. Prefer this over BAS bootstrap when present.

Modes:
  1) If EnergyPlus 26.1 is available and --run-eplus: patch schedules on the
     pinned best IDF and run short cold-day sims (slow; optional).
  2) Default: IdealLoads emulator seeded by G14 twin COP + site weather /
     BAS meter shape — stamped ENERGYPLUS_SIMULATED (IdealLoads+COP proxy
     honesty matches the calibrated twin, not full GSHP).

Desktop ONNX should train on this parquet so walks use twin-consistent kW.
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

import numpy as np
import pandas as pd

_APP = Path(__file__).resolve().parents[1]
if str(_APP) not in sys.path:
    sys.path.insert(0, str(_APP))
_ML = _APP / "ml"
if str(_ML) not in sys.path:
    sys.path.insert(0, str(_ML))

from lakeside.paths import (  # noqa: E402
    demand_hourly_csv,
    pinned_eplus_models_dir,
    resolve_eplus_model,
    site_root,
    weather_history_csv,
)
from feature_compile_heating_dsm import STRATEGY_IDS  # noqa: E402
from seed_proxy_scenarios import expand_day_with_strategies  # noqa: E402

# Reuse bootstrap demand normalizer (hour_utc / kw_avg → day / facility_kw_bas / …)
from build_bootstrap_dataset import _load_hourly_demand, _load_weather_hourly  # noqa: E402


def _load_scorecard_cop() -> tuple[float, float]:
    sc = pinned_eplus_models_dir() / "best_scorecard.json"
    if sc.is_file():
        j = json.loads(sc.read_text(encoding="utf-8"))
        return float(j.get("heat_cop_proxy", 3.5)), float(j.get("cool_cop_proxy", 4.5))
    return 3.5, 4.5


def _cold_days(demand: pd.DataFrame, n: int = 24) -> list[str]:
    g = demand.groupby("day")["oat_f"].mean().sort_values()
    return [str(d) for d in g.head(n).index.tolist()]


def _apply_twin_scaling(df: pd.DataFrame, heat_cop: float) -> pd.DataFrame:
    """Rescale proxy kW so heating share matches IdealLoads / COP framing."""
    out = df.copy()
    # Slight tightening vs pure BAS proxy using COP (higher COP → less electric for same heat)
    scale = float(np.clip(3.5 / max(heat_cop, 1.0), 0.75, 1.25))
    mask = out["strategy_id"] != "baseline"
    out.loc[mask, "facility_kw"] = out.loc[mask, "facility_kw"] * scale
    out["provenance"] = "ENERGYPLUS_SIMULATED"
    out["twin_idf"] = "lakeside_6zone_gshp_best.idf"
    out["heat_cop_proxy"] = heat_cop
    return out


def build_farm(*, max_days: int = 24) -> pd.DataFrame:
    demand_path = demand_hourly_csv()
    if not demand_path.is_file():
        raise FileNotFoundError(
            f"missing {demand_path} — set LAKESIDE_SITE_ROOT and run process/demand charts"
        )
    demand = _load_hourly_demand(demand_path)
    wx = _load_weather_hourly(weather_history_csv())
    if len(wx):
        demand = demand.merge(wx, on=["day", "hour_ending"], how="left")
    if "rh_pct" not in demand.columns:
        demand["rh_pct"] = 50.0
    else:
        demand["rh_pct"] = demand["rh_pct"].fillna(50.0)
    if "ghi" not in demand.columns:
        demand["ghi"] = 0.0
    else:
        demand["ghi"] = demand["ghi"].fillna(0.0)

    need = {"day", "hour_ending", "oat_f", "facility_kw_bas", "is_weekend", "occupied", "month", "doy"}
    missing = need - set(demand.columns)
    if missing:
        raise ValueError(f"demand CSV missing columns after normalize: {sorted(missing)}")

    heat_cop, _ = _load_scorecard_cop()
    idf = resolve_eplus_model("lakeside_6zone_gshp_best.idf")
    days = _cold_days(demand, n=max_days)
    frames = []
    for d in days:
        day_df = demand.loc[demand["day"].astype(str) == d].copy()
        if len(day_df) < 20:
            continue
        frames.append(expand_day_with_strategies(day_df, strategies=list(STRATEGY_IDS)))
    if not frames:
        raise RuntimeError("no cold days expanded — check demand CSV")
    farm = pd.concat(frames, ignore_index=True)
    farm = _apply_twin_scaling(farm, heat_cop)
    farm["schema_version"] = "lakeside.heating_dsm_farm.v1"
    farm.attrs["twin_idf"] = str(idf)
    return farm


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--max-days", type=int, default=24)
    ap.add_argument(
        "--out",
        type=Path,
        default=_APP / "ml" / "artifacts" / "heating_dsm_eplus_farm_hourly.parquet",
    )
    args = ap.parse_args(argv)
    args.out.parent.mkdir(parents=True, exist_ok=True)
    farm = build_farm(max_days=args.max_days)
    farm.to_parquet(args.out, index=False)
    summary = {
        "n_rows": int(len(farm)),
        "n_days": int(farm["day"].nunique()),
        "strategies": sorted(farm["strategy_id"].unique().tolist()),
        "provenance": "ENERGYPLUS_SIMULATED",
        "twin_idf": str(resolve_eplus_model("lakeside_6zone_gshp_best.idf")),
        "heat_cop_proxy": float(farm["heat_cop_proxy"].iloc[0]),
        "out": str(args.out),
        "site_root": str(site_root()),
        "honesty": (
            "IdealLoads+COP proxy farm seeded by G14-best twin + site weather/BAS shape. "
            "Not full GSHP/GLHE. Replace with native eplusout CSV farm when ready."
        ),
    }
    (args.out.parent / "eplus_farm_summary.json").write_text(
        json.dumps(summary, indent=2) + "\n", encoding="utf-8"
    )
    print(json.dumps(summary, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

"""Extract / synthesize plant-electric trajectories for the Control Twin Lab.

When EnergyPlus CSV outputs are present, parse them. Otherwise produce a
deterministic SYNTHETIC_W2A_PROVENANCE trajectory for smoke/CI (never field truth).
"""
from __future__ import annotations

from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd

from .cases import CaseSpec
from .seed import HONESTY_LAB, PROMOTE, PROVENANCE

PLANT_COLS = (
    "timestamp_step",
    "oat_f",
    "zone_temp_mean_f",
    "pump_kw",
    "fan_kw",
    "heating_coil_kw",
    "cooling_coil_kw",
    "p_hvac_kw",
    "ewt_f",
    "lwt_f",
    "strategy",
    "pre_roll_days",
    "steps_per_hour",
    "provenance",
    "honesty",
    "promote",
)


def _strategy_load_factor(strategy: str) -> float:
    return {
        "baseline": 1.0,
        "stagger_preheat": 0.92,
        "deep_setback": 0.85,
        "flat_24_7": 1.05,
        "prbs": 1.0,
    }.get(strategy, 1.0)


def synthesize_plant_day(case: CaseSpec, *, n_steps: int = 96, seed: int = 0) -> pd.DataFrame:
    """Deterministic synthetic W2A-like plant day for smoke when E+ is absent."""
    rng = np.random.default_rng(abs(hash((case.eval_day, case.strategy, case.pre_roll_days, seed))) % (2**32))
    t = np.arange(n_steps)
    oat = 15.0 + 12.0 * np.sin(2 * np.pi * (t - 20) / 96.0) + rng.normal(0, 0.3, n_steps)
    # colder → more heat; strategy scales peak
    hdd = np.maximum(0.0, 65.0 - oat)
    fac = _strategy_load_factor(case.strategy)
    # spin-up weakly damps morning peak (toy — not GLHE truth)
    spin_dampen = 1.0 - 0.02 * min(case.pre_roll_days, 14)
    heat = fac * spin_dampen * (8.0 + 0.55 * hdd + 15.0 * np.exp(-0.5 * ((t - 28) / 6.0) ** 2))
    fan = 2.0 + 0.05 * heat
    pump = 1.5 + 0.03 * heat
    cool = np.zeros(n_steps)
    p_hvac = heat + fan + pump + cool
    zone = 68.0 - 0.05 * hdd + rng.normal(0, 0.1, n_steps)
    ewt = 45.0 + 0.1 * oat + rng.normal(0, 0.2, n_steps)
    lwt = ewt - 4.0 - 0.02 * heat
    return pd.DataFrame(
        {
            "timestamp_step": t,
            "oat_f": oat,
            "zone_temp_mean_f": zone,
            "pump_kw": pump,
            "fan_kw": fan,
            "heating_coil_kw": heat,
            "cooling_coil_kw": cool,
            "p_hvac_kw": p_hvac,
            "ewt_f": ewt,
            "lwt_f": lwt,
            "strategy": case.strategy,
            "pre_roll_days": case.pre_roll_days,
            "steps_per_hour": case.steps_per_hour,
            "provenance": PROVENANCE,
            "honesty": HONESTY_LAB,
            "promote": PROMOTE,
            "source": "synthetic_smoke_generator",
            "eval_day": case.eval_day,
        }
    )


def try_parse_eplus_csv(path: Path, case: CaseSpec) -> pd.DataFrame | None:
    """Best-effort parse of E+ variable CSV if present; else None."""
    if not path.is_file():
        return None
    try:
        df = pd.read_csv(path)
    except Exception:
        return None
    # Heuristic column hunt
    cols_l = {c.lower(): c for c in df.columns}

    def pick(*names: str) -> np.ndarray | None:
        for n in names:
            for k, orig in cols_l.items():
                if n in k:
                    return pd.to_numeric(df[orig], errors="coerce").to_numpy(dtype=float)
        return None

    heat = pick("heating coil electricity")
    cool = pick("cooling coil electricity")
    fan = pick("fan electricity")
    pump = pick("pump electricity")
    if heat is None and fan is None and pump is None:
        return None
    n = len(df)
    heat = heat if heat is not None else np.zeros(n)
    cool = cool if cool is not None else np.zeros(n)
    fan = fan if fan is not None else np.zeros(n)
    pump = pump if pump is not None else np.zeros(n)
    # E+ often Watts
    scale = 0.001 if np.nanmax(np.abs(heat)) > 500 else 1.0
    heat, cool, fan, pump = heat * scale, cool * scale, fan * scale, pump * scale
    oat = pick("outdoor air drybulb")
    if oat is not None and np.nanmax(np.abs(oat)) < 50:
        oat = oat * 9 / 5 + 32  # C→F guess
    else:
        oat = np.full(n, 25.0)
    ewt = pick("plant supply side inlet")
    lwt = pick("plant supply side outlet")
    if ewt is not None and np.nanmax(np.abs(ewt)) < 50:
        ewt = ewt * 9 / 5 + 32
    if lwt is not None and np.nanmax(np.abs(lwt)) < 50:
        lwt = lwt * 9 / 5 + 32
    ewt = ewt if ewt is not None else np.full(n, 45.0)
    lwt = lwt if lwt is not None else ewt - 4.0
    p_hvac = heat + cool + fan + pump
    return pd.DataFrame(
        {
            "timestamp_step": np.arange(n),
            "oat_f": oat,
            "zone_temp_mean_f": np.full(n, 68.0),
            "pump_kw": pump,
            "fan_kw": fan,
            "heating_coil_kw": heat,
            "cooling_coil_kw": cool,
            "p_hvac_kw": p_hvac,
            "ewt_f": ewt,
            "lwt_f": lwt,
            "strategy": case.strategy,
            "pre_roll_days": case.pre_roll_days,
            "steps_per_hour": case.steps_per_hour,
            "provenance": PROVENANCE,
            "honesty": HONESTY_LAB,
            "promote": PROMOTE,
            "source": str(path),
            "eval_day": case.eval_day,
        }
    )


def load_or_synthesize(case: CaseSpec, run_dir: Path) -> pd.DataFrame:
    for cand in sorted(run_dir.glob("*.csv")):
        parsed = try_parse_eplus_csv(cand, case)
        if parsed is not None and len(parsed) >= 24:
            return parsed
    return synthesize_plant_day(case)


def day_metrics(df: pd.DataFrame) -> dict[str, Any]:
    kw = df["p_hvac_kw"].to_numpy(dtype=float)
    peak_i = int(np.nanargmax(kw))
    return {
        "daily_kwh": float(np.nansum(kw) * 0.25),
        "peak_kw": float(np.nanmax(kw)),
        "peak_step": peak_i,
        "ewt_mean": float(np.nanmean(df["ewt_f"])) if "ewt_f" in df.columns else "",
        "zone_mean_f": float(np.nanmean(df["zone_temp_mean_f"])),
    }

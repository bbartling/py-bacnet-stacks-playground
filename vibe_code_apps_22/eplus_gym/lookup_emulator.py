"""Farm parquet lookup emulator — honest stand-in when live E+ API unavailable.

Not closed-loop dynamics: returns precomputed IdealLoads farm trajectories
keyed by (day, strategy). Label: FARM_LOOKUP_EMULATOR.
"""
from __future__ import annotations

from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

import numpy as np
import pandas as pd

from .honesty import HONESTY_IDEALLOADS, LOOKUP_EMULATOR, PROMOTE


STEPS = 96


def resolve_farm_root(site: Path) -> Path:
    return Path(site) / "eplus" / "dsm_farm_paired"


def _from_paired_parquet(
    farm: Path, day: str, strategy: str
) -> Optional[Tuple[np.ndarray, Optional[np.ndarray]]]:
    pq = farm / "heating_dsm_eplus_paired_15min_v1.parquet"
    if not pq.is_file():
        return None
    df = pd.read_parquet(pq)
    mask = (df["day"].astype(str) == str(day)) & (
        df["strategy_id"].astype(str) == str(strategy)
    )
    df = df.loc[mask].copy()
    if df.empty:
        return None
    sort_col = "timestamp_utc" if "timestamp_utc" in df.columns else "quarter_index"
    if sort_col in df.columns:
        df = df.sort_values(sort_col)
    col = (
        "site_electric_proxy_kw"
        if "site_electric_proxy_kw" in df.columns
        else "facility_kw"
    )
    kw = df[col].to_numpy(dtype=float)[:STEPS]
    oat = df["oat_f"].to_numpy(dtype=float)[:STEPS] if "oat_f" in df.columns else None
    if len(kw) < STEPS:
        return None
    return kw[:STEPS], (oat[:STEPS] if oat is not None and len(oat) >= STEPS else oat)


def _load_run_kw(farm: Path, day: str, strategy: str) -> Tuple[np.ndarray, Optional[np.ndarray]]:
    # Prefer paired parquet (canonical farm product)
    got = _from_paired_parquet(farm, day, strategy)
    if got is not None:
        return got

    runs = sorted(farm.glob(f"{day}_{strategy}_*"))
    if not runs:
        raise FileNotFoundError(f"no farm run for {day}/{strategy} under {farm}")
    run_dir = runs[0]
    ts = None
    for name in ("timeseries.parquet", "plant_15min.parquet", "facility_15min.parquet"):
        p = run_dir / name
        if p.is_file():
            ts = pd.read_parquet(p)
            break
    if ts is None:
        csvs = list(run_dir.glob("*.csv"))
        if not csvs:
            raise FileNotFoundError(
                f"no timeseries in {run_dir} and paired parquet miss for {day}/{strategy}"
            )
        ts = pd.read_csv(csvs[0])
    col = "site_electric_proxy_kw" if "site_electric_proxy_kw" in ts.columns else "facility_kw"
    if col not in ts.columns:
        num = ts.select_dtypes(include=[np.number])
        col = num.columns[0]
    kw = ts[col].to_numpy(dtype=float)[:STEPS]
    oat = ts["oat_f"].to_numpy(dtype=float)[:STEPS] if "oat_f" in ts.columns else None
    if len(kw) < STEPS:
        pad = np.full(STEPS - len(kw), float(kw[-1]) if len(kw) else 0.0)
        kw = np.concatenate([kw, pad])
    return kw[:STEPS], (oat[:STEPS] if oat is not None and len(oat) >= STEPS else oat)


class FarmLookupEnv:
    """Minimal env-like object: reset/step over a farm day without live E+."""

    def __init__(
        self,
        *,
        site_root: Path,
        day: str,
        strategy_id: str,
        htg_setpoints_f: Optional[List[float]] = None,
    ):
        self.site_root = Path(site_root)
        self.day = day
        self.strategy_id = strategy_id
        self.farm = resolve_farm_root(self.site_root)
        self.honesty = HONESTY_IDEALLOADS
        self.provenance = LOOKUP_EMULATOR
        self.promote = PROMOTE
        self._kw: Optional[np.ndarray] = None
        self._oat: Optional[np.ndarray] = None
        self._htg_f = htg_setpoints_f
        self.t = 0
        self.last_obs: Dict[str, float] = {}

    def reset(self):
        self._kw, self._oat = _load_run_kw(self.farm, self.day, self.strategy_id)
        self.t = 0
        self.last_obs = self._obs_at(0)
        return self.last_obs, {
            "honesty": self.honesty,
            "provenance": self.provenance,
            "promote": self.promote,
            "day": self.day,
            "strategy_id": self.strategy_id,
        }

    def _obs_at(self, i: int) -> Dict[str, float]:
        assert self._kw is not None
        oat = float(self._oat[i]) if self._oat is not None else 0.0
        htg = float(self._htg_f[i]) if self._htg_f is not None else 68.0
        return {
            "facility_kw": float(self._kw[i]),
            "oat_f": oat,
            "htg_sp_f": htg,
            "step": float(i),
        }

    def step(self, action_c: float):
        """Advance one 15-min step. action_c ignored for lookup (trajectory fixed)."""
        _ = action_c
        self.t += 1
        done = self.t >= STEPS
        if done:
            obs = self.last_obs
        else:
            obs = self._obs_at(self.t)
            self.last_obs = obs
        reward = -float(obs["facility_kw"]) / 100.0
        info = {
            "honesty": self.honesty,
            "provenance": self.provenance,
            "action_ignored": True,
            "note": "lookup emulator — strategy baked into farm trajectory",
        }
        return obs, reward, done, False, info

    def close(self):
        return None


def list_farm_days(site_root: Path, strategy: str = "baseline") -> List[str]:
    """Days with usable trajectories. Prefer paired parquet when present."""
    farm = resolve_farm_root(site_root)
    pq = farm / "heating_dsm_eplus_paired_15min_v1.parquet"
    if pq.is_file():
        df = pd.read_parquet(pq, columns=["day", "strategy_id"])
        m = df["strategy_id"].astype(str) == str(strategy)
        days = sorted(set(df.loc[m, "day"].astype(str).unique()))
        if days:
            return days
    days = set()
    for p in farm.glob(f"*_{strategy}_*"):
        day = p.name.split("_")[0]
        if len(day) == 10 and day[4] == "-":
            days.add(day)
    return sorted(days)

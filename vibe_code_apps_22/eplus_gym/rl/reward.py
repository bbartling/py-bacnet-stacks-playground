"""Daily RL reward: illustrative cost + pre-8AM comfort penalties."""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Dict, Sequence

import numpy as np
import pandas as pd

from eplus_gym.objective import BAS_ZONE_COLS, DT_H, _facility_series
from eplus_gym.rl import SCHOOL_START_STEP

FAIL_REWARD = -1.0e6


@dataclass
class RewardWeights:
    energy_rate_per_kwh: float = 0.12
    demand_rate_per_kw: float = 15.0
    lambda_pre8: float = 50.0
    lambda_occ: float = 5.0
    occupied_min_f: float = 68.0


@dataclass
class RewardBreakdown:
    reward: float
    daily_kwh: float
    peak_kw: float
    energy_cost: float
    peak_cost: float
    pre8_violations: int
    pre8_degree_hours: float
    occ_violations: int
    failed: bool
    extras: Dict[str, Any]


def _zone_cols(df: pd.DataFrame) -> list[str]:
    cols = [c for c in BAS_ZONE_COLS if c in df.columns]
    if len(cols) < 6:
        raise ValueError(f"need six BAS zone cols; have {cols}")
    return cols


def compute_daily_reward(
    df: pd.DataFrame | None,
    *,
    weights: RewardWeights | None = None,
    school_start_step: int = SCHOOL_START_STEP,
    failed: bool = False,
) -> RewardBreakdown:
    """Single scalar reward for one LIVE day trajectory."""
    w = weights or RewardWeights()
    if failed or df is None or len(df) == 0:
        return RewardBreakdown(
            reward=FAIL_REWARD,
            daily_kwh=float("nan"),
            peak_kw=float("nan"),
            energy_cost=float("nan"),
            peak_cost=float("nan"),
            pre8_violations=0,
            pre8_degree_hours=0.0,
            occ_violations=0,
            failed=True,
            extras={"reason": "failed_or_empty"},
        )
    try:
        fac = _facility_series(df)
    except ValueError as exc:
        return RewardBreakdown(
            reward=FAIL_REWARD,
            daily_kwh=float("nan"),
            peak_kw=float("nan"),
            energy_cost=float("nan"),
            peak_cost=float("nan"),
            pre8_violations=0,
            pre8_degree_hours=0.0,
            occ_violations=0,
            failed=True,
            extras={"reason": str(exc)},
        )
    if fac.isna().all():
        return compute_daily_reward(None, weights=w, failed=True)

    peak = float(fac.max())
    kwh = float(fac.sum() * DT_H)
    energy_cost = kwh * float(w.energy_rate_per_kwh)
    peak_cost = peak * float(w.demand_rate_per_kw)

    cols = _zone_cols(df)
    # Prefer local_step if present (0..95), else step % 96
    if "local_step" in df.columns:
        steps = [int(s) % 96 for s in df["local_step"].tolist()]
    elif "step" in df.columns:
        steps = [int(s) % 96 for s in df["step"].tolist()]
    else:
        steps = list(range(len(df)))

    pre8_viol = 0
    pre8_dh = 0.0
    occ_viol = 0
    for i, st in enumerate(steps):
        row = df.iloc[i]
        temps = [float(row[c]) for c in cols]
        cold = any(t != t or t < float(w.occupied_min_f) for t in temps)
        if st <= int(school_start_step):
            # Pre-school / at school start: must be warm by 08:00
            if st == int(school_start_step) or st >= max(0, int(school_start_step) - 4):
                if cold:
                    pre8_viol += 1
                    for t in temps:
                        if t == t and t < float(w.occupied_min_f):
                            pre8_dh += (float(w.occupied_min_f) - t) * DT_H
        elif 28 <= st < 68:
            if cold:
                occ_viol += 1

    reward = -(energy_cost + peak_cost)
    reward -= float(w.lambda_pre8) * float(pre8_viol)
    reward -= float(w.lambda_pre8) * 0.1 * float(pre8_dh)
    reward -= float(w.lambda_occ) * float(occ_viol)

    return RewardBreakdown(
        reward=float(reward),
        daily_kwh=kwh,
        peak_kw=peak,
        energy_cost=float(energy_cost),
        peak_cost=float(peak_cost),
        pre8_violations=int(pre8_viol),
        pre8_degree_hours=float(pre8_dh),
        occ_violations=int(occ_viol),
        failed=False,
        extras={"school_start_step": int(school_start_step)},
    )

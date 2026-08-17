"""Reward / accounting contract v2. Does not reinterpret operator-pay v1 artifacts."""
from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Mapping, Sequence

import numpy as np

from eplus_gym.control_v2 import ACTION_KEYS, school_windows
from eplus_gym.objective import BAS_ZONE_COLS, DT_H

_APP = Path(__file__).resolve().parents[2]
CONTRACT_NAME = "reward_contract_v2.json"

ENERGY_RATE = 0.12
DEMAND_RATE = 15.0
COST_SCALE = 100.0
LAMBDA_OCC = 0.05
LAMBDA_MOVE = 0.02
READINESS_LO_F = 68.0
READINESS_HI_F = 74.0
READINESS_STEPS = (30, 31)
TRAIN_FAIL_BASE = -20.0
TRAIN_CLIP = (-5.0, 5.0)
PAYCHECK_BASE = 100.0
PAYCHECK_CAP = 500.0
N_INTERVALS = 96
N_ZONES = 6


class IntegrityFailure(RuntimeError):
    """Campaign-fatal. Not a learnable transition. Do not fabricate values."""


class MissingBaselineError(IntegrityFailure):
    """Paired baseline missing or cache key mismatch."""


def load_reward_contract_v2() -> dict[str, Any]:
    path = _APP / "contracts" / CONTRACT_NAME
    return json.loads(path.read_text(encoding="utf-8"))


def _finite(xs: Sequence[float], *, name: str) -> list[float]:
    out = [float(x) for x in xs]
    if any(v != v or v in (float("inf"), float("-inf")) for v in out):
        raise IntegrityFailure(f"{name} contains NaN/Inf")
    return out


def _zone_matrix(zone_temps_f: Mapping[str, Sequence[float]] | Sequence[Sequence[float]]) -> np.ndarray:
    if isinstance(zone_temps_f, Mapping):
        cols = []
        missing = []
        for key, col_name in zip(ACTION_KEYS, BAS_ZONE_COLS):
            series = zone_temps_f.get(key)
            if series is None:
                series = zone_temps_f.get(col_name)
            if series is None:
                missing.append(key)
                continue
            cols.append(_finite(series, name=f"zone:{key}"))
        if missing:
            raise IntegrityFailure(f"missing zones: {missing}")
        arr = np.asarray(cols, dtype=np.float64)
    else:
        arr = np.asarray(zone_temps_f, dtype=np.float64)
        if arr.ndim != 2:
            raise IntegrityFailure("zone temps must be 6 x n or n x 6")
        if arr.shape[0] == N_ZONES:
            pass
        elif arr.shape[1] == N_ZONES:
            arr = arr.T
        else:
            raise IntegrityFailure(f"need six zone series, got shape {arr.shape}")
        if not np.isfinite(arr).all():
            raise IntegrityFailure("zone temps contain NaN/Inf")
    if arr.shape[0] != N_ZONES:
        raise IntegrityFailure(f"need six zones, got {arr.shape[0]}")
    return arr


def assert_scored_trajectory(
    facility_kw: Sequence[float],
    zone_temps_f: Mapping[str, Sequence[float]] | Sequence[Sequence[float]],
    *,
    n_intervals: int = N_INTERVALS,
) -> tuple[np.ndarray, np.ndarray]:
    fac = np.asarray(_finite(facility_kw, name="facility_kw"), dtype=np.float64)
    if fac.size != int(n_intervals):
        raise IntegrityFailure(f"wrong timestep count: expected {n_intervals}, got {fac.size}")
    zones = _zone_matrix(zone_temps_f)
    if zones.shape[1] != int(n_intervals):
        raise IntegrityFailure(
            f"zone series length {zones.shape[1]} != facility length {n_intervals}"
        )
    return fac, zones


def utility_accounting(
    facility_kw: Sequence[float],
    *,
    rate_kwh: Sequence[float] | float = ENERGY_RATE,
    demand_rate: float = DEMAND_RATE,
    mtd_peak_kw: float = 0.0,
    ratchet_kw: float = 0.0,
    contract_kw: float = 0.0,
    dt_h: float = DT_H,
) -> dict[str, float]:
    fac = np.asarray(_finite(facility_kw, name="facility_kw"), dtype=np.float64)
    if np.isscalar(rate_kwh) or (not hasattr(rate_kwh, "__len__")):
        rates = np.full(fac.shape, float(rate_kwh), dtype=np.float64)
    else:
        rates = np.asarray(_finite(rate_kwh, name="rate_kwh"), dtype=np.float64)
        if rates.shape != fac.shape:
            raise IntegrityFailure("rate_kwh length must match facility_kw")
    energy_cost = float(np.sum(rates * fac * float(dt_h)))
    day_peak = float(np.max(fac)) if fac.size else 0.0
    old_floor = max(float(mtd_peak_kw), float(ratchet_kw), float(contract_kw))
    new_floor = max(old_floor, day_peak)
    demand_increment = float(demand_rate) * (new_floor - old_floor)
    daily_cost = energy_cost + demand_increment
    return {
        "energy_cost": energy_cost,
        "day_peak_kw": day_peak,
        "old_floor_kw": old_floor,
        "new_floor_kw": new_floor,
        "demand_increment": demand_increment,
        "daily_cost": daily_cost,
        "daily_kwh": float(np.sum(fac) * float(dt_h)),
        "mtd_peak_kw": float(mtd_peak_kw),
        "ratchet_kw": float(ratchet_kw),
        "contract_kw": float(contract_kw),
    }


def readiness_all_six(
    zone_temps_f: Mapping[str, Sequence[float]] | Sequence[Sequence[float]],
    *,
    day: str,
    steps: Sequence[int] = READINESS_STEPS,
    lo_f: float = READINESS_LO_F,
    hi_f: float = READINESS_HI_F,
    school_day: bool | None = None,
) -> dict[str, Any]:
    win = school_windows(day)
    is_school = bool(win["school_occupied"]) if school_day is None else bool(school_day)
    zones = _zone_matrix(zone_temps_f)
    if not is_school:
        return {
            "school_day": False,
            "readiness_ok": True,
            "checked": False,
            "failed_zones": [],
            "degree_violation": 0.0,
        }
    failed: list[str] = []
    violation = 0.0
    for st in steps:
        idx = int(st)
        if idx < 0 or idx >= zones.shape[1]:
            raise IntegrityFailure(f"readiness step {idx} out of trajectory")
        for z_i, key in enumerate(ACTION_KEYS):
            t = float(zones[z_i, idx])
            if t < float(lo_f) or t > float(hi_f):
                failed.append(f"{key}@step{idx}")
                if t < float(lo_f):
                    violation += (float(lo_f) - t) * DT_H
                else:
                    violation += (t - float(hi_f)) * DT_H
    return {
        "school_day": True,
        "readiness_ok": not failed,
        "checked": True,
        "failed_zones": failed,
        "degree_violation": float(violation),
        "all_six_required": True,
        "never_mean_of_six": True,
        "band_f": [float(lo_f), float(hi_f)],
        "steps": [int(s) for s in steps],
    }


def occupied_zone_degree_hours(
    zone_temps_f: Mapping[str, Sequence[float]] | Sequence[Sequence[float]],
    *,
    day: str,
    occupied_min_f: float = READINESS_LO_F,
) -> float:
    win = school_windows(day)
    if not win["school_occupied"]:
        return 0.0
    start = int(win["school_occupied_start_step"] or 0)
    end = int(win["school_occupied_end_step"] or N_INTERVALS)
    zones = _zone_matrix(zone_temps_f)
    dh = 0.0
    for t in range(start, min(end, zones.shape[1])):
        for z_i in range(zones.shape[0]):
            temp = float(zones[z_i, t])
            if temp < float(occupied_min_f):
                dh += (float(occupied_min_f) - temp) * DT_H
    return float(dh)


def action_movement(schedules: Mapping[str, Sequence[float]] | Sequence[Sequence[float]]) -> float:
    if isinstance(schedules, Mapping):
        series = [list(schedules[k]) for k in ACTION_KEYS]
    else:
        series = [list(s) for s in schedules]
    move = 0.0
    n = 0
    for row in series:
        if len(row) < 2:
            continue
        for a, b in zip(row, row[1:]):
            move += abs(float(b) - float(a))
            n += 1
    return float(move / n) if n else 0.0


def display_paycheck(
    *,
    savings: float,
    readiness_ok: bool,
    k: float,
    base_wage: float = PAYCHECK_BASE,
    payout_cap: float = PAYCHECK_CAP,
) -> dict[str, float | bool]:
    if float(k) not in {2.0, 3.0}:
        raise ValueError("k must be 2 or 3 (separate experiments)")
    if not readiness_ok:
        raw = 0.0
    else:
        raw = float(base_wage) + float(k) * float(savings)
        raw = max(0.0, min(float(payout_cap), raw))
    return {
        "savings_usd": float(savings),
        "display_paycheck_usd": float(raw),
        "k": float(k),
        "readiness_ok": bool(readiness_ok),
        "human_only": True,
    }


def normalized_degree_violation(degree_violation: float) -> float:
    return max(0.0, float(degree_violation) / float(N_ZONES))


def train_reward(
    *,
    savings: float,
    readiness_ok: bool,
    occupied_dh: float = 0.0,
    movement: float = 0.0,
    degree_violation: float = 0.0,
    cost_scale: float = COST_SCALE,
    lambda_occ: float = LAMBDA_OCC,
    lambda_move: float = LAMBDA_MOVE,
) -> float:
    if not readiness_ok:
        return float(TRAIN_FAIL_BASE) - normalized_degree_violation(degree_violation)
    shaped = float(np.clip(float(savings) / float(cost_scale), TRAIN_CLIP[0], TRAIN_CLIP[1]))
    shaped -= float(lambda_occ) * float(occupied_dh)
    shaped -= float(lambda_move) * float(movement)
    return float(np.clip(shaped, TRAIN_CLIP[0], TRAIN_CLIP[1]))


@dataclass
class RewardV2Result:
    training_reward: float
    display_paycheck_usd: float
    savings: float
    candidate: dict[str, float]
    baseline: dict[str, float]
    readiness: dict[str, Any]
    extras: dict[str, Any] = field(default_factory=dict)
    invalid: bool = False


def score_day_v2(
    *,
    day: str,
    candidate_facility_kw: Sequence[float],
    candidate_zone_temps_f: Mapping[str, Sequence[float]] | Sequence[Sequence[float]],
    baseline_facility_kw: Sequence[float] | None,
    baseline_zone_temps_f: Mapping[str, Sequence[float]] | Sequence[Sequence[float]] | None,
    candidate_schedules: Mapping[str, Sequence[float]] | None = None,
    mtd_peak_kw: float = 0.0,
    ratchet_kw: float = 0.0,
    contract_kw: float = 0.0,
    baseline_mtd_peak_kw: float | None = None,
    baseline_ratchet_kw: float | None = None,
    baseline_contract_kw: float | None = None,
    rate_kwh: Sequence[float] | float = ENERGY_RATE,
    demand_rate: float = DEMAND_RATE,
    paycheck_k: float = 2.0,
    failed: bool = False,
    fail_reason: str | None = None,
) -> RewardV2Result:
    if failed:
        raise IntegrityFailure(fail_reason or "energyplus_crash")
    if baseline_facility_kw is None or baseline_zone_temps_f is None:
        raise MissingBaselineError("paired EnergyPlus baseline required; refusing candidate-as-baseline")
    fac, zones = assert_scored_trajectory(candidate_facility_kw, candidate_zone_temps_f)
    b_fac, _b_zones = assert_scored_trajectory(baseline_facility_kw, baseline_zone_temps_f)
    cand = utility_accounting(
        fac,
        rate_kwh=rate_kwh,
        demand_rate=demand_rate,
        mtd_peak_kw=mtd_peak_kw,
        ratchet_kw=ratchet_kw,
        contract_kw=contract_kw,
    )
    base = utility_accounting(
        b_fac,
        rate_kwh=rate_kwh,
        demand_rate=demand_rate,
        mtd_peak_kw=mtd_peak_kw if baseline_mtd_peak_kw is None else baseline_mtd_peak_kw,
        ratchet_kw=ratchet_kw if baseline_ratchet_kw is None else baseline_ratchet_kw,
        contract_kw=contract_kw if baseline_contract_kw is None else baseline_contract_kw,
    )
    savings = float(base["daily_cost"] - cand["daily_cost"])
    ready = readiness_all_six(zones, day=day)
    occ_dh = occupied_zone_degree_hours(zones, day=day)
    move = action_movement(candidate_schedules) if candidate_schedules is not None else 0.0
    pay = display_paycheck(savings=savings, readiness_ok=bool(ready["readiness_ok"]), k=paycheck_k)
    train = train_reward(
        savings=savings,
        readiness_ok=bool(ready["readiness_ok"]),
        occupied_dh=occ_dh,
        movement=move,
        degree_violation=float(ready["degree_violation"]),
    )
    return RewardV2Result(
        training_reward=float(train),
        display_paycheck_usd=float(pay["display_paycheck_usd"]),
        savings=savings,
        candidate=cand,
        baseline=base,
        readiness=ready,
        extras={
            "reward_name": "reward_v2",
            "occupied_zone_DH": occ_dh,
            "action_movement": move,
            "paycheck_k": float(paycheck_k),
            "never_paycheck_capped_train": True,
        },
    )

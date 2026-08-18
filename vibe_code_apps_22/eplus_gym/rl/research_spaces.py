"""Conservative research action contract v1. Frozen school calendar. Shallow setback only."""
from __future__ import annotations

from typing import Sequence

import gymnasium as gym
import numpy as np

from eplus_gym.control_v2 import (
    ACTION_KEYS,
    SixZoneDailyParamsV2,
    ZoneOffsetsV2,
    continuous_params,
    school_windows,
)

RESEARCH_ACTION_CONTRACT = "research_action_contract_v1"
OCC_F_LO, OCC_F_HI = 68.0, 70.0
RESEARCH_UNOCC_F_LO, RESEARCH_UNOCC_F_HI = 66.0, 70.0
REC_LO, REC_HI = 0.0, 120.0
SETBACK_LO, SETBACK_HI = -1.0, 1.0
N_CONT = 3 + len(ACTION_KEYS)

DQN_UNOCC = (66.0, 68.0)
DQN_REC = (60, 120)
DQN_OFFSET = (-1.0, 0.0)


def frozen_school_occupancy(day: str) -> dict[str, int]:
    win = school_windows(day)
    start = win.get("school_occupied_start_step")
    end = win.get("school_occupied_end_step")
    if start is None or end is None:
        return {"heating_setpoint_start_step": 30, "heating_setpoint_end_step": 59}
    return {
        "heating_setpoint_start_step": int(start),
        "heating_setpoint_end_step": int(end),
    }


def research_continuous_68() -> SixZoneDailyParamsV2:
    return continuous_params(68.0)


def research_continuous_70() -> SixZoneDailyParamsV2:
    return continuous_params(70.0)


def _clip(v: float, lo: float, hi: float) -> float:
    return float(min(hi, max(lo, v)))


def continuous_action_space_research() -> gym.spaces.Box:
    low = np.asarray(
        [OCC_F_LO, RESEARCH_UNOCC_F_LO, REC_LO] + [SETBACK_LO] * len(ACTION_KEYS),
        dtype=np.float32,
    )
    high = np.asarray(
        [OCC_F_HI, RESEARCH_UNOCC_F_HI, REC_HI] + [SETBACK_HI] * len(ACTION_KEYS),
        dtype=np.float32,
    )
    return gym.spaces.Box(low=low, high=high, shape=(N_CONT,), dtype=np.float32)


def decode_continuous_research(
    action: Sequence[float] | np.ndarray,
    *,
    day: str,
) -> SixZoneDailyParamsV2:
    a = np.asarray(action, dtype=np.float64).reshape(-1)
    if a.size != N_CONT:
        raise ValueError(f"expected research action len {N_CONT}, got {a.size}")
    occ = _clip(float(a[0]), OCC_F_LO, OCC_F_HI)
    unocc = _clip(float(a[1]), RESEARCH_UNOCC_F_LO, min(RESEARCH_UNOCC_F_HI, occ))
    rec = int(round(_clip(float(a[2]), REC_LO, REC_HI) / 15.0) * 15)
    zo = {
        key: ZoneOffsetsV2(setback_offset_f=_clip(float(a[3 + i]), SETBACK_LO, SETBACK_HI))
        for i, key in enumerate(ACTION_KEYS)
    }
    frozen = frozen_school_occupancy(day)
    if abs(occ - unocc) < 1e-6:
        return continuous_params(occ)
    return SixZoneDailyParamsV2(
        occupied_heating_f=occ,
        unoccupied_heating_f=unocc,
        heating_setpoint_start_step=frozen["heating_setpoint_start_step"],
        heating_setpoint_end_step=frozen["heating_setpoint_end_step"],
        recovery_lead_minutes=rec,
        recovery_ramp_minutes=rec,
        zone_offsets=zo,
    )


def _raw_discrete() -> list[SixZoneDailyParamsV2]:
    out = [research_continuous_68(), research_continuous_70()]
    frozen = frozen_school_occupancy("2026-01-12")
    for unocc in DQN_UNOCC:
        for rec in DQN_REC:
            for off in DQN_OFFSET:
                zo = {k: ZoneOffsetsV2(setback_offset_f=float(off)) for k in ACTION_KEYS}
                out.append(
                    SixZoneDailyParamsV2(
                        occupied_heating_f=70.0,
                        unoccupied_heating_f=float(unocc),
                        heating_setpoint_start_step=frozen["heating_setpoint_start_step"],
                        heating_setpoint_end_step=frozen["heating_setpoint_end_step"],
                        recovery_lead_minutes=int(rec),
                        recovery_ramp_minutes=int(rec),
                        zone_offsets=zo,
                    )
                )
    return out


def discrete_n_research() -> int:
    return len(_raw_discrete())


def discrete_action_space_research() -> gym.spaces.Discrete:
    return gym.spaces.Discrete(discrete_n_research())


def decode_discrete_research(index: int, *, day: str) -> SixZoneDailyParamsV2:
    table = _raw_discrete()
    params = table[int(index) % len(table)]
    if params.continuous_conditioning:
        return params
    frozen = frozen_school_occupancy(day)
    return SixZoneDailyParamsV2(
        occupied_heating_f=params.occupied_heating_f,
        unoccupied_heating_f=params.unoccupied_heating_f,
        heating_setpoint_start_step=frozen["heating_setpoint_start_step"],
        heating_setpoint_end_step=frozen["heating_setpoint_end_step"],
        recovery_lead_minutes=params.recovery_lead_minutes,
        recovery_ramp_minutes=params.recovery_lead_minutes,
        zone_offsets=params.zone_offsets,
    )

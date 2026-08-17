"""PPO/DQN action contract v2. Does not reinterpret Discrete(64) v1."""
from __future__ import annotations

from typing import Sequence

import gymnasium as gym
import numpy as np

from eplus_gym.control_v2 import (
    ACTION_KEYS,
    END_OF_DAY_STEP,
    SixZoneDailyParamsV2,
    ZoneOffsetsV2,
    continuous_params,
    school_windows,
    validate_params,
)
from eplus_native.six_zone_htg_stage import ACTION_KEYS as _KEYS

assert ACTION_KEYS == _KEYS

N_CONT_V2 = 5 + len(ACTION_KEYS)
OCC_F_LO, OCC_F_HI = 68.0, 72.0
SETBACK_DEPTH_LO, SETBACK_DEPTH_HI = 0.0, 14.0
SETBACK_DEADBAND_F = 0.25
START_LO, START_HI = 20, 40
END_LO, END_HI = 52, 96
REC_LO, REC_HI = 0.0, 180.0
SETBACK_LO, SETBACK_HI = -3.0, 1.0
UNOCC_F_LO, UNOCC_F_HI = 58.0, 72.0

DQN_V2_OCC = (68.0, 70.0)
DQN_V2_UNOCC = (58.0, 62.0, 64.0)
DQN_V2_START = (24, 28, 32)
DQN_V2_REC = (0, 60, 120)
DQN_V2_OFFSET = (-2.0, 0.0)
DQN_V2_N_CONTINUOUS = 2


def _clip(v: float, lo: float, hi: float) -> float:
    return float(min(hi, max(lo, v)))


def continuous_action_space_v2() -> gym.spaces.Box:
    low = np.asarray(
        [OCC_F_LO, SETBACK_DEPTH_LO, float(START_LO), float(END_LO), REC_LO]
        + [SETBACK_LO] * len(ACTION_KEYS),
        dtype=np.float32,
    )
    high = np.asarray(
        [OCC_F_HI, SETBACK_DEPTH_HI, float(START_HI), float(END_HI), REC_HI]
        + [SETBACK_HI] * len(ACTION_KEYS),
        dtype=np.float32,
    )
    return gym.spaces.Box(low=low, high=high, shape=(N_CONT_V2,), dtype=np.float32)


def discrete_n_v2() -> int:
    return DQN_V2_N_CONTINUOUS + (
        len(DQN_V2_OCC) * len(DQN_V2_UNOCC) * len(DQN_V2_START) * len(DQN_V2_REC) * len(DQN_V2_OFFSET)
    )


def discrete_action_space_v2() -> gym.spaces.Discrete:
    return gym.spaces.Discrete(discrete_n_v2())


def decode_continuous_v2(action: Sequence[float] | np.ndarray) -> SixZoneDailyParamsV2:
    a = np.asarray(action, dtype=np.float64).reshape(-1)
    if a.size != N_CONT_V2:
        raise ValueError(f"expected action len {N_CONT_V2}, got {a.size}")
    occ = _clip(float(a[0]), OCC_F_LO, OCC_F_HI)
    depth = _clip(float(a[1]), SETBACK_DEPTH_LO, min(SETBACK_DEPTH_HI, occ - UNOCC_F_LO))
    start = int(round(_clip(float(a[2]), START_LO, START_HI)))
    end = int(round(_clip(float(a[3]), END_LO, END_HI)))
    rec = int(round(_clip(float(a[4]), REC_LO, REC_HI) / 15.0) * 15)
    zo = {
        key: ZoneOffsetsV2(setback_offset_f=_clip(float(a[5 + i]), SETBACK_LO, SETBACK_HI))
        for i, key in enumerate(ACTION_KEYS)
    }
    if depth < SETBACK_DEADBAND_F:
        depth = 0.0
        continuous = True
        unocc = occ
        start, end, rec = 0, END_OF_DAY_STEP, 0
        zo = {key: ZoneOffsetsV2(setback_offset_f=0.0) for key in ACTION_KEYS}
    else:
        continuous = False
        unocc = occ - depth
        if end <= start:
            raise ValueError("invalid start/end combination")
    params = SixZoneDailyParamsV2(
        occupied_heating_f=occ,
        unoccupied_heating_f=unocc,
        heating_setpoint_start_step=start,
        heating_setpoint_end_step=end,
        recovery_lead_minutes=rec,
        recovery_ramp_minutes=rec,
        continuous_conditioning=continuous,
        zone_offsets=zo,
    )
    validate_params(params)
    return params


def encode_continuous_v2(params: SixZoneDailyParamsV2) -> np.ndarray:
    if params.continuous_conditioning:
        depth = 0.0
    else:
        depth = float(params.occupied_heating_f) - float(params.unoccupied_heating_f)
    zo = [float(params.zone_offsets[k].setback_offset_f) for k in ACTION_KEYS]
    return np.asarray(
        [
            params.occupied_heating_f,
            depth,
            float(params.heating_setpoint_start_step),
            float(params.heating_setpoint_end_step),
            float(params.recovery_lead_minutes),
            *zo,
        ],
        dtype=np.float32,
    )


def decode_discrete_v2(index: int, *, day: str | None = None) -> SixZoneDailyParamsV2:
    n = discrete_n_v2()
    idx = int(index)
    if idx < 0 or idx >= n:
        raise ValueError(f"DQN index {idx} outside [0, {n}); wrap is forbidden")
    if idx == 0:
        return continuous_params(68.0)
    if idx == 1:
        return continuous_params(70.0)
    idx -= DQN_V2_N_CONTINUOUS
    n_off = len(DQN_V2_OFFSET)
    n_rec = len(DQN_V2_REC)
    n_start = len(DQN_V2_START)
    n_unocc = len(DQN_V2_UNOCC)
    off_i = idx % n_off
    idx //= n_off
    rec_i = idx % n_rec
    idx //= n_rec
    start_i = idx % n_start
    idx //= n_start
    unocc_i = idx % n_unocc
    idx //= n_unocc
    occ_i = idx % len(DQN_V2_OCC)
    occ = DQN_V2_OCC[occ_i]
    unocc = DQN_V2_UNOCC[unocc_i]
    start = DQN_V2_START[start_i]
    rec = DQN_V2_REC[rec_i]
    off = DQN_V2_OFFSET[off_i]
    end = 68
    if day is not None:
        win = school_windows(day)
        if win["school_occupied"] and win["school_occupied_end_step"] is not None:
            end = int(win["school_occupied_end_step"])
    zo = {k: ZoneOffsetsV2(setback_offset_f=float(off)) for k in ACTION_KEYS}
    params = SixZoneDailyParamsV2(
        occupied_heating_f=float(occ),
        unoccupied_heating_f=float(unocc),
        heating_setpoint_start_step=int(start),
        heating_setpoint_end_step=int(end),
        recovery_lead_minutes=int(rec),
        recovery_ramp_minutes=int(rec),
        zone_offsets=zo,
    )
    validate_params(params)
    return params

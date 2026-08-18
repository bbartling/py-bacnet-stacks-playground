"""Conservative research action contract v1. Frozen school calendar. Shallow setback only."""
from __future__ import annotations

from typing import Sequence

import gymnasium as gym
import numpy as np

from eplus_gym.control_v2 import (
    ACTION_KEYS,
    SixZoneDailyParamsV2,
    ZoneOffsetsV2,
    build_six_schedules_f,
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


# --- research_action_contract_v2 (normalized PPO). Do not reinterpret v1. ---

RESEARCH_ACTION_CONTRACT_V2 = "research_action_contract_v2"
DECODER_VERSION_V2 = "research_affine_v2"
N_CONT_V2 = 3 + len(ACTION_KEYS)
OCC_F_LO_V2, OCC_F_HI_V2 = 68.0, 72.0
UNOCC_F_FLOOR_V2 = 60.0
REC_LO_V2, REC_HI_V2 = 0.0, 180.0
OFFSET_LO_V2, OFFSET_HI_V2 = -1.0, 1.0
CLG_OCC_F = 74.0
CLG_UNOCC_F = 85.0
HTG_CLG_DEADBAND_F = 2.0

DQN_V2_UNOCC = (60.0, 64.0, 66.0)
DQN_V2_REC = (0, 60, 120, 180)
DQN_V2_OFFSET = (-1.0, 0.0, 1.0)


class ActionContractMismatch(ValueError):
    """Saved policy action contract does not match research_action_contract_v2."""


def assert_research_v2_contract(meta: dict | object) -> None:
    body = meta if isinstance(meta, dict) else {}
    got = str(body.get("action_contract_version") or "")
    if got != RESEARCH_ACTION_CONTRACT_V2:
        raise ActionContractMismatch(
            f"refusing to load action contract {got!r}; expected {RESEARCH_ACTION_CONTRACT_V2}"
        )


def _affine(x: float, lo: float, hi: float) -> float:
    x = _clip(float(x), -1.0, 1.0)
    return float(lo + (x + 1.0) * 0.5 * (float(hi) - float(lo)))


def _inv_affine(y: float, lo: float, hi: float) -> float:
    span = float(hi) - float(lo)
    if span <= 1e-9:
        return 1.0
    return _clip(2.0 * (float(y) - float(lo)) / span - 1.0, -1.0, 1.0)


def continuous_action_space_research_v2() -> gym.spaces.Box:
    return gym.spaces.Box(low=-1.0, high=1.0, shape=(N_CONT_V2,), dtype=np.float32)


def frozen_school_occupancy_v2(day: str) -> dict[str, int] | None:
    win = school_windows(day)
    start = win.get("school_occupied_start_step")
    end = win.get("school_occupied_end_step")
    if start is None or end is None:
        return None
    return {
        "heating_setpoint_start_step": int(start),
        "heating_setpoint_end_step": int(end),
    }


def decode_continuous_research_v2(
    action: Sequence[float] | np.ndarray,
    *,
    day: str,
) -> SixZoneDailyParamsV2:
    a = np.asarray(action, dtype=np.float64).reshape(-1)
    if a.size != N_CONT_V2:
        raise ValueError(f"expected research v2 action len {N_CONT_V2}, got {a.size}")
    occ = _affine(float(a[0]), OCC_F_LO_V2, OCC_F_HI_V2)
    unocc = _affine(float(a[1]), UNOCC_F_FLOOR_V2, occ)
    rec = int(round(_affine(float(a[2]), REC_LO_V2, REC_HI_V2) / 15.0) * 15)
    rec = int(min(REC_HI_V2, max(REC_LO_V2, rec)))
    zo: dict[str, ZoneOffsetsV2] = {}
    for i, key in enumerate(ACTION_KEYS):
        raw = _affine(float(a[3 + i]), OFFSET_LO_V2, OFFSET_HI_V2)
        eff = _clip(unocc + raw, UNOCC_F_FLOOR_V2, occ)
        zo[key] = ZoneOffsetsV2(setback_offset_f=float(eff - unocc))
    frozen = frozen_school_occupancy_v2(day)
    if abs(occ - unocc) < 1e-6:
        return continuous_params(occ)
    # Do not invent school start=30/end=59 on weekends/holidays.
    if frozen is None:
        start, end = 0, 0
    else:
        start = frozen["heating_setpoint_start_step"]
        end = frozen["heating_setpoint_end_step"]
    return SixZoneDailyParamsV2(
        occupied_heating_f=occ,
        unoccupied_heating_f=unocc,
        heating_setpoint_start_step=int(start),
        heating_setpoint_end_step=int(end),
        recovery_lead_minutes=rec,
        recovery_ramp_minutes=rec,
        zone_offsets=zo,
    )


def encode_continuous_research_v2(params: SixZoneDailyParamsV2) -> np.ndarray:
    occ = float(params.occupied_heating_f)
    unocc = float(params.unoccupied_heating_f)
    rec = float(params.recovery_lead_minutes)
    x0 = _inv_affine(occ, OCC_F_LO_V2, OCC_F_HI_V2)
    x1 = _inv_affine(unocc, UNOCC_F_FLOOR_V2, occ)
    x2 = _inv_affine(rec, REC_LO_V2, REC_HI_V2)
    offs = []
    for key in ACTION_KEYS:
        raw = float(params.zone_offsets[key].setback_offset_f)
        offs.append(_inv_affine(raw, OFFSET_LO_V2, OFFSET_HI_V2))
    return np.asarray([x0, x1, x2, *offs], dtype=np.float32)


def _effective_unocc(params: SixZoneDailyParamsV2, key: str) -> float:
    off = float(params.zone_offsets[key].setback_offset_f)
    return _clip(float(params.unoccupied_heating_f) + off, UNOCC_F_FLOOR_V2, float(params.occupied_heating_f))


def _clamp_htg_clg(series: list[float], *, day: str) -> list[float]:
    win = school_windows(day)
    start = win.get("school_occupied_start_step")
    end = win.get("school_occupied_end_step")
    out = []
    for t, val in enumerate(series):
        occupied = start is not None and end is not None and int(start) <= t < int(end)
        clg = CLG_OCC_F if occupied else CLG_UNOCC_F
        out.append(min(float(val), clg - HTG_CLG_DEADBAND_F))
    return out


def research_build_six_schedules_f(params: SixZoneDailyParamsV2, day: str) -> dict[str, list[float]]:
    win = school_windows(day)
    if params.continuous_conditioning or win.get("school_occupied"):
        raw = build_six_schedules_f(params)
    else:
        raw = {k: [_effective_unocc(params, k)] * 96 for k in ACTION_KEYS}
    return {k: _clamp_htg_clg(list(raw[k]), day=day) for k in ACTION_KEYS}


def _raw_discrete_v2() -> list[SixZoneDailyParamsV2]:
    out = [research_continuous_68(), research_continuous_70()]
    frozen = frozen_school_occupancy_v2("2025-12-08") or {
        "heating_setpoint_start_step": 30,
        "heating_setpoint_end_step": 59,
    }
    for unocc in DQN_V2_UNOCC:
        for rec in DQN_V2_REC:
            for off in DQN_V2_OFFSET:
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


def sample_random_params_v2(
    rng: np.random.Generator | None = None,
    *,
    day: str,
) -> SixZoneDailyParamsV2:
    r = rng or np.random.default_rng()
    x = r.uniform(-1.0, 1.0, size=N_CONT_V2).astype(np.float32)
    return decode_continuous_research_v2(x, day=day)


def discrete_n_research_v2() -> int:
    return len(_raw_discrete_v2())


def discrete_action_space_research_v2() -> gym.spaces.Discrete:
    return gym.spaces.Discrete(discrete_n_research_v2())


def decode_discrete_research_v2(index: int, *, day: str) -> SixZoneDailyParamsV2:
    table = _raw_discrete_v2()
    n = len(table)
    idx = int(index)
    if idx < 0 or idx >= n:
        raise ValueError(f"DQN research v2 index {idx} wrap is forbidden; valid range [0, {n})")
    params = table[idx]
    if params.continuous_conditioning:
        return params
    frozen = frozen_school_occupancy_v2(day)
    if frozen is None:
        start, end = 0, 0
    else:
        start = frozen["heating_setpoint_start_step"]
        end = frozen["heating_setpoint_end_step"]
    return SixZoneDailyParamsV2(
        occupied_heating_f=params.occupied_heating_f,
        unoccupied_heating_f=params.unoccupied_heating_f,
        heating_setpoint_start_step=int(start),
        heating_setpoint_end_step=int(end),
        recovery_lead_minutes=params.recovery_lead_minutes,
        recovery_ramp_minutes=params.recovery_lead_minutes,
        zone_offsets=params.zone_offsets,
    )

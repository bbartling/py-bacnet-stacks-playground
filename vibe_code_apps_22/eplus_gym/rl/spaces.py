"""Encode/decode RL actions ↔ SixZoneDailyParams."""
from __future__ import annotations

from typing import Sequence

import gymnasium as gym
import numpy as np

from eplus_gym.rl import SCHOOL_START_STEP
from eplus_gym.six_zone_daily_controller import (
    ACTION_KEYS,
    SixZoneDailyParams,
    ZoneOffsets,
)

# Continuous Box order (PPO):
# 0 occ_f, 1 unocc_f, 2 occupied_setpoint_start_step (stored occupancy_start_step),
# 3 end_step, 4 recovery_min, 5..10 setback_offset_f for ACTION_KEYS
N_CONT = 5 + len(ACTION_KEYS)

OCC_F_LO, OCC_F_HI = 68.0, 72.0
UNOCC_F_LO, UNOCC_F_HI = 58.0, 68.0
START_LO, START_HI = 20, 40
END_LO, END_HI = 60, 80
REC_LO, REC_HI = 0.0, 180.0
SETBACK_LO, SETBACK_HI = -3.0, 1.0

# DQN coarse grid (frozen occ=70, start/end near defaults)
DQN_UNOCC = (60.0, 62.0, 64.0, 66.0)
DQN_REC = (0, 60, 120, 180)
DQN_SETBACK = (-2.0, -1.0, 0.0, 1.0)


def continuous_action_space() -> gym.spaces.Box:
    low = np.asarray(
        [OCC_F_LO, UNOCC_F_LO, float(START_LO), float(END_LO), REC_LO]
        + [SETBACK_LO] * len(ACTION_KEYS),
        dtype=np.float32,
    )
    high = np.asarray(
        [OCC_F_HI, UNOCC_F_HI, float(START_HI), float(END_HI), REC_HI]
        + [SETBACK_HI] * len(ACTION_KEYS),
        dtype=np.float32,
    )
    return gym.spaces.Box(low=low, high=high, shape=(N_CONT,), dtype=np.float32)


def discrete_n() -> int:
    """Flat Discrete size for DQN (unocc × recovery × setback^6 is huge).

    Use shared setback for all zones to keep cardinality tractable:
    unocc × recovery × setback = 4 * 4 * 4 = 64.
    """
    return len(DQN_UNOCC) * len(DQN_REC) * len(DQN_SETBACK)


def discrete_action_space() -> gym.spaces.Discrete:
    return gym.spaces.Discrete(discrete_n())


def _clip(v: float, lo: float, hi: float) -> float:
    return float(min(hi, max(lo, v)))


def sample_random_params(rng: np.random.Generator | None = None) -> SixZoneDailyParams:
    """Uniform random walk in the locked daily action box (not Brownian kW)."""
    r = rng or np.random.default_rng()
    start = int(r.integers(START_LO, START_HI + 1))
    end = int(r.integers(max(END_LO, start + 1), END_HI + 1))
    rec = int(round(float(r.uniform(REC_LO, REC_HI)) / 15.0) * 15)
    zo = {
        key: ZoneOffsets(setback_offset_f=float(r.uniform(SETBACK_LO, SETBACK_HI)))
        for key in ACTION_KEYS
    }
    return SixZoneDailyParams(
        occupied_heating_f=float(r.uniform(OCC_F_LO, OCC_F_HI)),
        unoccupied_heating_f=float(r.uniform(UNOCC_F_LO, UNOCC_F_HI)),
        occupancy_start_step=start,
        occupancy_end_step=end,
        recovery_start_minutes_before_occupancy=rec,
        recovery_ramp_minutes=60,
        zone_offsets=zo,
    )


def decode_continuous(action: Sequence[float] | np.ndarray) -> SixZoneDailyParams:
    a = np.asarray(action, dtype=np.float64).reshape(-1)
    if a.size != N_CONT:
        raise ValueError(f"expected action len {N_CONT}, got {a.size}")
    occ = _clip(float(a[0]), OCC_F_LO, OCC_F_HI)
    unocc = _clip(float(a[1]), UNOCC_F_LO, UNOCC_F_HI)
    start = int(round(_clip(float(a[2]), START_LO, START_HI)))
    end = int(round(_clip(float(a[3]), END_LO, END_HI)))
    if end <= start:
        end = min(END_HI, start + 1)
    rec = int(round(_clip(float(a[4]), REC_LO, REC_HI) / 15.0) * 15)
    zo = {
        key: ZoneOffsets(setback_offset_f=_clip(float(a[5 + i]), SETBACK_LO, SETBACK_HI))
        for i, key in enumerate(ACTION_KEYS)
    }
    return SixZoneDailyParams(
        occupied_heating_f=occ,
        unoccupied_heating_f=unocc,
        occupancy_start_step=start,
        occupancy_end_step=end,
        recovery_start_minutes_before_occupancy=rec,
        recovery_ramp_minutes=60,
        zone_offsets=zo,
    )


def encode_continuous(params: SixZoneDailyParams) -> np.ndarray:
    zo = [float(params.zone_offsets[k].setback_offset_f) for k in ACTION_KEYS]
    return np.asarray(
        [
            params.occupied_heating_f,
            params.unoccupied_heating_f,
            float(params.occupancy_start_step),
            float(params.occupancy_end_step),
            float(params.recovery_start_minutes_before_occupancy),
            *zo,
        ],
        dtype=np.float32,
    )


def decode_discrete(index: int) -> SixZoneDailyParams:
    n = discrete_n()
    idx = int(index) % n
    n_sb = len(DQN_SETBACK)
    n_rec = len(DQN_REC)
    sb_i = idx % n_sb
    idx //= n_sb
    rec_i = idx % n_rec
    idx //= n_rec
    unocc_i = idx % len(DQN_UNOCC)
    unocc = DQN_UNOCC[unocc_i]
    rec = DQN_REC[rec_i]
    sb = DQN_SETBACK[sb_i]
    zo = {k: ZoneOffsets(setback_offset_f=float(sb)) for k in ACTION_KEYS}
    return SixZoneDailyParams(
        occupied_heating_f=70.0,
        unoccupied_heating_f=float(unocc),
        occupancy_start_step=28,
        occupancy_end_step=68,
        recovery_start_minutes_before_occupancy=int(rec),
        recovery_ramp_minutes=60,
        zone_offsets=zo,
    )


OBS_SCHEMA_V2 = "vibe22.obs.v2"
N_OBS_V2 = 19


def observation_space(n: int = N_OBS_V2) -> gym.spaces.Box:
    return gym.spaces.Box(low=-np.inf, high=np.inf, shape=(n,), dtype=np.float32)


def build_day_observation(
    *,
    month: int,
    dow: int,
    doy: int,
    oat_mean_c: float,
    oat_min_c: float,
    oat_max_c: float,
    billing_floor_kw: float = 0.0,
    mtd_peak_kw: float = 0.0,
    morning_min_c: float | None = None,
    hours_below_0c: float = 0.0,
    hours_below_m10c: float = 0.0,
    forecast_is_live: float = 0.0,
    illustrative_school_day: float = 0.0,
    zone_temps_f: Sequence[float] | None = None,
    prior_peak_kw: float | None = None,
    prior_kwh: float | None = None,
    site_occ_f: float | None = None,
    site_unocc_f: float | None = None,
) -> np.ndarray:
    """vibe22.obs.v2: calendar + compact forecast + billing + six start-of-day zone F.

    Compact 6 forecast stats (not 24 hourly OAT) to avoid overfitting a 1-step
    contextual bandit. Full hourly OAT belongs on the episode artifact.
    ``prior_peak_kw`` is accepted as an alias for ``mtd_peak_kw``.
    """
    _ = (prior_kwh, site_occ_f, site_unocc_f)
    if prior_peak_kw is not None and not mtd_peak_kw:
        mtd_peak_kw = float(prior_peak_kw)
    morn = oat_min_c if morning_min_c is None else float(morning_min_c)
    zt = [70.0] * 6
    if zone_temps_f is not None:
        vals = [float(x) for x in zone_temps_f]
        if len(vals) != 6:
            raise ValueError(f"need 6 zone temps, got {len(vals)}")
        zt = vals
    return np.asarray(
        [
            month / 12.0,
            dow / 6.0,
            doy / 366.0,
            oat_mean_c / 40.0,
            oat_min_c / 40.0,
            oat_max_c / 40.0,
            morn / 40.0,
            float(hours_below_0c) / 24.0,
            float(hours_below_m10c) / 24.0,
            float(billing_floor_kw) / 500.0,
            float(mtd_peak_kw) / 500.0,
            float(illustrative_school_day),
            zt[0] / 100.0,
            zt[1] / 100.0,
            zt[2] / 100.0,
            zt[3] / 100.0,
            zt[4] / 100.0,
            zt[5] / 100.0,
            float(forecast_is_live),
        ],
        dtype=np.float32,
    )

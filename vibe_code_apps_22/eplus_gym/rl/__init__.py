"""RL daily six-zone DSM package (LIVE EnergyPlus episodes).

Trainer process uses SB3/torch; each LIVE day runs in ``live_day_worker``
subprocess isolation (torch + EnergyPlus delete_state is unsafe in-process).
"""
from __future__ import annotations

from eplus_gym.episode import SCREENING_CLAIM, SIMULATOR

SIMULATOR_REQUIRED = "LIVE_ENERGYPLUS"
SCHOOL_START_STEP = 32  # 08:00

__all__ = ["SCREENING_CLAIM", "SIMULATOR", "SIMULATOR_REQUIRED", "SCHOOL_START_STEP"]

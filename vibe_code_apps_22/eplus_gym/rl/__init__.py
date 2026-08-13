"""RL daily six-zone DSM package (LIVE EnergyPlus episodes).

Trainer process uses SB3/torch; each LIVE day runs in ``live_day_worker``
subprocess isolation (torch + EnergyPlus delete_state is unsafe in-process).
"""
from __future__ import annotations

SCREENING_CLAIM = "ENERGYPLUS DSM OPTIMIZATION SCREENING / RETROSPECTIVE REPLAY"
SIMULATOR_REQUIRED = "LIVE_ENERGYPLUS"
SCHOOL_START_STEP = 32  # 08:00

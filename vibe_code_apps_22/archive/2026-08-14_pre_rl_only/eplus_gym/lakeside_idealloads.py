"""Lakeside IdealLoads gym env (STRUCTURAL_LOAD_DIAGNOSTIC)."""
from __future__ import annotations

from pathlib import Path
from typing import Any, Dict, Tuple, Union

import gymnasium as gym
import numpy as np

from ..env import EnergyPlusEnv
from ..honesty import HONESTY_IDEALLOADS

_ROOT = Path(__file__).resolve().parents[2]
_DEFAULT_IDF = _ROOT / "models" / "eplus" / "lakeside_6zone_gshp_best_utility.idf"


class LakesideIdealLoadsEnv(EnergyPlusEnv):
    """Actuate SCH_HtgSP (°C); observe Electricity:Facility + outdoor drybulb."""

    def __init__(self, env_config: Dict[str, Any]):
        cfg = dict(env_config)
        cfg.setdefault("honesty", HONESTY_IDEALLOADS)
        super().__init__(cfg)

    def get_weather_file(self) -> Union[Path, str]:
        epw = self.env_config.get("epw")
        if not epw:
            raise ValueError("env_config['epw'] required")
        return Path(epw)

    def get_idf_file(self) -> Union[Path, str]:
        idf = self.env_config.get("idf") or _DEFAULT_IDF
        p = Path(idf)
        if not p.is_file():
            raise FileNotFoundError(p)
        return p

    def get_observation_space(self) -> gym.Space:
        # facility J or W depending on meter — treat as unbounded float vector
        n = len(self.get_variables()) + len(self.get_meters())
        return gym.spaces.Box(low=-np.inf, high=np.inf, shape=(n,), dtype=np.float32)

    def get_action_space(self) -> gym.Space:
        # heating setpoint °C
        return gym.spaces.Box(low=10.0, high=26.0, shape=(1,), dtype=np.float32)

    def compute_reward(self, obs: Dict[str, float]) -> float:
        # minimize facility electricity (meter often cumulative J — use rate key if present)
        if "facility_w" in obs:
            return -float(obs["facility_w"]) / 1e5
        if "facility_j" in obs:
            return -float(obs["facility_j"]) / 1e8
        # first meter/var value
        if obs:
            return -float(next(iter(obs.values()))) / 1e5
        return 0.0

    def get_variables(self) -> Dict[str, Tuple[str, str]]:
        return {
            "oat_c": ("Site Outdoor Air Drybulb Temperature", "Environment"),
        }

    def get_meters(self) -> Dict[str, str]:
        return {
            "facility_j": "Electricity:Facility",
        }

    def get_actuators(self) -> Dict[str, Tuple[str, str, str]]:
        # Schedule Value on heating SP schedule (EnergyPlus °C)
        name = str(self.env_config.get("htg_schedule", "SCH_HtgSP"))
        return {
            "htg_sp_c": ("Schedule:Compact", "Schedule Value", name),
        }

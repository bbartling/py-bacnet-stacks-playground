"""Lakeside W2A plant gym env (W2A_PHYSICAL_DSM) — A04 champion."""
from __future__ import annotations

from pathlib import Path
from typing import Any, Dict, Tuple, Union

import gymnasium as gym
import numpy as np

from eplus_native.idf_inspect import NINE_ZONES
from eplus_native.zone_agg import aggregate_zone_temps_row, load_agg_contract

from ..env import EnergyPlusEnv
from ..honesty import HONESTY_W2A

_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_IDF = _ROOT / "models" / "eplus" / "lakeside_w2a_a04_dual_champion.idf"
HONESTY = HONESTY_W2A

ZONE_VAR = "Zone Mean Air Temperature"


def _c_to_f(c: float) -> float:
    return float(c) * 9.0 / 5.0 + 32.0


def enrich_obs_with_bas_aggregates(obs: Dict[str, float]) -> Dict[str, float]:
    """Add six BAS aggregate zone temps (°F) from nine raw °C sensors; fail-closed."""
    out = dict(obs)
    temps_f: Dict[str, float] = {}
    missing: list[str] = []
    for z in NINE_ZONES:
        key = f"zone_t_c_{z}"
        if key not in obs or obs[key] != obs[key]:
            missing.append(z)
            continue
        temps_f[z] = _c_to_f(float(obs[key]))
        out[f"zone_t_f_{z}"] = temps_f[z]
    if missing:
        raise ValueError(f"missing zone mean air temps for aggregation: {missing}")
    aggs = aggregate_zone_temps_row(temps_f, load_agg_contract(), mode="hp_count")
    out.update(aggs)
    return out


class LakesideW2AEnv(EnergyPlusEnv):
    """Actuate SCH_HtgSP (°C) on the published W2A champion IDF."""

    def __init__(self, env_config: Dict[str, Any]):
        cfg = dict(env_config)
        cfg.setdefault("honesty", HONESTY_W2A)
        super().__init__(cfg)

    def get_weather_file(self) -> Union[Path, str]:
        epw = self.env_config.get("epw")
        if not epw:
            raise ValueError("env_config['epw'] required")
        return Path(epw)

    def get_idf_file(self) -> Union[Path, str]:
        idf = self.env_config.get("idf") or DEFAULT_IDF
        p = Path(idf)
        if not p.is_file():
            raise FileNotFoundError(p)
        return p

    def get_observation_space(self) -> gym.Space:
        n = len(self.get_variables()) + len(self.get_meters()) + 7  # calendar fields
        return gym.spaces.Box(low=-np.inf, high=np.inf, shape=(n,), dtype=np.float32)

    def get_action_space(self) -> gym.Space:
        return gym.spaces.Box(low=10.0, high=26.0, shape=(1,), dtype=np.float32)

    def compute_reward(self, obs: Dict[str, float]) -> float:
        if "facility_w" in obs:
            return -float(obs["facility_w"]) / 1e5
        if "facility_j" in obs:
            return -float(obs["facility_j"]) / 1e8
        if obs:
            return -float(next(iter(obs.values()))) / 1e5
        return 0.0

    def get_variables(self) -> Dict[str, Tuple[str, str]]:
        vars_: Dict[str, Tuple[str, str]] = {
            "oat_c": ("Site Outdoor Air Drybulb Temperature", "Environment"),
        }
        for z in NINE_ZONES:
            vars_[f"zone_t_c_{z}"] = (ZONE_VAR, z)
        return vars_

    def get_meters(self) -> Dict[str, str]:
        return {
            "facility_j": "Electricity:Facility",
        }

    def get_actuators(self) -> Dict[str, Tuple[str, str, str]]:
        name = str(self.env_config.get("htg_schedule", "SCH_HtgSP"))
        return {
            "htg_sp_c": ("Schedule:Compact", "Schedule Value", name),
        }

    def step(self, action):
        obs_vec, reward, done, truncated, info = super().step(action)
        od = dict(info.get("obs_dict") or {})
        try:
            info["obs_dict"] = enrich_obs_with_bas_aggregates(od)
            info["zone_agg_ok"] = True
        except ValueError as exc:
            info["obs_dict"] = od
            info["zone_agg_ok"] = False
            info["zone_agg_error"] = str(exc)
        return obs_vec, reward, done, truncated, info

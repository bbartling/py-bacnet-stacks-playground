"""Lakeside W2A plant gym env — six BAS-zone heating actuators (or legacy scalar)."""
from __future__ import annotations

from pathlib import Path
from typing import Any, Dict, List, Tuple, Union

import gymnasium as gym
import numpy as np

from eplus_native.idf_inspect import NINE_ZONES
from eplus_native.six_zone_htg_stage import ACTION_KEYS, dsm_htg_schedule_name
from eplus_native.zone_agg import aggregate_zone_temps_row, load_agg_contract

from ..a04_identity import A04_IDF_NAME, is_a04_idf_filename, is_allowed_lakeside_gym_idf
from ..env import EnergyPlusEnv
from ..honesty import HONESTY_W2A

_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_IDF = _ROOT / "models" / "eplus" / A04_IDF_NAME
HONESTY = HONESTY_W2A
ZONE_VAR = "Zone Mean Air Temperature"

__all__ = ["A04_IDF_NAME", "DEFAULT_IDF", "HONESTY", "ZONE_VAR", "is_a04_idf_filename"]

OBS_META_KEYS = (
    "oat_c",
    "facility_j",
    "ep_year",
    "ep_month",
    "ep_day",
    "ep_hour",
    "ep_minute",
    "kind_of_sim",
    "warmup",
)


def _c_to_f(c: float) -> float:
    return float(c) * 9.0 / 5.0 + 32.0


def enrich_obs_with_bas_and_setpoints(
    obs: Dict[str, float],
    *,
    requested_c: List[float] | None = None,
    six_zone: bool = True,
) -> Dict[str, float]:
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
        raise ValueError(f"missing zone mean air temps: {missing}")
    aggs = aggregate_zone_temps_row(temps_f, load_agg_contract(), mode="hp_count")
    out.update(aggs)
    if six_zone and requested_c is not None and len(requested_c) == len(ACTION_KEYS):
        for key, val_c in zip(ACTION_KEYS, requested_c):
            out[f"htg_sp_{key}_c"] = float(val_c)
            out[f"htg_sp_{key}_f"] = _c_to_f(float(val_c))
    if six_zone:
        for key in ACTION_KEYS:
            applied_key = f"applied_htg_sp_c_{key}"
            if applied_key in obs and obs[applied_key] == obs[applied_key]:
                out[f"htg_sp_applied_{key}_c"] = float(obs[applied_key])
                out[f"htg_sp_applied_{key}_f"] = _c_to_f(float(obs[applied_key]))
                out.setdefault(f"htg_sp_{key}_f", out[f"htg_sp_applied_{key}_f"])
    if "facility_j" in out and out["facility_j"] == out["facility_j"]:
        out["facility_kw"] = float(out["facility_j"]) / 900_000.0
    return out


class LakesideW2AEnv(EnergyPlusEnv):
    """Actuate DSM six-zone schedules or legacy single SCH_HtgSP."""

    ACTION_KEYS = ACTION_KEYS

    def __init__(self, env_config: Dict[str, Any]):
        cfg = dict(env_config)
        cfg.setdefault("honesty", HONESTY_W2A)
        self.six_zone = bool(cfg.get("six_zone_actuators", True))
        super().__init__(cfg)

    def get_weather_file(self) -> Union[Path, str]:
        epw = self.env_config.get("epw")
        if not epw:
            raise ValueError("env_config['epw'] required")
        return Path(epw)

    def get_idf_file(self) -> Union[Path, str]:
        idf = self.env_config.get("idf") or DEFAULT_IDF
        p = Path(idf)
        if not is_allowed_lakeside_gym_idf(p.name):
            raise FileNotFoundError(
                f"fail-closed: Lakeside A04 / A04-v2 / Track B required "
                f"({A04_IDF_NAME} or lakeside_w2a_a04v2_*.idf or lakeside_w2a_trackb_*.idf), got {p.name}"
            )
        if not p.is_file():
            raise FileNotFoundError(p)
        return p

    def get_observation_space(self) -> gym.Space:
        n = 80 if self.six_zone else 40
        return gym.spaces.Box(low=-np.inf, high=np.inf, shape=(n,), dtype=np.float32)

    def get_action_space(self) -> gym.Space:
        if self.six_zone:
            return gym.spaces.Box(low=10.0, high=26.0, shape=(6,), dtype=np.float32)
        return gym.spaces.Box(low=10.0, high=26.0, shape=(1,), dtype=np.float32)

    def compute_reward(self, obs: Dict[str, float]) -> float:
        if "facility_j" in obs and obs["facility_j"] == obs["facility_j"]:
            return -float(obs["facility_j"]) / 1e8
        if "facility_kw" in obs and obs["facility_kw"] == obs["facility_kw"]:
            return -float(obs["facility_kw"]) / 100.0
        return 0.0

    def get_variables(self) -> Dict[str, Tuple[str, str]]:
        vars_: Dict[str, Tuple[str, str]] = {
            "oat_c": ("Site Outdoor Air Drybulb Temperature", "Environment"),
        }
        for z in NINE_ZONES:
            vars_[f"zone_t_c_{z}"] = (ZONE_VAR, z)
        return vars_

    def get_meters(self) -> Dict[str, str]:
        return {"facility_j": "Electricity:Facility"}

    def get_actuators(self) -> Dict[str, Tuple[str, str, str]]:
        if not self.six_zone:
            name = str(self.env_config.get("htg_schedule", "SCH_HtgSP"))
            return {"htg_sp_c": ("Schedule:Compact", "Schedule Value", name)}
        out: Dict[str, Tuple[str, str, str]] = {}
        for key in ACTION_KEYS:
            out[f"htg_sp_c_{key}"] = (
                "Schedule:Compact",
                "Schedule Value",
                dsm_htg_schedule_name(key),
            )
        return out

    def step(self, action):
        obs_vec, reward, done, truncated, info = super().step(action)
        od = dict(info.get("obs_dict") or {})
        req = info.get("action")
        req_list = list(req) if isinstance(req, list) else None
        try:
            info["obs_dict"] = enrich_obs_with_bas_and_setpoints(
                od, requested_c=req_list, six_zone=self.six_zone
            )
            info["zone_agg_ok"] = True
        except ValueError as exc:
            info["obs_dict"] = od
            info["zone_agg_ok"] = False
            info["zone_agg_error"] = str(exc)
        return obs_vec, reward, done, truncated, info

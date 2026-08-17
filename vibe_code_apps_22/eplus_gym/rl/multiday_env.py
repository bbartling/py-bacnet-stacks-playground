"""Multi-day daily-decision env. One EnergyPlus process per episode; one action per day."""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date, timedelta
from typing import Any, Sequence

import gymnasium as gym
import numpy as np

from eplus_gym.control_v2 import (
    SixZoneDailyParamsV2,
    build_six_schedules_f,
    chronological_days,
    school_windows,
)
from eplus_gym.rl.billing_state import BillingState
from eplus_gym.rl.obs_v3 import (
    N_OBS_V3,
    build_observation_v3,
    observation_space_v3,
    params_to_prev_action,
)
from eplus_gym.rl.reward import FAIL_REWARD, INFEASIBLE_TRAIN_REWARD
from eplus_gym.rl.spaces_v2 import (
    continuous_action_space_v2,
    decode_continuous_v2,
    decode_discrete_v2,
    discrete_action_space_v2,
    encode_continuous_v2,
)
from eplus_gym.objective import DT_H

DEMAND_RATE = 15.0
ENERGY_RATE = 0.12


def incremental_monthly_demand_cost(
    *,
    demand_rate: float,
    billing_floor_kw: float,
    candidate_day_peak_kw: float,
    baseline_day_peak_kw: float,
) -> float:
    return float(demand_rate) * (
        max(float(billing_floor_kw), float(candidate_day_peak_kw))
        - max(float(billing_floor_kw), float(baseline_day_peak_kw))
    )


@dataclass
class FakeContinuityPlant:
    """Carries thermal and billing-relevant state across days without restarting.

    This is a test double for MultiDayDailyEnv bookkeeping. It is not EnergyPlus
    and must not be used as a surrogate trajectory in scored campaigns.
    """

    zone_temps_f: list[float] = field(default_factory=lambda: [64.0] * 6)
    n_process_starts: int = 0
    n_days: int = 0
    last_schedules: dict[str, list[float]] | None = None
    morning_peak_kw: float = 0.0
    daily_kwh: float = 0.0
    live_energyplus: bool = False

    def start_episode(self) -> None:
        self.n_process_starts += 1
        self.n_days = 0

    def simulate_day(self, schedules: dict[str, list[float]], *, oat_c: Sequence[float]) -> dict[str, Any]:
        if self.n_process_starts < 1:
            raise RuntimeError("start_episode() first; refusing a per-day EnergyPlus restart")
        self.n_days += 1
        self.last_schedules = {k: list(v) for k, v in schedules.items()}
        first = next(iter(schedules.values()))
        continuous = max(first) - min(first) < 1e-6
        mean_sp = float(np.mean(first))
        oat = [float(x) for x in oat_c]
        # Carry overnight temps: setback cools the mass; continuous holds it.
        if continuous:
            self.zone_temps_f = [mean_sp] * 6
            recovery_kw = 40.0
        else:
            night = min(first)
            self.zone_temps_f = [0.7 * t + 0.3 * night for t in self.zone_temps_f]
            recovery_kw = 40.0 + max(0.0, 70.0 - float(np.mean(self.zone_temps_f))) * 8.0
            self.zone_temps_f = [0.4 * t + 0.6 * max(first) for t in self.zone_temps_f]
        self.morning_peak_kw = recovery_kw + max(0.0, -min(oat)) * 1.5
        self.daily_kwh = (mean_sp / 70.0) * (80.0 if continuous else 55.0)
        return {
            "start_zone_temps_f": list(self.zone_temps_f),
            "peak_kw": float(self.morning_peak_kw),
            "daily_kwh": float(self.daily_kwh),
            "n_process_starts": self.n_process_starts,
            "live_energyplus": self.live_energyplus,
        }


class MultiDayDailyEnv(gym.Env):
    """One RL step = one civil day. EnergyPlus (or the test double) is not reset at midnight."""

    metadata = {"render_modes": []}

    def __init__(self, env_config: dict[str, Any] | None = None):
        super().__init__()
        cfg = dict(env_config or {})
        self.cfg = cfg
        self.n_days = int(cfg.get("n_days") or 3)
        self.start_day = str(cfg.get("start_day") or "2026-01-12")
        self.days = list(cfg.get("days") or chronological_days(self.start_day, self.n_days))
        self.algo_space = str(cfg.get("action_kind") or "continuous")
        self.plant: FakeContinuityPlant = cfg.get("plant") or FakeContinuityPlant()
        self.hourly_oat: dict[str, list[float]] = dict(cfg.get("hourly_oat") or {})
        self._billing = BillingState(
            floor_kw=float(cfg.get("billing_floor_kw") or 0.0),
            ratchet_kw=float(cfg.get("ratchet_kw") or 0.0),
            contract_kw=float(cfg.get("contract_demand_kw") or 0.0),
        )
        self._baseline_billing = BillingState(
            floor_kw=float(cfg.get("billing_floor_kw") or 0.0),
            ratchet_kw=float(cfg.get("ratchet_kw") or 0.0),
            contract_kw=float(cfg.get("contract_demand_kw") or 0.0),
        )
        self._day_i = 0
        self._prev_action = [0.0] * 11
        self._prev_peak = 0.0
        self._prev_kwh = 0.0
        self._prev_cc = 0.0
        self._episode_return = 0.0
        if self.algo_space == "discrete":
            self.action_space = discrete_action_space_v2()
        else:
            self.action_space = continuous_action_space_v2()
        self.observation_space = observation_space_v3()

    def _oat(self, day: str) -> list[float]:
        if day in self.hourly_oat:
            vals = [float(x) for x in self.hourly_oat[day]]
            if len(vals) != 24:
                raise ValueError("hourly OAT must be 24 values")
            return vals
        # Deterministic placeholder when no EPW is supplied (unit tests).
        return [-10.0] * 24

    def _obs(self, day: str):
        floor = self._billing.start_of_day(day)
        return build_observation_v3(
            day=day,
            hourly_oat_c=self._oat(day),
            zone_temps_f=self.plant.zone_temps_f,
            billing_floor_kw=floor,
            mtd_peak_kw=floor,
            previous_day_peak_kw=self._prev_peak,
            previous_day_kwh=self._prev_kwh,
            previous_action=self._prev_action,
            continuous_conditioning_state=self._prev_cc,
        )

    def reset(self, *, seed: int | None = None, options: dict | None = None):
        super().reset(seed=seed)
        self.plant.start_episode()
        self._day_i = 0
        self._prev_action = [0.0] * 11
        self._prev_peak = 0.0
        self._prev_kwh = 0.0
        self._prev_cc = 0.0
        self._episode_return = 0.0
        init = dict(
            floor_kw=float(self.cfg.get("billing_floor_kw") or 0.0),
            ratchet_kw=float(self.cfg.get("ratchet_kw") or 0.0),
            contract_kw=float(self.cfg.get("contract_demand_kw") or 0.0),
        )
        self._billing = BillingState(**init)
        self._baseline_billing = BillingState(**init)
        day = self.days[0]
        obs, ctx = self._obs(day)
        info = {
            "day": day,
            "school": school_windows(day),
            "n_process_starts": self.plant.n_process_starts,
            "obs_ctx": ctx,
            "live_energyplus": self.plant.live_energyplus,
        }
        return obs, info

    def _decode(self, action) -> SixZoneDailyParamsV2:
        day = self.days[min(self._day_i, len(self.days) - 1)]
        if self.algo_space == "discrete":
            return decode_discrete_v2(int(np.asarray(action).reshape(-1)[0]), day=day)
        return decode_continuous_v2(action)

    def step(self, action):
        if self._day_i >= len(self.days):
            raise RuntimeError("episode already done")
        day = self.days[self._day_i]
        params = self._decode(action)
        schedules = build_six_schedules_f(params)
        payload = self.plant.simulate_day(schedules, oat_c=self._oat(day))
        peak = float(payload["peak_kw"])
        kwh = float(payload["daily_kwh"])
        floor = self._billing.start_of_day(day)
        base_floor = self._baseline_billing.start_of_day(day)
        energy_cost = ENERGY_RATE * kwh
        demand_cost = incremental_monthly_demand_cost(
            demand_rate=DEMAND_RATE,
            billing_floor_kw=floor,
            candidate_day_peak_kw=peak,
            baseline_day_peak_kw=float(self.cfg.get("baseline_day_peak_kw") or peak),
        )
        win = school_windows(day)
        readiness_fail = False
        if win["readiness_check_steps"]:
            mean_t = float(np.mean(self.plant.zone_temps_f))
            readiness_fail = mean_t < 67.5
        if payload.get("failed"):
            reward = FAIL_REWARD
            display = float("nan")
        elif readiness_fail:
            reward = INFEASIBLE_TRAIN_REWARD
            display = 0.0
        else:
            reward = -(energy_cost + demand_cost)
            display = -(energy_cost + demand_cost)
        self._billing.observe_peak(peak)
        self._baseline_billing.observe_peak(float(self.cfg.get("baseline_day_peak_kw") or peak))
        self._prev_action = encode_continuous_v2(params).astype(float).tolist()
        self._prev_peak = peak
        self._prev_kwh = kwh
        self._prev_cc = 1.0 if params.continuous_conditioning else 0.0
        self._episode_return += float(reward)
        self._day_i += 1
        terminated = self._day_i >= len(self.days)
        if terminated:
            obs = np.zeros(N_OBS_V3, dtype=np.float32)
            next_day = None
        else:
            next_day = self.days[self._day_i]
            obs, _ctx = self._obs(next_day)
        info = {
            "day": day,
            "next_day": next_day,
            "energy_cost": energy_cost,
            "incremental_demand_cost": demand_cost,
            "display_paycheck_usd": display,
            "peak_kw": peak,
            "daily_kwh": kwh,
            "readiness_fail": readiness_fail,
            "continuous_conditioning": params.continuous_conditioning,
            "n_process_starts": self.plant.n_process_starts,
            "n_days_simulated": self.plant.n_days,
            "episode_return": self._episode_return,
            "billing_floor_kw": self._billing.billing_floor_kw(),
            "live_energyplus": self.plant.live_energyplus,
            "dt_h": DT_H,
        }
        return obs, float(reward), terminated, False, info

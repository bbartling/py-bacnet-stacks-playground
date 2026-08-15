"""Day-MDP Gymnasium env: one SB3 step = one LIVE EnergyPlus day.

Default: each day runs in a **subprocess** so torch/SB3 never coexists with
pyenergyplus (Windows heap corruption on ``delete_state``).
"""
from __future__ import annotations

from datetime import date
from pathlib import Path
from typing import Any, Callable, Dict, Optional

import gymnasium as gym
import numpy as np

from eplus_gym.episode import SCREENING_CLAIM
from eplus_gym.rl import SCHOOL_START_STEP, SIMULATOR_REQUIRED
from eplus_gym.rl.day_pool import calendar_day
from eplus_gym.rl.live_day_worker import run_live_day_inprocess, run_live_day_subprocess
from eplus_gym.rl.midnight_forecast import forecast_from_epw_replay
from eplus_gym.rl.billing_state import BillingState
from eplus_gym.rl.reward import FAIL_REWARD, RewardBreakdown, RewardWeights
from eplus_gym.rl.spaces import (
    N_OBS_V2,
    build_day_observation,
    continuous_action_space,
    decode_continuous,
    decode_discrete,
    discrete_action_space,
    observation_space,
)


def _breakdown_from_payload(payload: Dict[str, Any]) -> RewardBreakdown:
    return RewardBreakdown(
        reward=float(payload.get("reward", FAIL_REWARD)),
        daily_kwh=float(payload.get("daily_kwh", float("nan"))),
        peak_kw=float(payload.get("peak_kw", float("nan"))),
        energy_cost=float(payload.get("energy_cost", float("nan"))),
        peak_cost=float(payload.get("peak_cost", float("nan"))),
        pre8_violations=int(payload.get("pre8_violations", 0) or 0),
        pre8_degree_hours=float(payload.get("pre8_degree_hours", 0.0) or 0.0),
        occ_violations=int(payload.get("occ_violations", 0) or 0),
        failed=bool(payload.get("failed")),
        extras=dict(payload.get("extras") or {}),
    )


class DailySixZoneGymEnv(gym.Env):
    """Length-1 MDP: reset → obs; step(action) → full LIVE day → terminated."""

    metadata = {"render_modes": []}

    def __init__(self, env_config: Dict[str, Any]):
        super().__init__()
        self.cfg = dict(env_config)
        sim = str(self.cfg.get("simulator") or SIMULATOR_REQUIRED)
        if sim != SIMULATOR_REQUIRED and sim != "LIVE_ENERGYPLUS":
            raise ValueError(f"refusing simulator={sim!r}; require {SIMULATOR_REQUIRED}")
        self.site_root = Path(self.cfg["site_root"])
        self.epw = Path(self.cfg["epw"])
        self.champion_idf = Path(self.cfg["champion_idf"])
        self.output_root = Path(
            self.cfg.get("output_root")
            or (self.site_root / "reports" / "eplus_gym" / "rl" / "_episodes")
        )
        self.days: list[str] = sorted(
            [str(d) for d in (self.cfg.get("days") or ["2026-01-26"])],
            key=lambda x: str(x)[:10],
        )
        self._specs: dict[str, dict] = {}
        for spec in self.cfg.get("day_specs") or []:
            if isinstance(spec, dict) and spec.get("id"):
                self._specs[str(spec["id"])] = spec
        self.algo_space = str(self.cfg.get("action_kind") or "continuous")
        rw = self.cfg.get("reward_weights")
        self.reward_weights = (
            RewardWeights(**rw) if isinstance(rw, dict) else RewardWeights()
        )
        self.site_occ_f = float(self.cfg.get("occupied_heating_f", 70.0))
        self.site_unocc_f = float(self.cfg.get("unoccupied_heating_f", 65.0))
        # Default isolate: torch + E+ delete_state is unsafe in-process on Windows.
        self.isolate_eplus = bool(self.cfg.get("isolate_eplus", True))
        self._day_i = 0
        self._prior_peak = 0.0
        self._prior_kwh = 0.0
        self._start_temps: dict[str, list[float]] = dict(self.cfg.get("start_temps") or {})
        self._billing_init = dict(
            floor_kw=float(self.cfg.get("billing_floor_kw") or 0.0),
            ratchet_kw=float(self.cfg.get("ratchet_kw") or 0.0),
            contract_kw=float(self.cfg.get("contract_demand_kw") or 0.0),
        )
        self._billing = BillingState(**self._billing_init)
        self._last_day: Optional[str] = None
        self._rng = np.random.default_rng(int(self.cfg.get("seed", 0)))
        self._ep_counter = 0

        if self.algo_space == "discrete":
            self.action_space = discrete_action_space()
        else:
            self.action_space = continuous_action_space()
        self.observation_space = observation_space(N_OBS_V2)
        self.sha256_file: Callable[[Path], str] | None = self.cfg.get("sha256_file")

    def _pick_day(self) -> str:
        if self.cfg.get("cycle_days", True):
            if self._day_i > 0 and self._day_i % max(1, len(self.days)) == 0:
                self._billing = BillingState(**self._billing_init)
                self._prior_peak = 0.0
                self._prior_kwh = 0.0
            d = self.days[self._day_i % len(self.days)]
            self._day_i += 1
            return d
        return str(self.days[int(self._rng.integers(0, len(self.days)))])

    def _norm_id(self, raw: str) -> str:
        s = str(raw)
        if "__" in s:
            return s
        return s[:10]

    def _calendar(self, day_id: str) -> str:
        spec = self._specs.get(day_id)
        if spec and spec.get("day"):
            return str(spec["day"])[:10]
        return calendar_day(day_id)

    def _epw_for(self, day_id: str) -> Path:
        spec = self._specs.get(day_id)
        if spec and spec.get("epw"):
            return Path(spec["epw"])
        return self.epw

    def _obs_for_day(self, day_s: str) -> np.ndarray:
        cal = self._calendar(day_s)
        d = date.fromisoformat(cal)
        fc = forecast_from_epw_replay(self._epw_for(day_s), d)
        mean_c, min_c, max_c, morn_c, h0, hm10 = fc.features()
        floor = float(self._billing.start_of_day(cal))
        temps = self._start_temps.get(cal) or self._start_temps.get(day_s) or [70.0] * 6
        return build_day_observation(
            month=d.month,
            dow=d.weekday(),
            doy=int(d.strftime("%j")),
            oat_mean_c=mean_c,
            oat_min_c=min_c,
            oat_max_c=max_c,
            billing_floor_kw=floor,
            mtd_peak_kw=floor,
            morning_min_c=morn_c,
            hours_below_0c=h0,
            hours_below_m10c=hm10,
            forecast_is_live=0.0,
            illustrative_school_day=1.0 if d.weekday() < 5 else 0.0,
            zone_temps_f=temps,
        )

    def reset(self, *, seed: int | None = None, options: dict | None = None):
        super().reset(seed=seed)
        if seed is not None:
            self._rng = np.random.default_rng(int(seed))
        opts = options or {}
        day_s = self._norm_id(str(opts.get("day") or self._pick_day()))
        self._last_day = day_s
        info = {
            "scientific_claim": SCREENING_CLAIM,
            "simulator": SIMULATOR_REQUIRED,
            "day": day_s,
            "school_start_step": SCHOOL_START_STEP,
            "isolate_eplus": self.isolate_eplus,
            "weather_kind": (self._specs.get(day_s) or {}).get("kind", "observed"),
        }
        return self._obs_for_day(day_s), info

    def step(self, action):
        day_s = self._last_day or self._pick_day()
        cal = self._calendar(day_s)
        epw = self._epw_for(day_s)
        if self.algo_space == "discrete":
            params = decode_discrete(int(np.asarray(action).reshape(-1)[0]))
        else:
            params = decode_continuous(action)

        self._ep_counter += 1
        ep_dir = self.output_root / f"{day_s.replace(':', '_')}_{self._ep_counter:05d}"
        ep_dir.mkdir(parents=True, exist_ok=True)

        failed = False
        payload: Dict[str, Any]
        try:
            kwargs = dict(
                site_root=self.site_root,
                epw=epw,
                champion_idf=self.champion_idf,
                day=cal,
                params=params.to_dict(),
                ep_dir=ep_dir,
                queue_timeout_s=float(self.cfg.get("queue_timeout_s", 180.0)),
                lookback_days=int(self.cfg.get("lookback_days", 1)),
                reward_name=str(self.cfg.get("reward_name") or "legacy_reward_v1"),
                reward_weights=self.reward_weights.__dict__,
                mtd_peak_kw=float(self._billing.start_of_day(cal)),
            )
            if self.isolate_eplus:
                payload = run_live_day_subprocess(
                    **kwargs,
                    timeout_s=float(self.cfg.get("worker_timeout_s", 600.0)),
                )
            else:
                payload = run_live_day_inprocess(**kwargs)
            if payload.get("failed") or payload.get("error"):
                failed = True
        except Exception as exc:  # noqa: BLE001
            failed = True
            payload = {
                "reward": FAIL_REWARD,
                "failed": True,
                "error": str(exc),
                "daily_kwh": float("nan"),
                "peak_kw": float("nan"),
                "pre8_violations": 0,
                "params": params.to_dict(),
                "day": day_s,
                "n_rows": 0,
            }
            (ep_dir / "error.txt").write_text(str(exc), encoding="utf-8")
            (ep_dir / "reward.json").write_text(
                json_dumps(payload),
                encoding="utf-8",
            )

        br = _breakdown_from_payload(payload)
        if failed:
            br = RewardBreakdown(
                reward=FAIL_REWARD,
                daily_kwh=float("nan"),
                peak_kw=float("nan"),
                energy_cost=float("nan"),
                peak_cost=float("nan"),
                pre8_violations=0,
                pre8_degree_hours=0.0,
                occ_violations=0,
                failed=True,
                extras={"error": payload.get("error")},
            )

        if not br.failed:
            self._prior_peak = float(br.peak_kw)
            self._prior_kwh = float(br.daily_kwh)
            self._billing.observe_peak(float(br.peak_kw))

        info = {
            "day": day_s,
            "reward_breakdown": br.__dict__,
            "params": params.to_dict(),
            "episode_dir": str(ep_dir),
            "failed": bool(br.failed),
            "scientific_claim": SCREENING_CLAIM,
            "simulator": SIMULATOR_REQUIRED,
            "n_rows": int(payload.get("n_rows") or 0),
            "isolate_eplus": self.isolate_eplus,
            "weather_kind": (self._specs.get(day_s) or {}).get("kind", "observed"),
        }
        return self._obs_for_day(day_s), float(br.reward), True, False, info


def json_dumps(obj: Dict[str, Any]) -> str:
    import json

    return json.dumps(obj, indent=2) + "\n"

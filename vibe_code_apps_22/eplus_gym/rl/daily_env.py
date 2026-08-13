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
from eplus_gym.rl.live_day_worker import run_live_day_inprocess, run_live_day_subprocess
from eplus_gym.rl.reward import FAIL_REWARD, RewardBreakdown, RewardWeights
from eplus_gym.rl.spaces import (
    build_day_observation,
    continuous_action_space,
    decode_continuous,
    decode_discrete,
    discrete_action_space,
    observation_space,
)


def _oat_stats_from_epw(epw: Path, day: date) -> tuple[float, float, float]:
    """Parse EPW dry-bulb for civil day (simple line filter)."""
    temps: list[float] = []
    text = Path(epw).read_text(encoding="utf-8", errors="ignore").splitlines()
    for line in text:
        if not line or line[0].isalpha() or line.startswith("!"):
            continue
        parts = line.split(",")
        if len(parts) < 7:
            continue
        try:
            mo, dy = int(parts[1]), int(parts[2])
            if mo == day.month and dy == day.day:
                temps.append(float(parts[6]))
        except ValueError:
            continue
    if not temps:
        return 0.0, 0.0, 0.0
    arr = np.asarray(temps, dtype=float)
    return float(arr.mean()), float(arr.min()), float(arr.max())


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
        self.days: list[str] = [str(d) for d in (self.cfg.get("days") or ["2026-01-26"])]
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
        self._last_day: Optional[str] = None
        self._rng = np.random.default_rng(int(self.cfg.get("seed", 0)))
        self._ep_counter = 0

        if self.algo_space == "discrete":
            self.action_space = discrete_action_space()
        else:
            self.action_space = continuous_action_space()
        self.observation_space = observation_space(16)
        self.sha256_file: Callable[[Path], str] | None = self.cfg.get("sha256_file")

    def _pick_day(self) -> str:
        if self.cfg.get("cycle_days", True):
            d = self.days[self._day_i % len(self.days)]
            self._day_i += 1
            return d
        return str(self.days[int(self._rng.integers(0, len(self.days)))])

    def _obs_for_day(self, day_s: str) -> np.ndarray:
        d = date.fromisoformat(day_s)
        oat_mean, oat_min, oat_max = _oat_stats_from_epw(self.epw, d)
        return build_day_observation(
            month=d.month,
            dow=d.weekday(),
            doy=int(d.strftime("%j")),
            oat_mean_c=oat_mean,
            oat_min_c=oat_min,
            oat_max_c=oat_max,
            prior_peak_kw=self._prior_peak,
            prior_kwh=self._prior_kwh,
            site_occ_f=self.site_occ_f,
            site_unocc_f=self.site_unocc_f,
        )

    def reset(self, *, seed: int | None = None, options: dict | None = None):
        super().reset(seed=seed)
        if seed is not None:
            self._rng = np.random.default_rng(int(seed))
        opts = options or {}
        day_s = str(opts.get("day") or self._pick_day())[:10]
        self._last_day = day_s
        info = {
            "scientific_claim": SCREENING_CLAIM,
            "simulator": SIMULATOR_REQUIRED,
            "day": day_s,
            "school_start_step": SCHOOL_START_STEP,
            "isolate_eplus": self.isolate_eplus,
        }
        return self._obs_for_day(day_s), info

    def step(self, action):
        day_s = self._last_day or self._pick_day()
        if self.algo_space == "discrete":
            params = decode_discrete(int(np.asarray(action).reshape(-1)[0]))
        else:
            params = decode_continuous(action)

        self._ep_counter += 1
        ep_dir = self.output_root / f"{day_s}_{self._ep_counter:05d}"
        ep_dir.mkdir(parents=True, exist_ok=True)

        failed = False
        payload: Dict[str, Any]
        try:
            kwargs = dict(
                site_root=self.site_root,
                epw=self.epw,
                champion_idf=self.champion_idf,
                day=day_s,
                params=params.to_dict(),
                ep_dir=ep_dir,
                queue_timeout_s=float(self.cfg.get("queue_timeout_s", 180.0)),
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
        }
        return self._obs_for_day(day_s), float(br.reward), True, False, info


def json_dumps(obj: Dict[str, Any]) -> str:
    import json

    return json.dumps(obj, indent=2) + "\n"

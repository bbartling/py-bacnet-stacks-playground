"""Multi-day daily-decision env. One EnergyPlus process per episode; one action per day."""
from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass, field
from datetime import date, timedelta
from typing import Any, Mapping, Sequence

import gymnasium as gym
import numpy as np

from eplus_gym.control_v2 import (
    ACTION_KEYS,
    SixZoneDailyParamsV2,
    build_six_schedules_f,
    chronological_days,
    school_windows,
)
from eplus_gym.objective import DT_H
from eplus_gym.rl.billing_state import BillingState
from eplus_gym.rl.obs_v3 import (
    LABELED_PLACEHOLDER_FORECAST,
    N_OBS_V3,
    build_observation_v3,
    observation_space_v3,
)
from eplus_gym.mega.obs_tariff_v4 import N_OBS_V4, build_observation_v4, observation_space_v4
from eplus_gym.rl.reward_v2 import (
    IntegrityFailure,
    MissingBaselineError,
    score_day_v2,
)
from eplus_gym.rl.spaces_v2 import (
    continuous_action_space_v2,
    decode_continuous_v2,
    decode_discrete_v2,
    discrete_action_space_v2,
    encode_continuous_v2,
)

DEMAND_RATE = 15.0
ENERGY_RATE = 0.12


def incremental_monthly_demand_cost(
    *,
    demand_rate: float,
    billing_floor_kw: float,
    candidate_day_peak_kw: float,
    baseline_day_peak_kw: float,
) -> float:
    """Legacy helper kept for unit tests. New campaigns use reward_v2 dual-arm accounting."""
    return float(demand_rate) * (
        max(float(billing_floor_kw), float(candidate_day_peak_kw))
        - max(float(billing_floor_kw), float(baseline_day_peak_kw))
    )


def baseline_cache_key_v2(
    *,
    model_id: str,
    weather_id: str,
    run_period: str,
    initial_state_id: str,
    schedule_id: str,
) -> str:
    payload = "|".join(
        [str(model_id), str(weather_id), str(run_period), str(initial_state_id), str(schedule_id)]
    )
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def schedule_fingerprint(schedules: Mapping[str, Sequence[float]]) -> str:
    body = {k: [round(float(x), 4) for x in schedules[k]] for k in ACTION_KEYS}
    return hashlib.sha256(json.dumps(body, sort_keys=True).encode("utf-8")).hexdigest()


def trajectory_hash(payload: Mapping[str, Any]) -> str:
    body = {
        "facility_kw": [round(float(x), 6) for x in payload.get("facility_kw") or []],
        "n_intervals": int(payload.get("n_intervals") or 0),
    }
    return hashlib.sha256(json.dumps(body, sort_keys=True).encode("utf-8")).hexdigest()


def validate_baseline_payload(
    payload: Mapping[str, Any],
    *,
    live_energyplus: bool,
    expected_day: str,
    expected_idf_sha256: str | None = None,
    expected_epw_sha256: str | None = None,
    expected_energyplus_version: str | None = None,
    expected_lookback_fp: str | None = None,
    expected_baseline_fp: str | None = None,
) -> dict[str, Any]:
    if not isinstance(payload, Mapping):
        raise MissingBaselineError("baseline payload is not a mapping")
    if payload.get("TEST_DOUBLE"):
        if live_energyplus:
            raise MissingBaselineError("TEST DOUBLE cannot satisfy a live EnergyPlus baseline")
        fac = payload.get("facility_kw")
        zones = payload.get("zone_temps_series_f")
        if fac is None or zones is None:
            raise MissingBaselineError("TEST DOUBLE missing trajectory")
        n = int(payload.get("n_intervals") or len(fac))
        if n != 96:
            raise MissingBaselineError("TEST DOUBLE expected 96 intervals")
        return dict(payload)
    required = (
        "idf_sha256",
        "epw_sha256",
        "energyplus_version",
        "run_period",
        "lookback_schedule_fingerprint",
        "baseline_schedule_fingerprint",
        "initial_state_id",
        "trajectory_hash",
        "n_intervals",
        "facility_kw",
        "zone_temps_series_f",
    )
    missing = [k for k in required if payload.get(k) in (None, "")]
    if missing:
        raise MissingBaselineError(f"baseline provenance missing: {missing}")
    if str(payload.get("baseline_schedule_fingerprint")) == "paired_baseline":
        raise MissingBaselineError("schedule_fingerprint must not be the literal paired_baseline")
    if int(payload.get("n_intervals") or 0) != 96:
        raise MissingBaselineError("expected 96 intervals")
    if expected_idf_sha256 and str(payload["idf_sha256"]) != str(expected_idf_sha256):
        raise MissingBaselineError("baseline IDF SHA-256 mismatch")
    if expected_epw_sha256 and str(payload["epw_sha256"]) != str(expected_epw_sha256):
        raise MissingBaselineError("baseline staged EPW SHA-256 mismatch")
    if expected_energyplus_version and str(payload["energyplus_version"]) != str(expected_energyplus_version):
        raise MissingBaselineError("EnergyPlus version mismatch")
    if expected_lookback_fp and str(payload["lookback_schedule_fingerprint"]) != str(expected_lookback_fp):
        raise MissingBaselineError("lookback schedule fingerprint mismatch")
    if expected_baseline_fp and str(payload["baseline_schedule_fingerprint"]) != str(expected_baseline_fp):
        raise MissingBaselineError("baseline schedule fingerprint mismatch")
    if expected_day and payload.get("day") not in (None, expected_day) and expected_day not in str(
        payload.get("run_period") or ""
    ):
        raise MissingBaselineError(f"run period does not include {expected_day}")
    return dict(payload)


def assert_live_campaign_plant(plant: Any) -> None:
    if not bool(getattr(plant, "live_energyplus", False)):
        raise ValueError("campaign paths refuse FakeContinuityPlant; EnergyPlusContinuityPlant required")


def _f_to_series_from_schedule(schedules: Mapping[str, Sequence[float]], *, lag: float = 0.35) -> dict[str, list[float]]:
    out: dict[str, list[float]] = {}
    for key in ACTION_KEYS:
        sp = [float(x) for x in schedules[key]]
        temps = []
        t = float(sp[0])
        for s in sp:
            t = (1.0 - lag) * t + lag * float(s)
            temps.append(t)
        out[key] = temps
    return out


@dataclass
class FakeContinuityPlant:
    """TEST DOUBLE for MultiDayDailyEnv bookkeeping.

    Not EnergyPlus. Must not unlock a model gate. Must not be used as physics evidence.
    """

    zone_temps_f: list[float] = field(default_factory=lambda: [64.0] * 6)
    n_process_starts: int = 0
    n_days: int = 0
    last_schedules: dict[str, list[float]] | None = None
    morning_peak_kw: float = 0.0
    daily_kwh: float = 0.0
    live_energyplus: bool = False
    TEST_DOUBLE: bool = True
    _prev_final_temps: list[float] | None = None

    def start_episode(self) -> None:
        self.n_process_starts += 1
        self.n_days = 0
        self._prev_final_temps = None

    def close(self) -> None:
        return None

    def simulate_day(self, schedules: dict[str, list[float]], *, oat_c: Sequence[float]) -> dict[str, Any]:
        if self.n_process_starts < 1:
            raise RuntimeError("start_episode() first; refusing a per-day EnergyPlus restart")
        start_temps = list(self.zone_temps_f)
        self.n_days += 1
        self.last_schedules = {k: list(schedules[k]) for k in ACTION_KEYS}
        first = schedules[ACTION_KEYS[0]]
        continuous = max(first) - min(first) < 1e-6
        oat = [float(x) for x in oat_c]
        zone_series: dict[str, list[float]] = {}
        for i, key in enumerate(ACTION_KEYS):
            sp = [float(x) for x in schedules[key]]
            t = float(self.zone_temps_f[i])
            temps = []
            for s in sp:
                t = 0.65 * t + 0.35 * float(s)
                temps.append(t)
            zone_series[key] = temps
        final_temps = [zone_series[k][-1] for k in ACTION_KEYS]
        self.zone_temps_f = list(final_temps)
        self._prev_final_temps = list(final_temps)
        facility: list[float] = []
        for t in range(96):
            mean_sp = float(np.mean([schedules[k][t] for k in ACTION_KEYS]))
            rec = 0.0 if continuous else max(0.0, 70.0 - mean_sp) * 1.2
            oat_i = oat[min(len(oat) - 1, t // 4)] if oat else 0.0
            kw = 35.0 + mean_sp * 0.4 + rec + max(0.0, -oat_i) * 0.8
            if 24 <= t <= 36 and not continuous:
                kw += 25.0
            facility.append(float(kw))
        self.morning_peak_kw = float(max(facility))
        self.daily_kwh = float(sum(facility) * DT_H)
        return {
            "TEST_DOUBLE": True,
            "start_zone_temps_f": list(start_temps),
            "zone_temps_f": list(final_temps),
            "final_zone_temps_f": list(final_temps),
            "zone_temps_series_f": zone_series,
            "facility_kw": facility,
            "peak_kw": float(self.morning_peak_kw),
            "daily_kwh": float(self.daily_kwh),
            "n_intervals": 96,
            "n_process_starts": self.n_process_starts,
            "live_energyplus": self.live_energyplus,
            "first_runtime_timestamp": "TEST_DOUBLE+step0",
            "last_runtime_timestamp": "TEST_DOUBLE+step95",
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
        self._research_contract = str(cfg.get("action_contract_version") or "")
        self._research_v1 = self._research_contract == "research_action_contract_v1"
        self._research_v2 = self._research_contract == "research_action_contract_v2"
        self._research = self._research_v1 or self._research_v2
        self._all_days = list(self.days)
        self._block_size = int(cfg.get("block_size") or 0)
        self._block_cursor = int(cfg.get("block_cursor") or 0)
        self._persist_billing = bool(cfg.get("persist_billing"))
        self.plant = cfg.get("plant") or FakeContinuityPlant()
        if cfg.get("require_live_energyplus"):
            assert_live_campaign_plant(self.plant)
        self.hourly_oat: dict[str, list[float]] = dict(cfg.get("hourly_oat") or {})
        self._placeholder_oat = cfg.get("labeled_placeholder_oat_c")
        self._forecast_source = str(cfg.get("forecast_source") or "PERFECT_EPISODE_FORECAST")
        self._obs_schema = str(cfg.get("obs_schema") or "v3")
        self._tariff_mode = str(cfg.get("tariff_mode") or "flat_illustrative")
        self.paycheck_k = float(cfg.get("paycheck_k") or 2.0)
        self._model_id = str(cfg.get("model_id") or "fake")
        self._weather_id = str(cfg.get("weather_id") or "fake")
        self._initial_state_id = str(cfg.get("initial_state_id") or "default")
        self._baseline_cache: dict[str, dict[str, Any]] = dict(cfg.get("baseline_cache") or {})
        self._baseline_payloads: dict[str, dict[str, Any]] = dict(cfg.get("baseline_payloads") or {})
        self._require_baseline = bool(cfg.get("require_baseline", True))
        init = dict(
            floor_kw=float(cfg.get("billing_floor_kw") or 0.0),
            ratchet_kw=float(cfg.get("ratchet_kw") or 0.0),
            contract_kw=float(cfg.get("contract_demand_kw") or 0.0),
        )
        self._billing = BillingState(**init)
        self._baseline_billing = BillingState(**init)
        self._day_i = 0
        self._prev_action = [0.0] * 11
        self._prev_schedules: dict[str, list[float]] | None = None
        self._prev_peak = 0.0
        self._prev_kwh = 0.0
        self._prev_cc = 0.0
        self._episode_return = 0.0
        self._closed = False
        self._quality_evidence: dict[str, Any] | None = None
        if self._research_v2:
            from eplus_gym.rl.research_spaces import (
                continuous_action_space_research_v2,
                discrete_action_space_research_v2,
            )

            if self.algo_space == "discrete":
                self.action_space = discrete_action_space_research_v2()
            else:
                self.action_space = continuous_action_space_research_v2()
        elif self._research:
            from eplus_gym.rl.research_spaces import (
                continuous_action_space_research,
                discrete_action_space_research,
            )

            if self.algo_space == "discrete":
                self.action_space = discrete_action_space_research()
            else:
                self.action_space = continuous_action_space_research()
        elif self.algo_space == "discrete":
            self.action_space = discrete_action_space_v2()
        else:
            self.action_space = continuous_action_space_v2()
        if self._obs_schema == "v4":
            self.observation_space = observation_space_v4()
        else:
            self.observation_space = observation_space_v3()

    def _oat(self, day: str) -> tuple[list[float], str]:
        if day in self.hourly_oat:
            vals = [float(x) for x in self.hourly_oat[day]]
            if len(vals) != 24:
                raise ValueError("hourly OAT must be 24 values")
            return vals, self._forecast_source
        if self._placeholder_oat is not None:
            vals = [float(x) for x in self._placeholder_oat]
            if len(vals) == 1:
                vals = vals * 24
            if len(vals) != 24:
                raise ValueError("labeled_placeholder_oat_c must be 24 values or a scalar")
            return vals, LABELED_PLACEHOLDER_FORECAST
        raise ValueError(
            f"missing hourly OAT for {day}; refusing silent -10C forecast "
            "(pass hourly_oat or labeled_placeholder_oat_c)"
        )

    def _tariff_for_step(self) -> tuple[list[float], float, str]:
        from eplus_gym.mega.tariff_modes import build_tariff_forecast_vectors, default_tariff_catalog

        spec = default_tariff_catalog()[self._tariff_mode]
        fc = build_tariff_forecast_vectors(self._tariff_mode)  # type: ignore[arg-type]
        rates = [float(x) for x in fc["next_96x15min_energy_rates"]]
        sha = hashlib.sha256(json.dumps(rates).encode("utf-8")).hexdigest()
        return rates, float(spec.demand_rate_per_kw), sha

    def _obs(self, day: str):
        oat, src = self._oat(day)
        floor = self._billing.billing_floor_kw()
        mtd = self._billing.mtd_peak_kw
        if self._obs_schema == "v4":
            mask = [1.0] * 24 if src != LABELED_PLACEHOLDER_FORECAST else [0.0] * 24
            return build_observation_v4(
                day=day,
                hourly_oat_c=oat,
                forecast_valid_mask=mask,
                zone_temps_f=self.plant.zone_temps_f,
                billing_floor_kw=floor,
                mtd_peak_kw=mtd,
                ratchet_floor_kw=self._billing.ratchet_kw,
                contract_floor_kw=self._billing.contract_kw,
                previous_day_peak_kw=self._prev_peak,
                previous_day_kwh=self._prev_kwh,
                previous_action=self._prev_action,
                continuous_conditioning_state=self._prev_cc,
                tariff_mode=self._tariff_mode,  # type: ignore[arg-type]
            )
        return build_observation_v3(
            day=day,
            hourly_oat_c=oat,
            forecast_source=src,
            zone_temps_f=self.plant.zone_temps_f,
            billing_floor_kw=floor,
            mtd_peak_kw=mtd,
            previous_day_peak_kw=self._prev_peak,
            previous_day_kwh=self._prev_kwh,
            previous_action=self._prev_action,
            continuous_conditioning_state=self._prev_cc,
        )

    def _select_block(self) -> None:
        if int(self._block_size or 0) <= 0 or not self._all_days:
            return
        start = int(self._block_cursor)
        if start >= len(self._all_days):
            start = 0
        self.days = list(self._all_days[start : start + int(self._block_size)])
        if not self.days:
            start = 0
            self.days = list(self._all_days[: int(self._block_size)])
        nxt = start + len(self.days)
        self._block_cursor = 0 if nxt >= len(self._all_days) else nxt

    def reset(self, *, seed: int | None = None, options: dict | None = None):
        super().reset(seed=seed)
        self._select_block()
        self.plant.start_episode()
        self._day_i = 0
        self._prev_action = [0.0] * 11
        self._prev_schedules = None
        self._prev_peak = 0.0
        self._prev_kwh = 0.0
        self._prev_cc = 0.0
        self._episode_return = 0.0
        self._closed = False
        init = dict(
            floor_kw=float(self.cfg.get("billing_floor_kw") or 0.0),
            ratchet_kw=float(self.cfg.get("ratchet_kw") or 0.0),
            contract_kw=float(self.cfg.get("contract_demand_kw") or 0.0),
        )
        if not (self._persist_billing and getattr(self, "_billing", None) is not None):
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
        if getattr(self, "_research_v2", False):
            from eplus_gym.rl.research_spaces import (
                decode_continuous_research_v2,
                decode_discrete_research_v2,
            )

            if self.algo_space == "discrete":
                return decode_discrete_research_v2(int(np.asarray(action).reshape(-1)[0]), day=day)
            return decode_continuous_research_v2(action, day=day)
        if getattr(self, "_research", False):
            from eplus_gym.rl.research_spaces import decode_continuous_research, decode_discrete_research

            if self.algo_space == "discrete":
                return decode_discrete_research(int(np.asarray(action).reshape(-1)[0]), day=day)
            return decode_continuous_research(action, day=day)
        if self.algo_space == "discrete":
            return decode_discrete_v2(int(np.asarray(action).reshape(-1)[0]), day=day)
        return decode_continuous_v2(action)

    def _lookup_baseline(self, day: str) -> dict[str, Any]:
        live = bool(getattr(self.plant, "live_energyplus", False))
        if day in self._baseline_payloads:
            return validate_baseline_payload(
                self._baseline_payloads[day],
                live_energyplus=live,
                expected_day=day,
                expected_idf_sha256=str(self.cfg.get("idf_sha256") or "") or None,
                expected_epw_sha256=str(self.cfg.get("epw_sha256") or "") or None,
                expected_energyplus_version=str(self.cfg.get("energyplus_version") or "") or None,
                expected_lookback_fp=str(self.cfg.get("lookback_schedule_fingerprint") or "") or None,
                expected_baseline_fp=str(self.cfg.get("baseline_schedule_fingerprint") or "") or None,
            )
        sched_fp = str(self.cfg.get("baseline_schedule_fingerprint") or "")
        if sched_fp in {"", "paired_baseline"}:
            raise MissingBaselineError(
                f"paired baseline missing for {day}; refusing literal schedule_id=paired_baseline"
            )
        run_period = f"{self.days[0]}:{self.days[-1]}"
        key = baseline_cache_key_v2(
            model_id=self._model_id,
            weather_id=self._weather_id,
            run_period=f"{run_period}:{day}",
            initial_state_id=self._initial_state_id,
            schedule_id=sched_fp,
        )
        if key in self._baseline_cache:
            return validate_baseline_payload(
                self._baseline_cache[key],
                live_energyplus=live,
                expected_day=day,
                expected_baseline_fp=sched_fp,
            )
        raise MissingBaselineError(f"paired baseline missing for {day} (key={key})")

    def step(self, action):
        if self._day_i >= len(self.days):
            raise RuntimeError("episode already done")
        day = self.days[self._day_i]
        params = self._decode(action)
        if getattr(self, "_research_v2", False):
            from eplus_gym.rl.research_spaces import research_build_six_schedules_f

            schedules = research_build_six_schedules_f(params, day)
        else:
            schedules = build_six_schedules_f(params)
        oat, _src = self._oat(day)
        try:
            payload = self.plant.simulate_day(schedules, oat_c=oat)
        except IntegrityFailure:
            raise
        except Exception as exc:  # noqa: BLE001
            raise IntegrityFailure(f"energyplus_crash:{type(exc).__name__}:{exc}") from exc
        if payload.get("failed") or payload.get("invalid"):
            raise IntegrityFailure(str(payload.get("reason") or "energyplus_crash"))
        facility = payload.get("facility_kw")
        zone_series = payload.get("zone_temps_series_f")
        if facility is None or zone_series is None:
            raise IntegrityFailure("incomplete trajectory: missing facility_kw or zone_temps_series_f")
        if int(payload.get("n_intervals") or len(facility) or 0) != 96:
            raise IntegrityFailure("incomplete trajectory: expected 96 intervals")
        try:
            baseline = self._lookup_baseline(day)
        except MissingBaselineError:
            raise
        b_fac = baseline.get("facility_kw")
        b_zones = baseline.get("zone_temps_series_f")
        cand_old = self._billing.start_of_day(day)
        base_old = self._baseline_billing.start_of_day(day)
        rate_kwh, demand_rate, rate_sha = self._tariff_for_step()
        scored = score_day_v2(
            day=day,
            candidate_facility_kw=facility,
            candidate_zone_temps_f=zone_series,
            baseline_facility_kw=b_fac,
            baseline_zone_temps_f=b_zones,
            candidate_schedules=schedules,
            previous_schedules=self._prev_schedules,
            mtd_peak_kw=self._billing.mtd_peak_kw,
            ratchet_kw=self._billing.ratchet_kw,
            contract_kw=self._billing.contract_kw,
            baseline_mtd_peak_kw=self._baseline_billing.mtd_peak_kw,
            baseline_ratchet_kw=self._baseline_billing.ratchet_kw,
            baseline_contract_kw=self._baseline_billing.contract_kw,
            paycheck_k=self.paycheck_k,
            rate_kwh=rate_kwh,
            demand_rate=demand_rate,
        )
        peak = float(scored.candidate["day_peak_kw"])
        kwh = float(scored.candidate["daily_kwh"])
        self._billing.observe_peak(peak)
        self._baseline_billing.observe_peak(float(scored.baseline["day_peak_kw"]))
        if hasattr(self.plant, "zone_temps_f") and payload.get("zone_temps_f"):
            self.plant.zone_temps_f = list(payload["zone_temps_f"])
        self._prev_action = encode_continuous_v2(params).astype(float).tolist()
        self._prev_schedules = {k: list(schedules[k]) for k in ACTION_KEYS}
        self._prev_peak = peak
        self._prev_kwh = kwh
        self._prev_cc = 1.0 if params.continuous_conditioning else 0.0
        reward = float(scored.training_reward)
        self._episode_return += reward
        self._day_i += 1
        terminated = self._day_i >= len(self.days)
        if terminated:
            n_obs = N_OBS_V4 if self._obs_schema == "v4" else N_OBS_V3
            obs = np.zeros(n_obs, dtype=np.float32)
            next_day = None
        else:
            next_day = self.days[self._day_i]
            obs, _ctx = self._obs(next_day)
        info = {
            "day": day,
            "next_day": next_day,
            "energy_cost": scored.candidate["energy_cost"],
            "incremental_demand_cost": scored.candidate["demand_increment"],
            "candidate_old_floor_kw": scored.candidate["old_floor_kw"],
            "candidate_new_floor_kw": scored.candidate["new_floor_kw"],
            "candidate_day_peak_kw": scored.candidate["day_peak_kw"],
            "baseline_old_floor_kw": scored.baseline["old_floor_kw"],
            "baseline_new_floor_kw": scored.baseline["new_floor_kw"],
            "baseline_day_peak_kw": scored.baseline["day_peak_kw"],
            "savings": scored.savings,
            "display_paycheck_usd": scored.display_paycheck_usd,
            "training_reward": scored.training_reward,
            "peak_kw": peak,
            "daily_kwh": kwh,
            "readiness_fail": not bool(scored.readiness["readiness_ok"]),
            "readiness": scored.readiness,
            "continuous_conditioning": params.continuous_conditioning,
            "n_process_starts": self.plant.n_process_starts,
            "n_days_simulated": self.plant.n_days,
            "episode_return": self._episode_return,
            "billing_floor_kw": self._billing.billing_floor_kw(),
            "mtd_peak_kw": self._billing.mtd_peak_kw,
            "live_energyplus": self.plant.live_energyplus,
            "dt_h": DT_H,
            "learnable": True,
            "billing_floor_at_start_kw": cand_old,
            "baseline_billing_floor_at_start_kw": base_old,
            "block_id": self.cfg.get("block_id") or f"{self.days[0]}:{self.days[-1]}",
            "action": action if not hasattr(action, "tolist") else np.asarray(action).tolist(),
            "decoded_schedule_fingerprint": schedule_fingerprint(schedules),
            "reward": reward,
            "occupied_low_DH": scored.extras.get("occupied_low_DH"),
            "occupied_high_DH": scored.extras.get("occupied_high_DH"),
            "within_day_schedule_movement": scored.extras.get("within_day_schedule_movement"),
            "between_day_action_movement": scored.extras.get("between_day_action_movement"),
            "opening_mtd_kw": cand_old,
            "closing_mtd_kw": self._billing.mtd_peak_kw,
            "eplus_quality_ref": getattr(self.plant, "last_eplus_quality", None),
            "model_sha256": self.cfg.get("idf_sha256"),
            "epw_sha256": self.cfg.get("epw_sha256"),
            "trajectory_sha256": trajectory_hash(payload),
            "payload": payload,
            "tariff_mode": self._tariff_mode,
            "rate_vector_sha256": rate_sha,
            "demand_rate": demand_rate,
            "opening_billing_floor_kw": cand_old,
            "closing_mtd_peak_kw": self._billing.mtd_peak_kw,
            "reward_breakdown": {
                "reward": reward,
                "day": day,
                "daily_kwh": kwh,
                "peak_kw": peak,
                "savings": scored.savings,
            },
        }
        return obs, reward, terminated, False, info

    def close(self):
        if self._closed:
            return
        self._closed = True
        plant = self.plant
        if hasattr(plant, "finish_quality"):
            try:
                self._quality_evidence = plant.finish_quality()
            except Exception:  # noqa: BLE001
                if hasattr(plant, "close"):
                    plant.close()
        elif hasattr(plant, "close"):
            plant.close()
        closer = getattr(super(), "close", None)
        if callable(closer):
            closer()
        return None

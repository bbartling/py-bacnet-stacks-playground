"""One EnergyPlus process per multi-day episode. FakeContinuityPlant is not this class."""
from __future__ import annotations

from datetime import date, timedelta
from pathlib import Path
from typing import Any, Sequence

from eplus_gym.control_v2 import ACTION_KEYS, build_six_schedules_f, continuous_params
from eplus_gym.eplus_err import parse_eplus_err
from eplus_gym.objective import BAS_ZONE_COLS, DT_H
from eplus_gym.rl.reward_v2 import IntegrityFailure
from eplus_gym.simulate import runtime_day_from_obs, validate_live_trajectory_calendar
from eplus_gym.six_zone_daily_controller import f_to_c
from eplus_native.six_zone_htg_stage import ACTION_KEYS as _KEYS

assert ACTION_KEYS == _KEYS

STEPS_PER_DAY = 96


def weather_steps_after_reset(*, lookback_days: int) -> int:
    """reset() already yielded the first RunPeriodWeather timestep (typically 00:15).

    A naive ``lookback_days * 96`` loop therefore overshoots into the first scored
    day and the last gym step of each scored day lands on the next civil date.
    """
    n = int(lookback_days)
    if n < 1:
        raise ValueError("lookback_days must be >= 1; reset() consumes the first weather timestep")
    return n * STEPS_PER_DAY - 1


def lookback_local_indices(*, lookback_days: int) -> list[int]:
    """Schedule indices after reset() consumed slot 0.

    Remaining lookback for one day is 1..95, not a second copy of 0 that drops 95.
    """
    n = weather_steps_after_reset(lookback_days=lookback_days)
    return [(t + 1) % STEPS_PER_DAY for t in range(n)]


def _row_timestamp(row: dict[str, Any], *, fallback: str) -> str:
    for key in ("timestamp", "time", "sim_time", "current_time"):
        if row.get(key) not in (None, ""):
            return str(row[key])
    day = row.get("day")
    step = row.get("local_step")
    if day is not None and step is not None:
        return f"{day}+step{int(step)}"
    return str(fallback)


def _six_temps(od: dict[str, Any]) -> list[float]:
    missing = [c for c in BAS_ZONE_COLS if c not in od or od[c] != od[c]]
    if missing:
        raise IntegrityFailure(f"missing zones: {missing}")
    return [float(od[c]) for c in BAS_ZONE_COLS]


def _zone_series_dict(rows: list[dict[str, Any]]) -> dict[str, list[float]]:
    out: dict[str, list[float]] = {k: [] for k in ACTION_KEYS}
    for row in rows:
        temps = _six_temps(row)
        for key, val in zip(ACTION_KEYS, temps):
            out[key].append(val)
    return out


class EnergyPlusContinuityPlant:
    """Wraps EnergyPlusRunner via LakesideW2AEnv. One process per episode; no midnight restart."""

    live_energyplus = True

    def __init__(
        self,
        *,
        site_root: Path,
        epw: Path,
        idf: Path,
        output: Path,
        days: Sequence[str],
        lookback_days: int = 1,
        lookback_schedules: dict[str, list[float]] | None = None,
        queue_timeout_s: float = 180.0,
    ) -> None:
        self.site_root = Path(site_root)
        self.epw = Path(epw)
        self.idf = Path(idf)
        self.output = Path(output)
        self.days = [str(d)[:10] for d in days]
        self.lookback_days = int(lookback_days)
        if self.lookback_days < 1:
            raise ValueError("lookback_days must be >= 1; reset() consumes the first weather timestep")
        self.lookback_schedules = lookback_schedules or build_six_schedules_f(continuous_params(70.0))
        self.queue_timeout_s = float(queue_timeout_s)
        self.zone_temps_f: list[float] = [70.0] * 6
        self.n_process_starts = 0
        self.n_days = 0
        self._env: Any = None
        self._day_i = 0
        self._prev_final_temps: list[float] | None = None
        self.last_eplus_quality: dict[str, Any] | None = None
        self.TEMP_CONTINUITY_TOL_F = 0.05

    def close(self) -> None:
        if self._env is not None:
            try:
                self._env.close()
            except Exception:  # noqa: BLE001
                pass
            self._env = None

    def start_episode(self) -> None:
        from eplus_gym.envs.lakeside_w2a import LakesideW2AEnv
        from eplus_gym.epw_stage import stage_year_aware_epw
        from eplus_gym.stage_idf import stage_idf_for_period

        self.close()
        self.output.mkdir(parents=True, exist_ok=True)
        first = date.fromisoformat(self.days[0])
        last = date.fromisoformat(self.days[-1])
        begin = first - timedelta(days=self.lookback_days)
        staged_epw = stage_year_aware_epw(self.epw, self.output / f"staged_{self.epw.name}")["staged_epw"]
        staged_idf = stage_idf_for_period(
            self.idf,
            self.output / f"staged_{self.idf.name}",
            begin.isoformat(),
            last.isoformat(),
            site_root=self.site_root,
            six_zone_actuators=True,
        )
        default_c = [f_to_c(self.lookback_schedules[k][0]) for k in ACTION_KEYS]
        self._env = LakesideW2AEnv(
            {
                "epw": str(staged_epw),
                "idf": str(staged_idf),
                "output": str(self.output / "eplus"),
                "queue_timeout_s": self.queue_timeout_s,
                "default_action_c": default_c,
                "six_zone_actuators": True,
            }
        )
        _obs, info = self._env.reset()
        self.n_process_starts += 1
        self.n_days = 0
        self._day_i = 0
        self._prev_final_temps = None
        od = dict(info.get("obs_dict") or {})
        if od:
            try:
                self.zone_temps_f = _six_temps(od)
            except IntegrityFailure:
                pass
        self._consume_lookback()

    def _consume_lookback(self) -> None:
        indices = lookback_local_indices(lookback_days=self.lookback_days)
        last_od: dict[str, Any] = {}
        for local in indices:
            action = [f_to_c(self.lookback_schedules[k][local]) for k in ACTION_KEYS]
            _v, _r, term, trunc, info = self._env.step(action)
            if term or trunc:
                raise IntegrityFailure("EnergyPlus ended during unscored lookback")
            last_od = dict(info.get("obs_dict") or {})
        if last_od:
            self.zone_temps_f = _six_temps(last_od)

    def simulate_day(self, schedules: dict[str, list[float]], *, oat_c: Sequence[float]) -> dict[str, Any]:
        _ = oat_c
        if self._env is None or self.n_process_starts < 1:
            raise RuntimeError("start_episode() first; refusing a per-day EnergyPlus restart")
        if self._day_i >= len(self.days):
            raise IntegrityFailure("no remaining scored days in this EnergyPlus process")
        day = self.days[self._day_i]
        start_temps = list(self.zone_temps_f)
        if self._prev_final_temps is not None:
            deltas = [abs(a - b) for a, b in zip(start_temps, self._prev_final_temps)]
            if any(d > self.TEMP_CONTINUITY_TOL_F for d in deltas):
                raise IntegrityFailure(
                    f"day {day} start temps {start_temps} != previous final {self._prev_final_temps}"
                )
        rows: list[dict[str, Any]] = []
        for t in range(96):
            action = [f_to_c(schedules[k][t]) for k in ACTION_KEYS]
            _v, _r, term, trunc, info = self._env.step(action)
            od = dict(info.get("obs_dict") or {})
            if term or trunc or not od:
                raise IntegrityFailure(f"EnergyPlus ended mid-day {day} at local step {t}")
            rt = runtime_day_from_obs(od)
            row = dict(od)
            row["day"] = rt
            row["local_step"] = t
            if "facility_kw" not in row and "facility_j" in row and row["facility_j"] == row["facility_j"]:
                row["facility_kw"] = float(row["facility_j"]) / 900_000.0
            rows.append(row)
        cal = validate_live_trajectory_calendar(rows, expected_day=day, expected_end=day, expect_steps=96)
        if not cal.get("ok"):
            raise IntegrityFailure("runtime calendar failed: " + "; ".join(cal.get("issues") or []))
        facility = [float(r["facility_kw"]) for r in rows]
        if any(v != v for v in facility):
            raise IntegrityFailure("NaN facility_kw in scored trajectory")
        zone_series = _zone_series_dict(rows)
        final_temps = [zone_series[k][-1] for k in ACTION_KEYS]
        self.zone_temps_f = list(final_temps)
        self._prev_final_temps = list(final_temps)
        self.n_days += 1
        self._day_i += 1
        first_ts = _row_timestamp(rows[0], fallback=f"{day}+step0")
        last_ts = _row_timestamp(rows[-1], fallback=f"{day}+step95")
        return {
            "start_zone_temps_f": list(start_temps),
            "zone_temps_f": list(final_temps),
            "final_zone_temps_f": list(final_temps),
            "zone_temps_series_f": zone_series,
            "facility_kw": facility,
            "peak_kw": float(max(facility)),
            "daily_kwh": float(sum(facility) * DT_H),
            "n_intervals": 96,
            "n_process_starts": self.n_process_starts,
            "live_energyplus": True,
            "calendar_ok": True,
            "day": day,
            "first_runtime_timestamp": first_ts,
            "last_runtime_timestamp": last_ts,
            "rows": rows,
        }

    def finish_quality(self) -> dict[str, Any]:
        self.close()
        err = None
        eplus_root = self.output / "eplus"
        if eplus_root.is_dir():
            hits = list(eplus_root.rglob("eplusout.err"))
            if hits:
                err = hits[0]
        gate = parse_eplus_err(err) if err else {"completed_successfully": False}
        self.last_eplus_quality = gate
        return gate

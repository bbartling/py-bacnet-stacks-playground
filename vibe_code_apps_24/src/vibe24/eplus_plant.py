"""Plant protocol + EnergyPlus residential day adapter for the live twin."""
from __future__ import annotations

import logging
import tempfile
from dataclasses import dataclass, field
from pathlib import Path
from typing import Protocol

import numpy as np

from .thermostat import effective_heat_cool

log = logging.getLogger(__name__)

CLAIM_SURROGATE = "SURROGATE_PLANT_V1"
CLAIM_ENERGYPLUS = "ENERGYPLUS_RESIDENTIAL_V1"


class Plant(Protocol):
    def reset(self, *, oa_f: float, zone_f: float) -> None: ...

    def step(self, dt_hours: float, commands: dict[str, float]) -> dict[str, float]: ...


@dataclass
class EnergyPlusPlant:
    """Stream vibe23 residential EnergyPlus day results into the live twin.

    Mid-sim ZONE-SP / DEADBAND / UNIT-ENABLE changes re-run the day but keep the
    past schedule intact and only rewrite from the current timestep forward.

    Claim: ENERGYPLUS_RESIDENTIAL_V1 (real E+ residential IDF; not GL14 calibrated).
    """

    month: int = 7
    day: int = 15
    run_root: Path | None = None
    idf_path: Path | None = None
    epw_path: Path | None = None
    sp_epsilon_f: float = 0.25
    claim: str = CLAIM_ENERGYPLUS

    _idx: int = field(default=0, init=False, repr=False)
    _minute_accum: float = field(default=0.0, init=False, repr=False)
    _zone: np.ndarray | None = field(default=None, init=False, repr=False)
    _kw: np.ndarray | None = field(default=None, init=False, repr=False)
    _oa: np.ndarray | None = field(default=None, init=False, repr=False)
    _heat_sched: np.ndarray | None = field(default=None, init=False, repr=False)
    _cool_sched: np.ndarray | None = field(default=None, init=False, repr=False)
    _cmd_sig: tuple[float, float, float] | None = field(default=None, init=False, repr=False)
    _seed_zone_f: float = field(default=72.0, init=False, repr=False)
    _seed_oa_f: float = field(default=85.0, init=False, repr=False)
    _last: dict[str, float] = field(default_factory=dict, init=False, repr=False)

    def reset(self, *, oa_f: float, zone_f: float) -> None:
        self._seed_oa_f = float(oa_f)
        self._seed_zone_f = float(zone_f)
        self._idx = 0
        self._minute_accum = 0.0
        self._zone = None
        self._kw = None
        self._oa = None
        self._heat_sched = None
        self._cool_sched = None
        self._cmd_sig = None
        self._last = {
            "ZONE-T": self._seed_zone_f,
            "OA-T": self._seed_oa_f,
            "RTU-KW": 0.0,
            "FAN-S": 0.0,
            "MODE": 0.0,
        }

    def sim_clock(self) -> dict[str, int | str]:
        base = int(self._idx) * 5 + int(self._minute_accum)
        minute_of_day = base % (24 * 60)
        hour = minute_of_day // 60
        minute = minute_of_day % 60
        return {
            "month": int(self.month),
            "day": int(self.day),
            "hour": hour,
            "minute": minute,
            "label": f"{self.month:02d}/{self.day:02d} {hour:02d}:{minute:02d}",
        }

    def step(self, dt_hours: float, commands: dict[str, float]) -> dict[str, float]:
        heat = float(commands.get("HEAT-EFF", commands.get("HEAT-SP", 71.0)))
        cool = float(commands.get("COOL-EFF", commands.get("COOL-SP", 73.0)))
        if "HEAT-EFF" not in commands and "ZONE-SP" in commands:
            heat, cool = effective_heat_cool(
                float(commands["ZONE-SP"]),
                float(commands.get("DEADBAND", 2.0)),
            )
        enable = 1.0 if float(commands.get("UNIT-ENABLE", 1.0)) >= 0.5 else 0.0
        if heat > cool - 0.5:
            cool = heat + 1.0
        sig = (round(heat, 2), round(cool, 2), enable)
        if self._zone is None or self._needs_rerun(sig):
            self._run_day(heat=heat, cool=cool, enable=enable)
            self._cmd_sig = sig

        minutes = max(0.0, float(dt_hours) * 60.0)
        self._minute_accum += minutes
        assert self._zone is not None
        n = len(self._zone)
        while self._minute_accum >= 5.0 and self._idx < n - 1:
            self._minute_accum -= 5.0
            self._idx += 1

        self._last = self._sample(heat=heat, cool=cool, enable=enable)
        return dict(self._last)

    def _needs_rerun(self, sig: tuple[float, float, float]) -> bool:
        if self._cmd_sig is None:
            return True
        ph, pc, pe = self._cmd_sig
        h, c, e = sig
        if e != pe:
            return True
        return abs(h - ph) >= self.sp_epsilon_f or abs(c - pc) >= self.sp_epsilon_f

    def _run_day(self, *, heat: float, cool: float, enable: float) -> None:
        from vibe23.residential.constants import INTERVALS_PER_DAY
        from vibe23.residential.model import MODEL_IDF, find_denver_epw
        from vibe23.residential.runner import parse_eplus_csv, run_residential_day

        keep_idx = self._idx
        n = INTERVALS_PER_DAY
        if enable < 0.5:
            future_heat, future_cool = 40.0, 99.0
        else:
            future_heat, future_cool = float(heat), float(cool)

        if self._heat_sched is None or self._cool_sched is None:
            heat_sched = np.full(n, future_heat, dtype=float)
            cool_sched = np.full(n, future_cool, dtype=float)
        else:
            heat_sched = np.array(self._heat_sched, dtype=float, copy=True)
            cool_sched = np.array(self._cool_sched, dtype=float, copy=True)
            heat_sched[keep_idx:] = future_heat
            cool_sched[keep_idx:] = future_cool

        idf = self.idf_path or MODEL_IDF
        epw = self.epw_path or find_denver_epw()
        if epw is None:
            raise FileNotFoundError("Denver/Golden EPW not found for EnergyPlusPlant")

        root = Path(self.run_root) if self.run_root else Path(tempfile.mkdtemp(prefix="vibe24_eplus_"))
        root.mkdir(parents=True, exist_ok=True)
        out = root / "day"
        log.info(
            "EnergyPlusPlant day %02d/%02d heat=%.1f cool=%.1f enable=%s from_idx=%d -> %s",
            self.month,
            self.day,
            float(future_heat),
            float(future_cool),
            enable >= 0.5,
            keep_idx,
            out,
        )
        meta = run_residential_day(
            idf,
            epw=epw,
            output_dir=out,
            month=self.month,
            day=self.day,
            heat_f=heat_sched,
            cool_f=cool_sched,
        )
        if not bool(meta.get("soft_ok")):
            raise RuntimeError(f"EnergyPlus day failed soft quality gate: {meta}")
        if int(meta.get("fatal_count") or 0) > 0:
            raise RuntimeError(f"EnergyPlus day fatal: {meta}")

        frame = parse_eplus_csv(out)
        self._zone = frame["zone_temp_f"].to_numpy(dtype=float)
        if "hvac_kw" in frame.columns:
            self._kw = frame["hvac_kw"].to_numpy(dtype=float)
        else:
            self._kw = frame["facility_kw"].to_numpy(dtype=float)
        self._oa = self._outdoor_from_epw(Path(epw), n=len(self._zone))
        self._heat_sched = heat_sched
        self._cool_sched = cool_sched
        self._idx = min(keep_idx, len(self._zone) - 1)
        log.info(
            "EnergyPlusPlant loaded %d timesteps (claim=%s, eplus=%s)",
            len(self._zone),
            self.claim,
            meta.get("energyplus_version") or meta.get("version"),
        )

    def _outdoor_from_epw(self, epw: Path, *, n: int) -> np.ndarray:
        rows: list[tuple[int, float]] = []
        with epw.open(encoding="utf-8", errors="replace") as handle:
            for i, line in enumerate(handle):
                if i < 8:
                    continue
                parts = line.strip().split(",")
                if len(parts) < 7:
                    continue
                try:
                    month = int(float(parts[1]))
                    day = int(float(parts[2]))
                    hour = int(float(parts[3]))
                    db_c = float(parts[6])
                except ValueError:
                    continue
                if month == self.month and day == self.day:
                    rows.append((hour, db_c * 9.0 / 5.0 + 32.0))
        if not rows:
            return np.full(n, self._seed_oa_f, dtype=float)
        by_hour = {h: t for h, t in rows}
        out = np.zeros(n, dtype=float)
        for i in range(n):
            hour = (i // 12) + 1
            out[i] = by_hour.get(hour, by_hour.get(min(24, hour), self._seed_oa_f))
        return out

    def _sample(self, *, heat: float, cool: float, enable: float) -> dict[str, float]:
        assert self._zone is not None and self._kw is not None and self._oa is not None
        i = self._idx
        n = len(self._zone)
        frac = min(max(self._minute_accum / 5.0, 0.0), 1.0)
        j = min(i + 1, n - 1)

        def lerp(a: float, b: float) -> float:
            return float(a + (b - a) * frac)

        zone = lerp(float(self._zone[i]), float(self._zone[j]))
        kw = lerp(float(self._kw[i]), float(self._kw[j]))
        oa = lerp(float(self._oa[i]), float(self._oa[j]))
        fan = 1.0 if (enable >= 0.5 and kw > 0.05) else 0.0
        mode = 0.0
        if enable >= 0.5 and fan >= 0.5:
            if zone < heat - 0.5:
                mode = 1.0
            elif zone > cool + 0.5:
                mode = 2.0
            else:
                mode = 3.0
        return {
            "ZONE-T": zone,
            "OA-T": oa,
            "RTU-KW": max(0.0, kw),
            "FAN-S": fan,
            "MODE": mode,
        }

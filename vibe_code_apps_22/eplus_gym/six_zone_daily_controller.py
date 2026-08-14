"""Six-zone parametric daily heating controller (coordinate-descent friendly)."""
from __future__ import annotations

import hashlib
import json
from dataclasses import asdict, dataclass, field
from typing import Any, Dict, List

import numpy as np

from eplus_native.six_zone_htg_stage import ACTION_KEYS


def f_to_c(f: float) -> float:
    return (float(f) - 32.0) * 5.0 / 9.0


def c_to_f(c: float) -> float:
    return float(c) * 9.0 / 5.0 + 32.0


@dataclass
class ZoneOffsets:
    setback_offset_f: float = 0.0
    recovery_offset_min: int = 0
    occupied_offset_f: float = 0.0  # disabled by default (keep 0)


@dataclass
class SixZoneDailyParams:
    occupied_heating_f: float = 70.0
    unoccupied_heating_f: float = 65.0
    recovery_start_minutes_before_occupancy: int = 0
    recovery_ramp_minutes: int = 60
    occupancy_start_step: int = 28
    occupancy_end_step: int = 68
    zone_offsets: Dict[str, ZoneOffsets] = field(default_factory=dict)

    def __post_init__(self) -> None:
        for key in ACTION_KEYS:
            if key not in self.zone_offsets:
                self.zone_offsets[key] = ZoneOffsets()

    def to_dict(self) -> Dict[str, Any]:
        d = asdict(self)
        return d


def _clamp_step(m: int) -> int:
    return max(0, min(95, int(m)))


def build_zone_series_f(params: SixZoneDailyParams, action_key: str) -> List[float]:
    off = params.zone_offsets.get(action_key) or ZoneOffsets()
    occ = float(params.occupied_heating_f) + float(off.occupied_offset_f)
    unocc = float(params.unoccupied_heating_f) + float(off.setback_offset_f)
    start = int(params.occupancy_start_step) % 96
    end = int(params.occupancy_end_step) % 96
    if end <= start:
        end = min(96, start + 1)
    lead = max(0, int(round(params.recovery_start_minutes_before_occupancy / 15.0)))
    lead += int(round(off.recovery_offset_min / 15.0))
    lead = max(0, lead)
    ramp = max(0, int(round(params.recovery_ramp_minutes / 15.0)))
    recovery_begin = _clamp_step(start - lead)
    series: List[float] = []
    for t in range(96):
        if start <= t < end:
            series.append(occ)
            continue
        if recovery_begin <= t < start:
            if ramp <= 0:
                series.append(occ)
            else:
                progressed = t - (start - ramp)
                if progressed <= 0:
                    series.append(unocc)
                else:
                    frac = min(1.0, progressed / float(ramp))
                    series.append(unocc + frac * (occ - unocc))
            continue
        series.append(unocc)
    return series


class SixZoneDailyController:
    """Emits length-6 °C actions in stable ACTION_KEYS order."""

    ACTION_KEYS = ACTION_KEYS

    def __init__(self, params: SixZoneDailyParams | Dict[str, Any] | None = None):
        if params is None:
            params = SixZoneDailyParams()
        elif isinstance(params, dict):
            zo = params.get("zone_offsets") or {}
            parsed = {
                k: ZoneOffsets(**v) if isinstance(v, dict) else v for k, v in zo.items()
            }
            kwargs = {k: v for k, v in params.items() if k != "zone_offsets"}
            params = SixZoneDailyParams(**kwargs, zone_offsets=parsed)
        self.params = params
        self._series_f: Dict[str, List[float]] = {
            k: build_zone_series_f(params, k) for k in ACTION_KEYS
        }
        self._series_c: Dict[str, List[float]] = {
            k: [f_to_c(v) for v in self._series_f[k]] for k in ACTION_KEYS
        }
        # Baseline lookback uses global unocc/occ without zone moves unless provided
        self._lookback = self

    def action(self, step: int) -> np.ndarray:
        t = int(step) % 96
        return np.asarray([self._series_c[k][t] for k in ACTION_KEYS], dtype=np.float32)

    def action_lookback(self, step: int) -> np.ndarray:
        """Baseline lookback controls (same as action unless overridden)."""
        return self.action(step)

    def series_f(self) -> Dict[str, List[float]]:
        return {k: list(self._series_f[k]) for k in ACTION_KEYS}

    def series_c(self) -> Dict[str, List[float]]:
        return {k: list(self._series_c[k]) for k in ACTION_KEYS}

    def schedule_sha256(self) -> str:
        blob = json.dumps(self.series_f(), sort_keys=True)
        return hashlib.sha256(blob.encode("utf-8")).hexdigest()

    def movement_total_f(self) -> float:
        total = 0.0
        for k in ACTION_KEYS:
            s = self._series_f[k]
            total += sum(abs(s[i] - s[i - 1]) for i in range(1, len(s)))
        return float(total)

    def bounds_ok(self, lo_f: float = 50.0, hi_f: float = 80.0) -> bool:
        for k in ACTION_KEYS:
            for v in self._series_f[k]:
                if v < lo_f or v > hi_f:
                    return False
        return True

    def provenance(self) -> Dict[str, Any]:
        return {
            "controller": "SixZoneDailyController",
            "action_keys": list(ACTION_KEYS),
            "params": self.params.to_dict(),
            "schedule_sha256": self.schedule_sha256(),
            "movement_total_f": self.movement_total_f(),
            "bounds_ok": self.bounds_ok(),
        }

    def with_zone_move(self, action_key: str, **offset_kwargs: Any) -> "SixZoneDailyController":
        if action_key not in ACTION_KEYS:
            raise ValueError(action_key)
        p = SixZoneDailyParams(**{k: getattr(self.params, k) for k in (
            "occupied_heating_f",
            "unoccupied_heating_f",
            "recovery_start_minutes_before_occupancy",
            "recovery_ramp_minutes",
            "occupancy_start_step",
            "occupancy_end_step",
        )})
        p.zone_offsets = {
            k: ZoneOffsets(**asdict(v)) for k, v in self.params.zone_offsets.items()
        }
        cur = p.zone_offsets[action_key]
        for field, val in offset_kwargs.items():
            setattr(cur, field, getattr(cur, field) + val)
        return SixZoneDailyController(p)


def controller_hash(ctrl: SixZoneDailyController) -> str:
    return hashlib.sha256(
        json.dumps(ctrl.params.to_dict(), sort_keys=True).encode("utf-8")
    ).hexdigest()[:16]

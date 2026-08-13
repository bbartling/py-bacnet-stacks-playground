"""Parametric 96-step SCH_HtgSP daily controller (heating recovery ≠ HVAC lead)."""
from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import Any, Dict, List, Optional, Sequence

from .controllers import RuleController, f_to_c


@dataclass(frozen=True)
class ParametricDailyParams:
    """Global low-dimensional schedule parameters for one calendar day."""

    occupied_heating_f: float = 70.0
    unoccupied_heating_f: float = 65.0
    recovery_start_minutes_before_occupancy: int = 0
    recovery_ramp_minutes: int = 0
    hvac_start_minutes_before_occupancy: int = 0
    occupied_setpoint_offset_f: float = 0.0
    # First occupied 15-min index from Site Config / strategy (default 7:00 → step 28)
    occupancy_start_step: int = 28
    occupancy_end_step: int = 68  # 17:00 exclusive-ish; inclusive occupied while < end

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


def _clamp_step(m: int) -> int:
    return max(0, min(95, int(m)))


def build_htg_sp_series_f(params: ParametricDailyParams) -> List[float]:
    """Emit 96 heating setpoints °F with optional recovery ramp into occupied SP."""
    occ = float(params.occupied_heating_f) + float(params.occupied_setpoint_offset_f)
    unocc = float(params.unoccupied_heating_f)
    start = int(params.occupancy_start_step) % 96
    end = int(params.occupancy_end_step) % 96
    if end <= start:
        end = min(96, start + 1)

    lead_steps = max(0, int(round(params.recovery_start_minutes_before_occupancy / 15.0)))
    ramp_steps = max(0, int(round(params.recovery_ramp_minutes / 15.0)))
    recovery_begin = _clamp_step(start - lead_steps)

    series: List[float] = []
    for t in range(96):
        occupied = start <= t < end
        if occupied:
            series.append(occ)
            continue
        if recovery_begin <= t < start:
            # Linear ramp unocc → occ over ramp_steps ending at occupancy start.
            if ramp_steps <= 0:
                series.append(occ)
            else:
                # Distance from recovery_begin toward start
                progressed = t - (start - ramp_steps)
                if progressed <= 0:
                    series.append(unocc)
                else:
                    frac = min(1.0, progressed / float(ramp_steps))
                    series.append(unocc + frac * (occ - unocc))
            continue
        series.append(unocc)
    return series


class ParametricDailyController:
    """Authoritative SCH_HtgSP schedule; HVAC lead is metadata only (staging)."""

    def __init__(self, params: ParametricDailyParams | Dict[str, Any]):
        if isinstance(params, dict):
            params = ParametricDailyParams(**{
                k: params[k]
                for k in ParametricDailyParams.__dataclass_fields__
                if k in params
            })
        self.params = params
        self._htg_f = build_htg_sp_series_f(params)
        self.strategy_id = "parametric_daily"
        self.occ_htg_sp_f = float(params.occupied_heating_f)
        self.unocc_htg_sp_f = float(params.unoccupied_heating_f)

    def setpoint_f(self, step: int) -> float:
        return float(self._htg_f[int(step) % 96])

    def action_c(self, step: int) -> float:
        return f_to_c(self.setpoint_f(step))

    def series_f(self) -> List[float]:
        return list(self._htg_f)

    def provenance(self) -> Dict[str, Any]:
        return {
            "controller": "ParametricDailyController",
            "params": self.params.to_dict(),
            "note": (
                "recovery_* shapes SCH_HtgSP; hvac_start_minutes_before_occupancy "
                "is fan/OA/HVAC availability only — not heating optimum start alone."
            ),
            "htg_sp_f_96": self.series_f(),
        }


def occupancy_steps_from_site_config(cfg: Dict[str, Any] | None) -> tuple[int, int]:
    """Map people start/end clock times to 15-min steps (best-effort)."""
    if not cfg:
        return 28, 68
    people = cfg.get("people") or cfg.get("schedules") or {}
    start = people.get("people_start") or people.get("start") or "07:00"
    end = people.get("people_end") or people.get("end") or "17:00"

    def _to_step(hhmm: str) -> int:
        parts = str(hhmm).strip().split(":")
        h = int(parts[0])
        m = int(parts[1]) if len(parts) > 1 else 0
        return _clamp_step(h * 4 + m // 15)

    return _to_step(start), _to_step(end)


def controller_from_site_and_params(
    site_cfg: Dict[str, Any] | None,
    *,
    recovery_start_minutes_before_occupancy: int = 0,
    recovery_ramp_minutes: int = 0,
    hvac_start_minutes_before_occupancy: int = 0,
    occupied_setpoint_offset_f: float = 0.0,
    unoccupied_heating_f: float | None = None,
) -> ParametricDailyController:
    sp = (site_cfg or {}).get("setpoints_f") or {}
    occ = float(sp.get("occupied_heating_f", 70.0))
    unocc = float(
        unoccupied_heating_f
        if unoccupied_heating_f is not None
        else sp.get("unoccupied_heating_f", 65.0)
    )
    start, end = occupancy_steps_from_site_config(site_cfg)
    return ParametricDailyController(
        ParametricDailyParams(
            occupied_heating_f=occ,
            unoccupied_heating_f=unocc,
            recovery_start_minutes_before_occupancy=int(
                recovery_start_minutes_before_occupancy
            ),
            recovery_ramp_minutes=int(recovery_ramp_minutes),
            hvac_start_minutes_before_occupancy=int(
                hvac_start_minutes_before_occupancy
            ),
            occupied_setpoint_offset_f=float(occupied_setpoint_offset_f),
            occupancy_start_step=start,
            occupancy_end_step=end,
        )
    )


def as_rule_compatible(ctrl: ParametricDailyController) -> RuleController:
    """Shim: RuleController interface already matched (setpoint_f/action_c/series_f)."""
    return ctrl  # type: ignore[return-value]

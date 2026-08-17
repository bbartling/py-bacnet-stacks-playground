"""Control contract v2: school calendar vs DualSP schedules. Does not mutate v1."""
from __future__ import annotations

import json
from dataclasses import dataclass, field
from datetime import date, timedelta
from pathlib import Path
from typing import Any, Sequence

from eplus_native.six_zone_htg_stage import ACTION_KEYS

__all__ = ["ACTION_KEYS"]

STEPS_PER_DAY = 96
END_OF_DAY_STEP = 96
CONTINUOUS_CONDITIONING_THERMOSTATIC = "CONTINUOUS_CONDITIONING_THERMOSTATIC"
_APP = Path(__file__).resolve().parents[1]


def load_json_contract(name: str) -> dict[str, Any]:
    path = _APP / "contracts" / name
    return json.loads(path.read_text(encoding="utf-8"))


def local_hhmm_to_step(hhmm: str) -> int:
    h_s, m_s = str(hhmm).split(":")
    h, m = int(h_s), int(m_s)
    if m % 15:
        m = int(round(m / 15.0) * 15)
        if m == 60:
            h += 1
            m = 0
    return int(h) * 4 + int(m) // 15


@dataclass
class ZoneOffsetsV2:
    setback_offset_f: float = 0.0


@dataclass
class SixZoneDailyParamsV2:
    occupied_heating_f: float = 70.0
    unoccupied_heating_f: float = 65.0
    heating_setpoint_start_step: int = 28
    heating_setpoint_end_step: int = 68
    recovery_lead_minutes: int = 60
    recovery_ramp_minutes: int = 60
    continuous_conditioning: bool = False
    zone_offsets: dict[str, ZoneOffsetsV2] = field(default_factory=dict)

    def __post_init__(self) -> None:
        for key in ACTION_KEYS:
            if key not in self.zone_offsets:
                self.zone_offsets[key] = ZoneOffsetsV2()
        if abs(float(self.occupied_heating_f) - float(self.unoccupied_heating_f)) < 1e-6:
            self.continuous_conditioning = True
            self.heating_setpoint_start_step = 0
            self.heating_setpoint_end_step = END_OF_DAY_STEP
            self.recovery_lead_minutes = 0
            self.recovery_ramp_minutes = 0
        else:
            # recovery_lead_minutes IS the linear ramp duration (no extra fixed 60-min ramp).
            self.recovery_ramp_minutes = int(self.recovery_lead_minutes)

    def mode_label(self) -> str:
        if self.continuous_conditioning:
            return CONTINUOUS_CONDITIONING_THERMOSTATIC
        return "SETBACK_THERMOSTATIC"


def school_windows(day: date | str, calendar: dict[str, Any] | None = None) -> dict[str, Any]:
    cal = calendar or load_json_contract("school_calendar_v2.json")
    d = day if isinstance(day, date) else date.fromisoformat(str(day)[:10])
    regular = cal["regular_day"]
    holidays = set(cal.get("holidays_and_breaks_local", {}).get("assumed_holidays") or [])
    winter = cal.get("holidays_and_breaks_local", {}).get("winter_break_inclusive") or []
    in_winter = False
    if len(winter) == 2:
        in_winter = date.fromisoformat(winter[0]) <= d <= date.fromisoformat(winter[1])
    weekend = d.weekday() >= 5
    holiday = d.isoformat() in holidays or in_winter
    school = (not weekend) and (not holiday)
    thu = d.weekday() == 3
    start = int(regular["doors_open_step"])
    end = int(regular["dismissal_thu_step"] if thu else regular["dismissal_mon_tue_wed_fri_step_approx"])
    readiness = list(cal["readiness_check_steps"]["weekday"]) if school else []
    return {
        "day": d.isoformat(),
        "school_occupied": school,
        "weekend": weekend,
        "holiday": holiday,
        "thursday_early_dismissal": bool(school and thu),
        "school_occupied_start_step": start if school else None,
        "school_occupied_end_step": end if school else None,
        "readiness_check_steps": readiness,
        "day_type": "weekend" if weekend else ("holiday" if holiday else ("thursday" if thu else "weekday")),
    }


def validate_params(params: SixZoneDailyParamsV2, *, envelope: dict[str, Any] | None = None) -> None:
    env = envelope or load_json_contract("control_contract_v2.json")["agent_envelope"]
    occ_b = env["occupied_heating_setpoint_f"]
    unocc_b = env["unoccupied_heating_setpoint_f"]
    start_b = env["heating_setpoint_start_step"]
    end_b = env["heating_setpoint_end_step"]
    rec_b = env["recovery_lead_minutes"]
    off_b = env["six_zone_setback_offsets_f"]
    occ = float(params.occupied_heating_f)
    unocc = float(params.unoccupied_heating_f)
    if not (occ_b["min"] <= occ <= occ_b["max"]):
        raise ValueError(f"occupied_heating_f {occ} outside envelope")
    if not (unocc_b["min"] <= unocc <= unocc_b["max"]):
        raise ValueError(f"unoccupied_heating_f {unocc} outside envelope")
    if params.continuous_conditioning:
        if abs(occ - unocc) > 1e-6:
            raise ValueError("continuous conditioning requires equal occupied/unoccupied setpoints")
        return
    start = int(params.heating_setpoint_start_step)
    end = int(params.heating_setpoint_end_step)
    if not (start_b["min"] <= start <= start_b["max"]):
        raise ValueError(f"heating_setpoint_start_step {start} outside envelope")
    if not (end_b["min"] <= end <= end_b["max"]):
        raise ValueError(f"heating_setpoint_end_step {end} outside envelope")
    if end <= start:
        raise ValueError("invalid start/end: end must be > start; end=96 is end of day")
    rec = int(params.recovery_lead_minutes)
    if not (rec_b["min"] <= rec <= rec_b["max"]):
        raise ValueError(f"recovery_lead_minutes {rec} outside envelope")
    for key in ACTION_KEYS:
        off = float(params.zone_offsets[key].setback_offset_f)
        if not (off_b["min"] <= off <= off_b["max"]):
            raise ValueError(f"offset {key}={off} outside envelope")
        unocc_eff = unocc + off
        if unocc_eff > occ + 1e-9:
            raise ValueError(
                f"effective unoccupied SP for {key}={unocc_eff} exceeds occupied {occ}; "
                "preheat is not a named mode in this contract — reject"
            )


def first_change_step(series: Sequence[float]) -> int:
    if not series:
        return 0
    base = float(series[0])
    for i, v in enumerate(series):
        if abs(float(v) - base) > 1e-9:
            return i
    return 0


def build_zone_series_f_v2(params: SixZoneDailyParamsV2, action_key: str) -> list[float]:
    off = params.zone_offsets.get(action_key) or ZoneOffsetsV2()
    occ = float(params.occupied_heating_f) + 0.0
    unocc = float(params.unoccupied_heating_f) + float(off.setback_offset_f)
    if unocc > occ + 1e-9:
        raise ValueError(
            f"effective unoccupied SP {unocc} exceeds occupied {occ}; preheat rejected"
        )
    env = load_json_contract("control_contract_v2.json")["agent_envelope"]
    unocc_b = env["unoccupied_heating_setpoint_f"]
    unocc = min(occ, max(float(unocc_b["min"]), unocc))
    if params.continuous_conditioning:
        return [float(params.occupied_heating_f)] * STEPS_PER_DAY
    start = int(params.heating_setpoint_start_step)
    end = int(params.heating_setpoint_end_step)
    if end == 0:
        raise ValueError("end_step 0 is a wrap; use 96 for end of day")
    if not (0 <= start <= 95 and 1 <= end <= END_OF_DAY_STEP):
        raise ValueError("start/end out of range")
    if end <= start:
        raise ValueError("invalid start/end combination")
    # recovery_lead_minutes is the linear ramp duration ending at start_step.
    lead = max(0, int(round(params.recovery_lead_minutes / 15.0)))
    recovery_begin = max(0, start - lead)
    series: list[float] = []
    for t in range(STEPS_PER_DAY):
        if start <= t < end:
            series.append(occ)
            continue
        if lead > 0 and recovery_begin <= t < start:
            frac = (t - recovery_begin + 1) / float(lead)
            series.append(unocc + min(1.0, frac) * (occ - unocc))
            continue
        series.append(unocc)
    return series


def build_six_schedules_f(params: SixZoneDailyParamsV2) -> dict[str, list[float]]:
    return {k: build_zone_series_f_v2(params, k) for k in ACTION_KEYS}


def observed_bas_incumbent_params() -> SixZoneDailyParamsV2:
    return SixZoneDailyParamsV2(
        occupied_heating_f=68.0,
        unoccupied_heating_f=64.0,
        heating_setpoint_start_step=28,
        heating_setpoint_end_step=68,
        recovery_lead_minutes=60,
        recovery_ramp_minutes=60,
        continuous_conditioning=False,
    )


def continuous_params(setpoint_f: float) -> SixZoneDailyParamsV2:
    sp = float(setpoint_f)
    return SixZoneDailyParamsV2(
        occupied_heating_f=sp,
        unoccupied_heating_f=sp,
        heating_setpoint_start_step=0,
        heating_setpoint_end_step=END_OF_DAY_STEP,
        recovery_lead_minutes=0,
        recovery_ramp_minutes=0,
        continuous_conditioning=True,
    )


def deep_setback_params() -> SixZoneDailyParamsV2:
    return SixZoneDailyParamsV2(
        occupied_heating_f=70.0,
        unoccupied_heating_f=58.0,
        heating_setpoint_start_step=28,
        heating_setpoint_end_step=68,
        recovery_lead_minutes=180,
        recovery_ramp_minutes=180,
    )


def shallow_setback_params() -> SixZoneDailyParamsV2:
    return SixZoneDailyParamsV2(
        occupied_heating_f=70.0,
        unoccupied_heating_f=66.0,
        heating_setpoint_start_step=28,
        heating_setpoint_end_step=68,
        recovery_lead_minutes=30,
        recovery_ramp_minutes=30,
    )


def weather_rule_optimal_start_params(*, oat_min_c: float) -> SixZoneDailyParamsV2:
    """Lead longer when colder. Not a learned policy."""
    if oat_min_c <= -15.0:
        lead = 180
    elif oat_min_c <= -5.0:
        lead = 120
    elif oat_min_c <= 0.0:
        lead = 60
    else:
        lead = 30
    return SixZoneDailyParamsV2(
        occupied_heating_f=68.0,
        unoccupied_heating_f=64.0,
        heating_setpoint_start_step=28,
        heating_setpoint_end_step=68,
        recovery_lead_minutes=lead,
        recovery_ramp_minutes=lead,
    )


def chronological_days(start: str, n: int) -> list[str]:
    d0 = date.fromisoformat(str(start)[:10])
    return [(d0 + timedelta(days=i)).isoformat() for i in range(int(n))]

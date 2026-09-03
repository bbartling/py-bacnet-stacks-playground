#!/usr/bin/env python
"""Export studio extreme-day fixtures (Jul 15 + Jan 15) from EnergyPlus + EPW."""
from __future__ import annotations

import json
from pathlib import Path

from vibe23.residential.constants import DT_HOURS, INTERVALS_PER_DAY, MAX_HEAT_F, DEFAULT_HEAT_F
from vibe23.residential.model import MODEL_IDF, PACKAGE_ROOT, find_denver_epw
from vibe23.residential.runner import run_residential_day
from vibe23.residential.thermostat import action_to_setpoints_f, build_schedule_action
from vibe23.studio.uploads import parse_epw_path

FIXTURES = PACKAGE_ROOT / "fixtures" / "studio"


def _round_series(values: list[float], nd: int) -> list[float]:
    return [round(float(v), nd) for v in values]


def _write_day(path: Path, *, season: str, label: str, month: int, day: int, baseline, event) -> None:
    dt = DT_HOURS
    payload = {
        "schema": "vibe23.studio_day.v1",
        "season": season,
        "label": label,
        "month": month,
        "day": day,
        "intervals": INTERVALS_PER_DAY,
        "dt_hours": dt,
        "baseline_kw": _round_series(baseline["facility_kw"], 4),
        "event_kw": _round_series(event["facility_kw"], 4),
        "baseline_temp_f": _round_series(baseline["zone_temp_f"], 3),
        "event_temp_f": _round_series(event["zone_temp_f"], 3),
        "baseline_daily_kwh": round(sum(x * dt for x in baseline["facility_kw"]), 3),
        "event_daily_kwh": round(sum(x * dt for x in event["facility_kw"]), 3),
        "floor_ft2": 3499,
        "energy_note": f"kWh=sum(kW*dt_hours) over 288 intervals; ~3500 ft2 / 5-ton {month:02d}/{day:02d} extreme day",
    }
    path.write_text(json.dumps(payload) + "\n", encoding="utf-8")


def _write_outdoor(path: Path, month: int, day: int) -> None:
    epw = find_denver_epw()
    if epw is None:
        raise SystemExit("Golden/NREL EPW not found; set ENERGYPLUS_WEATHER in .env")
    outdoor = parse_epw_path(epw, month=month, day=day)
    path.write_text(outdoor.model_dump_json() + "\n", encoding="utf-8")


def main() -> None:
    FIXTURES.mkdir(parents=True, exist_ok=True)
    _write_outdoor(FIXTURES / "summer_outdoor_jul15.json", 7, 15)
    _write_outdoor(FIXTURES / "winter_outdoor_jan15.json", 1, 15)

    winter_root = PACKAGE_ROOT / "campaigns" / "runs" / "studio_winter_fixture"
    base = run_residential_day(MODEL_IDF, output_dir=winter_root / "baseline", month=1, day=15)
    action = build_schedule_action(
        pre_start_hour=5.0,
        event_start=6.0,
        event_end=9.0,
        recover_end=12.0,
        pre_heat_f=73.5,
        event_heat_f=MAX_HEAT_F,
        recover_heat_f=DEFAULT_HEAT_F,
        mode="winter_dr",
    )
    heat, cool = action_to_setpoints_f(action)
    event = run_residential_day(
        MODEL_IDF,
        output_dir=winter_root / "event",
        month=1,
        day=15,
        heat_f=heat,
        cool_f=cool,
    )
    _write_day(
        FIXTURES / "winter_dr_day.json",
        season="winter",
        label="Jan 15 winter extreme (from EnergyPlus 5-min)",
        month=1,
        day=15,
        baseline=base,
        event=event,
    )
    print("exported winter fixtures")


if __name__ == "__main__":
    main()

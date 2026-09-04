#!/usr/bin/env python
"""Export studio day fixtures from EnergyPlus + Golden/NREL EPW.

Writes summer Jul 15 DR, winter design (Jan 3 near-cold), and winter typical (Jan 15 mild).
"""
from __future__ import annotations

import json
from pathlib import Path

from vibe23.residential.constants import (
    DEFAULT_HEAT_F,
    DT_HOURS,
    INTERVALS_PER_DAY,
    MAX_HEAT_F,
    SUMMER_DEMO_DAY,
    SUMMER_DEMO_MONTH,
    WINTER_DESIGN_DAY,
    WINTER_DESIGN_MONTH,
    WINTER_TYPICAL_DAY,
    WINTER_TYPICAL_MONTH,
)
from vibe23.residential.dr import july_dr_action
from vibe23.residential.model import MODEL_IDF, PACKAGE_ROOT, find_denver_epw
from vibe23.residential.runner import run_residential_day
from vibe23.residential.thermostat import action_to_setpoints_f, build_schedule_action
from vibe23.studio.uploads import parse_epw_path

FIXTURES = PACKAGE_ROOT / "fixtures" / "studio"


def _round_series(values: list[float], nd: int) -> list[float]:
    return [round(float(v), nd) for v in values]


def _write_day(
    path: Path,
    *,
    season: str,
    label: str,
    month: int,
    day: int,
    baseline,
    event,
    day_class: str,
) -> None:
    dt = DT_HOURS
    payload = {
        "schema": "vibe23.studio_day.v1",
        "season": season,
        "day_class": day_class,
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
        "claim_model": "HYPOTHETICAL_GL14_TUNED_DEMO_MODEL",
        "energy_note": (
            f"kWh=sum(kW*dt_hours) over 288 intervals; ~3500 ft2 / 5-ton "
            f"{month:02d}/{day:02d} {day_class} day; diurnal RESIDENTIAL_LIGHTS/PLUGS"
        ),
    }
    path.write_text(json.dumps(payload) + "\n", encoding="utf-8")


def _write_outdoor(path: Path, month: int, day: int) -> None:
    epw = find_denver_epw()
    if epw is None:
        raise SystemExit("Golden/NREL EPW not found; set ENERGYPLUS_WEATHER in .env")
    outdoor = parse_epw_path(epw, month=month, day=day)
    path.write_text(outdoor.model_dump_json() + "\n", encoding="utf-8")


def _export_pair(
    *,
    season: str,
    day_class: str,
    label: str,
    month: int,
    day: int,
    day_path: Path,
    outdoor_path: Path,
    action: dict,
    run_root: Path,
) -> None:
    _write_outdoor(outdoor_path, month, day)
    base = run_residential_day(MODEL_IDF, output_dir=run_root / "baseline", month=month, day=day)
    heat, cool = action_to_setpoints_f(action)
    event = run_residential_day(
        MODEL_IDF,
        output_dir=run_root / "event",
        month=month,
        day=day,
        heat_f=heat,
        cool_f=cool,
    )
    _write_day(
        day_path,
        season=season,
        label=label,
        month=month,
        day=day,
        baseline=base,
        event=event,
        day_class=day_class,
    )
    print(f"exported {day_path.name} ({base['total_kwh']:.1f} -> {event['total_kwh']:.1f} kWh)")


def main() -> None:
    FIXTURES.mkdir(parents=True, exist_ok=True)
    campaigns = PACKAGE_ROOT / "campaigns" / "runs"

    _export_pair(
        season="summer",
        day_class="hot_extreme",
        label="Jul 15 summer hot day (from EnergyPlus 5-min)",
        month=SUMMER_DEMO_MONTH,
        day=SUMMER_DEMO_DAY,
        day_path=FIXTURES / "summer_dr_day.json",
        outdoor_path=FIXTURES / "summer_outdoor_jul15.json",
        action=july_dr_action(),
        run_root=campaigns / "studio_summer_fixture",
    )

    winter_action = build_schedule_action(
        pre_start_hour=5.0,
        event_start=6.0,
        event_end=9.0,
        recover_end=12.0,
        pre_heat_f=73.5,
        event_heat_f=MAX_HEAT_F,
        recover_heat_f=DEFAULT_HEAT_F,
        mode="winter_dr",
    )
    _export_pair(
        season="winter",
        day_class="design_cold",
        label="Jan 3 winter design cold (from EnergyPlus 5-min)",
        month=WINTER_DESIGN_MONTH,
        day=WINTER_DESIGN_DAY,
        day_path=FIXTURES / "winter_dr_day.json",
        outdoor_path=FIXTURES / "winter_outdoor_design_jan03.json",
        action=winter_action,
        run_root=campaigns / "studio_winter_design_fixture",
    )
    _export_pair(
        season="winter",
        day_class="typical_mild",
        label="Jan 15 winter typical mild (from EnergyPlus 5-min)",
        month=WINTER_TYPICAL_MONTH,
        day=WINTER_TYPICAL_DAY,
        day_path=FIXTURES / "winter_typical_jan15_dr_day.json",
        outdoor_path=FIXTURES / "winter_outdoor_jan15.json",
        action=winter_action,
        run_root=campaigns / "studio_winter_typical_fixture",
    )
    print("exported all studio fixtures")


if __name__ == "__main__":
    main()

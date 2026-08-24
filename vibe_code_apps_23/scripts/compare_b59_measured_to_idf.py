#!/usr/bin/env python3
"""Compare measured Building 59 operating evidence with the screening IDF.

This is a discrepancy report, not a calibration score. It preserves partial
occupancy scope, source-clock uncertainty, command-versus-response semantics,
and water-loop runtime proxies rather than inventing unavailable equipment
status points.
"""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def _load_json(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise ValueError(f"{path} must contain a JSON object")
    return value


def _finite_stats(values: pd.Series) -> dict[str, Any]:
    array = pd.to_numeric(values, errors="coerce").to_numpy(float)
    array = array[np.isfinite(array)]
    if not array.size:
        return {"count": 0}
    return {
        "count": int(array.size),
        "min": round(float(array.min()), 4),
        "p05": round(float(np.quantile(array, 0.05)), 4),
        "median": round(float(np.quantile(array, 0.50)), 4),
        "p95": round(float(np.quantile(array, 0.95)), 4),
        "max": round(float(array.max()), 4),
        "mean": round(float(array.mean()), 4),
    }


def _plant_loop_evidence(path: Path, *, supply: str, return_: str, flow: str) -> dict[str, Any]:
    frame = pd.read_csv(path, usecols=["date", supply, return_, flow])
    timestamps = pd.to_datetime(frame["date"], errors="coerce")
    if timestamps.isna().any():
        raise ValueError(f"{path.name} contains invalid timestamps")
    flow_values = pd.to_numeric(frame[flow], errors="coerce")
    active = flow_values > 1.0
    valid_flow = flow_values.notna()
    supply_values = pd.to_numeric(frame[supply], errors="coerce")
    return_values = pd.to_numeric(frame[return_], errors="coerce")
    return {
        "file": path.name,
        "sha256": _sha256(path),
        "coverage_source_clock": [timestamps.min().isoformat(), timestamps.max().isoformat()],
        "flow_gpm": _finite_stats(flow_values),
        "active_flow_threshold_gpm": 1.0,
        "active_flow_fraction_of_valid_rows": round(float(active.sum() / valid_flow.sum()), 6),
        "supply_temperature_degF_when_flow_active": _finite_stats(supply_values.loc[active]),
        "return_temperature_degF_when_flow_active": _finite_stats(return_values.loc[active]),
        "return_minus_supply_delta_degF_when_flow_active": _finite_stats(
            (return_values - supply_values).loc[active]
        ),
        "runtime_claim_boundary": "Flow >1 gpm is a water-loop activity proxy, not proof that a named chiller or heat pump compressor was enabled.",
    }


def _range(points: dict[str, Any], key: str) -> list[float] | None:
    values = [float(item[key]) for item in points.values() if item.get(key) is not None]
    return [round(min(values), 4), round(max(values), 4)] if values else None


def _pct(value: float) -> str:
    return f"{100 * value:.1f}%"


def _f_range(values: list[float] | None, unit: str = "") -> str:
    if values is None:
        return "NA"
    suffix = f" {unit}" if unit else ""
    return f"{values[0]:.2f}–{values[1]:.2f}{suffix}"


def build_comparison(
    *,
    raw_root: Path,
    occupancy_evidence_path: Path,
    hvac_evidence_path: Path,
    champion_parameters_path: Path,
    champion_idf_path: Path,
    energyplus_validation_path: Path,
) -> dict[str, Any]:
    occupancy = _load_json(occupancy_evidence_path)
    hvac = _load_json(hvac_evidence_path)
    params = _load_json(champion_parameters_path)
    validation = _load_json(energyplus_validation_path)
    idf_text = champion_idf_path.read_text(encoding="utf-8")
    if idf_text.count("HVACTemplate:System:PackagedVAV,") != 4:
        raise ValueError("champion IDF must contain exactly four packaged-VAV templates")
    if idf_text.count("HVACTemplate:Zone:VAV,") != 24 or idf_text.count("\n  Electric,\n") < 24:
        raise ValueError("champion IDF terminal proxy topology changed unexpectedly")

    analysis = hvac["analysis"]
    fan_points = analysis["rtu_fan_speed_feedback"]["points"]
    supply_fans = {name: value for name, value in fan_points.items() if "_sf_" in name}
    return_fans = {name: value for name, value in fan_points.items() if "_rf_" in name}
    sat_sp = analysis["rtu_supply_air_temperature_setpoint"]["points"]
    static_sp = analysis["rtu_supply_static_pressure_setpoint"]["points"]
    cooling_sp = analysis["zone_cooling_temperature_setpoint"]["points"]
    heating_sp = analysis["zone_heating_temperature_setpoint"]["points"]
    uft_fans = analysis["uft_fan_speed"]["points"]
    uft_valves = analysis["uft_heating_water_valve_position"]["points"]
    relationships = hvac["paired_relationships"]

    camera = occupancy["profiles"]["camera_south_office_sum"]
    camera_weekday = [value for value in camera["hourly_median_by_source_day_type"]["weekday_non_holiday"] if value is not None]
    camera_peak = max(camera_weekday)
    modeled_people = 4650.0 / float(params["people_area_per_person_m2"])
    modeled_deadband_f = (float(params["occupied_cooling_setpoint_c"]) - float(params["occupied_heating_setpoint_c"])) * 1.8
    modeled_sat_f = 14.4 * 1.8 + 32
    sat_medians = _range(sat_sp, "median_sampled")
    oa_ratio = float(relationships["outdoor_air_fraction"]["aggregate_ratio"]["median_sampled"])
    modeled_minimum_oa_ratio = float(params["minimum_outdoor_air_m3_s"] / params["coil_airflow_m3_s"])

    chilled = _plant_loop_evidence(
        raw_root / "ashp_cw.csv",
        supply="aru_001_cws_temp",
        return_="aru_001_cwr_temp",
        flow="aru_001_cws_fr_gpm",
    )
    hot = _plant_loop_evidence(
        raw_root / "ashp_hw.csv",
        supply="aru_001_hws_temp",
        return_="aru_001_hwr_temp",
        flow="aru_001_hws_fr_gpm",
    )
    historical_hws = pd.read_csv(raw_root / "hp_hws_temp.csv", usecols=["date", "hp_hws_temp"])
    historical_hws_time = pd.to_datetime(historical_hws["date"], errors="coerce")
    historical_hws_evidence = {
        "file": "hp_hws_temp.csv",
        "sha256": _sha256(raw_root / "hp_hws_temp.csv"),
        "coverage_source_clock": [historical_hws_time.min().isoformat(), historical_hws_time.max().isoformat()],
        "hot_water_supply_temperature_degF": _finite_stats(historical_hws["hp_hws_temp"]),
        "claim_boundary": "Temperature alone does not prove water flow, heat delivery, or heat-pump compressor runtime.",
    }
    meter = pd.read_csv(raw_root / "ashp_meter.csv", usecols=["date", "aru_001_power_mbtuph"])
    meter_time = pd.to_datetime(meter["date"], errors="coerce")
    meter_values = pd.to_numeric(meter["aru_001_power_mbtuph"], errors="coerce")
    meter_active = meter_values.abs() > 0.1
    plant_meter = {
        "file": "ashp_meter.csv",
        "sha256": _sha256(raw_root / "ashp_meter.csv"),
        "coverage_source_clock": [meter_time.min().isoformat(), meter_time.max().isoformat()],
        "publisher_named_thermal_rate_mbtuph": _finite_stats(meter_values),
        "nontrivial_fraction_abs_above_0_1": round(float(meter_active.sum() / meter_values.notna().sum()), 6),
        "claim_boundary": "The point name reports MBtu/h; it is not treated as electrical kW or compressor status.",
    }

    rows = [
        {
            "domain": "EnergyPlus execution",
            "measured_or_runtime_evidence": "Post-release champion validation",
            "screening_idf_configuration": (
                f"EnergyPlus admitted={validation.get('admitted_under_strengthened_gate')}; warnings={validation.get('warning_count')}; "
                f"severe={validation.get('severe_count')}; fatal={validation.get('fatal_count')}"
            ),
            "difference_and_disposition": "Engine/syntax gate passes; this does not establish physical calibration.",
            "severity": "PASS_ENGINE_ONLY",
        },
        {
            "domain": "Occupancy count/schedule",
            "measured_or_runtime_evidence": (
                f"South-office camera only: weekday source-clock peak {camera_peak:.1f} people; "
                f"active hours {camera['source_clock_active_hours_by_day_type']['weekday_non_holiday']}"
            ),
            "screening_idf_configuration": (
                f"{modeled_people:.1f} design people over 4,650 m²; local weekday "
                f"{params['weekday_occupancy_start_hour']:.1f}–{params['weekday_occupancy_end_hour']:.1f}; "
                f"post-March multiplier {params['post_march17_people_multiplier']:.2f}"
            ),
            "difference_and_disposition": "Not numerically comparable: camera excludes north office and source clock is unresolved. Replace generic schedule only after spatial/time mapping.",
            "severity": "BLOCKING_SCOPE_TIME",
        },
        {
            "domain": "RTU supply-fan feedback/runtime proxy",
            "measured_or_runtime_evidence": (
                f"Four BAS medians {_f_range(_range(supply_fans, 'median_sampled'), '%')}; "
                f">5% fractions {_f_range([100 * value for value in _range(supply_fans, 'fraction_above_activity_threshold')], '%')}"
            ),
            "screening_idf_configuration": "Continuous availability, identical four-RTU schedule",
            "difference_and_disposition": "Continuous operation is a hypothesis, not proven runtime. Build enable state from fan, airflow, pressure, SAT response, and panel power.",
            "severity": "BLOCKING_CONTROL",
        },
        {
            "domain": "RTU return-fan feedback/runtime proxy",
            "measured_or_runtime_evidence": (
                f"Four BAS medians {_f_range(_range(return_fans, 'median_sampled'), '%')}; "
                f">5% fractions {_f_range([100 * value for value in _range(return_fans, 'fraction_above_activity_threshold')], '%')}"
            ),
            "screening_idf_configuration": "Continuous availability; 415 Pa return-fan pressure-rise proxy",
            "difference_and_disposition": "No measured fan-power/status binding; validate return tracking and power separately.",
            "severity": "MAJOR",
        },
        {
            "domain": "RTU supply-air-temperature setpoint",
            "measured_or_runtime_evidence": (
                f"Four point medians {_f_range(_range(sat_sp, 'median_sampled'), '°F')}; "
                f"point p05 {_f_range(_range(sat_sp, 'p05_sampled'), '°F')}; "
                f"p95 {_f_range(_range(sat_sp, 'p95_sampled'), '°F')}"
            ),
            "screening_idf_configuration": f"Fixed 14.4°C ({modeled_sat_f:.1f}°F) SAT for all four RTUs",
            "difference_and_disposition": (
                f"IDF is {sat_medians[0] - modeled_sat_f:.1f}–{sat_medians[1] - modeled_sat_f:.1f}°F below the four measured median setpoints. "
                "Replace it with dated measured replay for physics calibration, then infer a validated reset law."
            ),
            "severity": "BLOCKING_CONTROL",
        },
        {
            "domain": "Measured SAT tracking",
            "measured_or_runtime_evidence": (
                f"Actual-minus-setpoint mean {relationships['sat_tracking']['aggregate_error'].get('mean')}°F; "
                f"within ±2°F {_pct(relationships['sat_tracking']['fraction_within_2F'])}"
            ),
            "screening_idf_configuration": "No BAS tracking-error target in the 50-run objective",
            "difference_and_disposition": "Add per-RTU SAT bias/RMSE/tracking gate; monthly kWh cannot substitute.",
            "severity": "MAJOR",
        },
        {
            "domain": "Zone cooling setpoints",
            "measured_or_runtime_evidence": f"41 BAS point medians {_f_range(_range(cooling_sp, 'median_sampled'), '°F')}",
            "screening_idf_configuration": (
                f"One occupied setpoint {params['occupied_cooling_setpoint_c']:.1f}°C "
                f"({params['occupied_cooling_setpoint_c'] * 1.8 + 32:.1f}°F)"
            ),
            "difference_and_disposition": "One thermostat erases measured zone diversity and regime changes; use zone/cluster schedules.",
            "severity": "BLOCKING_CONTROL",
        },
        {
            "domain": "Zone heating setpoints",
            "measured_or_runtime_evidence": f"41 BAS point medians {_f_range(_range(heating_sp, 'median_sampled'), '°F')}",
            "screening_idf_configuration": (
                f"One occupied setpoint {params['occupied_heating_setpoint_c']:.1f}°C "
                f"({params['occupied_heating_setpoint_c'] * 1.8 + 32:.1f}°F)"
            ),
            "difference_and_disposition": "Use measured zone/cluster setpoints; do not replace them with a generic code schedule.",
            "severity": "BLOCKING_CONTROL",
        },
        {
            "domain": "Occupied thermostat deadband",
            "measured_or_runtime_evidence": (
                f"Valid BAS cooling-minus-heating median "
                f"{relationships['zone_deadbands']['valid_deadband'].get('median_sampled')}°F"
            ),
            "screening_idf_configuration": f"{modeled_deadband_f:.2f}°F",
            "difference_and_disposition": f"Model minus measured median {modeled_deadband_f - float(relationships['zone_deadbands']['valid_deadband'].get('median_sampled')):.2f}°F; preserve zone diversity.",
            "severity": "MAJOR",
        },
        {
            "domain": "Supply/static pressure setpoint",
            "measured_or_runtime_evidence": (
                f"Four BAS medians {_f_range(_range(static_sp, 'median_sampled'))} in publisher-labeled psi; unit/Brick semantics unresolved"
            ),
            "screening_idf_configuration": "1,100 Pa supply-fan pressure rise; not a static-pressure control setpoint",
            "difference_and_disposition": "Not directly comparable. Verify units and bind measured setpoint plus plenum-pressure response before tuning fan power.",
            "severity": "BLOCKING_UNIT_BINDING",
        },
        {
            "domain": "Outdoor-air fraction/minimum",
            "measured_or_runtime_evidence": (
                f"OA/SA ratio median {oa_ratio:.4f} "
                "during plausible active rows; useful OA data mainly Apr-Dec 2020"
            ),
            "screening_idf_configuration": (
                f"Fixed minimum OA {params['minimum_outdoor_air_m3_s']:.3f} m³/s versus "
                f"{params['coil_airflow_m3_s']:.3f} m³/s coil flow "
                f"({100 * modeled_minimum_oa_ratio:.1f}%)"
            ),
            "difference_and_disposition": (
                f"Plausible-row measured median is {100 * (oa_ratio - modeled_minimum_oa_ratio):+.1f} percentage points above the IDF minimum ratio, "
                "but it is not a like-for-like minimum-OA test. Replay measured OA/control regimes and smoke modes."
            ),
            "severity": "BLOCKING_CONTROL",
        },
        {
            "domain": "UFT terminal fans",
            "measured_or_runtime_evidence": (
                f"51 fan columns; point medians {_f_range(_range(uft_fans, 'median_sampled'), '%')}"
            ),
            "screening_idf_configuration": "No terminal fans; 24 conventional VAV terminal proxies",
            "difference_and_disposition": "Topology mismatch: implement mapped fan-powered perimeter terminals.",
            "severity": "BLOCKING_TOPOLOGY",
        },
        {
            "domain": "UFT hydronic heating valves",
            "measured_or_runtime_evidence": (
                f"44 valve columns; point medians {_f_range(_range(uft_valves, 'median_sampled'), '%')}"
            ),
            "screening_idf_configuration": "24 electric reheat coils; about 626 MWh/year excluded from the scored subtotal",
            "difference_and_disposition": "Nonphysical major mismatch: replace electric reheat with hydronic UFT coils and regime-correct plant.",
            "severity": "BLOCKING_TOPOLOGY",
        },
        {
            "domain": "Chilled-water loop temperature/activity",
            "measured_or_runtime_evidence": (
                f"Active-flow supply median {chilled['supply_temperature_degF_when_flow_active'].get('median')}°F; "
                f"return {chilled['return_temperature_degF_when_flow_active'].get('median')}°F; "
                f"return-minus-supply median {chilled['return_minus_supply_delta_degF_when_flow_active'].get('median')}°F; "
                f"flow-active fraction {_pct(chilled['active_flow_fraction_of_valid_rows'])}"
            ),
            "screening_idf_configuration": "No chilled/condenser-water plant; four air-cooled TwoSpeedDX coils",
            "difference_and_disposition": "Water-cooled topology is absent. Flow is continuously above the proxy threshold in this late-2020 slice, and the negative return-minus-supply median requires sensor/flow-direction review; it is not proven chiller runtime.",
            "severity": "BLOCKING_TOPOLOGY",
        },
        {
            "domain": "Hot-water loop temperature/activity",
            "measured_or_runtime_evidence": (
                f"Active-flow supply median {hot['supply_temperature_degF_when_flow_active'].get('median')}°F; "
                f"return {hot['return_temperature_degF_when_flow_active'].get('median')}°F; "
                f"return-minus-supply median {hot['return_minus_supply_delta_degF_when_flow_active'].get('median')}°F; "
                f"flow-active fraction {_pct(hot['active_flow_fraction_of_valid_rows'])}"
            ),
            "screening_idf_configuration": "No hot-water loop or heat-pump plant; electric terminal reheat proxy",
            "difference_and_disposition": "Implement dated hydronic plant/UFT configuration; do not infer compressor runtime from water flow alone.",
            "severity": "BLOCKING_TOPOLOGY",
        },
        {
            "domain": "Historical heat-pump HWS temperature",
            "measured_or_runtime_evidence": (
                f"`hp_hws_temp` median {historical_hws_evidence['hot_water_supply_temperature_degF'].get('median')}°F; "
                f"p05-p95 {historical_hws_evidence['hot_water_supply_temperature_degF'].get('p05')}–"
                f"{historical_hws_evidence['hot_water_supply_temperature_degF'].get('p95')}°F"
            ),
            "screening_idf_configuration": "No hot-water supply-temperature schedule or plant",
            "difference_and_disposition": "Use as a temperature/regime diagnostic only; temperature alone is not runtime or delivered heat.",
            "severity": "BLOCKING_TOPOLOGY",
        },
        {
            "domain": "Plant thermal-rate point",
            "measured_or_runtime_evidence": (
                f"Publisher-named `aru_001_power_mbtuph` median "
                f"{plant_meter['publisher_named_thermal_rate_mbtuph'].get('median')}; "
                f"nontrivial fraction {_pct(plant_meter['nontrivial_fraction_abs_above_0_1'])}"
            ),
            "screening_idf_configuration": "No corresponding plant output/meter binding",
            "difference_and_disposition": "Resolve MBtu/h sign and asset scope; never compare this thermal-rate point directly with electrical kW.",
            "severity": "BLOCKING_UNIT_BINDING",
        },
        {
            "domain": "RTU design airflow/cooling capacity",
            "measured_or_runtime_evidence": "Published per RTU: 20,000 cfm and 105.5 kW (30 ton)",
            "screening_idf_configuration": (
                f"{params['coil_airflow_m3_s'] / 0.00047194745:,.0f} cfm and "
                f"{params['cooling_capacity_w'] / 1000:.1f} kW"
            ),
            "difference_and_disposition": (
                f"Airflow {100 * (params['coil_airflow_m3_s'] / 9.438949 - 1):+.1f}%; "
                f"capacity {100 * (params['cooling_capacity_w'] / 105505.59 - 1):+.1f}% versus published rating. "
                "Do not widen bounds to chase kWh."
            ),
            "severity": "MAJOR",
        },
    ]

    return {
        "schema": "vibe23.b59_measured_vs_screening_idf.v1",
        "claim_status": "DISCREPANCY_AUDIT_NOT_CALIBRATED",
        "scope": "two monitored office floors; source clocks unresolved",
        "sources": {
            "occupancy_evidence": {"path": str(occupancy_evidence_path), "sha256": _sha256(occupancy_evidence_path)},
            "hvac_evidence": {"path": str(hvac_evidence_path), "sha256": _sha256(hvac_evidence_path)},
            "champion_parameters": {"path": str(champion_parameters_path), "sha256": _sha256(champion_parameters_path)},
            "champion_idf": {"path": str(champion_idf_path), "sha256": _sha256(champion_idf_path)},
            "energyplus_validation": {"path": str(energyplus_validation_path), "sha256": _sha256(energyplus_validation_path)},
        },
        "plant_evidence": {
            "chilled_water": chilled,
            "hot_water": hot,
            "historical_hws_temperature": historical_hws_evidence,
            "thermal_rate": plant_meter,
        },
        "comparison_rows": rows,
        "decision": "The screening IDF compiles/runs cleanly but is materially inconsistent with measured controls, terminal/plant topology, and several equipment/configuration values. It must not be tuned further as an as-operated model.",
    }


def render_markdown(comparison: dict[str, Any]) -> str:
    lines = [
        "# Building 59 measured BAS analytics versus screening EnergyPlus IDF",
        "",
        "**Status:** `DISCREPANCY_AUDIT_NOT_CALIBRATED`",
        "",
        "The EnergyPlus seed compiles and runs cleanly, but clean execution is not physical calibration. Values below preserve source-clock, partial-scope, command/response, and runtime-proxy caveats.",
        "",
        "| Domain | Downloaded-data analytics | Current screening IDF | Difference / required action |",
        "| --- | --- | --- | --- |",
    ]
    for row in comparison["comparison_rows"]:
        cells = [
            row["domain"],
            row["measured_or_runtime_evidence"],
            row["screening_idf_configuration"],
            f"**{row['severity']}** — {row['difference_and_disposition']}",
        ]
        lines.append("| " + " | ".join(str(cell).replace("|", "\\|").replace("\n", " ") for cell in cells) + " |")
    lines.extend(
        [
            "",
            "## Decision",
            "",
            comparison["decision"],
            "",
            "The current IDF remains `OFFICE_SCREENING_SEED_UNCALIBRATED`. Monthly 2020 NMBE is -4.13%, but CV(RMSE) is 22.36%, so the monthly Guideline 14-style gate is not met. The next IDF must implement the telemetry-first architecture in `docs/B59_AS_OPERATED_MODEL_REVISION_PLAN.md` and pass the same zero-warning/severe/fatal plus complete-EIO gate before scoring.",
            "",
        ]
    )
    return "\n".join(lines)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--raw-root", type=Path, required=True)
    parser.add_argument("--occupancy-evidence", type=Path, default=Path("config/b59_occupancy_load_evidence.json"))
    parser.add_argument("--hvac-evidence", type=Path, default=Path("config/b59_hvac_operating_evidence.json"))
    parser.add_argument("--champion-parameters", type=Path, default=Path("scorecards/b59_2020_screening/champion_parameters.json"))
    parser.add_argument("--champion-idf", type=Path, default=Path("model/b59_screening_champion.generated.idf"))
    parser.add_argument("--energyplus-validation", type=Path, default=Path("scorecards/b59_2020_screening/postrelease_champion_validation.json"))
    parser.add_argument("--json-out", type=Path, required=True)
    parser.add_argument("--markdown-out", type=Path, required=True)
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    comparison = build_comparison(
        raw_root=args.raw_root,
        occupancy_evidence_path=args.occupancy_evidence,
        hvac_evidence_path=args.hvac_evidence,
        champion_parameters_path=args.champion_parameters,
        champion_idf_path=args.champion_idf,
        energyplus_validation_path=args.energyplus_validation,
    )
    args.json_out.parent.mkdir(parents=True, exist_ok=True)
    args.markdown_out.parent.mkdir(parents=True, exist_ok=True)
    args.json_out.write_text(json.dumps(comparison, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    args.markdown_out.write_text(render_markdown(comparison), encoding="utf-8")
    print(json.dumps({"json": str(args.json_out), "markdown": str(args.markdown_out)}, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

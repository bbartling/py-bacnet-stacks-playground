"""Bounded, non-promoting 50-run EnergyPlus screening campaign for Building 59.

This runner is intentionally independent of the CLI.  It is a reproducible
screening harness for the runnable office proxy, not a calibration workflow:
the source-meter scope and source-clock month basis differ from the EnergyPlus
facility proxy and local-standard-time output basis.
"""
from __future__ import annotations

import csv
import hashlib
import json
import math
import re
import subprocess
from concurrent.futures import ThreadPoolExecutor
from dataclasses import asdict, dataclass, replace
from pathlib import Path
from typing import Any, Mapping, Sequence

import pandas as pd

from .b59_model import (
    CFM_TO_M3_S,
    DEFAULT_CALIBRATION_PARAMETERS,
    DX_MAX_AIRFLOW_PER_CAPACITY_M3_S_W,
    DX_MIN_AIRFLOW_PER_CAPACITY_M3_S_W,
    METER_PARTIAL_TARGET_PROXY,
    B59CalibrationParameters,
    build_b59_screening_seed_idf,
)
from .metrics import score_calibration

MAX_B59_SCREENING_RUNS = 50
FACILITY_SCOPE_LABEL = "PARTIAL_METER_BOUND_PROXY_VS_DERIVED_OFFICE_SUBTOTAL_SCOPE_GAPS"
TIME_BASIS_LABEL = "SOURCE_CLOCK_MONTHS_VS_LOCAL_STANDARD_MONTHS_TIME_BASIS_MISMATCH"
_FACILITY_HOURLY = re.compile(r"^\s*Electricity:Facility\s*\[J\]\(Hourly\)\s*$", re.I)
_EPLUS_TIME = re.compile(r"^\s*(\d{1,2})/(\d{1,2})\s+(\d{1,2}):(\d{2})(?::\d{2})?\s*$")
_WARNING = re.compile(r"\*\*\s*Warning\s*\*\*", re.I)
_SEVERE = re.compile(r"\*\*\s*Severe\s*\*\*", re.I)
_FATAL = re.compile(r"\*\*\s*Fatal\s*\*\*", re.I)
_READVARS_FAILURE = re.compile(r"(?:EOF encountered on eplusout|ReadVarsESO program terminated)", re.I)


@dataclass(frozen=True)
class B59CampaignCandidate:
    ordinal: int
    run_id: str
    stage: str
    parameter_families: tuple[str, ...]
    parameters: B59CalibrationParameters
    parent_run_id: str | None = None
    holdout: bool = False

    def __post_init__(self) -> None:
        if not 1 <= self.ordinal <= MAX_B59_SCREENING_RUNS or self.run_id != f"R{self.ordinal:02d}":
            raise ValueError("candidate ordinal/run_id must be R01 through R50")
        if not self.parameter_families:
            raise ValueError("candidate needs named parameter families")
        if len(self.parameter_families) > 2:
            raise ValueError("candidate may change at most two named parameter families")

    def as_dict(self) -> dict[str, Any]:
        return asdict(self)


def _set(base: B59CalibrationParameters, family: str, side: str) -> B59CalibrationParameters:
    """Return an evidence-bounded low/high representative using ``replace``."""
    values: dict[str, dict[str, Mapping[str, Any]]] = {
        "occupancy_calendar": {
            "low": {"people_area_per_person_m2": 28.0, "post_march17_people_multiplier": 0.15},
            "high": {"people_area_per_person_m2": 14.0, "post_march17_people_multiplier": 0.40},
        },
        "internal_loads": {
            "low": {"lighting_w_m2": 5.5, "equipment_w_m2": 7.0},
            "high": {"lighting_w_m2": 11.0, "equipment_w_m2": 15.0},
        },
        "hvac_schedule": {
            "low": {"weekday_hvac_start_hour": 6.5, "weekday_hvac_end_hour": 20.0},
            "high": {
                "weekday_hvac_start_hour": 4.5,
                "weekday_hvac_end_hour": 23.0,
                "hvac_availability_mode": "continuous",
            },
        },
        "envelope": {
            "low": {"wall_thermal_resistance_m2_k_w": 1.8, "roof_thermal_resistance_m2_k_w": 3.8, "glazing_u_w_m2_k": 3.1, "glazing_shgc": 0.45},
            "high": {"wall_thermal_resistance_m2_k_w": 4.2, "roof_thermal_resistance_m2_k_w": 7.0, "glazing_u_w_m2_k": 1.5, "glazing_shgc": 0.25},
        },
        "infiltration": {"low": {"infiltration_m3_s_m2": 0.00015}, "high": {"infiltration_m3_s_m2": 0.00075}},
        "outdoor_air": {"low": {"minimum_outdoor_air_m3_s": 0.80 * 2.35973725}, "high": {"minimum_outdoor_air_m3_s": 1.05 * 2.35973725}},
        "fans": {
            "low": {
                "supply_fan_pressure_pa": 750.0,
                "supply_fan_total_efficiency": 0.78,
                "return_fan_pressure_pa": 250.0,
                "return_fan_total_efficiency": 0.78,
            },
            "high": {
                "supply_fan_pressure_pa": 1400.0,
                "supply_fan_total_efficiency": 0.60,
                "return_fan_pressure_pa": 650.0,
                "return_fan_total_efficiency": 0.60,
            },
        },
        "cooling": {
            "low": {"cooling_cop": 2.65, "cooling_capacity_w": 0.95 * 105505.5852},
            "high": {
                "cooling_cop": 4.1,
                "cooling_capacity_w": 1.35 * 105505.5852,
                "cooling_shr": 0.70,
                "coil_airflow_m3_s": 13_500.0 * CFM_TO_M3_S,
            },
        },
        "setpoints": {"low": {"occupied_heating_setpoint_c": 19.5, "occupied_cooling_setpoint_c": 25.5}, "high": {"occupied_heating_setpoint_c": 21.8, "occupied_cooling_setpoint_c": 23.2}},
    }
    updates = dict(values[family][side])
    if family == "cooling" and side == "low":
        capacity = float(updates["cooling_capacity_w"])
        airflow_ratio = base.coil_airflow_m3_s / capacity
        if not (
            DX_MIN_AIRFLOW_PER_CAPACITY_M3_S_W
            <= airflow_ratio
            <= DX_MAX_AIRFLOW_PER_CAPACITY_M3_S_W
        ):
            # A prior high-cooling incumbent may carry the maximum airflow.
            # Couple it back to the published 12,000-cfm proxy when testing a
            # low-capacity hypothesis instead of generating an invalid coil.
            updates["coil_airflow_m3_s"] = 12_000.0 * CFM_TO_M3_S
    return replace(base, **updates)


_FAMILIES = ("occupancy_calendar", "internal_loads", "hvac_schedule", "envelope", "infiltration", "outdoor_air", "fans", "cooling", "setpoints")


def preregistered_candidates(
    base: B59CalibrationParameters = DEFAULT_CALIBRATION_PARAMETERS,
    *,
    incumbent: B59CalibrationParameters | None = None,
) -> tuple[B59CampaignCandidate, ...]:
    """Generate exactly the preregistered R01--R50 ordinal candidate slots.

    ``incumbent`` is a stage boundary input (normally selected only from prior
    tuning results).  It never alters ordinals, family names, or the 50-run cap.
    """
    current = incumbent or base
    items: list[B59CampaignCandidate] = []

    def add(
        stage: str,
        families: Sequence[str],
        params: B59CalibrationParameters,
        parent: str | None = None,
        holdout: bool = False,
    ) -> None:
        ordinal = len(items) + 1
        items.append(B59CampaignCandidate(ordinal, f"R{ordinal:02d}", stage, tuple(families), params, parent, holdout))
    add("seed", ("seed",), base)
    add("repeatability", ("seed",), base, "R01")
    for family in _FAMILIES:
        add("family_screen_low", (family,), _set(base, family, "low"), "R01")
        add("family_screen_high", (family,), _set(base, family, "high"), "R01")
    refinement_families = ("internal_loads", "hvac_schedule", "outdoor_air", "cooling")
    for family in refinement_families:
        low, high = _set(current, family, "low"), _set(current, family, "high")
        for fraction in (0.25, 0.5, 0.75):
            fields = {key: getattr(current, key) for key in current.BOUNDS}
            for key in fields:
                a, b = getattr(low, key), getattr(high, key)
                if a != getattr(current, key) or b != getattr(current, key):
                    fields[key] = float(a) + fraction * (float(b) - float(a))
            add("coordinate_refinement", (family,), replace(current, **fields), "R20")
    pairs = (("internal_loads", "hvac_schedule"), ("outdoor_air", "fans"), ("cooling", "setpoints"))
    for first, second in pairs:
        for side in ("low", "high"):
            candidate = _set(_set(current, first, side), second, side)
            add("interaction", (first, second), candidate, "R32")
    for ordinal, family in enumerate(("internal_loads", "hvac_schedule", "outdoor_air", "cooling", "fans", "infiltration")):
        add("adaptive_refinement", (family,), _set(current, family, "low" if ordinal % 2 == 0 else "high"), "R38")
    add("identifiability_challenger", ("envelope", "infiltration"), _set(_set(current, "envelope", "low"), "infiltration", "high"), "R44")
    add("identifiability_challenger", ("outdoor_air", "fans"), _set(_set(current, "outdoor_air", "high"), "fans", "low"), "R44")
    add("frozen_champion", ("frozen_champion",), current, "R46")
    add("frozen_champion_repeat", ("frozen_champion",), current, "R47")
    add("holdout_evaluation", ("frozen_champion",), current, "R47", True)
    add("holdout_evaluation_repeat", ("frozen_champion",), current, "R49", True)
    if len(items) != MAX_B59_SCREENING_RUNS:
        raise AssertionError("preregistered campaign must contain exactly 50 candidates")
    return tuple(items)


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def parse_hourly_meter(csv_path: Path, meter_name: str) -> pd.Series:
    """Parse exactly one named hourly joule meter; reject ambiguity."""
    meter_pattern = re.compile(rf"^\s*{re.escape(meter_name)}\s*\[J\]\(Hourly\)\s*$", re.I)
    with Path(csv_path).open(encoding="utf-8", newline="") as stream:
        rows = csv.reader(stream)
        header = next(rows, [])
        indexes = [i for i, value in enumerate(header) if meter_pattern.fullmatch(value)]
        if len(indexes) != 1 or not header or header[0].strip().casefold() != "date/time":
            raise ValueError(f"expected exactly one Hourly {meter_name} [J] meter")
        values: list[float] = []
        index: list[pd.Timestamp] = []
        for number, row in enumerate(rows, start=2):
            if len(row) != len(header):
                raise ValueError(f"row {number} has unexpected field count")
            match = _EPLUS_TIME.fullmatch(row[0])
            if match is None:
                raise ValueError(f"row {number} has invalid EnergyPlus timestamp")
            month, day, hour, minute = map(int, match.groups())
            if not 1 <= hour <= 24 or minute != 0:
                raise ValueError(f"row {number} is not an hourly end-of-interval timestamp")
            # EnergyPlus labels an hourly value by the interval end (01:00 to
            # 24:00).  Convert to its unique start time without moving a
            # 24:00 record into the next billing month.
            stamp = pd.Timestamp(year=2020, month=month, day=day) + pd.Timedelta(hours=hour - 1)
            value = float(row[indexes[0]])
            if not math.isfinite(value) or value < 0:
                raise ValueError(f"row {number} has invalid Facility joules")
            index.append(stamp)
            values.append(value)
    result = pd.Series(values, index=pd.DatetimeIndex(index), name=meter_name)
    if len(result) < 1 or result.index.has_duplicates or not result.index.is_monotonic_increasing:
        raise ValueError("hourly Facility meter must be nonempty, unique, and ordered")
    return result


def parse_hourly_facility_meter(csv_path: Path) -> pd.Series:
    """Parse exactly one canonical hourly Facility J meter; reject ambiguity."""
    return parse_hourly_meter(csv_path, "Electricity:Facility")


def parse_hourly_target_proxy(csv_path: Path) -> pd.Series:
    """Parse the model's explicit meter-bound subtotal proxy."""
    return parse_hourly_meter(csv_path, METER_PARTIAL_TARGET_PROXY)


def monthly_facility_kwh(hourly_j: pd.Series) -> pd.Series:
    monthly = (hourly_j / 3_600_000.0).groupby(hourly_j.index.month).sum()
    if list(monthly.index) != list(range(1, 13)):
        raise ValueError("Facility output must cover every month January through December")
    return monthly.rename("simulated_kwh")


def parse_measured_monthly_kwh(path: Path) -> pd.Series:
    frame = pd.read_csv(path)
    value_column = next((name for name in ("energy_kwh", "measured_kwh", "measured") if name in frame), None)
    month_column = next((name for name in ("month", "timestamp", "date") if name in frame), None)
    if value_column is None or month_column is None:
        raise ValueError("measured monthly CSV requires month/timestamp and energy_kwh/measured columns")
    raw_months = frame[month_column]
    numeric_months = pd.to_numeric(raw_months, errors="coerce")
    if numeric_months.notna().all() and numeric_months.between(1, 12).all():
        months = numeric_months
    else:
        months = pd.to_datetime(raw_months, errors="coerce", utc=True).dt.month
    values = pd.to_numeric(frame[value_column], errors="coerce")
    result = pd.Series(values.to_numpy(float), index=pd.Index(months.to_numpy(int), name="month"), name="measured_kwh")
    if result.isna().any() or sorted(result.index.tolist()) != list(range(1, 13)) or (result < 0).any():
        raise ValueError("measured monthly CSV must contain one finite nonnegative record for each month")
    return result


def score_facility_proxy(simulated_monthly_kwh: pd.Series, measured_monthly_kwh: pd.Series) -> dict[str, Any]:
    paired = pd.concat([measured_monthly_kwh, simulated_monthly_kwh], axis=1).reindex(range(1, 13))
    if paired.isna().any().any():
        raise ValueError("monthly measured/simulated values must pair for January through December")
    tuning = paired.loc[1:9]
    reserved = paired.loc[10:12]
    tuning_score = score_calibration(tuning.iloc[:, 0], tuning.iloc[:, 1], "monthly", p=1)
    reserved_score = score_calibration(reserved.iloc[:, 0], reserved.iloc[:, 1], "monthly", p=1)
    full_year_score = score_calibration(paired.iloc[:, 0], paired.iloc[:, 1], "monthly", p=1)
    objective = (abs(tuning_score.nmbe_pct) / 5.0) ** 2 + (tuning_score.cvrmse_pct / 15.0) ** 2
    return {
        "claim_status": "SCREENING_ONLY_NOT_A_CALIBRATION_CLAIM",
        "comparison_labels": [FACILITY_SCOPE_LABEL, TIME_BASIS_LABEL],
        "tuning_months": list(range(1, 10)),
        "holdout_months": list(range(10, 13)),
        "tuning_gl14": tuning_score.as_dict(),
        "holdout_gl14": reserved_score.as_dict(),
        "reserved_validation_disclosure": (
            "Legacy keys retain 'holdout' for artifact compatibility, but October-December metrics are computed "
            "for every candidate and are not blind holdout evidence."
        ),
        "full_year_gl14": full_year_score.as_dict(),
        "objective": float(objective),
        "monthly_kwh": [{"month": int(month), "measured_kwh": float(row.iloc[0]), "simulated_kwh": float(row.iloc[1])} for month, row in paired.iterrows()],
    }


def _admission(run_dir: Path, returncode: int) -> tuple[bool, list[str]]:
    text = "\n".join((run_dir / name).read_text(encoding="utf-8", errors="replace") if (run_dir / name).is_file() else "" for name in ("eplusout.err", "eplusout.end", "console.log"))
    reasons = [] if returncode == 0 else ["nonzero_returncode"]
    for name, pattern in (("warning", _WARNING), ("severe", _SEVERE), ("fatal", _FATAL)):
        if pattern.search(text):
            reasons.append(name)
    if _READVARS_FAILURE.search(text):
        reasons.append("readvars_failure")
    eio_path = run_dir / "eplusout.eio"
    if not eio_path.is_file() or "End of Data" not in eio_path.read_text(
        encoding="utf-8", errors="replace"
    ):
        reasons.append("sizing_evidence_incomplete")
    try:
        facility = parse_hourly_facility_meter(run_dir / "eplusout.csv")
        target_proxy = parse_hourly_target_proxy(run_dir / "eplusout.csv")
        if len(facility) not in {8760, 8784} or not facility.index.equals(target_proxy.index):
            reasons.append("facility_meter:annual coverage/index mismatch")
    except (OSError, ValueError) as exc:
        reasons.append(f"facility_meter:{exc}")
    return not reasons, reasons


def run_b59_screening_campaign(
    *, energyplus_executable: Path, epw: Path, measured_monthly_csv: Path, output_root: Path, max_workers: int = 1,
    candidates: Sequence[B59CampaignCandidate] | None = None,
) -> list[dict[str, Any]]:
    """Run/resume staged candidates without exceeding the immutable 50-run cap."""
    executable = Path(energyplus_executable).resolve()
    epw = Path(epw).resolve()
    measured = Path(measured_monthly_csv).resolve()
    root = Path(output_root).resolve()
    if not executable.is_file() or not epw.is_file() or max_workers < 1:
        raise ValueError("preflight requires executable EPW and max_workers >= 1")
    measured_values = parse_measured_monthly_kwh(measured)
    queue = tuple(candidates or preregistered_candidates())
    if len(queue) > MAX_B59_SCREENING_RUNS or len({item.ordinal for item in queue}) != len(queue):
        raise ValueError("campaign candidate list exceeds or violates the 50-run cap")
    root.mkdir(parents=True, exist_ok=True)

    def run_one(item: B59CampaignCandidate) -> dict[str, Any]:
        run_dir = root / item.run_id
        result_path = run_dir / "result.json"
        if result_path.is_file():
            existing = json.loads(result_path.read_text(encoding="utf-8"))
            expected_candidate = json.loads(json.dumps(item.as_dict(), default=str))
            expected_hashes = {
                "epw_sha256": _sha256(epw),
                "measured_monthly_sha256": _sha256(measured),
            }
            if existing.get("candidate") != expected_candidate:
                raise ValueError(f"{item.run_id} resume candidate does not match the requested preregistration")
            for name, digest in expected_hashes.items():
                if existing.get("input_hashes", {}).get(name) != digest:
                    raise ValueError(f"{item.run_id} resume {name} does not match the current input")
            current_admitted, current_reasons = _admission(run_dir, int(existing.get("returncode", -1)))
            if not current_admitted:
                raise ValueError(
                    f"{item.run_id} existing artifacts fail the current admission gate: {current_reasons}; "
                    "use a fresh run root for a new execution"
                )
            if existing.get("admitted") is not True:
                raise ValueError(f"{item.run_id} existing result was not admitted")
            return existing
        run_dir.mkdir(parents=True, exist_ok=False)
        idf = run_dir / "in.idf"
        idf.write_text(build_b59_screening_seed_idf(item.parameters, output_profile="lean"), encoding="utf-8")
        (run_dir / "parameters.json").write_text(json.dumps(item.as_dict(), default=str, indent=2, sort_keys=True) + "\n", encoding="utf-8")
        # EnergyPlus invokes ExpandObjects and may create fixed-name helper
        # symlinks in its working directory.  Isolate each process in its own
        # run directory so concurrent candidates cannot collide.
        completed = subprocess.run(
            [str(executable), "-x", "-r", "-w", str(epw), "-d", ".", idf.name],
            cwd=run_dir,
            capture_output=True,
            text=True,
            check=False,
        )
        (run_dir / "console.log").write_text((completed.stdout or "") + "\n" + (completed.stderr or ""), encoding="utf-8")
        admitted, reasons = _admission(run_dir, completed.returncode)
        payload: dict[str, Any] = {"schema": "vibe23.b59_screening_run.v1", "candidate": item.as_dict(), "returncode": completed.returncode, "admitted": admitted, "reasons": reasons, "claim_status": "SCREENING_ONLY_NOT_A_CALIBRATION_CLAIM", "comparison_labels": [FACILITY_SCOPE_LABEL, TIME_BASIS_LABEL], "input_hashes": {"idf_sha256": _sha256(idf), "epw_sha256": _sha256(epw), "measured_monthly_sha256": _sha256(measured)}}
        if admitted:
            payload["score"] = score_facility_proxy(
                monthly_facility_kwh(parse_hourly_target_proxy(run_dir / "eplusout.csv")),
                measured_values,
            )
            payload["score"]["simulation_meter"] = METER_PARTIAL_TARGET_PROXY
        payload["artifact_hashes"] = {path.name: _sha256(path) for path in sorted(run_dir.iterdir()) if path.is_file()}
        result_path.write_text(json.dumps(payload, default=str, indent=2, sort_keys=True) + "\n", encoding="utf-8")
        return payload

    results: list[dict[str, Any]] = []
    for stage in dict.fromkeys(item.stage for item in queue):
        stage_items = [item for item in queue if item.stage == stage]
        with ThreadPoolExecutor(max_workers=max_workers) as executor:
            results.extend(executor.map(run_one, stage_items))
    results.sort(key=lambda row: row["candidate"]["ordinal"])
    summary = root / "summary.jsonl"
    summary.write_text("".join(json.dumps(row, default=str, sort_keys=True, separators=(",", ":")) + "\n" for row in results), encoding="utf-8")
    return results

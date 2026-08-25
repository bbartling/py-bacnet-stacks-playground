"""Shared EnergyPlus helpers for Vibe23 grid-search lessons.

EDUCATIONAL ONLY — stock ExampleFiles, illustrative tariffs, no BACnet.
"""

from __future__ import annotations

import csv
import json
import os
import re
import shutil
import subprocess
import time
from dataclasses import asdict, dataclass
from pathlib import Path


DEFAULT_EPLUS_ROOT = Path(os.environ.get("ENERGYPLUS_ROOT", r"C:\EnergyPlusV26-1-0"))
DEFAULT_WEATHER = (
    DEFAULT_EPLUS_ROOT
    / "WeatherData"
    / "USA_IL_Chicago-OHare.Intl.AP.725300_TMY3.epw"
)

INTERVAL_HOURS = 0.25
ENERGY_RATE_USD_PER_KWH = 0.07
ON_PEAK_DEMAND_RATE_USD_PER_KW = 12.25
ON_PEAK_START_HOUR = 8
ON_PEAK_END_HOUR = 20


@dataclass
class RunMetrics:
    candidate: str
    ready: bool
    min_ready_zone_f: float
    electricity_kwh: float
    facility_peak_kw: float
    on_peak_peak_kw: float
    energy_cost_usd: float
    demand_cost_usd: float
    objective_usd: float
    runtime_seconds: float
    severe_errors: int
    fatal_errors: int
    extra: dict | None = None


def eplus_exe(root: Path | None = None) -> Path:
    root = root or DEFAULT_EPLUS_ROOT
    for name in ("energyplus.exe", "energyplus"):
        candidate = root / name
        if candidate.exists():
            return candidate
    raise FileNotFoundError(f"energyplus executable not found under {root}")


def example_idf(name: str, root: Path | None = None) -> Path:
    path = (root or DEFAULT_EPLUS_ROOT) / "ExampleFiles" / name
    if not path.exists():
        raise FileNotFoundError(path)
    return path


def weather_file(root: Path | None = None) -> Path:
    path = DEFAULT_WEATHER if root is None else (
        root / "WeatherData" / "USA_IL_Chicago-OHare.Intl.AP.725300_TMY3.epw"
    )
    if not path.exists():
        raise FileNotFoundError(path)
    return path


def c_to_f(value_c: float) -> float:
    return value_c * 9.0 / 5.0 + 32.0


def f_to_c(value_f: float) -> float:
    return (value_f - 32.0) * 5.0 / 9.0


def replace_object(text: str, object_type: str, object_name: str, replacement: str) -> str:
    pattern = re.compile(
        rf"(?ims)^\s*{re.escape(object_type)}\s*,\s*\r?\n"
        rf"\s*{re.escape(object_name)}\s*,.*?;"
    )
    updated, count = pattern.subn(replacement.strip(), text, count=1)
    if count != 1:
        raise RuntimeError(f"Could not uniquely replace {object_type} named {object_name}")
    return updated


def remove_all_objects(text: str, object_type: str) -> tuple[str, int]:
    pattern = re.compile(rf"(?ims)^\s*{re.escape(object_type)}\s*,.*?;")
    return pattern.subn("", text)


def set_single_run_period(
    text: str,
    *,
    begin_month: int = 1,
    begin_day: int = 14,
    end_month: int | None = None,
    end_day: int | None = None,
    name: str = "GRID SEARCH LESSON DAY",
) -> str:
    end_month = end_month or begin_month
    end_day = end_day or begin_day
    text, _ = remove_all_objects(text, "RunPeriod")
    run_period = f"""
RunPeriod,
  {name},
  {begin_month},
  {begin_day},
  ,
  {end_month},
  {end_day},
  ,
  Tuesday,
  Yes,
  Yes,
  No,
  Yes,
  Yes;
"""
    return text + "\n\n" + run_period.strip() + "\n"


def force_run_period_only(text: str) -> str:
    """Skip sizing/design days; run the weather file period only.

    Use only on ExampleFiles that are already hard-sized (e.g. classic 5Zone
    WLHP). Autosized reference / PV-storage models need ensure_weather_run().
    """
    simulation_control = """
SimulationControl,
  No,
  No,
  No,
  No,
  Yes,
  No,
  1;
"""
    updated, count = re.subn(
        r"(?ims)^\s*SimulationControl\s*,.*?;",
        simulation_control.strip(),
        text,
        count=1,
    )
    if count != 1:
        raise RuntimeError("Could not uniquely replace SimulationControl")
    return updated


def ensure_weather_run(
    text: str,
    *,
    zone_sizing: bool = True,
    system_sizing: bool = True,
    plant_sizing: bool = True,
    sizing_periods: bool = True,
) -> str:
    """Keep sizing flags on and force a weather-file run period."""

    def yn(flag: bool) -> str:
        return "Yes" if flag else "No"

    simulation_control = f"""
SimulationControl,
  {yn(zone_sizing)},
  {yn(system_sizing)},
  {yn(plant_sizing)},
  {yn(sizing_periods)},
  Yes,
  No,
  1;
"""
    updated, count = re.subn(
        r"(?ims)^\s*SimulationControl\s*,.*?;",
        simulation_control.strip(),
        text,
        count=1,
    )
    if count != 1:
        raise RuntimeError("Could not uniquely replace SimulationControl")
    return updated


def append_outputs(text: str, lines: list[str]) -> str:
    block = "\n\n!- Added by vibe23 grid_search lessons\n" + "\n".join(lines) + "\n"
    return text + block


DEFAULT_OUTPUTS = [
    "Output:Meter,Electricity:Facility,Timestep;",
    "Output:Variable,*,Zone Mean Air Temperature,Timestep;",
]

BESS_OUTPUTS = [
    "Output:Meter,Electricity:Facility,Timestep;",
    "Output:Meter,ElectricityPurchased:Facility,Timestep;",
    "Output:Meter,ElectricitySurplusSold:Facility,Timestep;",
    "Output:Variable,*,Zone Mean Air Temperature,Timestep;",
    "Output:Variable,*,Electric Storage Battery Charge State,Timestep;",
    "Output:Variable,*,Electric Storage Charge Fraction,Timestep;",
]


def heating_setpoint_schedule(
    name: str,
    *,
    setback_c: float,
    occupied_c: float,
    recovery_hour: int,
    occupied_end_hour: int = 18,
) -> str:
    return f"""
Schedule:Compact,
  {name},
  Temperature,
  Through: 12/31,
  For: Weekdays CustomDay1 CustomDay2,
  Until: {recovery_hour}:00,{setback_c:.3f},
  Until: {occupied_end_hour}:00,{occupied_c:.3f},
  Until: 24:00,{setback_c:.3f},
  For: Weekends Holidays SummerDesignDay,
  Until: 24:00,{setback_c:.3f},
  For: WinterDesignDay,
  Until: 24:00,{occupied_c:.3f};
"""


def demand_limit_schedule(name: str, peak_limit_w: float) -> str:
    return f"""
Schedule:Compact,
  {name},
  Any Number,
  Through: 12/31,
  For: AllDays,
  Until: 8:00,9999999,
  Until: 20:00,{peak_limit_w:.0f},
  Until: 24:00,9999999;
"""


def run_energyplus(
    idf_text: str,
    run_dir: Path,
    *,
    weather: Path | None = None,
    exe: Path | None = None,
) -> float:
    if run_dir.exists():
        shutil.rmtree(run_dir)
    run_dir.mkdir(parents=True)
    idf_path = run_dir / "candidate.idf"
    idf_path.write_text(idf_text, encoding="utf-8")
    exe = exe or eplus_exe()
    weather = weather or weather_file()
    started = time.perf_counter()
    process = subprocess.run(
        [str(exe), "-w", str(weather), "-d", str(run_dir), "-r", str(idf_path)],
        capture_output=True,
        text=True,
        check=False,
    )
    runtime = time.perf_counter() - started
    (run_dir / "console.log").write_text(
        (process.stdout or "") + "\n" + (process.stderr or ""),
        encoding="utf-8",
    )
    if process.returncode != 0:
        raise RuntimeError(
            f"EnergyPlus exited {process.returncode}; see {run_dir / 'console.log'}"
        )
    return runtime


def find_column(fieldnames: list[str], starts_with: str) -> str:
    for name in fieldnames:
        if name.upper().startswith(starts_with.upper()):
            return name
    raise RuntimeError(f"EnergyPlus CSV is missing a column beginning with {starts_with!r}")


def find_columns_containing(fieldnames: list[str], needle: str) -> list[str]:
    needle_u = needle.upper()
    return [name for name in fieldnames if needle_u in name.upper()]


def count_err_markers(err_path: Path) -> tuple[int, int]:
    if not err_path.exists():
        return 0, 0
    err_text = err_path.read_text(encoding="utf-8", errors="replace")
    severe = len(re.findall(r"\*\* Severe \*\*", err_text))
    fatal = len(re.findall(r"\*\*  Fatal  \*\*|\*\* Fatal \*\*", err_text))
    return severe, fatal


def parse_facility_and_readiness(
    run_dir: Path,
    *,
    candidate: str,
    runtime: float,
    ready_clocks: tuple[tuple[int, int], ...] = ((8, 0), (8, 15)),
    ready_min_f: float = 68.0,
    meter_prefix: str = "ELECTRICITY:FACILITY",
    max_zones: int | None = 5,
) -> RunMetrics:
    csv_path = run_dir / "eplusout.csv"
    if not csv_path.exists():
        raise RuntimeError(f"EnergyPlus did not create {csv_path}")

    severe, fatal = count_err_markers(run_dir / "eplusout.err")
    with csv_path.open(newline="", encoding="utf-8-sig") as handle:
        reader = csv.DictReader(handle)
        fieldnames = list(reader.fieldnames or [])
        meter_col = find_column(fieldnames, meter_prefix)
        zone_cols = [
            name
            for name in fieldnames
            if "ZONE MEAN AIR TEMPERATURE" in name.upper()
            and "PLENUM" not in name.upper()
        ]
        if max_zones is not None:
            zone_cols = zone_cols[:max_zones]
        rows = list(reader)

    electricity_kwh = 0.0
    facility_peak_kw = 0.0
    on_peak_peak_kw = 0.0
    ready_temperatures_f: list[float] = []

    for row in rows:
        joules = float(row[meter_col] or 0.0)
        interval_kwh = joules / 3_600_000.0
        interval_kw = interval_kwh / INTERVAL_HOURS
        electricity_kwh += interval_kwh
        facility_peak_kw = max(facility_peak_kw, interval_kw)

        match = re.search(r"\s(\d{1,2}):(\d{2}):", row.get("Date/Time", ""))
        if not match:
            continue
        hour = int(match.group(1))
        minute = int(match.group(2))
        clock_hour = 0 if hour == 24 else hour

        if ON_PEAK_START_HOUR <= clock_hour < ON_PEAK_END_HOUR:
            on_peak_peak_kw = max(on_peak_peak_kw, interval_kw)

        if (hour, minute) in ready_clocks and zone_cols:
            ready_temperatures_f.extend(c_to_f(float(row[name])) for name in zone_cols)

    min_ready_f = min(ready_temperatures_f) if ready_temperatures_f else -999.0
    ready = bool(ready_temperatures_f) and min_ready_f >= ready_min_f
    energy_cost = electricity_kwh * ENERGY_RATE_USD_PER_KWH
    demand_cost = on_peak_peak_kw * ON_PEAK_DEMAND_RATE_USD_PER_KW

    return RunMetrics(
        candidate=candidate,
        ready=ready,
        min_ready_zone_f=min_ready_f,
        electricity_kwh=electricity_kwh,
        facility_peak_kw=facility_peak_kw,
        on_peak_peak_kw=on_peak_peak_kw,
        energy_cost_usd=energy_cost,
        demand_cost_usd=demand_cost,
        objective_usd=energy_cost + demand_cost,
        runtime_seconds=runtime,
        severe_errors=severe,
        fatal_errors=fatal,
    )


def write_results_csv(results: list[RunMetrics], path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    rows = []
    for result in results:
        row = asdict(result)
        extra = row.pop("extra") or {}
        row.update(extra)
        rows.append(row)
    fieldnames = list(rows[0].keys()) if rows else []
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)


def write_decision_json(path: Path, payload: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2), encoding="utf-8")


def print_ranked(results: list[RunMetrics], *, top: int = 8) -> RunMetrics | None:
    eligible = [
        r
        for r in results
        if r.ready and r.severe_errors == 0 and r.fatal_errors == 0
    ]
    eligible.sort(key=lambda item: item.objective_usd)
    print("\nTOP FEASIBLE PLANS")
    print("-" * 92)
    print("rank  plan                      minF      kWh   peak kW  on-peak      objective")
    print("-" * 92)
    for rank, result in enumerate(eligible[:top], start=1):
        print(
            f"{rank:>4}  {result.candidate:<24} {result.min_ready_zone_f:6.1f} "
            f"{result.electricity_kwh:8.1f} {result.facility_peak_kw:9.1f} "
            f"{result.on_peak_peak_kw:8.1f} ${result.objective_usd:10.2f}"
        )
    print("-" * 92)
    return eligible[0] if eligible else None

"""Day 10 — BESS bonus: ShopWithPVandBattery SOC / capacity grid."""

from __future__ import annotations

import argparse
import csv
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import eplus_lab as lab

SOURCE = "ShopWithPVandBattery.idf"


def patch_storage_bounds(
    text: str,
    *,
    max_soc: float,
    min_soc: float,
    initial_soc: float,
    modules_parallel: int,
) -> str:
    """Patch ElectricLoadCenter:Distribution SOC bounds and battery initial SOC / size."""

    def dist_repl(match: re.Match[str]) -> str:
        block = match.group(0)
        # Replace trailing SOC fraction fields carefully by rewriting the object.
        return f"""ElectricLoadCenter:Distribution,
    PV Array Load Center,    !- Name
    Generator List,          !- Generator List Name
    TrackElectrical,         !- Generator Operation Scheme Type
    0,                       !- Generator Demand Limit Scheme Purchased Electric Demand Limit {{W}}
    ,                        !- Generator Track Schedule Name Scheme Schedule Name
    ,                        !- Generator Track Meter Scheme Meter Name
    DirectCurrentWithInverterDCStorage,  !- Electrical Buss Type
    PV Inverter,             !- Inverter Name
    Kibam,                   !- Electrical Storage Object Name
    ,                        !- Transformer Object Name
    TrackFacilityElectricDemandStoreExcessOnSite,  !- Storage Operation Scheme
    ,                        !- Storage Control Track Meter Name
    ,                        !- Storage Converter Object Name
    {max_soc:.2f},                    !- Maximum Storage State of Charge Fraction
    {min_soc:.2f};                    !- Minimum Storage State of Charge Fraction
"""

    text, n = re.subn(
        r"(?ims)^\s*ElectricLoadCenter:Distribution\s*,\s*\r?\n\s*PV Array Load Center\s*,.*?;",
        dist_repl,
        text,
        count=1,
    )
    if n != 1:
        raise RuntimeError("Could not patch ElectricLoadCenter:Distribution")

    def batt_repl(match: re.Match[str]) -> str:
        return f"""ElectricLoadCenter:Storage:Battery,
    Kibam,                   !- Name
    ALWAYS_ON,               !- Availability Schedule Name
    ,                        !- Zone Name
    0,                       !- Radiative Fraction
    {modules_parallel},                      !- Number of Battery Modules in Parallel
    10,                      !- Number of Battery Modules in Series
    86.1,                    !- Maximum Module Capacity {{Ah}}
    {initial_soc:.2f},                    !- Initial Fractional State of Charge
    0.37,                    !- Fraction of Available Charge Capacity
    0.5874,                  !- Change Rate from Bound Charge to Available Charge {{1/hr}}
    12.6,                    !- Fully Charged Module Open Circuit Voltage {{V}}
    12.4,                    !- Fully Discharged Module Open Circuit Voltage {{V}}
    charging,                !- Voltage Change Curve Name for Charging
    discharging,             !- Voltage Change Curve Name for Discharging
    0.054,                   !- Module Internal Electrical Resistance {{ohms}}
    100,                     !- Maximum Module Discharging Current {{A}}
    10,                      !- Module Cut-off Voltage {{V}}
    1,                       !- Module Charge Rate Limit
    Yes,                     !- Battery Life Calculation
    5,                       !- Number of Cycle Bins
    Doubleexponential;       !- Battery Life Curve Name
"""

    text, n = re.subn(
        r"(?ims)^\s*ElectricLoadCenter:Storage:Battery\s*,\s*\r?\n\s*Kibam\s*,.*?;",
        batt_repl,
        text,
        count=1,
    )
    if n != 1:
        raise RuntimeError("Could not patch ElectricLoadCenter:Storage:Battery")
    return text


def candidate_menu() -> list[dict]:
    return [
        {
            "name": "BASE_SOC95_20_P10",
            "max_soc": 0.95,
            "min_soc": 0.20,
            "initial_soc": 0.70,
            "modules_parallel": 10,
        },
        {
            "name": "DEEP_SOC90_10_P10",
            "max_soc": 0.90,
            "min_soc": 0.10,
            "initial_soc": 0.70,
            "modules_parallel": 10,
        },
        {
            "name": "SHALLOW_SOC80_40_P10",
            "max_soc": 0.80,
            "min_soc": 0.40,
            "initial_soc": 0.60,
            "modules_parallel": 10,
        },
        {
            "name": "BIGGER_PACK_P15",
            "max_soc": 0.95,
            "min_soc": 0.20,
            "initial_soc": 0.70,
            "modules_parallel": 15,
        },
        {
            "name": "SMALLER_PACK_P5",
            "max_soc": 0.95,
            "min_soc": 0.20,
            "initial_soc": 0.70,
            "modules_parallel": 5,
        },
    ]


def parse_purchased(run_dir: Path, candidate: str, runtime: float) -> lab.RunMetrics:
    """Prefer purchased electricity when present (behind-the-meter PV+BESS)."""
    csv_path = run_dir / "eplusout.csv"
    with csv_path.open(newline="", encoding="utf-8-sig") as handle:
        reader = csv.DictReader(handle)
        fieldnames = list(reader.fieldnames or [])
        purchased = None
        for prefix in (
            "ELECTRICITYPURCHASED:FACILITY",
            "ELECTRICITY:FACILITY",
        ):
            try:
                purchased = lab.find_column(fieldnames, prefix)
                break
            except RuntimeError:
                continue
        if purchased is None:
            raise RuntimeError("No electricity meter column found")
        rows = list(reader)

    kwh = 0.0
    peak = 0.0
    on_peak = 0.0
    for row in rows:
        joules = float(row[purchased] or 0.0)
        interval_kwh = joules / 3_600_000.0
        interval_kw = interval_kwh / lab.INTERVAL_HOURS
        kwh += interval_kwh
        peak = max(peak, interval_kw)
        match = re.search(r"\s(\d{1,2}):(\d{2}):", row.get("Date/Time", ""))
        if not match:
            continue
        hour = int(match.group(1))
        clock = 0 if hour == 24 else hour
        if lab.ON_PEAK_START_HOUR <= clock < lab.ON_PEAK_END_HOUR:
            on_peak = max(on_peak, interval_kw)

    severe, fatal = lab.count_err_markers(run_dir / "eplusout.err")
    energy = kwh * lab.ENERGY_RATE_USD_PER_KWH
    demand = on_peak * lab.ON_PEAK_DEMAND_RATE_USD_PER_KW
    return lab.RunMetrics(
        candidate=candidate,
        ready=severe == 0 and fatal == 0,
        min_ready_zone_f=-999.0,
        electricity_kwh=kwh,
        facility_peak_kw=peak,
        on_peak_peak_kw=on_peak,
        energy_cost_usd=energy,
        demand_cost_usd=demand,
        objective_usd=energy + demand,
        runtime_seconds=runtime,
        severe_errors=severe,
        fatal_errors=fatal,
        extra={"meter": purchased},
    )


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--output",
        type=Path,
        default=Path(__file__).resolve().parents[1] / "outputs" / "day10_bess",
    )
    args = parser.parse_args()

    source_path = lab.example_idf(SOURCE)
    source = source_path.read_text(encoding="utf-8", errors="replace")
    menu = candidate_menu()

    print("DAY 10 — BESS / PV + BATTERY GRID (BONUS)")
    print(f"Model: {SOURCE}")
    print("Vary SOC window + pack size; score purchased electricity + demand\n")

    results = []
    for index, cand in enumerate(menu, start=1):
        name = cand["name"]
        print(f"[{index}/{len(menu)}] {name}", end=" ", flush=True)
        text = patch_storage_bounds(
            source,
            max_soc=cand["max_soc"],
            min_soc=cand["min_soc"],
            initial_soc=cand["initial_soc"],
            modules_parallel=cand["modules_parallel"],
        )
        text = lab.set_single_run_period(
            text, begin_month=7, begin_day=15, name="BESS LESSON DAY"
        )
        # ShopWithPVandBattery autosizes terminals — keep zone/system sizing on.
        text = lab.ensure_weather_run(
            text, plant_sizing=False, sizing_periods=False
        )
        text = lab.append_outputs(text, lab.BESS_OUTPUTS)
        runtime = lab.run_energyplus(text, args.output / "runs" / name)
        metrics = parse_purchased(args.output / "runs" / name, name, runtime)
        metrics.extra = {**(metrics.extra or {}), **cand}
        results.append(metrics)
        print(
            f"purchased_kWh={metrics.electricity_kwh:.1f} "
            f"peak={metrics.facility_peak_kw:.1f} obj=${metrics.objective_usd:.2f}"
        )

    winner = lab.print_ranked(results)
    lab.write_results_csv(results, args.output / "grid_search_results.csv")
    lab.write_decision_json(
        args.output / "selected_plan.json",
        {
            "lesson": "day10",
            "model": SOURCE,
            "winner": None if winner is None else winner.candidate,
            "warning": "EDUCATIONAL BESS demo on stock ShopWithPVandBattery — no BACnet",
        },
    )


if __name__ == "__main__":
    main()

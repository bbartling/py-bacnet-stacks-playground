"""School 30-year deep-retrofit rehearsal — fictional Detroit K-12 school.

End-to-end ESCO rehearsal on clearly synthetic data (examples/school_30yr):

  1. validate the pseudo-actual 2025 bills through ``UtilityDataset``
  2. derive actual blended $/kWh and $/therm rates from those bills
  3. download (or reuse cached) Detroit 2025 hourly weather from the
     Open-Meteo archive via a validated ``WeatherRequest``
  4. build an annual AMY EPW (coverage_mode='annual': exactly 8,760 rows)
  5. run the ``school_30yr_hydronic`` and ``school_30yr_electrify`` measure
     sets through the real Docker easy button (baseline + progressive ECMs)
  6. area-scale incremental EnergyPlus fuel deltas from the ~5k ft2 prototype
     to the 100k ft2 school
  7. price each measure at the cost-registry p50 with the correct unit basis
     (building_ft2 vs glazing_ft2) and roll 30-year economics
  8. gate each capital plan against the benchmark guardrails
  9. apply a release guard that forces INVESTIGATE when G14 fails, any
     conceptual surrogate patch is present, a simulation is incomplete, or
     weather/bills provenance is missing

Run:  python scripts/school_30yr_rehearsal.py [--out ...] [--cache-dir ...]
Requires network (Open-Meteo) and Docker (energyplus-mcp-dev). Unit tests
inject ``opener`` and ``easy_button_runner`` so nothing live is touched.
"""

from __future__ import annotations

import argparse
import json
import math
import sys
from datetime import date, datetime, timezone
from pathlib import Path
from typing import Any, Callable

import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from wattlab.benchmarks.costs import lookup as cost_lookup  # noqa: E402
from wattlab.benchmarks.costs import scope_for_measure  # noqa: E402
from wattlab.benchmarks.guardrails import gate_capital_plan  # noqa: E402
from wattlab.benchmarks.meters import load_bill_csv  # noqa: E402
from wattlab.config import ARTIFACTS, weather_suitability  # noqa: E402
from wattlab.contracts import (  # noqa: E402
    RetrofitScenario,
    UtilityBillRecord,
    UtilityDataset,
    WeatherDatasetMeta,
    WeatherRequest,
)
from wattlab.crosscheck import g14_gates, prototype_area_scale  # noqa: E402
from wattlab.defaults import resolve_profile  # noqa: E402
from wattlab.finance import capital_plan, measure_economics  # noqa: E402
from wattlab.measures.measure_sets import (  # noqa: E402
    expand_measure_set,
    list_measure_sets,
    load_measure_sets,
)
from wattlab.weather.epw import (  # noqa: E402
    build_amy_epw,
    utc_frame_to_local_standard,
)
from wattlab.weather.open_meteo import download_archive_weather  # noqa: E402

PRODUCT = "OpenFDD WattLab"
SCRIPT = "school_30yr_rehearsal"

CAMPUS_JSON = ROOT / "examples" / "school_30yr" / "campus.json"

DETROIT_LAT = 42.33
DETROIT_LON = -83.05
# EPW rows are local standard time year-round: Eastern Standard Time (UTC-5).
DETROIT_TZ_HOURS = -5.0
WEATHER_YEAR = 2025

FLOOR_AREA_FT2 = 100_000.0
FLOORS = 2
WWR = 0.25
FLOOR_TO_FLOOR_FT = 13.0
ANALYSIS_YEARS = 30

MEASURE_SETS = ("school_30yr_hydronic", "school_30yr_electrify")

KBTU_PER_KWH = 3.412
KBTU_PER_THERM = 100.0

# Quality flags that mark an uncalibrated screening run in general, not a
# conceptual equipment/envelope surrogate patch — these do not trip the guard.
_GENERIC_CONCEPTUAL_FLAGS = frozenset({"conceptual_screening"})

_VALID_BILL_PROVENANCE = frozenset({"actual", "synthetic_rehearsal"})


# ---------------------------------------------------------------------------
# Bills: UtilityDataset validation + blended rates + summary
# ---------------------------------------------------------------------------


def load_school_bills(campus_path: Path | str = CAMPUS_JSON) -> dict[str, Any]:
    """Load campus.json + bill CSVs and validate through UtilityDataset.

    Returns ``{"campus", "provenance", "floor_area_ft2", "datasets"}`` where
    datasets maps fuel -> validated :class:`UtilityDataset`.
    """
    campus_path = Path(campus_path)
    doc = json.loads(campus_path.read_text(encoding="utf-8"))
    provenance = doc.get("provenance")
    if provenance not in _VALID_BILL_PROVENANCE:
        raise ValueError(
            f"campus.json must declare provenance in "
            f"{sorted(_VALID_BILL_PROVENANCE)} (got {provenance!r})"
        )
    buildings = doc.get("buildings") or []
    if len(buildings) != 1:
        raise ValueError("school_30yr rehearsal expects exactly one building")
    floor_area_ft2 = float(buildings[0]["floor_area_ft2"])

    datasets: dict[str, UtilityDataset] = {}
    for meter in doc.get("meters") or []:
        fuel = str(meter["fuel"])
        unit = str(meter["unit"])
        frame = load_bill_csv(campus_path.parent / meter["file"])
        bills = []
        for row in frame.to_dict(orient="records"):
            demand = row.get("demand_kw")
            bills.append(
                UtilityBillRecord(
                    month=str(row["month"]),
                    fuel=fuel,
                    unit=unit,
                    usage=float(row["usage"]),
                    cost_usd=float(row["cost_usd"]),
                    demand_kw=(
                        float(demand)
                        if demand is not None and pd.notna(demand)
                        else None
                    ),
                )
            )
        datasets[fuel] = UtilityDataset(
            bills=bills,
            floor_area_sqft=floor_area_ft2,
            provenance=provenance,
        )
    if set(datasets) != {"electricity", "gas"}:
        raise ValueError(
            f"expected one electricity and one gas meter (got {sorted(datasets)})"
        )
    if datasets["gas"].bills[0].unit != "therm":
        raise ValueError("school_30yr gas bills must be in therms")
    return {
        "campus": doc,
        "provenance": provenance,
        "floor_area_ft2": floor_area_ft2,
        "datasets": datasets,
    }


def blended_rates(datasets: dict[str, UtilityDataset]) -> dict[str, float]:
    """Actual blended rates from the bills: total cost / total usage."""
    elec = datasets["electricity"]
    gas = datasets["gas"]
    elec_kwh = sum(b.usage for b in elec.bills)
    gas_therms = sum(b.usage for b in gas.bills)
    if elec_kwh <= 0 or gas_therms <= 0:
        raise ValueError("bills must have positive annual usage for both fuels")
    return {
        "elec_usd_per_kwh": round(
            sum(b.cost_usd or 0.0 for b in elec.bills) / elec_kwh, 4
        ),
        "gas_usd_per_therm": round(
            sum(b.cost_usd or 0.0 for b in gas.bills) / gas_therms, 4
        ),
    }


def bills_summary(
    datasets: dict[str, UtilityDataset], floor_area_ft2: float
) -> dict[str, Any]:
    elec = sorted(datasets["electricity"].bills, key=lambda b: b.month)
    gas = sorted(datasets["gas"].bills, key=lambda b: b.month)
    annual_kwh = sum(b.usage for b in elec)
    annual_therms = sum(b.usage for b in gas)
    eui = (
        annual_kwh * KBTU_PER_KWH + annual_therms * KBTU_PER_THERM
    ) / floor_area_ft2
    return {
        "window": {"start": elec[0].month, "end": elec[-1].month, "months": 12},
        "annual_kwh": round(annual_kwh, 1),
        "annual_therms": round(annual_therms, 1),
        "elec_cost_usd": round(sum(b.cost_usd or 0.0 for b in elec), 2),
        "gas_cost_usd": round(sum(b.cost_usd or 0.0 for b in gas), 2),
        "peak_demand_kw": max((b.demand_kw or 0.0) for b in elec),
        "site_eui_kbtu_ft2": round(eui, 1),
        "monthly_kwh": [b.usage for b in elec],
        "monthly_therms": [b.usage for b in gas],
    }


# ---------------------------------------------------------------------------
# Weather: Open-Meteo Detroit 2025 -> annual AMY EPW
# ---------------------------------------------------------------------------


def fetch_detroit_weather(
    cache_dir: Path,
    year: int = WEATHER_YEAR,
    opener: Callable[[str], bytes] | None = None,
) -> tuple[pd.DataFrame, WeatherDatasetMeta]:
    request = WeatherRequest(
        latitude=DETROIT_LAT,
        longitude=DETROIT_LON,
        start_date=date(year, 1, 1),
        end_date=date(year, 12, 31),
    )
    return download_archive_weather(request, Path(cache_dir), opener=opener)


def build_school_epw(
    df: pd.DataFrame, meta: WeatherDatasetMeta, out_path: Path
) -> dict[str, Any]:
    """Annual AMY EPW in Detroit local standard time (UTC rows shifted)."""
    local = utc_frame_to_local_standard(df, tz_hours=DETROIT_TZ_HOURS)
    return build_amy_epw(
        local,
        out_path,
        lat=meta.latitude,
        lon=meta.longitude,
        elevation_m=190.0,
        location_name=f"Detroit_MI_School_AMY_{meta.start_date.year}",
        coverage_mode="annual",
        tz_hours=DETROIT_TZ_HOURS,
    )


def amy_epw_note(meta: WeatherDatasetMeta) -> str:
    return (
        "Actual Meteorological Year EPW built from Open-Meteo archive hourly "
        f"weather for Detroit, MI, {meta.start_date.year} "
        f"(source={meta.source}, sha256={meta.sha256[:12]}..., rows={meta.rows})."
    )


# ---------------------------------------------------------------------------
# Profile + scenario contracts
# ---------------------------------------------------------------------------


def build_school_profile(
    measure_set: str,
    *,
    epw_path: Path | str,
    epw_note: str,
    rates: dict[str, float],
) -> dict[str, Any]:
    profile = resolve_profile(
        {
            "building_type": "school",
            "city": "detroit",
            "floor_area_ft2": FLOOR_AREA_FT2,
            "floors": FLOORS,
            "wwr": WWR,
            "floor_to_floor_ft": FLOOR_TO_FLOOR_FT,
            "utility": {
                "elec_usd_per_kwh": rates["elec_usd_per_kwh"],
                "gas_usd_per_therm": rates["gas_usd_per_therm"],
            },
            "project_id": "WATTLAB-SCHOOL-30YR",
            "display_name": "Fictional Detroit K-12 School (30-yr rehearsal)",
            "measure_set": measure_set,
        }
    )
    profile["energyplus"]["epw"] = str(epw_path)
    profile["energyplus"]["epw_note"] = epw_note
    return profile


def scenario_contract(measure_set: str) -> RetrofitScenario:
    measures = expand_measure_set(measure_set)
    kind = "electrification" if "electrify" in measure_set else "hydronic_renewal"
    return RetrofitScenario(
        name=measure_set,
        measure_ids=[m["measure_id"] for m in measures],
        scenario_kind=kind,
        analysis_years=ANALYSIS_YEARS,
        # Both bundles include explicit conceptual surrogates (simple-glazing
        # envelope proxy; AWHP-as-electric-boiler for electrify).
        conceptual_surrogate=True,
    )


def estimate_glazing_area_ft2(
    floor_area_ft2: float = FLOOR_AREA_FT2,
    floors: int = FLOORS,
    wwr: float = WWR,
    floor_to_floor_ft: float = FLOOR_TO_FLOOR_FT,
) -> float:
    """Glazing area from a square-footprint massing assumption.

    footprint = floor_area / floors; gross wall = perimeter x total height;
    glazing = gross wall x WWR. A stated assumption, not a takeoff.
    """
    footprint_ft2 = floor_area_ft2 / floors
    side_ft = math.sqrt(footprint_ft2)
    gross_wall_ft2 = 4.0 * side_ft * (floors * floor_to_floor_ft)
    return gross_wall_ft2 * wwr


# ---------------------------------------------------------------------------
# Costs, area scaling, 30-year economics
# ---------------------------------------------------------------------------


def measure_cost_usd(
    measure_id: str,
    *,
    floor_area_ft2: float,
    glazing_area_ft2: float,
) -> dict[str, Any]:
    """Registry-p50 implementation cost with the scope's own unit basis."""
    scope = scope_for_measure(measure_id)
    ref = cost_lookup(scope)
    if ref is None:
        raise ValueError(f"no cost registry entry for scope {scope!r}")
    basis = ref.get("unit_basis") or "building_ft2"
    denom = glazing_area_ft2 if basis == "glazing_ft2" else floor_area_ft2
    p50 = float(ref["p50"])
    catalog = (load_measure_sets().get("catalog") or {}).get(measure_id) or {}
    package_share = (
        float(catalog["major_hvac_package_share"])
        if scope == "major_hvac" and "major_hvac_package_share" in catalog
        else None
    )
    if scope == "major_hvac" and package_share is None:
        raise ValueError(
            f"major-HVAC measure {measure_id!r} must declare "
            "major_hvac_package_share"
        )
    cost_multiplier = package_share if package_share is not None else 1.0
    return {
        "measure_id": measure_id,
        "scope": scope,
        "package_share": package_share,
        "unit_basis": basis,
        "usd_per_unit_p50": p50,
        "basis_area_ft2": round(float(denom), 1),
        "cost_usd": cost_multiplier * p50 * float(denom),
        "currency_year": ref.get("currency_year"),
        "confidence": ref.get("confidence"),
        "source": ref.get("source"),
    }


def area_scale_from_report(
    report: dict[str, Any], floor_area_ft2: float
) -> float | None:
    records = report.get("result_records") or []
    if not records:
        return None
    model_area_m2 = (records[0].get("annual") or {}).get("building_area_m2")
    return prototype_area_scale(
        target_ft2=floor_area_ft2, model_area_m2=model_area_m2
    )


def scaled_measure_deltas(
    report: dict[str, Any], floor_area_ft2: float
) -> list[dict[str, Any]]:
    """Incremental (vs previous step) E+ fuel deltas, scaled to the school."""
    scale = area_scale_from_report(report, floor_area_ft2)
    if scale is None:
        raise ValueError(
            "cannot area-scale: baseline record lacks building_area_m2"
        )
    out: list[dict[str, Any]] = []
    for row in report.get("savings_by_measure") or []:
        mid = row.get("measure_id")
        if not mid or mid == "baseline":
            continue
        vs_prev = row.get("vs_previous") or {}
        kwh = float(vs_prev.get("kwh_saved") or 0.0)
        therms = float(vs_prev.get("therms_saved") or 0.0)
        out.append(
            {
                "measure_id": mid,
                "kwh_saved": kwh,
                "therms_saved": therms,
                "kwh_saved_scaled": round(kwh * scale, 1),
                "therms_saved_scaled": round(therms * scale, 1),
                "area_scale": round(scale, 4),
            }
        )
    return out


def thirty_year_plan(
    deltas: list[dict[str, Any]],
    *,
    rates: dict[str, float],
    floor_area_ft2: float,
    glazing_area_ft2: float,
) -> dict[str, Any]:
    """30-year capital plan from scaled deltas + registry-p50 costs.

    ``capital_plan`` sorts its ``measures`` table by simple payback for review.
    ``application_order`` preserves the progressive EnergyPlus sequence so the
    two orders cannot be mistaken for one another.
    """
    application_order = [str(d["measure_id"]) for d in deltas]
    rows: list[dict[str, Any]] = []
    for d in deltas:
        cost = measure_cost_usd(
            d["measure_id"],
            floor_area_ft2=floor_area_ft2,
            glazing_area_ft2=glazing_area_ft2,
        )
        row = measure_economics(
            measure_id=d["measure_id"],
            implementation_cost_usd=cost["cost_usd"],
            kwh_saved=float(d.get("kwh_saved_scaled") or 0.0),
            therms_saved=float(d.get("therms_saved_scaled") or 0.0),
            elec_rate_usd_per_kwh=rates["elec_usd_per_kwh"],
            gas_rate_usd_per_therm=rates["gas_usd_per_therm"],
            measure_life_years=ANALYSIS_YEARS,
        )
        row["cost_basis"] = cost
        rows.append(row)
    plan = capital_plan(rows)
    plan["application_order"] = application_order
    plan["plan_sort"] = "simple_payback_years"
    plan["order_note"] = (
        "measures are sorted by simple payback for capital-plan review; "
        "application_order preserves the progressive EnergyPlus application order"
    )
    return plan


def gate_plan(
    plan: dict[str, Any],
    *,
    bills: dict[str, Any],
    floor_area_ft2: float,
    glazing_area_ft2: float,
) -> dict[str, Any]:
    return gate_capital_plan(
        plan,
        property_type="k12_school",
        floor_area_ft2=floor_area_ft2,
        baseline_kwh=bills["annual_kwh"],
        baseline_therms=bills["annual_therms"],
        site_eui_kbtu_ft2=bills["site_eui_kbtu_ft2"],
        glazing_area_ft2=glazing_area_ft2,
    )


# ---------------------------------------------------------------------------
# G14 + release guard
# ---------------------------------------------------------------------------


def baseline_g14(
    report: dict[str, Any],
    monthly_kwh_bills: list[float],
    monthly_therm_bills: list[float],
    floor_area_ft2: float,
) -> dict[str, Any] | None:
    """Dual-fuel G14 gates: bills vs area-scaled baseline electricity and gas."""
    records = report.get("result_records") or []
    if not records:
        return None
    scale = area_scale_from_report(report, floor_area_ft2)
    monthly = records[0].get("monthly") or []

    def fuel_gate(
        fuel: str, bills: list[float], model_field: str
    ) -> dict[str, Any]:
        if len(bills) != 12:
            return {
                "calibrated": False,
                "error": f"expected 12 monthly {fuel} bills (got {len(bills)})",
            }
        if len(monthly) != 12:
            return {
                "calibrated": False,
                "error": f"expected 12 modeled {fuel} months (got {len(monthly)})",
            }
        missing = [
            int(row.get("month") or index)
            for index, row in enumerate(monthly, start=1)
            if row.get(model_field) is None
        ]
        if missing:
            return {
                "calibrated": False,
                "error": f"modeled {fuel} missing for months: {missing}",
            }
        if scale is None:
            return {
                "calibrated": False,
                "error": f"cannot area-scale modeled {fuel}: building area missing",
            }
        modeled = [float(row[model_field]) * scale for row in monthly]
        gates = g14_gates([float(v) for v in bills], modeled)
        gates["area_scale_applied"] = round(scale, 4)
        return gates

    electricity = fuel_gate(
        "electricity", monthly_kwh_bills, "electricity_kwh"
    )
    natural_gas = fuel_gate(
        "natural gas", monthly_therm_bills, "natural_gas_therm"
    )
    errors = [
        f"{fuel}: {gate['error']}"
        for fuel, gate in (
            ("electricity", electricity),
            ("natural_gas", natural_gas),
        )
        if gate.get("error")
    ]
    return {
        "calibrated": bool(
            electricity.get("calibrated") and natural_gas.get("calibrated")
        ),
        "electricity": electricity,
        "natural_gas": natural_gas,
        "errors": errors,
        "area_scale_applied": round(scale, 4) if scale is not None else None,
    }


def release_guard(
    *,
    scenario: RetrofitScenario,
    g14: dict[str, Any] | None,
    result_records: list[dict[str, Any]],
    weather: dict[str, Any] | None,
    bills_provenance: str | None,
) -> dict[str, Any]:
    """Fail-closed publication gate for a rehearsal scenario.

    Forces INVESTIGATE when G14 fails (or was never computed), any conceptual
    surrogate patch is present, any simulation is incomplete, or weather /
    bills provenance is missing.
    """
    reasons: list[str] = []

    dual_fuel_calibrated = bool(
        g14
        and g14.get("calibrated")
        and (g14.get("electricity") or {}).get("calibrated")
        and (g14.get("natural_gas") or {}).get("calibrated")
    )
    if not dual_fuel_calibrated:
        reasons.append(
            "dual-fuel G14 gate failed or unavailable: baseline electricity "
            "and natural gas must both pass monthly NMBE +/-5% and "
            "CV(RMSE) <=15%."
        )

    if scenario.conceptual_surrogate:
        reasons.append(
            "scenario declares conceptual_surrogate=true "
            "(not construction-ready)."
        )

    surrogate_flags = sorted(
        {
            flag
            for rec in result_records or []
            for flag in rec.get("quality_flags") or []
            if flag.startswith("conceptual_")
            and flag not in _GENERIC_CONCEPTUAL_FLAGS
        }
    )
    if surrogate_flags:
        reasons.append(
            "conceptual surrogate patches present (not construction-ready): "
            + ", ".join(surrogate_flags)
        )

    if not result_records:
        reasons.append("simulation records missing: no EnergyPlus runs found.")
    else:
        incomplete = [
            str(rec.get("measure_id") or "baseline")
            for rec in result_records
            if rec.get("status") != "COMPLETE"
        ]
        if incomplete:
            reasons.append(
                "simulation incomplete for: " + ", ".join(incomplete)
            )

    sha = (weather or {}).get("sha256") or ""
    if not (weather or {}).get("source") or len(str(sha)) != 64:
        reasons.append(
            "weather provenance missing: need source + sha256 of the "
            "downloaded dataset."
        )

    if bills_provenance not in _VALID_BILL_PROVENANCE:
        reasons.append(
            "bills provenance missing or unknown: expected 'actual' or "
            f"'synthetic_rehearsal' (got {bills_provenance!r})."
        )

    return {
        "verdict": "INVESTIGATE" if reasons else "PUBLISH",
        "reasons": reasons,
    }


def comparison_rollup(
    scenarios: dict[str, dict[str, Any]],
    scenario_order: tuple[str, ...] | list[str],
) -> dict[str, Any]:
    """Comparable hydronic/electrify annual savings and capital outcomes."""
    rows: list[dict[str, Any]] = []
    ordered = [sid for sid in scenario_order if sid in scenarios]
    for sid in ordered:
        block = scenarios[sid]
        deltas = block.get("scaled_deltas") or []
        totals = (block.get("capital_plan") or {}).get("totals") or {}
        rows.append(
            {
                "scenario": sid,
                "annual_kwh_saved": round(
                    sum(float(d.get("kwh_saved_scaled") or 0.0) for d in deltas), 1
                ),
                "annual_therms_saved": round(
                    sum(
                        float(d.get("therms_saved_scaled") or 0.0)
                        for d in deltas
                    ),
                    1,
                ),
                "annual_cost_saved_usd": totals.get("annual_cost_saved_usd"),
                "implementation_cost_usd": totals.get("implementation_cost_usd"),
                "npv_usd": totals.get("npv_usd"),
                "release_verdict": (block.get("release") or {}).get("verdict"),
            }
        )
    return {"scenario_order": ordered, "scenarios": rows}


# ---------------------------------------------------------------------------
# Orchestration
# ---------------------------------------------------------------------------


def run_rehearsal(
    *,
    cache_dir: Path | str | None = None,
    out_path: Path | str | None = None,
    opener: Callable[[str], bytes] | None = None,
    easy_button_runner: Callable[..., dict[str, Any]] | None = None,
    measure_sets: tuple[str, ...] = MEASURE_SETS,
    campus_path: Path | str = CAMPUS_JSON,
    year: int = WEATHER_YEAR,
) -> dict[str, Any]:
    cache_dir = Path(cache_dir) if cache_dir else ARTIFACTS / "school_30yr_cache"
    out_path = (
        Path(out_path) if out_path else ARTIFACTS / "school_30yr_rehearsal.json"
    )
    if easy_button_runner is None:
        from wattlab.easy_button import run_easy_button as easy_button_runner

    # 1-2) bills + blended rates
    loaded = load_school_bills(campus_path)
    datasets = loaded["datasets"]
    floor_area_ft2 = loaded["floor_area_ft2"]
    rates = blended_rates(datasets)
    bills = bills_summary(datasets, floor_area_ft2)
    print(
        f"[bills] {bills['annual_kwh']:,.0f} kWh + {bills['annual_therms']:,.0f} "
        f"therms ({loaded['provenance']}); blended "
        f"${rates['elec_usd_per_kwh']}/kWh, ${rates['gas_usd_per_therm']}/therm; "
        f"EUI {bills['site_eui_kbtu_ft2']} kBtu/ft2"
    )

    # 3-4) actual-year weather + annual EPW
    df, meta = fetch_detroit_weather(cache_dir, year=year, opener=opener)
    epw_path = cache_dir / f"detroit_{year}_school_amy.epw"
    epw_meta = build_school_epw(df, meta, epw_path)
    note = amy_epw_note(meta)
    wx = weather_suitability(source="amy", epw_path=epw_path, epw_note=note)
    print(
        f"[weather] {meta.rows} rows sha256={meta.sha256[:12]}... "
        f"cache={meta.cached_path} -> EPW {epw_meta['rows']} rows "
        f"({wx['mode']})"
    )

    glazing_area_ft2 = estimate_glazing_area_ft2(
        floor_area_ft2, FLOORS, WWR, FLOOR_TO_FLOOR_FT
    )

    # 5-9) per-scenario simulate, scale, price, gate, guard
    scenarios: dict[str, Any] = {}
    for set_id in measure_sets:
        scenario = scenario_contract(set_id)
        profile = build_school_profile(
            set_id, epw_path=epw_path, epw_note=note, rates=rates
        )
        print(f"[simulate] {set_id}: {len(scenario.measure_ids)} measures ...")
        report = easy_button_runner(profile=profile, measure_set=set_id)
        records = report.get("result_records") or []
        statuses = {
            str(r.get("measure_id") or "baseline"): r.get("status")
            for r in records
        }
        deltas = scaled_measure_deltas(report, floor_area_ft2)
        plan = thirty_year_plan(
            deltas,
            rates=rates,
            floor_area_ft2=floor_area_ft2,
            glazing_area_ft2=glazing_area_ft2,
        )
        gate = gate_plan(
            plan,
            bills=bills,
            floor_area_ft2=floor_area_ft2,
            glazing_area_ft2=glazing_area_ft2,
        )
        g14 = baseline_g14(
            report,
            bills["monthly_kwh"],
            bills["monthly_therms"],
            floor_area_ft2,
        )
        release = release_guard(
            scenario=scenario,
            g14=g14,
            result_records=records,
            weather={"sha256": meta.sha256, "source": meta.source},
            bills_provenance=loaded["provenance"],
        )
        totals = plan["totals"]
        print(
            f"[{set_id}] cost ${totals['implementation_cost_usd']:,.0f}, "
            f"saves ${totals['annual_cost_saved_usd']:,.0f}/yr, "
            f"30-yr NPV ${totals['npv_usd']:,.0f}; gate={gate['verdict']} "
            f"release={release['verdict']}"
        )
        scenarios[set_id] = {
            "scenario": scenario.model_dump(),
            "measure_set": set_id,
            "artifacts_dir": report.get("artifacts_dir"),
            "result_records": records,
            "result_statuses": statuses,
            "savings_by_measure": report.get("savings_by_measure"),
            "scaled_deltas": deltas,
            "capital_plan": plan,
            "gate": gate,
            "g14": g14,
            "release": release,
        }

    overall = (
        "PUBLISH"
        if scenarios
        and all(s["release"]["verdict"] == "PUBLISH" for s in scenarios.values())
        else "INVESTIGATE"
    )
    simulations_complete = all(
        status == "COMPLETE"
        for block in scenarios.values()
        for status in block["result_statuses"].values()
    )
    execution_outcome = (
        "SIMULATION_COMPLETE" if simulations_complete else "SIMULATION_FAILED"
    )
    result: dict[str, Any] = {
        "product": PRODUCT,
        "script": SCRIPT,
        "execution_outcome": execution_outcome,
        "generated_at_utc": datetime.now(timezone.utc).strftime(
            "%Y-%m-%dT%H:%M:%SZ"
        ),
        "inputs": {
            "campus": loaded["campus"],
            "building": {
                "floor_area_ft2": floor_area_ft2,
                "floors": FLOORS,
                "wwr": WWR,
                "glazing_area_ft2": round(glazing_area_ft2, 1),
                "glazing_area_assumption": (
                    "square footprint massing: 4 x sqrt(floor_area/floors) x "
                    "floors x floor_to_floor x WWR"
                ),
            },
            "analysis_years": ANALYSIS_YEARS,
            "rates": rates,
            "provenance": {
                "bills": loaded["provenance"],
                "weather_source": meta.source,
            },
        },
        "weather": {
            "sha256": meta.sha256,
            "cached_path": meta.cached_path,
            "meta": meta.model_dump(mode="json"),
            "epw": epw_meta,
            "suitability": wx,
        },
        "bills": bills,
        "scenarios": scenarios,
        "comparison": comparison_rollup(scenarios, measure_sets),
        "release": {
            "verdict": overall,
            "scenarios": {k: v["release"]["verdict"] for k, v in scenarios.items()},
        },
    }
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(json.dumps(result, indent=2), encoding="utf-8")
    print(
        f"[done] execution={execution_outcome}; review_status={overall}; "
        f"INVESTIGATE is a review status, not a runtime failure; report: {out_path}"
    )
    return result


def main(argv: list[str] | None = None) -> int:
    set_ids = [s["id"] for s in list_measure_sets()]
    p = argparse.ArgumentParser(
        description="School 30-year deep-retrofit rehearsal (Open-Meteo + Docker)"
    )
    p.add_argument(
        "--out",
        type=Path,
        default=None,
        help="Output JSON path (default .artifacts/school_30yr_rehearsal.json)",
    )
    p.add_argument(
        "--cache-dir",
        type=Path,
        default=None,
        help="Weather cache directory (default .artifacts/school_30yr_cache)",
    )
    p.add_argument(
        "--measure-set",
        action="append",
        choices=set_ids,
        default=None,
        help="Measure set(s) to run (repeatable; default both school_30yr sets)",
    )
    p.add_argument("--year", type=int, default=WEATHER_YEAR)
    args = p.parse_args(argv)

    result = run_rehearsal(
        cache_dir=args.cache_dir,
        out_path=args.out,
        measure_sets=tuple(args.measure_set or MEASURE_SETS),
        year=args.year,
    )
    return 0 if result["execution_outcome"] == "SIMULATION_COMPLETE" else 1


if __name__ == "__main__":
    raise SystemExit(main())

"""Load studio demo day traces and illustrative grid rankings."""
from __future__ import annotations

import json
from functools import lru_cache
from typing import Any

from ..battery import BatteryParams, simulate_dispatch
from ..residential.constants import DT_HOURS, INTERVALS_PER_DAY
from ..residential.experiment import default_thermostat_candidates
from ..residential.model import MODEL_IDF, PACKAGE_ROOT
from ..residential.tariffs import summer_tou_hourly
from ..tariff import BillingState, billing_cost

FIXTURES = PACKAGE_ROOT / "fixtures" / "studio"
SUMMER_DR_DAY = FIXTURES / "summer_dr_day.json"


@lru_cache(maxsize=4)
def load_summer_dr_day() -> dict[str, Any]:
    payload = json.loads(SUMMER_DR_DAY.read_text(encoding="utf-8"))
    if int(payload.get("intervals", 0)) != INTERVALS_PER_DAY:
        raise ValueError("studio summer_dr_day fixture interval count mismatch")
    return payload


# Demo IDF floor plate (~59×59×10 ft single zone) — used for intensity captions.
DEMO_FLOOR_M2 = 325.08
DEMO_FLOOR_FT2 = DEMO_FLOOR_M2 * 10.7639


def f_to_c(temp_f: float) -> float:
    return (float(temp_f) - 32.0) * 5.0 / 9.0


def interval_kwh(kw: list[float], *, dt_hours: float = DT_HOURS) -> list[float]:
    """Convert average-interval kW to interval energy: kWh_i = kW_i × Δt_h."""
    return [float(v) * float(dt_hours) for v in kw]


def cumulative_kwh(kw: list[float], *, dt_hours: float = DT_HOURS) -> list[float]:
    total = 0.0
    out: list[float] = []
    for value in kw:
        total += float(value) * float(dt_hours)
        out.append(total)
    return out


def daily_kwh(kw: list[float], *, dt_hours: float = DT_HOURS) -> float:
    """Full-day facility energy from 5-min average kW (288 × 1/12 h)."""
    return float(sum(float(v) * float(dt_hours) for v in kw))


def energy_intensity_kwh_per_ft2(kwh: float, *, floor_ft2: float = DEMO_FLOOR_FT2) -> float:
    if floor_ft2 <= 0:
        raise ValueError("floor_ft2 must be positive")
    return float(kwh) / float(floor_ft2)


def hourly_kwh(kw: list[float], *, dt_hours: float = DT_HOURS) -> list[float]:
    """Collapse 5-min kW into 24 hourly kWh totals."""
    n = len(kw)
    if n % 24 != 0:
        raise ValueError("series length must be divisible by 24")
    step = n // 24
    return [sum(float(kw[h * step + i]) * dt_hours for i in range(step)) for h in range(24)]


def hourly_cost(
    kw: list[float],
    rates: tuple[float, ...] | list[float],
    *,
    dt_hours: float = DT_HOURS,
) -> list[float]:
    n = len(kw)
    if n != len(rates):
        raise ValueError("kw and rates length mismatch")
    if n % 24 != 0:
        raise ValueError("series length must be divisible by 24")
    step = n // 24
    out: list[float] = []
    for h in range(24):
        total = 0.0
        for i in range(step):
            idx = h * step + i
            total += float(kw[idx]) * dt_hours * float(rates[idx])
        out.append(total)
    return out


def load_outdoor_day(*, season: str) -> dict[str, Any]:
    name = "winter_outdoor_jan15.json" if season == "winter" else "summer_outdoor_jul15.json"
    path = FIXTURES / name
    return json.loads(path.read_text(encoding="utf-8"))


@lru_cache(maxsize=4)
def load_season_day(season: str = "summer") -> dict[str, Any]:
    key = season.strip().lower()
    if key in {"winter", "jan", "january"}:
        path = FIXTURES / "winter_dr_day.json"
        if path.is_file():
            payload = json.loads(path.read_text(encoding="utf-8"))
            if int(payload.get("intervals", 0)) != INTERVALS_PER_DAY:
                raise ValueError("studio winter_dr_day fixture interval count mismatch")
            return payload
    return load_summer_dr_day()


def cumulative_energy_cost(
    kw: list[float],
    rates: tuple[float, ...],
    *,
    dt_hours: float = DT_HOURS,
) -> list[float]:
    total = 0.0
    out: list[float] = []
    for i, value in enumerate(kw):
        total += float(value) * dt_hours * float(rates[i])
        out.append(total)
    return out


def _tariff_for_season(season: str):
    if season in {"winter", "jan", "january"}:
        from ..residential.tariffs import winter_tou_hourly

        return winter_tou_hourly()
    return summer_tou_hourly()


def day_bill(kw: list[float], *, season: str = "summer") -> float:
    tariff = _tariff_for_season(season)
    return float(billing_cost(kw, tariff=tariff, opening_state=BillingState())["total_cost_usd"])


def run_battery_on_load(
    facility_kw: list[float],
    *,
    capacity_kwh: float,
    max_power_kw: float,
    eta: float = 0.95,
    soc_min: float = 0.1,
    soc_max: float = 0.95,
    initial_soc: float = 0.5,
    season: str = "summer",
) -> dict[str, Any]:
    tariff = _tariff_for_season(season)
    params = BatteryParams(
        capacity_kwh=float(capacity_kwh),
        max_charge_kw=float(max_power_kw),
        max_discharge_kw=float(max_power_kw),
        eta_c=float(eta),
        eta_d=float(eta),
        soc_min=float(soc_min),
        soc_max=float(soc_max),
        initial_soc=float(initial_soc),
    )
    dispatch = simulate_dispatch(
        facility_kw,
        list(tariff.energy_rates_per_kwh),
        params,
        mode="price_arbitrage",
    )
    purchased = list(dispatch["purchased_kw"])  # type: ignore[arg-type]
    bill = billing_cost(purchased, tariff=tariff, opening_state=BillingState())
    house_kwh = daily_kwh(facility_kw)
    purchased_kwh = daily_kwh(purchased)
    return {
        **dispatch,
        "params": params.to_dict(),
        "billing_cost": float(bill["total_cost_usd"]),
        "baseline_billing_cost": day_bill(facility_kw, season=season),
        "house_kwh": house_kwh,
        "purchased_kwh": purchased_kwh,
        "energy_kwh_bill": float(bill["energy_kwh"]),
        "rates": list(tariff.energy_rates_per_kwh),
    }


def illustrative_grid_ranking(*, season: str = "summer") -> dict[str, Any]:
    """Build an educational ranking board from the DR fixture + candidate catalog.

    Real EnergyPlus grid search is available from the Streamlit 'Run live E+' button.
    This board uses the published Jul-15 baseline/event traces plus battery variants
    so the UI works without a local EnergyPlus install.
    """
    day = load_summer_dr_day()
    baseline_kw = list(day["baseline_kw"])
    event_kw = list(day["event_kw"])
    base_cost = day_bill(baseline_kw, season=season)
    event_cost = day_bill(event_kw, season=season)
    batt = run_battery_on_load(baseline_kw, capacity_kwh=13.5, max_power_kw=5.0, season=season)
    comb = run_battery_on_load(event_kw, capacity_kwh=13.5, max_power_kw=5.0, season=season)

    candidates = list(default_thermostat_candidates(season="summer"))[:6]
    rows: list[dict[str, Any]] = [
        {
            "rank": 1,
            "candidate_id": "COMBINED_EVENT_BESS",
            "stage": "thermal+battery",
            "billing_cost": comb["billing_cost"],
            "delta_vs_baseline": comb["billing_cost"] - base_cost,
            "note": "DR event house load + 13.5 kWh / 5 kW battery",
        },
        {
            "rank": 2,
            "candidate_id": "BATTERY_ONLY_BASELINE",
            "stage": "battery",
            "billing_cost": batt["billing_cost"],
            "delta_vs_baseline": batt["billing_cost"] - base_cost,
            "note": "Baseline thermostat + battery price arbitrage",
        },
        {
            "rank": 3,
            "candidate_id": "THERMAL_DR_EVENT",
            "stage": "thermal",
            "billing_cost": event_cost,
            "delta_vs_baseline": event_cost - base_cost,
            "note": "Published summer DR precool / shed / recover schedule",
        },
        {
            "rank": 4,
            "candidate_id": "BASELINE",
            "stage": "baseline",
            "billing_cost": base_cost,
            "delta_vs_baseline": 0.0,
            "note": "Fixed 71.5 / 72.5 °F dual setpoint",
        },
    ]
    # Catalog leftovers (not simulated here) so the grid UI shows the search space.
    for cand in candidates:
        rows.append(
            {
                "rank": 0,
                "candidate_id": cand.candidate_id,
                "stage": "enumerated",
                "billing_cost": None,
                "delta_vs_baseline": None,
                "note": json.dumps(dict(cand.action), sort_keys=True),
            }
        )
    scored = [r for r in rows if r["billing_cost"] is not None]
    scored.sort(key=lambda r: float(r["billing_cost"]))
    for i, row in enumerate(scored, start=1):
        row["rank"] = i
    unscored = [r for r in rows if r["billing_cost"] is None]
    for j, row in enumerate(unscored, start=len(scored) + 1):
        row["rank"] = j
    ordered = scored + unscored
    return {
        "schema": "vibe23.studio_grid_board.v1",
        "claim_tariff": "ILLUSTRATIVE_HIGH_VALUE_TOU_TARIFF",
        "claim_model": "HYPOTHETICAL_GL14_TUNED_DEMO_MODEL",
        "source": "fixtures/studio/summer_dr_day.json + battery dispatch",
        "winner": scored[0] if scored else None,
        "rows": ordered,
        "catalog_size": len(candidates),
        "model_idf": str(MODEL_IDF),
    }


def interval_clock(step: int, *, intervals: int = INTERVALS_PER_DAY) -> str:
    minutes = int(round(step * (24 * 60 / intervals)))
    minutes = min(max(minutes, 0), 24 * 60 - 1)
    return f"{minutes // 60:02d}:{minutes % 60:02d}"


# DSM playback levels (native fixture is always 5-min / 288).
DSM_INTERVAL_MINUTES = (5, 15, 30, 60)


def dsm_block_size(minutes: int) -> int:
    """Number of native 5-min samples in one DSM display step."""
    m = int(minutes)
    if m not in DSM_INTERVAL_MINUTES:
        raise ValueError(f"DSM interval must be one of {DSM_INTERVAL_MINUTES}, got {minutes}")
    return m // 5


def dsm_dt_hours(minutes: int) -> float:
    return float(minutes) / 60.0


def dsm_steps_per_day(minutes: int, *, native: int = INTERVALS_PER_DAY) -> int:
    block = dsm_block_size(minutes)
    if native % block != 0:
        raise ValueError("native intervals must be divisible by DSM block size")
    return native // block


def downsample_mean(values: list[float] | tuple[float, ...], block: int) -> list[float]:
    """Average contiguous native samples into coarser DSM steps (energy-preserving)."""
    series = [float(v) for v in values]
    b = int(block)
    if b < 1:
        raise ValueError("block must be >= 1")
    if b == 1:
        return series
    if len(series) % b != 0:
        raise ValueError(f"length {len(series)} not divisible by block {b}")
    return [sum(series[i : i + b]) / b for i in range(0, len(series), b)]


def outdoor_hour_index(step: int, *, minutes: int) -> int:
    """Map a DSM playhead step to the 0–23 outdoor-hour index."""
    return min(max(int(step) * int(minutes) // 60, 0), 23)

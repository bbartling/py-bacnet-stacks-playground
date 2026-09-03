"""Residential thermostat / battery campaign orchestration."""
from __future__ import annotations

import json
import time
from pathlib import Path
from typing import Any

import numpy as np

from ..battery import BatteryParams, simulate_dispatch
from ..compute import CampaignCompute, PerRunTelemetry, collect_host_info, write_host_json
from ..plotting import save_baseline_vs_winner_png
from ..tariff import BillingState, billing_cost
from .experiment import default_thermostat_candidates, save_ranking
from .model import MODEL_IDF
from .runner import run_residential_day
from .tariffs import summer_tou_hourly, winter_tou_hourly
from .thermostat import (
    action_to_setpoints_f,
    baseline_setpoints_f,
    build_schedule_action,
    comfort_ok,
    enforce_heat_below_cool,
)


def _season_config(season: str) -> dict[str, Any]:
    key = season.strip().lower()
    if key in {"summer", "jul", "july"}:
        return {
            "season": "summer",
            "month": 7,
            "day": 15,
            "tariff": summer_tou_hourly(),
            "mode": "summer_dr",
            "decision_day": "illustrative-07-15",
        }
    if key in {"winter", "jan", "january"}:
        return {
            "season": "winter",
            "month": 1,
            "day": 15,
            "tariff": winter_tou_hourly(),
            "mode": "winter_dr",
            "decision_day": "illustrative-01-15",
        }
    raise ValueError(f"unknown season: {season}")


def run_thermostat_grid(
    *,
    season: str,
    output_root: Path | str,
    eplus_path: Path | str | None = None,
    max_candidates: int | None = 5,
    idf: Path | str | None = None,
) -> dict[str, Any]:
    cfg = _season_config(season)
    root = Path(output_root)
    root.mkdir(parents=True, exist_ok=True)
    write_host_json(root / "compute" / "host.json", collect_host_info())
    source = Path(idf) if idf else MODEL_IDF
    tariff = cfg["tariff"]
    campaign_start = time.perf_counter()

    baseline = run_residential_day(
        source,
        output_dir=root / "baseline",
        eplus_path=eplus_path,
        month=cfg["month"],
        day=cfg["day"],
    )
    heat0, cool0 = baseline_setpoints_f()
    opening = BillingState()
    baseline_bill = billing_cost(baseline["facility_kw"], tariff=tariff, opening_state=opening)

    candidates = list(default_thermostat_candidates(season=cfg["season"]))
    # Always include an explicit baseline-like candidate first in ranking via baseline row.
    if max_candidates is not None:
        candidates = candidates[: max(0, int(max_candidates))]

    rows: list[dict[str, Any]] = [
        {
            "candidate_id": "BASELINE",
            "billing_cost": float(baseline_bill["total_cost_usd"]),
            "peak_kw": float(baseline["peak_kw"]),
            "total_kwh": float(baseline["total_kwh"]),
            "comfort_ok": bool(comfort_ok(baseline["zone_temp_f"])),
            "soft_ok": bool(baseline.get("soft_ok")),
            "wall_seconds": float(baseline["wall_seconds"]),
            "action_json": json.dumps({"mode": "baseline"}),
            "idf_sha256": baseline["idf_sha256"],
        }
    ]
    telemetry = [
        PerRunTelemetry(
            candidate_id="BASELINE",
            wall_seconds=float(baseline["wall_seconds"]),
            process_returncode=int(baseline["process_returncode"]),
            fatal_count=int(baseline["fatal_count"]),
            severe_count=int(baseline["severe_count"]),
            warning_count=int(baseline["warning_count"]),
            peak_kw=float(baseline["peak_kw"]),
            total_kwh=float(baseline["total_kwh"]),
        )
    ]
    trajectories: dict[str, dict[str, Any]] = {"BASELINE": baseline}

    for candidate in candidates:
        action = build_schedule_action(mode=cfg["mode"], **dict(candidate.action))
        heat, cool = action_to_setpoints_f(action)
        # Keep opposing setpoint at baseline defaults, then enforce deadband.
        if cfg["season"] == "summer":
            heat = np.full(len(cool), float(heat0[0]))
        else:
            cool = np.full(len(heat), float(cool0[0]))
        heat, cool = enforce_heat_below_cool(heat, cool)
        metrics = run_residential_day(
            source,
            output_dir=root / "candidates" / candidate.candidate_id,
            eplus_path=eplus_path,
            month=cfg["month"],
            day=cfg["day"],
            heat_f=heat,
            cool_f=cool,
        )
        ok_comfort = comfort_ok(metrics["zone_temp_f"]) if metrics.get("zone_temp_f") else False
        bill = (
            billing_cost(metrics["facility_kw"], tariff=tariff, opening_state=opening)
            if metrics.get("facility_kw")
            else {"total_cost_usd": float("inf")}
        )
        cost = float(bill["total_cost_usd"]) if metrics.get("soft_ok") and ok_comfort else float("inf")
        rows.append(
            {
                "candidate_id": candidate.candidate_id,
                "billing_cost": cost,
                "peak_kw": float(metrics.get("peak_kw") or 0.0),
                "total_kwh": float(metrics.get("total_kwh") or 0.0),
                "comfort_ok": ok_comfort,
                "soft_ok": bool(metrics.get("soft_ok")),
                "wall_seconds": float(metrics.get("wall_seconds") or 0.0),
                "action_json": json.dumps(action, sort_keys=True),
                "idf_sha256": metrics.get("idf_sha256"),
            }
        )
        telemetry.append(
            PerRunTelemetry(
                candidate_id=candidate.candidate_id,
                wall_seconds=float(metrics.get("wall_seconds") or 0.0),
                process_returncode=int(metrics.get("process_returncode") or 1),
                fatal_count=int(metrics.get("fatal_count") or 0),
                severe_count=int(metrics.get("severe_count") or 0),
                warning_count=int(metrics.get("warning_count") or 0),
                peak_kw=float(metrics.get("peak_kw") or 0.0),
                total_kwh=float(metrics.get("total_kwh") or 0.0),
            )
        )
        trajectories[candidate.candidate_id] = metrics

    ranking = save_ranking(
        rows,
        csv_path=root / "ranking.csv",
        json_path=root / "ranking.json",
        winner_key="billing_cost",
    )
    winner = ranking.get("winner") or {}
    winner_id = str(winner.get("candidate_id") or "BASELINE")
    winner_metrics = trajectories.get(winner_id, baseline)
    plot = save_baseline_vs_winner_png(
        baseline,
        winner_metrics,
        root / "baseline_vs_winner.png",
        title=f"{cfg['season']} baseline vs winner ({winner_id})",
    )
    winner_schedule = {
        "candidate_id": winner_id,
        "action": json.loads(winner.get("action_json") or "{}"),
        "billing_cost": winner.get("billing_cost"),
        "claim_tariff": "ILLUSTRATIVE_HIGH_VALUE_TOU_TARIFF",
        "claim_model": "HYPOTHETICAL_GL14_TUNED_DEMO_MODEL",
    }
    (root / "winner_schedule.json").write_text(
        json.dumps(winner_schedule, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )
    campaign_wall = time.perf_counter() - campaign_start
    compute = CampaignCompute(runs=telemetry, campaign_wall_seconds=campaign_wall).summary()
    compute["nominal_zone_timestep_evaluations"] = 288 * len(telemetry)
    (root / "compute" / "campaign.json").write_text(
        json.dumps(compute, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )
    return {
        "schema": "vibe23.residential_thermostat_grid.v1",
        "season": cfg["season"],
        "decision_day": cfg["decision_day"],
        "tariff_id": tariff.tariff_id,
        "tariff_sha256": tariff.fingerprint(),
        "baseline": {k: v for k, v in baseline.items() if k not in {"facility_kw", "zone_temp_f", "inspection"}},
        "ranking": ranking,
        "winner_schedule": winner_schedule,
        "plot": str(plot),
        "compute": compute,
        "claim_model": "HYPOTHETICAL_GL14_TUNED_DEMO_MODEL",
        "claim_tariff": "ILLUSTRATIVE_HIGH_VALUE_TOU_TARIFF",
    }


def run_battery_grid(
    *,
    season: str,
    output_root: Path | str,
    eplus_path: Path | str | None = None,
    max_candidates: int | None = 3,
    idf: Path | str | None = None,
) -> dict[str, Any]:
    """Thermal top-N plus battery-only and combined purchased-grid comparison."""

    root = Path(output_root)
    thermal = run_thermostat_grid(
        season=season,
        output_root=root / "thermal",
        eplus_path=eplus_path,
        max_candidates=max_candidates,
        idf=idf,
    )
    cfg = _season_config(season)
    tariff = cfg["tariff"]
    prices = list(tariff.energy_rates_per_kwh)
    # Re-load baseline facility from thermal campaign artifacts via re-run is expensive;
    # use ranking winner/baseline by re-simulating baseline only once more if needed.
    baseline = run_residential_day(
        Path(idf) if idf else MODEL_IDF,
        output_dir=root / "battery_baseline",
        eplus_path=eplus_path,
        month=cfg["month"],
        day=cfg["day"],
    )
    params = BatteryParams(
        capacity_kwh=13.5,
        max_charge_kw=5.0,
        max_discharge_kw=5.0,
        eta_c=0.95,
        eta_d=0.95,
        soc_min=0.1,
        soc_max=0.95,
        initial_soc=0.5,
    )
    opening = BillingState()
    thermal_only_kw = baseline["facility_kw"]
    battery_only = simulate_dispatch(thermal_only_kw, prices, params, mode="price_arbitrage")
    # Combined: use winner thermal if available else baseline, then battery.
    winner_id = str((thermal.get("winner_schedule") or {}).get("candidate_id") or "BASELINE")
    winner_dir = root / "thermal" / "candidates" / winner_id
    if winner_id == "BASELINE" or not (winner_dir / "eplusout.csv").is_file():
        combined_house_kw = thermal_only_kw
    else:
        from .runner import _resample_288, parse_eplus_csv

        parsed = parse_eplus_csv(winner_dir)
        combined_house_kw = _resample_288(parsed["facility_kw"].tolist())
    combined = simulate_dispatch(combined_house_kw, prices, params, mode="price_arbitrage")

    def _cost(kw: list[float]) -> float:
        return float(billing_cost(kw, tariff=tariff, opening_state=opening)["total_cost_usd"])

    comparison = {
        "thermal_only_cost": _cost(thermal_only_kw),
        "battery_only_cost": _cost(list(battery_only["purchased_kw"])),  # type: ignore[arg-type]
        "combined_cost": _cost(list(combined["purchased_kw"])),  # type: ignore[arg-type]
        "thermal_only_peak_kw": float(max(thermal_only_kw) if thermal_only_kw else 0.0),
        "battery_only_peak_kw": float(max(battery_only["purchased_kw"])),  # type: ignore[arg-type]
        "combined_peak_kw": float(max(combined["purchased_kw"])),  # type: ignore[arg-type]
        "battery_params": params.to_dict(),
        "winner_thermal_id": winner_id,
    }
    out = {
        "schema": "vibe23.residential_battery_grid.v1",
        "season": cfg["season"],
        "thermal": {k: v for k, v in thermal.items() if k != "baseline"},
        "comparison": comparison,
        "claim_model": "HYPOTHETICAL_GL14_TUNED_DEMO_MODEL",
        "claim_tariff": "ILLUSTRATIVE_HIGH_VALUE_TOU_TARIFF",
        "note": "Costs use purchased-grid load after battery dispatch; illustrative TOU only.",
    }
    (root / "battery_comparison.json").write_text(
        json.dumps(out, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )
    return out

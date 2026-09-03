"""July demand-response scenario helpers."""
from __future__ import annotations

from pathlib import Path
from typing import Any, Mapping

from .. import plotting
from .constants import DEFAULT_COOL_F, DEFAULT_HEAT_F, DT_HOURS, MAX_COOL_F
from .runner import run_residential_day
from .thermostat import action_to_setpoints_f, build_schedule_action, comfort_ok


def july_dr_action() -> dict[str, Any]:
    return build_schedule_action(
        pre_start_hour=12.0,
        event_start=14.0,
        event_end=18.0,
        recover_end=21.0,
        pre_cool_f=70.5,
        event_cool_f=MAX_COOL_F,
        recover_cool_f=DEFAULT_COOL_F,
        mode="summer_dr",
    )


def run_july_dr(
    *,
    output_root: Path | str,
    eplus_path: Path | str | None = None,
    idf: Path | str | None = None,
) -> dict[str, Any]:
    from .model import MODEL_IDF

    root = Path(output_root)
    root.mkdir(parents=True, exist_ok=True)
    source = idf or MODEL_IDF
    baseline = run_residential_day(
        source,
        output_dir=root / "baseline",
        eplus_path=eplus_path,
        month=7,
        day=15,
    )
    action = july_dr_action()
    heat, cool = action_to_setpoints_f(action)
    event = run_residential_day(
        source,
        output_dir=root / "event",
        eplus_path=eplus_path,
        month=7,
        day=15,
        heat_f=heat,
        cool_f=cool,
    )
    comparison = compare_dr(baseline, event)
    plot_path = root / "dr_comparison.png"
    plotting.save_dr_comparison_png(baseline, event, plot_path)
    return {
        "schema": "vibe23.residential_dr.v1",
        "action": action,
        "baseline": baseline,
        "event": event,
        "comparison": comparison,
        "plot": str(plot_path),
        "claim_model": "HYPOTHETICAL_GL14_TUNED_DEMO_MODEL",
        "claim_assumptions": "ILLUSTRATIVE_RESIDENTIAL_ASSUMPTIONS",
    }


def _peak_period_kwh(facility_kw: list[float], start_hour: float = 14.0, end_hour: float = 18.0) -> float:
    n = len(facility_kw)
    total = 0.0
    for i, kw in enumerate(facility_kw):
        hour = (i + 1) * 24.0 / max(n, 1)
        if start_hour < hour <= end_hour:
            total += float(kw) * DT_HOURS
    return total


def compare_dr(baseline_metrics: Mapping[str, Any], event_metrics: Mapping[str, Any]) -> dict[str, Any]:
    b_kw = list(baseline_metrics.get("facility_kw") or [])
    e_kw = list(event_metrics.get("facility_kw") or [])
    b_temp = list(baseline_metrics.get("zone_temp_f") or [])
    e_temp = list(event_metrics.get("zone_temp_f") or [])
    return {
        "peak_kw_baseline": float(baseline_metrics.get("peak_kw") or 0.0),
        "peak_kw_event": float(event_metrics.get("peak_kw") or 0.0),
        "peak_kw_delta": float(event_metrics.get("peak_kw") or 0.0) - float(baseline_metrics.get("peak_kw") or 0.0),
        "total_kwh_baseline": float(baseline_metrics.get("total_kwh") or 0.0),
        "total_kwh_event": float(event_metrics.get("total_kwh") or 0.0),
        "total_kwh_delta": float(event_metrics.get("total_kwh") or 0.0)
        - float(baseline_metrics.get("total_kwh") or 0.0),
        "peak_period_kwh_baseline": _peak_period_kwh(b_kw),
        "peak_period_kwh_event": _peak_period_kwh(e_kw),
        "peak_period_kwh_delta": _peak_period_kwh(e_kw) - _peak_period_kwh(b_kw),
        "comfort_ok_baseline": comfort_ok(b_temp) if b_temp else False,
        "comfort_ok_event": comfort_ok(e_temp) if e_temp else False,
        "default_heat_f": DEFAULT_HEAT_F,
        "default_cool_f": DEFAULT_COOL_F,
    }

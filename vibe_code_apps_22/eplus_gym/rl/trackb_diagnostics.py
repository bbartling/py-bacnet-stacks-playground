"""Per-bank Track B physics diagnostics from a scored trajectory + eio totals."""
from __future__ import annotations

from eplus_gym.control_v2 import ACTION_KEYS


def diagnose_w2a_hypotheses(*, actual_rated_air_ratio: float | None) -> list[str]:
    hyps = [
        "mismatched_fan_and_coil_rated_flow",
        "mismatched_noload_heating_airflow",
        "independent_bank_sizing",
        "sequential_bank_staging",
        "plant_loop_flow",
        "oversized_bank_capacity",
        "reporting_or_parser_defect",
    ]
    if actual_rated_air_ratio is not None and actual_rated_air_ratio < 0.25:
        return ["mismatched_fan_and_coil_rated_flow", "oversized_bank_capacity"] + hyps[2:]
    return hyps


def bank_group_diagnostics(
    *,
    plan: Mapping[str, Any],
    sizing_totals: Mapping[str, Mapping[str, Any]],
    payload: Mapping[str, Any],
    w2a_scored_runtime: int,
) -> dict[str, Any]:
    groups: list[dict[str, Any]] = []
    six = plan.get("groups") or plan.get("six_group_plan", {}).get("groups") or []
    fac = [float(x) for x in (payload.get("facility_kw") or [])]
    for g in six:
        zone = str(g.get("bas_group") or g.get("eplus_zone") or g.get("action_key") or "")
        totals = dict(sizing_totals.get(zone) or {})
        idx = list(ACTION_KEYS).index(str(g.get("action_key"))) if g.get("action_key") in ACTION_KEYS else 0
        start = list(payload.get("start_zone_temps_f") or [])
        final = list(payload.get("final_zone_temps_f") or payload.get("zone_temps_f") or [])
        rated_air = totals.get("heating_airflow_m3s")
        rated_cap = totals.get("heating_capacity_w")
        rec = {
            "action_key": g.get("action_key"),
            "bas_group": g.get("bas_group"),
            "eplus_zone": zone or g.get("bas_group"),
            "hp_count": g.get("hp_count"),
            "n_banks": g.get("n_banks"),
            "assumed_capacity_class": g.get("fractions"),
            "total_heating_capacity_w": rated_cap,
            "rated_airflow_m3s": rated_air,
            "actual_airflow_m3s": None,
            "actual_rated_airflow_ratio": None,
            "rated_water_flow_m3s": totals.get("heating_water_m3s"),
            "actual_water_flow_m3s": None,
            "plr_or_runtime_fraction": None,
            "fan_airflow_and_power": None,
            "compressor_power_kw": None,
            "pump_loop_power_kw": None,
            "ewt_lwt_c": None,
            "zone_load": None,
            "zone_temperature_f_start": start[idx] if idx < len(start) else None,
            "zone_temperature_f_final": final[idx] if idx < len(final) else None,
            "facility_kw_peak": float(max(fac)) if fac else None,
            "missing_eso_meter_fields": True,
        }
        groups.append(rec)
    ratio = None
    return {
        "schema": "vibe22.trackb.bank_diagnostics.v1",
        "w2a_scored_runtime": int(w2a_scored_runtime),
        "w2a_bound": 0,
        "warnings_not_suppressed": True,
        "hypotheses": diagnose_w2a_hypotheses(actual_rated_air_ratio=ratio),
        "groups": groups,
        "facility_kw_n": len(fac),
        "note": (
            "Rated coil/fan fields come from LIVE eio sizing totals. "
            "Actual airflow/PLR/EWT require scored meters; missing meters are reported, not invented."
        ),
    }

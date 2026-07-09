"""KPI summaries from cookbook_engine — single source for dashboard overview cards."""

from __future__ import annotations

from typing import Any


def fault_hours_for_rule(
    equipment_id: str,
    kind: str,
    rule_id: str,
    *,
    params_by_rule: dict[str, dict] | None = None,
) -> dict[str, Any]:
    """Return fault hours/pct for one rule on one equipment (uses disk cache)."""
    import cookbook_engine as ce

    view = ce.equipment_view(equipment_id, kind, params_by_rule=params_by_rule or {})
    for rule in view.get("rules") or []:
        if rule.get("id") == rule_id:
            return {
                "rule_id": rule_id,
                "applicable": rule.get("applicable", False),
                "fault_hours": rule.get("fault_hours", 0.0),
                "fault_pct": rule.get("fault_pct", 0.0),
                "message": rule.get("message", ""),
            }
    return {"rule_id": rule_id, "applicable": False, "fault_hours": 0.0, "fault_pct": 0.0}


def overview_kpis(*, params_by_rule: dict[str, dict] | None = None) -> dict[str, Any]:
    """Key overview metrics from cookbook (COMFORT proxy, ECON, excess fan proxy)."""
    params_by_rule = params_by_rule or {}
    out: dict[str, Any] = {}

    # Zone comfort — aggregate VAV-1 across first VAV with data
    try:
        import cookbook_engine as ce
        targets = ce.page_targets("zones", vav_limit=5)
        vav_hours = []
        for eq_id, kind in targets:
            if kind != "vav":
                continue
            r = fault_hours_for_rule(eq_id, kind, "VAV-1", params_by_rule=params_by_rule)
            if r.get("applicable"):
                vav_hours.append(r["fault_hours"])
        if vav_hours:
            out["zone_comfort_fault_h"] = round(sum(vav_hours), 1)
    except Exception:
        pass

    for eq, rule, key in [
        ("AHU_1", "ECON-3", "econ3_fault_h"),
        ("AHU_1", "OAT-METEO", "oat_meteo_fault_h"),
        ("AHU_1", "EXCESS-FAN", "excess_fan_fault_h"),
    ]:
        try:
            kind = "ahu"
            if rule == "EXCESS-FAN":
                rule = "SCHED-1"  # unoccupied runtime proxy
            r = fault_hours_for_rule(eq, kind, rule, params_by_rule=params_by_rule)
            if r.get("applicable"):
                out[key] = r["fault_hours"]
        except Exception:
            pass

    return out

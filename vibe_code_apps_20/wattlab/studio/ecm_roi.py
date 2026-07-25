"""Per-ECM ROI cost seeding — $/ft² × coverage fraction, engineer-tweakable.

Liberty-style example: convert ~50% of a building to full DDC so Guideline 36
VAV sequences can run → cost = area_ft2 × coverage_fraction × usd_per_ft2.

Prefills come from public retrofit cost bands + measure-specific overrides;
Studio lets the engineer edit every row before capital-plan rollup.
"""

from __future__ import annotations

from typing import Any

# Screening defaults: usd_per_ft2 is applied to (floor_area × coverage_fraction).
# fixed_usd_override wins when set (>0) — use for lump-sum equipment quotes.
DEFAULT_ECM_ROI_MODELS: dict[str, dict[str, Any]] = {
    "ECM-AHU-SCHED-ALIGN": {
        "usd_per_ft2": 0.15,
        "coverage_fraction": 1.0,
        "note": "Schedule / BAS point work — RCx band",
    },
    "ECM-RCX-SETPOINT-REVIEW": {
        "usd_per_ft2": 0.26,
        "coverage_fraction": 1.0,
        "note": "RCx / setpoint reconciliation (LBNL median ~$0.26/ft²)",
    },
    "ECM-PREMIUM-FAN-VFD": {
        "usd_per_ft2": 1.8,
        "coverage_fraction": 1.0,
        "note": "Fan + VFD capital screening",
    },
    "ECM-PUMP-VFD": {
        "usd_per_ft2": 0.9,
        "coverage_fraction": 1.0,
        "note": "Hydronic pump VFD screening",
    },
    "ECM-DSP-RESET": {
        "usd_per_ft2": 0.20,
        "coverage_fraction": 1.0,
        "note": "Controls sequence + commissioning",
    },
    "ECM-SAT-RESET": {
        "usd_per_ft2": 0.25,
        "coverage_fraction": 1.0,
        "note": "Controls sequence + commissioning",
    },
    "ECM-VAV-MIN-RESET": {
        "usd_per_ft2": 0.40,
        "coverage_fraction": 1.0,
        "note": "Terminal reprogramming / TAB follow-up",
    },
    "ECM-ECON-REPAIR": {
        "usd_per_ft2": 0.30,
        "coverage_fraction": 1.0,
        "note": "Damper/actuator/sensor repair",
    },
    "ECM-DCV-CO2": {
        "usd_per_ft2": 0.50,
        "coverage_fraction": 1.0,
        "note": "CO₂ sensors + OA reset programming",
    },
    "ECM-BOILER-RESET": {
        "usd_per_ft2": 0.20,
        "coverage_fraction": 1.0,
        "note": "HWST reset sequence",
    },
    "ECM-CHW-RESET": {
        "usd_per_ft2": 0.25,
        "coverage_fraction": 1.0,
        "note": "CHWST reset sequence",
    },
    "ECM-CW-RESET": {
        "usd_per_ft2": 0.25,
        "coverage_fraction": 1.0,
        "note": "CWST / tower sequencing",
    },
    "ECM-CHILLER-LOCKOUT": {
        "usd_per_ft2": 0.12,
        "coverage_fraction": 1.0,
        "note": "Lockout logic + OAT sensor QA",
    },
    "ECM-BOILER-TUNE": {
        "usd_per_ft2": 0.25,
        "coverage_fraction": 1.0,
        "note": "Combustion tune / O₂ trim screening",
    },
    "ECM-ADVANCED-RTU": {
        "usd_per_ft2": 0.80,
        "coverage_fraction": 1.0,
        "note": "Packaged RTU advanced controls retrofit",
    },
    "ECM-CONDENSING-BOILER": {
        "usd_per_ft2": 8.0,
        "coverage_fraction": 1.0,
        "note": "HE / condensing boiler plant capital",
    },
    "ECM-CHILLER-REPLACE-HIEFF": {
        "usd_per_ft2": 12.0,
        "coverage_fraction": 1.0,
        "note": "High-efficiency chiller capital",
    },
    # Liberty-style: only part of the floor plate needs full DDC for G36 VAV.
    "ECM-GL36-AIRSIDE": {
        "usd_per_ft2": 6.0,
        "coverage_fraction": 0.50,
        "note": "Partial-building DDC + G36 airside — edit coverage (e.g. 0.5 = 50% floor)",
    },
    "ECM-PNEU-DDC-CONVERT": {
        "usd_per_ft2": 7.5,
        "coverage_fraction": 0.50,
        "note": "Pneumatic→DDC conversion — coverage = fraction of building converted",
    },
    "ECM-SENSOR-CRITICAL-REFRESH": {
        "usd_per_ft2": 0.35,
        "coverage_fraction": 1.0,
        "note": "Critical sensor refresh ahead of resets",
    },
}

# Fallback when measure not in DEFAULT_ECM_ROI_MODELS — use registry scope p50.
_SCOPE_FALLBACK_USD_FT2 = {
    "rcx_tuning": 0.26,
    "minor_hvac_controls": 2.35,
    "bas_overlay": 5.0,
    "controls_first": 3.0,
    "major_hvac": 4.6,
    "major_hvac_renewal": 18.0,
}


def implementation_cost_usd(
    *,
    floor_area_ft2: float,
    usd_per_ft2: float,
    coverage_fraction: float = 1.0,
    fixed_usd: float | None = None,
) -> float:
    """Cost = fixed_usd if set, else floor_area × coverage × $/ft²."""
    if fixed_usd is not None and float(fixed_usd) > 0:
        return float(fixed_usd)
    cov = max(0.0, min(1.0, float(coverage_fraction)))
    return float(floor_area_ft2) * cov * float(usd_per_ft2)


def default_model_for(measure_id: str) -> dict[str, Any]:
    """Return a copy of the screening cost model for one ECM."""
    mid = str(measure_id)
    if mid in DEFAULT_ECM_ROI_MODELS:
        return dict(DEFAULT_ECM_ROI_MODELS[mid])
    try:
        from wattlab.benchmarks.costs import scope_for_measure

        scope = scope_for_measure(mid)
        usd = _SCOPE_FALLBACK_USD_FT2.get(scope, 1.0)
    except Exception:
        usd = 1.0
        scope = "rcx_tuning"
    return {
        "usd_per_ft2": usd,
        "coverage_fraction": 1.0,
        "note": f"Fallback from scope `{scope}` — engineer should verify",
    }


def seed_roi_cost_rows(
    measure_ids: list[str],
    *,
    floor_area_ft2: float,
    existing: dict[str, dict[str, Any]] | None = None,
) -> list[dict[str, Any]]:
    """Build editable ROI cost rows; preserve engineer edits from ``existing``."""
    prior = existing or {}
    rows: list[dict[str, Any]] = []
    for mid in measure_ids:
        base = default_model_for(mid)
        prev = prior.get(mid) or {}
        usd = float(prev.get("usd_per_ft2", base["usd_per_ft2"]))
        cov = float(prev.get("coverage_fraction", base["coverage_fraction"]))
        fixed = prev.get("fixed_usd")
        fixed_f = float(fixed) if fixed not in (None, "") else None
        cost = implementation_cost_usd(
            floor_area_ft2=floor_area_ft2,
            usd_per_ft2=usd,
            coverage_fraction=cov,
            fixed_usd=fixed_f,
        )
        rows.append(
            {
                "measure_id": mid,
                "usd_per_ft2": round(usd, 4),
                "coverage_fraction": round(cov, 3),
                "applicable_ft2": round(float(floor_area_ft2) * max(0.0, min(1.0, cov)), 0),
                "fixed_usd": fixed_f,
                "implementation_cost_usd": round(cost, 0),
                "note": str(prev.get("note") or base.get("note") or ""),
            }
        )
    return rows


def rows_to_cost_map(rows: list[dict[str, Any]]) -> dict[str, float]:
    """measure_id → implementation_cost_usd for capital_plan / session state."""
    out: dict[str, float] = {}
    for r in rows:
        mid = r.get("measure_id")
        if not mid:
            continue
        out[str(mid)] = float(r.get("implementation_cost_usd") or 0.0)
    return out


def rows_to_models(rows: list[dict[str, Any]]) -> dict[str, dict[str, Any]]:
    """Persist engineer-tweaked models keyed by measure_id."""
    out: dict[str, dict[str, Any]] = {}
    for r in rows:
        mid = r.get("measure_id")
        if not mid:
            continue
        out[str(mid)] = {
            "usd_per_ft2": float(r.get("usd_per_ft2") or 0.0),
            "coverage_fraction": float(r.get("coverage_fraction") or 1.0),
            "fixed_usd": r.get("fixed_usd"),
            "note": r.get("note") or "",
        }
    return out


__all__ = [
    "DEFAULT_ECM_ROI_MODELS",
    "default_model_for",
    "implementation_cost_usd",
    "rows_to_cost_map",
    "rows_to_models",
    "seed_roi_cost_rows",
]

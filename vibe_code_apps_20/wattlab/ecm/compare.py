"""Simple spreadsheet vs EnergyPlus ECM compare contract.

Studio ECMs reads ``reports/ecm_compare.json``. Spreadsheet side is prepared
but stays null until external ESCO workbooks are wired in.
"""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

SCHEMA = "wattlab_ecm_compare_v1"
DEFAULT_COMPARE_NAME = "ecm_compare.json"


def compare_path(reports: Path | str) -> Path:
    return Path(reports) / DEFAULT_COMPARE_NAME


def _f(v: Any) -> float | None:
    if v is None or v == "":
        return None
    try:
        return float(v)
    except (TypeError, ValueError):
        return None


def _payback(capital: float | None, annual_usd: float | None) -> float | None:
    if capital is None or annual_usd is None or annual_usd <= 0:
        return None
    return round(capital / annual_usd, 2)


def _roi(capital: float | None, annual_usd: float | None) -> float | None:
    """Simple first-year ROI = annual $ / capital (not NPV)."""
    if capital is None or capital <= 0 or annual_usd is None:
        return None
    return round(annual_usd / capital, 3)


def capital_for_measure(
    measure_id: str,
    *,
    area_ft2: float | None,
    profile: dict[str, Any] | None = None,
) -> float | None:
    """Screening capital from ecm_roi defaults when area known."""
    if not area_ft2:
        return None
    try:
        from wattlab.studio.ecm_roi import default_model_for, implementation_cost_usd

        model = default_model_for(measure_id)
        return round(
            implementation_cost_usd(
                floor_area_ft2=float(area_ft2),
                usd_per_ft2=float(model.get("usd_per_ft2") or 0),
                coverage_fraction=float(model.get("coverage_fraction") or 1.0),
                fixed_usd=_f(model.get("fixed_usd")),
            ),
            0,
        )
    except Exception:
        return None


def build_compare_from_cascade(
    cascade_report: dict[str, Any],
    *,
    measure_ids: list[str] | None = None,
    twin_run: str | None = None,
    cascade_dir: str | Path | None = None,
    profile: dict[str, Any] | None = None,
    spreadsheet: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Merge EnergyPlus ``savings_by_measure`` into a Studio-ready compare table."""
    profile = profile or {}
    util = profile.get("utility") or {}
    elec = _f(util.get("elec_usd_per_kwh")) or _f(profile.get("elec_usd_per_kwh")) or 0.12
    gas = _f(util.get("gas_usd_per_therm")) or _f(profile.get("gas_usd_per_therm")) or 0.80
    area = (
        _f(profile.get("conditioned_floor_area_ft2"))
        or _f(profile.get("floor_area_ft2"))
        or _f((profile.get("geometry") or {}).get("floor_area_ft2"))
    )

    by_mid: dict[str, dict[str, Any]] = {}
    for row in cascade_report.get("savings_by_measure") or []:
        mid = str(row.get("measure_id") or "")
        if not mid or mid.lower() == "baseline":
            continue
        vs = row.get("vs_baseline") or {}
        kwh = _f(vs.get("kwh_saved"))
        therms = _f(vs.get("therms_saved"))
        usd = _f(vs.get("cost_saved_usd"))
        if usd is None and (kwh is not None or therms is not None):
            usd = round((kwh or 0.0) * elec + (therms or 0.0) * gas, 2)
        by_mid[mid] = {
            "ep_kwh": kwh,
            "ep_therms": therms,
            "ep_usd": usd,
            "ep_error": row.get("error"),
            "patch_ok": row.get("patch_ok"),
        }

    ids = list(measure_ids) if measure_ids else list(by_mid.keys())
    measures: list[dict[str, Any]] = []
    for mid in ids:
        ep = by_mid.get(mid) or {}
        capital = capital_for_measure(mid, area_ft2=area, profile=profile)
        ep_usd = ep.get("ep_usd")
        measures.append(
            {
                "measure_id": mid,
                # EnergyPlus (real when cascade filled)
                "ep_kwh": ep.get("ep_kwh"),
                "ep_therms": ep.get("ep_therms"),
                "ep_usd": ep_usd,
                "ep_note": ep.get("ep_error") or None,
                # Spreadsheet — reserved for external ESCO books
                "ss_kwh": None,
                "ss_therms": None,
                "ss_usd": None,
                "ss_note": "pending_external_spreadsheet",
                # ROI attempt (screening)
                "capital_usd": capital,
                "payback_yr_ep": _payback(capital, ep_usd),
                "payback_yr_ss": None,
                "roi_ep": _roi(capital, ep_usd),
                "roi_ss": None,
                "status": "ep_ready" if ep.get("ep_kwh") is not None else "ep_pending",
            }
        )

    return {
        "schema": SCHEMA,
        "updated_at": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "twin_run": twin_run or cascade_report.get("twin_run"),
        "cascade_dir": str(cascade_dir) if cascade_dir else cascade_report.get("run_id"),
        "rates": {"elec_usd_per_kwh": elec, "gas_usd_per_therm": gas},
        "area_ft2": area,
        "measures": measures,
        "spreadsheet": spreadsheet
        or {
            "status": "pending_external",
            "path": None,
            "note": "Agent-built WattLab xlsx retired — drop external ESCO books here later",
        },
        "energyplus": {
            "status": "ready" if by_mid else "empty",
            "source": "cascade_measures_on_twin",
            "weather_suitability": cascade_report.get("weather_suitability"),
        },
        "honesty": (
            "E+ columns = calibrated Twin − ECM-on-Twin when cascade succeeds. "
            "Spreadsheet columns stay blank until external calc books are imported. "
            "ROI = first-year annual $ / screening capital — not investment-grade."
        ),
    }


def write_compare(path: Path | str, payload: dict[str, Any]) -> Path:
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
    return path


def load_compare(path: Path | str) -> dict[str, Any] | None:
    path = Path(path)
    if not path.is_file():
        return None
    return json.loads(path.read_text(encoding="utf-8"))


def empty_compare_stub(
    *,
    twin_run: str | None = None,
    measure_ids: list[str] | None = None,
) -> dict[str, Any]:
    ids = measure_ids or ["ECM-DSP-RESET", "ECM-SAT-RESET", "ECM-CHILLER-LOCKOUT"]
    return build_compare_from_cascade(
        {"savings_by_measure": [], "twin_run": twin_run},
        measure_ids=ids,
        twin_run=twin_run,
        spreadsheet={
            "status": "pending_external",
            "path": None,
            "note": "Spreadsheet calcs from other sources — not ready yet",
        },
    )


__all__ = [
    "SCHEMA",
    "DEFAULT_COMPARE_NAME",
    "compare_path",
    "build_compare_from_cascade",
    "write_compare",
    "load_compare",
    "empty_compare_stub",
    "capital_for_measure",
]

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
FULL_PARITY_COMPARE_NAME = "ecm_full_parity_compare.json"
FULL_PARITY_SS_KEYS = (
    "ss_kwh",
    "ss_therms",
    "ss_usd",
    "payback_yr_ss",
    "roi_ss",
)


def compare_path(reports: Path | str) -> Path:
    return Path(reports) / DEFAULT_COMPARE_NAME


def full_parity_compare_path(reports: Path | str) -> Path:
    return Path(reports) / FULL_PARITY_COMPARE_NAME


def discover_notebook_xlsx(notebooks_dir: Path | str) -> list[Path]:
    """Recursive ``*.xlsx`` under ``reports/notebooks/**`` (skip Excel lockfiles)."""
    root = Path(notebooks_dir)
    if not root.is_dir():
        return []
    return sorted(
        p
        for p in root.rglob("*.xlsx")
        if p.is_file() and not p.name.startswith("~$")
    )


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


def _normalize_parity_row(row: dict[str, Any]) -> dict[str, Any]:
    """Map agent / cascade aliases onto Studio ``ss_*`` fields (BUG-ECM-015)."""
    mid = str(row.get("measure_id") or "")
    return {
        "measure_id": mid,
        "ss_kwh": row.get(
            "ss_kwh", row.get("kwh_saved", row.get("ss_kWh", row.get("sheet_kwh")))
        ),
        "ss_therms": row.get("ss_therms", row.get("therms_saved")),
        "ss_usd": row.get(
            "ss_usd",
            row.get("annual_usd", row.get("cost_saved_usd", row.get("usd_saved"))),
        ),
        "payback_yr_ss": row.get("payback_yr_ss", row.get("payback_yr")),
        "roi_ss": row.get("roi_ss", row.get("roi")),
        "ss_note": row.get("ss_note"),
    }


def _parity_measure_rows(parity: dict[str, Any]) -> list[dict[str, Any]]:
    """Normalize full-parity JSON shapes into measure dicts with ss_* fields.

    Agent full-parity writer emits top-level ``rows`` (+ ``annual_usd``); Studio
    historically expected ``measures`` / ``savings_by_measure`` (BUG-ECM-015).
    """
    rows = parity.get("measures")
    if isinstance(rows, list):
        return [_normalize_parity_row(r) for r in rows if isinstance(r, dict)]
    ss = parity.get("spreadsheet")
    if isinstance(ss, dict) and isinstance(ss.get("measures"), list):
        return [_normalize_parity_row(r) for r in ss["measures"] if isinstance(r, dict)]
    # Agent writer uses top-level "rows" (BUG-ECM-015).
    by_mid = (
        parity.get("rows")
        or parity.get("savings_by_measure")
        or parity.get("by_measure")
    )
    if isinstance(by_mid, list):
        out: list[dict[str, Any]] = []
        for row in by_mid:
            if not isinstance(row, dict):
                continue
            mapped = _normalize_parity_row(row)
            if mapped["measure_id"]:
                out.append(mapped)
        return out
    if isinstance(by_mid, dict):
        out = []
        for mid, row in by_mid.items():
            if not isinstance(row, dict):
                continue
            mapped = _normalize_parity_row({**row, "measure_id": row.get("measure_id") or mid})
            out.append(mapped)
        return out
    return []


def merge_full_parity_ss(
    compare_payload: dict[str, Any],
    reports_dir: Path | str,
    *,
    parity_path: Path | str | None = None,
) -> dict[str, Any]:
    """Fill ``ss_*`` from ``ecm_full_parity_compare.json`` when present (BUG-ECM-015).

    Merge-if-present only — never invent spreadsheet numbers. Returns the same
    payload dict (mutated in place when parity file exists and has values).
    """
    reports = Path(reports_dir)
    path = Path(parity_path) if parity_path else full_parity_compare_path(reports)
    if not path.is_file():
        return compare_payload

    try:
        parity = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return compare_payload
    if not isinstance(parity, dict):
        return compare_payload

    by_mid: dict[str, dict[str, Any]] = {}
    for row in _parity_measure_rows(parity):
        mid = str(row.get("measure_id") or "")
        if mid:
            by_mid[mid] = row

    if not by_mid:
        return compare_payload

    measures = compare_payload.get("measures")
    if not isinstance(measures, list):
        measures = []
        compare_payload["measures"] = measures

    existing = {str(m.get("measure_id")): m for m in measures if isinstance(m, dict)}
    filled = 0
    for mid, src in by_mid.items():
        row = existing.get(mid)
        if row is None:
            row = {
                "measure_id": mid,
                "ep_kwh": None,
                "ep_therms": None,
                "ep_usd": None,
                "ep_note": None,
                "ss_kwh": None,
                "ss_therms": None,
                "ss_usd": None,
                "ss_note": None,
                "capital_usd": None,
                "payback_yr_ep": None,
                "payback_yr_ss": None,
                "roi_ep": None,
                "roi_ss": None,
                "status": "ss_ready",
            }
            measures.append(row)
            existing[mid] = row

        for key in FULL_PARITY_SS_KEYS:
            val = src.get(key)
            if val is None or val == "":
                continue
            # Only fill from parity — do not invent; coerce numerics when present.
            if key in ("ss_kwh", "ss_therms", "ss_usd", "payback_yr_ss", "roi_ss"):
                num = _f(val)
                if num is None:
                    continue
                row[key] = num
            else:
                row[key] = val
            filled += 1

        if src.get("ss_note"):
            row["ss_note"] = src["ss_note"]
        elif row.get("ss_kwh") is not None and row.get("ss_note") in (
            None,
            "pending_external_spreadsheet",
        ):
            row["ss_note"] = "full_parity_workbook"

        # Recompute payback/ROI from capital + ss_usd when parity omitted them.
        capital = _f(row.get("capital_usd"))
        ss_usd = _f(row.get("ss_usd"))
        if row.get("payback_yr_ss") is None and capital is not None and ss_usd is not None:
            row["payback_yr_ss"] = _payback(capital, ss_usd)
        if row.get("roi_ss") is None and capital is not None and ss_usd is not None:
            row["roi_ss"] = _roi(capital, ss_usd)

        if row.get("ss_kwh") is not None or row.get("ss_usd") is not None:
            if row.get("ep_kwh") is not None:
                row["status"] = "ss_ep_ready"
            else:
                row["status"] = "ss_ready"

    if filled:
        ss_meta = dict(compare_payload.get("spreadsheet") or {})
        ss_meta["status"] = "full_parity"
        ss_meta["path"] = str(path)
        ss_meta["note"] = (
            ss_meta.get("note")
            or "Spreadsheet columns from ecm_full_parity_compare.json (merge-if-present)."
        )
        compare_payload["spreadsheet"] = ss_meta
        honesty = compare_payload.get("honesty") or ""
        tip = "Spreadsheet ss_* merged from ecm_full_parity_compare.json when present."
        if tip not in honesty:
            compare_payload["honesty"] = (honesty + " " + tip).strip()

    return compare_payload


def load_compare(
    path: Path | str,
    *,
    reports_dir: Path | str | None = None,
    merge_full_parity: bool = True,
) -> dict[str, Any] | None:
    path = Path(path)
    if not path.is_file():
        return None
    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        return None
    if merge_full_parity:
        reports = Path(reports_dir) if reports_dir is not None else path.parent
        merge_full_parity_ss(payload, reports)
    return payload


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
    "FULL_PARITY_COMPARE_NAME",
    "compare_path",
    "full_parity_compare_path",
    "discover_notebook_xlsx",
    "build_compare_from_cascade",
    "merge_full_parity_ss",
    "write_compare",
    "load_compare",
    "empty_compare_stub",
    "capital_for_measure",
]

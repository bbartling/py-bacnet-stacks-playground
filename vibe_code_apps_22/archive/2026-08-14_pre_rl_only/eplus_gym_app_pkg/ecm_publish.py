"""Normalize agent ECM payloads into ``site_ecm_compare_v1`` for Streamlit.

Agents publish ``reports/ecm_compare.json`` after open-fdd ``ECMJob`` workbooks
and staged EnergyPlus runs. Never invent spreadsheet savings numbers.
"""
from __future__ import annotations

import json
import os
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from eplus_gym_app.ecm_panel import SCHEMA, DEFAULT_COMPARE_NAME, empty_ecm_stub

NOTEBOOKS_REL = Path("reports") / "notebooks"


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
    if capital is None or capital <= 0 or annual_usd is None:
        return None
    return round(annual_usd / capital, 3)


def normalize_measure(raw: dict[str, Any]) -> dict[str, Any]:
    """Map vibe20 / open-fdd twin_compare rows onto site_ecm_compare_v1 fields."""
    mid = (
        raw.get("measure_id")
        or raw.get("measure")
        or raw.get("id")
        or raw.get("name")
        or "unknown"
    )
    ss_kwh = _f(
        raw.get("ss_kwh", raw.get("fitted_sheet_kwh", raw.get("spreadsheet_kwh")))
    )
    ep_kwh = _f(raw.get("ep_kwh", raw.get("eplus_kwh")))
    ss_usd = _f(raw.get("ss_usd", raw.get("fitted_sheet_usd", raw.get("spreadsheet_usd"))))
    ep_usd = _f(raw.get("ep_usd", raw.get("eplus_usd")))
    capital = _f(raw.get("capital_usd", raw.get("capital")))
    status = str(raw.get("status") or "published")
    out: dict[str, Any] = {
        "measure_id": str(mid),
        "ss_kwh": ss_kwh,
        "ep_kwh": ep_kwh,
        "ss_usd": ss_usd,
        "ep_usd": ep_usd,
        "capital_usd": capital,
        "payback_yr_ss": _f(raw.get("payback_yr_ss")) or _payback(capital, ss_usd),
        "payback_yr_ep": _f(raw.get("payback_yr_ep")) or _payback(capital, ep_usd),
        "roi_ss": _f(raw.get("roi_ss")) or _roi(capital, ss_usd),
        "roi_ep": _f(raw.get("roi_ep")) or _roi(capital, ep_usd),
        "status": status,
    }
    if raw.get("name"):
        out["name"] = str(raw["name"])
    if raw.get("hours_provenance"):
        out["hours_provenance"] = str(raw["hours_provenance"])
    if raw.get("eplus_source"):
        out["eplus_source"] = str(raw["eplus_source"])
    return out


def from_twin_compare(twin: dict[str, Any] | None) -> list[dict[str, Any]]:
    """Extract measures from open-fdd ``attach_twin_compare`` payload."""
    if not isinstance(twin, dict):
        return []
    rows = twin.get("measures")
    if not isinstance(rows, list):
        return []
    return [normalize_measure(m) for m in rows if isinstance(m, dict)]


def normalize_compare_payload(raw: Any) -> dict[str, Any]:
    """Coerce arbitrary agent JSON into ``site_ecm_compare_v1``."""
    if not isinstance(raw, dict):
        return empty_ecm_stub()
    measures_in = raw.get("measures")
    if not isinstance(measures_in, list):
        # open-fdd twin_compare nested under twin_compare / attach_twin_compare
        twin = raw.get("twin_compare") or raw.get("attach_twin_compare")
        measures = from_twin_compare(twin if isinstance(twin, dict) else raw)
    else:
        measures = [normalize_measure(m) for m in measures_in if isinstance(m, dict)]
    out = empty_ecm_stub()
    out["status"] = str(raw.get("status") or ("ok" if measures else "empty"))
    out["measures"] = measures
    if raw.get("note"):
        out["note"] = str(raw["note"])
    elif measures:
        out["note"] = (
            "Spreadsheet (ss_*) vs EnergyPlus (ep_*). "
            "Agents publish; champion IDF untouched."
        )
    for key in ("workbook", "xlsx", "provenance", "updated_at"):
        if key in raw and raw[key] is not None:
            out[key] = raw[key]
    return out


def compare_path(site: Path | str) -> Path:
    return Path(site) / "reports" / DEFAULT_COMPARE_NAME


def save_ecm_compare(site: Path | str, payload: dict[str, Any]) -> Path:
    """Write normalized compare JSON under the site reports folder."""
    doc = normalize_compare_payload(payload)
    doc["schema"] = SCHEMA
    doc["updated_at"] = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    path = compare_path(site)
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_name(f".{path.name}.{os.getpid()}.tmp")
    tmp.write_text(json.dumps(doc, indent=2) + "\n", encoding="utf-8")
    os.replace(tmp, path)
    return path


def discover_notebook_xlsx(site: Path | str) -> list[Path]:
    """Recursive ``*.xlsx`` under ``reports/notebooks/**`` (skip Excel locks)."""
    root = Path(site) / NOTEBOOKS_REL
    if not root.is_dir():
        return []
    return sorted(
        p
        for p in root.rglob("*.xlsx")
        if p.is_file() and not p.name.startswith("~$")
    )


def latest_notebook_xlsx(site: Path | str) -> Path | None:
    paths = discover_notebook_xlsx(site)
    if not paths:
        return None
    return max(paths, key=lambda p: p.stat().st_mtime)


__all__ = [
    "NOTEBOOKS_REL",
    "normalize_measure",
    "from_twin_compare",
    "normalize_compare_payload",
    "compare_path",
    "save_ecm_compare",
    "discover_notebook_xlsx",
    "latest_notebook_xlsx",
]

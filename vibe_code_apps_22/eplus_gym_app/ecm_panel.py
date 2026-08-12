"""Read published ``reports/ecm_compare.json`` for the ECMs tab."""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import pandas as pd

SCHEMA = "site_ecm_compare_v1"
DEFAULT_COMPARE_NAME = "ecm_compare.json"


def empty_ecm_stub() -> dict[str, Any]:
    return {
        "schema": SCHEMA,
        "measures": [],
        "status": "empty",
        "note": "Agents publish reports/ecm_compare.json after ECM runs.",
    }


def load_ecm_compare(site: Path | str) -> dict[str, Any]:
    """Load ``{site}/reports/ecm_compare.json`` or an empty stub."""
    root = Path(site)
    path = root / "reports" / DEFAULT_COMPARE_NAME
    if not path.is_file():
        return empty_ecm_stub()
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return empty_ecm_stub()
    if not isinstance(payload, dict):
        return empty_ecm_stub()
    if "measures" not in payload or not isinstance(payload.get("measures"), list):
        payload = dict(payload)
        payload["measures"] = list(payload.get("measures") or [])
    return payload


def ecm_compare_table(payload: dict[str, Any] | None) -> pd.DataFrame:
    """Flatten compare payload measures into a display DataFrame."""
    rows: list[dict[str, Any]] = []
    for m in (payload or {}).get("measures") or []:
        if not isinstance(m, dict):
            continue
        rows.append(
            {
                "measure": m.get("measure_id") or m.get("measure") or m.get("id"),
                "ss_kWh": m.get("ss_kwh"),
                "ep_kWh": m.get("ep_kwh"),
                "ss_$": m.get("ss_usd"),
                "ep_$": m.get("ep_usd"),
                "capital_$": m.get("capital_usd"),
                "payback_ss_yr": m.get("payback_yr_ss"),
                "payback_ep_yr": m.get("payback_yr_ep"),
                "ROI_ss": m.get("roi_ss"),
                "ROI_ep": m.get("roi_ep"),
                "status": m.get("status"),
            }
        )
    return pd.DataFrame(rows)


__all__ = [
    "SCHEMA",
    "DEFAULT_COMPARE_NAME",
    "empty_ecm_stub",
    "load_ecm_compare",
    "ecm_compare_table",
]

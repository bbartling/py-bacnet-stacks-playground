"""Geometry summary → pretty tables for Streamlit Building tab."""
from __future__ import annotations

from typing import Any

import pandas as pd


def envelope_table(summary: dict[str, Any]) -> pd.DataFrame:
    """Flat key/value envelope metrics from ``IdfGeometry.summary()``."""
    bbox = summary.get("bbox_ft") or {}
    rows = [
        ("Surfaces", summary.get("n_surfaces")),
        ("Zones", summary.get("n_zones")),
        ("Fenestration", summary.get("n_fenestration")),
        ("BBox X (ft)", bbox.get("dx")),
        ("BBox Y (ft)", bbox.get("dy")),
        ("BBox Z (ft)", bbox.get("dz")),
        ("Wall area (m²)", summary.get("wall_area_m2")),
        ("Window area (m²)", summary.get("window_area_m2")),
        ("Roof area (m²)", summary.get("roof_area_m2")),
        ("WWR", summary.get("wwr")),
        ("WWR %", summary.get("wwr_pct")),
        ("Source", summary.get("source")),
    ]
    return pd.DataFrame(
        [(m, "" if v is None else str(v)) for m, v in rows],
        columns=["Metric", "Value"],
    )


def zones_table(summary: dict[str, Any]) -> pd.DataFrame:
    zones = list(summary.get("zones") or [])
    if not zones:
        return pd.DataFrame(columns=["Zone"])
    return pd.DataFrame({"Zone": zones})


def knobs_table(knobs: dict[str, Any]) -> pd.DataFrame:
    if not knobs:
        return pd.DataFrame(columns=["Knob", "Value"])
    rows = [(str(k), "" if v is None else str(v)) for k, v in knobs.items()]
    return pd.DataFrame(rows, columns=["Knob", "Value"])

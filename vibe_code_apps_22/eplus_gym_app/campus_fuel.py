"""vibe20-style Campus + monthly fuel bill loading (viewer-side only).

Mirrors ``wattlab.benchmarks.meters.Campus`` / ``load_bill_csv`` shapes without
importing vibe20 — agents publish ``campus.json`` + sibling bill CSVs; Streamlit
only picks and renders.
"""
from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import pandas as pd

KBTU_PER_KWH = 3.412


def _find_col(cols: list[str], *needles: str) -> str | None:
    for c in cols:
        lc = c.lower()
        if all(n in lc for n in needles):
            return c
    return None


def load_bill_csv(
    path: str | Path,
    column_map: dict[str, str] | None = None,
) -> pd.DataFrame:
    """Tidy monthly bills: month, usage, optional cost_usd / demand_kw."""
    df = pd.read_csv(path, thousands=",")
    cols = list(df.columns)
    cmap = {str(k): str(v) for k, v in (column_map or {}).items()}

    def _mapped(logical: str, *needles: str, fallback: str | None = None) -> str | None:
        if logical in cmap and cmap[logical] in df.columns:
            return cmap[logical]
        found = _find_col(cols, *needles) if needles else None
        return found or fallback

    month_col = _mapped("month", "month", fallback=cols[0])
    usage_col = (
        _mapped("usage", "kwh")
        or _mapped("usage", "usage")
        or (cols[1] if len(cols) > 1 else cols[0])
    )
    cost_col = _mapped("cost_usd", "charges") or _mapped("cost_usd", "cost")
    demand_col = _mapped("demand_kw", "billed", "demand") or _mapped(
        "demand_kw", "demand"
    )

    out = pd.DataFrame(
        {
            "month": df[month_col].astype(str).str.strip().str[:7],
            "usage": pd.to_numeric(df[usage_col], errors="coerce"),
        }
    )
    out["cost_usd"] = (
        pd.to_numeric(df[cost_col], errors="coerce") if cost_col else float("nan")
    )
    if demand_col is not None:
        out["demand_kw"] = pd.to_numeric(df[demand_col], errors="coerce")

    agg: dict[str, str] = {"usage": "sum", "cost_usd": "sum"}
    if "demand_kw" in out.columns:
        agg["demand_kw"] = "max"
    return out.groupby("month", as_index=False).agg(agg).sort_values("month").reset_index(
        drop=True
    )


@dataclass(frozen=True)
class BuildingRef:
    building_id: str
    label: str
    floor_area_ft2: float
    property_type: str = "office"


@dataclass
class Meter:
    meter_id: str
    fuel: str
    unit: str
    serves: list[str]
    bills: pd.DataFrame
    file: str = ""
    allocation: dict[str, Any] = field(default_factory=dict)


@dataclass
class Campus:
    campus_id: str
    label: str
    buildings: list[BuildingRef]
    meters: list[Meter]
    notes: str = ""
    source: str = ""
    lat: float | None = None
    lon: float | None = None
    site_ref: str | None = None

    @classmethod
    def from_json(cls, path: str | Path) -> "Campus":
        p = Path(path)
        if not p.is_file():
            raise FileNotFoundError(f"Campus config not found: {p}")
        doc = json.loads(p.read_text(encoding="utf-8"))
        buildings = [
            BuildingRef(
                building_id=str(b["building_id"]),
                label=str(b.get("label") or b["building_id"]),
                floor_area_ft2=float(b["floor_area_ft2"]),
                property_type=str(b.get("property_type") or "office"),
            )
            for b in doc.get("buildings", [])
        ]
        meters: list[Meter] = []
        for m in doc.get("meters", []):
            fpath = p.parent / str(m.get("file") or "")
            if not fpath.is_file():
                raise FileNotFoundError(
                    f"Campus {p} references missing bill CSV: {fpath.name}"
                )
            cmap = m.get("bill_columns") or doc.get("bill_columns")
            meters.append(
                Meter(
                    meter_id=str(m["meter_id"]),
                    fuel=str(m["fuel"]),
                    unit=str(
                        m.get("unit")
                        or ("kwh" if m["fuel"] == "electricity" else "mcf")
                    ),
                    serves=[str(s) for s in m.get("serves", [])],
                    bills=load_bill_csv(fpath, column_map=cmap),
                    file=str(m.get("file") or fpath.name),
                    allocation=dict(m.get("allocation") or {}),
                )
            )
        lat = doc.get("lat", doc.get("latitude"))
        lon = doc.get("lon", doc.get("longitude"))
        return cls(
            campus_id=str(doc.get("campus_id") or p.stem),
            label=str(doc.get("label") or doc.get("campus_id") or p.stem),
            buildings=buildings,
            meters=meters,
            notes=str(doc.get("notes") or ""),
            source=str(p),
            lat=float(lat) if lat is not None else None,
            lon=float(lon) if lon is not None else None,
            site_ref=(
                str(doc["siteRef"])
                if doc.get("siteRef")
                else (str(doc["site_ref"]) if doc.get("site_ref") else None)
            ),
        )

    def electric_monthly(self) -> pd.DataFrame:
        frames = []
        for m in self.meters:
            if m.fuel != "electricity":
                continue
            f = m.bills.copy()
            f["meter_id"] = m.meter_id
            f["unit"] = m.unit
            frames.append(f)
        if not frames:
            return pd.DataFrame(columns=["month", "usage", "cost_usd", "meter_id"])
        return pd.concat(frames, ignore_index=True)

    def site_eui_kbtu_ft2(self, window: list[str] | None = None) -> float | None:
        area = sum(b.floor_area_ft2 for b in self.buildings)
        if area <= 0:
            return None
        elec = self.electric_monthly()
        if elec.empty:
            return None
        if window:
            elec = elec[elec["month"].isin(window)]
        kwh = float(elec["usage"].sum())
        return (kwh * KBTU_PER_KWH) / area

"""Utility-meter relationship model + bill math.

The Liberty campus proved the pattern: one shared electric meter feeding two
buildings while gas stays building-specific. This module makes that a
first-class, auditable concept instead of a spreadsheet hack:

- robust monthly bill CSV loading (thousands separators, duplicate bill months
  from split billing periods, missing months),
- a ``Campus`` model (buildings + meters + who-serves-whom) loaded from a small
  JSON sidecar next to the bill files,
- shared-meter **allocation modes** (``equal`` / ``area_weighted`` /
  ``gas_share`` / ``manual``) that are scenarios, not truth — shown
  side-by-side until submetered evidence exists,
- latest common complete 12-month window selection across all meters,
- site-EUI math in the industry's units (kBtu/ft²-year).

Conversions follow EIA: 1 kWh = 3,412 Btu; 1 Mcf natural gas ≈ 1.037 MMBtu.
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import pandas as pd

KBTU_PER_KWH = 3.412
KBTU_PER_MCF = 1037.0  # 1.037 MMBtu
THERMS_PER_MCF = 10.37

ALLOCATION_METHODS = ("area_weighted", "equal", "gas_share", "manual")


# ---------------------------------------------------------------------------
# Bill CSV loading
# ---------------------------------------------------------------------------

def _find_col(cols: list[str], *needles: str) -> str | None:
    for c in cols:
        lc = c.lower()
        if all(n in lc for n in needles):
            return c
    return None


def load_bill_csv(path: str | Path) -> pd.DataFrame:
    """Load a monthly utility bill summary CSV into a tidy frame.

    Returns columns: ``month`` (YYYY-MM str), ``usage`` (kWh or Mcf),
    ``cost_usd`` and, when present, ``demand_kw``. Duplicate bill months
    (split billing periods) are summed; demand takes the month max.
    """
    df = pd.read_csv(path, thousands=",")
    cols = list(df.columns)
    month_col = _find_col(cols, "month") or cols[0]
    usage_col = _find_col(cols, "kwh") or _find_col(cols, "usage") or cols[1]
    cost_col = _find_col(cols, "charges") or _find_col(cols, "cost")
    demand_col = _find_col(cols, "billed", "demand")

    out = pd.DataFrame({
        "month": df[month_col].astype(str).str.strip().str[:7],
        "usage": pd.to_numeric(df[usage_col], errors="coerce"),
    })
    out["cost_usd"] = pd.to_numeric(df[cost_col], errors="coerce") if cost_col else float("nan")
    if demand_col is not None:
        out["demand_kw"] = pd.to_numeric(df[demand_col], errors="coerce")

    agg: dict[str, str] = {"usage": "sum", "cost_usd": "sum"}
    if "demand_kw" in out.columns:
        agg["demand_kw"] = "max"
    out = out.groupby("month", as_index=False).agg(agg).sort_values("month")
    return out.reset_index(drop=True)


# ---------------------------------------------------------------------------
# Campus model
# ---------------------------------------------------------------------------

@dataclass(frozen=True)
class BuildingRef:
    building_id: str
    label: str
    floor_area_ft2: float
    property_type: str = "office"


@dataclass
class Meter:
    meter_id: str
    fuel: str  # "electricity" | "gas"
    unit: str  # "kwh" | "mcf"
    serves: list[str]
    bills: pd.DataFrame
    allocation: dict[str, Any] = field(default_factory=dict)

    @property
    def shared(self) -> bool:
        return len(self.serves) > 1

    def months(self) -> set[str]:
        return set(self.bills["month"])

    def usage_in(self, window: list[str]) -> float:
        sel = self.bills[self.bills["month"].isin(window)]
        return float(sel["usage"].sum())

    def cost_in(self, window: list[str]) -> float:
        sel = self.bills[self.bills["month"].isin(window)]
        return float(sel["cost_usd"].sum())


@dataclass
class Campus:
    campus_id: str
    label: str
    buildings: list[BuildingRef]
    meters: list[Meter]
    notes: str = ""
    source: str = ""

    @classmethod
    def from_json(cls, path: str | Path) -> "Campus":
        p = Path(path)
        if not p.is_file():
            raise FileNotFoundError(
                f"Campus config not found: {p}. "
                "Checked-in demo: tests/fixtures/shared_meter_campus/campus.json. "
                "Local Liberty CSVs under examples/liberty/ are gitignored — "
                "copy them beside campus.json or point Studio at the fixture."
            )
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
        missing = [
            str(m.get("file"))
            for m in doc.get("meters", [])
            if not (p.parent / str(m.get("file") or "")).is_file()
        ]
        if missing:
            raise FileNotFoundError(
                f"Campus {p} references missing bill CSV(s): {', '.join(missing)}. "
                "Use tests/fixtures/shared_meter_campus/ for the privacy-safe demo, "
                "or place local meter CSVs next to campus.json (examples/liberty CSVs "
                "are gitignored on purpose)."
            )
        meters = [
            Meter(
                meter_id=str(m["meter_id"]),
                fuel=str(m["fuel"]),
                unit=str(m.get("unit") or ("kwh" if m["fuel"] == "electricity" else "mcf")),
                serves=[str(s) for s in m.get("serves", [])],
                bills=load_bill_csv(p.parent / m["file"]),
                allocation=dict(m.get("allocation") or {}),
            )
            for m in doc.get("meters", [])
        ]
        return cls(
            campus_id=str(doc.get("campus_id") or p.stem),
            label=str(doc.get("label") or doc.get("campus_id") or p.stem),
            buildings=buildings,
            meters=meters,
            notes=str(doc.get("notes") or ""),
            source=str(p),
        )

    def building(self, building_id: str) -> BuildingRef:
        for b in self.buildings:
            if b.building_id == building_id:
                return b
        raise KeyError(building_id)

    @property
    def total_area_ft2(self) -> float:
        return float(sum(b.floor_area_ft2 for b in self.buildings))

    def monthly_frame(self) -> pd.DataFrame:
        """Tidy long frame of every meter's bills for plotting."""
        frames = []
        for m in self.meters:
            f = m.bills.copy()
            f.insert(0, "meter_id", m.meter_id)
            f.insert(1, "fuel", m.fuel)
            f.insert(2, "unit", m.unit)
            frames.append(f)
        return pd.concat(frames, ignore_index=True) if frames else pd.DataFrame()


def year_month_matrix(bills: pd.DataFrame) -> pd.DataFrame:
    """Pivot a tidy bill frame to a years × months usage matrix.

    Rows are calendar years (newest first), columns 1–12; missing months stay
    NaN so heatmaps/workbook views show gaps honestly instead of zeros.
    """
    f = bills.copy()
    f["year"] = f["month"].str[:4].astype(int)
    f["mon"] = f["month"].str[5:7].astype(int)
    mat = f.pivot_table(index="year", columns="mon", values="usage", aggfunc="sum")
    return mat.reindex(columns=range(1, 13)).sort_index(ascending=False)


# ---------------------------------------------------------------------------
# Annual windows
# ---------------------------------------------------------------------------

def _month_index(month: str) -> int:
    y, m = month.split("-")
    return int(y) * 12 + int(m) - 1


def _month_str(idx: int) -> str:
    return f"{idx // 12:04d}-{idx % 12 + 1:02d}"


def latest_complete_window(month_sets: list[set[str]], months: int = 12) -> list[str] | None:
    """Latest run of ``months`` consecutive months present in every set."""
    if not month_sets:
        return None
    common = set.intersection(*month_sets)
    for end in sorted(common, reverse=True):
        end_idx = _month_index(end)
        seq = [_month_str(end_idx - i) for i in range(months - 1, -1, -1)]
        if all(m in common for m in seq):
            return seq
    return None


# ---------------------------------------------------------------------------
# Shared-meter allocation + annual summary
# ---------------------------------------------------------------------------

def _building_shares(
    campus: Campus,
    meter: Meter,
    method: str,
    window: list[str],
    manual_shares: dict[str, float] | None,
) -> dict[str, float]:
    served = meter.serves
    if not meter.shared:
        return {served[0]: 1.0}

    if method == "manual":
        if not manual_shares:
            raise ValueError("manual allocation requires manual_shares")
        total = sum(manual_shares.get(b, 0.0) for b in served)
        if total <= 0:
            raise ValueError("manual_shares must sum > 0 across served buildings")
        return {b: manual_shares.get(b, 0.0) / total for b in served}

    if method == "equal":
        return {b: 1.0 / len(served) for b in served}

    if method == "area_weighted":
        areas = {b: campus.building(b).floor_area_ft2 for b in served}
        total = sum(areas.values())
        return {b: a / total for b, a in areas.items()}

    if method == "gas_share":
        # Proxy: split by each building's share of building-specific gas use.
        gas_use = {b: 0.0 for b in served}
        for m in campus.meters:
            if m.fuel == "gas" and not m.shared and m.serves[0] in gas_use:
                gas_use[m.serves[0]] += m.usage_in(window)
        total = sum(gas_use.values())
        if total <= 0:
            # No gas signal — fall back to area weighting.
            return _building_shares(campus, meter, "area_weighted", window, None)
        return {b: u / total for b, u in gas_use.items()}

    raise ValueError(f"unknown allocation method: {method!r} (use one of {ALLOCATION_METHODS})")


def annual_summary(
    campus: Campus,
    *,
    allocation: str = "area_weighted",
    manual_shares: dict[str, float] | None = None,
    window: list[str] | None = None,
) -> dict[str, Any]:
    """Annualized per-building + campus energy/EUI table over a common window.

    Shared meters are split per ``allocation``; every building row records the
    method used so downstream ROI math stays auditable.
    """
    if window is None:
        window = latest_complete_window([m.months() for m in campus.meters])
    if not window:
        raise ValueError("no common complete 12-month window across all meters")

    per: dict[str, dict[str, float]] = {
        b.building_id: {"kwh": 0.0, "mcf": 0.0, "elec_cost_usd": 0.0, "gas_cost_usd": 0.0}
        for b in campus.buildings
    }
    for meter in campus.meters:
        usage = meter.usage_in(window)
        cost = meter.cost_in(window)
        shares = _building_shares(campus, meter, allocation, window, manual_shares)
        for bid, share in shares.items():
            if meter.fuel == "electricity":
                per[bid]["kwh"] += usage * share
                per[bid]["elec_cost_usd"] += cost * share
            else:
                per[bid]["mcf"] += usage * share
                per[bid]["gas_cost_usd"] += cost * share

    rows = []
    for b in campus.buildings:
        u = per[b.building_id]
        elec_kbtu = u["kwh"] * KBTU_PER_KWH
        gas_kbtu = u["mcf"] * KBTU_PER_MCF
        rows.append({
            "building_id": b.building_id,
            "label": b.label,
            "property_type": b.property_type,
            "floor_area_ft2": b.floor_area_ft2,
            "kwh": round(u["kwh"], 1),
            "kwh_per_ft2": round(u["kwh"] / b.floor_area_ft2, 2),
            "mcf": round(u["mcf"], 1),
            "therms": round(u["mcf"] * THERMS_PER_MCF, 1),
            "elec_kbtu_ft2": round(elec_kbtu / b.floor_area_ft2, 1),
            "gas_kbtu_ft2": round(gas_kbtu / b.floor_area_ft2, 1),
            "site_eui_kbtu_ft2": round((elec_kbtu + gas_kbtu) / b.floor_area_ft2, 1),
            "elec_cost_usd": round(u["elec_cost_usd"], 2),
            "gas_cost_usd": round(u["gas_cost_usd"], 2),
            "allocation": allocation,
        })

    tot_kwh = sum(r["kwh"] for r in rows)
    tot_mcf = sum(r["mcf"] for r in rows)
    area = campus.total_area_ft2
    campus_row = {
        "kwh": round(tot_kwh, 1),
        "mcf": round(tot_mcf, 1),
        "kwh_per_ft2": round(tot_kwh / area, 2),
        "site_eui_kbtu_ft2": round((tot_kwh * KBTU_PER_KWH + tot_mcf * KBTU_PER_MCF) / area, 1),
        "floor_area_ft2": area,
        "cost_usd": round(sum(r["elec_cost_usd"] + r["gas_cost_usd"] for r in rows), 2),
    }
    return {
        "campus_id": campus.campus_id,
        "window": {"start": window[0], "end": window[-1], "months": len(window)},
        "allocation": allocation,
        "buildings": rows,
        "campus": campus_row,
    }


def allocation_scenarios(
    campus: Campus,
    *,
    window: list[str] | None = None,
    manual_shares: dict[str, float] | None = None,
) -> list[dict[str, Any]]:
    """Side-by-side per-building EUIs under every applicable allocation mode."""
    out: list[dict[str, Any]] = []
    for method in ALLOCATION_METHODS:
        if method == "manual" and not manual_shares:
            continue
        try:
            s = annual_summary(campus, allocation=method, manual_shares=manual_shares, window=window)
        except ValueError:
            continue
        for r in s["buildings"]:
            out.append({
                "allocation": method,
                "building_id": r["building_id"],
                "site_eui_kbtu_ft2": r["site_eui_kbtu_ft2"],
                "kwh": r["kwh"],
                "mcf": r["mcf"],
            })
    return out

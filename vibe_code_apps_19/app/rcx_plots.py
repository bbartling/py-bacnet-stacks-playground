"""RCx multi-equipment plot collectors — prebuilt mechanical categories + generic picker."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Callable

import numpy as np
import pandas as pd

from app.role_map import apply_role_map
from app.site_model import equipment_type_from_id
from app.weather_psychrometrics import prefer_web_oat


@dataclass(frozen=True)
class RcxPreset:
    id: str
    title: str
    description: str
    role: str
    equipment_types: tuple[str, ...]
    chart: str  # "timeseries" | "box" | "scatter_oat"
    filter_fan_on: bool = False
    y_role_alt: str | None = None  # for scatter: plant temp role


PRESETS: list[RcxPreset] = [
    RcxPreset("zone_temps", "All zone temperatures", "Every VAV/zone space temp on one chart.", "zone_t", ("VAV",), "timeseries"),
    RcxPreset("ahu_dats", "All AHU discharge air temps", "SAT / DAT for every AHU.", "sat", ("AHU",), "timeseries"),
    RcxPreset("ahu_mats", "All AHU mixed air temps", "MAT across AHUs.", "mat", ("AHU",), "timeseries"),
    RcxPreset("ahu_rats", "All AHU return air temps", "RAT across AHUs.", "rat", ("AHU",), "timeseries"),
    RcxPreset("ahu_dampers", "All AHU OA dampers", "OA damper % across AHUs.", "oa_damper_pct", ("AHU",), "timeseries"),
    RcxPreset(
        "duct_static_box",
        "AHU duct static (fan on)",
        "Box plot of duct static while fan proven on — look for high fixed static (reset opportunity).",
        "duct_static",
        ("AHU",),
        "box",
        filter_fan_on=True,
    ),
    RcxPreset(
        "hw_reset_scatter",
        "Hot-water reset vs web OAT",
        "HW supply temp vs Open-Meteo dry bulb (scatter).",
        "hw_supply_t",
        ("BOILER", "AHU"),
        "scatter_oat",
    ),
    RcxPreset(
        "chw_reset_scatter",
        "Chilled-water reset vs web OAT",
        "CHW supply temp vs Open-Meteo dry bulb (scatter).",
        "chw_supply_t",
        ("CHW_PLANT", "CHILLER", "AHU"),
        "scatter_oat",
    ),
    RcxPreset(
        "cw_reset_scatter",
        "Condenser-water vs web wet-bulb",
        "CW supply vs wet-bulb (or dry bulb if WB missing).",
        "cw_supply_t",
        ("CHW_PLANT", "CHILLER", "COOLING_TOWER"),
        "scatter_oat",
        y_role_alt="wx_oa_wetbulb",
    ),
    RcxPreset("vav_flows", "All VAV airflow", "Zone airflow across boxes.", "zone_flow", ("VAV",), "timeseries"),
    RcxPreset("fan_speeds", "All AHU fan speeds", "Fan command % across AHUs.", "fan_cmd", ("AHU",), "timeseries"),
]


def _etype(eq_id: str, raw: pd.DataFrame) -> str:
    return str(raw.attrs.get("equipment_type") or equipment_type_from_id(eq_id)).upper()


def _fan_on(df: pd.DataFrame) -> pd.Series:
    for role in ("fan_status", "fan_cmd"):
        if role in df.columns and df[role].notna().any():
            num = pd.to_numeric(df[role], errors="coerce")
            if num.notna().any():
                scaled = num.where(num <= 1.5, num / 100.0)
                return scaled.fillna(0) > 0.05
            return df[role].fillna(False).astype(bool)
    return pd.Series(True, index=df.index)


def collect_role_series(
    frames: dict[str, pd.DataFrame],
    role_map: dict,
    *,
    role: str,
    equipment_types: tuple[str, ...] | None = None,
    equipment_ids: list[str] | None = None,
    filter_fan_on: bool = False,
) -> dict[str, pd.Series]:
    """Map equipment_id → numeric series for a logical role."""
    out: dict[str, pd.Series] = {}
    for eq_id, raw in frames.items():
        if equipment_ids is not None and eq_id not in equipment_ids:
            continue
        et = _etype(eq_id, raw)
        if equipment_types:
            allowed = {t.upper() for t in equipment_types}
            if et not in allowed and not any(t in eq_id.upper() for t in allowed):
                continue
        mapped = apply_role_map(raw, eq_id, role_map)
        if role not in mapped.columns or mapped[role].notna().sum() == 0:
            continue
        s = pd.to_numeric(mapped[role], errors="coerce")
        if filter_fan_on:
            on = _fan_on(mapped).reindex(s.index).fillna(False)
            s = s.where(on)
        if s.notna().any():
            out[eq_id] = s
    return out


def series_summary_stats(series_map: dict[str, pd.Series], *, outlier_z: float = 2.5) -> pd.DataFrame:
    """Per-series summary + outlier sample counts (z-score vs cohort mean of means)."""
    rows: list[dict[str, Any]] = []
    means = []
    for eq_id, s in series_map.items():
        num = pd.to_numeric(s, errors="coerce").dropna()
        if num.empty:
            continue
        means.append(float(num.mean()))
        rows.append(
            {
                "equipment_id": eq_id,
                "n": int(len(num)),
                "mean": round(float(num.mean()), 3),
                "std": round(float(num.std(ddof=0)), 3) if len(num) > 1 else 0.0,
                "min": round(float(num.min()), 3),
                "p25": round(float(num.quantile(0.25)), 3),
                "p50": round(float(num.quantile(0.5)), 3),
                "p75": round(float(num.quantile(0.75)), 3),
                "max": round(float(num.max()), 3),
            }
        )
    if not rows:
        return pd.DataFrame(
            columns=["equipment_id", "n", "mean", "std", "min", "p25", "p50", "p75", "max", "outlier"]
        )
    df = pd.DataFrame(rows)
    if len(means) >= 3:
        mu, sd = float(np.mean(means)), float(np.std(means))
        if sd > 1e-9:
            df["outlier"] = (df["mean"] - mu).abs() / sd >= outlier_z
        else:
            df["outlier"] = False
    else:
        df["outlier"] = False
    return df.sort_values("equipment_id")


def outlier_equipment_ids(stats: pd.DataFrame) -> set[str]:
    if stats is None or stats.empty or "outlier" not in stats.columns:
        return set()
    return set(stats.loc[stats["outlier"], "equipment_id"].astype(str))


def collect_oat_scatter(
    frames: dict[str, pd.DataFrame],
    role_map: dict,
    *,
    y_role: str,
    weather: pd.DataFrame | None,
    equipment_types: tuple[str, ...] | None = None,
    x_prefer: str = "web",  # web drybulb, or wetbulb
) -> pd.DataFrame:
    """Long dataframe: timestamp, equipment_id, oat, y for scatter plots."""
    rows: list[dict[str, Any]] = []
    for eq_id, raw in frames.items():
        et = _etype(eq_id, raw)
        if equipment_types and et not in {t.upper() for t in equipment_types}:
            if not any(t.upper() in eq_id.upper() for t in equipment_types):
                continue
        mapped = apply_role_map(raw, eq_id, role_map)
        if y_role not in mapped.columns or mapped[y_role].notna().sum() == 0:
            continue
        if x_prefer == "wetbulb" and weather is not None and "wx_oa_wetbulb" in weather.columns:
            oat = pd.to_numeric(weather["wx_oa_wetbulb"], errors="coerce").reindex(mapped.index)
        else:
            oat = prefer_web_oat(mapped, weather, prefer_web=True)
        if oat is None:
            continue
        y = pd.to_numeric(mapped[y_role], errors="coerce")
        tmp = pd.DataFrame({"oat": oat, "y": y}).dropna()
        for ts, row in tmp.iterrows():
            rows.append({"timestamp": ts, "equipment_id": eq_id, "oat": float(row["oat"]), "y": float(row["y"])})
    return pd.DataFrame(rows)


def preset_by_id(preset_id: str) -> RcxPreset | None:
    for p in PRESETS:
        if p.id == preset_id:
            return p
    return None

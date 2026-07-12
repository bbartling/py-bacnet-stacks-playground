"""RCx multi-equipment plot collectors — prebuilt mechanical categories + generic picker."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

import numpy as np
import pandas as pd

from app.role_map import apply_role_map
from app.site_model import resolve_equipment_type
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
        "ahu_sat_reset_scatter",
        "AHU discharge temp vs web OAT",
        "SAT / leave-air temp vs Open-Meteo dry bulb — look for SAT reset with outdoor air.",
        "sat",
        ("AHU",),
        "scatter_oat",
    ),
    RcxPreset(
        "hw_reset_scatter",
        "Hot-water leave temp vs web OAT",
        "HW supply / leave temp vs Open-Meteo dry bulb (boiler / HW plant reset).",
        "hw_supply_t",
        ("BOILER", "AHU"),
        "scatter_oat",
    ),
    RcxPreset(
        "chw_reset_scatter",
        "Chilled-water leave temp vs web OAT",
        "CHW supply / leave temp vs Open-Meteo dry bulb (chiller plant reset).",
        "chw_supply_t",
        ("CHW_PLANT", "CHILLER", "AHU"),
        "scatter_oat",
    ),
    RcxPreset(
        "cw_reset_scatter",
        "Condenser / tower water vs web wet-bulb",
        "CW supply vs wet-bulb (cooling-tower / condenser-water reset; dry bulb if WB missing).",
        "cw_supply_t",
        ("CHW_PLANT", "CHILLER", "COOLING_TOWER"),
        "scatter_oat",
        y_role_alt="wx_oa_wetbulb",
    ),
    RcxPreset("vav_flows", "All VAV airflow", "Zone airflow across boxes.", "zone_flow", ("VAV",), "timeseries"),
    RcxPreset("fan_speeds", "All AHU fan speeds", "Fan command % across AHUs.", "fan_cmd", ("AHU",), "timeseries"),
]


# Full existing RCx catalog freeze — agents must not delete any of these without an
# explicit product decision + vibe19_agent_spec/docs/DASHBOARD_CONTRACT.md update.
# New presets may be added to PRESETS; promote them into this set when they become
# part of the supported dashboard.
REQUIRED_RCX_PRESET_IDS: frozenset[str] = frozenset(
    {
        "zone_temps",
        "ahu_dats",
        "ahu_mats",
        "ahu_rats",
        "ahu_dampers",
        "duct_static_box",
        "ahu_sat_reset_scatter",
        "hw_reset_scatter",
        "chw_reset_scatter",
        "cw_reset_scatter",
        "vav_flows",
        "fan_speeds",
    }
)


def _etype(eq_id: str, raw: pd.DataFrame, role_map: dict | None = None) -> str:
    return resolve_equipment_type(eq_id, df=raw, role_map=role_map)


def operating_mask(df: pd.DataFrame) -> tuple[pd.Series | None, str]:
    """Boolean mask when equipment looks running, plus proof role label.

    AHU / fans: ``fan_status`` then ``fan_cmd``.
    VAV / zones: ``zone_flow`` above a small activity threshold when fan roles absent.
    Returns ``(None, "")`` when no usable proof columns exist.
    """
    for role in ("fan_status", "fan_cmd"):
        if role in df.columns and df[role].notna().any():
            num = pd.to_numeric(df[role], errors="coerce")
            if num.notna().any():
                scaled = num.where(num <= 1.5, num / 100.0)
                return scaled.fillna(0) > 0.05, role
            return df[role].fillna(False).astype(bool), role
    if "zone_flow" in df.columns and df["zone_flow"].notna().any():
        flow = pd.to_numeric(df["zone_flow"], errors="coerce")
        if flow.notna().any():
            # CFM: treat near-zero as off; threshold scales with typical max when available
            p95 = float(flow.quantile(0.95)) if flow.notna().sum() >= 5 else float(flow.max())
            thr = max(10.0, 0.05 * p95) if np.isfinite(p95) else 10.0
            return flow.fillna(0) > thr, "zone_flow"
    return None, ""


def _fan_on(df: pd.DataFrame) -> pd.Series:
    """Legacy helper: operating mask, or all-True when no proof (keeps old filter_fan_on behavior)."""
    mask, _ = operating_mask(df)
    if mask is None:
        return pd.Series(True, index=df.index)
    return mask


def collect_role_series(
    frames: dict[str, pd.DataFrame],
    role_map: dict,
    *,
    role: str,
    equipment_types: tuple[str, ...] | None = None,
    equipment_ids: list[str] | None = None,
    filter_fan_on: bool = False,
    fan_mode: str = "all",
) -> dict[str, pd.Series]:
    """Map equipment_id → numeric series for a logical role.

    ``fan_mode``: ``all`` | ``on`` | ``off`` using :func:`operating_mask`.
    ``filter_fan_on=True`` is equivalent to ``fan_mode="on"`` (preset compatibility).
    """
    mode = "on" if filter_fan_on else str(fan_mode or "all").lower()
    if mode not in {"all", "on", "off"}:
        mode = "all"
    out: dict[str, pd.Series] = {}
    for eq_id, raw in frames.items():
        if equipment_ids is not None and eq_id not in equipment_ids:
            continue
        et = _etype(eq_id, raw, role_map)
        if equipment_types:
            allowed = {t.upper() for t in equipment_types}
            # Typed membership only — no id-substring fallback
            if et not in allowed:
                continue
        mapped = apply_role_map(raw, eq_id, role_map)
        if role not in mapped.columns or mapped[role].notna().sum() == 0:
            continue
        s = pd.to_numeric(mapped[role], errors="coerce")
        if mode in {"on", "off"}:
            mask, _proof = operating_mask(mapped)
            if mask is None:
                # Preset filter_fan_on legacy: no proof → keep all samples.
                # Explicit fan_mode slices: skip equipment without proof.
                if not (filter_fan_on and mode == "on"):
                    continue
            else:
                on = mask.reindex(s.index).fillna(False)
                s = s.where(on if mode == "on" else ~on)
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


def fan_mode_summary_bundle(
    frames: dict[str, pd.DataFrame],
    role_map: dict,
    *,
    role: str,
    equipment_types: tuple[str, ...] | None,
    outlier_z: float = 2.5,
) -> tuple[dict[str, pd.DataFrame], str]:
    """Build summary stats for all / on / off slices. Returns (tables_by_mode, proof_caption)."""
    proof_labels: set[str] = set()
    for eq_id, raw in frames.items():
        et = _etype(eq_id, raw, role_map)
        if equipment_types and et not in {t.upper() for t in equipment_types}:
            continue
        mapped = apply_role_map(raw, eq_id, role_map)
        _mask, label = operating_mask(mapped)
        if label:
            proof_labels.add(label)
    tables: dict[str, pd.DataFrame] = {}
    for mode, key in (("all", "all"), ("on", "on"), ("off", "off")):
        series_map = collect_role_series(
            frames,
            role_map,
            role=role,
            equipment_types=equipment_types,
            fan_mode=mode,
        )
        tables[key] = series_summary_stats(series_map, outlier_z=outlier_z)
    caption = ""
    if proof_labels:
        caption = "Operating proof: " + ", ".join(sorted(proof_labels))
        if "zone_flow" in proof_labels:
            caption += " (VAV airflow used when fan roles absent)"
    else:
        caption = "No fan_status / fan_cmd / zone_flow mapped — on/off slices empty"
    return tables, caption


def cohort_wants_fan_slices(equipment_types: tuple[str, ...] | None) -> bool:
    """AHU / VAV(/HP) air-side cohorts get All / on / off summary tabs."""
    if not equipment_types:
        return True  # generic "all types" — still offer slices when proof exists
    air = {"AHU", "VAV", "HP", "RTU"}
    return bool(air.intersection({t.upper() for t in equipment_types}))


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
        et = _etype(eq_id, raw, role_map)
        if equipment_types and et not in {t.upper() for t in equipment_types}:
            # Typed membership only — no id-substring fallback
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


def rcx_preset_coverage(
    frames: dict[str, pd.DataFrame],
    role_map: dict,
    *,
    weather: pd.DataFrame | None = None,
    outlier_z: float = 2.5,
) -> pd.DataFrame:
    """Diagnostics table: one row per RCx preset with series/row/outlier counts."""
    rows: list[dict[str, Any]] = []
    for preset in PRESETS:
        empty_reason = ""
        series_count = 0
        row_count = 0
        outlier_count = 0
        if preset.chart == "scatter_oat":
            x_pref = "wetbulb" if preset.id == "cw_reset_scatter" else "web"
            long_df = collect_oat_scatter(
                frames,
                role_map,
                y_role=preset.role,
                weather=weather,
                equipment_types=preset.equipment_types,
                x_prefer=x_pref,
            )
            row_count = int(len(long_df))
            series_count = int(long_df["equipment_id"].nunique()) if row_count and "equipment_id" in long_df.columns else 0
            if row_count == 0:
                empty_reason = f"no mapped {preset.role} and/or web OAT for {','.join(preset.equipment_types)}"
        else:
            series_map = collect_role_series(
                frames,
                role_map,
                role=preset.role,
                equipment_types=preset.equipment_types,
                filter_fan_on=preset.filter_fan_on,
            )
            series_count = len(series_map)
            row_count = int(sum(int(s.notna().sum()) for s in series_map.values()))
            stats = series_summary_stats(series_map, outlier_z=outlier_z)
            outlier_count = int(stats["outlier"].sum()) if not stats.empty and "outlier" in stats.columns else 0
            if series_count == 0:
                empty_reason = f"no mapped {preset.role} for {','.join(preset.equipment_types)}"
                if preset.filter_fan_on:
                    empty_reason += " (fan-on filter)"
        rows.append(
            {
                "preset_id": preset.id,
                "title": preset.title,
                "chart_type": preset.chart,
                "role": preset.role,
                "series_count": series_count,
                "row_count": row_count,
                "outlier_count": outlier_count,
                "empty_reason": empty_reason,
            }
        )
    return pd.DataFrame(rows)

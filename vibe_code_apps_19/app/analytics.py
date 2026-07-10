"""Dataset analytics: date span, motor hours, mech-cooling OAT bins."""

from __future__ import annotations

import re
from typing import Any

import numpy as np
import pandas as pd

from app.role_map import apply_role_map
from app.site_model import equipment_type_from_id

# Plant groups for weekly motor charts.
PLANT_AIR = "air"
PLANT_BOILER = "boiler"
PLANT_CHILLER = "chiller"
PLANT_GROUPS: tuple[str, ...] = (PLANT_AIR, PLANT_BOILER, PLANT_CHILLER)

# Logical roles treated as motor / fan / pump runtime signals (0–100% or bool).
MOTOR_SIGNAL_ROLES: tuple[str, ...] = (
    "fan_cmd",
    "fan_status",
    "chw_pump_cmd",
    "hw_pump_cmd",
    "pump_cmd",
    "pump_status",
)

# Mechanical cooling proof — chillers / DX (hydronic AHU valve is optional).
CHILLER_RUN_ROLES: tuple[str, ...] = (
    "chiller_status",
    "compressor_status",
    "equipment_enable",
    "chw_pump_cmd",
    "pump_status",
    "pump_cmd",
)
DX_RUN_ROLES: tuple[str, ...] = (
    "compressor_status",
    "dx_cool_cmd",
    "dx_cooling",
    "cool_stage",
    "dx_stage",
)


def _is_on(series: pd.Series) -> pd.Series:
    """True when a command/status indicates the motor is running."""
    num = pd.to_numeric(series, errors="coerce")
    if num.notna().any():
        scaled = num.where(num <= 1.5, num / 100.0)
        return scaled.fillna(0) > 0.05
    return series.fillna(False).astype(bool)


def _above_threshold(series: pd.Series, thr: float) -> pd.Series:
    num = pd.to_numeric(series, errors="coerce")
    return num.notna() & (num > float(thr))


def dataset_time_span(frames: dict[str, pd.DataFrame]) -> dict[str, Any]:
    starts: list[pd.Timestamp] = []
    ends: list[pd.Timestamp] = []
    for df in frames.values():
        if df is None or df.empty or not isinstance(df.index, pd.DatetimeIndex):
            continue
        starts.append(df.index.min())
        ends.append(df.index.max())
    if not starts:
        return {"start": None, "end": None, "span_hours": 0.0}
    start = min(starts)
    end = max(ends)
    span_h = float((end - start).total_seconds() / 3600.0) if end > start else 0.0
    return {"start": start, "end": end, "span_hours": span_h}


def motor_run_hours_for_frame(
    df: pd.DataFrame,
    *,
    poll_seconds: float,
    equipment_id: str = "",
) -> list[dict[str, Any]]:
    """Accumulate on-hours for each motor-like role present on one equipment frame."""
    poll = max(float(poll_seconds), 1.0)
    rows: list[dict[str, Any]] = []
    for role in MOTOR_SIGNAL_ROLES:
        if role not in df.columns or df[role].notna().sum() == 0:
            continue
        on = _is_on(df[role])
        hours = float(on.sum() * poll / 3600.0)
        kind = "fan" if "fan" in role else "pump"
        rows.append(
            {
                "equipment_id": equipment_id,
                "signal": role,
                "motor_kind": kind,
                "run_hours": round(hours, 2),
                "on_samples": int(on.sum()),
                "samples": int(len(df)),
            }
        )
    return rows


def motor_run_hours_table(
    frames: dict[str, pd.DataFrame],
    role_map: dict,
) -> pd.DataFrame:
    """Build a per-equipment motor run-hours table across the loaded dataset."""
    from app.data_loader import infer_poll_seconds

    rows: list[dict[str, Any]] = []
    for eq_id, raw in frames.items():
        mapped = apply_role_map(raw, eq_id, role_map)
        poll = float(raw.attrs.get("poll_seconds") or infer_poll_seconds(raw))
        rows.extend(motor_run_hours_for_frame(mapped, poll_seconds=poll, equipment_id=eq_id))
    if not rows:
        return pd.DataFrame(
            columns=["equipment_id", "signal", "motor_kind", "run_hours", "on_samples", "samples"]
        )
    return pd.DataFrame(rows).sort_values(["motor_kind", "equipment_id", "signal"])


def motor_run_hours_totals(table: pd.DataFrame) -> dict[str, float]:
    if table is None or table.empty:
        return {"fan_hours": 0.0, "pump_hours": 0.0, "total_hours": 0.0}
    prefer = table.copy()
    drop_idx: list = []
    for _eq, grp in prefer.groupby("equipment_id"):
        signals = set(grp["signal"])
        # Prefer proven status over command when both exist
        if "fan_status" in signals and "fan_cmd" in signals:
            drop_idx.extend(grp.index[grp["signal"] == "fan_cmd"].tolist())
        if "pump_status" in signals and any(s in signals for s in ("pump_cmd", "hw_pump_cmd", "chw_pump_cmd")):
            drop_idx.extend(
                grp.index[grp["signal"].isin(["pump_cmd", "hw_pump_cmd", "chw_pump_cmd"])].tolist()
            )
    prefer = prefer.drop(index=drop_idx)
    fan = float(prefer.loc[prefer["motor_kind"] == "fan", "run_hours"].sum())
    pump = float(prefer.loc[prefer["motor_kind"] == "pump", "run_hours"].sum())
    return {
        "fan_hours": round(fan, 1),
        "pump_hours": round(pump, 1),
        "total_hours": round(fan + pump, 1),
    }


def _preferred_motor_roles(df: pd.DataFrame) -> list[tuple[str, str]]:
    """Return (role, motor_kind) pairs, preferring status over command."""
    present = [r for r in MOTOR_SIGNAL_ROLES if r in df.columns and df[r].notna().any()]
    fans = [r for r in present if "fan" in r]
    pumps = [r for r in present if "fan" not in r]
    out: list[tuple[str, str]] = []
    if "fan_status" in fans:
        out.append(("fan_status", "fan"))
    elif "fan_cmd" in fans:
        out.append(("fan_cmd", "fan"))
    if "pump_status" in pumps:
        out.append(("pump_status", "pump"))
    else:
        for r in ("hw_pump_cmd", "chw_pump_cmd", "pump_cmd"):
            if r in pumps:
                out.append((r, "pump"))
                break
    return out


def _equipment_plant_group(equipment_id: str, equipment_type: str) -> str | None:
    """Map equipment to air / boiler / chiller plant chart group."""
    et = (equipment_type or "").upper()
    eq = (equipment_id or "").upper().replace("\\", "/")
    if et == "VAV" or "/VAV" in eq or eq.startswith("VAV"):
        return None  # zone boxes — not central motors
    if et == "AHU" or eq.startswith("AHU") or "/AHU" in eq:
        return PLANT_AIR
    if "TOWER" in eq or re.search(r"(^|/)CT\d", eq) or eq.startswith("CT_"):
        return PLANT_CHILLER
    if et in {"CHW_PLANT", "CHILLER"} or "CHILLER" in eq or eq.startswith("CHW"):
        return PLANT_CHILLER
    if et == "BOILER" or "BOILER" in eq:
        return PLANT_BOILER
    if "CWP" in eq or "CHW_PUMP" in eq or ("PUMP" in eq and ("CHW" in eq or "CW" in eq)):
        return PLANT_CHILLER
    if "PUMP" in eq and "HEAT" not in eq:
        return PLANT_BOILER
    return None


_RE_HWP = re.compile(r"(?:^|_)(hwp)(\d+)[_ ]?([sc]|status|cmd|command)?(?:_|$)", re.I)
_RE_CWP = re.compile(
    r"(?:^|_)(cwp|chw_?pump|cw_?pump)(\d*)[_ ]?([sc]|status|cmd|command)?(?:_|$)",
    re.I,
)
_RE_TOWER = re.compile(
    r"(tower_?fan|ct_?fan|cooling_?tower|ctf\d*|tower_?motor|ct_?motor)",
    re.I,
)


def _col_signal_kind(col: str, suffix: str | None) -> str:
    cl = col.lower()
    suf = (suffix or "").lower()
    if suf in {"s", "status"} or "status" in cl or cl.endswith("_s"):
        return "status"
    if suf in {"c", "cmd", "command"} or "cmd" in cl or "command" in cl or cl.endswith("_c"):
        return "cmd"
    # bare names (e.g. tower_fan) — treat as status-like proof
    return "status"


def _skip_motor_column(col: str) -> bool:
    cl = col.lower()
    return any(
        x in cl
        for x in (
            "alarm",
            "lead",
            "setpoint",
            "setpt",
            "reset",
            "override",
            "enable_setpoint",
            "timestamp",
        )
    )


def _discover_named_pumps_and_towers(
    raw: pd.DataFrame,
    *,
    equipment_id: str,
    default_plant: str | None,
) -> list[dict[str, Any]]:
    """One series per physical pump / tower motor (status preferred over cmd)."""
    # key -> {status_col, cmd_col, plant, motor_kind, short}
    buckets: dict[str, dict[str, Any]] = {}

    for col in raw.columns:
        if col == "timestamp_utc" or _skip_motor_column(str(col)):
            continue
        cl = str(col).lower()
        series = pd.to_numeric(raw[col], errors="coerce")
        if series.notna().sum() == 0:
            continue

        m_hwp = _RE_HWP.search(cl)
        if m_hwp:
            key = f"hwp{m_hwp.group(2)}"
            kind = _col_signal_kind(cl, m_hwp.group(3))
            b = buckets.setdefault(
                key,
                {"plant": PLANT_BOILER, "motor_kind": "pump", "short": key.upper()},
            )
            b[kind] = col
            continue

        m_cwp = _RE_CWP.search(cl)
        if m_cwp and "hwp" not in cl:
            num = m_cwp.group(2) or "1"
            prefix = m_cwp.group(1).replace("_", "")
            key = f"{prefix}{num}"
            kind = _col_signal_kind(cl, m_cwp.group(3))
            b = buckets.setdefault(
                key,
                {"plant": PLANT_CHILLER, "motor_kind": "pump", "short": key.upper()},
            )
            b[kind] = col
            continue

        if _RE_TOWER.search(cl) and "temp" not in cl and "set" not in cl:
            key = f"tower:{col}"
            kind = _col_signal_kind(cl, None)
            b = buckets.setdefault(
                key,
                {
                    "plant": PLANT_CHILLER,
                    "motor_kind": "tower",
                    "short": str(col),
                },
            )
            b[kind] = col
            continue

    out: list[dict[str, Any]] = []
    for key, b in sorted(buckets.items()):
        col = b.get("status") or b.get("cmd")
        if col is None:
            continue
        signal = "pump_status" if b.get("status") else "pump_cmd"
        if b["motor_kind"] == "tower":
            signal = "tower_status" if b.get("status") else "tower_cmd"
        plant = b["plant"] if b["plant"] else default_plant
        if plant is None:
            continue
        out.append(
            {
                "equipment_id": equipment_id,
                "signal": signal,
                "column": col,
                "motor_kind": b["motor_kind"],
                "plant_group": plant,
                "label": f"{equipment_id} · {b['short']}",
                "series": raw[col],
            }
        )
    return out


def _discover_air_supply_fan(
    mapped: pd.DataFrame,
    raw: pd.DataFrame,
    *,
    equipment_id: str,
) -> list[dict[str, Any]]:
    """Supply fan only (never return fan). Prefer status over command."""
    from app.role_map import suggest_roles

    # Merge heuristic suggestions when role_map left fan roles empty
    suggested = suggest_roles(raw)
    work = mapped
    if "fan_status" not in work.columns and "fan_status" in suggested:
        col = suggested["fan_status"]
        if col in raw.columns and "return" not in col.lower():
            work = work.copy()
            work["fan_status"] = pd.to_numeric(raw[col], errors="coerce")
    if "fan_cmd" not in work.columns and "fan_cmd" in suggested:
        col = suggested["fan_cmd"]
        if col in raw.columns and "return" not in col.lower():
            work = work.copy()
            work["fan_cmd"] = pd.to_numeric(raw[col], errors="coerce")

    if "fan_status" in work.columns and work["fan_status"].notna().any():
        role, kind = "fan_status", "fan"
        ser = work["fan_status"]
    elif "fan_cmd" in work.columns and work["fan_cmd"].notna().any():
        role, kind = "fan_cmd", "fan"
        ser = work["fan_cmd"]
    else:
        # Last resort: raw supply_* columns
        status_cols = [
            c
            for c in raw.columns
            if "supply" in str(c).lower()
            and ("fan_status" in str(c).lower() or str(c).lower().endswith("fanstatus"))
        ]
        cmd_cols = [
            c
            for c in raw.columns
            if "supply" in str(c).lower()
            and ("fan_speed" in str(c).lower() or "fan_cmd" in str(c).lower())
        ]
        if status_cols:
            role, kind, ser = "fan_status", "fan", raw[status_cols[0]]
        elif cmd_cols:
            role, kind, ser = "fan_cmd", "fan", raw[cmd_cols[0]]
        else:
            return []
    return [
        {
            "equipment_id": equipment_id,
            "signal": role,
            "column": role,
            "motor_kind": kind,
            "plant_group": PLANT_AIR,
            "label": f"{equipment_id} · {role}",
            "series": ser,
        }
    ]


def _resolve_linked_pump_series(
    frames: dict[str, pd.DataFrame],
    role_map: dict,
    *,
    equipment_id: str,
) -> tuple[pd.Series | None, str, str]:
    """Resolve designated CHW pump from role_map (same frame or linked equipment).

    Data-model keys on the chiller's role_map entry:
      - chw_pump_status / chw_pump_cmd → column name
      - chw_pump_equipment (optional meta) → other equipment_id that owns that column
    """
    eq_roles = role_map.get(equipment_id) or {}
    link_eq = str(eq_roles.get("chw_pump_equipment") or "").strip()
    src_id = link_eq if link_eq and link_eq in frames else equipment_id
    src = frames.get(src_id)
    if src is None or src.empty:
        return None, "", ""

    for role in ("chw_pump_status", "chw_pump_cmd"):
        col = eq_roles.get(role)
        if not col or not isinstance(col, str):
            continue
        if col in src.columns and pd.to_numeric(src[col], errors="coerce").notna().any():
            return src[col], role, f"{src_id}:{col}"
    return None, "", ""


def _discover_chiller_on(
    mapped: pd.DataFrame,
    raw: pd.DataFrame,
    frames: dict[str, pd.DataFrame],
    role_map: dict,
    *,
    equipment_id: str,
    chw_leave_max_f: float,
) -> list[dict[str, Any]]:
    """Chiller plant runtime: designated pump status first; CHW leave temp as backup only.

    Does **not** use chiller cmd/amps/power for the weekly motor chart (pump-driven model).
    """
    # 1) Role-map designated pump (possibly on linked equipment)
    linked, link_role, link_label = _resolve_linked_pump_series(
        frames, role_map, equipment_id=equipment_id
    )
    if linked is not None:
        on = _is_on(linked)
        if bool(on.any()):
            return [
                {
                    "equipment_id": equipment_id,
                    "signal": link_role or "chw_pump_status",
                    "column": link_label,
                    "motor_kind": "chiller",
                    "plant_group": PLANT_CHILLER,
                    "label": f"{equipment_id} · {link_role or 'chw_pump_status'}",
                    "series_on": on.astype(float),
                }
            ]

    # 2) Mapped logical roles on this chiller frame
    for role in ("chw_pump_status", "pump_status"):
        if role in mapped.columns and mapped[role].notna().any():
            on = _is_on(mapped[role])
            if bool(on.any()):
                return [
                    {
                        "equipment_id": equipment_id,
                        "signal": role,
                        "column": role,
                        "motor_kind": "chiller",
                        "plant_group": PLANT_CHILLER,
                        "label": f"{equipment_id} · {role}",
                        "series_on": on.astype(float),
                    }
                ]
    for role in ("chw_pump_cmd", "pump_cmd", "chw_pump_cmd"):
        if role in mapped.columns and mapped[role].notna().any():
            on = _is_on(mapped[role])
            if bool(on.any()):
                return [
                    {
                        "equipment_id": equipment_id,
                        "signal": role,
                        "column": role,
                        "motor_kind": "chiller",
                        "plant_group": PLANT_CHILLER,
                        "label": f"{equipment_id} · {role}",
                        "series_on": on.astype(float),
                    }
                ]

    # 3) Heuristic CWP columns on this frame (status over cmd)
    named = _discover_named_pumps_and_towers(
        raw, equipment_id=equipment_id, default_plant=PLANT_CHILLER
    )
    pumps = [p for p in named if p.get("motor_kind") == "pump"]
    status_pumps = [p for p in pumps if p.get("signal") == "pump_status"]
    pick = (status_pumps or pumps)
    if pick:
        p0 = pick[0]
        on = _is_on(p0["series"])
        if bool(on.any()):
            return [
                {
                    "equipment_id": equipment_id,
                    "signal": p0["signal"],
                    "column": p0.get("column", p0["signal"]),
                    "motor_kind": "chiller",
                    "plant_group": PLANT_CHILLER,
                    "label": f"{equipment_id} · {p0['signal']}",
                    "series_on": on.astype(float),
                }
            ]

    # 4) Backup only: CHW leave/supply vs sidebar slider
    temp = _chw_temp_proof(mapped, chw_leave_max_f)
    if temp is not None and bool(temp.any()):
        return [
            {
                "equipment_id": equipment_id,
                "signal": "chw_leave_temp",
                "column": "chw_leave_temp",
                "motor_kind": "chiller",
                "plant_group": PLANT_CHILLER,
                "label": f"{equipment_id} · chw_leave_temp",
                "series_on": temp.astype(float),
            }
        ]
    return []


def discover_plant_motor_series(
    frames: dict[str, pd.DataFrame],
    role_map: dict,
    *,
    chw_leave_max_f: float = 48.0,
) -> list[dict[str, Any]]:
    """Discover per-motor series for air / boiler / chiller weekly charts."""
    from app.role_map import suggest_roles

    found: list[dict[str, Any]] = []
    for eq_id, raw in frames.items():
        et = str(raw.attrs.get("equipment_type") or equipment_type_from_id(eq_id)).upper()
        plant = _equipment_plant_group(eq_id, et)
        mapped = apply_role_map(raw, eq_id, role_map)
        # Fill missing logical roles from column-name heuristics (same as Mapping enrich)
        suggested = suggest_roles(raw)
        for role, col in suggested.items():
            if role not in mapped.columns and col in raw.columns:
                mapped[role] = pd.to_numeric(raw[col], errors="coerce")
        if not isinstance(mapped.index, pd.DatetimeIndex) and not isinstance(raw.index, pd.DatetimeIndex):
            continue

        # Named pumps / tower fans from raw columns (each physical motor).
        found.extend(
            _discover_named_pumps_and_towers(raw, equipment_id=eq_id, default_plant=plant)
        )

        if plant == PLANT_AIR:
            found.extend(_discover_air_supply_fan(mapped, raw, equipment_id=eq_id))
        elif plant == PLANT_CHILLER and (
            et in {"CHW_PLANT", "CHILLER"} or "CHILLER" in eq_id.upper()
        ):
            found.extend(
                _discover_chiller_on(
                    mapped,
                    raw,
                    frames,
                    role_map,
                    equipment_id=eq_id,
                    chw_leave_max_f=chw_leave_max_f,
                )
            )
        elif plant == PLANT_CHILLER:
            # Generic CHW plant frame: fall back to mapped pump roles if no named pumps
            named = {s["label"] for s in found if s["equipment_id"] == eq_id}
            if not any(s["equipment_id"] == eq_id and s["motor_kind"] == "pump" for s in found):
                for role, kind in _preferred_motor_roles(mapped):
                    if "fan" in role:
                        continue
                    lab = f"{eq_id} · {role}"
                    if lab in named:
                        continue
                    found.append(
                        {
                            "equipment_id": eq_id,
                            "signal": role,
                            "column": role,
                            "motor_kind": kind,
                            "plant_group": PLANT_CHILLER,
                            "label": lab,
                            "series": mapped[role],
                        }
                    )
        elif plant == PLANT_BOILER:
            # Mapped pump fallback when columns aren't hwpN_* patterned
            if not any(s["equipment_id"] == eq_id and s["motor_kind"] == "pump" for s in found):
                for role, kind in _preferred_motor_roles(mapped):
                    if "fan" in role:
                        continue
                    found.append(
                        {
                            "equipment_id": eq_id,
                            "signal": role,
                            "column": role,
                            "motor_kind": kind,
                            "plant_group": PLANT_BOILER,
                            "label": f"{eq_id} · {role}",
                            "series": mapped[role],
                        }
                    )
    return found


def motor_run_hours_weekly(
    frames: dict[str, pd.DataFrame],
    role_map: dict,
    *,
    chw_leave_max_f: float = 48.0,
) -> pd.DataFrame:
    """Weekly on-hours per motor, split by plant_group (air / boiler / chiller).

    Columns: week_start, week_label, equipment_id, signal, motor_kind, plant_group, label, hours
    """
    from app.data_loader import infer_poll_seconds

    rows: list[dict[str, Any]] = []
    series_list = discover_plant_motor_series(
        frames, role_map, chw_leave_max_f=chw_leave_max_f
    )
    poll_by_eq: dict[str, float] = {}
    for eq_id, raw in frames.items():
        poll_by_eq[eq_id] = float(raw.attrs.get("poll_seconds") or infer_poll_seconds(raw))

    for spec in series_list:
        eq_id = spec["equipment_id"]
        raw = frames.get(eq_id)
        if raw is None:
            continue
        poll = poll_by_eq.get(eq_id, 300.0)
        if "series_on" in spec:
            on = spec["series_on"].astype(float)
            idx = on.index
        else:
            ser = spec["series"]
            if not isinstance(ser.index, pd.DatetimeIndex):
                # align to equipment frame index
                ser = pd.Series(ser.to_numpy(), index=raw.index)
            if not isinstance(ser.index, pd.DatetimeIndex) or ser.empty:
                continue
            on = _is_on(ser).astype(float)
            idx = on.index
        if not isinstance(idx, pd.DatetimeIndex) or len(on) == 0:
            continue
        hours = on * (poll / 3600.0)
        hours.index = idx
        weekly = hours.resample("W-MON", label="left", closed="left").sum()
        for ts, h in weekly.items():
            if pd.isna(h) or float(h) <= 0:
                continue
            week = pd.Timestamp(ts)
            if week.tzinfo is not None:
                week = week.tz_convert("UTC").tz_localize(None)
            rows.append(
                {
                    "week_start": week.normalize(),
                    "week_label": week.strftime("%Y-%m-%d"),
                    "equipment_id": eq_id,
                    "signal": spec["signal"],
                    "motor_kind": spec["motor_kind"],
                    "plant_group": spec["plant_group"],
                    "label": spec["label"],
                    "hours": round(float(h), 2),
                }
            )
    cols = [
        "week_start",
        "week_label",
        "equipment_id",
        "signal",
        "motor_kind",
        "plant_group",
        "label",
        "hours",
    ]
    if not rows:
        return pd.DataFrame(columns=cols)
    return pd.DataFrame(rows).sort_values(
        ["plant_group", "week_start", "motor_kind", "equipment_id", "signal"]
    )


def _first_on_mask(df: pd.DataFrame, roles: tuple[str, ...]) -> pd.Series | None:
    for role in roles:
        if role in df.columns and df[role].notna().any():
            return _is_on(df[role])
    return None


def _oat_series(
    df: pd.DataFrame,
    weather: pd.DataFrame | None,
    *,
    prefer_web: bool = True,
) -> pd.Series | None:
    from app.weather_psychrometrics import prefer_web_oat

    return prefer_web_oat(df, weather, prefer_web=prefer_web)


def _chw_temp_proof(df: pd.DataFrame, leave_max_f: float) -> pd.Series | None:
    """True when chilled-water leave/supply is colder than threshold (plant producing cold water)."""
    for role in ("chw_supply_t", "chw_leave_t", "chws_t"):
        if role in df.columns and df[role].notna().any():
            t = pd.to_numeric(df[role], errors="coerce")
            # Ignore long zero/null sensor dropouts common in historians
            return t.notna() & (t > 32.0) & (t < float(leave_max_f))
    return None


def _chiller_on_mask(
    df: pd.DataFrame,
    *,
    chw_leave_max_f: float,
    chiller_amps_min: float = 5.0,
    chiller_power_kw_min: float = 1.0,
) -> tuple[pd.Series | None, str]:
    """Chiller ON: cmd/status → amps → power → CHW leave vs slider (no pumps)."""
    run = _first_on_mask(df, ("chiller_status", "compressor_status", "equipment_enable"))
    if run is not None and bool(run.any()):
        return run, "chiller_status"
    if "chiller_amps" in df.columns and df["chiller_amps"].notna().any():
        amps = _above_threshold(df["chiller_amps"], chiller_amps_min)
        if bool(amps.any()):
            return amps, "chiller_amps"
    if "chiller_power_kw" in df.columns and df["chiller_power_kw"].notna().any():
        pwr = _above_threshold(df["chiller_power_kw"], chiller_power_kw_min)
        if bool(pwr.any()):
            return pwr, "chiller_power"
    temp = _chw_temp_proof(df, chw_leave_max_f)
    if temp is not None and bool(temp.any()):
        return temp, "chw_leave_temp"
    return None, ""


def _valve_open_mask(df: pd.DataFrame, role: str, thr_pct: float) -> pd.Series | None:
    if role not in df.columns or df[role].notna().sum() == 0:
        return None
    num = pd.to_numeric(df[role], errors="coerce")
    scaled = num.where(num <= 1.5, num / 100.0)
    return scaled.fillna(0) > (float(thr_pct) / 100.0)


def mech_cooling_run_mask(
    df: pd.DataFrame,
    *,
    equipment_type: str,
    equipment_id: str = "",
    chw_leave_max_f: float = 48.0,
    include_ahu_chw_valve: bool = True,
    clg_valve_thr_pct: float = 5.0,
    chiller_amps_min: float = 5.0,
    chiller_power_kw_min: float = 1.0,
) -> tuple[pd.Series | None, str]:
    """
    Flexible mechanical-cooling proof (first match wins).

    Chillers / CHW plant:
      1. status / command / pump proof
      2. amps above threshold
      3. power kW above threshold
      4. CHW supply/leave below adjustable °F (and > 32°F)

    AHUs:
      1. DX compressor / stage roles
      2. optional hydronic cool valve open (clg_valve_pct) — BUILDING_100-style CHW AHUs
    """
    et = equipment_type.upper()
    eq = equipment_id.upper()
    if et in {"CHW_PLANT", "CHILLER"} or "CHILLER" in eq or eq.startswith("CHW"):
        run = _first_on_mask(df, CHILLER_RUN_ROLES)
        if run is not None and bool(run.any()):
            return run, "chiller_status"
        if "chiller_amps" in df.columns and df["chiller_amps"].notna().any():
            amps = _above_threshold(df["chiller_amps"], chiller_amps_min)
            if bool(amps.any()):
                return amps, "chiller_amps"
        if "chiller_power_kw" in df.columns and df["chiller_power_kw"].notna().any():
            pwr = _above_threshold(df["chiller_power_kw"], chiller_power_kw_min)
            if bool(pwr.any()):
                return pwr, "chiller_power"
        temp = _chw_temp_proof(df, chw_leave_max_f)
        if temp is not None and bool(temp.any()):
            return temp, "chw_leave_temp"
        return None, ""
    if et == "AHU":
        run = _first_on_mask(df, DX_RUN_ROLES)
        if run is not None and bool(run.any()):
            return run, "ahu_dx"
        if include_ahu_chw_valve:
            valve = _valve_open_mask(df, "clg_valve_pct", clg_valve_thr_pct)
            if valve is not None and bool(valve.any()):
                return valve, "ahu_chw_valve"
        return None, ""
    if et == "HEATPUMP" or eq.startswith("HP"):
        run = _first_on_mask(df, DX_RUN_ROLES + ("compressor_status",))
        if run is not None and bool(run.any()):
            return run, "heatpump"
        return None, ""
    return None, ""


def mech_cooling_oat_bins(
    frames: dict[str, pd.DataFrame],
    role_map: dict,
    *,
    weather: pd.DataFrame | None = None,
    bin_width_f: float = 5.0,
    prefer_web_oat: bool = True,
    chw_leave_max_f: float = 48.0,
    include_ahu_chw_valve: bool = True,
    clg_valve_thr_pct: float = 5.0,
) -> pd.DataFrame:
    """
    Mechanical cooling run hours binned by OAT (default: web/Open-Meteo dry bulb).

    Flexible proof: chiller cmd/status → amps → power → CHW leave temp;
    AHU DX → optional AHU CHW valve open (hydronic).
    """
    from app.data_loader import infer_poll_seconds

    rows: list[dict[str, Any]] = []
    for eq_id, raw in frames.items():
        et = str(raw.attrs.get("equipment_type") or equipment_type_from_id(eq_id)).upper()
        mapped = apply_role_map(raw, eq_id, role_map)
        poll = float(raw.attrs.get("poll_seconds") or infer_poll_seconds(raw))
        oat = _oat_series(mapped, weather, prefer_web=prefer_web_oat)
        if oat is None:
            continue

        run, source_kind = mech_cooling_run_mask(
            mapped,
            equipment_type=et,
            equipment_id=eq_id,
            chw_leave_max_f=chw_leave_max_f,
            include_ahu_chw_valve=include_ahu_chw_valve,
            clg_valve_thr_pct=clg_valve_thr_pct,
        )
        if run is None or not bool(run.any()):
            continue

        oat_on = oat.where(run).dropna()
        if oat_on.empty:
            continue
        clamped = oat_on.clip(40, 110)
        bin_start = (np.floor(clamped.to_numpy(dtype=float) / bin_width_f) * bin_width_f).astype(int)
        tmp = pd.DataFrame({"oat": oat_on.to_numpy(), "bin_start": bin_start}, index=oat_on.index)
        for b, g in tmp.groupby("bin_start"):
            if pd.isna(b):
                continue
            b_i = int(b)
            hours = float(len(g) * poll / 3600.0)
            rows.append(
                {
                    "equipment_id": eq_id,
                    "source": f"{eq_id} ({source_kind})",
                    "source_kind": source_kind,
                    "bin_start": b_i,
                    "bin_label": f"{b_i}-{b_i + int(bin_width_f) - 1}",
                    "hours": round(hours, 2),
                }
            )

    if not rows:
        return pd.DataFrame(
            columns=["equipment_id", "source", "source_kind", "bin_start", "bin_label", "hours"]
        )
    return pd.DataFrame(rows).sort_values(["source", "bin_start"])


def sensor_fault_summary(
    df: pd.DataFrame,
    results: list,
    *,
    equipment_id: str,
    poll_seconds: float = 300.0,
) -> pd.DataFrame:
    """Summary statistics for sensors involved in FAULT sensor-validation results."""
    rows: list[dict] = []
    sensor_rules = {"SV-RANGE", "SV-FLATLINE", "SV-SPIKE", "SV-STALE"}
    for r in results:
        if getattr(r, "equipment_id", None) != equipment_id:
            continue
        if r.rule_id not in sensor_rules or r.status != "FAULT":
            continue
        series_map = getattr(r, "plot_series", None) or {}
        fault = getattr(r, "confirmed_fault", None)
        for name, s in series_map.items():
            num = pd.to_numeric(s, errors="coerce")
            if num.notna().sum() == 0:
                continue
            fault_vals = num
            if fault is not None:
                mask = fault.reindex(num.index).fillna(False).astype(bool)
                if mask.any():
                    fault_vals = num[mask]
            rows.append(
                {
                    "equipment_id": equipment_id,
                    "rule_id": r.rule_id,
                    "sensor": name,
                    "fault_hours": getattr(r, "fault_hours", None),
                    "n": int(num.notna().sum()),
                    "n_fault_samples": int(fault_vals.notna().sum()) if fault is not None else None,
                    "mean": round(float(num.mean()), 3),
                    "std": round(float(num.std(ddof=0)), 3) if num.notna().sum() > 1 else 0.0,
                    "min": round(float(num.min()), 3),
                    "p50": round(float(num.quantile(0.5)), 3),
                    "max": round(float(num.max()), 3),
                    "fault_mean": round(float(fault_vals.mean()), 3) if fault_vals.notna().any() else None,
                    "fault_min": round(float(fault_vals.min()), 3) if fault_vals.notna().any() else None,
                    "fault_max": round(float(fault_vals.max()), 3) if fault_vals.notna().any() else None,
                }
            )
    if not rows:
        return pd.DataFrame(
            columns=[
                "equipment_id",
                "rule_id",
                "sensor",
                "fault_hours",
                "n",
                "n_fault_samples",
                "mean",
                "std",
                "min",
                "p50",
                "max",
                "fault_mean",
                "fault_min",
                "fault_max",
            ]
        )
    return pd.DataFrame(rows)

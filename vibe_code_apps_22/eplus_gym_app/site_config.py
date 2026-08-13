"""Site DSM thermostat / occupancy config (staged IDF only).

Persists ``{SITE_ROOT}/reports/eplus_gym/site_dsm_config.json``. Values patch
``SCH_HtgSP`` / ``SCH_ClgSP`` on **staged** run IDFs - never overwrite the
published champion on disk.
"""
from __future__ import annotations

import json
import os
from copy import deepcopy
from datetime import date, time
from pathlib import Path
from typing import Any

SCHEMA_VERSION = 1

DAY_KEYS = ("mon", "tue", "wed", "thu", "fri", "sat", "sun")
DAY_LABELS = {
    "mon": "Monday",
    "tue": "Tuesday",
    "wed": "Wednesday",
    "thu": "Thursday",
    "fri": "Friday",
    "sat": "Saturday",
    "sun": "Sunday",
}

DEFAULT_SETPOINTS_F = {
    "occupied_heating_f": 70.0,
    "unoccupied_heating_f": 65.0,
    "occupied_cooling_f": 75.0,
    "unoccupied_cooling_f": 85.0,
}

_WEEKDAY = {"occupied": True, "start": "06:45", "end": "15:30"}
_WEEKEND = {"occupied": False, "start": "08:00", "end": "12:00"}


def default_occupancy_schedule() -> dict[str, Any]:
    days = {d: dict(_WEEKDAY) for d in ("mon", "tue", "wed", "thu", "fri")}
    days["sat"] = dict(_WEEKEND)
    days["sun"] = dict(_WEEKEND)
    return {"timezone": "America/Chicago", "days": days}


def default_site_dsm_config() -> dict[str, Any]:
    return {
        "schema_version": SCHEMA_VERSION,
        "setpoints_f": dict(DEFAULT_SETPOINTS_F),
        "occupancy_schedule": default_occupancy_schedule(),
        "peak_day_override": None,
    }


def site_dsm_config_path(site: Path | str) -> Path:
    return Path(site) / "reports" / "eplus_gym" / "site_dsm_config.json"


def _hhmm(value: Any, fallback: str) -> str:
    if isinstance(value, time):
        return f"{value.hour:02d}:{value.minute:02d}"
    s = str(value or fallback).strip()
    if len(s) >= 4 and ":" in s:
        parts = s.split(":")
        try:
            return f"{int(parts[0]):02d}:{int(parts[1]):02d}"
        except ValueError:
            return fallback
    return fallback


def normalize_occupancy_schedule(raw: Any) -> dict[str, Any]:
    base = default_occupancy_schedule()
    if not isinstance(raw, dict):
        return base
    tz = str(raw.get("timezone") or base["timezone"])
    days_in = raw.get("days") if isinstance(raw.get("days"), dict) else {}
    days_out: dict[str, Any] = {}
    for key in DAY_KEYS:
        src = days_in.get(key) if isinstance(days_in.get(key), dict) else {}
        fb = base["days"][key]
        days_out[key] = {
            "occupied": bool(src.get("occupied", fb["occupied"])),
            "start": _hhmm(src.get("start"), fb["start"]),
            "end": _hhmm(src.get("end"), fb["end"]),
        }
    return {"timezone": tz, "days": days_out}


def normalize_site_dsm_config(raw: Any) -> dict[str, Any]:
    out = default_site_dsm_config()
    if not isinstance(raw, dict):
        return out
    sp_in = raw.get("setpoints_f") if isinstance(raw.get("setpoints_f"), dict) else {}
    sp = out["setpoints_f"]
    for key in DEFAULT_SETPOINTS_F:
        if key in sp_in:
            try:
                sp[key] = float(sp_in[key])
            except (TypeError, ValueError):
                pass
    out["setpoints_f"] = sp
    out["occupancy_schedule"] = normalize_occupancy_schedule(raw.get("occupancy_schedule"))
    override = raw.get("peak_day_override")
    if override in (None, "", "null"):
        out["peak_day_override"] = None
    else:
        try:
            out["peak_day_override"] = date.fromisoformat(str(override)[:10]).isoformat()
        except ValueError:
            out["peak_day_override"] = None
    out["schema_version"] = int(raw.get("schema_version") or SCHEMA_VERSION)
    return out


def validate_setpoints_f(sp: dict[str, Any]) -> list[str]:
    errors: list[str] = []
    try:
        oh = float(sp["occupied_heating_f"])
        uh = float(sp["unoccupied_heating_f"])
        oc = float(sp["occupied_cooling_f"])
        uc = float(sp["unoccupied_cooling_f"])
    except (KeyError, TypeError, ValueError):
        return ["setpoints_f must include four numeric °F values"]
    if oh >= oc:
        errors.append(f"occupied heat ({oh}) must be < occupied cool ({oc})")
    if uh >= uc:
        errors.append(f"unoccupied heat ({uh}) must be < unoccupied cool ({uc})")
    return errors


def load_site_dsm_config(site: Path | str) -> dict[str, Any]:
    path = site_dsm_config_path(site)
    if not path.is_file():
        return default_site_dsm_config()
    try:
        raw = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return default_site_dsm_config()
    return normalize_site_dsm_config(raw)


def save_site_dsm_config(site: Path | str, cfg: dict[str, Any]) -> Path:
    site = Path(site)
    doc = normalize_site_dsm_config(cfg)
    errs = validate_setpoints_f(doc["setpoints_f"])
    if errs:
        raise ValueError("; ".join(errs))
    path = site_dsm_config_path(site)
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_name(f".{path.name}.{os.getpid()}.tmp")
    tmp.write_text(json.dumps(doc, indent=2) + "\n", encoding="utf-8")
    os.replace(tmp, path)
    return path


def setpoints_summary(cfg: dict[str, Any] | None = None) -> str:
    sp = (cfg or default_site_dsm_config()).get("setpoints_f") or {}
    oh = sp.get("occupied_heating_f", 70)
    uh = sp.get("unoccupied_heating_f", 65)
    oc = sp.get("occupied_cooling_f", 75)
    uc = sp.get("unoccupied_cooling_f", 85)
    try:
        deadband = float(oc) - float(oh)
        db = f"{deadband:.1f}"
    except (TypeError, ValueError):
        db = "?"
    return (
        f"occ heat {oh}F / unocc heat {uh}F / "
        f"occ cool {oc}F / unocc cool {uc}F (deadband {db}F)"
    )


def calendar_contract_from_site_config(cfg: dict[str, Any] | None = None) -> dict[str, Any]:
    """Shape accepted by schedule_calendar_repair setpoint patchers."""
    doc = normalize_site_dsm_config(cfg or {})
    return {"setpoints_f": deepcopy(doc["setpoints_f"])}


def render_site_config_tab(site: Path, bundle: Any | None = None) -> dict[str, Any]:
    """Streamlit Site Config form. Returns the saved/normalized config."""
    import streamlit as st

    st.subheader("Site Config")
    st.caption(
        "Thermostat setpoints and occupancy for **staged** DSM runs only. "
        "Never overwrites the published champion IDF."
    )
    cfg = load_site_dsm_config(site)
    sp = dict(cfg["setpoints_f"])

    c1, c2, c3, c4 = st.columns(4)
    sp["occupied_heating_f"] = c1.number_input(
        "Occupied heat (F)",
        min_value=50.0,
        max_value=80.0,
        value=float(sp["occupied_heating_f"]),
        step=0.5,
        key="site_cfg_occ_heat",
    )
    sp["unoccupied_heating_f"] = c2.number_input(
        "Unoccupied heat (F)",
        min_value=45.0,
        max_value=75.0,
        value=float(sp["unoccupied_heating_f"]),
        step=0.5,
        key="site_cfg_unocc_heat",
    )
    sp["occupied_cooling_f"] = c3.number_input(
        "Occupied cool (F)",
        min_value=65.0,
        max_value=90.0,
        value=float(sp["occupied_cooling_f"]),
        step=0.5,
        key="site_cfg_occ_cool",
    )
    sp["unoccupied_cooling_f"] = c4.number_input(
        "Unoccupied cool (F)",
        min_value=70.0,
        max_value=95.0,
        value=float(sp["unoccupied_cooling_f"]),
        step=0.5,
        key="site_cfg_unocc_cool",
    )
    deadband = float(sp["occupied_cooling_f"]) - float(sp["occupied_heating_f"])
    st.caption(f"Occupied deadband (derived): **{deadband:.1f} F** (occ cool - occ heat)")

    errs = validate_setpoints_f(sp)
    if errs:
        for e in errs:
            st.error(e)

    st.markdown("**Weekly occupancy**")
    occ = normalize_occupancy_schedule(cfg.get("occupancy_schedule"))
    tz = st.text_input("Timezone", value=occ["timezone"], key="site_cfg_occ_tz")
    days_out: dict[str, Any] = {}
    for d in DAY_KEYS:
        day = occ["days"][d]
        st.markdown(f"**{DAY_LABELS[d]}**")
        a, b, c = st.columns(3)
        occupied = a.checkbox("Occupied", value=bool(day["occupied"]), key=f"site_cfg_occ_{d}")
        start_t = b.time_input(
            "Start",
            value=time(int(day["start"][:2]), int(day["start"][3:5])),
            key=f"site_cfg_occ_s_{d}",
        )
        end_t = c.time_input(
            "End",
            value=time(int(day["end"][:2]), int(day["end"][3:5])),
            key=f"site_cfg_occ_e_{d}",
        )
        days_out[d] = {
            "occupied": bool(occupied),
            "start": _hhmm(start_t, day["start"]),
            "end": _hhmm(end_t, day["end"]),
        }

    st.markdown("**Sim date override**")
    use_override = st.checkbox(
        "Override peak day for Run DSM",
        value=bool(cfg.get("peak_day_override")),
        key="site_cfg_use_day_override",
    )
    peak_override = None
    if use_override:
        default_day = cfg.get("peak_day_override") or (
            getattr(getattr(bundle, "dial_ladder", None), "peak_day", None) or "2026-01-26"
        )
        try:
            default_d = date.fromisoformat(str(default_day)[:10])
        except ValueError:
            default_d = date(2026, 1, 26)
        picked = st.date_input("Peak day override", value=default_d, key="site_cfg_peak_day")
        peak_override = picked.isoformat() if picked else None

    if bundle is not None:
        champ = None
        try:
            champ = bundle.champion()
        except Exception:  # noqa: BLE001
            champ = None
        idf_name = (
            getattr(champ, "idf_pin", None)
            or (bundle.idf_path.name if getattr(bundle, "idf_path", None) else None)
            or "?"
        )
        epw = getattr(bundle, "epw", None)
        cov = ""
        if getattr(bundle, "epw_coverage_start", None) and getattr(bundle, "epw_coverage_end", None):
            cov = f"{bundle.epw_coverage_start} -> {bundle.epw_coverage_end}"
        st.markdown("**Published pack**")
        st.caption(
            f"Champion `{idf_name}` · EPW `{Path(epw).name if epw else '?'}`"
            + (f" · coverage {cov}" if cov else "")
        )

    draft = {
        "schema_version": SCHEMA_VERSION,
        "setpoints_f": sp,
        "occupancy_schedule": {"timezone": tz, "days": days_out},
        "peak_day_override": peak_override,
    }
    if st.button("Save Site Config", type="primary", key="site_cfg_save"):
        if errs:
            st.error("Fix setpoint validation before saving.")
        else:
            path = save_site_dsm_config(site, draft)
            st.success(f"Saved `{path}`")
            cfg = load_site_dsm_config(site)
    else:
        cfg = normalize_site_dsm_config(draft)

    st.session_state["site_dsm_config"] = cfg
    st.caption(f"Active: {setpoints_summary(cfg)}")
    return cfg

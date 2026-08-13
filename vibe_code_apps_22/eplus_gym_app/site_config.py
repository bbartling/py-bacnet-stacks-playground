"""Site DSM thermostat / occupancy / HVAC config (staged IDF only).

Persists ``{SITE_ROOT}/reports/eplus_gym/site_dsm_config.json``. Values patch
schedules on **staged** run IDFs - never overwrite the published champion.
"""
from __future__ import annotations

import json
import os
from copy import deepcopy
from datetime import date, datetime, time, timedelta
from pathlib import Path
from typing import Any

SCHEMA_VERSION = 2

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
# EnergyPlus Schedule:Compact For: tokens
_DAY_FOR = {
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

_WEEKDAY_PEOPLE = {"occupied": True, "people_start": "06:45", "people_end": "15:30"}
_WEEKEND_PEOPLE = {"occupied": False, "people_start": "08:00", "people_end": "12:00"}

PEOPLE_SCHEDULE_NAMES = (
    "SCH_Occ_Class",
    "SCH_Occ_Library",
    "SCH_Occ_Cafe",
    "SCH_Occ_Gym",
    "SCH_Occ",
)
PLUG_SCHEDULE_NAMES = ("SCH_Equip", "SCH_Kitchen")
HVAC_SCHEDULE_NAMES = (
    "SCH_CoolAvail",
    "SCH_FanProxy",
    "SCH_HVAC",
    "SCH_OA",
)
# HeatAvail is forced always-on on staged WAHP IDFs (unocc SP hold).
HEAT_AVAIL_ALWAYS_ON = "SCH_HeatAvail"


def _shift_hhmm(hhmm: str, minutes: int) -> str:
    t = datetime.strptime(_hhmm(hhmm, "06:45"), "%H:%M")
    t2 = t + timedelta(minutes=int(minutes))
    # Clamp to same civil day for schedule Until tokens
    if t2.day != t.day:
        return "00:00" if minutes < 0 else "23:59"
    return f"{t2.hour:02d}:{t2.minute:02d}"


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


def _hhmm_to_time(hhmm: str) -> time:
    s = _hhmm(hhmm, "06:45")
    return time(int(s[:2]), int(s[3:5]))


def default_day_block(*, weekday: bool) -> dict[str, Any]:
    people = dict(_WEEKDAY_PEOPLE if weekday else _WEEKEND_PEOPLE)
    # HVAC defaults: start 45 min before people, end 30 min after
    hvac_start = _shift_hhmm(people["people_start"], -45)
    hvac_end = _shift_hhmm(people["people_end"], 30)
    return {
        **people,
        "hvac_start": hvac_start,
        "hvac_end": hvac_end,
    }


def default_occupancy_schedule() -> dict[str, Any]:
    days = {d: default_day_block(weekday=True) for d in ("mon", "tue", "wed", "thu", "fri")}
    days["sat"] = default_day_block(weekday=False)
    days["sun"] = default_day_block(weekday=False)
    return {"timezone": "America/Chicago", "days": days}


def default_site_dsm_config() -> dict[str, Any]:
    return {
        "schema_version": SCHEMA_VERSION,
        "setpoints_f": dict(DEFAULT_SETPOINTS_F),
        "occupancy_schedule": default_occupancy_schedule(),
        "peak_day_override": None,
        # Always applied on staged IDFs (no UI toggles).
        "apply_people_plug_schedules": True,
        "apply_hvac_schedules": True,
        "optimum_start": False,
        "optimum_start_f_per_min": 0.10,
        "optimum_start_max_h": 4.0,
    }


def site_dsm_config_path(site: Path | str) -> Path:
    return Path(site) / "reports" / "eplus_gym" / "site_dsm_config.json"


def site_config_apply_report_path(site: Path | str) -> Path:
    return Path(site) / "reports" / "eplus_gym" / "site_config_apply_report.json"


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
        # Migrate legacy start/end -> people_*
        people_start = src.get("people_start", src.get("start", fb["people_start"]))
        people_end = src.get("people_end", src.get("end", fb["people_end"]))
        people_start = _hhmm(people_start, fb["people_start"])
        people_end = _hhmm(people_end, fb["people_end"])
        hvac_start = _hhmm(
            src.get("hvac_start"),
            _shift_hhmm(people_start, -45) if "hvac_start" not in src else fb["hvac_start"],
        )
        hvac_end = _hhmm(
            src.get("hvac_end"),
            _shift_hhmm(people_end, 30) if "hvac_end" not in src else fb["hvac_end"],
        )
        days_out[key] = {
            "occupied": bool(src.get("occupied", fb["occupied"])),
            "people_start": people_start,
            "people_end": people_end,
            "hvac_start": hvac_start,
            "hvac_end": hvac_end,
            # Keep legacy keys for older readers
            "start": people_start,
            "end": people_end,
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
    for flag in (
        "optimum_start",
    ):
        if flag in raw:
            out[flag] = bool(raw[flag])
    # People + HVAC Compact schedules always apply on staged IDFs.
    out["apply_people_plug_schedules"] = True
    out["apply_hvac_schedules"] = True
    try:
        out["optimum_start_f_per_min"] = float(
            raw.get("optimum_start_f_per_min", out["optimum_start_f_per_min"])
        )
    except (TypeError, ValueError):
        pass
    try:
        out["optimum_start_max_h"] = float(
            raw.get("optimum_start_max_h", out["optimum_start_max_h"])
        )
    except (TypeError, ValueError):
        pass
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
        return ["setpoints_f must include four numeric F values"]
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


def optimum_start_lead_hours(cfg: dict[str, Any] | None = None) -> float:
    """Lead hours from 0.10 F/min recovery and heating deadband (capped)."""
    doc = normalize_site_dsm_config(cfg or {})
    if not doc.get("optimum_start"):
        return 0.0
    sp = doc.get("setpoints_f") or {}
    try:
        deadband = abs(float(sp["occupied_heating_f"]) - float(sp["unoccupied_heating_f"]))
    except (KeyError, TypeError, ValueError):
        deadband = 10.0
    if deadband <= 0:
        deadband = 10.0
    rate = float(doc.get("optimum_start_f_per_min") or 0.10)
    max_h = float(doc.get("optimum_start_max_h") or 4.0)
    if rate <= 0:
        return 0.0
    hours = deadband / (rate * 60.0)
    return max(0.0, min(max_h, hours))


def calendar_contract_from_site_config(cfg: dict[str, Any] | None = None) -> dict[str, Any]:
    """Full Site Config document for staged IDF patchers."""
    return deepcopy(normalize_site_dsm_config(cfg or {}))


def site_config_feedback_rows(cfg: dict[str, Any] | None = None) -> list[dict[str, Any]]:
    """Rows for Calibration: what Site Config will write on next staged run."""
    doc = normalize_site_dsm_config(cfg or {})
    sp = doc["setpoints_f"]
    rows: list[dict[str, Any]] = [
        {
            "object": "SCH_HtgSP",
            "field": "occupied / unoccupied heating",
            "site_config_source": "setpoints_f.occupied_heating_f / unoccupied_heating_f",
            "value_written": f"{sp['occupied_heating_f']}F / {sp['unoccupied_heating_f']}F",
            "note": "staged IDF only",
        },
        {
            "object": "SCH_ClgSP",
            "field": "occupied / unoccupied cooling",
            "site_config_source": "setpoints_f.occupied_cooling_f / unoccupied_cooling_f",
            "value_written": f"{sp['occupied_cooling_f']}F / {sp['unoccupied_cooling_f']}F",
            "note": "staged IDF only",
        },
    ]
    occ = doc["occupancy_schedule"]["days"]
    if doc.get("apply_people_plug_schedules"):
        for d in DAY_KEYS:
            day = occ[d]
            if not day.get("occupied"):
                rows.append(
                    {
                        "object": ",".join(PEOPLE_SCHEDULE_NAMES),
                        "field": f"{DAY_LABELS[d]} people",
                        "site_config_source": f"occupancy_schedule.days.{d}",
                        "value_written": "unoccupied (0)",
                        "note": "staged IDF only",
                    }
                )
                continue
            rows.append(
                {
                    "object": ",".join(PEOPLE_SCHEDULE_NAMES[:2]) + ",...",
                    "field": f"{DAY_LABELS[d]} people",
                    "site_config_source": f"people_start/end.{d}",
                    "value_written": f"{day['people_start']} -> {day['people_end']}",
                    "note": "also drives SCH_Equip plugs",
                }
            )
    if doc.get("apply_hvac_schedules"):
        lead = optimum_start_lead_hours(doc)
        for d in DAY_KEYS:
            day = occ[d]
            hvac_start = day["hvac_start"]
            if lead > 0 and day.get("occupied"):
                pulled = _shift_hhmm(day["people_start"], -int(round(lead * 60)))
                # Earlier clock time wins (opt-start pull vs configured HVAC start)
                if _hhmm_to_time(pulled) <= _hhmm_to_time(day["hvac_start"]):
                    hvac_start = pulled
            rows.append(
                {
                    "object": ",".join(HVAC_SCHEDULE_NAMES[:3]) + ",...",
                    "field": f"{DAY_LABELS[d]} HVAC avail",
                    "site_config_source": f"hvac_start/end.{d}"
                    + (f" + opt-start lead {lead:.2f}h" if lead else ""),
                    "value_written": f"{hvac_start} -> {day['hvac_end']}",
                    "note": "Fan/OA/HVAC windowed; SCH_HeatAvail stays always-on (WAHP)",
                }
            )
    if doc.get("optimum_start"):
        rows.append(
            {
                "object": "SCH_FanProxy / SCH_OA / SCH_HVAC",
                "field": "optimum_start lead",
                "site_config_source": (
                    f"{doc.get('optimum_start_f_per_min')} F/min, "
                    f"max {doc.get('optimum_start_max_h')} h"
                ),
                "value_written": f"{optimum_start_lead_hours(doc):.2f} h before people",
                "note": "ZoneHVAC WAHP schedule lead (0 air loops); HeatAvail always-on",
            }
        )
    if doc.get("peak_day_override"):
        rows.append(
            {
                "object": "RunPeriod (via Run DSM)",
                "field": "peak day override",
                "site_config_source": "peak_day_override",
                "value_written": str(doc["peak_day_override"]),
                "note": "Peak day period only; ignores BAS meter peak",
            }
        )
    return rows


def save_apply_report(site: Path | str, report: dict[str, Any]) -> Path:
    path = site_config_apply_report_path(site)
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_name(f".{path.name}.{os.getpid()}.tmp")
    tmp.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    os.replace(tmp, path)
    return path


def load_apply_report(site: Path | str) -> dict[str, Any] | None:
    path = site_config_apply_report_path(site)
    if not path.is_file():
        return None
    try:
        doc = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return None
    return doc if isinstance(doc, dict) else None


def render_overview_staging_options(site: Path) -> dict[str, Any]:
    """Overview: optimum-start toggle only (people/HVAC schedules always apply)."""
    import streamlit as st

    cfg = load_site_dsm_config(site)
    st.markdown("**DSM staging options** (staged IDF only)")
    st.caption(
        "People + plug and HVAC run schedules from Site Config **always** patch "
        "staged IDFs. ``SCH_HeatAvail`` stays always-on (WAHP unocc SP hold); "
        "HVAC schedule lead advances ``SCH_FanProxy`` / ``SCH_OA`` / ``SCH_HVAC`` only — "
        "**not** heating recovery on ``SCH_HtgSP``. "
        "Heating recovery / economic screening lives on **Optimize Tomorrow**. "
        "W2A champion has **no air loops**, so HVAC lead is schedule-based "
        "(not AvailabilityManager:OptimumStart)."
    )
    opt = st.checkbox(
        "HVAC availability lead (fan/OA — not heating recovery)",
        value=bool(cfg.get("optimum_start", False)),
        key="ov_opt_start",
    )
    if opt != bool(cfg.get("optimum_start", False)):
        cfg["optimum_start"] = opt
        cfg["apply_people_plug_schedules"] = True
        cfg["apply_hvac_schedules"] = True
        try:
            save_site_dsm_config(site, cfg)
            st.caption("Staging options saved.")
        except ValueError as exc:
            st.error(str(exc))
    if opt:
        st.caption(
            f"Lead ~{optimum_start_lead_hours(cfg):.2f} h "
            f"(@ {cfg.get('optimum_start_f_per_min')} F/min, "
            f"max {cfg.get('optimum_start_max_h')} h). "
            "HVAC start/end in Site Config are driven by people + lead (greyed out)."
        )
    return cfg


def render_site_config_tab(site: Path, bundle: Any | None = None) -> dict[str, Any]:
    """Streamlit Site Config form. Returns the saved/normalized config."""
    import streamlit as st

    st.subheader("Site Config")
    st.caption(
        "Thermostat, **people** occupancy, and **HVAC** run hours for **staged** DSM runs only. "
        "Never overwrites the published champion IDF. Edits apply on **Save**."
    )
    cfg = load_site_dsm_config(site)
    sp0 = dict(cfg["setpoints_f"])
    occ0 = normalize_occupancy_schedule(cfg.get("occupancy_schedule"))

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
        if getattr(bundle, "epw_coverage_start", None) and getattr(
            bundle, "epw_coverage_end", None
        ):
            cov = f"{bundle.epw_coverage_start} -> {bundle.epw_coverage_end}"
        st.markdown("**Published pack**")
        st.caption(
            f"Champion `{idf_name}` · EPW `{Path(epw).name if epw else '?'}`"
            + (f" · coverage {cov}" if cov else "")
        )

    st.caption(f"Saved: {setpoints_summary(cfg)}")

    with st.form("site_dsm_config_form", clear_on_submit=False):
        c1, c2, c3, c4 = st.columns(4)
        occ_heat = c1.number_input(
            "Occupied heat (F)",
            min_value=50.0,
            max_value=80.0,
            value=float(sp0["occupied_heating_f"]),
            step=0.5,
        )
        unocc_heat = c2.number_input(
            "Unoccupied heat (F)",
            min_value=45.0,
            max_value=75.0,
            value=float(sp0["unoccupied_heating_f"]),
            step=0.5,
        )
        occ_cool = c3.number_input(
            "Occupied cool (F)",
            min_value=65.0,
            max_value=90.0,
            value=float(sp0["occupied_cooling_f"]),
            step=0.5,
        )
        unocc_cool = c4.number_input(
            "Unoccupied cool (F)",
            min_value=70.0,
            max_value=95.0,
            value=float(sp0["unoccupied_cooling_f"]),
            step=0.5,
        )
        st.caption(
            f"Occupied deadband (derived): **{float(occ_cool) - float(occ_heat):.1f} F** "
            "(occ cool - occ heat)"
        )

        st.markdown("**Weekly people + HVAC**")
        opt_on = bool(cfg.get("optimum_start", False))
        st.caption(
            "People drives occupancy and plug loads. HVAC is equipment availability "
            + (
                "(greyed: **optimum start** drives HVAC start from people start − lead; "
                "end follows people end + 30 min)."
                if opt_on
                else "(can start earlier / end later than people)."
            )
        )
        tz = st.text_input("Timezone", value=occ0["timezone"])
        days_out: dict[str, Any] = {}
        lead_h = optimum_start_lead_hours(cfg) if opt_on else 0.0
        for d in DAY_KEYS:
            day = occ0["days"][d]
            st.markdown(f"**{DAY_LABELS[d]}**")
            occupied = st.checkbox(
                "People occupied",
                value=bool(day["occupied"]),
                key=f"site_cfg_occ_{d}",
            )
            p1, p2, h1, h2 = st.columns(4)
            people_start = p1.time_input(
                "People start",
                value=_hhmm_to_time(day["people_start"]),
                key=f"site_cfg_people_s_{d}",
            )
            people_end = p2.time_input(
                "People end",
                value=_hhmm_to_time(day["people_end"]),
                key=f"site_cfg_people_e_{d}",
            )
            ps = _hhmm(people_start, day["people_start"])
            pe = _hhmm(people_end, day["people_end"])
            if opt_on and occupied:
                # Lead before people; end 30 min after people (manual HVAC edits disabled).
                auto_hvac_start = _shift_hhmm(ps, -int(round(lead_h * 60)))
                auto_hvac_end = _shift_hhmm(pe, 30)
                hvac_start = h1.time_input(
                    "HVAC start",
                    value=_hhmm_to_time(auto_hvac_start),
                    key=f"site_cfg_hvac_s_{d}",
                    disabled=True,
                )
                hvac_end = h2.time_input(
                    "HVAC end",
                    value=_hhmm_to_time(auto_hvac_end),
                    key=f"site_cfg_hvac_e_{d}",
                    disabled=True,
                )
                hs, he = auto_hvac_start, auto_hvac_end
            else:
                hvac_start = h1.time_input(
                    "HVAC start",
                    value=_hhmm_to_time(day["hvac_start"]),
                    key=f"site_cfg_hvac_s_{d}",
                    disabled=False,
                )
                hvac_end = h2.time_input(
                    "HVAC end",
                    value=_hhmm_to_time(day["hvac_end"]),
                    key=f"site_cfg_hvac_e_{d}",
                    disabled=False,
                )
                hs = _hhmm(hvac_start, day["hvac_start"])
                he = _hhmm(hvac_end, day["hvac_end"])
            days_out[d] = {
                "occupied": bool(occupied),
                "people_start": ps,
                "people_end": pe,
                "hvac_start": hs,
                "hvac_end": he,
                "start": ps,
                "end": pe,
            }

        st.markdown("**Sim date override**")
        st.caption(
            "Force **Peak day** Run DSM to this calendar date (ignores BAS meter peak). "
            "Does not change Calendar month / winter / year windows."
        )
        use_override = st.checkbox(
            "Override peak day for Run DSM",
            value=bool(cfg.get("peak_day_override")),
        )
        default_day = cfg.get("peak_day_override") or (
            getattr(getattr(bundle, "dial_ladder", None), "peak_day", None)
            or "2026-01-26"
        )
        try:
            default_d = date.fromisoformat(str(default_day)[:10])
        except ValueError:
            default_d = date(2026, 1, 26)
        picked = st.date_input("Peak day override", value=default_d)
        peak_override = picked.isoformat() if use_override and picked else None

        submitted = st.form_submit_button("Save Site Config", type="primary")

    if submitted:
        sp = {
            "occupied_heating_f": float(occ_heat),
            "unoccupied_heating_f": float(unocc_heat),
            "occupied_cooling_f": float(occ_cool),
            "unoccupied_cooling_f": float(unocc_cool),
        }
        errs = validate_setpoints_f(sp)
        if errs:
            for e in errs:
                st.error(e)
        else:
            draft = {
                **cfg,
                "schema_version": SCHEMA_VERSION,
                "setpoints_f": sp,
                "occupancy_schedule": {"timezone": tz, "days": days_out},
                "peak_day_override": peak_override,
            }
            path = save_site_dsm_config(site, draft)
            st.success(f"Saved `{path}`")
            cfg = load_site_dsm_config(site)

    st.session_state["site_dsm_config"] = cfg
    return cfg

"""BOPTEST-shaped DSM Run panel (W2A champion only)."""
from __future__ import annotations

import json
import subprocess
import sys
import time
from datetime import date, datetime, timezone
from pathlib import Path
from typing import TYPE_CHECKING, Any

import pandas as pd

from eplus_gym.discover import energyplus_available
from eplus_gym.lookup_emulator import list_farm_days, resolve_w2a_farm_root, w2a_farm_ready
from eplus_gym.month_calendar import DEPLOYABLE_STRATEGIES
from eplus_gym.simulate import FAMILY_W2A, run_rule_episode, trajectory_frame
from eplus_gym_app.period_explorer import PERIOD_PRESETS
from eplus_gym_app.weather_files import (
    KIND_AMY,
    KIND_TMY_MSN,
    epws_for_mode,
    weather_inventory,
)

if TYPE_CHECKING:
    from eplus_gym_app.site_bundle import SiteUiBundle

_APP = Path(__file__).resolve().parents[1]
_CLI = _APP / "scripts" / "run_eplus_gym_rules.py"

STRATEGY_LABELS = {
    "baseline": "E+ Site Config (twin)",
    "flat_24_7": "E+ Flat 24/7",
    "deep_setback": "E+ Deep setback",
    "stagger_preheat": "E+ Stagger preheat",
    "morning_all_on": "E+ Morning all-on",
    "optimized": "E+ Optimized (proposal)",
}

# Short tutorial copy for Results strategy tabs (what the rule does to E+).
STRATEGY_TUTORIALS: dict[str, str] = {
    "baseline": (
        "**E+ Site Config (twin)** is *not* the BAS meter. It is EnergyPlus replaying "
        "the published W2A twin with your Site Config occupied/unoccupied heat. "
        "Use it to judge how close the twin is to **Actual BAS**, and as the "
        "reference when comparing other E+ strategies (kW trim / kWh penalty)."
    ),
    "flat_24_7": (
        "**Flat 24/7** holds occupied heat all day and night (no setback). "
        "Usually the highest peak and kWh - a 'what if we never set back' bound."
    ),
    "deep_setback": (
        "**Deep setback** drops unoccupied heat further than Site Config "
        "(deeper than the twin baseline). Expect lower unoccupied heating energy and a "
        "possible morning recovery peak - compare peak kW and kWh vs the twin baseline "
        "and vs Actual BAS."
    ),
    "stagger_preheat": (
        "**Stagger preheat** stages morning recovery across zones to shave coincident peak."
    ),
    "morning_all_on": (
        "**Morning all-on** pulls heating early together - often a peak-forming stress test."
    ),
    "optimized": (
        "**Optimized (proposal)** comes from **Optimize Tomorrow** (economic screening). "
        "It is a recommendation artifact only - not auto-written to Site Config or BACnet."
    ),
}


def pick_frame(
    frames: dict[str, pd.DataFrame], *keys: str
) -> pd.DataFrame | None:
    """Return the first mapped DataFrame without using DataFrame truthiness."""
    for key in keys:
        if key in frames:
            df = frames[key]
            if df is not None:
                return df
    return None


def frame_map(value: Any) -> dict[str, pd.DataFrame]:
    """Coerce session/disk payload to a str->DataFrame map (never bool(DataFrame))."""
    if not isinstance(value, dict):
        return {}
    out: dict[str, pd.DataFrame] = {}
    for key, val in value.items():
        if isinstance(val, pd.DataFrame):
            out[str(key)] = val
    return out


def coalesce_frame(*candidates: Any) -> pd.DataFrame | None:
    """First non-None DataFrame among candidates (no DataFrame truthiness)."""
    for cand in candidates:
        if isinstance(cand, pd.DataFrame):
            return cand
    return None


def calendar_month_options(bundle: "SiteUiBundle") -> list[str]:
    months: set[str] = set()
    peak = str(getattr(getattr(bundle, "dial_ladder", None), "peak_day", "") or "")
    if len(peak) >= 7:
        months.add(peak[:7])
    months.update(("2026-01", "2026-02"))  # practice-pack months; BAS months dominate when present
    try:
        from eplus_gym_app.load_profiles import load_bas_demand_oat

        bas = load_bas_demand_oat(bundle, csv_path=bundle.bas_demand_oat_csv)
        months.update(str(d)[:7] for d in bas["local_day"].astype(str))
    except Exception:  # noqa: BLE001
        pass
    return sorted(m for m in months if m and len(m) == 7)


def default_calendar_month(months: list[str], peak_day: str | None) -> str:
    """Calendar-month widget defaults to the BAS peak day's month, not the earliest month."""
    ym = (peak_day or "")[:7]
    if ym in months:
        return ym
    return months[0] if months else "2026-01"


def strategy_library(site_cfg: dict[str, Any] | None = None) -> dict[str, Any]:
    """Desktop strategy cards + 96-step SP series (Site Config deg F when provided)."""
    from eplus_gym.controllers import RuleController, effective_htg_setpoints_f

    sp = (site_cfg or {}).get("setpoints_f") if isinstance(site_cfg, dict) else None
    occ = None
    unocc = None
    if isinstance(sp, dict):
        if "occupied_heating_f" in sp:
            occ = float(sp["occupied_heating_f"])
        if "unoccupied_heating_f" in sp:
            unocc = float(sp["unoccupied_heating_f"])

    rows: list[dict[str, Any]] = []
    series: dict[str, list[float]] = {}
    for sid in DEPLOYABLE_STRATEGIES:
        eff = effective_htg_setpoints_f(
            sid, occ_htg_sp_f=occ, unocc_htg_sp_f=unocc
        )
        ctrl = RuleController(sid, occ_htg_sp_f=occ, unocc_htg_sp_f=unocc)
        series[sid] = ctrl.series_f()
        rows.append(
            {
                "strategy_id": sid,
                "label": STRATEGY_LABELS.get(sid, sid),
                "occ_htg_sp_f": eff["occ_htg_sp_f"],
                "unocc_htg_sp_f": eff["unocc_htg_sp_f"],
                "preheat_lead_h": float(
                    (ctrl.contract.get("meta") or {}).get("preheat_lead_h") or 0.0
                ),
                "stagger_min": float(
                    (ctrl.contract.get("meta") or {}).get("stagger_min") or 0.0
                ),
            }
        )
    return {"rows": rows, "series": series}


def live_run_jobs(
    *,
    strategies: list[str],
    weathers: list[tuple[str, Path]],
    begin: str,
    end: str,
    max_steps: int,
) -> list[dict[str, Any]]:
    """One CLI job per strategy x weather. Keys are strategy:weather_kind."""
    jobs: list[dict[str, Any]] = []
    for sid in strategies:
        for kind, epw in weathers:
            jobs.append(
                {
                    "strategy_id": sid,
                    "weather_kind": kind,
                    "epw": Path(epw),
                    "begin": begin,
                    "end": end,
                    "max_steps": int(max_steps),
                    "key": f"{sid}:{kind}",
                }
            )
    return jobs


def split_frame_key(key: str) -> tuple[str, str]:
    if ":" in str(key):
        sid, kind = str(key).split(":", 1)
        return sid, kind
    return str(key), ""


def resolve_dsm_mode(site: Path, *, family: str = FAMILY_W2A) -> tuple[str, str]:
    """Return (lookup|live|error, reason). Never silently uses IdealLoads farm."""
    site = Path(site)
    if family != FAMILY_W2A:
        return "error", "human DSM console is W2A-only"
    if w2a_farm_ready(site):
        return "lookup", "champion farm present under eplus/dsm_farm_w2a"
    if energyplus_available():
        return "live", "no champion farm; live EnergyPlus via CLI subprocess"
    return (
        "error",
        "No champion farm (eplus/dsm_farm_w2a) and EnergyPlus is unavailable. "
        "Will not fall back to IdealLoads. Agent: grow a sparse W2A farm or set ENERGYPLUS_ROOT.",
    )


def dsm_kpis(
    df: pd.DataFrame,
    meta: dict[str, Any],
    *,
    actual_peak_kw: float | None = None,
    baseline_peak_kw: float | None = None,
    baseline_kwh: float | None = None,
) -> dict[str, Any]:
    peak = float(df["facility_kw"].max()) if df is not None and not df.empty and "facility_kw" in df.columns else None
    kwh = (
        float(df["facility_kw"].sum() * 0.25)
        if df is not None and not df.empty and "facility_kw" in df.columns
        else None
    )
    vs_actual = None
    if peak is not None and actual_peak_kw not in (None, 0):
        vs_actual = (peak - float(actual_peak_kw)) / float(actual_peak_kw) * 100.0
    vs_base = None
    kw_trim = None
    if peak is not None and baseline_peak_kw not in (None, 0):
        vs_base = (peak - float(baseline_peak_kw)) / float(baseline_peak_kw) * 100.0
        kw_trim = float(baseline_peak_kw) - float(peak)
    kwh_penalty = None
    if kwh is not None and baseline_kwh is not None:
        kwh_penalty = float(kwh) - float(baseline_kwh)
    return {
        "peak_kw": peak,
        "kwh": kwh,
        "kw_trim": kw_trim,
        "kwh_penalty": kwh_penalty,
        "vs_actual_pct": vs_actual,
        "vs_baseline_pct": vs_base,
        "honesty": meta.get("honesty"),
        "provenance": meta.get("provenance"),
        "mode": meta.get("mode"),
        "family": meta.get("family"),
        "promote": bool(meta.get("promote", False)),
        "day": meta.get("day"),
        "strategy_id": meta.get("strategy_id"),
    }


def attach_baseline_deltas(kpis_by: dict[str, dict[str, Any]]) -> dict[str, dict[str, Any]]:
    """Window-total kW trim and kWh penalty vs the baseline strategy.

    kw_trim = baseline peak kW - strategy peak kW  (+ = trimmed demand)
    kwh_penalty = strategy kWh - baseline kWh      (+ = energy penalty)
    Totals cover the whole selected window (peak day / month / winter / year).
    """
    base = kpis_by.get("baseline") or {}
    b_peak = base.get("peak_kw")
    b_kwh = base.get("kwh")
    for sid, row in kpis_by.items():
        peak = row.get("peak_kw")
        kwh = row.get("kwh")
        if peak is not None and b_peak not in (None, 0):
            row["kw_trim"] = float(b_peak) - float(peak)
            row["vs_baseline_pct"] = (float(peak) - float(b_peak)) / float(b_peak) * 100.0
        elif sid == "baseline" and peak is not None:
            row["kw_trim"] = 0.0
            row["vs_baseline_pct"] = 0.0
        if kwh is not None and b_kwh is not None:
            row["kwh_penalty"] = float(kwh) - float(b_kwh)
        elif sid == "baseline" and kwh is not None:
            row["kwh_penalty"] = 0.0
    return kpis_by


def attach_actual_deltas(
    kpis_by: dict[str, dict[str, Any]],
    actual_peak_kw: float | None,
) -> dict[str, dict[str, Any]]:
    """Fill vs_actual_pct from BAS meter peak when missing (AMY day <-> meter day)."""
    if actual_peak_kw in (None, 0):
        return kpis_by
    ap = float(actual_peak_kw)
    for row in kpis_by.values():
        peak = row.get("peak_kw")
        if peak is None:
            continue
        if row.get("vs_actual_pct") is None:
            row["vs_actual_pct"] = (float(peak) - ap) / ap * 100.0
        row["actual_peak_kw"] = ap
    return kpis_by


def run_dsm_lookup(
    *,
    site_root: Path,
    strategy_id: str,
    day: str,
    actual_peak_kw: float | None = None,
) -> dict[str, Any]:
    result = run_rule_episode(
        site_root=Path(site_root),
        strategy_id=strategy_id,
        day=day,
        mode="lookup",
        family=FAMILY_W2A,
    )
    df = trajectory_frame(result)
    baseline_peak = None
    if strategy_id != "baseline":
        try:
            base = run_rule_episode(
                site_root=Path(site_root),
                strategy_id="baseline",
                day=day,
                mode="lookup",
                family=FAMILY_W2A,
            )
            bdf = trajectory_frame(base)
            if not bdf.empty and "facility_kw" in bdf.columns:
                baseline_peak = float(bdf["facility_kw"].max())
        except FileNotFoundError:
            baseline_peak = None
    kpis = dsm_kpis(
        df,
        result["meta"],
        actual_peak_kw=actual_peak_kw,
        baseline_peak_kw=baseline_peak,
    )
    return {"frame": df, "meta": result["meta"], "kpis": kpis}


def meter_peak_day_for_period(
    bas: pd.DataFrame,
    *,
    preset: str,
    peak_anchor: str,
    month: str | None = None,
) -> dict[str, Any]:
    """Pick the BAS meter peak day inside a period. Live E+ still runs that one day."""
    from eplus_gym_app.period_explorer import days_for_period

    if bas is None or bas.empty or "local_day" not in bas.columns:
        return {
            "day": peak_anchor,
            "preset": preset,
            "month": month,
            "window_days": [peak_anchor],
            "actual_peak_kw": None,
            "why": "no interval meter rows; using published dial peak day",
        }
    days = days_for_period(bas, preset=preset, peak_day=peak_anchor, month=month)
    window = bas.loc[bas["local_day"].astype(str).isin(set(days))]
    if window.empty or "kw_avg" not in window.columns:
        return {
            "day": peak_anchor,
            "preset": preset,
            "month": month,
            "window_days": list(days),
            "actual_peak_kw": None,
            "why": "period window empty; using published dial peak day",
        }
    idx = window["kw_avg"].idxmax()
    day = str(window.loc[idx, "local_day"])
    peak_kw = float(window.loc[idx, "kw_avg"])
    label = preset
    if preset == "Calendar month" and month:
        label = f"Calendar month {month}"
    return {
        "day": day,
        "preset": preset,
        "month": month,
        "window_days": list(days),
        "actual_peak_kw": peak_kw,
        "why": f"BAS meter peak inside {label} ({len(days)} day window)",
    }


def pick_run_day(bundle: SiteUiBundle, preset: str, month: str | None = None) -> str:
    return pick_run_context(bundle, preset, month)["day"]


def pick_run_context(
    bundle: SiteUiBundle, preset: str, month: str | None = None
) -> dict[str, Any]:
    """Resolve which single calendar day a Run will simulate."""
    peak = bundle.dial_ladder.peak_day
    try:
        from eplus_gym_app.load_profiles import load_bas_demand_oat

        bas = load_bas_demand_oat(bundle, csv_path=bundle.bas_demand_oat_csv)
    except Exception:  # noqa: BLE001
        bas = pd.DataFrame()
    ctx = meter_peak_day_for_period(
        bas, preset=preset, peak_anchor=peak, month=month
    )
    farm = resolve_w2a_farm_root(bundle.site)
    farm_days = list_farm_days(bundle.site, "baseline", farm_root=farm)
    ctx["farm_has_day"] = ctx["day"] in set(farm_days)
    ctx["bas"] = bas
    return ctx


def period_run_spec(ctx: dict[str, Any], preset: str) -> dict[str, Any]:
    """Closed-loop window: peak day = 96 steps; week/month/winter = calendar span."""
    peak = str(ctx.get("day") or "")[:10]
    days = [str(d)[:10] for d in (ctx.get("window_days") or []) if d]
    if preset == "Peak day" or not days:
        days = [peak] if peak else days
    if not days:
        raise ValueError("no period days")
    begin, end = min(days), max(days)
    n = (date.fromisoformat(end) - date.fromisoformat(begin)).days + 1
    return {
        "begin": begin,
        "end": end,
        "n_days": n,
        "max_steps": n * 96,
        "period": f"{begin}/{end}",
        "window_days": days,
        "peak_day": peak or begin,
    }


def daily_peaks_from_traj(df: pd.DataFrame) -> pd.DataFrame:
    """Aggregate 15-min trajectory to daily peak kW."""
    empty = pd.DataFrame(columns=["local_day", "peak_kw"])
    if df is None or getattr(df, "empty", True) or "facility_kw" not in df.columns:
        return empty
    work = df.copy()
    if "day" in work.columns:
        work["local_day"] = work["day"].astype(str).str[:10]
    elif "step" in work.columns:
        work["local_day"] = (work["step"].astype(int) // 96).astype(str)
    else:
        return empty
    return (
        work.groupby("local_day", as_index=False)["facility_kw"]
        .max()
        .rename(columns={"facility_kw": "peak_kw"})
        .sort_values("local_day")
    )


def slice_traj_for_day(df: pd.DataFrame, day: str) -> pd.DataFrame:
    """15-min rows for one calendar day; remap step to 0..95 for overlay."""
    if df is None or getattr(df, "empty", True):
        return pd.DataFrame()
    want = str(day)[:10]
    work = df.copy()
    if "day" in work.columns:
        sub = work.loc[work["day"].astype(str).str[:10] == want].copy()
    else:
        sub = work.iloc[:96].copy()
    if sub.empty:
        return pd.DataFrame()
    if "step" in sub.columns:
        sub["step"] = sub["step"].astype(int) % 96
        sub["hod"] = sub["step"].astype(float) / 4.0
    return sub


def actual_day_profile(bundle: SiteUiBundle, day: str) -> pd.DataFrame:
    try:
        from eplus_gym_app.load_profiles import load_bas_demand_oat, peak_day_bas_profile

        bas = load_bas_demand_oat(bundle, csv_path=bundle.bas_demand_oat_csv)
        return peak_day_bas_profile(bas, str(day)[:10])
    except Exception:  # noqa: BLE001
        return pd.DataFrame()


def stage_idf_for_period(
    src: Path,
    dest: Path,
    begin: str,
    end: str,
    *,
    site_root: Path | None = None,
    site_config: dict[str, Any] | None = None,
    six_zone_actuators: bool = False,
) -> Path:
    """Copy IDF with RunPeriod clipped to ``begin``..``end``. Never overwrite champion.

    When ``site_root`` or ``site_config`` is provided, patch setpoints + people/HVAC
    schedules from Site Config onto the **staged** copy only.
    When ``six_zone_actuators`` is True, split DualSP into six DSM heating
    schedules for independent Gym actuators (CLI six-zone optimizer).
    """
    from datetime import date

    from eplus_native.idf_stage import (
        disable_sizing_periods,
        ensure_zone_mean_air_temperature_outputs,
        patch_run_period,
    )
    from eplus_native.schedule_calendar_repair import apply_site_config_to_idf
    from eplus_native.six_zone_htg_stage import (
        stage_six_zone_heating_actuators,
        verify_six_zone_staging,
    )

    src = Path(src)
    dest = Path(dest)
    if dest.resolve() == src.resolve():
        raise ValueError("refusing to overwrite source IDF; pass a staged dest path")
    b = date.fromisoformat(str(begin)[:10])
    e = date.fromisoformat(str(end)[:10])
    dest.parent.mkdir(parents=True, exist_ok=True)
    text = patch_run_period(
        src.read_text(encoding="utf-8"),
        begin_month=b.month,
        begin_day=b.day,
        end_month=e.month,
        end_day=e.day,
        begin_year=b.year,
        end_year=e.year,
        name=f"DSM_{b.isoformat()}_{e.isoformat()}",
    )
    # Operational weather-only scoring: never run sizing-period callbacks.
    text = disable_sizing_periods(text)
    text = ensure_zone_mean_air_temperature_outputs(text)
    six_zone_prov: dict[str, Any] = {}
    if six_zone_actuators:
        text, six_zone_prov = stage_six_zone_heating_actuators(text)
        verdict = verify_six_zone_staging(text)
        if not verdict["ok"]:
            raise ValueError("six-zone staging failed: " + "; ".join(verdict["issues"]))
        six_zone_prov["verify"] = verdict
    cfg = site_config
    if cfg is None and site_root is not None:
        try:
            from eplus_gym_app.site_config import (
                calendar_contract_from_site_config,
                load_site_dsm_config,
                save_apply_report,
            )

            cfg = calendar_contract_from_site_config(load_site_dsm_config(site_root))
        except Exception:  # noqa: BLE001
            cfg = None
    elif cfg is not None and "setpoints_f" not in cfg:
        try:
            from eplus_gym_app.site_config import calendar_contract_from_site_config

            cfg = calendar_contract_from_site_config(cfg)
        except Exception:  # noqa: BLE001
            pass
    report: dict[str, Any] = {"six_zone_actuators": six_zone_prov}
    if cfg is not None:
        text, sc_report = apply_site_config_to_idf(text, cfg)
        report.update(sc_report)
        if site_root is not None:
            try:
                from eplus_gym_app.site_config import save_apply_report

                save_apply_report(
                    site_root,
                    {
                        **report,
                        "staged_idf": str(dest),
                        "begin": str(begin)[:10],
                        "end": str(end)[:10],
                        "source_idf": str(src),
                    },
                )
            except Exception:  # noqa: BLE001
                pass
    dest.write_text(text, encoding="utf-8")
    return dest

def stage_idf_for_day(
    src: Path,
    dest: Path,
    day: str,
    *,
    site_root: Path | None = None,
    site_config: dict[str, Any] | None = None,
) -> Path:
    """Copy IDF with RunPeriod clipped to ``day``. Never overwrite the champion."""
    return stage_idf_for_period(
        src, dest, day, day, site_root=site_root, site_config=site_config
    )


def format_hms(seconds: float) -> str:
    """Human elapsed for status / Results (0s, 12s, 3m 05s, 1h 02m 01s)."""
    s = max(0, int(round(float(seconds))))
    h, rem = divmod(s, 3600)
    m, sec = divmod(rem, 60)
    if h:
        return f"{h}h {m:02d}m {sec:02d}s"
    if m:
        return f"{m}m {sec:02d}s"
    return f"{sec}s"


def live_log_tail(log: Path, *, n: int = 24) -> str:
    if not log.is_file():
        return ""
    try:
        lines = log.read_text(encoding="utf-8", errors="ignore").splitlines()
    except OSError:
        return ""
    return "\n".join(lines[-n:])


def summarize_eplus_failure(log: Path, *, exit_code: int | None = None) -> str:
    """Pull a short human diagnosis from live.log (Terminated / traceback)."""
    text = live_log_tail(log, n=80)
    if not text.strip():
        return f"CLI exited {exit_code}" if exit_code not in (None, 0) else "EnergyPlus failed (empty live.log)"
    lowered = text.lower()
    bits: list[str] = []
    if "energyplus terminated" in lowered or "error(s) detected" in lowered:
        bits.append("EnergyPlus terminated with errors during reset/startup")
    if "nonetype" in lowered and "values" in lowered:
        bits.append("gym received no observation after E+ abort (obs is None)")
    if "will not fall back to idealloads" in lowered:
        bits.append("no IdealLoads fallback")
    # last non-empty meaningful line
    for line in reversed(text.splitlines()):
        s = line.strip()
        if not s:
            continue
        if s.startswith("File ") or s.startswith("Traceback"):
            continue
        bits.append(s[:220])
        break
    if exit_code not in (None, 0):
        bits.insert(0, f"exit code {exit_code}")
    return "  |  ".join(dict.fromkeys(bits)) or text[-300:]


def wait_live_subprocess(
    proc: subprocess.Popen,
    *,
    status: Any,
    job_label: str,
    campaign_t0: float,
    job_t0: float,
    job_index: int,
    job_total: int,
    poll_s: float = 1.0,
    log_path: Path | None = None,
    log_handle: Any | None = None,
) -> tuple[int, float]:
    """Poll EnergyPlus until exit; refresh status with live job + campaign timers."""
    try:
        while proc.poll() is None:
            job_elapsed = time.perf_counter() - job_t0
            camp_elapsed = time.perf_counter() - campaign_t0
            health = ""
            if log_path is not None and log_path.is_file():
                try:
                    snippet = log_path.read_text(encoding="utf-8", errors="ignore")[-500:].lower()
                except OSError:
                    snippet = ""
                if "energyplus terminated" in snippet or "error(s) detected" in snippet:
                    health = "  |  E+ ERROR in log"
            status.update(
                label=(
                    f"{job_label}  |  sim {job_index}/{job_total}  |  "
                    f"job {format_hms(job_elapsed)}  |  total {format_hms(camp_elapsed)}"
                    f"{health}"
                ),
                state="running",
            )
            time.sleep(max(0.2, float(poll_s)))
        code = int(proc.returncode if proc.returncode is not None else 0)
        return code, time.perf_counter() - job_t0
    finally:
        if log_handle is not None:
            try:
                log_handle.close()
            except Exception:  # noqa: BLE001
                pass


def start_live_subprocess(
    *,
    site: Path,
    strategy_id: str,
    epw: Path,
    idf: Path,
    out_dir: Path,
    day: str | None = None,
    begin: str | None = None,
    end: str | None = None,
    max_steps: int = 96,
) -> tuple[subprocess.Popen, Any, Path]:
    """Launch CLI live W2A run (do not bind pyenergyplus into Streamlit)."""
    out_dir.mkdir(parents=True, exist_ok=True)
    begin = begin or day
    end = end or day or begin
    cmd = [
        sys.executable,
        "-u",
        str(_CLI),
        "--mode",
        "live",
        "--family",
        "w2a",
        "--strategies",
        strategy_id,
        "--epw",
        str(epw),
        "--idf",
        str(idf),
        "--out",
        str(out_dir),
        "--max-steps",
        str(int(max_steps)),
    ]
    if begin:
        cmd.extend(["--day", begin, "--begin", begin])
    if end:
        cmd.extend(["--end", end])
    log = out_dir / "live.log"
    handle = log.open("w", encoding="utf-8")
    proc = subprocess.Popen(
        cmd,
        cwd=str(_APP),
        stdout=handle,
        stderr=subprocess.STDOUT,
        text=True,
    )
    return proc, handle, log


def _resolve_epw(bundle: SiteUiBundle) -> Path | None:
    inv = weather_inventory(bundle.site, published=bundle.epw)
    return inv.get("amy") or inv.get("tmy")


def _eplus_with_oat_f(df: pd.DataFrame | None) -> pd.DataFrame:
    if df is None:
        return pd.DataFrame()
    out = df.copy()
    if "oat_c" in out.columns and "oat_f" not in out.columns:
        out["oat_f"] = out["oat_c"].astype(float) * 9.0 / 5.0 + 32.0
    return out


def last_run_pointer(site: Path) -> Path:
    return Path(site) / "reports" / "eplus_gym" / "last_dsm_run.json"


def load_last_run_meta(bundle: SiteUiBundle) -> dict[str, Any] | None:
    """Pointer JSON only (preset / window_days). Does not require parquets."""
    ptr = last_run_pointer(bundle.site)
    if not ptr.is_file():
        return None
    try:
        doc = json.loads(ptr.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return None
    return doc if isinstance(doc, dict) else None


def persist_last_run(
    site: Path,
    *,
    df: pd.DataFrame,
    actual: pd.DataFrame,
    kpis: dict[str, Any],
    strategy: str,
    day: str,
    preset: str,
    mode: str,
    epw_name: str,
    why: str,
    window_days: list[str],
    parquet: str | None = None,
    png: str | None = None,
    elapsed_s: float | None = None,
    out_dir: str | None = None,
    weather_mode: str | None = None,
    period: str | None = None,
    max_steps: int | None = None,
    n_days: int | None = None,
    parquets: dict[str, str] | None = None,
    elapsed_by_weather: dict[str, float] | None = None,
    tmy_note: str | None = None,
    weather_kind: str | None = None,
    strategies: list[str] | None = None,
    kpis_by_strategy: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Write last-run pointer (no DataFrames) and return the session payload."""
    payload = {
        "kpis": kpis,
        "frame": df,
        "actual": actual,
        "title": f"E+ champion {strategy} vs Actual meter  |  {day}  |  {preset}",
        "strategy": strategy,
        "day": day,
        "preset": preset,
        "mode": mode,
        "epw_name": epw_name,
        "why": why,
        "window_n": len(window_days),
        "window_days": list(window_days),
        "parquet": parquet,
        "png": png,
        "elapsed_s": elapsed_s,
        "out_dir": out_dir,
        "site": str(Path(site)),
        "weather_mode": weather_mode,
        "period": period,
        "max_steps": max_steps,
        "n_days": n_days,
        "parquets": dict(parquets or {}),
        "elapsed_by_weather": dict(elapsed_by_weather or {}),
        "tmy_note": tmy_note,
        "weather_kind": weather_kind,
        "loop": "CLOSED_LOOP_RULE_DR",
        "weekend_sp": "repeat_96_step_profile",
        "promote": False,
        "strategies": list(strategies or []),
        "kpis_by_strategy": dict(kpis_by_strategy or {}),
    }
    ptr = last_run_pointer(site)
    ptr.parent.mkdir(parents=True, exist_ok=True)
    disk = {k: v for k, v in payload.items() if k not in {"frame", "actual", "frames"}}
    ptr.write_text(json.dumps(disk, indent=2), encoding="utf-8")
    return payload


def load_last_run(bundle: SiteUiBundle) -> dict[str, Any] | None:
    ptr = last_run_pointer(bundle.site)
    if not ptr.is_file():
        return None
    try:
        doc = json.loads(ptr.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return None
    parquets = dict(doc.get("parquets") or {})
    frames: dict[str, pd.DataFrame] = {}
    for kind, path in parquets.items():
        p = Path(str(path))
        if p.is_file():
            try:
                frames[kind] = pd.read_parquet(p)
            except Exception:  # noqa: BLE001
                continue
    pq = Path(str(doc.get("parquet") or ""))
    df = pick_frame(frames, KIND_AMY)
    if df is None and frames:
        df = next(iter(frames.values()))
    if df is None and pq.is_file():
        try:
            df = pd.read_parquet(pq)
        except Exception:  # noqa: BLE001
            df = None
    if df is None:
        return None
    doc["frame"] = df
    doc["frames"] = frames
    doc["actual"] = actual_day_profile(bundle, str(doc.get("day") or ""))
    return doc


def _store_run(
    *,
    site: Path,
    df: pd.DataFrame,
    actual: pd.DataFrame,
    kpis: dict[str, Any],
    strategy: str,
    day: str,
    preset: str,
    mode: str,
    epw_name: str,
    why: str,
    window_days: list[str],
    parquet: str | None = None,
    png: str | None = None,
    elapsed_s: float | None = None,
    out_dir: str | None = None,
    weather_mode: str | None = None,
    period: str | None = None,
    max_steps: int | None = None,
    n_days: int | None = None,
    parquets: dict[str, str] | None = None,
    elapsed_by_weather: dict[str, float] | None = None,
    tmy_note: str | None = None,
    weather_kind: str | None = None,
    frames: dict[str, pd.DataFrame] | None = None,
    strategies: list[str] | None = None,
    kpis_by_strategy: dict[str, Any] | None = None,
) -> dict:
    payload = persist_last_run(
        site,
        df=df,
        actual=actual,
        kpis=kpis,
        strategy=strategy,
        day=day,
        preset=preset,
        mode=mode,
        epw_name=epw_name,
        why=why,
        window_days=window_days,
        parquet=parquet,
        png=png,
        elapsed_s=elapsed_s,
        out_dir=out_dir,
        weather_mode=weather_mode,
        period=period,
        max_steps=max_steps,
        n_days=n_days,
        parquets=parquets,
        elapsed_by_weather=elapsed_by_weather,
        tmy_note=tmy_note,
        weather_kind=weather_kind,
        strategies=strategies,
        kpis_by_strategy=kpis_by_strategy,
    )
    if isinstance(frames, dict) and frames:
        payload["frames"] = frames
    return payload


def _actual_peak(bundle: SiteUiBundle, day: str) -> float | None:
    try:
        from eplus_gym_app.load_profiles import load_bas_demand_oat

        bas = load_bas_demand_oat(bundle, csv_path=bundle.bas_demand_oat_csv)
        sub = bas.loc[bas["local_day"].astype(str) == str(day)[:10]]
        if sub.empty:
            return None
        return float(sub["kw_avg"].max())
    except Exception:  # noqa: BLE001
        return None


_WX_LABEL = {
    KIND_AMY: "E+ AMY",
    KIND_TMY_MSN: "E+ TMY",
}
_WX_COLOR = {
    KIND_AMY: "#2a9d8f",
    KIND_TMY_MSN: "#e9c46a",
}


def _collect_traj(out_dir: Path) -> Path | None:
    frames = sorted(out_dir.glob("traj_*.parquet"))
    if not frames and (out_dir / "runs").is_dir():
        frames = sorted((out_dir / "runs").glob("*.parquet"))
    return frames[0] if frames else None


def _campaign_cli() -> Path:
    return _APP / "scripts" / "run_dsm_campaign.py"


def start_dsm_campaign_subprocess(*, site: Path, request_path: Path) -> subprocess.Popen:
    """Launch durable campaign supervisor (Streamlit must not import pyenergyplus)."""
    import os

    log_dir = Path(site) / "reports" / "eplus_gym"
    log_dir.mkdir(parents=True, exist_ok=True)
    log = log_dir / "campaign_supervisor.log"
    handle = log.open("a", encoding="utf-8")
    cmd = [
        sys.executable,
        "-u",
        str(_campaign_cli()),
        "--site",
        str(site),
        "--request",
        str(request_path),
    ]
    env = os.environ.copy()
    env["SITE_ROOT"] = str(site)
    env["LAKESIDE_SITE_ROOT"] = str(site)
    return subprocess.Popen(
        cmd,
        cwd=str(_APP),
        stdout=handle,
        stderr=subprocess.STDOUT,
        text=True,
        start_new_session=True,
        env=env,
    )

# Streamlit Run DSM UI archived to archive/streamlit_ui_2026-08-13/.

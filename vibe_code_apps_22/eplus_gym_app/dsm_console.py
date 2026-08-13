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
        "Usually the highest peak and kWh — a 'what if we never set back' bound."
    ),
    "deep_setback": (
        "**Deep setback** drops unoccupied heat further than Site Config "
        "(deeper than the twin baseline). Expect lower unoccupied heating energy and a "
        "possible morning recovery peak — compare peak kW and kWh vs the twin baseline "
        "and vs Actual BAS."
    ),
    "stagger_preheat": (
        "**Stagger preheat** stages morning recovery across zones to shave coincident peak."
    ),
    "morning_all_on": (
        "**Morning all-on** pulls heating early together — often a peak-forming stress test."
    ),
    "optimized": (
        "**Optimized (proposal)** comes from **Optimize Tomorrow** (economic screening). "
        "It is a recommendation artifact only — not auto-written to Site Config or BACnet."
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
    """Fill vs_actual_pct from BAS meter peak when missing (AMY day ↔ meter day)."""
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
) -> Path:
    """Copy IDF with RunPeriod clipped to ``begin``..``end``. Never overwrite champion.

    When ``site_root`` or ``site_config`` is provided, patch setpoints + people/HVAC
    schedules from Site Config onto the **staged** copy only.
    """
    from datetime import date

    from eplus_native.idf_stage import (
        disable_sizing_periods,
        ensure_zone_mean_air_temperature_outputs,
        patch_run_period,
    )
    from eplus_native.schedule_calendar_repair import apply_site_config_to_idf

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
    report: dict[str, Any] = {}
    if cfg is not None:
        text, report = apply_site_config_to_idf(text, cfg)
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
) -> None:
    import streamlit as st

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
    st.session_state["dsm_last"] = payload
    st.session_state["lakeside_main_tabs"] = "Run DSM"


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


def render_run_dsm_tab(bundle: SiteUiBundle) -> None:
    import streamlit as st
    from datetime import timedelta

    from eplus_gym_app.dsm_campaign import (
        active_campaign_running,
        build_jobs,
        cancel_request_path,
        current_run_path,
        default_strategy_selection,
        elapsed_seconds,
        peak_day_smoke_ok,
        reconcile_campaign,
        request_cancel,
        write_campaign,  # noqa: F401 - imported for tests/monkeypatch
    )
    from eplus_gym_app.dsm_preflight import sha256_file
    from eplus_gym_app.plots import (
        COLORS,
        dsm_compare_overlay_figure,
        dsm_panel_figure,
        dsm_trajectory_figure,
        period_daily_peak_figure,
        strategy_setpoint_figure,
    )

    st.subheader("Run DSM")
    from eplus_gym_app.site_config import load_site_dsm_config, setpoints_summary

    site_cfg = load_site_dsm_config(bundle.site)
    st.caption(
        f"Champion `{bundle.dsm_champion}`  |  W2A_PHYSICAL_DSM  |  promote=False. "
        "**Actual BAS** = meter truth. **E+ Site Config (twin)** = EnergyPlus with Site Config "
        "(not the meter). Other strategies are alternate E+ controls. "
        "AI optimization proposals live on **Optimize Tomorrow** (not auto-applied here). "
        "Default: **Peak day**  |  **AMY**  |  twin + one strategy (2 jobs). "
        f"Site Config: {setpoints_summary(site_cfg)}."
    )
    mode, reason = resolve_dsm_mode(bundle.site)
    st.info(f"Mode: **{mode}** - {reason}")

    # Reconcile stale campaigns on every render
    camp = reconcile_campaign(bundle.site)

    lib = strategy_library(site_cfg)
    with st.expander("Strategy library (Site Config setpoints)", expanded=False):
        st.caption(
            "Reference only. Live Run DSM actuates these deg F via closed-loop SCH_HtgSP. "
            "Deep setback unocc is Site Config unocc minus 5 F."
        )
        st.dataframe(pd.DataFrame(lib["rows"]), width="stretch", hide_index=True)
        st.plotly_chart(
            strategy_setpoint_figure(lib["series"]),
            width="stretch",
            key="dsm_strategy_sp_library",
        )

    inv = weather_inventory(bundle.site, published=bundle.epw)
    if inv.get("stale_bundle_epw"):
        st.warning(inv.get("stale_bundle_note") or "Published bundle EPW is stale vs amy_meta.")

    month_opts = calendar_month_options(bundle)
    default_m = default_calendar_month(month_opts, bundle.dial_ladder.peak_day)

    c1, c2, c3 = st.columns(3)
    with c1:
        preset = st.select_slider(
            "Period", options=list(PERIOD_PRESETS), value="Peak day", key="dsm_period"
        )
    with c2:
        month = st.selectbox(
            "Month",
            options=month_opts,
            index=month_opts.index(default_m) if default_m in month_opts else 0,
            key="dsm_month",
            disabled=preset != "Calendar month",
        )
    with c3:
        non_base = [s for s in DEPLOYABLE_STRATEGIES if s != "baseline"]
        selected = st.selectbox(
            "Strategy (+ baseline)",
            options=non_base,
            index=non_base.index("deep_setback") if "deep_setback" in non_base else 0,
            key="dsm_strategy_pick",
            format_func=lambda s: STRATEGY_LABELS.get(s, s),
        )

    with st.expander("Advanced weather / batch", expanded=False):
        wx_mode = st.radio(
            "Weather",
            options=["AMY", "TMY", "Both"],
            index=0,
            key="dsm_weather",
            help="Default AMY. Both/TMY and run-all-five live here.",
        )
        run_all_five = st.checkbox("Run all five strategies", value=False, key="dsm_run_all")
        if inv.get("tmy") is None:
            st.caption(inv.get("tmy_missing_note") or "No Madison MSN TMY on this site.")

    ctx = pick_run_context(bundle, preset, month if preset == "Calendar month" else None)
    override = site_cfg.get("peak_day_override")
    if override and preset == "Peak day":
        ctx = dict(ctx)
        ctx["day"] = str(override)[:10]
        ctx["window_days"] = [str(override)[:10]]
        ctx["why"] = f"Site Config peak_day_override={override}"
    spec = period_run_spec(ctx, preset)
    day = spec["peak_day"]
    strategies = (
        list(DEPLOYABLE_STRATEGIES)
        if run_all_five
        else default_strategy_selection(selected)
    )
    pairs = epws_for_mode(wx_mode, inv)
    jobs = live_run_jobs(
        strategies=strategies,
        weathers=pairs,
        begin=spec["begin"],
        end=spec["end"],
        max_steps=int(spec["max_steps"]),
    )
    epw_names = ", ".join(f"{k}={p.name}" for k, p in pairs) if pairs else "(no EPW)"

    champ = bundle.champion()
    idf = (champ.idf_path if champ else None) or bundle.idf_path
    idf_hash = sha256_file(Path(idf)) if idf and Path(idf).is_file() else ""
    amy_hash = None
    if inv.get("amy") and Path(inv["amy"]).is_file():
        amy_hash = sha256_file(Path(inv["amy"]))
    calendar_ok = peak_day_smoke_ok(
        bundle.site, idf_sha256=idf_hash, epw_sha256=amy_hash
    )
    if preset == "Calendar year" and not calendar_ok:
        st.error(
            "Calendar year is gated until a successful peak-day smoke completes "
            "for this IDF + AMY hash. Run Peak day first."
        )

    st.markdown(
        f"**Will run** `{', '.join(strategies)}`  |  `{spec['begin']}` -> `{spec['end']}`  |  "
        f"**{spec['n_days']} days**  |  **{spec['max_steps']} steps**  |  "
        f"**{len(jobs)} job(s)**  |  weather `{wx_mode}` ({epw_names}). "
        f"Meter-peak day: `{day}` - {ctx['why']}."
    )

    @st.fragment(run_every=timedelta(seconds=1))
    def _campaign_status_fragment() -> None:
        doc = reconcile_campaign(bundle.site) or {}
        state = str(doc.get("state") or "idle")
        done = int(doc.get("completed_jobs") or 0)
        total = int(doc.get("total_jobs") or 0)
        elapsed = elapsed_seconds(doc) if doc else 0.0
        err = doc.get("error") or {}
        msg = ""
        if isinstance(err, dict):
            msg = str(err.get("message") or "")
        st.markdown(
            f"**Campaign:** `{state}`  |  "
            f"**{done} / {total}**  |  "
            f"elapsed **{format_hms(elapsed)}**"
            + (f"  |  `{doc.get('run_id')}`" if doc.get("run_id") else "")
        )
        if state in {"failed", "cancelled"} and msg:
            st.error(msg)
            severe = None
            if isinstance(err, dict):
                severe = err.get("severe_or_fatal") or err.get("eplusout_err")
                details = err.get("details") if isinstance(err.get("details"), dict) else {}
                if not severe and details:
                    severe = details.get("severe_or_fatal") or details.get("message")
            if severe:
                st.warning(f"eplusout.err: {severe}")
        elif state == "succeeded":
            st.success(f"Campaign succeeded ({done}/{total}) in {format_hms(elapsed)}")
        elif state in {"preflight", "queued", "starting", "running"}:
            st.info(msg or "Supervisor running...")
            if st.button("Cancel campaign", key="dsm_cancel_btn"):
                request_cancel(bundle.site)
                st.warning("Cancel requested")

    _campaign_status_fragment()

    long_campaign = len(jobs) > 2 or int(spec["n_days"]) > 7 or preset in {
        "Winter (Dec-Feb)",
        "Calendar year",
    }
    run_label = "Run DSM" if not run_all_five else "Run all 5 strategies"
    if st.button(run_label, key="dsm_run_btn", type="primary"):
        if preset == "Calendar year" and not calendar_ok:
            st.error("Calendar year blocked until peak-day smoke succeeds.")
            return
        if long_campaign:
            st.warning(
                f"Long campaign: {len(jobs)} jobs  |  {preset}  |  {spec['period']}  |  "
                f"~{spec['max_steps']} steps/job  |  IDF `{Path(idf).name if idf else '?'}`  |  "
                f"EPW {epw_names}"
            )
        actual_peak = ctx.get("actual_peak_kw")
        if actual_peak is None:
            actual_peak = _actual_peak(bundle, day)
        actual = actual_day_profile(bundle, day)
        if mode == "error":
            st.error(reason)
            return
        if active_campaign_running(bundle.site):
            st.error("A DSM campaign is already running for this site.")
            return
        if mode == "lookup":
            frames_by: dict[str, pd.DataFrame] = {}
            kpis_by: dict[str, Any] = {}
            for sid in strategies:
                try:
                    pack = run_dsm_lookup(
                        site_root=bundle.site,
                        strategy_id=sid,
                        day=day,
                        actual_peak_kw=actual_peak,
                    )
                except FileNotFoundError:
                    continue
                frames_by[f"{sid}:lookup"] = pack["frame"]
                kpis_by[sid] = pack["kpis"]
            if not frames_by:
                st.error("No W2A farm days for the selected strategies.")
                return
            attach_baseline_deltas(kpis_by)
            primary = pick_frame(frames_by, "baseline:lookup")
            if primary is None:
                primary = next(iter(frames_by.values()))
            _store_run(
                site=bundle.site,
                df=primary,
                actual=actual,
                kpis=kpis_by.get("baseline") or next(iter(kpis_by.values())),
                strategy="all",
                day=day,
                preset=preset,
                mode="lookup",
                epw_name=epw_names,
                why=str(ctx["why"]),
                window_days=list(spec["window_days"]),
                weather_mode=wx_mode,
                period=spec["period"],
                max_steps=96,
                n_days=1,
                weather_kind=None,
                tmy_note=inv.get("tmy_missing_note"),
                frames=frames_by,
                strategies=list(kpis_by.keys()),
                kpis_by_strategy=kpis_by,
            )
            st.rerun()
            return

        if idf is None or not Path(idf).is_file():
            st.error("No champion IDF on the published pack.")
            return
        if not pairs:
            st.error(
                "No AMY or site TMY EPW. Agent must publish {site_slug}_amy_*.epw. "
                "Chicago screening is not used."
            )
            return

        stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
        run_id = f"{stamp}_dsm"
        req_dir = Path(bundle.site) / "reports" / "eplus_gym" / "runs" / run_id
        req_dir.mkdir(parents=True, exist_ok=True)
        request = {
            "run_id": run_id,
            "idf": str(idf),
            "expected_idf_sha256": idf_hash or None,
            "begin": spec["begin"],
            "end": spec["end"],
            "n_days": int(spec["n_days"]),
            "max_steps": int(spec["max_steps"]),
            "strategies": strategies,
            "weather_mode": wx_mode,
            "preset": preset,
            "peak_day": day,
            "jobs": [
                {
                    "strategy_id": j["strategy_id"],
                    "weather_kind": j["weather_kind"],
                    "epw": str(j["epw"]),
                    "begin": j["begin"],
                    "end": j["end"],
                    "max_steps": int(j["max_steps"]),
                    "key": j["key"],
                }
                for j in jobs
            ],
            "require_energyplus": True,
        }
        req_path = req_dir / "campaign_request.json"
        req_path.write_text(json.dumps(request, indent=2), encoding="utf-8")
        try:
            start_dsm_campaign_subprocess(site=Path(bundle.site), request_path=req_path)
        except OSError as exc:
            st.error(f"Failed to start campaign supervisor: {exc}")
            return
        st.success(f"Started campaign `{run_id}` ({len(jobs)} jobs). Status updates above.")
        st.rerun()

    last = st.session_state.get("dsm_last")
    if not isinstance(last, dict) or last.get("frame") is None:
        loaded = load_last_run(bundle)
        if loaded:
            st.session_state["dsm_last"] = loaded
            last = loaded
    if not isinstance(last, dict):
        return
    stale = (
        last.get("day") != day
        or last.get("preset") != preset
        or last.get("weather_mode") != wx_mode
        or str(last.get("period") or "") != spec["period"]
    )
    if stale:
        st.warning(
            f"Chart below is the **last Run** (`{last.get('preset')}`  |  `{last.get('period')}`  |  "
            f"`{last.get('weather_mode')}`). "
            f"Click **{run_label}** for `{preset}` -> `{spec['period']}`."
        )
    kpis_by = dict(last.get("kpis_by_strategy") or {})
    if not kpis_by and last.get("kpis"):
        kpis_by = {str(last.get("strategy") or "run"): last["kpis"]}
    actual = last.get("actual")
    if not isinstance(actual, pd.DataFrame):
        actual = None
    if actual is None or getattr(actual, "empty", True):
        actual = actual_day_profile(bundle, str(last.get("day") or day))
        last["actual"] = actual
    frames = frame_map(last.get("frames"))
    if not frames:
        primary = coalesce_frame(last.get("frame"))
        if primary is not None:
            sid0 = str(last.get("strategy") or "baseline")
            kind0 = str(last.get("weather_kind") or KIND_AMY)
            frames = {f"{sid0}:{kind0}": primary}
    primary_frame = coalesce_frame(last.get("frame"), pick_frame(frames, *list(frames.keys())))
    if primary_frame is None:
        st.info("Last run pointer found but no trajectory frame on disk.")
        return
    eplus = _eplus_with_oat_f(primary_frame)
    actual_peak_show = None
    if actual is not None and not actual.empty and "kw_avg" in actual.columns:
        actual_peak_show = float(actual["kw_avg"].max())
    elif actual_peak_show is None:
        actual_peak_show = _actual_peak(bundle, str(last.get("day") or day))
    # Always backfill vs_actual_pct for the Overview scorecard when BAS peak exists.
    attach_actual_deltas(kpis_by, actual_peak_show)
    elapsed_map = last.get("elapsed_by_weather") or {}
    if elapsed_map:
        elapsed_bit = (
            f"  |  {format_hms(sum(elapsed_map.values()))} total ({len(elapsed_map)} runs)"
        )
    else:
        elapsed = last.get("elapsed_s")
        elapsed_bit = (
            f"  |  EnergyPlus wall {format_hms(elapsed)}"
            if isinstance(elapsed, (int, float))
            else ""
        )
    ran = list(last.get("strategies") or kpis_by.keys()) or ["all"]
    st.header("Results")
    wx = str(last.get("weather_mode") or "")
    amy_note = (
        " AMY EPW = actual-year weather for this calendar day — compare to BAS meter below."
        if "AMY" in wx.upper() or wx.upper() == "AMY"
        else ""
    )
    st.info(
        f"**Last run** `{last.get('preset')}`  |  period `{last.get('period') or last.get('day')}`  |  "
        f"{len(ran)} strategies ({', '.join(ran)})  |  "
        f"{last.get('n_days') or last.get('window_n') or '?'} days  |  "
        f"{last.get('max_steps') or '?'} steps{elapsed_bit}.{amy_note} "
        "Charts below."
    )
    if actual_peak_show is not None:
        st.caption(
            f"**Actual BAS meter peak** this day: **{actual_peak_show:.1f} kW** "
            "(ground truth). Strategy tabs below are EnergyPlus sims — "
            "‘E+ Site Config (twin)’ is not the meter."
        )
    _render_dsm_results_charts(
        last=last,
        kpis_by=kpis_by,
        actual=actual,
        frames=frames,
        eplus=eplus,
        day=str(last.get("day") or day),
        COLORS=COLORS,
        dsm_panel_figure=dsm_panel_figure,
        dsm_trajectory_figure=dsm_trajectory_figure,
        dsm_compare_overlay_figure=dsm_compare_overlay_figure,
        period_daily_peak_figure=period_daily_peak_figure,
        actual_peak_kw=actual_peak_show,
    )


def _render_dsm_results_charts(**kwargs):
    import streamlit as st

    last = kwargs["last"]
    kpis_by = kwargs["kpis_by"]
    actual = kwargs["actual"]
    frames = kwargs["frames"]
    eplus = kwargs["eplus"]
    day = kwargs["day"]
    COLORS = kwargs["COLORS"]
    dsm_trajectory_figure = kwargs["dsm_trajectory_figure"]
    dsm_compare_overlay_figure = kwargs["dsm_compare_overlay_figure"]
    period_daily_peak_figure = kwargs["period_daily_peak_figure"]
    actual_peak_kw = kwargs.get("actual_peak_kw")

    peak_slices = {}
    for key, df in frames.items():
        peak_slices[key] = slice_traj_for_day(df, day)

    ran = list(last.get("strategies") or kpis_by.keys())
    if not ran:
        ran = sorted({split_frame_key(k)[0] for k in frames})
    tab_labels = ["Overview", *[STRATEGY_LABELS.get(s, s) for s in ran]]
    tabs = st.tabs(tab_labels, key=f"dsm_results_tabs_{last.get('run_id') or last.get('day')}")

    def _slice_for(sid: str):
        for prefer in (f"{sid}:{KIND_AMY}", f"{sid}:lookup", sid):
            cand = peak_slices.get(prefer)
            if cand is None:
                for key, v in peak_slices.items():
                    if split_frame_key(key)[0] == sid and v is not None and not v.empty:
                        cand = v
                        break
            if cand is not None and not getattr(cand, "empty", True):
                return cand
        return None

    has_actual = (
        actual is not None
        and not getattr(actual, "empty", True)
        and "kw_avg" in getattr(actual, "columns", [])
    )

    with tabs[0]:
        st.markdown(
            """
**How to read this page**

| Row | What it is |
| --- | --- |
| **Actual BAS (meter)** | Real facility kW from the interval meter for this calendar day — the ground truth. |
| **E+ Site Config (twin)** | EnergyPlus twin with Site Config heat — *not* the meter. Gap vs Actual = twin fidelity. |
| **Other E+ strategies** | Alternate control rules on the same twin/weather (24/7, deep setback, …). |
| **E+ Optimized** | Only if **Optimize Tomorrow** produced a proposal — never auto-applied to BACnet. |

Peak % vs Actual uses the BAS meter peak. kW trim / kWh Δ use the **E+ twin baseline**, not the meter.
            """.strip()
        )
        if not has_actual:
            st.warning(
                "No BAS meter profile for this day — cannot overlay Actual. "
                "Check demand/interval CSV coverage."
            )

        # Optimization proposal status (separate from Run DSM strategies)
        site_path = None
        if last.get("site"):
            site_path = Path(last["site"])
        elif last.get("out_dir"):
            # .../reports/eplus_gym/runs/<run_id>/... → site root is parents[3]
            try:
                site_path = Path(last["out_dir"]).resolve().parents[3]
            except Exception:  # noqa: BLE001
                site_path = None
        if site_path is not None:
            try:
                from eplus_gym_app.optimize_tomorrow import list_studies

                studies = list_studies(site_path)
            except Exception:  # noqa: BLE001
                studies = []
            if studies:
                rec_path = studies[0] / "recommendation.json"
                appr = studies[0] / "approved_recommendation.json"
                if appr.is_file():
                    st.success(
                        f"Approved optimization proposal: `{studies[0].name}` — still not "
                        "written to Site Config / BACnet. Review on **Optimize Tomorrow**."
                    )
                elif rec_path.is_file():
                    st.info(
                        f"Optimization proposal available: `{studies[0].name}`. "
                        "Open **Optimize Tomorrow** to review / approve. "
                        "Run DSM does not auto-apply the optimized schedule."
                    )
                else:
                    st.caption(
                        "Optimization study folder exists but has no recommendation.json yet."
                    )
            else:
                st.caption(
                    "No Optimize Tomorrow study on this site yet — agent screening lives "
                    "on that tab, not inside these Run DSM strategy tabs."
                )
        if kpis_by:
            actual_kwh = None
            if has_actual and "kw_avg" in actual.columns:
                # 15-min intervals → kWh
                actual_kwh = float(actual["kw_avg"].sum() * 0.25)
            rows = []
            if actual_peak_kw is not None:
                rows.append(
                    {
                        "source": "Actual BAS (meter)",
                        "kind": "meter",
                        "peak_kW": round(float(actual_peak_kw), 1),
                        "kWh": round(actual_kwh, 0) if actual_kwh is not None else None,
                        "Δpeak_vs_Actual_%": 0.0,
                        "Δpeak_vs_E+_twin_kW": None,
                        "ΔkWh_vs_E+_twin": None,
                        "note": "Ground truth for this calendar day",
                    }
                )
            for sid, row in kpis_by.items():
                peak = row.get("peak_kw")
                kwh = row.get("kwh")
                vs_act = row.get("vs_actual_pct")
                rows.append(
                    {
                        "source": STRATEGY_LABELS.get(sid, sid),
                        "kind": "EnergyPlus sim",
                        "peak_kW": round(float(peak), 1) if peak is not None else None,
                        "kWh": round(float(kwh), 0) if kwh is not None else None,
                        "Δpeak_vs_Actual_%": (
                            round(float(vs_act), 2) if vs_act is not None else None
                        ),
                        "Δpeak_vs_E+_twin_kW": (
                            round(float(row["kw_trim"]), 1)
                            if row.get("kw_trim") is not None
                            else None
                        ),
                        "ΔkWh_vs_E+_twin": (
                            round(float(row["kwh_penalty"]), 0)
                            if row.get("kwh_penalty") is not None
                            else None
                        ),
                        "note": (
                            "Twin fidelity vs meter"
                            if sid == "baseline"
                            else "Compare to Actual + E+ twin"
                        ),
                    }
                )
            st.subheader("Scorecard")
            st.dataframe(pd.DataFrame(rows), width="stretch", hide_index=True)
            st.caption(
                "Δpeak_vs_Actual_% = (E+ peak − Actual peak) / Actual × 100. "
                "Negative means the sim peak is below the meter. "
                "Δpeak_vs_E+_twin_kW = twin peak − this strategy (+ = trimmed vs twin). "
                "Costs: use **Optimize Tomorrow** (PHYSICAL_ONLY / verified tariff) — "
                "Run DSM does not invent bill dollars."
            )

        overlay_series = []
        for sid in ran:
            sl = _slice_for(sid)
            if sl is not None:
                overlay_series.append(
                    (f"E+ {STRATEGY_LABELS.get(sid, sid)}", COLORS.get(sid, "#2a9d8f"), sl)
                )
        st.plotly_chart(
            dsm_compare_overlay_figure(
                actual=actual if has_actual else None,
                series=overlay_series,
                title=(
                    f"Actual BAS vs EnergyPlus  |  {day}  |  "
                    f"{last.get('weather_mode') or 'AMY'}"
                ),
                actual_peak_kw=actual_peak_kw,
                height=480,
            ),
            width="stretch",
            key=f"dsm_overlay_all_{last.get('day')}_{last.get('period')}",
        )

        daily = daily_peaks_from_traj(eplus)
        if daily is not None and not daily.empty and int(last.get("n_days") or 1) > 1:
            st.plotly_chart(
                period_daily_peak_figure(
                    daily,
                    highlight_day=str(day)[:10],
                    title="Daily peak kW over run window",
                ),
                width="stretch",
                key=f"dsm_daily_{last.get('period')}",
            )

    for i, sid in enumerate(ran):
        with tabs[i + 1]:
            st.markdown(STRATEGY_TUTORIALS.get(sid, f"**{sid}** demand-response rule."))
            kpi = kpis_by.get(sid) or {}
            if kpi:
                m1, m2, m3, m4 = st.columns(4)
                m1.metric(
                    "Peak kW",
                    f"{kpi['peak_kw']:.1f}" if kpi.get("peak_kw") is not None else "-",
                )
                m2.metric(
                    "kWh",
                    f"{kpi['kwh']:.0f}" if kpi.get("kwh") is not None else "-",
                )
                m3.metric(
                    "Δ peak vs Actual BAS %",
                    (
                        f"{kpi['vs_actual_pct']:+.1f}%"
                        if kpi.get("vs_actual_pct") is not None
                        else "-"
                    ),
                    help="(E+ peak − Actual meter peak) / Actual × 100",
                )
                m4.metric(
                    "kW trim vs E+ twin",
                    f"{kpi['kw_trim']:+.1f}" if kpi.get("kw_trim") is not None else "-",
                    help="E+ Site Config twin peak − this strategy (+ = lower peak than twin)",
                )

            sl = _slice_for(sid)
            if sl is None:
                st.info(f"No trajectory frame for `{sid}` in this run.")
                continue

            color = COLORS.get(sid, "#2a9d8f")
            st.plotly_chart(
                dsm_compare_overlay_figure(
                    actual=actual if has_actual else None,
                    series=[(f"E+ {STRATEGY_LABELS.get(sid, sid)}", color, sl)],
                    title=f"Actual vs E+ {STRATEGY_LABELS.get(sid, sid)}  |  {day}",
                    actual_peak_kw=actual_peak_kw,
                    height=460,
                ),
                width="stretch",
                key=f"dsm_overlay_{sid}_{last.get('day')}",
            )
            st.plotly_chart(
                dsm_trajectory_figure(
                    sl,
                    actual=actual if has_actual else None,
                    title=f"{STRATEGY_LABELS.get(sid, sid)} 15-min + heating SP  |  {day}",
                    height=480,
                ),
                width="stretch",
                key=f"dsm_traj_{sid}_{last.get('day')}_{last.get('preset')}",
            )


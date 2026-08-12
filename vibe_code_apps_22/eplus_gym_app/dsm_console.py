"""BOPTEST-shaped DSM Run panel (W2A champion only)."""
from __future__ import annotations

import json
import subprocess
import sys
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
    "baseline": "Baseline",
    "flat_24_7": "Flat 24/7",
    "deep_setback": "Deep setback",
    "stagger_preheat": "Stagger preheat",
    "morning_all_on": "Morning all-on",
}


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


def strategy_library() -> dict[str, Any]:
    """Desktop strategy cards + 96-step SP series. Not list_strategies() (skips index.json)."""
    from eplus_gym.controllers import RuleController, load_strategy_contract

    rows: list[dict[str, Any]] = []
    series: dict[str, list[float]] = {}
    for sid in DEPLOYABLE_STRATEGIES:
        meta = load_strategy_contract(sid).get("meta") or {}
        ctrl = RuleController(sid)
        series[sid] = ctrl.series_f()
        rows.append(
            {
                "strategy_id": sid,
                "label": STRATEGY_LABELS.get(sid, sid),
                "occ_htg_sp_f": float(meta.get("occ_htg_sp_f", 68.0)),
                "unocc_htg_sp_f": float(meta.get("unocc_htg_sp_f", 65.0)),
                "preheat_lead_h": float(meta.get("preheat_lead_h") or 0.0),
                "stagger_min": float(meta.get("stagger_min") or 0.0),
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
    """One CLI job per strategy × weather. Keys are strategy:weather_kind."""
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

    kw_trim = baseline peak kW − strategy peak kW  (+ = trimmed demand)
    kwh_penalty = strategy kWh − baseline kWh      (+ = energy penalty)
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


def stage_idf_for_period(src: Path, dest: Path, begin: str, end: str) -> Path:
    """Copy IDF with RunPeriod clipped to ``begin``..``end``. Never overwrite champion."""
    from datetime import date

    from eplus_native.idf_stage import patch_run_period

    src = Path(src)
    dest = Path(dest)
    if dest.resolve() == src.resolve():
        raise ValueError("refusing to overwrite source IDF; pass a staged dest path")
    b = date.fromisoformat(str(begin)[:10])
    e = date.fromisoformat(str(end)[:10])
    dest.parent.mkdir(parents=True, exist_ok=True)
    dest.write_text(
        patch_run_period(
            src.read_text(encoding="utf-8"),
            begin_month=b.month,
            begin_day=b.day,
            end_month=e.month,
            end_day=e.day,
            begin_year=b.year,
            end_year=e.year,
            name=f"DSM_{b.isoformat()}_{e.isoformat()}",
        ),
        encoding="utf-8",
    )
    return dest


def stage_idf_for_day(src: Path, dest: Path, day: str) -> Path:
    """Copy IDF with RunPeriod clipped to ``day``. Never overwrite the champion."""
    return stage_idf_for_period(src, dest, day, day)


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
) -> subprocess.Popen:
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
    return subprocess.Popen(
        cmd,
        cwd=str(_APP),
        stdout=handle,
        stderr=subprocess.STDOUT,
        text=True,
    )


def _resolve_epw(bundle: SiteUiBundle) -> Path | None:
    inv = weather_inventory(bundle.site, published=bundle.epw)
    return inv.get("amy") or inv.get("tmy")


def _eplus_with_oat_f(df: pd.DataFrame) -> pd.DataFrame:
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
        "title": f"E+ champion {strategy} vs Actual meter · {day} · {preset}",
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
    df = frames.get(KIND_AMY) or (next(iter(frames.values())) if frames else None)
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
    if frames:
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


def render_run_dsm_tab(bundle: SiteUiBundle) -> None:
    import time

    import streamlit as st

    from eplus_gym_app.plots import (
        COLORS,
        dsm_panel_figure,
        dsm_trajectory_figure,
        period_daily_peak_figure,
        strategy_setpoint_figure,
    )

    st.subheader("Run DSM")
    st.caption(
        f"Champion `{bundle.dsm_champion}` · W2A_PHYSICAL_DSM · promote=False. "
        "Run **all five** rule contracts on the selected window. "
        "**AMY** = Open-Meteo actual year (M&V). **TMY** = typical Madison MSN. "
        "Live E+ is closed-loop (`SCH_HtgSP` every 15 min) for the **whole selected window**."
    )
    mode, reason = resolve_dsm_mode(bundle.site)
    st.info(f"Mode: **{mode}** — {reason}")

    lib = strategy_library()
    st.markdown("**Strategy library** (all five run on every click)")
    st.caption(
        "Contracts: "
        + ", ".join(f"`{s}`" for s in DEPLOYABLE_STRATEGIES)
        + ". PRBS is not offered on this console."
    )
    st.dataframe(pd.DataFrame(lib["rows"]), width="stretch", hide_index=True)
    st.plotly_chart(
        strategy_setpoint_figure(lib["series"]),
        width="stretch",
        key="dsm_strategy_sp_library",
    )
    st.caption("Weekend heating SP repeats this 96-step profile (`weekend_sp=repeat_96_step_profile`).")

    inv = weather_inventory(bundle.site, published=bundle.epw)
    wx_opts = ["AMY", "TMY", "Both"]
    default_wx = inv.get("default_mode") or "AMY"

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
        wx_mode = st.radio(
            "Weather",
            options=wx_opts,
            index=wx_opts.index(default_wx) if default_wx in wx_opts else 0,
            key="dsm_weather",
            help="AMY = Open-Meteo actual year. TMY = Madison typical. Both = two sequential live runs per strategy.",
        )

    if inv.get("tmy") is None:
        st.warning(inv.get("tmy_missing_note") or "No Madison MSN TMY on this site.")
    if wx_mode == "TMY" and inv.get("tmy") is None:
        st.caption("TMY missing — Run will use AMY only (Chicago screening EPW is not auto-selected).")

    ctx = pick_run_context(bundle, preset, month if preset == "Calendar month" else None)
    spec = period_run_spec(ctx, preset)
    day = spec["peak_day"]
    pairs = epws_for_mode(wx_mode, inv)
    jobs = live_run_jobs(
        strategies=list(DEPLOYABLE_STRATEGIES),
        weathers=pairs,
        begin=spec["begin"],
        end=spec["end"],
        max_steps=int(spec["max_steps"]),
    )
    epw_names = ", ".join(f"{k}={p.name}" for k, p in pairs) if pairs else "(no EPW)"
    n_strat = len(DEPLOYABLE_STRATEGIES)
    n_wx = max(len(pairs), 1)
    live_note = (
        f"**Will simulate closed-loop all {n_strat} strategies** `{spec['begin']}` → `{spec['end']}` · "
        f"**{spec['n_days']} days** · **{spec['max_steps']} steps** (15 min) · "
        f"**{len(jobs)} live runs** ({n_strat} × {n_wx} weather). "
        f"Winter × 5 × AMY is typically 5–25 min; Both doubles that. "
        f"Meter-peak day inside the window: `{day}` — {ctx['why']}."
    )
    if mode == "lookup":
        live_note = (
            f"**Lookup is peak-day only** (`{day}`, 96 steps) for all five strategies. "
            "Grow a W2A farm or use live E+ for the full week/month/winter window."
        )
    st.markdown(live_note)
    st.caption(
        f"Weather files: {epw_names}. "
        "AMY is **not** a typical-year EPW. TMY is typical. "
        "OAT mismatch vs BAS is station/source, not 'TMY vs actual' when only AMY is present. "
        f"Honesty: loop=CLOSED_LOOP_RULE_DR · period={spec['period']} · "
        "weekend_sp=repeat_96_step_profile · promote=False."
    )
    if ctx.get("actual_peak_kw") is not None:
        st.caption(
            f"BAS meter peak in this window: **{ctx['actual_peak_kw']:.0f} kW** on `{day}`."
        )

    if st.button("Run all 5 strategies", key="dsm_run_btn", type="primary"):
        actual_peak = ctx.get("actual_peak_kw")
        if actual_peak is None:
            actual_peak = _actual_peak(bundle, day)
        actual = actual_day_profile(bundle, day)
        if mode == "error":
            st.error(reason)
            return
        if mode == "lookup":
            frames_by: dict[str, pd.DataFrame] = {}
            kpis_by: dict[str, Any] = {}
            base_peak = None
            for sid in DEPLOYABLE_STRATEGIES:
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
                if sid == "baseline":
                    base_peak = pack["kpis"].get("peak_kw")
            if not frames_by:
                st.error("No W2A farm days for any of the five strategies.")
                return
            attach_baseline_deltas(kpis_by)
            primary = frames_by.get("baseline:lookup") or next(iter(frames_by.values()))
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
        else:
            champ = bundle.champion()
            idf = (champ.idf_path if champ else None) or bundle.idf_path
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
            frames_by: dict[str, pd.DataFrame] = {}
            parquets: dict[str, str] = {}
            elapsed_by: dict[str, float] = {}
            kpis_by: dict[str, Any] = {}
            last_out = None
            last_meta: dict[str, Any] = {}
            with st.status("Live EnergyPlus (subprocess)…", expanded=True) as status:
                for i, job in enumerate(jobs, start=1):
                    sid = job["strategy_id"]
                    kind = job["weather_kind"]
                    key = job["key"]
                    out_dir = (
                        bundle.site
                        / "reports"
                        / "eplus_gym"
                        / "runs"
                        / f"{stamp}_{sid}_{kind}"
                    )
                    last_out = out_dir
                    t0 = time.perf_counter()
                    status.update(
                        label=(
                            f"{sid} · {kind} · {i}/{len(jobs)} · "
                            f"{spec['begin']}→{spec['end']} · {spec['max_steps']} steps…"
                        ),
                        state="running",
                    )
                    proc = start_live_subprocess(
                        site=bundle.site,
                        strategy_id=sid,
                        epw=Path(job["epw"]),
                        idf=Path(idf),
                        out_dir=out_dir,
                        day=spec["begin"],
                        begin=spec["begin"],
                        end=spec["end"],
                        max_steps=int(spec["max_steps"]),
                    )
                    code = proc.wait()
                    elapsed_s = time.perf_counter() - t0
                    elapsed_by[key] = elapsed_s
                    log = out_dir / "live.log"
                    if log.is_file():
                        tail = "\n".join(
                            log.read_text(encoding="utf-8", errors="ignore").splitlines()[-12:]
                        )
                        st.code(f"[{sid} {kind} {elapsed_s:.1f}s]\n{tail or '(empty log)'}")
                    if code != 0:
                        status.update(label=f"Live run failed ({sid} {kind})", state="error")
                        st.error(f"CLI exited {code} for {sid} / {kind}")
                        return
                    pq = _collect_traj(out_dir)
                    if pq is None:
                        st.warning(f"Live finished but no trajectory parquet under {out_dir}")
                        return
                    df_job = pd.read_parquet(pq)
                    frames_by[key] = df_job
                    parquets[key] = str(pq)
                    card = out_dir / "rule_dr_scorecard.json"
                    if card.is_file():
                        try:
                            doc = json.loads(card.read_text(encoding="utf-8"))
                            rows = doc.get("strategies") or []
                            if rows:
                                last_meta = dict(rows[0])
                        except (OSError, json.JSONDecodeError):
                            pass
                    st.write(
                        f"{sid} · {kind}: {spec['n_days']} days · {spec['max_steps']} steps · "
                        f"{elapsed_s:.1f}s · `{pq}`"
                    )
                bits = " · ".join(f"{k} {v:.1f}s" for k, v in elapsed_by.items())
                status.update(label=f"Live EnergyPlus finished ({bits})", state="complete")
            base_peak = None
            for sid in DEPLOYABLE_STRATEGIES:
                key_amy = f"{sid}:{KIND_AMY}"
                key_tmy = f"{sid}:{KIND_TMY_MSN}"
                df_sid = frames_by.get(key_amy) or frames_by.get(key_tmy)
                if df_sid is None:
                    continue
                meta = {
                    "honesty": last_meta.get("honesty") or "W2A_PHYSICAL_DSM",
                    "provenance": last_meta.get("provenance") or "ENERGYPLUS_PYTHON_API",
                    "mode": "live",
                    "family": "w2a",
                    "promote": False,
                    "day": day,
                    "strategy_id": sid,
                    "loop": "CLOSED_LOOP_RULE_DR",
                    "period": spec["period"],
                    "weekend_sp": "repeat_96_step_profile",
                }
                kpis_by[sid] = dsm_kpis(df_sid, meta, actual_peak_kw=actual_peak)
                if sid == "baseline":
                    base_peak = kpis_by[sid].get("peak_kw")
            attach_baseline_deltas(kpis_by)
            primary_key = f"baseline:{KIND_AMY}"
            if primary_key not in frames_by:
                primary_key = next(iter(frames_by))
            _store_run(
                site=bundle.site,
                df=frames_by[primary_key],
                actual=actual,
                kpis=kpis_by.get("baseline") or next(iter(kpis_by.values())),
                strategy="all",
                day=day,
                preset=preset,
                mode="live",
                epw_name=epw_names,
                why=str(ctx["why"]),
                window_days=list(spec["window_days"]),
                parquet=parquets.get(primary_key),
                elapsed_s=sum(elapsed_by.values()),
                out_dir=str(last_out) if last_out else None,
                weather_mode=wx_mode,
                period=spec["period"],
                max_steps=int(spec["max_steps"]),
                n_days=int(spec["n_days"]),
                parquets=parquets,
                elapsed_by_weather=elapsed_by,
                tmy_note=inv.get("tmy_missing_note"),
                weather_kind=split_frame_key(primary_key)[1] or KIND_AMY,
                frames=frames_by,
                strategies=list(kpis_by.keys()),
                kpis_by_strategy=kpis_by,
            )
            st.rerun()

    last = st.session_state.get("dsm_last")
    if not last or last.get("frame") is None:
        loaded = load_last_run(bundle)
        if loaded:
            st.session_state["dsm_last"] = loaded
            last = loaded
    if not last:
        return
    stale = (
        last.get("day") != day
        or last.get("preset") != preset
        or last.get("weather_mode") != wx_mode
        or str(last.get("period") or "") != spec["period"]
    )
    if stale:
        st.warning(
            f"Chart below is the **last Run** (`{last.get('preset')}` · `{last.get('period')}` · "
            f"`{last.get('weather_mode')}`). "
            f"Click **Run all 5 strategies** for `{preset}` -> `{spec['period']}`."
        )
    kpis_by = dict(last.get("kpis_by_strategy") or {})
    if not kpis_by and last.get("kpis"):
        kpis_by = {str(last.get("strategy") or "run"): last["kpis"]}
    actual = last.get("actual")
    frames = dict(last.get("frames") or {})
    if not frames and last.get("frame") is not None:
        sid0 = str(last.get("strategy") or "baseline")
        frames = {f"{sid0}:{last.get('weather_kind') or KIND_AMY}": last["frame"]}
    eplus = _eplus_with_oat_f(last["frame"])
    actual_peak_show = None
    if actual is not None and not getattr(actual, "empty", True) and "kw_avg" in actual.columns:
        actual_peak_show = float(actual["kw_avg"].max())
    elapsed_map = last.get("elapsed_by_weather") or {}
    if elapsed_map:
        elapsed_bit = f" · {sum(elapsed_map.values()):.1f}s total ({len(elapsed_map)} runs)"
    else:
        elapsed = last.get("elapsed_s")
        elapsed_bit = f" · EnergyPlus wall {elapsed:.1f}s" if isinstance(elapsed, (int, float)) else ""
    ran = list(last.get("strategies") or kpis_by.keys()) or ["all"]
    st.header("Results")
    st.info(
        f"**Last run** `{last.get('preset')}` · period `{last.get('period') or last.get('day')}` · "
        f"{len(ran)} strategies ({', '.join(ran)}) · "
        f"{last.get('n_days') or last.get('window_n') or '?'} days · "
        f"{last.get('max_steps') or '?'} steps{elapsed_bit}. "
        f"Black = **Actual BAS meter**"
        f"{f' (peak {actual_peak_show:.0f} kW)' if actual_peak_show is not None else ''}. "
        f"Colored lines = E+ champion strategies (AMY / TMY labeled). "
        f"loop=`CLOSED_LOOP_RULE_DR` · weekend_sp=`repeat_96_step_profile` · promote=False. "
        f"Files: `{last.get('epw_name')}`."
    )
    score_rows = []
    for sid in ran:
        row = kpis_by.get(sid) or {}
        score_rows.append(
            {
                "strategy_id": sid,
                "peak_kw": row.get("peak_kw"),
                "kw_trim": row.get("kw_trim"),
                "kwh": row.get("kwh"),
                "kwh_penalty": row.get("kwh_penalty"),
                "vs_actual_pct": row.get("vs_actual_pct"),
                "vs_baseline_pct": row.get("vs_baseline_pct"),
            }
        )
    if score_rows:
        st.dataframe(pd.DataFrame(score_rows), width="stretch", hide_index=True)
        st.caption(
            "Window totals for the selected period (peak day / month / winter / year). "
            "**kW trim** = baseline peak − strategy peak (+ trimmed demand). "
            "**kWh penalty** = strategy kWh − baseline kWh (+ used more energy)."
        )
    paths = list((last.get("parquets") or {}).values()) or (
        [last["parquet"]] if last.get("parquet") else []
    )
    if paths:
        st.caption("On disk: " + " · ".join(f"`{p}`" for p in paths[:8]))

    window_days = list(last.get("window_days") or [])
    show_daily = (last.get("n_days") or len(window_days) or 0) > 1 or len(window_days) > 1
    if show_daily:
        try:
            from eplus_gym_app.load_profiles import load_bas_demand_oat

            bas_win = load_bas_demand_oat(bundle, csv_path=bundle.bas_demand_oat_csv)
            span = set(window_days)
            if last.get("period"):
                b, _, e = str(last["period"]).partition("/")
                if b and e:
                    span = {
                        d
                        for d in bas_win["local_day"].astype(str)
                        if b <= d <= e
                    } or span
            daily = (
                bas_win.loc[bas_win["local_day"].astype(str).isin(span)]
                .groupby("local_day", as_index=False)["kw_avg"]
                .max()
                .rename(columns={"kw_avg": "peak_kw"})
                .sort_values("local_day")
            )
        except Exception:  # noqa: BLE001
            daily = pd.DataFrame()
        eplus_daily = {}
        for key, frame in frames.items():
            sid, kind = split_frame_key(key)
            wx = _WX_LABEL.get(kind, kind) if kind and kind != "lookup" else ""
            eplus_daily[f"{sid} {wx}".strip()] = daily_peaks_from_traj(frame)
        if not daily.empty or any(not v.empty for v in eplus_daily.values()):
            st.plotly_chart(
                period_daily_peak_figure(
                    daily,
                    highlight_day=str(last.get("day") or ""),
                    title=(
                        f"Daily peaks · {last.get('preset')} · {last.get('period')} "
                        f"· Actual + all strategies"
                    ),
                    eplus_daily=eplus_daily,
                ),
                width="stretch",
                key=f"dsm_period_daily_{last.get('preset')}_{last.get('period')}",
            )

    peak_slices = {
        key: slice_traj_for_day(_eplus_with_oat_f(frame), str(last.get("day") or day))
        for key, frame in frames.items()
    }
    extra = []
    for key, sl in peak_slices.items():
        if sl is None or sl.empty:
            continue
        sid, kind = split_frame_key(key)
        wx = _WX_LABEL.get(kind, kind) if kind and kind != "lookup" else ""
        extra.append((f"{sid} {wx}".strip(), COLORS.get(sid, "#2a9d8f"), sl))
    primary_slice = None
    for prefer in (f"baseline:{KIND_AMY}", "baseline:lookup"):
        if prefer in peak_slices and not peak_slices[prefer].empty:
            primary_slice = peak_slices[prefer]
            break
    if primary_slice is None:
        primary_slice = next(
            (v for v in peak_slices.values() if v is not None and not v.empty), eplus
        )
    left, right = st.columns(2)
    with left:
        st.plotly_chart(
            dsm_panel_figure(
                actual if actual is not None else pd.DataFrame(),
                title=f"Actual BAS meter · {last.get('day')}",
                ycol="kw_avg",
                name="Actual (BAS meter)",
                color="#1f2a30",
                oat_col="oat_f",
                oat_name="Actual OAT °F",
            ),
            width="stretch",
            key=f"dsm_actual_{last.get('day')}_{last.get('preset')}",
        )
    with right:
        st.plotly_chart(
            dsm_panel_figure(
                primary_slice if primary_slice is not None else eplus,
                title=f"EnergyPlus champion baseline · {last.get('day')}",
                ycol="facility_kw",
                name="E+ champion baseline kW",
                color=COLORS.get("baseline", "#2a9d8f"),
                oat_col="oat_f",
                oat_name="E+ EPW OAT °F",
            ),
            width="stretch",
            key=f"dsm_eplus_{last.get('day')}_all_{last.get('mode')}",
        )
    st.plotly_chart(
        dsm_trajectory_figure(
            primary_slice if primary_slice is not None else eplus,
            actual=actual,
            title=f"Peak-day 15-min overlay · {last.get('day')} · Actual vs all 5 strategies",
            extra_eplus=extra or None,
        ),
        width="stretch",
        key=f"dsm_overlay_{last.get('day')}_all_{last.get('preset')}_{last.get('mode')}",
    )
